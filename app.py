"""ScoreUp: evaluación única por club/evento, acceso QR y persistencia SQLite."""

import os
import secrets
import string
import uuid
import math
import threading
import re
from io import BytesIO
from pathlib import Path
from urllib.parse import urlsplit
from datetime import datetime

from flask import Flask, render_template, request, redirect, session, url_for, abort, flash, send_file, g, jsonify
from flask_wtf.csrf import CSRFProtect
from itsdangerous import URLSafeSerializer, BadSignature
from werkzeug.security import check_password_hash, generate_password_hash

import data as seed_data
import store
from calc import (
    ranking_evento, ranking_temporada, evaluacion_principal, actividad_staff,
    porcentaje_ponderado, fmt_pts, fmt_fecha, find,
)

app = Flask(__name__)
def _secret_key():
    configured = os.environ.get("SECRET_KEY") or os.environ.get("FLASK_SECRET")
    if configured:
        return configured
    if store.is_cloud():
        raise RuntimeError("SECRET_KEY es obligatoria en Vercel; configúrala como variable de entorno.")
    path = Path(__file__).with_name(".secret_key")
    try:
        with path.open("x", encoding="utf-8") as file:
            file.write(secrets.token_hex(32))
    except FileExistsError:
        pass
    return path.read_text(encoding="utf-8").strip()


app.secret_key = _secret_key()
app.config["TEMPLATES_AUTO_RELOAD"] = True
public_base = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")
if store.is_cloud() and not public_base:
    public_base = os.environ.get("VERCEL_URL", "").strip()
    if public_base and "://" not in public_base:
        public_base = "https://" + public_base
    public_base = public_base.rstrip("/")
app.config.update(MAX_CONTENT_LENGTH=10 * 1024 * 1024, SESSION_COOKIE_HTTPONLY=True,
                  SESSION_COOKIE_SAMESITE="Lax", PUBLIC_BASE_URL=public_base)
_db_lock = threading.RLock()
_accesos_generados = {}


@app.template_filter("club_nombre")
def _club_nombre(club_id, db):
    club = find(db, "clubs", "id", club_id)
    return club.nombre if club else club_id


@app.template_filter("pct")
def _pct(evaluacion, criterios):
    return porcentaje_ponderado(evaluacion, criterios)

DB = {} if store.is_cloud() else store.load()


def _verificar_clave(guardada, clave):
    """Acepta hash (werkzeug) o texto plano (datos antiguos en memoria)."""
    if guardada and guardada.startswith(("scrypt:", "pbkdf2:")):
        return check_password_hash(guardada, clave)
    return guardada == clave


@app.before_request
def _abrir_transaccion():
    """Recargar dentro del bloqueo evita notas duplicadas y estados obsoletos."""
    global DB
    _db_lock.acquire()
    g.db_locked = True
    g.connection = store.connect()
    store.begin(g.connection, write=request.method == "POST")
    DB = store.load(g.connection)
    user = current_user()
    if request.path.startswith(("/admin", "/staff", "/director")):
        if user is None:
            return redirect(url_for("login"))
    # Todas las operaciones que apuntan a un evento cerrado son inmutables.
    if request.method == "POST" and request.view_args and "evento_id" in request.view_args:
        evento = find(DB, "eventos", "id", request.view_args["evento_id"])
        if evento and evento.cerrado:
            abort(409, description="El evento está cerrado; no se permiten cambios.")
        if evento and request.endpoint in {"admin_evento_criterio", "admin_evento_criterio_peso", "admin_evento_criterio_eliminar"}:
            if any(e.evento_id == evento.id and e.oficial for e in DB["evaluaciones"]):
                abort(409, description="Los criterios no pueden cambiar después de empezar a evaluar.")


# Registrar CSRF después de la transacción para que cualquier error libere recursos.
CSRFProtect(app)


@app.after_request
def _confirmar_transaccion(response):
    conn = g.get("connection")
    if conn is not None:
        if request.method == "POST" and response.status_code < 400:
            store.save(DB, conn)
            conn.commit()
        else:
            conn.rollback()
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Cache-Control"] = "no-store"
    return response


@app.teardown_request
def _cerrar_transaccion(exc=None):
    conn = g.pop("connection", None)
    if conn is not None:
        conn.rollback()
        conn.close()
    if g.pop("db_locked", False):
        _db_lock.release()


@app.errorhandler(400)
@app.errorhandler(403)
@app.errorhandler(404)
@app.errorhandler(409)
@app.errorhandler(413)
def error_page(error):
    return render_template("error.html", error=error), error.code


def new_id(prefix):
    return f"{prefix}-{uuid.uuid4().hex}"


# --------------------------------------------------------------------------
# Utilidades de organización (multi-tenant)
# --------------------------------------------------------------------------

def _eventos_org(user):
    return [e for e in DB["eventos"] if e.organizacion_id == user.organizacion_id]


def _clubs_org(user):
    return [c for c in DB["clubs"] if c.organizacion_id == user.organizacion_id]


def db_org(user):
    """Vista de los datos aislada por organización (RNF-04 / RF-06)."""
    ev_ids = {e.id for e in _eventos_org(user)}
    cl_ids = {c.id for c in _clubs_org(user)}
    org = next((o for o in DB["organizaciones"] if o["id"] == user.organizacion_id), DB["organizaciones"][0])
    return {
        "organizacion": org,
        "clubs": _clubs_org(user),
        "users": [u for u in DB["users"] if u.organizacion_id == user.organizacion_id],
        "eventos": _eventos_org(user),
        "criterios": [c for c in DB["criterios"] if c.evento_id in ev_ids],
        "evento_club": [x for x in DB["evento_club"] if x.evento_id in ev_ids],
        "evaluaciones": [x for x in DB["evaluaciones"] if x.evento_id in ev_ids],
        "motivos": [m for m in DB["motivos"] if m.organizacion_id == user.organizacion_id],
        "penalizaciones": [p for p in DB["penalizaciones"] if p.evento_id in ev_ids and p.club_id in cl_ids],
        "incidentes": [i for i in DB["incidentes"] if i.evento_id in ev_ids],
        "organizaciones": [org],
        "correcciones": [r for r in DB["correcciones"] if r["evento_id"] in ev_ids],
    }


def generar_password(n=8):
    """Contraseña aleatoria (RF-04)."""
    chars = string.ascii_letters + string.digits
    return "".join(secrets.choice(chars) for _ in range(n))


def _username_unico(base):
    """Devuelve un username no utilizado agregando sufijo numérico."""
    i = 1
    candidato = base
    existentes = {u.username.lower() for u in DB["users"]}
    while candidato.lower() in existentes:
        i += 1
        candidato = f"{base}{i}"
    return candidato


# --------------------------------------------------------------------------
# Utilidades de sesión
# --------------------------------------------------------------------------

def current_user():
    uid = session.get("user_id")
    if not uid:
        return None
    return find(DB, "users", "id", uid)


def require_login():
    user = current_user()
    if user is None:
        return redirect(url_for("login"))
    return user


def require_rol(*roles):
    user = current_user()
    if user is None:
        return redirect(url_for("login"))
    if user.rol not in roles:
        abort(403)
    return user


def _safe_next(value):
    """Solo rutas locales, nunca una URL externa suministrada por el cliente."""
    if value and value.startswith("/") and not value.startswith("//") and "\\" not in value:
        parsed = urlsplit(value)
        if not parsed.scheme and not parsed.netloc:
            return value
    return None


def _club_participante(user, evento, club_id):
    club = find(DB, "clubs", "id", club_id)
    if (not club or club.organizacion_id != user.organizacion_id or
            not any(ec.evento_id == evento.id and ec.club_id == club_id for ec in DB["evento_club"])):
        abort(404, description="El club no participa en tu evento.")
    return club


@app.context_processor
def _avisos_admin():
    user = current_user()
    count = 0
    if user and user.rol == "admin":
        count = sum(r["estado"] == "pendiente" for r in db_org(user)["correcciones"])
    shell = {}
    if user and user.rol == "admin":
        view = db_org(user)
        shell = {
            "organizacion": view["organizacion"],
            "incidentes_abiertos": sum(i.estado == "abierto" for i in view["incidentes"]),
            "busqueda": [
                {"nombre": c.nombre, "tipo": "Club", "url": url_for("admin_club_miembros", club_id=c.id)}
                for c in view["clubs"]
            ] + [
                {"nombre": e.nombre, "tipo": "Evento", "url": url_for("admin_evento_detalle", evento_id=e.id)}
                for e in view["eventos"]
            ],
        }
    return {"correcciones_pendientes": count, "admin_shell": shell}


def _evento_abierto(user):
    evento = find(DB, "eventos", "id", user.evento_id)
    if not evento or evento.organizacion_id != user.organizacion_id:
        abort(403)
    if evento.cerrado:
        abort(409, description="El evento está cerrado.")
    return evento


def _token_club(club):
    # El ID es globalmente único; la organización se verifica en la base.
    # Evitar repetirla permite imprimir un QR considerablemente menos denso.
    return URLSafeSerializer(app.secret_key, salt="scoreup-club-qr-v2").dumps(club.id)


