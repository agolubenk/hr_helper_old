(function () {
  var g = typeof window !== 'undefined' ? window : self;
  g.__HRH__ = g.__HRH__ || {};

  function createStateManager(initialState) {
    var state = Object.assign({}, initialState || {});
    var subs = [];

    function getState() {
      return state;
    }

    function setState(patch) {
      if (!patch || typeof patch !== 'object') return;
      var prev = state;
      state = Object.assign({}, state, patch);
      subs.slice().forEach(function (fn) {
        try {
          fn(state, prev);
        } catch (e) {
          console.error('[HRHelper StateManager]', e);
        }
      });
    }

    function subscribe(handler) {
      if (typeof handler !== 'function') return function () {};
      subs.push(handler);
      return function unsubscribe() {
        subs = subs.filter(function (h) { return h !== handler; });
      };
    }

    return {
      getState: getState,
      setState: setState,
      subscribe: subscribe,
    };
  }

  if (!g.__HRH__.createStateManager) {
    g.__HRH__.createStateManager = createStateManager;
  }
})();
