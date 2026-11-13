# ScoreUp — Sistema de Evaluación de Clubes de Conquistadores

<p align="center">
  <img src="image/landing-page.png" alt="Landing de ScoreUp con diseño azul y naranja" width="1000"/>
</p>

> Plataforma web para registrar, evaluar y calificar el desempeño de clubes de Conquistadores (y organizaciones similares) en eventos y temporadas.

Las capturas de esta página corresponden a la interfaz actual, generadas con una base aislada y datos ficticios de demostración; no muestran información de la instalación personal.

## Portada pública

La página `/` incluye diseño azul/naranja, ondas, vistas ilustrativas del producto, roles, guía de uso, preguntas frecuentes y una demostración del puntaje ponderado que no guarda datos. Tiene animaciones de entrada al hacer scroll, tarjetas flotantes, paralaje suave y barra de avance; respeta `prefers-reduced-motion` y conserva el contenido visible sin JavaScript. CSS, JavaScript e ilustraciones son locales, sin recursos externos. Los ejemplos están señalados como ilustrativos; no se publican datos de organizaciones.

Para verla si tienes una sesión iniciada, cierra sesión o abre una ventana privada: se conserva la redirección automática al panel del usuario. Prueba opcional en Edge: `.venv\Scripts\python.exe tests/manual_landing.py`.

**Login y registro** comparten la identidad azul/naranja de la portada: fondo con ondas, tarjeta blanca, animación suave y diseño adaptable. Recursos locales en `auth.css`/`auth.js`; botón para mostrar/ocultar contraseña y aviso de Bloq Mayús. Los errores conservan los campos no secretos, nunca la contraseña; se mantienen CSRF, acceso por roles y retorno al club después del login mediante QR. Prueba opcional con base temporal: `.venv\Scripts\python.exe tests/manual_auth.py`.

## Evaluación mediante QR (implementada)

Cada club tiene una tarjeta QR descargable e imprimible. El staff escanea con la cámara normal del celular e inicia sesión si hace falta; vuelve automáticamente al club. La primera evaluación guardada por **club y evento** es la oficial. Solo su autor puede corregirla mientras el evento esté abierto; cada corrección genera una notificación revisable en **Reportes**.

También puede entrar a **Staff → Escanear QR de un club**: cámara en vivo en HTTPS/localhost o lectura de una foto en la red local HTTP. El lector usa jsQR 1.4.0 incluido localmente; las imágenes no se suben. La cámara en vivo por HTTP usando la IP del PC está bloqueada por los navegadores: utiliza una foto o la cámara normal del celular.

El lector de fotos prueba varias resoluciones/recortes y recupera contraste; usa además BarcodeDetector cuando el navegador lo ofrece. Los QR nuevos contienen un identificador firmado más corto, con mayor margen blanco y tarjeta ampliada; las tarjetas anteriores siguen siendo válidas. Descarga nuevamente para obtener la versión menos densa. Ningún lector puede recuperar una foto muy desenfocada, con reflejos sobre el código o partes fuera del encuadre.

En Windows, **`INICIAR.bat`** inicia la aplicación y muestra una dirección de red para los QR. PC y teléfono deben compartir red. En **Clubes → QR del club** se puede corregir esa dirección antes de descargar o imprimir; no cambia la identidad del club ni su evento. Si hay un servidor anterior, debe cerrarse primero.

**Guía para probar desde el celular:** [documents/GUIA_PRUEBAS_QR.md](documents/GUIA_PRUEBAS_QR.md).

Las evaluaciones oficiales antiguas se conservan, igual que los respaldos históricos (que no cuentan en el ranking). Al migrar una base anterior se genera automáticamente una copia `scoreup.db.backup-*`. No borres `.secret_key`: mantiene válidos los QR entre reinicios.

### Uso en campamento sin internet

La propuesta consiste en una laptop con ScoreUp y un router que conecte los teléfonos por Wi-Fi local, sin necesidad de salida a Internet. El diagrama interactivo y sus escenarios están en [documents/solucion-sin-internet/index.html](documents/solucion-sin-internet/index.html); descárgalo y ábrelo en el navegador, o usa `ABRIR.bat` de esa carpeta. Es una explicación, no configura equipos ni demuestra un despliegue real: faltan pruebas físicas, preparar el lector QR offline y retirar las dependencias externas restantes.

---

## Table of Contents

