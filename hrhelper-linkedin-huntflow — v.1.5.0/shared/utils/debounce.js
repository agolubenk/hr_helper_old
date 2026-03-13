/**
 * HR Helper — debounce для обработчиков и MutationObserver (снижение нагрузки на CPU)
 * @fileoverview
 */
(function () {
  var g = typeof window !== "undefined" ? window : self;
  g.__HRH__ = g.__HRH__ || {};

  /**
   * Возвращает функцию, откладывающую вызов fn до истечения delay мс после последнего вызова.
   * @param {function} fn — функция для вызова
   * @param {number} delay — задержка в мс
   * @returns {function}
   */
  function debounce(fn, delay) {
    var timer = null;
    return function () {
      var args = arguments;
      var that = this;
      if (timer) clearTimeout(timer);
      timer = setTimeout(function () {
        timer = null;
        fn.apply(that, args);
      }, delay);
    };
  }

  g.__HRH__.debounce = debounce;
})();
