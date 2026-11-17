# ScoreUp — prueba completa con QR y celular

## 1. Iniciar el proyecto

Desde PowerShell, en la raíz de ScoreUp:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

Mantén esa terminal abierta. Para detenerlo, `Ctrl+C`. Si ya hay un servidor viejo abierto, detenlo antes de arrancar el nuevo.

Alternativa en Windows: abre `INICIAR.bat`. Detecta una IPv4 de un adaptador físico activo y la usa como dirección pública de los QR durante esa ejecución. Si tienes varias redes, comprueba que sea accesible desde el celular. No modifica el firewall.

La base existente se migra sin borrar notas oficiales ni respaldos antiguos. Antes de esa migración se crea `scoreup.db.backup-*`. La clave aleatoria está en `.secret_key`: no la compartas ni la borres, porque cambiarla invalida sesiones y QR ya impresos. Para respaldar la instalación conserva la base, esa clave y las fotos de `static/uploads/` (con el servidor detenido).

## 2. Conectar el teléfono

1. PC y celular en el **mismo Wi-Fi de confianza** (no una red de invitados con aislamiento de dispositivos).
2. Ejecuta `ipconfig` en PowerShell y busca la dirección IPv4 del adaptador Wi-Fi activo.
3. En el PC y en el celular abre `http://IP-DEL-PC:5000`. Por ejemplo, `http://192.168.1.20:5000`.
4. Si Windows solicita permiso, permite Python **solo en redes privadas**. No desactives el firewall. Si no aparece el aviso y el celular no conecta, revisa la regla de entrada para Python/TCP 5000 en el perfil privado.

**No uses `localhost`, `127.0.0.1` ni `0.0.0.0` en el teléfono.** Localhost allí es el propio celular. No abras puertos del router ni publiques este servidor en Internet.

Si vas a administrar desde localhost pero necesitas imprimir enlaces para el celular, configura primero:

```powershell
$env:PUBLIC_BASE_URL="http://192.168.1.20:5000"
.\.venv\Scripts\python.exe app.py
```

Sustituye la IP por la de tu PC. Si cambia la IP debes regenerar/imprimir la tarjeta; el token de identidad del club sigue siendo válido, pero el enlace antiguo apunta a otra dirección.

## 3. Preparar una prueba limpia

Recomendado: en el PC abre **Crear cuenta de Admin** para registrar una organización de prueba. Así no modificas los resultados de ejemplo.

- [ ] Crear dos clubes: Club A y Club B.
- [ ] Crear un evento de prueba con temporada y puntaje máximo, por ejemplo 100.
- [ ] Agregar criterios: Disciplina 40%, Participación 40%, Puntualidad 20%.
- [ ] Agregar ambos clubes como participantes del evento. **No se asigna staff principal.**
- [ ] Crear dos cuentas Staff con usuarios distintos y asignar ambas al mismo evento.
- [ ] Crear un Director asignado al Club A, desde Usuarios (o generar accesos masivos).
- [ ] Desde Clubes → **QR del club**, abrir la tarjeta de cada club.
- [ ] Descargar el PNG e imprimir o mostrar el QR en la pantalla del PC.

Comprueba que el enlace de la tarjeta contiene la IP del PC, no localhost. El QR es estable por club y organización, no por evento; se aplica al evento asignado al staff que lo escanea.

La tarjeta incluye **Dirección del servidor para el celular → Actualizar QR**. Puedes introducir `http://IP-DEL-PC:5000` sin reiniciar; tanto la imagen como **Descargar PNG** usarán esa dirección. El ajuste afecta esa tarjeta, no otras pestañas ni la configuración global.

## 4. Escanear y evaluar

Puedes usar la **cámara normal del celular** o Google Lens para abrir el enlace sin instalar una app.

También puedes iniciar sesión como staff y pulsar **Escanear QR de un club**:

- **Elegir imagen del QR:** abre archivos/galería y es la única opción de importación visible en esa tarjeta. La captura de foto se realiza desde **Activar cámara**, sin duplicar otro selector en la tarjeta. Ambas vías funcionan en HTTP por Wi-Fi. Con **Usar lectura avanzada QReader** activado se envía una copia JPEG reducida al servidor de ScoreUp; se procesa de forma transitoria, sin guardarse como evidencia. Desmarcarlo conserva lectura local con jsQR. El navegador acepta archivos de hasta 15 MB y reduce a 2400 píxeles antes del envío; el servidor limita la imagen recibida a 8 MB y 32 megapíxeles.
- **Activar cámara:** abre directamente la captura de fotografía. Funciona también por HTTP local; confirmar la foto inicia la lectura. En celulares compatibles solicita la cámara trasera; otros navegadores pueden mostrar un selector de cámara/archivos.
- **Escaneo en vivo:** opción secundaria visible solo en HTTPS o localhost compatibles, con permiso del navegador. Detener cámara o salir de la pantalla libera el acceso. Si se deniega, el botón principal sigue disponible para tomar una foto.
- Con QReader activo, la cámara intenta lectura local y envía como máximo un fotograma en curso al servidor cuando no lo reconoce localmente. QReader se ejecuta en CPU con un modelo reutilizado; si está ocupado o no está disponible se conserva la alternativa local.
- La aplicación solo abre rutas QR de ScoreUp en el servidor actual; la firma, organización, inscripción del club y evento del staff se verifican en el servidor. Una imagen sin QR o con un enlace ajeno muestra un aviso.

