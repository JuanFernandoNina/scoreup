"""Datos de ejemplo en memoria para la demo web de ScoreUp (versión Flask)."""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Miembro:
    id: str
    nombre: str
    edad: int
    cargo: str
    anio_ingreso: int
    categoria: str


@dataclass
class Club:
    id: str
    nombre: str
    organizacion_id: str
    miembros: list = field(default_factory=list)


@dataclass
class Usuario:
    id: str
    organizacion_id: str
    nombre: str
    username: str
    password: str
    rol: str  # admin | staff | director
    evento_id: str = None
    club_id: str = None


@dataclass
class Evento:
    id: str
    organizacion_id: str
    nombre: str
    fecha: str
    lugar: str
    tipo: str
    temporada: str
    puntaje_maximo: int
    cerrado: bool = False


@dataclass
class Criterio:
    id: str
    evento_id: str
    nombre: str
    peso: float


@dataclass
class EventoClub:
    id: str
    evento_id: str
    club_id: str
    staff_principal_id: str = None


@dataclass
class Evaluacion:
    id: str
    evento_id: str
    club_id: str
    evaluador_id: str
    comentario: str = ""
    fecha: str = ""
    valores: dict = field(default_factory=dict)


@dataclass
class MotivoPenalizacion:
    id: str
    organizacion_id: str
    nombre: str
    descripcion: str
    puntos_descuento: float
    activo: bool = True


@dataclass
class PenalizacionAplicada:
    id: str
    club_id: str
    evento_id: str
    usuario_id: str
    motivo_id: str
    comentario: str = ""
    fecha: str = ""


@dataclass
class Incidente:
    id: str
    evento_id: str
    usuario_id: str
    tipo: str
    gravedad: str
    descripcion: str
    estado: str = "abierto"
    club_id: str = None
    foto_url: str = None
    fecha_hora: str = ""


def _miembros_club1():
    data = [
        ("Andrés Cáceres", 14, "Guía Mayor", 2021, "Guía"),
        ("María Torres", 13, "Secretaria", 2022, "Compañerismo"),
        ("Luis Ríos", 12, "Tesorero", 2023, "Explorador"),
        ("Sofía Mendoza", 11, "Miembro", 2024, "Explorador"),
        ("Valentina Rojas", 13, "Abanderada", 2023, "Compañerismo"),
        ("Santiago Pino", 12, "Cronista", 2023, "Explorador"),
        ("Amanda Contreras", 11, "Miembro", 2024, "Explorador"),
        ("Diego Villanueva", 15, "Guía Mayor", 2020, "Guía"),
        ("Catalina Herrera", 10, "Miembro", 2025, "Aventurero"),
        ("Martín Álvarez", 13, "Bibliotecario", 2024, "Compañerismo"),
        ("Ignacia Salinas", 11, "Miembro", 2025, "Explorador"),
        ("Rodrigo Fuentes", 14, "Guía Mayor", 2022, "Guía"),
        ("Josefina Lara", 12, "Tesorera", 2023, "Explorador"),
        ("Tomás Ibáñez", 9, "Miembro", 2026, "Aventurero"),
        ("Antonia Campos", 13, "Secretaria", 2022, "Compañerismo"),
        ("Felipe Carvajal", 12, "Cronista", 2024, "Explorador"),
        ("Florencia Sandoval", 10, "Miembro", 2025, "Aventurero"),
        ("Matías Espinoza", 14, "Guía Mayor", 2021, "Guía"),
        ("Javiera Ortiz", 11, "Miembro", 2024, "Explorador"),
        ("Benjamín Silva", 12, "Tesorero", 2023, "Explorador"),
        ("Emilia Navarro", 10, "Miembro", 2025, "Aventurero"),
        ("Nicolás Ávila", 13, "Abanderado", 2022, "Compañerismo"),
        ("Constanza Bravo", 12, "Miembro", 2024, "Explorador"),
        ("Joaquín Reyes", 11, "Miembro", 2025, "Explorador"),
    ]
    return [Miembro(f"m1-{i}", *v) for i, v in enumerate(data, start=1)]


def _miembros_club2():
    data = [
        ("Pedro Salazar", 15, "Guía Mayor", 2020, "Guía"),
        ("Camila Díaz", 13, "Abanderada", 2022, "Compañerismo"),
        ("Jorge Paredes", 12, "Cronista", 2023, "Explorador"),
        ("Valentina Ruiz", 10, "Miembro", 2025, "Aventurero"),
    ]
    return [Miembro(f"m2-{i}", *v) for i, v in enumerate(data, start=1)]


def _miembros_club3():
    data = [
        ("Bruno Vega", 14, "Guía Mayor", 2021, "Guía"),
        ("Ana Lucía Flores", 13, "Secretaria", 2022, "Compañerismo"),
        ("Mateo Guzmán", 11, "Miembro", 2024, "Explorador"),
    ]
    return [Miembro(f"m3-{i}", *v) for i, v in enumerate(data, start=1)]


