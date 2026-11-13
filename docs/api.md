# API / Módulos

## Alcance de la interfaz HTTP

ScoreUp utiliza rutas Flask que renderizan HTML, procesan formularios o
descargan archivos. Esta sección es una referencia de módulos y rutas
representativas, **no una especificación de API REST JSON**.

Las operaciones protegidas requieren sesión y rol válido. Los formularios
POST también requieren un token CSRF; no basta con enviar una petición sin
contexto de sesión.

## Módulo `app.py`

Coordina autenticación, organización, permisos, evaluaciones, QR e informes.

| Método | Ruta | Función / acceso |
| --- | --- | --- |
| GET | `/` | Página principal. |
| GET, POST | `/login` | Formulario e inicio de sesión. |
| GET, POST | `/registro` | Alta de organización y administrador. |
| GET | `/admin` | Panel de administrador. |
| GET, POST | `/admin/clubes` | Listado y creación de clubes; administrador. |
| GET, POST | `/admin/eventos` | Listado y creación de eventos; administrador. |
| GET | `/admin/clubes/<club_id>/qr` | Tarjeta o imagen QR; administrador. |
| GET | `/qr/<token>` | Valida el QR y dirige al flujo autorizado. |
| GET | `/staff` | Panel del staff, con filtro opcional `club`. |
| POST | `/staff/evaluar/<club_id>` | Guarda o corrige una evaluación; staff. |
| POST | `/staff/incidente` | Registra un incidente; staff. |
| POST | `/staff/penalizar` | Aplica una penalización; staff. |
| POST | `/admin/eventos/<evento_id>/cerrar` | Cierra un evento válido; administrador. |
| GET | `/admin/reportes` | Avisos de correcciones; administrador. |
| GET | `/admin/exportar` | Exportación de resultados; administrador. |
| GET | `/director` | Resultados del club asociado al director. |

### Campos de evaluación

El formulario de `/staff/evaluar/<club_id>` incluye:

- `val_<id_criterio>`: un número finito entre 0 y 100 por criterio.
- `comentario`: texto opcional.
- `version`: `0` para una nota nueva o la versión vigente para corregir.
- `csrf_token`: token generado para la sesión.

Los nombres concretos de los criterios se generan desde los datos del evento.

## Módulo `calc.py`

| Función | Resultado |
| --- | --- |
| `porcentaje_ponderado(evaluacion, criterios)` | Suma de notas ponderadas. |
| `puntaje_evento(evaluacion, criterios, puntaje_maximo)` | Puntaje redondeado a dos decimales. |
| `evaluacion_principal(db, evento, club_id)` | Evaluación oficial o `None`. |
| `ranking_evento(db, evento)` | Filas ordenadas con puntaje, desempate y posición. |
| `ranking_temporada(db, temporada)` | Eventos y filas con bruto, descuentos y total. |
| `actividad_staff(db, evento)` | Evaluaciones oficiales por staff y respaldos históricos. |

### Ejemplo aislado de cálculo

Este ejemplo no necesita iniciar Flask ni abrir la base de datos:

```python
from data import Criterio, Evaluacion
from calc import porcentaje_ponderado, puntaje_evento

criterios = [
    Criterio("c1", "evento-demo", "Disciplina", 40),
    Criterio("c2", "evento-demo", "Participación", 60),
]
evaluacion = Evaluacion(
    "eval-demo", "evento-demo", "club-demo", "staff-demo",
    valores={"c1": 80, "c2": 90},
)

print(porcentaje_ponderado(evaluacion, criterios))  # 86.0
print(puntaje_evento(evaluacion, criterios, 200))  # 172.0
```

## Módulos `data.py` y `persist.py`

`data.py` contiene las entidades descritas en [Arquitectura](arquitectura.md)
y `seed()`, que proporciona datos iniciales de demostración.

`persist.py` ofrece `connect()`, `initialize()`, `load(connection=None)` y
`save(db, connection=None)`. Usa SQLite y admite elegir otro archivo mediante
`SCOREUP_DB`. Las migraciones de bases anteriores pueden generar un respaldo
automático `scoreup.db.backup-*`.

!!! warning "Efectos de importar la aplicación"
    `app.py` carga la base al importarse. Usa las pruebas con almacenamiento
    temporal para experimentar; no ejecutes ejemplos de modificación sobre
    la base de trabajo ni publiques sus respaldos.

## Pruebas automáticas

Desde la raíz del proyecto, utiliza el entorno de la **aplicación**:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

La suite define 22 pruebas y usa bases SQLite temporales. Cubre permisos,
CSRF, QR, flujo completo, evaluación única, concurrencia, correcciones,
aislamiento por organización, cierre, penalizaciones, exportaciones,
evidencias y migración.

La existencia de las pruebas no sustituye su ejecución ni la comprobación
manual del flujo con un celular en la red local.
