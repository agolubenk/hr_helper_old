/**
 * HR Helper — единый API-клиент для content scripts (через background proxy)
 * Возвращает { ok, status, json } — json как функция, возвращающая данные (совместимо с content.js/content-huntflow)
 * @fileoverview
 */
(function () {
  var g = typeof window !== "undefined" ? window : self;
  g.__HRH__ = g.__HRH__ || {};

  function isExtensionContextValid() {
    try {
      return typeof chrome !== "undefined" && chrome.runtime && chrome.runtime.id != null;
    } catch (_) {
      return false;
    }
  }

  function apiFetch(path, init) {
    init = init || {};
    var method = init.method || "GET";
    var body = init.body;
    if (typeof body === "string") {
      try {
        body = JSON.parse(body);
      } catch (_) {
        body = undefined;
      }
    }

    if (!isExtensionContextValid()) {
      return Promise.resolve({
        ok: false,
        status: 0,
        json: function () {
          return Promise.resolve({
            success: false,
            message: "Extension context invalidated. Please reload the page.",
          });
        },
      });
    }

    return new Promise(function (resolve, reject) {
      try {
        chrome.runtime.sendMessage(
          { type: "HRHELPER_API", payload: { path: path, method: method, body: body } },
          function (response) {
            if (chrome.runtime.lastError) {
              reject(new Error(chrome.runtime.lastError.message));
              return;
            }
            var result = response;
            resolve({
              ok: !!result && !!result.ok,
              status: (result && result.status) || 0,
              json: function () {
                return Promise.resolve(result && result.json != null ? result.json : null);
              },
            });
          }
        );
      } catch (err) {
        reject(err);
      }
    }).catch(function (err) {
      var msg = err && err.message ? err.message : "Unknown error";
      if (msg.indexOf("Extension context invalidated") !== -1) {
        return {
          ok: false,
          status: 0,
          json: function () {
            return Promise.resolve({
              success: false,
              message: "Extension context invalidated. Please reload the page.",
            });
          },
        };
      }
      return {
        ok: false,
        status: 0,
        json: function () {
          return Promise.resolve({ success: false, message: msg });
        },
      };
    });
  }

  g.__HRH__.apiFetch = apiFetch;
  g.__HRH__.isExtensionContextValid = isExtensionContextValid;
})();
