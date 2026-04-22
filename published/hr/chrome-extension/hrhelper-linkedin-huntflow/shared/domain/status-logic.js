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
    var configured = null;
    try {
      configured = g.__HRH__ && Array.isArray(g.__HRH__.blackFrameLabels) ? g.__HRH__.blackFrameLabels : null;
    } catch (_) {
      configured = null;
    }
    var defaults = null;
    try {
      defaults = g.__HRH__ && Array.isArray(g.__HRH__.DEFAULT_BLACKLIST_LABELS) ? g.__HRH__.DEFAULT_BLACKLIST_LABELS : null;
    } catch (_) {
      defaults = null;
    }
    var norm = function (s) {
      return (s || "")
        .toString()
        .trim()
        .toLowerCase()
        .replace(/ё/g, "е")
        .replace(/\s+/g, " ");
    };
    var configuredNorm = null;
    try {
      var list = (configured && configured.length ? configured : defaults) || [];
      configuredNorm = list
        .map(function (x) { return norm(x); })
        .filter(function (x) { return !!x; })
        .map(function (x) { return { spaced: x, nospaces: x.replace(/\s/g, "") }; });
    } catch (_) {
      configuredNorm = null;
    }
    return labels.some(function (l) {
      var name =
        (typeof l === "string" ? l : l && (l.name || l.title)) || "";
      var n = norm(name);
      var noSpaces = n.replace(/\s/g, "");
      if (configuredNorm && configuredNorm.length) {
        return configuredNorm.some(function (x) {
          return x.spaced === n || x.nospaces === noSpaces;
        });
      }
      // fallback (legacy hardcoded)
      if (n === "черный список" || n === "black list" || n === "blacklist") return true;
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

  // Инициализация гибких настроек "чёрной рамки" (sync storage → g.__HRH__.blackFrameLabels)
  (function initBlackFrameLabels() {
    try {
      if (!chrome || !chrome.storage || !chrome.storage.sync) return;
    } catch (_) {
      return;
    }
    var KEY = (g.__HRH__ && g.__HRH__.BLACKLIST_LABELS_KEY) || "hrhelper_black_frame_labels";
    try {
      chrome.storage.sync.get({ [KEY]: null }, function (data) {
        try {
          var v = data && data[KEY];
          if (Array.isArray(v)) g.__HRH__.blackFrameLabels = v;
        } catch (_) {}
      });
      chrome.storage.onChanged.addListener(function (changes, areaName) {
        if (areaName !== "sync") return;
        if (!changes || !changes[KEY]) return;
        try {
          var nv = changes[KEY].newValue;
          if (Array.isArray(nv)) g.__HRH__.blackFrameLabels = nv;
          else g.__HRH__.blackFrameLabels = null;
        } catch (_) {}
      });
    } catch (_) {}
  })();
})();

