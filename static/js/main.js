/* Shared UI behaviour: toasts, mobile nav, relative timestamps, CSRF helper. */
(function () {
  'use strict';

  var BDMIS = window.BDMIS || {};

  /* --- CSRF ------------------------------------------------------------- */

  BDMIS.getCookie = function (name) {
    var match = document.cookie.match('(^|;)\\s*' + name + '\\s*=\\s*([^;]+)');
    return match ? decodeURIComponent(match.pop()) : null;
  };

  BDMIS.csrfToken = function () {
    var field = document.querySelector('[name=csrfmiddlewaretoken]');
    return field ? field.value : BDMIS.getCookie('csrftoken');
  };

  /* --- Toasts ----------------------------------------------------------- */

  function toastStack() {
    var stack = document.querySelector('.toast-stack');
    if (!stack) {
      stack = document.createElement('div');
      stack.className = 'toast-stack';
      stack.setAttribute('role', 'status');
      stack.setAttribute('aria-live', 'polite');
      document.body.appendChild(stack);
    }
    return stack;
  }

  BDMIS.toast = function (message, level, timeout) {
    var node = document.createElement('div');
    node.className = 'toast toast-' + (level || 'info');
    node.innerHTML =
      '<span></span>' +
      '<button class="toast-close" type="button" aria-label="Dismiss">' +
      '<svg class="icon" viewBox="0 0 256 256" fill="currentColor" ' +
      'aria-hidden="true" focusable="false">' +
      '<path d="M205.66,194.34a8,8,0,0,1-11.32,11.32L128,139.31,61.66,205.66a8,8,0,0,1' +
      '-11.32-11.32L116.69,128,50.34,61.66A8,8,0,0,1,61.66,50.34L128,116.69l66.34-66.35' +
      'a8,8,0,0,1,11.32,11.32L139.31,128Z"/></svg></button>';
    // textContent, not innerHTML: the message must never be parsed as markup.
    node.firstChild.textContent = message;
    toastStack().appendChild(node);

    var dismiss = function () {
      node.classList.add('leaving');
      setTimeout(function () {
        if (node.parentNode) node.parentNode.removeChild(node);
      }, 250);
    };

    node.querySelector('.toast-close').addEventListener('click', dismiss);
    setTimeout(dismiss, timeout || 4000);
    return node;
  };

  /* --- Relative timestamps ---------------------------------------------- */

  BDMIS.relativeTime = function (isoString) {
    var then = new Date(isoString);
    if (isNaN(then.getTime())) return '';
    var seconds = Math.max(Math.round((Date.now() - then.getTime()) / 1000), 0);
    if (seconds < 45) return 'just now';
    if (seconds < 90) return 'a minute ago';
    var minutes = Math.round(seconds / 60);
    if (minutes < 60) return minutes + ' minutes ago';
    var hours = Math.round(minutes / 60);
    if (hours < 24) return hours + (hours === 1 ? ' hour ago' : ' hours ago');
    var days = Math.round(hours / 24);
    if (days < 30) return days + (days === 1 ? ' day ago' : ' days ago');
    return then.toLocaleDateString();
  };

  function refreshTimestamps() {
    document.querySelectorAll('[data-timestamp]').forEach(function (node) {
      node.textContent = BDMIS.relativeTime(node.getAttribute('data-timestamp'));
    });
  }

  /* --- Init ------------------------------------------------------------- */

  document.addEventListener('DOMContentLoaded', function () {
    // Server-side messages arrive as data attributes and become toasts.
    document.querySelectorAll('[data-message]').forEach(function (node) {
      BDMIS.toast(node.getAttribute('data-message'), node.getAttribute('data-level'));
      node.remove();
    });

    var toggle = document.querySelector('.nav-toggle');
    var panel = toggle && document.getElementById(toggle.getAttribute('aria-controls'));
    if (toggle && panel) {
      var setOpen = function (open) {
        if (open) {
          panel.setAttribute('data-open', '');
        } else {
          panel.removeAttribute('data-open');
        }
        toggle.setAttribute('aria-expanded', String(open));
        toggle.setAttribute('aria-label', open ? 'Close menu' : 'Open menu');
      };

      toggle.addEventListener('click', function () {
        setOpen(!panel.hasAttribute('data-open'));
      });

      document.addEventListener('keydown', function (event) {
        if (event.key === 'Escape' && panel.hasAttribute('data-open')) {
          setOpen(false);
          toggle.focus();
        }
      });

      // Leaving the mobile layout with the menu open must not strand it open.
      var desktop = window.matchMedia('(min-width: 1080px)');
      var onChange = function () { if (desktop.matches) setOpen(false); };
      if (desktop.addEventListener) {
        desktop.addEventListener('change', onChange);
      } else if (desktop.addListener) {
        desktop.addListener(onChange);
      }
    }

    document.querySelectorAll('[data-password-toggle]').forEach(function (button) {
      var field = button.closest('.password-field');
      var input = field ? field.querySelector('input') : null;
      if (!input) return;

      button.addEventListener('click', function () {
        var revealed = input.type === 'text';
        var start = input.selectionStart;
        var end = input.selectionEnd;

        input.type = revealed ? 'password' : 'text';
        field.classList.toggle('is-revealed', !revealed);
        button.setAttribute('aria-pressed', String(!revealed));
        button.setAttribute('aria-label', revealed ? 'Show password' : 'Hide password');

        // Changing `type` drops focus and the caret, so put both back.
        input.focus();
        try {
          input.setSelectionRange(start, end);
        } catch (err) {
          /* some browsers refuse setSelectionRange right after a type swap */
        }
      });
    });

    // Never leave a password on screen after the page is left or submitted.
    window.addEventListener('pagehide', function () {
      document.querySelectorAll('.password-field.is-revealed input').forEach(
        function (input) { input.type = 'password'; }
      );
    });

    // Confirmation for destructive POST buttons.
    document.querySelectorAll('form[data-confirm]').forEach(function (form) {
      form.addEventListener('submit', function (event) {
        if (!window.confirm(form.getAttribute('data-confirm'))) {
          event.preventDefault();
        }
      });
    });

    document.querySelectorAll('[data-autosubmit] select').forEach(function (select) {
      select.addEventListener('change', function () {
        if (select.form.requestSubmit) {
          select.form.requestSubmit();
        } else {
          select.form.submit();
        }
      });
    });

    refreshTimestamps();
    setInterval(refreshTimestamps, 30000);

    document.querySelectorAll('.fade-in-on-load').forEach(function (node, index) {
      node.style.animationDelay = Math.min(index * 40, 320) + 'ms';
      node.classList.add('fade-in');
    });
  });

  /* --- Loading feedback ------------------------------------------------ */

  var SAFETY_RESET_MS = 25000;
  var safetyTimer = null;

  function startNavigating() {
    document.documentElement.classList.add('is-navigating');
    clearTimeout(safetyTimer);
    safetyTimer = setTimeout(resetLoading, SAFETY_RESET_MS);
  }

  function setButtonLoading(button) {
    if (!button || button.classList.contains('is-loading')) return;
    // Hold the current width so a longer label does not make the layout jump.
    button.style.minWidth = button.offsetWidth + 'px';
    button.setAttribute('data-original-label', button.innerHTML);
    var label = button.getAttribute('data-loading-label');
    if (label) {
      // textContent keeps the label from ever being parsed as markup.
      var text = document.createElement('span');
      text.textContent = label;
      button.textContent = '';
      button.appendChild(text);
    }
    var spinner = document.createElement('span');
    spinner.className = 'btn-spinner';
    spinner.setAttribute('aria-hidden', 'true');
    button.insertBefore(spinner, button.firstChild);
    button.classList.add('is-loading');
    button.setAttribute('aria-disabled', 'true');
  }

  function resetLoading() {
    clearTimeout(safetyTimer);
    document.documentElement.classList.remove('is-navigating');
    document.querySelectorAll('form[data-submitting]').forEach(function (form) {
      form.removeAttribute('data-submitting');
      form.removeAttribute('aria-busy');
    });
    document.querySelectorAll('.is-loading').forEach(function (button) {
      var original = button.getAttribute('data-original-label');
      if (original !== null) button.innerHTML = original;
      button.removeAttribute('data-original-label');
      button.removeAttribute('aria-disabled');
      button.classList.remove('is-loading');
      button.style.minWidth = '';
    });
  }

  document.addEventListener('submit', function (event) {
    var form = event.target;
    if (event.defaultPrevented || form.target === '_blank') return;

    // A second click while the first submission is in flight is ignored.
    if (form.hasAttribute('data-submitting')) {
      event.preventDefault();
      return;
    }
    form.setAttribute('data-submitting', '');
    form.setAttribute('aria-busy', 'true');

    var button = event.submitter || form.querySelector('[type="submit"]');
    if (button && button.classList.contains('btn')) setButtonLoading(button);
    startNavigating();
  });

  document.addEventListener('click', function (event) {
    if (event.defaultPrevented || event.button !== 0) return;
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;

    var link = event.target.closest ? event.target.closest('a[href]') : null;
    if (!link || link.hasAttribute('download')) return;
    if (link.target && link.target !== '_self') return;
    if (link.protocol !== 'http:' && link.protocol !== 'https:') return;
    if (link.origin !== window.location.origin) return;
    // A jump within the same page is not a page load.
    if (link.pathname === window.location.pathname &&
        link.search === window.location.search && link.hash) return;

    if (link.classList.contains('btn')) setButtonLoading(link);
    startNavigating();
  });

  window.addEventListener('pageshow', function (event) {
    if (event.persisted) resetLoading();
  });

  BDMIS.resetLoading = resetLoading;

  window.BDMIS = BDMIS;
})();
