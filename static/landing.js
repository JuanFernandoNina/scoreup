(() => {
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)');
  const header = document.getElementById('lp-header');
  const reveals = [...document.querySelectorAll('[data-reveal]')];
  const parallax = [...document.querySelectorAll('[data-parallax]')];
  let observer;
  let pending = false;
  function updateScroll() {
    pending = false;
    const y = window.scrollY;
    header.classList.toggle('is-scrolled', y > 30);
    const max = document.documentElement.scrollHeight - window.innerHeight;
    header.style.setProperty('--scroll-progress', `${max > 0 ? Math.min(100, y / max * 100) : 0}%`);
    if (!reduced.matches && y < window.innerHeight * 1.5) {
      parallax.forEach(el => { el.style.transform = `translate3d(0,${y * Number(el.dataset.parallax)}px,0)`; });
    }
  }
  function requestUpdate() {
    if (!pending) { pending = true; requestAnimationFrame(updateScroll); }
  }
  function configureMotion() {
    if (observer) observer.disconnect();
    if (reduced.matches || !('IntersectionObserver' in window)) {
      document.documentElement.classList.remove('lp-motion');
      reveals.forEach(el => el.classList.add('is-visible'));
      parallax.forEach(el => { el.style.transform = ''; });
      return;
    }
    observer = new IntersectionObserver(entries => {
      entries.forEach(entry => {
        if (!entry.isIntersecting) return;
        entry.target.classList.add('is-visible');
        observer.unobserve(entry.target);
      });
    }, { threshold: 0.1, rootMargin: '0px 0px -24px 0px' });
    // Solo ocultar secciones fuera de pantalla; nunca esconder el hero inicial.
    reveals.forEach(el => {
      if (el.getBoundingClientRect().top < window.innerHeight - 24) el.classList.add('is-visible');
      else observer.observe(el);
    });
    document.documentElement.classList.add('lp-motion');
  }
  configureMotion();
  reduced.addEventListener('change', configureMotion);
  window.addEventListener('scroll', requestUpdate, { passive: true });
  window.addEventListener('resize', requestUpdate);
  window.addEventListener('pageshow', requestUpdate);
  updateScroll();
  document.querySelectorAll('.lp-mobile-menu a').forEach(link => link.addEventListener('click', () => {
    document.querySelector('.lp-mobile-menu').open = false;
  }));
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape') document.querySelector('.lp-mobile-menu').open = false;
    if (event.key === 'Tab') reveals.forEach(el => el.classList.add('is-visible'));
  });
  const inputs = [...document.querySelectorAll('[data-demo-weight]')];
  const total = document.getElementById('lp-demo-total');
  function calculateDemo() {
    let score = 0;
    inputs.forEach(input => {
      const value = Number(input.value);
      score += value * Number(input.dataset.demoWeight) / 100;
      input.nextElementSibling.textContent = value;
      input.style.setProperty('--range-fill', `${value}%`);
    });
    total.replaceChildren(document.createTextNode(`${score.toLocaleString('es', { maximumFractionDigits: 1 })} `));
    const suffix = document.createElement('small');
    suffix.textContent = '/ 100';
    total.append(suffix);
  }
  inputs.forEach(input => input.addEventListener('input', calculateDemo));
  calculateDemo();
})();
