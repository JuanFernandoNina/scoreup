/* jsQR local + lectura avanzada QReader en el servidor, con consentimiento visible. */
(() => {
  const video = document.getElementById('preview');
  const canvas = document.getElementById('scan-canvas');
  const context = canvas.getContext('2d', { willReadFrequently: true });
  const status = document.getElementById('scan-status');
  const start = document.getElementById('start-camera');
  const liveStart = document.getElementById('start-live-camera');
  const stopButton = document.getElementById('stop-camera');
  liveStart.hidden = !window.isSecureContext || !navigator.mediaDevices?.getUserMedia;
  const advanced = document.getElementById('qreader-enabled');
  const readerUrl = document.currentScript.dataset.readerUrl;
  const csrf = document.querySelector('meta[name="csrf-token"]').content;
  let serverController = null;
  let serverReading = false;
  let lastServerRead = 0;
  let liveServerAvailable = true;
  let stream = null;
  let frame = null;
  let starting = false;
  let generation = 0;
  let readingPhoto = false;
  function stop() {
    generation += 1;
    if (serverController) serverController.abort();
    if (frame !== null) cancelAnimationFrame(frame);
    frame = null;
    if (stream) stream.getTracks().forEach(track => track.stop());
    stream = null;
    video.srcObject = null;
    video.hidden = true;
    stopButton.hidden = true;
    start.disabled = false;
    liveStart.disabled = false;
  }
  function openCode(value) {
    try {
      const url = new URL(value, location.origin);
      if (!['http:', 'https:'].includes(url.protocol) || !/^\/qr\/[A-Za-z0-9_.-]+$/.test(url.pathname) || url.search || url.hash) {
        throw new Error('invalid');
      }
      // Solo navegar en esta instalación; la firma y los permisos se verifican en el servidor.
      stop();
      status.textContent = 'QR leído. Abriendo el club en tu evento…';
      location.assign(url.pathname);
      return true;
    } catch (_) {
      status.textContent = 'El código no es un QR de club de ScoreUp. Prueba con la tarjeta del administrador.';
      return false;
    }
  }
  function decode(source, width, height, maxSide = 1600, region = [0, 0, 1, 1]) {
    const [x, y, w, h] = region;
    const cropWidth = width * w;
    const cropHeight = height * h;
    const scale = Math.min(1, maxSide / Math.max(cropWidth, cropHeight));
    canvas.width = Math.max(1, Math.round(cropWidth * scale));
    canvas.height = Math.max(1, Math.round(cropHeight * scale));
    context.fillStyle = 'white';
    context.fillRect(0, 0, canvas.width, canvas.height);
    context.drawImage(source, width * x, height * y, cropWidth, cropHeight, 0, 0, canvas.width, canvas.height);
    const pixels = context.getImageData(0, 0, canvas.width, canvas.height);
    const options = { inversionAttempts: 'attemptBoth' };
    const code = jsQR(pixels.data, pixels.width, pixels.height, options);
    if (code) return code;
    // Recuperar contraste en fotos grises/lavadas sin depender del servidor.
    const histogram = new Uint32Array(256);
    let samples = 0;
    for (let i = 0; i < pixels.data.length; i += 64) {
      const gray = Math.round(0.299 * pixels.data[i] + 0.587 * pixels.data[i + 1] + 0.114 * pixels.data[i + 2]);
      histogram[gray] += 1;
      samples += 1;
    }
    let low = 0;
    let high = 255;
    let count = 0;
    while (low < 255 && count + histogram[low] < samples * 0.02) count += histogram[low++];
    count = 0;
    while (high > low && count + histogram[high] < samples * 0.02) count += histogram[high--];
    if (high - low >= 16 && high - low < 200) {
      for (let i = 0; i < pixels.data.length; i += 4) {
        const gray = 0.299 * pixels.data[i] + 0.587 * pixels.data[i + 1] + 0.114 * pixels.data[i + 2];
        const value = Math.max(0, Math.min(255, (gray - low) * 255 / (high - low)));
        pixels.data[i] = pixels.data[i + 1] = pixels.data[i + 2] = value;
      }
      return jsQR(pixels.data, pixels.width, pixels.height, options);
    }
    return null;
  }
  async function decodePhoto(image, current) {
    // El detector del dispositivo puede corregir perspectiva mejor que jsQR.
    // No depender de él: muchos navegadores no lo incluyen.
    if ('BarcodeDetector' in window) {
      try {
        const detector = new BarcodeDetector({ formats: ['qr_code'] });
        const codes = await detector.detect(image);
        if (current !== generation) return null;
        if (codes.length) return { data: codes[0].rawValue };
      } catch (_) { /* Continuar con el decodificador local. */ }
    }
    // Una foto de varios megapíxeles puede perder los módulos pequeños al
    // reducirla a 1600 px. Probar tamaños y recortes sin exigir otra foto.
    const attempts = [
      [1200, [0, 0, 1, 1]],
      [2600, [0, 0, 1, 1]],
      [1800, [0.15, 0.15, 0.7, 0.7]],
      [1600, [0.3, 0.3, 0.4, 0.4]],
      [1600, [0, 0, 0.6, 0.6]],
      [1600, [0.4, 0, 0.6, 0.6]],
      [1600, [0, 0.4, 0.6, 0.6]],
      [1600, [0.4, 0.4, 0.6, 0.6]],
    ];
    for (let i = 0; i < attempts.length; i += 1) {
      if (current !== generation) return null;
      status.textContent = `Analizando foto… intento ${i + 1} de ${attempts.length}.`;
      // Permitir que el navegador muestre el avance entre intentos.
      await new Promise(resolve => setTimeout(resolve, 0));
      if (current !== generation) return null;
      const [size, region] = attempts[i];
      const code = decode(image, image.naturalWidth, image.naturalHeight, size, region);
      if (code) return code;
    }
    return null;
  }
  async function decodeOnServer(source, width, height, current, quietMiss = false) {
    if (serverReading) return null;
    serverReading = true;
    const controller = new AbortController();
    serverController = controller;
    const timeout = setTimeout(() => controller.abort(), 30000);
    try {
      const capture = document.createElement('canvas');
      const scale = Math.min(1, 2400 / Math.max(width, height));
      capture.width = Math.max(1, Math.round(width * scale));
      capture.height = Math.max(1, Math.round(height * scale));
      capture.getContext('2d').drawImage(source, 0, 0, capture.width, capture.height);
      const blob = await new Promise(resolve => capture.toBlob(resolve, 'image/jpeg', 0.94));
      if (!blob || current !== generation || !advanced.checked) return null;
      const form = new FormData();
      form.append('imagen', blob, 'qr.jpg');
      const response = await fetch(readerUrl, {
        method: 'POST', body: form, credentials: 'same-origin',
        headers: { 'X-CSRFToken': csrf, 'Accept': 'application/json' }, signal: controller.signal,
      });
      if (current !== generation) return null;
      if (response.redirected) throw new Error('Tu sesión pudo finalizar. Vuelve a iniciar sesión.');
      const result = await response.json().catch(() => ({}));
      if (!response.ok) {
        if (quietMiss && (response.status === 422 || result.code === 'reader_busy')) return null;
        const error = new Error(result.error || 'No se pudo leer la foto con QReader.');
        error.code = result.code;
        throw error;
      }
      return { data: result.path };
    } finally {
      clearTimeout(timeout);
      if (serverController === controller) serverController = null;
      serverReading = false;
    }
  }
  function scan() {
    if (!stream) return;
    if (video.readyState >= 2 && video.videoWidth) {
      const code = decode(video, video.videoWidth, video.videoHeight);
      if (code && openCode(code.data)) return;
      if (advanced.checked && liveServerAvailable && !serverReading && performance.now() - lastServerRead > 3500) {
        lastServerRead = performance.now();
        const current = generation;
        decodeOnServer(video, video.videoWidth, video.videoHeight, current, true).then(result => {
          if (current === generation && result) openCode(result.data);
        }).catch(error => {
          if (current !== generation || error.name === 'AbortError') return;
          liveServerAvailable = false;
          status.textContent = 'QReader no pudo leer el fotograma. La lectura local continúa; también puedes tomar una foto.';
        });
      }
    }
    frame = requestAnimationFrame(scan);
  }
  function takePhoto() {
    if (readingPhoto) return;
    stop();
    status.textContent = 'Toma una foto del QR completo. Se leerá al confirmar la fotografía.';
    // Abrir dentro del gesto del usuario, sin esperar permisos de getUserMedia.
    // capture="environment" solicita la cámara trasera en celulares compatibles.
    document.getElementById('qr-camera').click();
  }
  start.addEventListener('click', takePhoto);
  liveStart.addEventListener('click', async () => {
    if (starting || stream || readingPhoto) return;
    if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
      takePhoto();
      return;
    }
    starting = true;
    start.disabled = true;
    liveStart.disabled = true;
    const current = ++generation;
    try {
      const camera = await navigator.mediaDevices.getUserMedia({ video: {
        facingMode: { ideal: 'environment' }, width: { ideal: 1920 }, height: { ideal: 1080 },
      }, audio: false });
      if (current !== generation) {
        camera.getTracks().forEach(track => track.stop());
        return;
      }
      stream = camera;
      liveServerAvailable = true;
      lastServerRead = performance.now();
      video.srcObject = stream;
      video.hidden = false;
      stopButton.hidden = false;
      await video.play();
      status.textContent = 'Apunta al QR completo del club, con buena luz.';
      scan();
    } catch (_) {
      stop();
      status.textContent = 'No se pudo abrir la cámara en vivo. Pulsa «Activar cámara» para tomar una foto del QR.';
    } finally {
      starting = false;
      if (!stream) { start.disabled = false; liveStart.disabled = false; }
    }
  });
  stopButton.addEventListener('click', () => {
    stop();
    status.textContent = 'Cámara detenida.';
  });
  async function readPhoto(event) {
    if (readingPhoto) return;
    stop();
    const file = event.target.files[0];
    if (!file) return;
    if (file.size > 15 * 1024 * 1024) {
      status.textContent = 'La imagen supera 15 MB. Usa una foto más pequeña.';
      return;
    }
    readingPhoto = true;
    start.disabled = true;
    liveStart.disabled = true;
    const inputs = [document.getElementById('qr-photo'), document.getElementById('qr-camera')];
    inputs.forEach(input => { input.disabled = true; });
    const current = generation;
    const url = URL.createObjectURL(file);
    try {
      status.textContent = 'Leyendo imagen…';
      const image = new Image();
      image.src = url;
      await image.decode();
      let code = null;
      let serverError = '';
      let ambiguous = false;
      if (advanced.checked) {
        status.textContent = 'Leyendo foto con QReader en el servidor…';
        try {
          code = await decodeOnServer(image, image.naturalWidth, image.naturalHeight, current);
        } catch (error) {
          if (current !== generation) return;
          serverError = error.name === 'AbortError' ? 'QReader tardó demasiado. Reintenta con una foto más cercana.' : error.message;
          ambiguous = error.code === 'multiple_qr';
        }
      }
      if (!code && !ambiguous && current === generation) code = await decodePhoto(image, current);
      if (current !== generation) return;
      if (code) openCode(code.data);
      else status.textContent = serverError || 'No se encontró un QR. Acerca la cámara para que el código ocupe la mayor parte de la foto, enfoca y conserva su borde blanco. Evita reflejos e inclinación.';
    } catch (_) {
      status.textContent = 'No se pudo leer la imagen. Prueba con JPG o PNG.';
    } finally {
      URL.revokeObjectURL(url);
      event.target.value = '';
      readingPhoto = false;
      start.disabled = false;
      liveStart.disabled = false;
      inputs.forEach(input => { input.disabled = false; });
    }
  }
  document.getElementById('qr-photo').addEventListener('change', readPhoto);
  document.getElementById('qr-camera').addEventListener('change', readPhoto);
  advanced.addEventListener('change', () => {
    if (!advanced.checked && serverController) serverController.abort();
    liveServerAvailable = true;
    status.textContent = advanced.checked ? 'QReader activo: las imágenes se envían al servidor para leerlas.' : 'Lectura local activa: las imágenes no se envían al servidor.';
  });
  window.addEventListener('pagehide', stop);
  document.addEventListener('visibilitychange', () => { if (document.hidden) stop(); });
})();
