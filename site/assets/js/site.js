/* Shared chrome: mobile nav, base-path helper, small utilities. */
window.PSIU = (function () {
  const base = window.PSIU_BASE || '';
  // Absolute so it works from any folder depth and as a module specifier.
  const url = p => new URL(base + String(p).replace(/^\//, ''), location.href).href;

  document.addEventListener('click', e => {
    const b = e.target.closest('.burger');
    if (b) {
      const nav = document.getElementById('nav');
      const open = nav.classList.toggle('open');
      b.setAttribute('aria-expanded', open ? 'true' : 'false');
    }
  });

  const esc = s => String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');

  const debounce = (fn, ms) => { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; };

  const fmtBytes = n => !n ? '' : n > 1048576 ? (n / 1048576).toFixed(n > 10485760 ? 0 : 1) + ' MB'
                                              : Math.round(n / 1024) + ' KB';
  return { base, url, esc, debounce, fmtBytes };
})();
