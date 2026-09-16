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
    """Evaluación del Staff principal para un club en un evento (solo esa cuenta)."""
    ec = _find(db["evento_club"], evento.id, club_id)
    if ec is None or ec.staff_principal_id is None:
        return None
    for e in db["evaluaciones"]:
        if (e.evento_id == evento.id and e.club_id == club_id and e.evaluador_id == ec.staff_principal_id):
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


def total_penalizaciones_club(db, club_id):
    total = 0.0
    for p in db["penalizaciones"]:
        if p.club_id == club_id:
            motivo = _find_motivo(db, p.motivo_id)
            if motivo:
                total += motivo.puntos_descuento
    return round(total, 2)


def _find_motivo(db, motivo_id):
    for m in db["motivos"]:
        if m.id == motivo_id:
            return m
    return None


def ranking_temporada(db, temporada):
    """Ranking de temporada: Σ puntaje_evento (todos los eventos) − Σ penalizaciones."""
    eventos = [e for e in db["eventos"] if e.temporada == temporada]
    filas = []
    for club in db["clubs"]:
        por_evento = {}
        bruto = 0.0
        for evento in eventos:
            rank = ranking_evento(db, evento)
            fila = next((r for r in rank if r["club"].id == club.id), None)
            puntaje = fila["puntaje"] if fila else 0.0
            por_evento[evento.id] = puntaje
            bruto += puntaje
        pen = total_penalizaciones_club(db, club.id)
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
    """Por staff principal del evento: clubes asignados vs evaluaciones completadas."""
    criterios = [c for c in db["criterios"] if c.evento_id == evento.id]
    ecs = [x for x in db["evento_club"] if x.evento_id == evento.id]
    por_staff = {}
    for ec in ecs:
        evl = None
        for e in db["evaluaciones"]:
            if (e.evento_id == evento.id and e.club_id == ec.club_id and e.evaluador_id == ec.staff_principal_id):
                evl = e
        staff = _find_user(db, ec.staff_principal_id)
        key = ec.staff_principal_id
        if key not in por_staff:
            por_staff[key] = {"staff": staff, "total": 0, "completadas": 0}
        por_staff[key]["total"] += 1
        if evl:
            por_staff[key]["completadas"] += 1

    respaldos = sum(
        1 for e in db["evaluaciones"]
        if e.evento_id == evento.id and not any(
            ec.staff_principal_id == e.evaluador_id and ec.club_id == e.club_id for ec in ecs
        )
    )
    return {"por_staff": list(por_staff.values()), "respaldos": respaldos}


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