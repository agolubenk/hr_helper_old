/**
 * HR Helper — API статусов (DRY)
 * @fileoverview
 */
(function () {
  var g = typeof window !== "undefined" ? window : self;
  g.__HRH__ = g.__HRH__ || {};

  async function fetchStatusMulti(params) {
    params = params || {};
    var apiFetch = g.__HRH__.apiFetch;
    var normalize = g.__HRH__.normalizeLinkedInProfileUrl;
    if (!apiFetch) throw new Error("[HRHelper] shared/api/client.js not loaded");
    if (!normalize) throw new Error("[HRHelper] shared/utils/url.js not loaded");

    var qp = new URLSearchParams();
    if (params.linkedinUrl) {
      var li = normalize(params.linkedinUrl);
      if (li) qp.set("linkedin_url", li);
    }
    if (params.huntflowUrl) {
      qp.set("huntflow_url", params.huntflowUrl);
    }
    if (!qp.toString()) {
      return { error: "Нужен linkedin_url или huntflow_url" };
    }

    var res = await apiFetch(
      "/api/v1/huntflow/linkedin-applicants/status-multi/?" + qp.toString(),
      { method: "GET" }
    );
    var data = await res.json().catch(function () { return null; });
    if (!res.ok || !data) return { error: (data && (data.message || data.error)) || "Ошибка API" };
    if (data && data.success === false) return { error: data.message || "Ошибка API" };
    return data;
  }

  g.__HRH__.fetchStatusMulti = fetchStatusMulti;
})();

