/* Client-side filtering for the browse grid. */
(function () {
  const grid = document.getElementById('grid');
  if (!grid) return;
  const { esc, url, debounce } = window.PSIU;
  const cards = Array.from(grid.children);
  const fColl = document.getElementById('f-coll');
  const fDec  = document.getElementById('f-dec');
  const fSort = document.getElementById('f-sort');
  const fQ    = document.getElementById('f-q');
  const out   = document.getElementById('gridcount');

  function apply() {
    const c = fColl.value, d = fDec.value, q = (fQ.value || '').toLowerCase().trim();
    let n = 0;
    cards.forEach(el => {
      const ok = (!c || el.dataset.coll === c)
              && (!d || el.dataset.decade === d)
              && (!q || el.dataset.search.includes(q));
      el.style.display = ok ? '' : 'none';
      if (ok) n++;
    });
    out.textContent = `${n} of ${cards.length} items`;
    const dir = fSort.value;
    const sorted = cards.slice().sort((a, b) => {
      const ya = +a.dataset.year, yb = +b.dataset.year;
      if (dir === 'old') return ya - yb || a.dataset.seq - b.dataset.seq;
      if (dir === 'new') return yb - ya || b.dataset.seq - a.dataset.seq;
      return a.dataset.title.localeCompare(b.dataset.title);
    });
    sorted.forEach(el => grid.appendChild(el));
    const u = new URL(location.href);
    c ? u.searchParams.set('collection', c) : u.searchParams.delete('collection');
    d ? u.searchParams.set('decade', d) : u.searchParams.delete('decade');
    history.replaceState(null, '', u);
  }

  [fColl, fDec, fSort].forEach(el => el.addEventListener('change', apply));
  fQ.addEventListener('input', debounce(apply, 140));

  const p = new URL(location.href).searchParams;
  if (p.get('collection')) fColl.value = p.get('collection');
  if (p.get('decade')) fDec.value = p.get('decade');
  apply();
})();
