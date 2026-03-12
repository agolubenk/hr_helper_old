/**
 * HR Helper — общие константы (DRY: единственный источник правды)
 * @fileoverview
 */
(function () {
  var g = typeof window !== "undefined" ? window : self;
  g.__HRH__ = g.__HRH__ || {};

  g.__HRH__.DEFAULTS = {
    baseUrl: "https://hr.sftntx.com",
    apiToken: "",
  };

  g.__HRH__.ACTIVE_PAGES_KEY = "hrhelper_active_pages";
  g.__HRH__.DEFAULT_ACTIVE_PAGES = {
    linkedin: true,
    hh_ecosystem: true,
    huntflow: true,
    meet: true,
    calendar: true,
  };

  g.__HRH__.DEFAULT_ICONS = {
    16: "icons/icon-16.png",
    32: "icons/icon-32.png",
    48: "icons/icon-48.png",
    128: "icons/icon-128.png",
  };
  g.__HRH__.UNKNOWN_PAGE_ICONS = {
    16: "icons/dark-label-24.png",
    32: "icons/dark-label-48.png",
    48: "icons/dark-label-72.png",
    128: "icons/dark-label-192.png",
  };

  /** Ключ темы оформления в настройках: "system" | "light" | "dark" */
  g.__HRH__.OPTIONS_THEME_KEY = "hrhelper_options_theme";
  g.__HRH__.DEFAULT_THEME = "system";
})();
