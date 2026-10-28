(function () {
  'use strict';

  var STORAGE_KEY = 'bdmis-theme';
  var root = document.documentElement;

  root.classList.add('js');

  function stored() {
    try {
      return window.localStorage.getItem(STORAGE_KEY);
    } catch (err) {
      return null; // private mode, or storage disabled
    }
  }

  function persist(theme) {
    try {
      window.localStorage.setItem(STORAGE_KEY, theme);
    } catch (err) {
      /* nothing we can do; the theme still applies for this page view */
    }
  }

  function systemPrefersDark() {
    return Boolean(
      window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches
    );
  }

  function apply(theme) {
    root.setAttribute('data-theme', theme);
    var button = document.querySelector('[data-theme-toggle]');
    if (button) {
      button.setAttribute(
        'aria-label',
        theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'
      );
    }
  }

  // An explicit stored choice always wins; otherwise follow the system.
  var choice = stored();
  apply(choice === 'dark' || choice === 'light' ? choice : (systemPrefersDark() ? 'dark' : 'light'));

  document.addEventListener('DOMContentLoaded', function () {
    apply(root.getAttribute('data-theme'));
    var button = document.querySelector('[data-theme-toggle]');
    if (!button) return;
    button.addEventListener('click', function () {
      var next = root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
      apply(next);
      persist(next);
    });
  });
})();
