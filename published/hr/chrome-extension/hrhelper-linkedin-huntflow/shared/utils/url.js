/**
 * HR Helper — утилиты URL (нормализация LinkedIn, base URL)
 * @fileoverview
 */
(function () {
  var g = typeof window !== "undefined" ? window : self;
  g.__HRH__ = g.__HRH__ || {};

  function normalizeLinkedInProfileUrl(url) {
    if (!url || typeof url !== "string") return null;
    try {
      var u = new URL(url.trim());
      if (!u.hostname.endsWith("linkedin.com")) return null;
      var parts = u.pathname.split("/").filter(Boolean);
      var idx = parts.indexOf("in");
      if (idx === -1 || !parts[idx + 1]) return null;
      return "https://www.linkedin.com/in/" + parts[idx + 1] + "/";
    } catch (_) {
      return null;
    }
  }

  /** Базовая часть URL (до ? и #) для сопоставления и хранения */
  function getBaseUrl(url) {
    if (!url || typeof url !== "string") return "";
    try {
      var u = new URL(url.trim());
      return u.origin + u.pathname;
    } catch (_) {
      return url.split("?")[0].split("#")[0] || "";
    }
  }

  g.__HRH__.normalizeLinkedInProfileUrl = normalizeLinkedInProfileUrl;
  g.__HRH__.getBaseUrl = getBaseUrl;
})();
