# Base de demostración compartida

`scoreup-demo.db` contiene una copia anonimizada de los datos de prueba: organizaciones, clubes, miembros, eventos, criterios, evaluaciones, incidentes, penalizaciones e historial. **No contiene las contraseñas ni la clave de sesión de Fernando.** Las cuentas incluidas están bloqueadas con claves aleatorias descartadas; prepara tu copia antes de iniciar.

## Preparar en Windows

Desde la carpeta del proyecto, con Python 3.10 o superior:

```powershell
py -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe scripts\preparar_demo.py
.\INICIAR.bat
```

El asistente pide tres contraseñas propias: administrador, staff y director. Para esta demostración, todas las cuentas del mismo rol reciben la contraseña elegida para ese rol. No las publiques.

En Linux/macOS: crea/activa `.venv`, instala `requirements.txt`, ejecuta `python scripts/preparar_demo.py` y luego `python app.py`.

## Cuentas principales

| Rol | Usuario | Contraseña |
|---|---|---|
| Administrador | `admin.campamento` | La elegida para admin |
| Staff de Nudos y amarres | `staff.campamento` | La elegida para staff |
| Director de Orión | `director.campamento` | La elegida para director |

Las cuentas secundarias se identifican como `admin.demo.N`, `staff.demo.N` o `director.demo.N` y conservan sus asignaciones. Puedes consultarlas desde **Accesos**.

## Datos del campamento

- Cuatro eventos cerrados/publicados; el director de Orión puede ver sus resultados y el descuento de 3 puntos.
- Primeros auxilios abierto: falta la evaluación del club `pio`.
- Tres eventos nuevos sin calificar: Orientación y brújula, Pista de obstáculos y Arte de acampar; diez clubes inscritos en cada uno.
- Incidentes y penalizaciones ficticios para mostrar casos abiertos, en revisión y resueltos.
- Los nombres personales fueron sustituidos y los textos no identificados como ejemplos se anonimizaron. Las fotos privadas no se incluyen.

## Conservar tus datos y acceder por celular

El asistente **no reemplaza una base existente**. Si ya iniciaste la aplicación, detén el servidor y usa una carpeta nueva o prepara otra base:

```powershell
.venv\Scripts\python.exe scripts\preparar_demo.py --destino mi-demo.db
$env:SCOREUP_DB = (Resolve-Path mi-demo.db).Path
.\INICIAR.bat
```

Computadora: `http://localhost:5000`. Celular: la dirección IP que imprime `INICIAR.bat`, conectado al mismo Wi-Fi. Permite Python solo en una red de confianza. No abras puertos hacia internet.

Cada instalación genera su propia `.secret_key`: **descarga otra vez los QR desde tu copia**, porque las tarjetas firmadas en otra computadora no son válidas aquí. Para QR de celular, usa la IP local de tu computadora, no `localhost`.

La base pública es una foto de los datos de demostración; las modificaciones de tu copia local no se suben a Git.
