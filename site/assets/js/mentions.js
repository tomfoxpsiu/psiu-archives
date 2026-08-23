/* "Show the other N volumes" on people, chapter and song pages. */
(function () {
  document.querySelectorAll('.mmore').forEach(btn => {
    btn.addEventListener('click', () => {
      const list = btn.previousElementSibling;
      list.querySelectorAll('.mhide').forEach(li => li.classList.remove('mhide'));
      btn.remove();
    });
  });
})();
