(function () {
  'use strict';
  document.addEventListener('click', async function (event) {
    var button = event.target.closest('[data-fullscreen]'); if (!button) return;
    var target = document.querySelector(button.dataset.fullscreen); if (!target) return;
    try {
      if (document.fullscreenElement) await document.exitFullscreen();
      else if (target.requestFullscreen) await target.requestFullscreen();
      else if (window.toast) toast('Use your browser’s full-screen control.');
    } catch (_) { if (window.toast) toast('Full screen was blocked by the browser. The player is still available.'); }
  });
  document.addEventListener('fullscreenchange', function () {
    document.querySelectorAll('[data-fullscreen]').forEach(function(button){button.textContent=document.fullscreenElement===document.querySelector(button.dataset.fullscreen)?'Exit full screen':'Full screen';});
    window.dispatchEvent(new Event('resize'));
  });
})();