Si el PNG original funciona pero una foto no: vuelve a descargar la tarjeta actual (QR firmado más corto y menos denso), muestra el QR grande o imprime al menos 6 cm de ancho, encuadra de frente y evita reflejos. El lector intenta distintas resoluciones, recortes y recuperación de contraste; espera a que termine el análisis. Las tarjetas antiguas siguen siendo válidas. Para reproducir un fallo hace falta la **foto que falla**, no solo el PNG original.

- [ ] Escanear Club A sin sesión: aparece Login.
- [ ] Iniciar sesión con Staff 1: vuelve al Club A, no al listado general.
- [ ] Introducir 80, 90 y 100 en los criterios y guardar. Con pesos 40/40/20 y máximo 100, el resultado esperado es **88 puntos**.
- [ ] Recargar: la nota sigue guardada.
- [ ] Salir, entrar con Staff 2 y escanear Club A: debe indicar **ya evaluado** y no permitir reemplazar la nota.
- [ ] Evaluar Club B con Staff 2: el primer guardado debe funcionar.

Para mantener dos sesiones a la vez usa otro teléfono, otro navegador o una ventana privada. Si sigues conectado como Admin y escaneas el QR, recibirás 403: el QR de evaluación requiere una cuenta Staff.

## 5. Correcciones y notificaciones

- [ ] Volver a Staff 1 y escanear Club A mientras el evento esté abierto.
- [ ] Cambiar una nota y/o comentario y guardar corrección.
- [ ] En el PC, Admin → **Reportes → Correcciones de evaluaciones**.
- [ ] Comprobar club, evento, evaluador, fecha, valores anteriores/nuevos y comentarios.
- [ ] Marcar revisado o descartar el aviso: la nota corregida y el ranking **no deben revertirse**.
- [ ] Intentar guardar desde un formulario antiguo abierto en otra pestaña: debe pedir recargar, no sobrescribir una corrección posterior.

## 6. Penalizaciones, incidentes y cierre

- [ ] Crear un motivo de descuento de 5 puntos y aplicarlo a Club A desde Staff.
- [ ] Comprobar que el ranking de **temporada** descuenta 5 puntos; el ranking de evento muestra puntaje bruto, sin descuentos.
- [ ] Cambiar el descuento del catálogo: la penalización ya aplicada debe conservar sus 5 puntos históricos.
- [ ] Reportar incidente con foto válida y revisar desde Admin → Incidentes.
- [ ] Intentar cerrar con un club pendiente: el sistema debe impedirlo.
- [ ] Con todos los clubes evaluados y criterios al 100%, cerrar el evento.
- [ ] Escanear otra vez: solo lectura; no permite correcciones, incidentes ni penalizaciones.
- [ ] Revisar con la cuenta Director: ve únicamente los resultados de su club correspondientes a eventos cerrados de la temporada.
- [ ] Exportar ranking por evento y temporada a Excel/PDF; abrir ambos archivos.
- [ ] Detener y reiniciar el servidor: notas, reportes y QR deben seguir funcionando.

Los criterios se bloquean al empezar a evaluar para impedir que cambien puntajes ya registrados. No se puede quitar del evento a un club ya evaluado ni anular descuentos de un evento cerrado.

## 7. Si algo falla

- **No conecta desde celular:** revisar IP, puerto, mismo Wi-Fi, VPN, aislamiento del punto de acceso y permiso privado del firewall.
- **400 al guardar:** sesión/formulario caducado o dato inválido; recargar y volver a intentar.
- **403:** rol incorrecto o cuenta sin evento válido.
- **404 al escanear:** QR alterado, clave cambiada, club eliminado o club fuera del evento/organización del staff.
- **409:** evento cerrado, club ya evaluado por otro staff o formulario obsoleto. El mensaje explica qué hacer.
- **413 al subir foto:** reducir tamaño; el límite total de petición es 10 MB.
- **QR no se lee:** descargar PNG, mostrarlo completo y aumentar brillo/tamaño; evitar recortes o impresiones borrosas.

Al reportar un fallo anota: pantalla, rol, pasos y mensaje mostrado. No compartas contraseñas, `.secret_key` ni cookies.

## Verificación automática

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Las pruebas se ejecutan con SQLite temporal y no usan tu base local. La validación física de lectura con la cámara, impresión, Wi-Fi e interfaz móvil corresponde a esta lista manual.

Verificación adicional opcional en Edge (requiere `playwright` en el entorno de desarrollo): `.venv\Scripts\python.exe tests/manual_browser_qr.py`. Prueba descarga PNG, lectura real de imagen, guardado y recarga, rechazo de imágenes sin QR/enlaces ajenos, dirección antigua, permiso denegado y vídeo con cámara simulada. Usa SQLite temporal y no sustituye la prueba física con celular.

Para comprobar lectura de un archivo concreto y sus variantes sintéticas: `.venv\Scripts\python.exe tests/manual_photo_qr.py "ruta\qr.png"`. Comprueba el original, contraste bajo, giro/desenfoque leve, QR pequeño en una foto grande e inclinación moderada; intercepta la navegación sin modificar datos reales. Son simulaciones, no una validación de la cámara física.
