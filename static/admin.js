(() => {
  const toggle = document.getElementById('admin-menu-toggle');
  const backdrop = document.createElement('button');
  backdrop.type = 'button';
  backdrop.className = 'admin-mobile-backdrop';
  backdrop.setAttribute('aria-label', 'Cerrar navegación lateral');
  backdrop.tabIndex = -1;
  document.body.append(backdrop);
  const mobile = window.matchMedia('(max-width: 760px)');
  function setDrawer(open, restoreFocus = false) {
    document.body.classList.toggle('admin-menu-open', open);
    toggle.setAttribute('aria-expanded', String(open));
    toggle.setAttribute('aria-label', open ? 'Cerrar menú' : 'Abrir menú');
    document.querySelector('.admin-main').inert = open && mobile.matches;
    if (restoreFocus) toggle.focus();
  }
  toggle.addEventListener('click', () => {
    setDrawer(!document.body.classList.contains('admin-menu-open'));
  });
  backdrop.addEventListener('click', () => setDrawer(false, true));
  mobile.addEventListener('change', () => setDrawer(false));
  const search = document.getElementById('admin-search-input');
  const results = document.getElementById('admin-search-results');
  const data = JSON.parse(document.getElementById('admin-search-data').textContent);
  const normalize = value => value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
  function closeSearch() {
    results.hidden = true;
    search.setAttribute('aria-expanded', 'false');
  }
  function renderSearch() {
    const query = normalize(search.value.trim());
    results.replaceChildren();
    if (!query) { closeSearch(); return; }
    const matches = data.filter(item => normalize(item.nombre).includes(query)).slice(0, 8);
    for (const item of matches) {
      const link = document.createElement('a');
      link.href = item.url;
      const name = document.createElement('strong');
      name.textContent = item.nombre;
      const type = document.createElement('small');
      type.textContent = item.tipo;
      link.append(name, type);
      results.append(link);
    }
    if (!matches.length) {
      const empty = document.createElement('p');
      empty.textContent = 'No hay clubes ni eventos que coincidan.';
      results.append(empty);
    }
    results.hidden = false;
    search.setAttribute('aria-expanded', 'true');
  }
  search.addEventListener('input', renderSearch);
  search.addEventListener('focus', renderSearch);
  search.addEventListener('keydown', event => {
    if (event.key === 'Enter' && !results.hidden) {
      event.preventDefault();
      const link = results.querySelector('a');
      if (link) link.click();
    }
    if (event.key === 'ArrowDown' && !results.hidden) {
      const link = results.querySelector('a');
      if (link) { event.preventDefault(); link.focus(); }
    }
  });
  document.addEventListener('keydown', event => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
      event.preventDefault();
      search.focus();
    }
    if (event.key === 'Escape') {
      closeSearch();
      setDrawer(false, document.body.classList.contains('admin-menu-open'));
    }
  });
  document.addEventListener('click', event => {
    if (!event.target.closest('.admin-search')) closeSearch();
  });
})();