def _miembros_club4():
    data = [
        ("Daniel Ocampo", 15, "Guía Mayor", 2020, "Guía"),
        ("Isabella Rojas", 14, "Tesorera", 2021, "Guía"),
        ("Sebastián Núñez", 12, "Cronista", 2023, "Explorador"),
        ("Renata Silva", 11, "Miembro", 2024, "Explorador"),
        ("Emiliano Cruz", 10, "Miembro", 2025, "Aventurero"),
    ]
    return [Miembro(f"m4-{i}", *v) for i, v in enumerate(data, start=1)]


def _miembros_club5():
    data = [
        ("Gabriel Mora", 13, "Guía Mayor", 2022, "Compañerismo"),
        ("Mía Fuentes", 12, "Secretaria", 2023, "Explorador"),
        ("Noah Rivas", 11, "Miembro", 2024, "Explorador"),
    ]
    return [Miembro(f"m5-{i}", *v) for i, v in enumerate(data, start=1)]


def seed():
    organizacion = {"id": "org-1", "nombre": "Asociación Central de Conquistadores", "fecha_creacion": "2024-01-15"}

    clubs = [
        Club("club-1", "Tigres del Valle", "org-1", _miembros_club1()),
        Club("club-2", "Águilas del Norte", "org-1", _miembros_club2()),
        Club("club-3", "Halcones del Sur", "org-1", _miembros_club3()),
        Club("club-4", "Leones de la Montaña", "org-1", _miembros_club4()),
        Club("club-5", "Zorros del Bosque", "org-1", _miembros_club5()),
    ]

    users = [
        Usuario("user-admin", "org-1", "Admin Central", "admin", "admin", "admin"),
        Usuario("user-staff1", "org-1", "Staff Elena", "elena", "staff", "staff", evento_id="ev-1"),
        Usuario("user-staff2", "org-1", "Staff Roberto", "roberto", "staff", "staff", evento_id="ev-1"),
        Usuario("user-staff3", "org-1", "Staff Luisa", "luisa", "staff", "staff", evento_id="ev-2"),
        Usuario("user-staff4", "org-1", "Staff Tomás", "tomas", "staff", "staff", evento_id="ev-3"),
        Usuario("user-dir1", "org-1", "Directora Lucía", "lucia", "director", "director", club_id="club-1"),
        Usuario("user-dir2", "org-1", "Director Hugo", "hugo", "director", "director", club_id="club-2"),
        Usuario("user-dir3", "org-1", "Directora Paula", "paula", "director", "director", club_id="club-3"),
        Usuario("user-dir4", "org-1", "Director Iván", "ivan", "director", "director", club_id="club-4"),
        Usuario("user-dir5", "org-1", "Directora Nora", "nora", "director", "director", club_id="club-5"),
    ]

    eventos = [
        Evento("ev-1", "org-1", "Campamento de Invierno", "2026-02-14", "Parque Nacional Torres del Paine", "campamento", "2026", 520, cerrado=True),
        Evento("ev-2", "org-1", "Reunión Mensual de Marzo", "2026-03-22", "Salón Comunitario Central", "reunion", "2026", 120, cerrado=True),
        Evento("ev-3", "org-1", "Campamento Regional", "2026-05-09", "Valle de los Cóndores", "campamento", "2026", 320, cerrado=False),
    ]

    criterios = [
        Criterio("cr-1", "ev-1", "Puntualidad", 20), Criterio("cr-2", "ev-1", "Disciplina", 30), Criterio("cr-3", "ev-1", "Actividades", 50),
        Criterio("cr-4", "ev-2", "Asistencia", 30), Criterio("cr-5", "ev-2", "Participación", 40), Criterio("cr-6", "ev-2", "Orden y limpieza", 30),
        Criterio("cr-7", "ev-3", "Espíritu de equipo", 25), Criterio("cr-8", "ev-3", "Disciplina", 35), Criterio("cr-9", "ev-3", "Desafíos superados", 40),
    ]

    evento_club = [
        EventoClub("ec-1", "ev-1", "club-1", "user-staff1"), EventoClub("ec-2", "ev-1", "club-2", "user-staff1"),
        EventoClub("ec-3", "ev-1", "club-3", "user-staff2"), EventoClub("ec-4", "ev-1", "club-4", "user-staff2"),
        EventoClub("ec-5", "ev-1", "club-5", "user-staff2"),
        EventoClub("ec-6", "ev-2", "club-1", "user-staff3"), EventoClub("ec-7", "ev-2", "club-2", "user-staff3"),
        EventoClub("ec-8", "ev-2", "club-3", "user-staff3"), EventoClub("ec-9", "ev-2", "club-4", "user-staff3"),
        EventoClub("ec-10", "ev-2", "club-5", "user-staff3"),
        EventoClub("ec-11", "ev-3", "club-1", "user-staff4"), EventoClub("ec-12", "ev-3", "club-2", "user-staff4"),
        EventoClub("ec-13", "ev-3", "club-3", "user-staff4"), EventoClub("ec-14", "ev-3", "club-4", "user-staff4"),
        EventoClub("ec-15", "ev-3", "club-5", "user-staff4"),
    ]

    evaluaciones = [
        Evaluacion("evl-1", "ev-1", "club-1", "user-staff1", "Muy buen desempeño general.", "2026-02-16", {"cr-1": 80, "cr-2": 90, "cr-3": 85}),
        Evaluacion("evl-2", "ev-1", "club-2", "user-staff1", "Excelente disciplina en campamento.", "2026-02-16", {"cr-1": 90, "cr-2": 85, "cr-3": 88}),
        Evaluacion("evl-3", "ev-1", "club-3", "user-staff2", "Buen trabajo en equipo.", "2026-02-17", {"cr-1": 70, "cr-2": 75, "cr-3": 80}),
        Evaluacion("evl-4", "ev-1", "club-4", "user-staff2", "Destacaron en todas las actividades.", "2026-02-16", {"cr-1": 92, "cr-2": 94, "cr-3": 95}),
        Evaluacion("evl-5", "ev-1", "club-5", "user-staff2", "Pueden mejorar la puntualidad.", "2026-02-17", {"cr-1": 75, "cr-2": 80, "cr-3": 72}),
        Evaluacion("evl-6", "ev-1", "club-1", "user-staff2", "Respaldo, no oficial.", "2026-02-17", {"cr-1": 82, "cr-2": 88, "cr-3": 87}),
        Evaluacion("evl-7", "ev-2", "club-1", "user-staff3", "Buena asistencia.", "2026-03-23", {"cr-4": 85, "cr-5": 90, "cr-6": 84}),
        Evaluacion("evl-8", "ev-2", "club-2", "user-staff3", "Participación constante.", "2026-03-23", {"cr-4": 90, "cr-5": 85, "cr-6": 84}),
        Evaluacion("evl-9", "ev-2", "club-3", "user-staff3", "Correctos.", "2026-03-23", {"cr-4": 78, "cr-5": 82, "cr-6": 80}),
        Evaluacion("evl-10", "ev-2", "club-4", "user-staff3", "Muy ordenados.", "2026-03-23", {"cr-4": 90, "cr-5": 84, "cr-6": 87}),
        Evaluacion("evl-11", "ev-2", "club-5", "user-staff3", "Asistencia irregular.", "2026-03-23", {"cr-4": 72, "cr-5": 75, "cr-6": 76}),
        Evaluacion("evl-12", "ev-3", "club-2", "user-staff4", "Muy fuertes en las pruebas.", "2026-05-10", {"cr-7": 90, "cr-8": 88, "cr-9": 85}),
        Evaluacion("evl-13", "ev-3", "club-4", "user-staff4", "Buen espíritu competitivo.", "2026-05-10", {"cr-7": 80, "cr-8": 85, "cr-9": 82}),
    ]

    motivos = [
        MotivoPenalizacion("mp-1", "org-1", "Campamento no limpio", "Área de campamento dejada con basura o desorden.", 5),
        MotivoPenalizacion("mp-2", "org-1", "Retraso injustificado", "Llegada tardía a actividades sin justificación.", 10),
        MotivoPenalizacion("mp-3", "org-1", "Uso de celular en actividades", "Uso de dispositivos móviles durante las actividades.", 8),
    ]

    now = datetime.now().strftime("%Y-%m-%d")
    penalizaciones = [
        PenalizacionAplicada("pa-1", "club-2", "ev-3", "user-staff4", "mp-2", "Llegó 2 horas tarde al registro del campamento.", now),
        PenalizacionAplicada("pa-2", "club-5", "ev-1", "user-staff2", "mp-1", "Zona de campamento con restos de basura.", now),
        PenalizacionAplicada("pa-3", "club-4", "ev-3", "user-staff4", "mp-3", "Se les vio celulares durante la fogata.", now),
    ]

    incidentes = [
        Incidente("inc-1", "ev-3", "user-staff4", "disciplina", "grave", "Discusión entre miembros del club durante las actividades nocturnas.", "abierto", "club-3", None, "2026-05-09 21:40"),
        Incidente("inc-2", "ev-1", "user-staff2", "logistica", "leve", "Tienda de campaña en mal estado; se reemplazó a tiempo.", "en_revision", "club-5", None, "2026-02-15 08:15"),
        Incidente("inc-3", "ev-2", "user-staff3", "salud", "leve", "Una asistente presentó una quemadura solar leve; atendida sin mayores consecuencias.", "resuelto", None, None, "2026-03-22 12:05"),
    ]

    return {
        "organizacion": organizacion,
        "organizaciones": [organizacion],
        "clubs": clubs,
        "users": users,
        "eventos": eventos,
        "criterios": criterios,
        "evento_club": evento_club,
        "evaluaciones": evaluaciones,
        "motivos": motivos,
        "penalizaciones": penalizaciones,
        "incidentes": incidentes,
    }