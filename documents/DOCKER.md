# ScoreUp con Docker

## Inicio en Windows

Requiere Docker Desktop iniciado con contenedores Linux. Desde la raíz de ScoreUp:

La imagen incluye QReader, PyTorch CPU y las bibliotecas de lectura. La primera construcción descarga el modelo QR: tarda más y ocupa más espacio que la versión sin QReader. El modelo se incluye en la imagen para no necesitar descargarlo al escanear en campamento.

```powershell
docker compose up -d --build
docker compose ps
```

Abrir **http://localhost:5001**. La primera instalación está vacía: entrar a **Crear cuenta** para registrar la organización y su administrador con una contraseña propia. No incluye cuentas ni contraseñas de demostración.

La instalación Docker es independiente de `scoreup.db` y `.secret_key` de la carpeta del proyecto. No importa ni reemplaza sus datos. El servidor Python existente puede seguir en el puerto 5000.

## Celulares y tarjetas QR

PC y celulares deben compartir la misma red. Usar `http://IP-DE-LA-LAPTOP:5001`, nunca `localhost` desde un teléfono. Para conocer la IP, consultar `ipconfig` en Windows.

En PowerShell se puede fijar la dirección para las nuevas tarjetas:

```powershell
$env:SCOREUP_PUBLIC_BASE_URL = "http://192.168.1.20:5001"
docker compose up -d
```

Sustituir la dirección de ejemplo por la IP real. También se puede ajustar desde **Clubes → QR**. Si cambia la red/IP, actualizar la dirección y regenerar las tarjetas. Las tarjetas de otra instalación usan otra clave y no son válidas en la instalación nueva.

El puerto 5001 se publica en las interfaces del PC. El firewall de Windows puede requerir autorización para la red privada; esta configuración no modifica el firewall ni abre puertos del router a Internet. Para limitarlo a la computadora:

```powershell
$env:SCOREUP_BIND_IP = "127.0.0.1"
docker compose up -d
```

Por HTTP local, el lector admite fotografía o galería. Docker no habilita la cámara web en vivo sobre HTTP por IP ni cifra las credenciales: para esos fines se necesita HTTPS. No exponer esta configuración directamente a Internet.

## Datos persistentes y seguridad

El volumen de Compose `scoreup-data` se monta en `/data` y conserva:

| Ruta | Contenido |
|---|---|
| `/data/scoreup.db` | Base SQLite de esta instalación |
| `/data/.secret_key` | Clave de sesión y firma de QR |
| `/data/uploads/` | Fotografías de incidentes |

Los cambios permanecen al reiniciar o recrear el contenedor. **No ejecutar `docker compose down -v` ni borrar el volumen:** elimina datos, fotos y clave QR. Un volumen persistente no sustituye los respaldos.

La imagen no contiene la base personal, la demo compartible, las claves, `.env`, Git, los respaldos ni fotografías de usuarios. El contenedor corre sin privilegios, con código de solo lectura y escritura únicamente en el volumen y `/tmp`.

Gunicorn atiende Flask con **un worker y cuatro threads**. No aumentar workers ni réplicas: la aplicación actual mantiene datos y bloqueos por proceso, y no está diseñada para escalar de esa forma.

## Comandos de operación

```powershell
# Estado y registros (no muestran contraseñas)
docker compose ps
docker compose logs --tail 50 web

# Reiniciar
docker compose restart web

# Actualizar código y recrear conservando el volumen
docker compose up -d --build

# Detener conservando datos
docker compose down

# Cambiar el puerto publicado
$env:SCOREUP_PORT = "5002"
docker compose up -d
```

## Respaldo completo

Ejecutar desde la raíz y usar un destino nuevo para cada respaldo. La aplicación debe permanecer detenida durante la copia para que SQLite y las fotos sean coherentes:

```powershell
docker compose stop web
New-Item -ItemType Directory -Path .\respaldos\docker-2026-11-17
docker compose cp web:/data/. .\respaldos\docker-2026-11-17
docker compose start web
```

Guardar la copia de manera privada: contiene datos, hashes de acceso, fotografías y la clave de firma. No publicarla en GitHub. Comprobar la restauración en una instalación separada antes de depender del respaldo. Para migrar la instalación actual a Docker se necesitan una copia consistente de su base, su clave y sus fotos; no copiar únicamente la base ni mezclar instalaciones. Esta configuración no realiza esa migración automáticamente.

## Funcionamiento sin internet

La primera construcción descarga la imagen Python y las librerías. Prepararla antes de salir. Una vez construida, puede iniciarse sin descargar de nuevo:

```powershell
docker compose up -d --no-build --pull never
```

La comunicación con teléfonos sigue necesitando una red local funcional. Los recursos de los paneles y el lector QR son locales, pero Docker no garantiza que toda pantalla heredada carezca de dependencias externas. Probar el recorrido completo, la cámara y la impresión en los equipos reales.

## Pruebas de la configuración

Desde un entorno Python con las dependencias del proyecto:

```powershell
python -m unittest discover -s tests -p "test_*.py"
python tests/manual_docker.py
```

La segunda prueba requiere la imagen `scoreup:local` ya construida. Crea un contenedor y un volumen temporales exclusivos; registra una cuenta ficticia, crea un club, descarga su QR y comprueba la conservación de base, firma, sesión y un archivo de evidencia tras recrear el contenedor. Elimina únicamente esos recursos temporales. No utiliza el volumen de trabajo ni los datos personales.
