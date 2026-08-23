/* ------------------------------------------------------------------
   Full-text search across every scanned page in the archive.

   Backed by Pagefind: the index is split into small chunks and only
   the chunks a query needs are downloaded, so this stays fast with
   tens of thousands of pages indexed. Result bodies ("fragments") are
   fetched lazily, ten at a time, as the visitor pages through.
   ------------------------------------------------------------------ */
(function () {
  const { url, esc, debounce } = window.PSIU;
  const input = document.getElementById('q');
  const panel = document.getElementById('results');
  if (!input || !panel) return;

  const listEl  = panel.querySelector('[data-list]');
  const countEl = panel.querySelector('[data-count]');
  const facetEl = panel.querySelector('[data-facets]');
  const moreEl  = panel.querySelector('[data-more]');
  const sortEl  = panel.querySelector('[data-sort]');
  const hideOnSearch = document.querySelectorAll('[data-hide-on-search]');

  const PAGE = 10;
  let pf = null, results = [], shown = 0, filter = null, token = 0, busy = false;

  async function engine() {
    if (pf) return pf;
    pf = await import(url('pagefind/pagefind.js'));
    await pf.options({ excerptLength: 34 });
    await pf.init();
    await pf.filters();          // load filter chunks so counts come back
    return pf;
  }

  function setUrlQuery(q) {
    const u = new URL(location.href);
    q ? u.searchParams.set('q', q) : u.searchParams.delete('q');
    history.replaceState(null, '', u);
  }

  const pageFromAnchor = u => {
    const m = /#page-(\d+)/.exec(u || '');
    return m ? +m[1] : null;
  };

  /* Pagefind returns every match position plus the location of every page
     anchor, so the complete list of pages a term appears on can be derived
     here — not just the handful it hands back pre-excerpted. */
  function allPages(d) {
    const anchors = (d.anchors || [])
      .filter(a => /^page-\d+$/.test(a.id || ''))
      .sort((a, b) => a.location - b.location);
    if (!anchors.length) return [];
    const out = new Set();
    for (const loc of (d.locations || [])) {
      let lo = 0, hi = anchors.length - 1, found = -1;
      while (lo <= hi) {
        const mid = (lo + hi) >> 1;
        if (anchors[mid].location <= loc) { found = mid; lo = mid + 1; } else hi = mid - 1;
      }
      if (found >= 0) out.add(+anchors[found].id.slice(5));
    }
    return [...out].sort((a, b) => a - b);
  }

  function hitHtml(d, q) {
    const meta = d.meta || {};
    const href = url(d.raw_url.replace(/^\//, ''));
    const term = encodeURIComponent(q);
    const link = p => `${href}#page-${p}${q ? '&q=' + term : ''}`;
    const cover = meta.cover
      ? `<img src="${url(esc(meta.cover))}" alt="" loading="lazy" width="52"
              style="width:52px;border-radius:3px;border:1px solid var(--line-2);flex:0 0 auto">`
      : '';
    const topSubs = (d.sub_results || []).filter(s => pageFromAnchor(s.url)).slice(0, 3);
    const subs = topSubs.map(s => {
      const p = pageFromAnchor(s.url);
      return `<div class="subhit"><a href="${link(p)}">Page ${p}</a><span>${s.excerpt}</span></div>`;
    }).join('');
    const seen = new Set(topSubs.map(s => pageFromAnchor(s.url)));
    const rest = allPages(d).filter(p => !seen.has(p));
    const restLine = rest.length
      ? `<div class="alsopages"><span>Also on page${rest.length > 1 ? 's' : ''}</span>` +
        rest.slice(0, 14).map(p => `<a href="${link(p)}">${p}</a>`).join('') +
        (rest.length > 14 ? `<span>+${rest.length - 14} more</span>` : '') + '</div>'
      : '';
    return `<article class="hit">
      <div style="display:flex;gap:14px;align-items:flex-start">${cover}
        <div style="flex:1;min-width:0">
          <h3><a href="${href}">${esc(meta.title || 'Untitled')}</a></h3>
          <div class="meta">
            ${meta.collection_name ? `<span>${esc(meta.collection_name)}</span>` : ''}
            ${meta.year && meta.year !== '0' ? `<span>${esc(meta.year)}</span>` : ''}
            ${meta.pagecount && meta.pagecount !== '0' ? `<span>${esc(meta.pagecount)} pages</span>` : ''}
          </div>
          ${subs ? '' : `<p class="ex">${d.excerpt}</p>`}
          ${(subs || restLine) ? `<div class="subhits">${subs}${restLine}</div>` : ''}
        </div></div></article>`;
  }

  async function renderMore(reset, q) {
    if (busy && !reset) return;   // only guard against double-clicking "show more"
    busy = true;
    const my = token;
    if (reset) { listEl.innerHTML = ''; shown = 0; }
    const slice = results.slice(shown, shown + PAGE);
    // only these ten fragments are fetched
    const data = await Promise.all(slice.map(r => r.data().catch(() => null)));
    if (my !== token) { busy = false; return; }
    listEl.insertAdjacentHTML('beforeend', data.filter(Boolean).map(d => hitHtml(d, q)).join(''));
    shown += slice.length;
    const left = results.length - shown;
    moreEl.style.display = left > 0 ? 'block' : 'none';
    moreEl.textContent = `Show ${Math.min(left, PAGE)} more (${left} left)`;
    busy = false;
  }

  function drawFacets(search) {
    // With a facet applied, Pagefind zeroes the others in `filters`; `totalFilters`
    // gives the counts as if no facet were selected, so you can switch between them.
    const src = (filter && filter.kind) ? (search.totalFilters || {}) : (search.filters || {});
    const mk = (kind, k, n) =>
      `<button class="facet" data-kind="${kind}" data-val="${esc(k)}"
        aria-pressed="${!!(filter && filter.kind === kind && filter.val === k)}">${esc(k)} <span class="muted">${n}</span></button>`;
    const parts = [];
    Object.entries(src.collection || {}).filter(([, n]) => n).sort((a, b) => b[1] - a[1])
      .forEach(([k, n]) => parts.push(mk('collection', k, n)));
    Object.entries(src.decade || {}).filter(([, n]) => n).sort()
      .forEach(([k, n]) => parts.push(mk('decade', k, n)));
    facetEl.innerHTML = parts.length
      ? `<button class="facet" data-kind="" data-val="" aria-pressed="${!filter}">All results</button>` + parts.join('')
      : '';
  }

  async function run(q) {
    const my = ++token;
    q = (q || '').trim();
    setUrlQuery(q);
    if (!q) {
      panel.classList.remove('on');
      hideOnSearch.forEach(el => el.style.display = '');
      return;
    }
    hideOnSearch.forEach(el => el.style.display = 'none');
    panel.classList.add('on');
    if (q.length < 2) {
      countEl.textContent = '';
      facetEl.innerHTML = '';
      listEl.innerHTML = `<div class="empty"><h3>Keep typing</h3>
        <p>A single letter matches almost every page in the archive. Two or more
        characters gives something useful.</p></div>`;
      moreEl.style.display = 'none';
      return;
    }
    countEl.innerHTML = '<span class="spinner"></span> Searching the archive…';
    listEl.innerHTML = '';
    moreEl.style.display = 'none';

    let pfl;
    try { pfl = await engine(); }
    catch (err) {
      countEl.textContent = '';
      listEl.innerHTML = `<div class="empty"><h3>Search isn't available</h3>
        <p>The search index didn't load. If you are opening these files straight from
        your computer, the site needs to be served over http for search to work.</p></div>`;
      return;
    }
    if (my !== token) return;

    const params = {};
    if (filter && filter.kind) params.filters = { [filter.kind]: [filter.val] };
    const s = sortEl ? sortEl.value : '';
    if (s === 'year_asc')  params.sort = { year: 'asc' };
    if (s === 'year_desc') params.sort = { year: 'desc' };

    let search;
    try { search = await pfl.search(q, params); }
    catch (err) { countEl.textContent = 'Search failed: ' + (err.message || err); return; }
    if (my !== token) return;

    results = search.results;
    drawFacets(search);
    countEl.innerHTML = results.length
      ? `<b>${results.length}</b> volume${results.length === 1 ? '' : 's'} mention
         &ldquo;${esc(q)}&rdquo;${filter && filter.kind ? ` in ${esc(filter.val)}` : ''}`
      : '';
    if (!results.length) {
      listEl.innerHTML = `<div class="empty"><h3>Nothing found for &ldquo;${esc(q)}&rdquo;</h3>
        <p>These are scans of old print, so the machine-read text is imperfect.
        Try a shorter word, a surname on its own, or a different spelling.</p></div>`;
      return;
    }
    renderMore(true, q);
  }

  const go = debounce(() => { filter = null; run(input.value); }, 200);
  input.addEventListener('input', go);
  input.addEventListener('search', () => { filter = null; run(input.value); });
  moreEl.addEventListener('click', () => renderMore(false, input.value.trim()));
  if (sortEl) sortEl.addEventListener('change', () => run(input.value));

  facetEl.addEventListener('click', e => {
    const b = e.target.closest('.facet');
    if (!b) return;
    filter = b.dataset.kind ? { kind: b.dataset.kind, val: b.dataset.val } : null;
    run(input.value);
  });

  document.querySelectorAll('[data-suggest]').forEach(el => {
    el.addEventListener('click', () => {
      input.value = el.dataset.suggest;
      input.focus();
      filter = null;
      run(input.value);
      panel.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  });

  const initial = new URL(location.href).searchParams.get('q');
  if (initial) { input.value = initial; run(initial); }
})();
