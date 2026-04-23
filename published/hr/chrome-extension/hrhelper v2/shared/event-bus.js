(function () {
  var g = typeof window !== 'undefined' ? window : self;
  g.__HRH__ = g.__HRH__ || {};

  function createEventBus() {
    var listeners = Object.create(null);

    function on(event, handler) {
      if (!event || typeof handler !== 'function') return function () {};
      (listeners[event] = listeners[event] || []).push(handler);
      return function offOnce() { off(event, handler); };
    }

    function once(event, handler) {
      if (!event || typeof handler !== 'function') return function () {};
      function wrapped() {
        off(event, wrapped);
        handler.apply(null, arguments);
      }
      return on(event, wrapped);
    }

    function off(event, handler) {
      if (!event || !listeners[event]) return;
      if (!handler) {
        delete listeners[event];
        return;
      }
      listeners[event] = listeners[event].filter(function (h) { return h !== handler; });
      if (!listeners[event].length) delete listeners[event];
    }

    function emit(event, payload) {
      var arr = listeners[event];
      if (!arr || !arr.length) return;
      arr.slice().forEach(function (handler) {
        try {
          handler(payload);
        } catch (e) {
          console.error('[HRHelper EventBus]', event, e);
        }
      });
    }

    return { on: on, once: once, off: off, emit: emit };
  }

  if (!g.__HRH__.eventBus) {
    g.__HRH__.eventBus = createEventBus();
  }
})();
