/* ------------------------------------------------------------------
   In-page volume reader.

   The PDFs stay on psiu.org. That host sends both
   `accept-ranges: bytes` and `access-control-allow-origin: *`, so
   pdf.js streams just the pages it needs instead of pulling a 90 MB
   scan down before showing anything.

   If the URL carries #page-26&q=berwanger the reader opens at that
   page and paints a highlight over every match on it.
   ------------------------------------------------------------------ */
(function () {
  const root = document.getElementById('reader');
  if (!root) return;
  const { url, esc, debounce } = window.PSIU;

  const pdfUrl = root.dataset.pdf;
  const docId  = root.dataset.id;
  const title  = root.dataset.title || 'this volume';
  const stage   = root.querySelector('[data-stage]');
  const openBtn = root.querySelector('[data-open]');
  const bar     = root.querySelector('[data-bar]');
  const prevB   = root.querySelector('[data-prev]');
  const nextB   = root.querySelector('[data-next]');
  const numIn   = root.querySelector('[data-num]');
  const totalEl = root.querySelector('[data-total]');
  const zoomIn  = root.querySelector('[data-zin]');
  const zoomOut = root.querySelector('[data-zout]');
  const markEl  = root.querySelector('[data-mark]');

  let pdfjs = null, doc = null, page = 1, zoom = 1, term = '', rendering = false, queued = null;

  function fromHash() {
    const h = location.hash || '';
    const p = /#page-(\d+)/.exec(h);
    const q = /[#&]q=([^&]*)/.exec(h);
    return { page: p ? Math.max(1, +p[1]) : 1, term: q ? decodeURIComponent(q[1]) : '' };
  }

  function showTerm() {
    if (!markEl) return;
    markEl.innerHTML = term
      ? `highlighting <b>${esc(term)}</b> <button data-clearmark title="Stop highlighting">&times;</button>`
      : '';
  }

  async function boot(startPage, startTerm) {
    if (startTerm !== undefined) { term = startTerm; showTerm(); }
    if (doc) { show(startPage); return; }
    bar.style.display = 'flex';
    stage.innerHTML = `<div class="reader-msg"><span class="spinner"></span>
      Opening the volume… only the pages you look at are downloaded.</div>`;
    try {
      pdfjs = await import(url('vendor/pdfjs/pdf.min.mjs'));
      pdfjs.GlobalWorkerOptions.workerSrc = url('vendor/pdfjs/pdf.worker.min.mjs');
      doc = await pdfjs.getDocument({
        url: pdfUrl,
        disableAutoFetch: true,     // don't slurp the whole file
        disableStream: false,
        rangeChunkSize: 262144,
      }).promise;
      totalEl.textContent = doc.numPages;
      numIn.max = doc.numPages;
      show(startPage);
    } catch (err) {
      stage.innerHTML = `<div class="reader-msg">
        <p>The in-page reader couldn't load this volume.</p>
        <p><a class="btn ghost" style="display:inline-flex;width:auto" target="_blank" rel="noopener"
           href="${esc(pdfUrl)}#page=${startPage}">Open the PDF directly instead</a></p>
        <p class="muted" style="font-size:12.5px">${esc((err && err.message) || err)}</p></div>`;
    }
  }

  /* Paint a translucent block over every run of text on the page that
     contains the search term. Text runs in these OCR'd scans are close to
     word-level, so this lands where you expect. */
  async function highlight(pg, viewport, ctx) {
    if (!term || term.length < 2) return;
    let content;
    try { content = await pg.getTextContent(); } catch { return; }
    const needle = term.toLowerCase().replace(/^"|"$/g, '');
    const words = needle.split(/\s+/).filter(w => w.length > 1);
    if (!words.length) return;
    ctx.save();
    ctx.globalCompositeOperation = 'multiply';
    ctx.fillStyle = 'rgba(240, 200, 90, 0.42)';
    for (const item of content.items) {
      const s = (item.str || '').toLowerCase();
      if (!s || !words.some(w => s.includes(w))) continue;
      const t = pdfjs.Util.transform(viewport.transform, item.transform);
      const h = Math.hypot(t[2], t[3]) || 10;
      const w = (item.width || 0) * viewport.scale;
      if (w <= 0) continue;
      ctx.fillRect(t[4] - 1, t[5] - h + 1, w + 2, h + 1);
    }
    ctx.restore();
  }

  async function show(n) {
    if (!doc) return;
    page = Math.min(Math.max(1, n | 0), doc.numPages);
    numIn.value = page;
    prevB.disabled = page <= 1;
    nextB.disabled = page >= doc.numPages;
    if (rendering) { queued = page; return; }
    rendering = true;
    try {
      const pg = await doc.getPage(page);
      const avail = Math.min((stage.clientWidth || 820) - 36, 980);
      const base = pg.getViewport({ scale: 1 });
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      const cssScale = (avail / base.width) * zoom;
      const viewport = pg.getViewport({ scale: cssScale * dpr });
      const canvas = document.createElement('canvas');
      canvas.width = Math.floor(viewport.width);
      canvas.height = Math.floor(viewport.height);
      canvas.style.width = Math.floor(viewport.width / dpr) + 'px';
      canvas.setAttribute('role', 'img');
      canvas.setAttribute('aria-label', `Page ${page} of ${title}`);
      const ctx = canvas.getContext('2d', { alpha: false });
      await pg.render({ canvasContext: ctx, viewport }).promise;
      await highlight(pg, viewport, ctx);
      stage.innerHTML = '';
      stage.appendChild(canvas);
    } catch (err) {
      stage.innerHTML = `<div class="reader-msg">Couldn't render page ${page}.
        ${esc(err.message || '')}</div>`;
    }
    rendering = false;
    if (queued != null) { const q = queued; queued = null; if (q !== page) show(q); }
  }

  openBtn && openBtn.addEventListener('click', () => { const h = fromHash(); boot(h.page, h.term); });
  prevB.addEventListener('click', () => show(page - 1));
  nextB.addEventListener('click', () => show(page + 1));
  numIn.addEventListener('change', () => show(+numIn.value));
  zoomIn.addEventListener('click',  () => { zoom = Math.min(3, zoom * 1.25); show(page); });
  zoomOut.addEventListener('click', () => { zoom = Math.max(0.5, zoom / 1.25); show(page); });
  root.addEventListener('click', e => {
    if (e.target.closest('[data-clearmark]')) { term = ''; showTerm(); show(page); }
  });
  document.addEventListener('keydown', e => {
    if (!doc || e.metaKey || e.ctrlKey || e.altKey) return;
    if (/input|textarea|select/i.test(e.target.tagName)) return;
    if (e.key === 'ArrowLeft')  { e.preventDefault(); show(page - 1); }
    if (e.key === 'ArrowRight') { e.preventDefault(); show(page + 1); }
  });
  window.addEventListener('resize', debounce(() => { if (doc) show(page); }, 250));
  window.addEventListener('hashchange', () => {
    if (/#page-\d+/.test(location.hash)) { const h = fromHash(); boot(h.page, h.term); }
  });
  root.jumpTo = (p, t) => { boot(p, t); if (doc) { if (t !== undefined) { term = t; showTerm(); } show(p); } };

  /* ---------------- search within this one volume ---------------- */
  const inq = document.getElementById('inq');
  if (inq) {
    const out = document.getElementById('inhits');
    let pagesText = null, loading = null;

    async function load() {
      if (pagesText) return pagesText;
      if (!loading) loading = fetch(url('text/' + docId + '.json'))
        .then(r => r.ok ? r.json() : Promise.reject(new Error('no transcript')))
        .then(j => (pagesText = j.text));
      return loading;
    }

    const run = debounce(async () => {
      const q = inq.value.trim();
      if (q.length < 2) { out.innerHTML = ''; return; }
      out.innerHTML = '<div class="muted sans" style="font-size:13px"><span class="spinner"></span> looking…</div>';
      let pages;
      try { pages = await load(); }
      catch {
        out.innerHTML = '<p class="muted sans" style="font-size:13.5px">No text layer available for this volume yet.</p>';
        return;
      }
      const re = new RegExp(q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'ig');
      const hits = [];
      let total = 0;
      pages.forEach((t, i) => {
        if (!t) return;
        let m, first = null, n = 0;
        re.lastIndex = 0;
        while ((m = re.exec(t))) { n++; if (first === null) first = m.index; if (n > 40) break; }
        if (first === null) return;
        total += n;
        const s = Math.max(0, first - 90), e = Math.min(t.length, first + q.length + 110);
        hits.push({
          p: i + 1, n,
          html: (s ? '…' : '') + esc(t.slice(s, first)) + '<mark>' +
                esc(t.slice(first, first + q.length)) + '</mark>' +
                esc(t.slice(first + q.length, e)) + (e < t.length ? '…' : '')
        });
      });
      out.innerHTML = hits.length
        ? `<div class="muted sans" style="font-size:13px;margin-bottom:4px">${total} mention${total === 1 ? '' : 's'}
           on ${hits.length} page${hits.length === 1 ? '' : 's'}</div>` +
          hits.map(h => `<button class="inpage-hit" data-p="${h.p}"><b>Page ${h.p}${h.n > 1 ? ` · ${h.n} mentions` : ''}</b>${h.html}</button>`).join('')
        : `<p class="muted sans" style="font-size:13.5px">No mention of &ldquo;${esc(q)}&rdquo; in this volume.</p>`;
    }, 220);

    inq.addEventListener('input', run);
    // arriving from a search result: prefill and list every page that mentions it
    const h0 = fromHash();
    if (h0.term) { inq.value = h0.term; run(); }
    out.addEventListener('click', e => {
      const b = e.target.closest('.inpage-hit');
      if (!b) return;
      root.jumpTo(+b.dataset.p, inq.value.trim());
      root.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  }

  if (/#page-\d+/.test(location.hash)) { const h = fromHash(); boot(h.page, h.term); }
})();
