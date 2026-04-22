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
    gdrive: true,
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

  /** Гибкие настройки: метки для "чёрной рамки" */
  g.__HRH__.BLACKLIST_LABELS_KEY = "hrhelper_black_frame_labels";
  g.__HRH__.DEFAULT_BLACKLIST_LABELS = [
    "черный список",
    "black list",
    "blacklist",
    "no come back",
    "no-come-back",
    "no_come_back",
    "nocomeback",
  ];

  /** Ширина плавающего виджета (LinkedIn и HH экосистема — единая), 350px */
  g.__HRH__.FLOATING_WIDGET_WIDTH = 350;

  /** Тайминги для debounce и задержек (DRY, единый источник правды) */
  g.__HRH__.TIMING = {
    DEBOUNCE_MUTATION: 100,
    DEBOUNCE_THEME: 50,
    DEBOUNCE_CALENDAR_MEET: 500,
    RETRY_INITIAL_MS: 1000,
    SCAN_DELAY_MS: 1500,
  };
})();
