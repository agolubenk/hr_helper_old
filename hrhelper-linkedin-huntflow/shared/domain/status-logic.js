/**
 * HR Helper — доменная логика статусов/меток (DRY)
 * @fileoverview
 */
(function () {
  var g = typeof window !== "undefined" ? window : self;
  g.__HRH__ = g.__HRH__ || {};

  function isNewStatusName(statusName) {
    var s = (statusName || "").toString().trim().toLowerCase();
    return s === "new" || s === "новый";
  }

  /** Метки, при которых показываем "чёрный список" */
  function hasBlacklistLabel(candidateInfo) {
    var labels = candidateInfo && candidateInfo.labels;
    if (!Array.isArray(labels)) return false;
    var norm = function (s) {
      return (s || "")
        .toString()
        .trim()
        .toLowerCase()
        .replace(/ё/g, "е")
        .replace(/\s+/g, " ");
    };
    return labels.some(function (l) {
      var name =
        (typeof l === "string" ? l : l && (l.name || l.title)) || "";
      var n = norm(name);
      if (n === "черный список" || n === "black list" || n === "blacklist")
        return true;
      var noSpaces = n.replace(/\s/g, "");
      return (
        noSpaces === "nocomeback" ||
        noSpaces === "no-come-back" ||
        noSpaces === "no_come_back" ||
        n === "no come back"
      );
    });
  }

  /**
   * Определяет, является ли статус отказом.
   * Поддерживает:
   * - строку `statusName`
   * - `<option>` из popup со `dataset.type` / `dataset.name`
   */
  function isRejectionStatus(input) {
    // popup: <option data-type data-name>
    try {
      if (input && typeof input === "object" && input.dataset) {
        var type = (input.dataset.type || "").toLowerCase();
        var name = (input.dataset.name || "").toLowerCase();
        if (
          type === "rejected" ||
          type === "rejection" ||
          type === "trash"
        )
          return true;
        return (
          name.indexOf("отказ") !== -1 ||
          name.indexOf("reject") !== -1 ||
          name.indexOf("отклон") !== -1
        );
      }
    } catch (_) {}

    // content: string status name
    var s = (input || "").toString().trim().toLowerCase();
    if (!s) return false;
    return (
      s.indexOf("отказ") !== -1 ||
      s.indexOf("reject") !== -1 ||
      s.indexOf("rejected") !== -1 ||
      s.indexOf("trash") !== -1 ||
      s.indexOf("отклон") !== -1
    );
  }

  g.__HRH__.isNewStatusName = isNewStatusName;
  g.__HRH__.hasBlacklistLabel = hasBlacklistLabel;
  g.__HRH__.isRejectionStatus = isRejectionStatus;
})();

