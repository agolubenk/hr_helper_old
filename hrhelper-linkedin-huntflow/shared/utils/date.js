/**
 * HR Helper — утилиты даты/времени (DRY)
 * @fileoverview
 */
(function () {
  var g = typeof window !== "undefined" ? window : self;
  g.__HRH__ = g.__HRH__ || {};

  /** Формат даты: дд.мм.гггг */
  function formatVacancyDate(isoStr) {
    if (!isoStr) return "—";
    var d = new Date(isoStr);
    if (isNaN(d.getTime())) return "—";
    var day = String(d.getDate()).padStart(2, "0");
    var month = String(d.getMonth() + 1).padStart(2, "0");
    return day + "." + month + "." + d.getFullYear();
  }

  /** Формат даты+времени: дд.мм.гггг чч:мм */
  function formatRejectionDateTime(isoStr) {
    if (!isoStr) return "";
    var d = new Date(isoStr);
    if (isNaN(d.getTime())) return "";
    var day = String(d.getDate()).padStart(2, "0");
    var month = String(d.getMonth() + 1).padStart(2, "0");
    var hh = String(d.getHours()).padStart(2, "0");
    var mm = String(d.getMinutes()).padStart(2, "0");
    return day + "." + month + "." + d.getFullYear() + " " + hh + ":" + mm;
  }

  /** Дата+время для комментариев: дд.мм.гггг чч:мм */
  function formatCommentDate(isoStr) {
    if (!isoStr) return "";
    var d = new Date(isoStr);
    if (isNaN(d.getTime())) return "";
    var day = String(d.getDate()).padStart(2, "0");
    var month = String(d.getMonth() + 1).padStart(2, "0");
    var hh = String(d.getHours()).padStart(2, "0");
    var mm = String(d.getMinutes()).padStart(2, "0");
    return day + "." + month + "." + d.getFullYear() + " " + hh + ":" + mm;
  }

  g.__HRH__.formatVacancyDate = formatVacancyDate;
  g.__HRH__.formatRejectionDateTime = formatRejectionDateTime;
  g.__HRH__.formatCommentDate = formatCommentDate;
})();

