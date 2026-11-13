(() => {
  const normalize = value => value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
  document.querySelectorAll('.admin-management table').forEach((table, index) => {
    if (table.dataset.noEnhance !== undefined) return;
    const rows = [...table.querySelectorAll('tbody > tr')];
    let scroller = table.parentElement;
    if (!scroller.classList.contains('overflow-x-auto') && !scroller.classList.contains('mg-table-scroll')) {
      scroller = document.createElement('div');
      table.before(scroller);
      scroller.append(table);
    }
    scroller.classList.add('mg-table-scroll');
    table.classList.add('mg-table');
    const toolbar = document.createElement('div');
    toolbar.className = 'mg-table-toolbar';
    const label = document.createElement('label');
    label.className = 'mg-table-search';
    const hint = document.createElement('span');
    hint.className = 'admin-visually-hidden';
    hint.textContent = table.dataset.searchLabel || 'Buscar en esta tabla';
    const input = document.createElement('input');
    input.type = 'search';
    input.id = `mg-search-${index}`;
    input.placeholder = table.dataset.searchLabel || 'Buscar en los registros…';
    const magnifier = document.createElement('span');
    magnifier.textContent = '⌕';
    magnifier.setAttribute('aria-hidden', 'true');
    label.append(hint, magnifier, input);
    const count = document.createElement('span');
    count.className = 'mg-count';
    toolbar.append(label, count);
    scroller.before(toolbar);
    const empty = document.createElement('p');
    empty.className = 'mg-empty';
    empty.textContent = 'No hay registros que coincidan con la búsqueda.';
    empty.hidden = true;
    scroller.after(empty);
    const footer = document.createElement('div');
    footer.className = 'mg-table-footer';
    const description = document.createElement('span');
    description.setAttribute('role', 'status');
    const pages = document.createElement('div');
    pages.className = 'mg-pages';
    const prev = document.createElement('button');
    prev.type = 'button'; prev.textContent = 'Anterior';
    const current = document.createElement('span');
    current.className = 'mg-current-page';
    const next = document.createElement('button');
    next.type = 'button'; next.textContent = 'Siguiente';
    pages.append(prev, current, next);
    footer.append(description, pages);
    empty.after(footer);
    let page = 1;
    const size = 10;
    function render() {
      const query = normalize(input.value.trim());
      const matches = rows.filter(row => normalize(row.textContent).includes(query));
      const totalPages = Math.max(1, Math.ceil(matches.length / size));
      page = Math.min(page, totalPages);
      const visible = new Set(matches.slice((page - 1) * size, page * size));
      rows.forEach(row => { row.hidden = !visible.has(row); });
      count.textContent = `${matches.length} registros`;
      description.textContent = matches.length ? `Mostrando ${(page - 1) * size + 1}–${Math.min(page * size, matches.length)} de ${matches.length} registros` : '0 registros';
      if (query) description.textContent += ` · ${rows.length} en total`;
      current.textContent = `${page} / ${totalPages}`;
      prev.disabled = page === 1;
      next.disabled = page === totalPages;
      empty.hidden = matches.length > 0 || rows.length === 0;
    }
    input.addEventListener('input', () => { page = 1; render(); });
    prev.addEventListener('click', () => { page -= 1; render(); });
    next.addEventListener('click', () => { page += 1; render(); });
    window.addEventListener('beforeprint', () => rows.forEach(row => { row.hidden = false; }));
    window.addEventListener('afterprint', render);
    render();
  });
  document.querySelectorAll('[data-confirm]').forEach(form => form.addEventListener('submit', event => {
    if (!confirm(form.dataset.confirm)) event.preventDefault();
  }));
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape') document.querySelectorAll('.mg-create[open],.mg-edit[open]').forEach(detail => { detail.open = false; });
  });
})();