@app.route("/qr/<token>")
def qr_club(token):
    try:
        club_id = URLSafeSerializer(app.secret_key, salt="scoreup-club-qr-v2").loads(token)
    except BadSignature:
        # Compatibilidad con tarjetas descargadas antes de simplificar el QR.
        try:
            payload = URLSafeSerializer(app.secret_key, salt="scoreup-club-qr-v1").loads(token)
        except BadSignature:
            abort(404, description="El QR no es válido o su firma ha cambiado.")
        if not isinstance(payload, dict):
            abort(404)
        club_id = payload.get("club")
        legacy_club = find(DB, "clubs", "id", club_id)
        if not legacy_club or legacy_club.organizacion_id != payload.get("org"):
            abort(404)
    if not isinstance(club_id, str):
        abort(404)
    club = find(DB, "clubs", "id", club_id)
    if not club:
        abort(404)
    if current_user() is None:
        return redirect(url_for("login", next=request.path))
    user = require_rol("staff")
    evento = find(DB, "eventos", "id", user.evento_id)
    if not evento or evento.organizacion_id != user.organizacion_id:
        abort(403)
    _club_participante(user, evento, club.id)
    return redirect(url_for("panel_staff", club=club.id))


def _qr_base_url(value):
    base = value.strip().rstrip("/")
    try:
        parsed = urlsplit(base)
        valid_base = (parsed.scheme in {"http", "https"} and parsed.hostname and
                      not parsed.username and not parsed.password and
                      not parsed.path and not parsed.query and not parsed.fragment and
                      not any(c.isspace() or c == "\\" for c in base))
        parsed.port
    except ValueError:
        valid_base = False
    if not valid_base:
        abort(400, description="Usa una dirección como http://192.168.1.20:5000, sin rutas ni credenciales.")
    return base, parsed


def _club_qr_png(club, link, download=False):
    import io
    import qrcode

    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=12, border=6)
    qr.add_data(link)
    qr.make(fit=True)
    image = qr.make_image(fill_color="black", back_color="white")
    output = io.BytesIO()
    image.save(output, format="PNG")
    output.seek(0)
    return send_file(output, mimetype="image/png", as_attachment=download,
                     download_name=f"scoreup-{club.id}-qr.png")


@app.route("/admin/clubes/<club_id>/qr")
def admin_club_qr(club_id):
    user = require_rol("admin")
    club = find(DB, "clubs", "id", club_id)
    if not club or club.organizacion_id != user.organizacion_id:
        abort(404)
    base, parsed = _qr_base_url(request.args.get("base_url") or app.config["PUBLIC_BASE_URL"] or request.url_root)
    link = base + url_for("qr_club", token=_token_club(club))
    if request.args.get("formato") == "png":
        return _club_qr_png(club, link, download=True)
    return render_template("admin/club_qr.html", club=club, link=link, user=user,
                           base_url=base, local_host=parsed.hostname in {"localhost", "127.0.0.1", "0.0.0.0", "::1", "::"})


# --------------------------------------------------------------------------
# Autenticación
# --------------------------------------------------------------------------

