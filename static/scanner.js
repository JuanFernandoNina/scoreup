/* Lectura local: las fotos no se suben al servidor. */
(() => {
  const video = document.getElementById('preview');
  const canvas = document.getElementById('scan-canvas');
  const context = canvas.getContext('2d', { willReadFrequently: true });
  const status = document.getElementById('scan-status');
  const start = document.getElementById('start-camera');
  const stopButton = document.getElementById('stop-camera');
  let stream = null;
  let frame = null;
  let starting = false;
  let generation = 0;
  let readingPhoto = false;
  function stop() {
    generation += 1;
    if (frame !== null) cancelAnimationFrame(frame);
    frame = null;
    if (stream) stream.getTracks().forEach(track => track.stop());
    stream = null;
    video.srcObject = null;
    video.hidden = true;
    stopButton.hidden = true;
    start.disabled = false;
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
  function scan() {
    if (!stream) return;
    if (video.readyState >= 2 && video.videoWidth) {
      const code = decode(video, video.videoWidth, video.videoHeight);
      if (code && openCode(code.data)) return;
    }
    frame = requestAnimationFrame(scan);
  }
  start.addEventListener('click', async () => {
    if (starting || stream || readingPhoto) return;
    if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
      status.textContent = 'Este navegador no permite cámara en vivo aquí. Usa «Elegir imagen», «Tomar una foto» o la cámara normal del celular.';
      return;
    }
    starting = true;
    start.disabled = true;
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
      video.srcObject = stream;
      video.hidden = false;
      stopButton.hidden = false;
      await video.play();
      status.textContent = 'Apunta al QR completo del club, con buena luz.';
      scan();
    } catch (_) {
      stop();
      status.textContent = 'No se pudo abrir la cámara. Revisa el permiso o utiliza una foto del QR.';
    } finally {
      starting = false;
      if (!stream) start.disabled = false;
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
    const inputs = [document.getElementById('qr-photo'), document.getElementById('qr-camera')];
    inputs.forEach(input => { input.disabled = true; });
    const current = generation;
    const url = URL.createObjectURL(file);
    try {
      status.textContent = 'Leyendo imagen…';
      const image = new Image();
      image.src = url;
      await image.decode();
      const code = await decodePhoto(image, current);
      if (current !== generation) return;
      if (code) openCode(code.data);
      else status.textContent = 'No se encontró un QR. Acerca la cámara para que el código ocupe la mayor parte de la foto, enfoca y conserva su borde blanco. Evita reflejos e inclinación.';
    } catch (_) {
      status.textContent = 'No se pudo leer la imagen. Prueba con JPG o PNG.';
    } finally {
      URL.revokeObjectURL(url);
      event.target.value = '';
      readingPhoto = false;
      start.disabled = false;
      inputs.forEach(input => { input.disabled = false; });
    }
  }
  document.getElementById('qr-photo').addEventListener('change', readPhoto);
  document.getElementById('qr-camera').addEventListener('change', readPhoto);
  window.addEventListener('pagehide', stop);
  document.addEventListener('visibilitychange', () => { if (document.hidden) stop(); });
})();
