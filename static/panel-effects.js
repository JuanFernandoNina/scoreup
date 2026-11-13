/* Efectos compartidos de los paneles. No altera formularios ni datos. */
(() => {
  if (!document.querySelector('[data-panel-theme]')) return;
  // Etiquetas reales de columnas para la vista de tarjetas en teléfonos.
  // Las tablas complejas (celdas combinadas) mantienen el desplazamiento local.
  document.querySelectorAll('.admin-management table,.director-table').forEach(table => {
    const headers = [...table.querySelectorAll('thead tr:last-child th')];
    const rows = [...table.querySelectorAll('tbody > tr')];
    if (!headers.length || headers.some(h => h.colSpan !== 1) || rows.some(row => row.cells.length !== headers.length || [...row.cells].some(cell => cell.colSpan !== 1 || cell.rowSpan !== 1))) return;
    table.classList.add('mobile-card-table');
    table.setAttribute('role', 'table');
    table.querySelectorAll('thead,tbody').forEach(group => group.setAttribute('role', 'rowgroup'));
    table.querySelectorAll('tr').forEach(row => row.setAttribute('role', 'row'));
    headers.forEach(header => header.setAttribute('role', 'columnheader'));
    rows.forEach(row => [...row.cells].forEach((cell,index) => {
      cell.dataset.label = headers[index].textContent.trim() || 'Acciones';
      cell.setAttribute('role', 'cell');
    }));
  });
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)');
  const selector = '.admin-metric,.admin-panel,.staff-action,.staff-card,.director-stat';
  const cards = [...document.querySelectorAll(selector)];
  let observer;
  function configure() {
    if (observer) observer.disconnect();
    if (reduced.matches || !('IntersectionObserver' in window)) {
      document.documentElement.classList.remove('panels-motion');
      cards.forEach(card => card.classList.add('panel-visible'));
      return;
    }
    observer = new IntersectionObserver(entries => entries.forEach(entry => {
      if (!entry.isIntersecting) return;
      entry.target.classList.add('panel-visible');
      observer.unobserve(entry.target);
    }), { threshold: 0.06, rootMargin: '0px 0px -18px 0px' });
    cards.forEach((card, index) => {
      card.classList.add('panel-reveal');
      card.style.setProperty('--panel-delay', `${(index % 4) * 45}ms`);
      if (card.getBoundingClientRect().top < innerHeight - 18) card.classList.add('panel-visible');
      else observer.observe(card);
    });
    document.documentElement.classList.add('panels-motion');
  }
  configure();
  reduced.addEventListener('change', configure);
  let scheduled = false;
  function update() {
    scheduled = false;
    const max = document.documentElement.scrollHeight - innerHeight;
    document.documentElement.style.setProperty('--panel-scroll', `${max > 0 ? Math.min(100, scrollY / max * 100) : 0}%`);
  }
  function requestUpdate() { if (!scheduled) { scheduled = true; requestAnimationFrame(update); } }
  addEventListener('scroll', requestUpdate, { passive: true });
  addEventListener('resize', requestUpdate);
  addEventListener('pageshow', requestUpdate);
  update();
  document.addEventListener('focusin', event => {
    const card = event.target.closest('.panel-reveal');
    if (card) card.classList.add('panel-visible');
  });
  document.addEventListener('keydown', event => {
    if (event.key === 'Tab') cards.forEach(card => card.classList.add('panel-visible'));
  });
  document.querySelectorAll('.director-app .staff-nav a[href^="#"]').forEach(link => link.addEventListener('click', () => {
    document.querySelectorAll('.director-app .staff-nav a').forEach(item => {
      item.classList.toggle('is-active', item === link);
      if (item === link) item.setAttribute('aria-current', 'location');
      else item.removeAttribute('aria-current');
    });
  }));
})();
