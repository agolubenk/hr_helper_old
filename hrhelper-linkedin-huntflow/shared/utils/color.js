/**
 * HR Helper — утилиты цветов (DRY)
 * @fileoverview
 */
(function () {
  var g = typeof window !== "undefined" ? window : self;
  g.__HRH__ = g.__HRH__ || {};

  function hexToRgba(hex, alpha) {
    var m = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex || "");
    if (!m) return hex;
    var r = parseInt(m[1], 16);
    var g1 = parseInt(m[2], 16);
    var b = parseInt(m[3], 16);
    return "rgba(" + r + "," + g1 + "," + b + "," + alpha + ")";
  }

  /** Нормализует цвет метки из API (hex с # или без) в CSS-значение для border/color. */
  function normalizeLabelColor(val) {
    if (val == null || typeof val !== "string") return "";
    var s = val.trim();
    if (!s) return "";
    if (s.indexOf("#") === 0) return s.length === 4 || s.length === 7 ? s : "#" + s.slice(-6).toLowerCase();
    var hex = s.replace(/^#/, "");
    if ((hex.length === 3 || hex.length === 6) && /^[0-9a-fA-F]+$/.test(hex)) {
      if (hex.length === 3) hex = hex[0] + hex[0] + hex[1] + hex[1] + hex[2] + hex[2];
      return "#" + hex.toLowerCase();
    }
    return s;
  }

  g.__HRH__.hexToRgba = hexToRgba;
  g.__HRH__.normalizeLabelColor = normalizeLabelColor;
})();

