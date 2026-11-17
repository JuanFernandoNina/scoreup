/* La solicitud Fullscreen debe hacerse dentro del clic del administrador. */
(() => {
  const launch = document.getElementById('launch-projection');
  if (!launch) return;
  launch.addEventListener('click', event => {
    if (!document.documentElement.requestFullscreen) return; // Enlace limpio + F11 como alternativa.
    event.preventDefault();
    const overlay = document.createElement('div');
    overlay.className = 'projection-overlay';
    overlay.setAttribute('role', 'dialog');
    overlay.setAttribute('aria-modal', 'true');
    overlay.setAttribute('aria-label', 'Proyección a pantalla completa');
    const frame = document.createElement('iframe');
    frame.src = launch.href;
    frame.title = 'Lugares y puntajes';
    const exit = document.createElement('button');
    exit.className = 'projection-exit';
    exit.textContent = 'Salir de proyección · Esc';
    const previousOverflow = document.body.style.overflow;
    let closed = false;
    function close() {
      if (closed) return;
      closed = true;
      document.removeEventListener('fullscreenchange', changed);
      document.removeEventListener('keydown', keydown);
      overlay.remove();
      document.body.classList.remove('is-projecting');
      document.body.style.overflow = previousOverflow;
      launch.focus();
    }
    function changed() { if (!document.fullscreenElement) close(); }
    function keydown(e) { if (e.key === 'Escape' && !document.fullscreenElement) close(); }
    exit.addEventListener('click', () => {
      if (document.fullscreenElement) document.exitFullscreen().catch(close);
      else close();
    });
    frame.addEventListener('load', () => {
      // Detectar sesión terminada sin proyectar el login o un error administrativo.
      if (!frame.contentDocument?.querySelector('.scoreboard')) { close(); return; }
      frame.contentDocument.addEventListener('keydown', keydown);
    });
    overlay.append(frame, exit);
    document.body.append(overlay);
    document.body.classList.add('is-projecting');
    document.body.style.overflow = 'hidden';
    document.addEventListener('fullscreenchange', changed);
    document.addEventListener('keydown', keydown);
    overlay.requestFullscreen().catch(() => { /* Mantener vista limpia a todo el viewport. */ });
    frame.focus();
  });
})();