@app.route("/")
def index():
    if current_user():
        return redirect(url_for(f"panel_{current_user().rol}"))
    return render_template("index.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    next_path = _safe_next(request.form.get("next") or request.args.get("next"))
    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")
        for u in DB["users"]:
            if u.username.lower() == username and _verificar_clave(u.password, password):
                session.clear()
                session["user_id"] = u.id
                return redirect(next_path or url_for(f"panel_{u.rol}"))
        return render_template("login.html", error="Usuario o contraseña incorrectos.", next_path=next_path)
    return render_template("login.html", error=None, next_path=next_path)


@app.route("/registro", methods=["GET", "POST"])
def registro():
    """RF-01 / Diagrama 1: auto-registro de Admin + creación de organización."""
    if current_user():
        return redirect(url_for(f"panel_{current_user().rol}"))
    if request.method == "POST":
        nombre = request.form.get("nombre", "").strip()
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")
        org_nombre = request.form.get("organizacion", "").strip()
        if not (nombre and username and password and org_nombre):
            return render_template("registro.html", error="Completa todos los campos.")
        if len(password) < 4:
            return render_template("registro.html", error="La contraseña debe tener al menos 4 caracteres.")
        if any(u.username.lower() == username for u in DB["users"]):
            return render_template("registro.html", error="Ese nombre de usuario ya está en uso.")
        org_id = new_id("org")
        DB["organizaciones"].append({
            "id": org_id,
            "nombre": org_nombre,
            "fecha_creacion": datetime.now().strftime("%Y-%m-%d"),
        })
        admin = seed_data.Usuario(new_id("user"), org_id, nombre, username, generate_password_hash(password), "admin")
        DB["users"].append(admin)
        session["user_id"] = admin.id
        flash("¡Cuenta de Admin y organización creadas correctamente!", "ok")
        return redirect(url_for("panel_admin"))
    return render_template("registro.html", error=None)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# --------------------------------------------------------------------------
# ADMIN
# --------------------------------------------------------------------------

@app.route("/admin")
def panel_admin():
    user = require_rol("admin")
    view = db_org(user)
    hoy = datetime.now().strftime("%Y-%m-%d")
    activos = [e for e in view["eventos"] if not e.cerrado]
    proximos = sorted([e for e in view["eventos"] if e.fecha >= hoy], key=lambda e: e.fecha)
    total_miembros = sum(len(c.miembros) for c in view["clubs"])
    staff_evento = [u for u in view["users"] if u.rol == "staff" and u.evento_id]
    temporadas = sorted({e.temporada for e in view["eventos"]}, reverse=True)
    temporada = request.args.get("temporada", temporadas[0] if temporadas else datetime.now().strftime("%Y"))
    if temporadas and temporada not in temporadas:
        abort(404, description="La temporada no existe en tu organización.")
    progreso_eventos = []
    pendientes = 0
    inscripciones_abiertas = 0
    meses = ["ENE", "FEB", "MAR", "ABR", "MAY", "JUN", "JUL", "AGO", "SEP", "OCT", "NOV", "DIC"]
    for evento in sorted(view["eventos"], key=lambda e: e.fecha, reverse=True):
        inscritos = [ec for ec in view["evento_club"] if ec.evento_id == evento.id]
        evaluados = sum(evaluacion_principal(view, evento, ec.club_id) is not None for ec in inscritos)
        faltan = len(inscritos) - evaluados
        if not evento.cerrado:
            pendientes += faltan
            inscripciones_abiertas += len(inscritos)
        try:
            fecha = datetime.strptime(evento.fecha, "%Y-%m-%d")
            dia, mes = fecha.strftime("%d"), meses[fecha.month - 1]
        except ValueError:
            dia, mes = "—", "S/F"
        progreso_eventos.append({"evento": evento, "clubes": len(inscritos), "evaluados": evaluados,
                                "pendientes": faltan, "avance": round(100 * evaluados / len(inscritos)) if inscritos else 0,
                                "dia": dia, "mes": mes})
    ranking = ranking_temporada(view, temporada)["filas"]
    eventos_temporada = {e.id for e in view["eventos"] if e.temporada == temporada}
    hay_notas = any(e.oficial and e.evento_id in eventos_temporada for e in view["evaluaciones"])
    posiciones = {}
    for fila in ranking:
        posiciones[fila["posicion"]] = posiciones.get(fila["posicion"], 0) + 1
    empates = [{"posicion": p, "clubes": n} for p, n in posiciones.items() if n > 1]
    abiertos = [i for i in view["incidentes"] if i.estado == "abierto"]
    hora = datetime.now().hour
    saludo = "Buenos días" if hora < 12 else ("Buenas tardes" if hora < 19 else "Buenas noches")
    return render_template("admin/dashboard.html", user=user, db=view, activos=activos,
                           proximos=proximos, total_miembros=total_miembros,
                           staff_evento=len(staff_evento), fmt_fecha=fmt_fecha, fmt_pts=fmt_pts,
                           temporadas=temporadas, temporada=temporada, ranking=ranking[:5], hay_notas=hay_notas,
                           empates=empates, ranking_provisional=any(e.id in eventos_temporada and not e.cerrado for e in view["eventos"]),
                           progreso_eventos=progreso_eventos[:4], pendientes=pendientes,
                           inscripciones_abiertas=inscripciones_abiertas, abiertos=abiertos,
                           graves=sum(i.gravedad == "grave" for i in abiertos), saludo=saludo)


@app.route("/admin/clubes", methods=["GET", "POST"])
def admin_clubes():
    user = require_rol("admin")
    if request.method == "POST":
        nombre = request.form.get("nombre", "").strip()
        if nombre:
            DB["clubs"].append(seed_data.Club(new_id("club"), nombre, user.organizacion_id, []))
        return redirect(url_for("admin_clubes"))
    return render_template("admin/clubes.html", user=user, db=db_org(user))


@app.route("/admin/clubes/<club_id>/editar", methods=["POST"])
def admin_club_editar(club_id):
    user = require_rol("admin")
    club = find(DB, "clubs", "id", club_id)
    if club and club.organizacion_id == user.organizacion_id:
        club.nombre = request.form.get("nombre", club.nombre).strip() or club.nombre
    return redirect(url_for("admin_clubes"))


@app.route("/admin/clubes/<club_id>/eliminar", methods=["POST"])
def admin_club_eliminar(club_id):
    """RF-07: el Admin puede eliminar un club de su organización."""
    user = require_rol("admin")
    club = find(DB, "clubs", "id", club_id)
    if club and club.organizacion_id == user.organizacion_id:
        if any(ec.club_id == club_id and find(DB, "eventos", "id", ec.evento_id).cerrado for ec in DB["evento_club"]):
            abort(409, description="No se puede eliminar un club con resultados cerrados.")
        DB["clubs"] = [c for c in DB["clubs"] if c.id != club_id]
        DB["evento_club"] = [x for x in DB["evento_club"] if x.club_id != club_id]
        DB["evaluaciones"] = [e for e in DB["evaluaciones"] if e.club_id != club_id]
        DB["penalizaciones"] = [p for p in DB["penalizaciones"] if p.club_id != club_id]
        DB["incidentes"] = [i for i in DB["incidentes"] if i.club_id != club_id]
        DB["users"] = [u for u in DB["users"] if not (u.rol == "director" and u.club_id == club_id)]
    return redirect(url_for("admin_clubes"))


@app.route("/admin/miembros")
def admin_miembros():
    user = require_rol("admin")
    view = db_org(user)
    miembros = [{"club": club, "miembro": miembro} for club in view["clubs"] for miembro in club.miembros]
    return render_template("admin/miembros.html", user=user, db=view, miembros=miembros)


@app.route("/admin/clubes/<club_id>/miembros", methods=["GET"])
def admin_club_miembros(club_id):
    user = require_rol("admin")
    club = find(DB, "clubs", "id", club_id)
    if not club or club.organizacion_id != user.organizacion_id:
        abort(404)
    q = request.args.get("q", "").strip().lower()
    cat = request.args.get("cat", "")
    lista = club.miembros
    if q:
        lista = [m for m in lista if q in m.nombre.lower()]
    if cat:
        lista = [m for m in lista if m.categoria == cat]
    return render_template("admin/club_miembros.html", user=user, db=db_org(user), club=club,
                           lista=lista, fmt_fecha=fmt_fecha)


@app.route("/admin/clubes/<club_id>/miembros/nuevo", methods=["POST"])
def admin_club_miembro_nuevo(club_id):
    user = require_rol("admin")
    club = find(DB, "clubs", "id", club_id)
    if club and club.organizacion_id == user.organizacion_id and request.form.get("nombre", "").strip():
        club.miembros.append(seed_data.Miembro(
            new_id("m"),
            request.form["nombre"].strip(),
            int(request.form.get("edad") or 0) or None,
            request.form.get("cargo", "").strip(),
            int(request.form.get("anio_ingreso") or 0) or None,
            request.form.get("categoria", "Explorador"),
        ))
    return redirect(url_for("admin_club_miembros", club_id=club_id))


@app.route("/admin/clubes/<club_id>/miembros/<miembro_id>/eliminar", methods=["POST"])
def admin_club_miembro_eliminar(club_id, miembro_id):
    user = require_rol("admin")
    club = find(DB, "clubs", "id", club_id)
    if club and club.organizacion_id == user.organizacion_id:
        club.miembros = [m for m in club.miembros if m.id != miembro_id]
    return redirect(url_for("admin_club_miembros", club_id=club_id))


@app.route("/admin/eventos", methods=["GET", "POST"])
def admin_eventos():
    user = require_rol("admin")
    if request.method == "POST":
        nombre = request.form.get("nombre", "").strip()
        try:
            puntaje_maximo = int(request.form.get("puntaje_maximo") or 320)
        except (TypeError, ValueError):
            puntaje_maximo = 320
        if puntaje_maximo <= 0:
            abort(400, description="El puntaje máximo debe ser positivo.")
        if nombre:
            DB["eventos"].append(seed_data.Evento(
                new_id("ev"), user.organizacion_id, nombre,
                request.form.get("fecha", ""),
                request.form.get("lugar", ""),
                request.form.get("tipo", "otro"),
                request.form.get("temporada", "2026"),
                puntaje_maximo,
            ))
        return redirect(url_for("admin_eventos"))
    view = db_org(user)
    eventos = sorted(view["eventos"], key=lambda e: e.fecha, reverse=True)
    return render_template("admin/eventos.html", user=user, db=view, eventos=eventos,
                           fmt_fecha=fmt_fecha)


@app.route("/admin/eventos/<evento_id>")
def admin_evento_detalle(evento_id):
    user = require_rol("admin")
    view = db_org(user)
    evento = find(view, "eventos", "id", evento_id)
    if not evento:
        abort(404)
    criterios = [c for c in view["criterios"] if c.evento_id == evento.id]
    ecs = [x for x in view["evento_club"] if x.evento_id == evento.id]
    staffs = [u for u in view["users"] if u.rol == "staff" and u.evento_id == evento.id]
    pendientes = []
    for ec in ecs:
        if not any(e.evento_id == evento.id and e.club_id == ec.club_id and e.oficial
                   for e in view["evaluaciones"]):
            pendientes.append(ec)
    act = actividad_staff(db=view, evento=evento)
    suma_pesos = sum(c.peso for c in criterios)
    creados = _accesos_generados.pop(user.id, None)
    return render_template("admin/evento_detalle.html", user=user, db=view, evento=evento,
                           criterios=criterios, ecs=ecs, staffs=staffs, pendientes=pendientes,
                           act=act, suma_pesos=suma_pesos, creados=creados,
                           fmt_fecha=fmt_fecha, fmt_pts=fmt_pts)


@app.route("/admin/eventos/<evento_id>/criterio", methods=["POST"])
def admin_evento_criterio(evento_id):
    user = require_rol("admin")
    nombre = request.form.get("nombre", "").strip()
    peso = request.form.get("peso")
    evento = find(DB, "eventos", "id", evento_id)
    if evento and evento.organizacion_id != user.organizacion_id:
        abort(404)
    if evento and nombre and peso:
        try:
            peso = float(peso)
        except (TypeError, ValueError):
            peso = None
        if peso is None or not math.isfinite(peso) or not 0 < peso <= 100:
            abort(400, description="El peso debe ser un número mayor que 0 y menor o igual a 100.")
        if peso is not None and math.isfinite(peso) and 0 < peso <= 100:
            suma = sum(c.peso for c in DB["criterios"] if c.evento_id == evento.id) + peso
            if suma > 100:
                flash(f"No se puede añadir: la suma de pesos superaría 100% ({suma:.1f}%).", "err")
            else:
                DB["criterios"].append(seed_data.Criterio(new_id("cr"), evento.id, nombre, peso))
    return redirect(url_for("admin_evento_detalle", evento_id=evento_id))


@app.route("/admin/eventos/<evento_id>/criterio/<criterio_id>/peso", methods=["POST"])
def admin_evento_criterio_peso(evento_id, criterio_id):
    user = require_rol("admin")
    evento = find(DB, "eventos", "id", evento_id)
    if not evento or evento.organizacion_id != user.organizacion_id:
        abort(404)
    crit = find(DB, "criterios", "id", criterio_id)
    if crit and crit.evento_id == evento.id:
        try:
            nuevo = float(request.form.get("peso"))
        except (TypeError, ValueError):
            nuevo = None
        if nuevo is None or not math.isfinite(nuevo) or not 0 < nuevo <= 100:
            abort(400, description="El peso debe estar entre 0 y 100, sin incluir 0.")
        if nuevo is not None and math.isfinite(nuevo) and 0 < nuevo <= 100:
            suma = sum(c.peso for c in DB["criterios"] if c.evento_id == evento.id and c.id != crit.id) + nuevo
            if suma > 100:
                flash(f"Peso no aplicado: la suma superaría 100% ({suma:.1f}%).", "err")
            else:
                crit.peso = nuevo
    return redirect(url_for("admin_evento_detalle", evento_id=evento_id))


@app.route("/admin/eventos/<evento_id>/criterio/<criterio_id>/eliminar", methods=["POST"])
def admin_evento_criterio_eliminar(evento_id, criterio_id):
    user = require_rol("admin")
    evento = find(DB, "eventos", "id", evento_id)
    if not evento or evento.organizacion_id != user.organizacion_id:
        abort(404)
    DB["criterios"] = [c for c in DB["criterios"] if not (c.id == criterio_id and c.evento_id == evento.id)]
    return redirect(url_for("admin_evento_detalle", evento_id=evento_id))


@app.route("/admin/eventos/<evento_id>/asignar", methods=["POST"])
def admin_evento_asignar(evento_id):
    user = require_rol("admin")
    club_id = request.form.get("club_id")
    staff_id = None  # Compatibilidad del esquema; ya no se asigna staff principal.
    evento = find(DB, "eventos", "id", evento_id)
    if not evento or evento.organizacion_id != user.organizacion_id:
        abort(404)
    if club_id and any(c.id == club_id and c.organizacion_id == user.organizacion_id for c in DB["clubs"]):
        ec = None
        for x in DB["evento_club"]:
            if x.evento_id == evento_id and x.club_id == club_id:
                ec = x
        if ec:
            if staff_id:
                ec.staff_principal_id = staff_id
        else:
            DB["evento_club"].append(seed_data.EventoClub(new_id("ec"), evento_id, club_id, staff_id))
    return redirect(url_for("admin_evento_detalle", evento_id=evento_id))


@app.route("/admin/eventos/<evento_id>/desasignar/<club_id>", methods=["POST"])
def admin_evento_desasignar(evento_id, club_id):
    user = require_rol("admin")
    evento = find(DB, "eventos", "id", evento_id)
    if not evento or evento.organizacion_id != user.organizacion_id:
        abort(404)
    if any(e.evento_id == evento_id and e.club_id == club_id and e.oficial for e in DB["evaluaciones"]):
        abort(409, description="No se puede quitar un club que ya fue evaluado.")
    DB["evento_club"] = [x for x in DB["evento_club"] if not (x.evento_id == evento_id and x.club_id == club_id)]
    return redirect(url_for("admin_evento_detalle", evento_id=evento_id))


@app.route("/admin/eventos/<evento_id>/staff", methods=["POST"])
def admin_evento_staff(evento_id):
    require_rol("admin")
    abort(409, description="La asignación de staff principal fue reemplazada por evaluación mediante QR.")


@app.route("/admin/eventos/<evento_id>/cerrar", methods=["POST"])
def admin_evento_cerrar(evento_id):
    """RF-15/RN-01: cierra el evento. Bloqueado si los pesos no suman 100%."""
    user = require_rol("admin")
    evento = find(DB, "eventos", "id", evento_id)
    if not evento or evento.organizacion_id != user.organizacion_id:
        abort(404)
    if not evento.cerrado:
        suma = sum(c.peso for c in DB["criterios"] if c.evento_id == evento.id)
        if abs(suma - 100) > 0.001:
            flash(f"No se puede cerrar: la suma de pesos es {suma:.1f}% y debe ser 100%.", "err")
        else:
            participantes = [ec for ec in DB["evento_club"] if ec.evento_id == evento.id]
            if not participantes or any(evaluacion_principal(DB, evento, ec.club_id) is None for ec in participantes):
                abort(409, description="Todos los clubes participantes deben estar evaluados antes de cerrar.")
            evento.cerrado = True
            flash("Evaluaciones cerradas. Ya no se pueden modificar datos del evento.", "ok")
    return redirect(url_for("admin_evento_detalle", evento_id=evento_id))


@app.route("/admin/eventos/<evento_id>/generar-accesos", methods=["POST"])
def admin_evento_generar_accesos(evento_id):
    """RF-04 / Diagrama 3: genera masivamente usuarios y contraseñas aleatorias
    para staff (n solicitado) y para los directores de los clubes participantes."""
    user = require_rol("admin")
    evento = find(DB, "eventos", "id", evento_id)
    if not evento or evento.organizacion_id != user.organizacion_id:
        abort(404)
    try:
        n_staff = max(0, int(request.form.get("n_staff", 0) or 0))
    except (TypeError, ValueError):
        n_staff = 0
    if n_staff > 25:
        n_staff = 25

    creados = []
    ecs = [x for x in DB["evento_club"] if x.evento_id == evento.id]

    for i in range(1, n_staff + 1):
        username = _username_unico(f"staff{evento.temporada}")
        passw = generar_password()
        nombre = f"Staff {evento.nombre} · #{i}"
        DB["users"].append(seed_data.Usuario(new_id("user"), user.organizacion_id, nombre,
                                             username, passw, "staff", evento_id=evento.id))
        creados.append({"rol": "Staff", "nombre": nombre, "username": username, "password": passw, "club": ""})

    for ec in ecs:
        club = find(DB, "clubs", "id", ec.club_id) if ec.club_id else None
        ya_tiene_director = any(u.rol == "director" and u.club_id == ec.club_id for u in DB["users"])
        if club and not ya_tiene_director:
            username = _username_unico(f"dir{evento.temporada}")
            passw = generar_password()
            nombre = f"Director {club.nombre}"
            DB["users"].append(seed_data.Usuario(new_id("user"), user.organizacion_id, nombre,
                                                 username, passw, "director", club_id=club.id,
                                                 evento_id=evento.id))
            creados.append({"rol": "Director", "nombre": nombre, "username": username,
                            "password": passw, "club": club.nombre})

    if not creados:
        flash("No se generaron accesos: indica cuántos Staff crear (los directores ya existen).", "err")
    else:
        _accesos_generados[user.id] = creados
        flash(f"Se generaron {len(creados)} accesos. Los verás en el detalle del evento para imprimir/compartir.", "ok")
    return redirect(url_for("admin_evento_detalle", evento_id=evento_id))


@app.route("/admin/eventos/<evento_id>/staff/nuevo", methods=["POST"])
def admin_evento_staff_nuevo(evento_id):
    """Crea un usuario Staff manualmente con el usuario y contraseña elegidos por el Admin."""
    user = require_rol("admin")
    evento = find(DB, "eventos", "id", evento_id)
    if not evento or evento.organizacion_id != user.organizacion_id:
        abort(404)
    nombre = request.form.get("nombre", "").strip()
    username = request.form.get("username", "").strip().lower()
    password = request.form.get("password", "")
    if not (nombre and username and password):
        flash("Faltan datos: nombre, usuario y contraseña son obligatorios.", "err")
    elif len(password) < 4:
        flash("La contraseña debe tener al menos 4 caracteres.", "err")
    elif any(u.username.lower() == username for u in DB["users"]):
        flash(f"El usuario '{username}' ya está en uso.", "err")
    else:
        DB["users"].append(seed_data.Usuario(new_id("user"), user.organizacion_id, nombre,
                                             username, password, "staff", evento_id=evento.id))
        flash(f"Staff '{nombre}' creado con usuario '{username}'.", "ok")
    return redirect(url_for("admin_evento_detalle", evento_id=evento_id))


@app.route("/admin/eventos/<evento_id>/staff/importar", methods=["POST"])
def admin_evento_importar_staff(evento_id):
    """Importa Staff desde un Excel (columnas: nombre, username, password)."""
    user = require_rol("admin")
    evento = find(DB, "eventos", "id", evento_id)
    if not evento or evento.organizacion_id != user.organizacion_id:
        abort(404)
    f = request.files.get("archivo")
    if not f or not f.filename:
        return redirect(url_for("admin_evento_detalle", evento_id=evento_id))
    ext = f.filename.rsplit(".", 1)[-1].lower() if "." in f.filename else ""
    if ext not in {"xlsx", "xlsm"}:
        flash("El archivo debe ser .xlsx", "err")
        return redirect(url_for("admin_evento_detalle", evento_id=evento_id))
    try:
        from openpyxl import load_workbook
        wb = load_workbook(filename=f, data_only=True)
        ws = wb.active
        filas = list(ws.iter_rows(values_only=True))
        errors = []
        importados = 0
        for idx, row in enumerate(filas[1:], start=2):
            if not row or not row[0]:
                continue
            row = tuple(row) + (None,) * max(0, 3 - len(row))
            nombre = str(row[0]).strip()
            username = str(row[1]).strip().lower() if row[1] else ""
            password = str(row[2]).strip() if row[2] else ""
            if not (nombre and username and password):
                errors.append(f"Fila {idx}: faltan datos (nombre, usuario, contraseña)")
                continue
            if len(password) < 4:
                errors.append(f"Fila {idx}: contraseña muy corta (mínimo 4)")
                continue
            if any(u.username.lower() == username for u in DB["users"]):
                errors.append(f"Fila {idx}: el usuario '{username}' ya existe")
                continue
            DB["users"].append(seed_data.Usuario(new_id("user"), user.organizacion_id, nombre,
                                                 username, password, "staff", evento_id=evento.id))
            importados += 1
        msg = f"Se importaron {importados} staff."
        if errors:
            msg += " Errores: " + "; ".join(errors[:5])
        flash(msg, "ok" if importados else "err")
    except Exception as exc:
        flash(f"No se pudo leer el archivo: {exc}", "err")
    return redirect(url_for("admin_evento_detalle", evento_id=evento_id))


@app.route("/plantilla-staff.xlsx")
def plantilla_staff():
    from openpyxl import Workbook
    from openpyxl.utils import get_column_letter
    import io

    wb = Workbook()
    ws = wb.active
    ws.title = "Staff"
    headers = ["nombre", "username", "password"]
    ws.append(headers)
    ws.append(["Staff Ejemplo 1", "staff2026a", "clave123"])
    ws.append(["Staff Ejemplo 2", "staff2026b", "clave456"])
    for col in range(1, len(headers) + 1):
        ws.column_dimensions[get_column_letter(col)].width = 24
    bio = io.BytesIO()
    wb.save(bio)
    bio.seek(0)
    return send_file(bio, as_attachment=True, download_name="plantilla-staff.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@app.route("/admin/incidentes")
def admin_incidentes():
    user = require_rol("admin")
    view = db_org(user)
    incidentes = list(view["incidentes"])
    f_evento = request.args.get("evento")
    f_club = request.args.get("club")
    f_tipo = request.args.get("tipo")
    f_gravedad = request.args.get("gravedad")
    f_estado = request.args.get("estado")
    if f_evento:
        incidentes = [i for i in incidentes if i.evento_id == f_evento]
    if f_club:
        incidentes = [i for i in incidentes if i.club_id == f_club]
    if f_tipo:
        incidentes = [i for i in incidentes if i.tipo == f_tipo]
    if f_gravedad:
        incidentes = [i for i in incidentes if i.gravedad == f_gravedad]
    if f_estado:
        incidentes = [i for i in incidentes if i.estado == f_estado]
    return render_template("admin/incidentes.html", user=user, db=view, incidentes=incidentes,
                           filtros=request.args, fmt_fecha=fmt_fecha)


@app.route("/admin/incidentes/<incidente_id>/estado", methods=["POST"])
def admin_incidente_estado(incidente_id):
    user = require_rol("admin")
    inc = find(DB, "incidentes", "id", incidente_id)
    ev_ids = {e.id for e in _eventos_org(user)}
    estado = request.form.get("estado")
    if inc and inc.evento_id in ev_ids and estado in ("abierto", "en_revision", "resuelto"):
        inc.estado = estado
    return redirect(url_for("admin_incidentes"))


@app.route("/admin/penalizaciones/motivos", methods=["GET", "POST"])
def admin_motivos():
    user = require_rol("admin")
    if request.method == "POST":
        nombre = request.form.get("nombre", "").strip()
        if nombre:
            try:
                puntos = float(request.form.get("puntos_descuento") or 0)
            except (TypeError, ValueError):
                puntos = 0.0
            if not math.isfinite(puntos) or puntos < 0:
                abort(400, description="El descuento debe ser un número no negativo.")
            DB["motivos"].append(seed_data.MotivoPenalizacion(
                new_id("mp"), user.organizacion_id, nombre,
                request.form.get("descripcion", ""),
                puntos,
            ))
        return redirect(url_for("admin_motivos"))
    return render_template("admin/motivos.html", user=user, db=db_org(user), fmt_pts=fmt_pts)


@app.route("/admin/penalizaciones/motivos/<motivo_id>", methods=["POST"])
def admin_motivo_editar(motivo_id):
    user = require_rol("admin")
    m = find(DB, "motivos", "id", motivo_id)
    if m and m.organizacion_id == user.organizacion_id:
        m.nombre = request.form.get("nombre", m.nombre).strip() or m.nombre
        m.descripcion = request.form.get("descripcion", m.descripcion)
        try:
            puntos = float(request.form.get("puntos_descuento", m.puntos_descuento))
            if not math.isfinite(puntos) or puntos < 0:
                abort(400, description="El descuento debe ser un número no negativo.")
            m.puntos_descuento = puntos
        except (TypeError, ValueError):
            pass
        m.activo = request.form.get("activo") == "on"
    return redirect(url_for("admin_motivos"))


@app.route("/admin/penalizaciones")
def admin_penalizaciones():
    user = require_rol("admin")
    view = db_org(user)
    lista = list(view["penalizaciones"])
    f_evento = request.args.get("evento")
    f_club = request.args.get("club")
    f_staff = request.args.get("staff")
    if f_evento:
        lista = [p for p in lista if p.evento_id == f_evento]
    if f_club:
        lista = [p for p in lista if p.club_id == f_club]
    if f_staff:
        lista = [p for p in lista if p.usuario_id == f_staff]
    return render_template("admin/penalizaciones.html", user=user, db=view, fmt_pts=fmt_pts, fmt_fecha=fmt_fecha,
                           filtros=request.args, lista=lista)


@app.route("/admin/penalizaciones/<penalizacion_id>/anular", methods=["POST"])
def admin_penalizacion_anular(penalizacion_id):
    user = require_rol("admin")
    p = find(DB, "penalizaciones", "id", penalizacion_id)
    if p:
        evento = find(DB, "eventos", "id", p.evento_id)
        if evento and evento.organizacion_id == user.organizacion_id:
            if evento.cerrado:
                abort(409, description="No se pueden anular penalizaciones de un evento cerrado.")
            DB["penalizaciones"] = [x for x in DB["penalizaciones"] if x.id != penalizacion_id]
    return redirect(url_for("admin_penalizaciones"))


@app.route("/admin/resultados")
def admin_resultados():
    user = require_rol("admin")
    view = db_org(user)
    temporada = request.args.get("temporada", view["eventos"][0].temporada if view["eventos"] else "2026")
    vista = request.args.get("vista", "temporada")
    evento_id = request.args.get("evento_id")
    evento = find(view, "eventos", "id", evento_id) if evento_id else None
    ranking = ranking_temporada(view, temporada)
    ranking_ev = ranking_evento(view, evento) if evento else None
    criterios_ev = [c for c in view["criterios"] if c.evento_id == evento_id] if evento else []
    return render_template("admin/resultados.html", user=user, db=view, temporada=temporada,
                           vista=vista, evento=evento, ranking=ranking,
                           ranking_ev=ranking_ev, criterios_ev=criterios_ev,
                           fmt_pts=fmt_pts, fmt_fecha=fmt_fecha)


@app.route("/admin/mostrar-resultado")
def admin_mostrar_resultado():
    user = require_rol("admin")
    view = db_org(user)
    scope = request.args.get("scope", "temporada")
    evento_id = request.args.get("evento_id")
    evento = find(view, "eventos", "id", evento_id) if evento_id else None
    if scope == "evento" and evento:
        filas = ranking_evento(view, evento)
    else:
        t = request.args.get("temporada", view["eventos"][0].temporada if view["eventos"] else "2026")
        filas = ranking_temporada(view, t)["filas"]
    template = "admin/proyeccion_pantalla.html" if request.args.get("pantalla") == "1" else "admin/mostrar_resultado.html"
    return render_template(template, user=user, db=view, scope=scope,
                            filas=filas, evento=evento, fmt_pts=fmt_pts)


@app.route("/admin/reportes")
def admin_reportes():
    user = require_rol("admin")
    view = db_org(user)
    tipo = request.args.get("tipo", "correcciones")
    temporada = request.args.get("temporada", view["eventos"][0].temporada if view["eventos"] else "2026")
    ranking = ranking_temporada(view, temporada)
    actividad = [(e, actividad_staff(view, e)) for e in view["eventos"]]
    return render_template("admin/reportes.html", user=user, db=view, tipo=tipo, temporada=temporada,
                           ranking=ranking, actividad=actividad,
                            fmt_pts=fmt_pts, fmt_fecha=fmt_fecha)


@app.route("/admin/reportes/<reporte_id>/estado", methods=["POST"])
def admin_reporte_estado(reporte_id):
    user = require_rol("admin")
    reporte = next((r for r in db_org(user)["correcciones"] if r["id"] == reporte_id), None)
    if not reporte:
        abort(404)
    estado = request.form.get("estado")
    if estado not in {"revisado", "descartado"}:
        abort(400)
    reporte["estado"] = estado
    flash("Notificación actualizada. La evaluación vigente no cambia.", "ok")
    return redirect(url_for("admin_reportes", tipo="correcciones"))


# --------------------------------------------------------------------------
# Exportar resultados a Excel / PDF (RF-23, Diagrama 12)
# --------------------------------------------------------------------------

def _datos_exportar(user):
    """Devuelve (titulo, cabeceras, filas) del ranking según la vista elegida."""
    view = db_org(user)
    vista = request.args.get("vista", "temporada")
    if vista == "evento":
        evento = find(view, "eventos", "id", request.args.get("evento_id")) if request.args.get("evento_id") else None
        if not evento:
            abort(404)
        r = ranking_evento(view, evento)
        criterios = [c for c in view["criterios"] if c.evento_id == evento.id]
        cab = ["#", "Club"] + [c.nombre for c in criterios] + ["% ponderado", "Puntaje"]
        filas = []
        for f in r:
            fila = [f["posicion"], f["club"].nombre]
            for c in criterios:
                fila.append(f["evaluacion"].valores.get(c.id, "") if f["evaluacion"] else "")
            fila.append(round(f["porcentaje"], 1))
            fila.append(f["puntaje"])
            filas.append(fila)
        return f"Ranking evento: {evento.nombre}", cab, filas
    t = request.args.get("temporada", view["eventos"][0].temporada if view["eventos"] else "2026")
    r = ranking_temporada(view, t)
    cab = ["#", "Club"] + [e.nombre for e in r["eventos"]] + ["Bruto", "Penalizaciones", "Total"]
    filas = []
    for f in r["filas"]:
        fila = [f["posicion"], f["club"].nombre]
        for e in r["eventos"]:
            fila.append(f["por_evento"].get(e.id, 0))
        fila.append(f["bruto"])
        fila.append(-f["penalizaciones"])
        fila.append(f["puntaje"])
        filas.append(fila)
    return f"Ranking de temporada {t}", cab, filas


@app.route("/admin/exportar")
def admin_exportar():
    user = require_rol("admin")
    formato = request.args.get("formato", "excel")
    titulo, cab, filas = _datos_exportar(user)
    org = db_org(user)["organizacion"]["nombre"]

    if formato == "excel":
        from openpyxl import Workbook
        from openpyxl.utils import get_column_letter
        from openpyxl.styles import Font, PatternFill, Alignment
        import io as _io
        wb = Workbook()
        ws = wb.active
        ws.title = "Resultados"
        ws.append([org])
        ws.append([titulo])
        ws.append([])
        ws.append(cab)
        for f in filas:
            ws.append(f)
        for col in range(1, len(cab) + 1):
            cell = ws.cell(row=4, column=col)
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="0E7490")
            cell.alignment = Alignment(horizontal="center")
            ws.column_dimensions[get_column_letter(col)].width = 22
        bio = _io.BytesIO()
        wb.save(bio)
        bio.seek(0)
        return send_file(bio, as_attachment=True, download_name=f"scoreup-{titulo.replace(' ', '_')}.xlsx",
                         mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    # PDF
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet
    import io as _io

    bio = _io.BytesIO()
    doc = SimpleDocTemplate(bio, pagesize=landscape(A4), title=f"ScoreUp - {titulo}")
    styles = getSampleStyleSheet()
    elementos = [Paragraph(f"<b>{org}</b>", styles["Title"]),
                 Paragraph(titulo, styles["Heading2"]), Spacer(1, 4 * mm)]
    tabla = Table([[Paragraph(str(x), styles["Normal"]) for x in cab]] + filas, repeatRows=1)
    tabla.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0E7490")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F1F5F9")]),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    elementos.append(tabla)
    doc.build(elementos)
    bio.seek(0)
    return send_file(bio, as_attachment=True, download_name=f"scoreup-{titulo.replace(' ', '_')}.pdf",
                     mimetype="application/pdf")


