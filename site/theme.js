(function () {
  "use strict";

  var KEY = "tdcest-theme";
  var DARK = "dark";
  var LIGHT = "light";
  var SUN =
    '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="4.5"></circle><path d="M12 2.5v2.2M12 19.3v2.2M4.9 4.9l1.6 1.6M17.5 17.5l1.6 1.6M2.5 12h2.2M19.3 12h2.2M4.9 19.1l1.6-1.6M17.5 6.5l1.6-1.6"></path></svg>';
  var MOON =
    '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20.5 14.2A8.8 8.8 0 1 1 9.8 3.5a7.3 7.3 0 0 0 10.7 10.7z"></path></svg>';

  function systemTheme() {
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? DARK : LIGHT;
  }

  function savedTheme() {
    try {
      return localStorage.getItem(KEY);
    } catch (error) {
      return null;
    }
  }

  function syncButton(theme) {
    var button = document.getElementById("theme-toggle");
    if (!button) return;
    var next = theme === DARK ? "light" : "dark";
    button.innerHTML = theme === DARK ? SUN : MOON;
    button.setAttribute("aria-label", "Switch to " + next + " mode");
    button.setAttribute("title", "Switch to " + next + " mode");
  }

  function syncMeta(theme) {
    var meta = document.querySelector('meta[name="theme-color"]:not([media])');
    if (!meta) return;
    meta.setAttribute("content", theme === DARK ? "#11161a" : "#f8f5ef");
  }

  function applyTheme(theme, persist) {
    document.documentElement.setAttribute("data-theme", theme);
    syncButton(theme);
    syncMeta(theme);
    if (persist) {
      try {
        localStorage.setItem(KEY, theme);
      } catch (error) {
        // Ignore storage failures.
      }
    }
    window.dispatchEvent(new CustomEvent("tdc-theme-change", { detail: { theme: theme } }));
  }

  function initTheme() {
    applyTheme(savedTheme() || systemTheme(), false);
  }

  window.toggleTheme = function () {
    var current = document.documentElement.getAttribute("data-theme") || systemTheme();
    applyTheme(current === DARK ? LIGHT : DARK, true);
  };

  initTheme();

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      syncButton(document.documentElement.getAttribute("data-theme") || systemTheme());
    });
  } else {
    syncButton(document.documentElement.getAttribute("data-theme") || systemTheme());
  }

  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", function (event) {
    if (!savedTheme()) applyTheme(event.matches ? DARK : LIGHT, false);
  });
})();
