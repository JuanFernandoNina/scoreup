# ScoreUp · Sistema de Evaluación de Clubes

> Plataforma web para registrar, evaluar y calificar el desempeño de clubes de Conquistadores (y organizaciones similares) en eventos y temporadas.

ScoreUp centraliza la información que hoy se maneja en planillas y hojas de cálculo: los administradores configuran eventos con criterios ponderados, el staff de cada evento evalúa a los clubes asignados, se registran incidentes y penalizaciones, y el sistema calcula automáticamente el **ranking por evento** y el **ranking de temporada**, con exportación a **Excel** y **PDF**.

## ✨ Funcionalidades

- **Organización y usuarios** — Registrar una organización con su Admin inicial; roles con permisos: `admin`, `staff`, `director`.
- **Clubes y miembros** — Crear, renombrar y eliminar clubes; registrar miembros y **importarlos desde Excel**.
- **Eventos y criterios** — Crear eventos (fecha, lugar, tipo, temporada, puntaje máximo) y configurar criterios de evaluación con peso en %. El evento **solo puede cerrarse si los pesos suman 100 %**.
- **Evaluación** — El staff registra valores 0–100 por criterio más un comentario por club. Se identifica la **evaluación oficial** (la del staff principal) y los respaldos.
- **Incidentes y penalizaciones** — Catálogo de motivos de descuento, aplicación/anulación de penalizaciones y registro de incidentes con **evidencia fotográfica** y filtros por evento, club, tipo, gravedad y estado.
- **Resultados** — Ranking por evento (con desempate según el criterio de mayor peso) y ranking de temporada (puntaje bruto − penalizaciones). Exportación a **Excel** y **PDF**.
- **Directores** — Consultan solo la posición y los puntajes de su propio club.
- **Generación de accesos** — Creación masiva de usuarios Staff y Directores con contraseñas aleatorias, o importación desde Excel.

## 🛠️ Tecnologías

- **Python 3.10+**
- **Flask** + **Jinja2** (HTML/CSS con Tailwind CSS)
- **SQLite** (persistencia vía repositorio propio)
- **openpyxl** (importación/exportación Excel) y **ReportLab** (exportación PDF)

## 🧱 Arquitectura

Aplicación monolítica en capas (interfaz → casos de uso → dominio → repositorio), coherente con los principios **SOLID** y los patrones **Repository** y **Factory**:

```
    Admin · Staff · Director
              │
        ┌─────▼──────┐
        │  Interfaz  │  templates/ (Jinja2) + app.py
        └─────┬──────┘
        ┌─────▼──────┐
        │ Casos uso  │  app.py (rutas, sesión, control por rol)
        └─────┬──────┘
        ┌─────▼──────┐
        │  Dominio   │  data.py (entidades) + calc.py (lógica de negocio)
        └─────┬──────┘
        ┌─────▼──────┐
        │ Acceso a   │  persist.py (repositorio)
        │  datos     │
        └─────┬──────┘
              ▼
        ┌───────────┐
        │  SQLite   │  scoreup.db
        └───────────┘
```

| Módulo | Responsabilidad |
|---|---|
| `app.py` | Rutas HTTP, autenticación, control de acceso por rol y casos de uso |
| `data.py` | Entidades de dominio (`dataclasses`): Club, Usuario, Evento, Evaluación… |
| `calc.py` | Reglas de negocio: porcentaje ponderado, puntaje, rankings y desempates |
| `persist.py` | Repositorio (Adapter sobre SQLite): guarda y recarga todo el estado |
| `templates/` | Vistas web con Jinja2 + Tailwind |
| `static/` | Archivos estáticos (imágenes subidas de incidentes) |

## 📁 Estructura del proyecto

```
scoreup-flask/
├── app.py               # Aplicación Flask y rutas
├── calc.py              # Cálculos y rankings
├── data.py              # Entidades de dominio (seed de demostración)
├── persist.py           # Persistencia SQLite
├── requirements.txt     # Dependencias
├── PROPUESTA_ScoreUp.md # Documento académico (propuesta del proyecto)
├── templates/           # Plantillas Jinja2
│   ├── admin/           #   Panel de administrador
│   ├── staff/           #   Panel de staff evaluador
│   └── director/        #   Panel de director de club
└── static/              # Recursos estáticos
```

## 🚀 Puesta en marcha

### 1. Requisitos

- Python 3.10 o superior
- (Opcional) `git`

### 2. Crear el entorno e instalar dependencias

```bash
# Windows (PowerShell)
py -m venv .venv
.venv\Scripts\activate

# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
```

### 3. Ejecutar

```bash
python app.py
```

Abre **http://127.0.0.1:5000** en tu navegador.

> La base de datos `scoreup.db` se crea automáticamente con datos de ejemplo en la primera ejecución (no está versionada en el repositorio).

### 4. Cuentas de demostración

El sistema incluye datos de ejemplo y estas credenciales:

| Rol | Usuario | Contraseña | Descripción |
|---|---|---|---|
| **Admin** | `admin` | `admin` | Gestiona la organización completa |
| **Staff** | `elena` | `staff` | Staff del *Campamento de Invierno* (evento cerrado) |
| **Staff** | `roberto` | `staff` | Staff del *Campamento de Invierno* (evento cerrado) |
| **Staff** | `luisa` | `staff` | Staff de la *Reunión Mensual de Marzo* (evento cerrado) |
| **Staff** | `tomas` | `staff` | Staff del *Campamento Regional* (evento abierto — evaluable) |
| **Director** | `lucia` | `director` | Directora de *Tigres del Valle* |
| **Director** | `hugo` | `director` | Director de *Águilas del Norte* |

También puedes hacer clic en **“Crear cuenta de Admin”** desde la portada para registrar una organización nueva (multi-tenant: cada organización solo ve sus propios datos).

## ⚖️ Reglas de negocio

- La suma de los pesos de los criterios de un evento debe ser **100 %** para poder cerrarlo (`admin_evento_cerrar`).
- La evaluación oficial de un club es la del **staff principal** asignado en el evento.
- Los empates en el ranking de evento se resuelven comparando el valor en el **criterio de mayor peso**.
- El puntaje de temporada es **Σ puntajes por evento − Σ penalizaciones**.

## 📄 Documentación

La propuesta académica completa (problema, requerimientos, historias de usuario, arquitectura, SOLID, patrones y DDD) está en **[PROPUESTA_ScoreUp.md](PROPUESTA_ScoreUp.md)**.

## 🧪 Verificación rápida

Con el servidor en marcha y usando las cuentas demo:

1. Ingresa como `admin` → crea un evento, define criterios (pesos que sumen 100 %), asigna clubes y staff.
2. Cerciórate de que el evento no se cierra si los pesos no suman 100 %.
3. Ingresa como `tomas` → evalúa los clubes del *Campamento Regional* (valores 0–100), registra un incidente con foto y aplica una penalización.
4. Vuelve como `admin` → revisa `Resultados`, cambia la vista a **evento** o **temporada**, y descarga el ranking en Excel o PDF.
5. Ingresa como `lucia` → consulta la posición y puntajes de *Tigres del Valle*.

## 📜 Licencia

Proyecto académico para el Taller de Programación. Uso educativo, sin fines comerciales.