# --------------------------------------------------------------------------
# USUARIOS (Staff y Directores)
# --------------------------------------------------------------------------

@app.route("/admin/usuarios")
def admin_usuarios():
    """Lista los usuarios de la organización y permite crear Staff/Director (RF-04)."""
    user = require_rol("admin")
    view = db_org(user)
    usuarios = sorted(view["users"], key=lambda u: (u.rol, u.nombre))
    return render_template("admin/usuarios.html", user=user, db=view, usuarios=usuarios,
                           fmt_fecha=fmt_fecha)


@app.route("/admin/usuarios/nuevo", methods=["POST"])
def admin_usuario_nuevo():
    """Crea manualmente un usuario Staff (asignado a un evento) o Director (asignado a un club)."""
    user = require_rol("admin")
    nombre = request.form.get("nombre", "").strip()
    username = request.form.get("username", "").strip().lower()
    password = request.form.get("password", "")
    rol = request.form.get("rol", "")
    evento_id = request.form.get("evento_id") or None
    club_id = request.form.get("club_id") or None

    if rol not in ("staff", "director"):
        flash("Rol inválido. Elige Staff o Director.", "err")
    elif not (nombre and username and password):
        flash("Faltan datos: nombre, usuario y contraseña son obligatorios.", "err")
    elif len(password) < 4:
        flash("La contraseña debe tener al menos 4 caracteres.", "err")
    elif any(u.username.lower() == username for u in DB["users"]):
        flash(f"El usuario '{username}' ya está en uso.", "err")
    else:
        evento_valido = None
        if evento_id:
            ev = next((e for e in DB["eventos"]
                       if e.id == evento_id and e.organizacion_id == user.organizacion_id), None)
            if ev:
                evento_valido = ev.id
        club_valido = None
        if club_id:
            cl = next((c for c in DB["clubs"]
                       if c.id == club_id and c.organizacion_id == user.organizacion_id), None)
            if cl:
                club_valido = cl.id

        if rol == "staff" and not evento_valido:
            flash("Selecciona un evento válido de tu organización.", "err")
        elif rol == "director" and not club_valido:
            flash("Selecciona un club válido de tu organización.", "err")
        elif rol == "director" and any(u.rol == "director" and u.club_id == club_valido for u in DB["users"]):
            flash("Ese club ya tiene un Director asignado.", "err")
        else:
            DB["users"].append(seed_data.Usuario(new_id("user"), user.organizacion_id, nombre,
                                                 username, password, rol,
                                                 evento_id=evento_valido, club_id=club_valido))
            flash(f"Usuario {rol} '{nombre}' creado con usuario '{username}'.", "ok")
    return redirect(url_for("admin_usuarios"))


