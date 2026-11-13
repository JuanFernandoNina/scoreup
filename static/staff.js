(() => {
  const search = document.getElementById('staff-search');
  if (search) {
    const normalize = text => text.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
    search.addEventListener('input', () => {
      let visible = 0;
      document.querySelectorAll('[data-club-name]').forEach(row => {
        row.hidden = !normalize(row.dataset.clubName).includes(normalize(search.value.trim()));
        if (!row.hidden) visible += 1;
      });
      document.getElementById('staff-search-empty').hidden = visible !== 0;
    });
  }
  document.querySelectorAll('[data-evaluation-form]').forEach(form => {
    const update = () => {
      let percentage = 0;
      let valid = true;
      form.querySelectorAll('[data-weight]').forEach(input => {
        if (input.value === '' || !input.validity.valid) valid = false;
        percentage += Number(input.value) * Number(input.dataset.weight) / 100;
      });
      const score = percentage / 100 * Number(form.dataset.maximum);
      form.querySelector('[data-score-output]').textContent = valid ? `${score.toLocaleString('es', { maximumFractionDigits: 2 })} pts` : 'Completa las notas';
    };
    form.querySelectorAll('[data-number]').forEach(range => range.addEventListener('input', () => {
      document.getElementById(range.dataset.number).value = range.value;
      update();
    }));
    form.querySelectorAll('[data-range]').forEach(input => input.addEventListener('input', () => {
      document.getElementById(input.dataset.range).value = input.value;
      update();
    }));
    update();
  });
})();
