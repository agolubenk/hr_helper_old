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

  g.__HRH__.hexToRgba = hexToRgba;
})();