- [About](#about)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [Configuration](#configuration)
- [Security](#security)
- [How to Contribute?](#how-to-contribute)
- [What's Next?](#whats-next)
- [License](#license)
- [Acknowledgements](#acknowledgements)
- [Author](#author)

---

## About

ScoreUp centraliza la información que hoy se maneja en planillas y hojas de cálculo: los administradores configuran eventos con criterios ponderados, el staff de cada evento evalúa a los clubes asignados, se registran incidentes y penalizaciones, y el sistema calcula automáticamente el **ranking por evento** y el **ranking de temporada**, con exportación a **Excel** y **PDF**.

### Panel de administrador

<p align="center">
  <img src="image/dashboard-admin.png" alt="Dashboard actual del administrador: indicadores, eventos y ranking" width="1000"/>
</p>

El administrador gestiona la organización completa: crea clubes, eventos, criterios y usuarios; supervisa incidentes, penalizaciones y resultados, y exporta los rankings oficiales.

El dashboard tiene diseño claro azul/naranja como la landing, menú lateral adaptable, buscador de clubes/eventos con `Ctrl+K`, indicadores reales, progreso de evaluación por evento y ranking de temporada con posiciones compartidas. Las evaluaciones pendientes cuentan solo inscripciones de eventos abiertos sin nota oficial; el ranking indica cuándo incluye eventos abiertos. No se muestran variaciones históricas inventadas. El acceso **Crear evento** abre directamente el formulario existente.

Prueba opcional en Edge con base temporal: `.venv\Scripts\python.exe tests/manual_admin_dashboard.py`; comprueba PC/móvil, búsqueda, menú, creación y selector de temporada. Todas las páginas que usan el layout admin cargan CSS y JavaScript locales, sin Tailwind CDN.

### Pantallas de gestión

Clubes, directorio de Miembros y Eventos usan tablas blancas con los acentos azules/naranja del dashboard. Incidentes, Penalizaciones, Accesos, Resultados y Reportes comparten estilos de tablas/formularios, búsqueda local y paginación de diez registros. En teléfonos, las tablas simples pasan a tarjetas con etiquetas de cada columna; las tablas complejas conservan desplazamiento horizontal. Sin JavaScript, los registros siguen visibles en tabla, pero la búsqueda/paginación local no se activa. Crear/editar/eliminar, importar miembros, descargar QR y gestionar eventos conservan sus rutas y controles del servidor.

El directorio `/admin/miembros` muestra solo miembros de la organización del administrador; para agregar/importar se accede al club correspondiente. No se agregaron descripciones ni estados ficticios al modelo de club. Prueba opcional: `.venv\Scripts\python.exe tests/manual_admin_management.py`.

Los estilos de utilidades están compilados en `static/admin-utilities.css`. Si cambias clases Tailwind de las plantillas admin, recompila desde la raíz:

```bash
npm exec --yes --package=tailwindcss@3.4.17 -- tailwindcss -i static/admin-utilities.src.css -o static/admin-utilities.css --content './templates/admin/**/*.html' --minify
```

No hace falta Node ni conexión a Internet para ejecutar la aplicación con ese CSS ya generado.

### Panel del staff evaluador

<p align="center">
  <img src="image/dashboard-staff.png" alt="Dashboard actual del staff: clubes, penalizaciones, incidentes y evaluación" width="1000"/>
</p>

El staff evalúa a los clubes de su evento asignando un valor 0–100 por cada criterio, reporta incidentes y aplica penalizaciones.

El panel incluye un resumen visual de avance y cuatro accesos: **Clubes** (búsqueda y estados), **Penalizaciones** (registro e historial propio), **Incidentes** (reporte con evidencia e historial propio) y **Evaluar** (Google Lens recomendado, lista de clubes y ficha con vista previa del puntaje). Menú lateral en PC y navegación inferior fija en celular, con estilos y JavaScript locales. Los historiales muestran únicamente los registros del usuario actual en su evento; los eventos cerrados son de solo lectura.

Prueba visual opcional con Edge y SQLite temporal: `.venv\Scripts\python.exe tests/manual_staff_dashboard.py`. Comprueba navegación, búsqueda, cálculo, formularios e historiales en PC y móvil, sin modificar los datos de la instalación.

### Panel del director

<p align="center">
  <img src="image/dashboard-director.png" alt="Dashboard del director: puntaje, posición y resultados publicados de su propio club" width="1000"/>
</p>

El director consulta el puntaje de temporada, su posición, penalizaciones y resultados de su propio club en eventos cerrados. Su acceso es de solo lectura, con selector de temporada y navegación adaptada al celular.

### Regenerar las capturas

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe tests/capture_readme.py
```

El script utiliza Microsoft Edge y una base SQLite temporal, cierra sus sesiones de prueba y guarda las cuatro imágenes en `image/`. No necesita ejecutar el servidor de trabajo ni modifica `scoreup.db`.

### Identidad común de los tres paneles

Admin, Staff y Director comparten `static/panel-theme.css` y `static/panel-effects.js`: encabezados azules con ondas, acciones principales naranja, aparición de tarjetas al hacer scroll y barra de progreso de página. Se conserva la distribución del staff. El director dispone de resumen, resultados por temporada y datos de su propio club, siempre de solo lectura y con resultados de eventos cerrados. Los efectos respetan movimiento reducido y no ocultan contenido sin JavaScript; no modifican datos ni permisos.

Los tres dashboards usan recursos locales. Otras pantallas basadas en `base.html`, como el lector QR alternativo, pueden conservar la dependencia CDN; no asumir que toda la aplicación está preparada para una instalación sin internet.

Prueba opcional de tema/scroll en Edge y SQLite temporal: `.venv\Scripts\python.exe tests/manual_panel_theme.py`.

**Mejoras para celular:** `static/mobile-panels.css` conserva el escritorio y adapta los controles táctiles, tamaños de campos y espacios de seguridad del teléfono. Staff/Director tienen navegación inferior fija, encabezado compacto y espacio de contenido para no tapar los botones finales. Admin usa menú desplegable con fondo de cierre y contenido principal inerte mientras está abierto. Las tarjetas de registros conservan los encabezados accesibles, búsqueda, paginación y acciones. Prueba opcional con emulación táctil de Edge: `.venv\Scripts\python.exe tests/manual_mobile_panels.py`; falta validar teclado y comportamiento en los teléfonos físicos.

---

## Features

- **Organización y usuarios** — Registrar una organización con su Admin inicial; roles con permisos: `admin`, `staff`, `director`.
- **Clubes y miembros** — Crear, renombrar y eliminar clubes; registrar miembros y **importarlos desde Excel**.
- **Eventos y criterios** — Crear eventos (fecha, lugar, tipo, temporada, puntaje máximo) y configurar criterios de evaluación con peso en %. El evento **solo puede cerrarse si los pesos suman 100 %**.
- **Evaluación QR** — Valores 0–100 y comentario. Una nota oficial por club/evento; correcciones solo por su autor y con historial de avisos para el administrador. No se asigna staff principal.
- **Incidentes y penalizaciones** — Catálogo de motivos de descuento, aplicación/anulación de penalizaciones y registro de incidentes con **evidencia fotográfica** y filtros por evento, club, tipo, gravedad y estado.
- **Resultados** — Ranking por evento (con desempate según el criterio de mayor peso) y ranking de temporada (puntaje bruto − penalizaciones). Exportación a **Excel** y **PDF**.
- **Directores** — Consultan solo la posición y los puntajes de su propio club.
- **Generación de accesos** — Creación masiva de usuarios Staff y Directores con contraseñas aleatorias, o importación desde Excel.

---

## Tech Stack

| Categoría | Tecnología |
|---|---|
| **Lenguaje** | Python 3.10+ |
| **Framework web** | Flask + Jinja2 |
| **Estilos** | CSS local y Tailwind compilado para Admin; CDN solo en pantallas heredadas |
| **Base de datos** | SQLite (persistencia vía repositorio propio) |
| **Excel** | openpyxl (importación/exportación) |
| **PDF** | ReportLab |
| **Seguridad** | Werkzeug (hash de contraseñas) |

---

## Architecture

Aplicación monolítica modular con separación inicial entre interfaz, cálculos, entidades y persistencia. `persist.py` es un adaptador de almacenamiento; Factory y una separación completa en servicios son propuestas de refactorización, no patrones ya implementados:

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
| `persist.py` | Adaptador SQLite: migraciones, recarga transaccional y restricción de evaluación única |
| `templates/` | Vistas web con Jinja2 + Tailwind |
| `static/` | CSS, JavaScript, lector QR local y evidencias privadas excluidas de Git |

---

## Project Structure

```
scoreup/
├── app.py               # Aplicación Flask y rutas
├── calc.py              # Cálculos y rankings
├── data.py              # Entidades de dominio (dataclasses)
├── persist.py           # Persistencia SQLite
├── requirements.txt     # Dependencias de la aplicación
├── requirements-dev.txt # Herramientas opcionales de pruebas visuales/capturas
├── README.md            # Este documento
├── documents/           # Propuesta académica del proyecto
├── image/               # Capturas de pantalla del sistema
├── templates/           # Plantillas Jinja2
│   ├── admin/           #   Panel de administrador
│   ├── staff/           #   Panel de staff evaluador
│   └── director/        #   Panel de director de club
└── static/              # Recursos estáticos (uploads)
```

---

## Getting Started

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

Abre **http://127.0.0.1:5000** en tu navegador. Para probar el QR desde el celular, abre el panel usando la **IP local del PC**, no localhost. Ambos dispositivos deben estar en la misma red. El servidor escucha en `0.0.0.0` por defecto, sin depurador; úsalo solo en una red de confianza. No es un servidor de producción.

> La base de datos `scoreup.db` se crea automáticamente con datos de ejemplo en la primera ejecución (no está versionada en el repositorio).

---

## Configuration

### Variables de entorno

| Variable | Descripción | Valor por defecto |
|---|---|---|
| `SECRET_KEY` / `FLASK_SECRET` | Clave de sesión y firma de QR (SECRET_KEY tiene prioridad) | Aleatoria, persistida en `.secret_key`, fuera de Git |
| `PORT` | Puerto del servidor | `5000` |
| `HOST` | Interfaz de escucha | `0.0.0.0` |
| `PUBLIC_BASE_URL` | Dirección accesible desde el teléfono, sin barra final | Dirección usada para abrir el panel |
| `SCOREUP_DB` | Archivo SQLite (útil para pruebas aisladas) | `scoreup.db` |

### Reglas de negocio

- La suma de los pesos de los criterios de un evento debe ser **100 %** para poder cerrarlo (`admin_evento_cerrar`).
- La primera evaluación guardada de un club en un evento es la oficial; SQLite impide duplicados y los guardados se serializan entre peticiones/procesos.
- Solo el autor puede corregir su nota; una versión obsoleta del formulario se rechaza para evitar sobrescrituras.
- Los criterios no cambian después de iniciar evaluaciones. Todos los participantes deben tener nota oficial antes de cerrar; los eventos cerrados son inmutables.
- Los empates en el ranking de evento se resuelven comparando el valor en el **criterio de mayor peso**.
- El puntaje de temporada es **Σ puntajes por evento − Σ penalizaciones de esa temporada**. El importe de cada penalización se conserva aunque cambie el catálogo.
- El administrador puede consultar resultados provisionales; el director solo recibe resultados de eventos cerrados de la temporada seleccionada.

---

## Security

- **Autenticación** por usuario y contraseña mediante cookie de sesión firmada de Flask (no una sesión almacenada en servidor). No se incluyen contraseñas generadas en la cookie.
- **Contraseñas** almacenadas con hash seguro de Werkzeug (`scrypt`/`pbkdf2`), nunca en texto plano.
- **Control de acceso por rol**: comprobaciones `require_login` / `require_rol`, redirección al login y respuesta **403** para roles no autorizados.
- **Aislamiento multi-tenant**: cada organización solo ve sus propios clubes, eventos, evaluaciones y usuarios.
- **Formularios** protegidos contra CSRF; imágenes verificadas con Pillow y límite de petición de 10 MB. Evidencias accesibles solo por admin/staff de la organización.
- **Límite actual:** esta es una versión académica para pruebas locales, no una instalación endurecida para Internet. No expongas las cuentas de ejemplo públicamente; un despliegue real requiere HTTPS, servidor WSGI y política de accesos/contraseñas más estricta.

### Pruebas automáticas

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Usan bases SQLite temporales y no modifican la base local. Cubren flujo completo, QR/login, formularios CSRF, evaluación única, concurrencia, correcciones, migración, permisos, aislamiento, cierre, penalizaciones y exportaciones.

---

## How to Contribute?

1. Haz **fork** del repositorio.
2. Crea una rama para tu funcionalidad: `git checkout -b feature/mi-mejora`.
3. Realiza tus cambios y prueba que el flujo end-to-end siga funcionando (crear evento → evaluar → ranking → exportar).
4. Envía un **pull request** describiendo el cambio.

Toda contribución debe respetar la arquitectura en capas y las reglas de negocio documentadas.

---

## What's Next?

- Aplicación móvil nativa (Flutter).
- Notificaciones automáticas por correo o mensajería.
- Integración con sistemas institucionales externos.
- Módulo de pagos o inscripciones.
- Sistema de autoevaluación por parte de los clubes.
- Predicción de desempeño mediante Machine Learning.

---

## License

Proyecto académico para el Taller de Programación. Uso educativo, sin fines comerciales.

---

## Acknowledgements

- **Taller de Programación** — Ingeniería de Sistemas (4to semestre).
- Documento de referencia: **PROPUESTA_ScoreUp.md** (análisis, requerimientos, arquitectura y justificación del proyecto).

---

## Author

<p align="center">
  <b>ScoreUp</b> — Desarrollado por:
</p>

- Juan Fernando Nina Cachi
- Axel Alberto Ticona Villegas
- Kevin Quispe Canaviri
- Erick Lanchimba Lanchimba

<p align="center">
  <i>Ingeniería de Sistemas · Universidad — Taller de Programación</i>
</p>