@app.route("/admin/usuarios/<user_id>/password", methods=["POST"])
def admin_usuario_password(user_id):
    user = require_rol("admin")
    target = find(DB, "users", "id", user_id)
    if not target or target.organizacion_id != user.organizacion_id:
        abort(404)
    nueva = request.form.get("password", "")
    if len(nueva) < 4:
        flash("La contraseña debe tener al menos 4 caracteres.", "err")
    else:
        target.password = nueva
        flash(f"Contraseña de '{target.nombre}' actualizada.", "ok")
    return redirect(url_for("admin_usuarios"))


@app.route("/admin/usuarios/<user_id>/eliminar", methods=["POST"])
def admin_usuario_eliminar(user_id):
    user = require_rol("admin")
    target = find(DB, "users", "id", user_id)
    if not target or target.organizacion_id != user.organizacion_id:
        abort(404)
    if target.rol == "admin":
        flash("No se puede eliminar un usuario Admin.", "err")
    elif target.id == user.id:
        flash("No puedes eliminar tu propia cuenta.", "err")
    else:
        if any(e.evaluador_id == user_id for e in DB["evaluaciones"]):
            abort(409, description="Este usuario tiene evaluaciones históricas y no se puede eliminar.")
        DB["users"] = [u for u in DB["users"] if u.id != user_id]
        DB["evaluaciones"] = [e for e in DB["evaluaciones"] if e.evaluador_id != user_id]
        for x in DB["evento_club"]:
            if x.staff_principal_id == user_id:
                x.staff_principal_id = None
        flash(f"Usuario '{target.nombre}' eliminado.", "ok")
    return redirect(url_for("admin_usuarios"))


