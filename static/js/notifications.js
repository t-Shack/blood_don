/* Dashboard live checks: donor eligibility and system-wide shortages. */
(function () {
  'use strict';

  var BDMIS = window.BDMIS || {};

  function refreshEligibility() {
    var panel = document.querySelector('[data-eligibility-url]');
    if (!panel) return;

    fetch(panel.getAttribute('data-eligibility-url'), {
      headers: {'X-Requested-With': 'XMLHttpRequest'},
      credentials: 'same-origin'
    })
      .then(function (response) { return response.json(); })
      .then(function (payload) {
        if (!payload.success) return;
        var data = payload.data;

        var badge = panel.querySelector('[data-eligibility-badge]');
        if (badge) {
          badge.textContent = data.is_eligible ? 'Eligible to donate' : 'Not yet eligible';
          badge.className = 'badge ' + (data.is_eligible ? 'badge-green' : 'badge-amber');
        }

        var countdown = panel.querySelector('[data-days-until]');
        if (countdown) {
          countdown.textContent = data.is_eligible
            ? 'You can donate today'
            : data.days_until_eligible + ' day(s) to go';
        }
      })
      .catch(function () { /* dashboard stays on its server-rendered values */ });
  }

  function refreshShortages() {
    var node = document.querySelector('[data-shortage-url]');
    if (!node) return;

    fetch(node.getAttribute('data-shortage-url'), {
      headers: {'X-Requested-With': 'XMLHttpRequest'}
    })
      .then(function (response) { return response.json(); })
      .then(function (payload) {
        if (!payload.success) return;
        var counter = node.querySelector('[data-shortage-count]');
        // type_count matches the server-rendered badge (blood types in
        // shortage); count is the number of hospitals and stays in the API.
        if (counter) {
          counter.textContent = payload.data.type_count !== undefined
            ? payload.data.type_count
            : payload.data.count;
        }
      })
      .catch(function () { /* non-critical */ });
  }

  document.addEventListener('DOMContentLoaded', function () {
    refreshEligibility();
    refreshShortages();

    var interval = parseInt(
      document.body.getAttribute('data-poll-interval') || '30000', 10
    ) * 2;
    setInterval(function () {
      if (document.hidden) return;
      refreshEligibility();
      refreshShortages();
    }, interval);
  });

  window.BDMIS = BDMIS;
})();
