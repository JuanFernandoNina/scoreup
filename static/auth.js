(() => {
  const password = document.getElementById('auth-password');
  const toggle = document.querySelector('[data-password-toggle]');
  const caps = document.getElementById('auth-caps');
  toggle.hidden = false;
  toggle.addEventListener('click', () => {
    const show = password.type === 'password';
    password.type = show ? 'text' : 'password';
    toggle.textContent = show ? 'Ocultar' : 'Mostrar';
    toggle.setAttribute('aria-label', show ? 'Ocultar contraseña' : 'Mostrar contraseña');
    toggle.setAttribute('aria-pressed', String(show));
  });
  function updateCaps(event) {
    if (event.getModifierState) caps.hidden = !event.getModifierState('CapsLock');
  }
  password.addEventListener('keydown', updateCaps);
  password.addEventListener('keyup', updateCaps);
  password.addEventListener('blur', () => { caps.hidden = true; });
})();