@app.route("/admin/usuarios/importar", methods=["POST"])
def admin_usuarios_importar():
    """Importa usuarios Staff o Directores desde un Excel
    (columnas Staff: nombre, username, password, evento · Director: nombre, username, password, club)."""
    user = require_rol("admin")
    rol = request.form.get("rol", "")
    f = request.files.get("archivo")
    if rol not in ("staff", "director"):
        flash("Indica el rol de los usuarios a importar (Staff o Director).", "err")
        return redirect(url_for("admin_usuarios"))
    if not f or not f.filename:
        return redirect(url_for("admin_usuarios"))
    ext = f.filename.rsplit(".", 1)[-1].lower() if "." in f.filename else ""
    if ext not in {"xlsx", "xlsm"}:
        flash("El archivo debe ser .xlsx", "err")
        return redirect(url_for("admin_usuarios"))
    try:
        from openpyxl import load_workbook
        wb = load_workbook(filename=f, data_only=True)
        ws = wb.active
        filas = list(ws.iter_rows(values_only=True))
        errors = []
        importados = 0
        for idx, row in enumerate(filas[1:], start=2):
            if not row or not row[0]:
                continue
            row = tuple(row) + (None,) * max(0, 4 - len(row))
            nombre = str(row[0]).strip()
            username = str(row[1]).strip().lower() if row[1] else ""
            password = str(row[2]).strip() if row[2] else ""
            asignacion = str(row[3]).strip() if row[3] else ""
            if not (nombre and username and password):
                errors.append(f"Fila {idx}: faltan datos (nombre, usuario, contraseña)")
                continue
            if len(password) < 4:
                errors.append(f"Fila {idx}: contraseña muy corta (mínimo 4)")
                continue
            if any(u.username.lower() == username for u in DB["users"]):
                errors.append(f"Fila {idx}: el usuario '{username}' ya existe")
                continue
            evento_valido = None
            club_valido = None
            if rol == "staff":
                if asignacion:
                    ev = next((e for e in DB["eventos"]
                               if e.organizacion_id == user.organizacion_id
                               and e.nombre.lower() == asignacion.lower()), None)
                    if ev:
                        evento_valido = ev.id
                    else:
                        errors.append(f"Fila {idx}: evento '{asignacion}' no encontrado")
                        continue
            else:
                if asignacion:
                    cl = next((c for c in DB["clubs"]
                               if c.organizacion_id == user.organizacion_id
                               and c.nombre.lower() == asignacion.lower()), None)
                    if cl:
                        if any(u.rol == "director" and u.club_id == cl.id for u in DB["users"]):
                            errors.append(f"Fila {idx}: el club '{asignacion}' ya tiene director")
                            continue
                        club_valido = cl.id
                    else:
                        errors.append(f"Fila {idx}: club '{asignacion}' no encontrado")
                        continue
                else:
                    errors.append(f"Fila {idx}: falta el club del director")
                    continue
            DB["users"].append(seed_data.Usuario(new_id("user"), user.organizacion_id, nombre,
                                                 username, password, rol,
                                                 evento_id=evento_valido, club_id=club_valido))
            importados += 1
        msg = f"Se importaron {importados} {rol}(s)."
        if errors:
            msg += " Errores: " + "; ".join(errors[:5])
        flash(msg, "ok" if importados else "err")
    except Exception as exc:
        flash(f"No se pudo leer el archivo: {exc}", "err")
    return redirect(url_for("admin_usuarios"))


