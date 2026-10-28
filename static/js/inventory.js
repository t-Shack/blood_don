(function () {
  'use strict';

  var BDMIS = window.BDMIS || {};

  function statusFor(item) {
    return item.status;
  }

  function patchCell(cell, item) {
    var unitsNode = cell.querySelector('[data-units]');
    var previous = parseInt(unitsNode.getAttribute('data-units'), 10);

    if (previous !== item.available_units) {
      unitsNode.textContent = item.available_units;
      unitsNode.setAttribute('data-units', item.available_units);
      unitsNode.classList.remove('value-flash');
      // Reflow so the animation can restart on a repeat change.
      void unitsNode.offsetWidth;
      unitsNode.classList.add('value-flash');
    }

    var status = statusFor(item);
    cell.setAttribute('data-status', status);

    var bar = cell.querySelector('.inventory-bar-fill');
    if (bar) {
      bar.style.width = item.fill_percentage + '%';
      bar.setAttribute('data-status', status);
    }

    var label = cell.querySelector('[data-status-label]');
    if (label) {
      label.textContent = item.status_label;
      label.className = 'inventory-status badge badge-' + (
        status === 'critical' ? 'red' : status === 'low' ? 'amber' : 'green'
      );
    }
  }

  function markUpdated(container, isoString, state) {
    var stamp = container.querySelector('[data-timestamp]');
    if (stamp && isoString) {
      stamp.setAttribute('data-timestamp', isoString);
      stamp.textContent = BDMIS.relativeTime(isoString);
    }
    var dot = container.querySelector('.live-dot');
    if (dot) {
      if (state) {
        dot.setAttribute('data-state', state);
      } else {
        dot.removeAttribute('data-state');
      }
    }
  }

  function poll(container) {
    var url = container.getAttribute('data-inventory-url');
    if (!url) return;

    fetch(url, {headers: {'X-Requested-With': 'XMLHttpRequest'}})
      .then(function (response) {
        if (!response.ok) throw new Error('HTTP ' + response.status);
        return response.json();
      })
      .then(function (payload) {
        if (!payload.success) throw new Error(payload.message || 'Request failed');

        var newest = null;
        payload.data.inventory.forEach(function (item) {
          var cell = container.querySelector('[data-blood-type="' + item.blood_type + '"]');
          if (cell) patchCell(cell, item);
          if (!newest || item.last_updated > newest) newest = item.last_updated;
        });

        var totalNode = container.querySelector('[data-total-units]');
        if (totalNode) totalNode.textContent = payload.data.total_units;

        markUpdated(container, newest || new Date().toISOString(), null);
      })
      .catch(function () {
        // Keep the last good numbers on screen; just flag the feed as stale.
        markUpdated(container, null, 'error');
      });
  }

  document.addEventListener('DOMContentLoaded', function () {
    var containers = document.querySelectorAll('[data-inventory-url]');
    if (!containers.length) return;

    var interval = parseInt(
      document.body.getAttribute('data-poll-interval') || '30000', 10
    );

    containers.forEach(function (container) {
      var timer = setInterval(function () { poll(container); }, interval);

      document.addEventListener('visibilitychange', function () {
        if (document.hidden) {
          clearInterval(timer);
        } else {
          poll(container);
          timer = setInterval(function () { poll(container); }, interval);
        }
      });

      var manual = container.querySelector('[data-refresh-now]');
      if (manual) {
        manual.addEventListener('click', function () { poll(container); });
      }
    });
  });
})();
