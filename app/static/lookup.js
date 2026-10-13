(function () {
  'use strict';
  var form = document.getElementById('lookup');
  if (!form) return;
  var add = document.getElementById('addmate');
  var submit = form.querySelector('.go');
  var status = document.getElementById('lookup-status');
  function rows() { return Array.from(form.querySelectorAll('.prow')); }
  function update() {
    var visible = rows().filter(function (row) { return !row.hidden; });
    visible.forEach(function (row, i) {
      if (!i) return;
      row.querySelector('label span').textContent = 'Squadmate ' + i;
      row.querySelector('.removemate').setAttribute('aria-label', 'Remove squadmate ' + i);
    });
    add.hidden = visible.length === 4;
    submit.textContent = 'Show stats';
  }
  add.addEventListener('click', function () {
    var row = rows().find(function (row) { return row.hidden; });
    if (!row) return;
    row.hidden = false;
    update();
    row.querySelector('input').focus();
  });
  form.addEventListener('click', function (event) {
    var button = event.target.closest('.removemate');
    if (!button) return;
    var row = button.closest('.prow');
    row.querySelectorAll('input').forEach(function (input) { input.value = ''; });
    row.hidden = true;
    form.insertBefore(row, form.querySelector('.lookup-actions'));
    update();
    add.focus();
  });
  form.addEventListener('submit', function (event) {
    if (submit.disabled) { event.preventDefault(); return; }
    submit.disabled = true;
    submit.textContent = 'Looking up players…';
    form.setAttribute('aria-busy', 'true');
    status.textContent = 'Checking Xbox and Twitch. This may take a few seconds.';
    status.hidden = false;
  });
  window.addEventListener('pageshow', function () {
    submit.disabled = false;
    form.removeAttribute('aria-busy');
    status.hidden = true;
    update();
  });
  update();
})();
