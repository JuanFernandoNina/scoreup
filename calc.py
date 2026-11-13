"""Lógica de cálculo del sistema ScoreUp (versión Python, equivalente a utils/calc.js)."""

from functools import cmp_to_key


def porcentaje_ponderado(evaluacion, criterios):
    """Porcentaje ponderado (0-100) de una evaluación según los criterios del evento."""
    if evaluacion is None:
        return 0.0
    total = 0.0
    for c in criterios:
        valor = (evaluacion.valores or {}).get(c.id, 0)
        total += valor * (c.peso / 100.0)
    return total


def puntaje_evento(evaluacion, criterios, puntaje_maximo):
    """puntaje_evento = porcentaje ponderado × puntaje máximo del evento."""
    if evaluacion is None:
        return 0.0
    return round((porcentaje_ponderado(evaluacion, criterios) / 100.0) * puntaje_maximo, 2)


def evaluacion_principal(db, evento, club_id):
    """Única evaluación oficial por club y evento (respaldos antiguos excluidos)."""
    ec = _find(db["evento_club"], evento.id, club_id)
    if ec is None:
        return None
    for e in db["evaluaciones"]:
        if e.evento_id == evento.id and e.club_id == club_id and e.oficial:
            return e
    return None


def _valor_criterio_mayor_peso(evaluacion, criterios):
    """Valor en el criterio de mayor peso (usado para desempatar)."""
    if evaluacion is None or not criterios:
        return 0
    mayor = max(criterios, key=lambda c: c.peso)
    return (evaluacion.valores or {}).get(mayor.id, 0)


def _find(lista, evento_id, club_id):
    for x in lista:
        if x.evento_id == evento_id and x.club_id == club_id:
            return x
    return None


def ranking_evento(db, evento):
    """Ranking de un evento. NO resta penalizaciones.
    Empates: se compara el criterio de mayor peso; si persiste, posición compartida."""
    criterios = [c for c in db["criterios"] if c.evento_id == evento.id]
    filas = []
    for club in db["clubs"]:
        ec = _find(db["evento_club"], evento.id, club.id)
        if ec is None:
            continue
        evl = evaluacion_principal(db, evento, club.id)
        if evl is None:
            continue
        filas.append({
            "club": club,
            "evento": evento,
            "staff_principal_id": ec.staff_principal_id,
            "evaluacion": evl,
            "porcentaje": porcentaje_ponderado(evl, criterios),
            "puntaje": puntaje_evento(evl, criterios, evento.puntaje_maximo),
            "desempate": _valor_criterio_mayor_peso(evl, criterios),
        })

    def _cmp(a, b):
        if b["puntaje"] != a["puntaje"]:
            return (b["puntaje"] > a["puntaje"]) - (b["puntaje"] < a["puntaje"])
        return (b["desempate"] > a["desempate"]) - (b["desempate"] < a["desempate"])

    filas.sort(key=cmp_to_key(_cmp))
    return _with_positions(filas)


def _with_positions(ordenado):
    res = []
    for idx, fila in enumerate(ordenado):
        pos = idx + 1
        empatado = False
        if idx > 0:
            prev = res[idx - 1]
            if fila["puntaje"] == prev["puntaje"] and fila["desempate"] == prev["desempate"]:
                pos = prev["posicion"]
                empatado = True
        fila["posicion"] = pos
        fila["empatado"] = empatado
        res.append(fila)
    return res


def total_penalizaciones_club(db, club_id, evento_ids=None):
    total = 0.0
    for p in db["penalizaciones"]:
        if p.club_id == club_id and (evento_ids is None or p.evento_id in evento_ids):
            motivo = _find_motivo(db, p.motivo_id)
            total += p.puntos if p.puntos is not None else (motivo.puntos_descuento if motivo else 0)
    return round(total, 2)


def _find_motivo(db, motivo_id):
    for m in db["motivos"]:
        if m.id == motivo_id:
            return m
    return None


def ranking_temporada(db, temporada):
    """Ranking de temporada: Σ puntaje_evento (todos los eventos) − Σ penalizaciones."""
    eventos = [e for e in db["eventos"] if e.temporada == temporada]
    evento_ids = {e.id for e in eventos}
    rankings = {e.id: {f["club"].id: f for f in ranking_evento(db, e)} for e in eventos}
    filas = []
    for club in db["clubs"]:
        por_evento = {}
        bruto = 0.0
        for evento in eventos:
            fila = rankings[evento.id].get(club.id)
            puntaje = fila["puntaje"] if fila else 0.0
            por_evento[evento.id] = puntaje
            bruto += puntaje
        pen = total_penalizaciones_club(db, club.id, evento_ids)
        filas.append({
            "club": club,
            "por_evento": por_evento,
            "bruto": round(bruto, 2),
            "penalizaciones": pen,
            "puntaje": round(bruto - pen, 2),
        })

    filas.sort(key=lambda f: f["puntaje"], reverse=True)
    for idx, fila in enumerate(filas):
        pos = idx + 1
        if idx > 0 and fila["puntaje"] == filas[idx - 1]["puntaje"]:
            pos = filas[idx - 1]["posicion"]
        fila["posicion"] = pos
    return {"eventos": eventos, "filas": filas}


def actividad_staff(db, evento):
    """Actividad real: evaluaciones oficiales realizadas por cada staff."""
    total = sum(ec.evento_id == evento.id for ec in db["evento_club"])
    filas = []
    for user in db["users"]:
        if user.rol == "staff" and user.evento_id == evento.id:
            completadas = sum(e.oficial and e.evento_id == evento.id and e.evaluador_id == user.id for e in db["evaluaciones"])
            filas.append({"staff": user, "total": total, "completadas": completadas})
    return {"por_staff": filas, "respaldos": sum(not e.oficial and e.evento_id == evento.id for e in db["evaluaciones"])}


def _find_user(db, user_id):
    for u in db["users"]:
        if u.id == user_id:
            return u
    return None


def find(db, kind, key, value):
    for item in db[kind]:
        if getattr(item, key) == value:
            return item
    return None


def fmt_pts(n):
    """Formatea número de puntos sin decimales si es entero."""
    if float(n) == int(n):
        return str(int(n))
    return f"{n:.2f}"


def fmt_fecha(iso):
    if not iso:
        return "—"
    try:
        partes = iso.split("-")
        return f"{partes[2]}/{partes[1]}/{partes[0]}"
    except Exception:
        return iso
