/* Timeline: filter by theme, show or hide chapter closures, and a decade rail
   that keeps up with where you are on the page. */
(function () {
  const tl = document.getElementById('tl');
  if (!tl) return;
  const items   = Array.from(tl.querySelectorAll('.tl-item'));
  const heads   = Array.from(tl.querySelectorAll('.tl-decade'));
  const chips   = document.querySelector('[data-cats]');
  const quietEl = document.querySelector('[data-quiet]');
  const countEl = document.querySelector('[data-count]');
  const rail    = document.querySelector('.tl-rail');
  let cat = '';

  function apply() {
    const showQuiet = quietEl ? quietEl.checked : true;
    let shown = 0;
    items.forEach(el => {
      const ok = (!cat || el.dataset.cat === cat)
              && (showQuiet || !el.classList.contains('quiet'));
      el.hidden = !ok;
      if (ok) shown++;
    });
    // hide a decade heading whose entries are all filtered out
    heads.forEach(h => {
      let n = 0;
      for (let el = h.nextElementSibling; el && !el.classList.contains('tl-decade');
           el = el.nextElementSibling) {
        if (el.classList.contains('tl-item') && !el.hidden) n++;
      }
      h.hidden = n === 0;
      const link = rail && rail.querySelector('[href="#' + h.id + '"]');
      if (link) link.classList.toggle('empty', n === 0);
    });
    if (countEl) countEl.textContent = shown + (shown === 1 ? ' entry' : ' entries');
  }

  chips && chips.addEventListener('click', e => {
    const b = e.target.closest('.facet');
    if (!b) return;
    cat = b.dataset.cat || '';
    chips.querySelectorAll('.facet').forEach(x =>
      x.setAttribute('aria-pressed', String(x === b)));
    apply();
  });
  quietEl && quietEl.addEventListener('change', apply);

  // mark the decade you are currently looking at
  if (rail && 'IntersectionObserver' in window) {
    const io = new IntersectionObserver(entries => {
      entries.forEach(en => {
        if (!en.isIntersecting) return;
        rail.querySelectorAll('a').forEach(a => a.classList.remove('here'));
        const link = rail.querySelector('[href="#' + en.target.id + '"]');
        if (link) link.classList.add('here');
      });
    }, { rootMargin: '-72px 0px -70% 0px' });
    heads.forEach(h => io.observe(h));
  }

  apply();
})();
