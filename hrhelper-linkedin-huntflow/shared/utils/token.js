/**
 * HR Helper — нормализация API-токена (DRY)
 * @fileoverview
 */
(function () {
  var g = typeof window !== "undefined" ? window : self;
  g.__HRH__ = g.__HRH__ || {};

  function normalizeToken(input) {
    if (!input || typeof input !== "string") return "";
    var s = input.trim();
    if (!s) return "";
    if (/^Token\s+/i.test(s)) s = s.replace(/^Token\s+/i, "");
    if (/^Bearer\s+/i.test(s)) s = s.replace(/^Bearer\s+/i, "");
    try {
      var parsed = JSON.parse(s);
      if (parsed && typeof parsed.data === "object" && parsed.data && typeof parsed.data.token === "string")
        return parsed.data.token.trim();
      if (parsed && typeof parsed.token === "string") return parsed.token.trim();
    } catch (_) {}
    return s;
  }

  g.__HRH__.normalizeToken = normalizeToken;
})();
