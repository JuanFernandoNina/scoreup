# Instalación y requisitos

## Requisitos

- Python **3.10 o superior** para ScoreUp. La guía de MkDocs indica 3.8 como
  mínimo, pero el proyecto utiliza una base de Python más reciente.
- `pip`, un editor como VS Code y un navegador.
- Conexión a Internet para descargar dependencias.

Ejecuta los comandos desde la raíz de `scoreup`, donde están `app.py` y
`mkdocs.yml`.

## Paso 1. Entorno virtual e instalación de MkDocs

Se usa `venv` para la documentación y se conserva `.venv` para la aplicación.
Los dos entornos son independientes.

```powershell
python -m venv venv
```

Activa el entorno según tu terminal:

| Terminal | Comando |
| --- | --- |
| Windows CMD | `venv\Scripts\activate.bat` |
| Windows PowerShell | `.\venv\Scripts\Activate.ps1` |
| Git Bash en Windows | `source venv/Scripts/activate` |
| macOS / Linux | `source venv/bin/activate` |

```powershell
python -m pip install mkdocs mkdocs-material
```

Para recrear las mismas versiones principales utilizadas en este laboratorio:

```powershell
python -m pip install -r requirements-docs.txt
```

!!! tip "Sin activar el entorno en Windows"
    Si PowerShell bloquea el activador, no necesitas cambiar su política.
    Usa directamente `venv\Scripts\python.exe -m mkdocs serve`.
    La activación solo facilita encontrar los ejecutables del entorno.

## Paso 2. Inicialización

Este comando se ejecutó una vez para generar la estructura base:

```powershell
mkdocs new .
```

```text
scoreup/
├── mkdocs.yml
├── requirements-docs.txt
└── docs/
    ├── index.md
    ├── instalacion.md
    ├── arquitectura.md
    ├── guia-uso.md
    └── api.md
```

!!! note "Proyecto ya inicializado"
    No hace falta volver a ejecutar `mkdocs new .`. Para continuar el trabajo,
    edita los archivos existentes.

## Paso 3. Configuración

`mkdocs.yml` define el nombre del sitio, el tema Material en español, la paleta
índigo/naranja, la búsqueda y las cinco páginas base más los recursos multimedia
de la actividad 4.2. También habilita
avisos y resaltado de código mediante extensiones de Markdown.

El servidor está configurado en `127.0.0.1:8080`.

## Paso 4. Contenido en Markdown

Las páginas están en `docs/`. Puedes escribir títulos con `#`, listas, tablas,
enlaces relativos y bloques de código. Por ejemplo:

````markdown
# Mi sección

Descripción de la funcionalidad.

```python
print("ScoreUp")
```
````

## Paso 5. Servidor local

Con `venv` activado:

```powershell
mkdocs serve
```

Abre **http://127.0.0.1:8080**. Los cambios en los archivos se recargan
automáticamente. Detén el servidor con **Ctrl+C** en su terminal.

!!! warning "Puerto de la guía"
    Aunque el PDF menciona después el puerto 8000, su configuración define
    8080. En este proyecto se utiliza **8080**.

## Paso 6. Compilación

```powershell
mkdocs build
```

El resultado queda en `site/`, con HTML, CSS, JavaScript y el índice de búsqueda.
No edites esa carpeta: se regenera a partir de `docs/` y `mkdocs.yml`.

Para comprobar que no hay advertencias de compilación:

```powershell
mkdocs build --strict
```

La publicación en GitHub Pages es una actividad posterior y no forma parte
de estos seis pasos.

## Ejecutar la aplicación ScoreUp

En **otra terminal**, utiliza el entorno de la aplicación, no el de MkDocs.
En una instalación nueva, créalo e instala sus dependencias:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

Si `.venv` ya existe, no necesitas crearlo de nuevo. La aplicación abre en
**http://127.0.0.1:5000** y crea su base con datos de ejemplo si no existe.

| Servicio | Dirección local | Entorno |
| --- | --- | --- |
| Documentación MkDocs | `http://127.0.0.1:8080` | `venv` |
| Aplicación ScoreUp | `http://127.0.0.1:5000` | `.venv` |