@app.route("/plantilla-usuarios.xlsx")
def plantilla_usuarios():
    """Plantilla de importación de usuarios según el rol (staff o director)."""
    rol = request.args.get("rol", "staff")
    from openpyxl import Workbook
    from openpyxl.utils import get_column_letter
    import io

    wb = Workbook()
    ws = wb.active
    if rol == "director":
        ws.title = "Directores"
        headers = ["nombre", "username", "password", "club"]
        ws.append(headers)
        ws.append(["Director Ejemplo", "dir2026a", "clave123", "Tigres del Valle"])
    else:
        ws.title = "Staff"
        headers = ["nombre", "username", "password", "evento"]
        ws.append(headers)
        ws.append(["Staff Ejemplo", "staff2026a", "clave123", "Campamento Regional"])
    for col in range(1, len(headers) + 1):
        ws.column_dimensions[get_column_letter(col)].width = 24
    bio = io.BytesIO()
    wb.save(bio)
    bio.seek(0)
    return send_file(bio, as_attachment=True, download_name=f"plantilla-{rol}.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


# --------------------------------------------------------------------------
# STAFF
# --------------------------------------------------------------------------

@app.route("/staff/escanear")
def staff_escanear():
    user = require_rol("staff")
    evento = find(DB, "eventos", "id", user.evento_id)
    if not evento or evento.organizacion_id != user.organizacion_id:
        return render_template("staff/sin_evento.html", user=user)
    return render_template("staff/escanear.html", user=user, evento=evento)


@app.route("/staff/escanear/imagen", methods=["POST"])
def staff_escanear_imagen():
    user = require_rol("staff")
    evento = find(DB, "eventos", "id", user.evento_id)
    if not evento or evento.organizacion_id != user.organizacion_id:
        abort(403)
    allowed = {c.id for c in db_org(user)["clubs"] if any(
        ec.evento_id == evento.id and ec.club_id == c.id for ec in DB["evento_club"]
    )}
    organization_id = user.organizacion_id
    image = request.files.get("imagen")
    if image is None:
        return jsonify(error="Selecciona una fotografía del QR."), 400
    from qr_reader import decode_image, MAX_IMAGE_BYTES, InvalidQRImage, QRReaderBusy, QRReaderUnavailable

    content = image.read(MAX_IMAGE_BYTES + 1)
    # La inferencia no escribe en la base ni debe bloquear otros usuarios.
    # La ruta /qr vuelve a autorizar contra el estado vigente al abrir la ficha.
    _cerrar_transaccion()
    try:
        codes = decode_image(content)
    except InvalidQRImage as error:
        return jsonify(error=str(error)), 400
    except QRReaderBusy as error:
        return jsonify(error=str(error), code="reader_busy"), 503, {"Retry-After": "3"}
    except QRReaderUnavailable:
        return jsonify(error="QReader no está disponible en este servidor. Usa la lectura local o avisa al administrador.", code="reader_unavailable"), 503
    paths = set()
    for value in codes:
        if len(value) > 2048:
            continue
        try:
            parsed = urlsplit(value)
            if (parsed.scheme not in {"", "http", "https"} or parsed.query or parsed.fragment
                    or parsed.username or parsed.password or not re.fullmatch(r"/qr/[A-Za-z0-9_.-]+", parsed.path)):
                continue
            token = parsed.path.removeprefix("/qr/")
            try:
                club_id = URLSafeSerializer(app.secret_key, salt="scoreup-club-qr-v2").loads(token)
            except BadSignature:
                legacy = URLSafeSerializer(app.secret_key, salt="scoreup-club-qr-v1").loads(token)
                if not isinstance(legacy, dict) or legacy.get("org") != organization_id:
                    continue
                club_id = legacy.get("club")
            if isinstance(club_id, str) and club_id in allowed:
                paths.add(parsed.path)
        except (ValueError, BadSignature):
            continue
    if len(paths) > 1:
        return jsonify(error="Hay varios QR de clubes. Fotografía una sola tarjeta.", code="multiple_qr"), 422
    if not paths:
        return jsonify(error="No se encontró un QR válido de un club de tu evento. Acerca la tarjeta y enfoca el código completo."), 422
    return jsonify(path=paths.pop(), reader="qreader")


@app.route("/staff")
def panel_staff():
    user = require_rol("staff")
    evento = find(DB, "eventos", "id", user.evento_id) if user.evento_id else None
    if not evento or evento.organizacion_id != user.organizacion_id:
        return render_template("staff/sin_evento.html", user=user)
    criterios = [c for c in DB["criterios"] if c.evento_id == evento.id]
    ecs = [x for x in DB["evento_club"] if x.evento_id == evento.id]
    club_id = request.args.get("club")
    if club_id:
        _club_participante(user, evento, club_id)
    vista = "evaluar" if club_id else request.args.get("vista", "inicio")
    if vista not in {"inicio", "clubes", "penalizaciones", "incidentes", "evaluar"}:
        abort(404)
    criterios_listos = bool(criterios) and abs(sum(c.peso for c in criterios) - 100) <= 0.001
    estados = []
    for ec in ecs:
        oficial = evaluacion_principal(DB, evento, ec.club_id)
        estados.append({
            "ec": ec,
            "club": find(DB, "clubs", "id", ec.club_id),
            "mi_evl": oficial if oficial and oficial.evaluador_id == user.id else None,
            "puede_evaluar": criterios_listos and not evento.cerrado and (oficial is None or oficial.evaluador_id == user.id),
            "oficial": oficial,
        })
    evaluados = sum(st["oficial"] is not None for st in estados)
    resumen = {"clubes": len(estados), "evaluados": evaluados,
               "pendientes": len(estados) - evaluados,
               "avance": round(100 * evaluados / len(estados)) if estados else 0}
    view = db_org(user)
    incidentes = [i for i in view["incidentes"] if i.evento_id == evento.id and i.usuario_id == user.id]
    penalizaciones = [p for p in view["penalizaciones"] if p.evento_id == evento.id and p.usuario_id == user.id]
    return render_template("staff/panel.html", user=user, evento=evento, criterios=criterios,
                           estados=[st for st in estados if not club_id or st["ec"].club_id == club_id],
                           participantes=estados, db=view, fmt_pts=fmt_pts, enfocado=bool(club_id),
                           vista=vista, resumen=resumen, criterios_listos=criterios_listos,
                           incidentes=list(reversed(incidentes)), penalizaciones=list(reversed(penalizaciones)))


@app.route("/staff/evaluar/<club_id>", methods=["POST"])
def staff_evaluar(club_id):
    user = require_rol("staff")
    evento = _evento_abierto(user)
    _club_participante(user, evento, club_id)
    criterios = [c for c in DB["criterios"] if c.evento_id == evento.id]
    if not criterios or abs(sum(c.peso for c in criterios) - 100) > 0.001:
        abort(409, description="Los criterios del evento todavía no suman 100%.")
    valores = {}
    for c in criterios:
        try:
            valor = float(request.form[f"val_{c.id}"])
            if not math.isfinite(valor) or not 0 <= valor <= 100:
                raise ValueError
            valores[c.id] = valor
        except (TypeError, ValueError):
            abort(400, description="Completa cada criterio con un número entre 0 y 100.")
    comentario = request.form.get("comentario", "")
    evl = evaluacion_principal(DB, evento, club_id)
    try:
        version = int(request.form.get("version", "0"))
    except ValueError:
        abort(400)
    if evl:
        if evl.evaluador_id != user.id:
            abort(409, description="Este club ya fue evaluado por otro staff. No se puede reemplazar su nota.")
        if version != evl.version:
            abort(409, description="La evaluación cambió desde que abriste la página. Recarga antes de corregir.")
        if evl.valores != valores or evl.comentario != comentario:
            DB["correcciones"].append({
                "id": new_id("rep"), "evento_id": evento.id, "club_id": club_id,
                "evaluador_id": user.id, "fecha": datetime.now().isoformat(timespec="seconds"),
                "anterior": {"valores": dict(evl.valores), "comentario": evl.comentario},
                "actual": {"valores": valores, "comentario": comentario}, "estado": "pendiente",
            })
            evl.version += 1
        evl.valores = valores
        evl.comentario = comentario
        evl.fecha = datetime.now().strftime("%Y-%m-%d")
    else:
        if version != 0:
            abort(409, description="La evaluación ya no existe; recarga la página.")
        DB["evaluaciones"].append(seed_data.Evaluacion(
            new_id("evl"), evento.id, club_id, user.id, comentario,
            datetime.now().strftime("%Y-%m-%d"), valores,
        ))
    flash("Evaluación guardada correctamente.", "ok")
    return redirect(url_for("panel_staff", club=club_id))


ALLOWED_EXT = {"png", "jpg", "jpeg", "gif", "webp"}


@app.route("/staff/incidente", methods=["POST"])
def staff_incidente():
    """RF-29/RF-32: reporta un incidente, con foto opcional adjunta."""
    user = require_rol("staff")
    evento = _evento_abierto(user)
    club_id = request.form.get("club_id") or None
    if club_id:
        _club_participante(user, evento, club_id)
    if request.form.get("tipo") not in {"accidente", "salud", "disciplina", "logistica", "otro"}:
        abort(400)
    if request.form.get("gravedad") not in {"leve", "moderado", "grave"} or not request.form.get("descripcion", "").strip():
        abort(400, description="Selecciona gravedad y escribe una descripción.")
    foto = request.files.get("foto")
    foto_url = None
    if foto and foto.filename:
        ext = foto.filename.rsplit(".", 1)[-1].lower() if "." in foto.filename else ""
        if ext not in ALLOWED_EXT:
            abort(400, description="Adjunta una imagen PNG, JPG, GIF o WebP.")
        from PIL import Image, UnidentifiedImageError
        try:
            image = Image.open(foto.stream)
            if image.format not in {"PNG", "JPEG", "GIF", "WEBP"}:
                raise ValueError
            image.verify()
            foto.stream.seek(0)
        except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
            abort(400, description="El archivo no contiene una imagen válida.")
        if ext in ALLOWED_EXT:
            nombre = f"{new_id('foto').replace('-', '')}.{ext}"
            foto.stream.seek(0)
            mime = Image.MIME.get(image.format, foto.mimetype or "application/octet-stream")
            store.save_evidence(nombre, foto.read(), mime, g.get("connection"))
            foto_url = url_for("evidencia", nombre=nombre)
    DB["incidentes"].append(seed_data.Incidente(
        new_id("inc"), evento.id, user.id,
        request.form.get("tipo", "otro"),
        request.form.get("gravedad", "leve"),
        request.form.get("descripcion", ""),
        "abierto",
        club_id,
        foto_url,
        datetime.now().isoformat(timespec="seconds"),
    ))
    flash("Incidente reportado correctamente. El administrador podrá revisarlo.", "ok")
    return redirect(url_for("panel_staff", vista="incidentes"))


@app.route("/staff/penalizar", methods=["POST"])
def staff_penalizar():
    user = require_rol("staff")
    evento = _evento_abierto(user)
    club_id = request.form.get("club_id")
    motivo_id = request.form.get("motivo_id")
    _club_participante(user, evento, club_id)
    motivo = find(DB, "motivos", "id", motivo_id)
    if not motivo or motivo.organizacion_id != user.organizacion_id or not motivo.activo:
        abort(404)
    if club_id and motivo_id:
        DB["penalizaciones"].append(seed_data.PenalizacionAplicada(
            new_id("pa"), club_id, evento.id, user.id, motivo_id,
            request.form.get("comentario", ""), datetime.now().strftime("%Y-%m-%d"), motivo.puntos_descuento,
        ))
    flash("Penalización aplicada correctamente.", "ok")
    return redirect(url_for("panel_staff", vista="penalizaciones"))


@app.route("/evidencias/<nombre>")
def evidencia(nombre):
    if current_user() is None:
        return redirect(url_for("login"))
    user = require_rol("admin", "staff")
    incidente = next((i for i in db_org(user)["incidentes"] if i.foto_url and i.foto_url.endswith("/" + nombre)), None)
    if not incidente:
        abort(404)
    encontrado = store.read_evidence(nombre, g.get("connection"))
    if encontrado is None:
        abort(404)
    contenido, mime = encontrado
    return send_file(BytesIO(contenido), mimetype=mime, download_name=nombre, max_age=0)


@app.before_request
def _proteger_uploads_antiguos():
    if request.path.startswith("/static/uploads/"):
        return evidencia(request.path.rsplit("/", 1)[-1])


# --------------------------------------------------------------------------
# DIRECTOR
# --------------------------------------------------------------------------

@app.route("/director")
def panel_director():
    user = require_rol("director")
    club = find(DB, "clubs", "id", user.club_id) if user.club_id else None
    if not club or club.organizacion_id != user.organizacion_id:
        abort(404)
    view = db_org(user)
    temporada = request.args.get("temporada", max((e.temporada for e in view["eventos"]), default="2026"))
    season = None
    published = dict(view, eventos=[e for e in view["eventos"] if e.cerrado])
    for f in ranking_temporada(published, temporada)["filas"]:
        if f["club"].id == club.id:
            season = f
    eventos_club = []
    for x in view["evento_club"]:
        if x.club_id == club.id:
            e = find(view, "eventos", "id", x.evento_id)
            if e and e.cerrado and e.temporada == temporada:
                r = ranking_evento(view, e)
                fila = next((f for f in r if f["club"].id == club.id), None)
                eventos_club.append({"evento": e, "puntaje": fila["puntaje"] if fila else None})
    eventos_club.sort(key=lambda x: x["evento"].fecha)
    return render_template("director/panel.html", user=user, db=view, club=club, season=season,
                            eventos_club=eventos_club, fmt_pts=fmt_pts, fmt_fecha=fmt_fecha)


@app.route("/director/qr.png")
def director_club_qr():
    user = require_rol("director")
    club = find(DB, "clubs", "id", user.club_id) if user.club_id else None
    if not club or club.organizacion_id != user.organizacion_id:
        abort(404)
    base, _ = _qr_base_url(app.config["PUBLIC_BASE_URL"] or request.url_root)
    link = base + url_for("qr_club", token=_token_club(club))
    return _club_qr_png(club, link, download=request.args.get("descargar") == "1")


# --------------------------------------------------------------------------
# Plantilla Excel de importación
# --------------------------------------------------------------------------

@app.route("/plantilla-miembros.xlsx")
def plantilla_miembros():
    from openpyxl import Workbook
    from openpyxl.utils import get_column_letter
    from flask import send_file
    import io

    wb = Workbook()
    ws = wb.active
    ws.title = "Miembros"
    headers = ["nombre", "edad", "cargo", "anio_ingreso", "categoria"]
    ws.append(headers)
    ws.append(["Ejemplo Miembro", 13, "Secretario/a", 2025, "Explorador"])
    ws.append(["Otro Miembro", 11, "Miembro", 2026, "Aventurero"])
    for col in range(1, len(headers) + 1):
        ws.column_dimensions[get_column_letter(col)].width = 24
    bio = io.BytesIO()
    wb.save(bio)
    bio.seek(0)
    return send_file(bio, as_attachment=True, download_name="plantilla-miembros.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@app.route("/admin/clubes/<club_id>/miembros/importar", methods=["POST"])
def admin_importar_miembros(club_id):
    user = require_rol("admin")
    club = find(DB, "clubs", "id", club_id)
    if not club or club.organizacion_id != user.organizacion_id:
        abort(404)
    f = request.files.get("archivo")
    if f and f.filename:
        ext = f.filename.rsplit(".", 1)[-1].lower() if "." in f.filename else ""
        if ext not in {"xlsx", "xlsm"}:
            return redirect(url_for("admin_club_miembros", club_id=club_id,
                                    msg="El archivo debe ser .xlsx"))
        try:
            from openpyxl import load_workbook
            wb = load_workbook(filename=f, data_only=True)
            ws = wb.active
            filas = list(ws.iter_rows(values_only=True))
            errors = []
            importados = 0
            for idx, row in enumerate(filas[1:], start=2):
                if not row or not row[0]:
                    continue
                row = tuple(row) + (None,) * max(0, 5 - len(row))
                nombre = str(row[0]).strip()
                if not nombre:
                    errors.append(f"Fila {idx}: falta el nombre")
                    continue
                if any(m.nombre.lower() == nombre.lower() for m in club.miembros):
                    continue  # duplicado omitido silenciosamente
                try:
                    edad = int(row[1]) if row[1] not in (None, "") else None
                except (TypeError, ValueError):
                    errors.append(f"Fila {idx}: edad inválida")
                    edad = None
                cargo = str(row[2]).strip() if row[2] else "Miembro"
                try:
                    anio = int(row[3]) if row[3] not in (None, "") else None
                except (TypeError, ValueError):
                    anio = None
                    errors.append(f"Fila {idx}: año de ingreso inválido")
                cat = str(row[4]).strip() if row[4] else "Explorador"
                club.miembros.append(seed_data.Miembro(new_id("m"), nombre, edad, cargo, anio, cat))
                importados += 1
            msg = f"Se importaron {importados} miembro(s)."
            if errors:
                msg += " Errores: " + "; ".join(errors[:5])
        except Exception as exc:
            msg = f"No se pudo leer el archivo: {exc}"
        return redirect(url_for("admin_club_miembros", club_id=club_id, msg=msg))
    return redirect(url_for("admin_club_miembros", club_id=club_id))


if __name__ == "__main__":
    app.run(host=os.environ.get("HOST", "0.0.0.0"), port=int(os.environ.get("PORT", "5000")), debug=False)
