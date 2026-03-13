importScripts("shared/constants.js", "shared/utils/token.js");

const DEFAULTS = self.__HRH__.DEFAULTS;
const ACTIVE_PAGES_KEY = self.__HRH__.ACTIVE_PAGES_KEY;
const DEFAULT_ACTIVE_PAGES = self.__HRH__.DEFAULT_ACTIVE_PAGES;
const DEFAULT_ICONS = self.__HRH__.DEFAULT_ICONS;
const UNKNOWN_PAGE_ICONS = self.__HRH__.UNKNOWN_PAGE_ICONS;
const normalizeToken = self.__HRH__.normalizeToken;

/** Тип страницы по URL для проверки «активных страниц». */
function getPageTypeFromUrl(url) {
  if (!url || typeof url !== "string") return null;
  try {
    const u = new URL(url);
    const host = u.hostname.toLowerCase();
    const path = (u.pathname || "").toLowerCase();
    const hash = (u.hash || "").toLowerCase();
    if (host.includes("linkedin.com")) return "linkedin";
    if (host.includes("calendar.google.com")) return "calendar";
    if (host.includes("meet.google.com")) return "meet";
    if ((host === "rabota.by" || host === "www.rabota.by" || host.endsWith(".rabota.by") || host.endsWith(".hh.ru") || host === "hh.ru") && path.includes("/resume/")) return "hh_ecosystem";
    if (host.includes("huntflow") && (path.includes("/my") || hash.includes("/my")) && (hash.includes("applicants/filter/all") || (hash.includes("applicants") && hash.includes("/id/")) || (hash.includes("vacancy") && hash.includes("/id/")) || (hash.includes("applicants") && /\/filter\/\d+\/\d+/.test(hash)))) return "huntflow";
  } catch (_) {}
  return null;
}

async function updateExtensionIcon(tabId, url) {
  if (!chrome.action || !chrome.action.setIcon) return;
  const pageType = getPageTypeFromUrl(url);
  if (!pageType) {
    chrome.action.setIcon({ tabId, path: UNKNOWN_PAGE_ICONS });
    return;
  }
  try {
    const data = await chrome.storage.sync.get({ [ACTIVE_PAGES_KEY]: DEFAULT_ACTIVE_PAGES });
    const active = data[ACTIVE_PAGES_KEY] || DEFAULT_ACTIVE_PAGES;
    if (!active[pageType]) {
      chrome.action.setIcon({ tabId, path: UNKNOWN_PAGE_ICONS });
      return;
    }
  } catch (_) {
    chrome.action.setIcon({ tabId, path: UNKNOWN_PAGE_ICONS });
    return;
  }
  chrome.action.setIcon({ tabId, path: DEFAULT_ICONS });
}

const CACHE_TTL_MS = 30_000;
const cache = new Map();
const inflight = new Map();

async function getConfig() {
  try {
    if (typeof chrome === "undefined" || !chrome.storage || !chrome.storage.sync) {
      return {
        baseUrl: (DEFAULTS.baseUrl || "").replace(/\/+$/, ""),
        apiToken: normalizeToken(DEFAULTS.apiToken || ""),
      };
    }
    const cfg = await chrome.storage.sync.get(DEFAULTS);
    const raw = (cfg.apiToken || DEFAULTS.apiToken || "").trim();
    return {
      baseUrl: (cfg.baseUrl || DEFAULTS.baseUrl).replace(/\/+$/, ""),
      apiToken: normalizeToken(raw),
    };
  } catch (err) {
    return {
      baseUrl: (DEFAULTS.baseUrl || "").replace(/\/+$/, ""),
      apiToken: normalizeToken(DEFAULTS.apiToken || ""),
    };
  }
}

function cacheKey({ path, method, body }) {
  let bodyKey = "";
  try {
    bodyKey = body ? JSON.stringify(body) : "";
  } catch {
    bodyKey = "";
  }
  return `${method || "GET"} ${path} ${bodyKey}`;
}

async function doRequest({ path, method, body }) {
  const key = cacheKey({ path, method, body });

  if (inflight.has(key)) {
    return await inflight.get(key);
  }

  const isStatus =
    (method || "GET").toUpperCase() === "GET" &&
    String(path || "").includes("/linkedin-applicants/status/");

  if (isStatus) {
    const hit = cache.get(key);
    if (hit && Date.now() - hit.ts < CACHE_TTL_MS) {
      return hit.value;
    }
  }

  const p = (async () => {
    const { baseUrl, apiToken } = await getConfig();
    const url = `${baseUrl}${path}`;

    if (!apiToken) {
      return {
        ok: false,
        status: 0,
        json: { message: "Нет API токена. Укажите его в настройках расширения." },
      };
    }

    const res = await fetch(url, {
      method: method || "GET",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Token ${apiToken}`,
      },
      body: body ? JSON.stringify(body) : undefined,
    });

    const json = await res.json().catch(() => null);
    const value = { ok: res.ok, status: res.status, json };

    if (isStatus && res.ok) {
      cache.set(key, { ts: Date.now(), value });
    }

    return value;
  })();

  inflight.set(key, p);
  try {
    return await p;
  } finally {
    inflight.delete(key);
  }
}

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (!msg) return;

  if (msg.type === "HRHELPER_OPEN_TABS") {
    try {
      const urls = Array.isArray(msg.urls) ? msg.urls.filter((u) => typeof u === "string" && u.trim()) : [];
      if (urls.length === 0) {
        sendResponse({ success: false, message: "No urls" });
        return true;
      }
      const sender = _sender;
      const tabId = sender && sender.tab && sender.tab.id;
      const startIndex = sender && sender.tab && typeof sender.tab.index === "number" ? sender.tab.index + 1 : undefined;

      const createNext = (i) => {
        if (i >= urls.length) {
          sendResponse({ success: true });
          return;
        }
        const url = urls[i];
        const index = typeof startIndex === "number" ? startIndex + i : undefined;
        chrome.tabs.create(
          {
            url,
            active: false,
            index,
            openerTabId: typeof tabId === "number" ? tabId : undefined,
          },
          () => createNext(i + 1)
        );
      };
      createNext(0);
    } catch (e) {
      sendResponse({ success: false, message: String(e) });
    }
    return true;
  }

  if (msg.type !== "HRHELPER_API") return;

  doRequest(msg.payload)
    .then((result) => sendResponse(result))
    .catch((e) =>
      sendResponse({ ok: false, status: 0, json: { message: String(e) } })
    );

  return true;
});

chrome.tabs.onActivated.addListener(async (activeInfo) => {
  try {
    const tab = await chrome.tabs.get(activeInfo.tabId);
    updateExtensionIcon(activeInfo.tabId, tab?.url);
  } catch (_) {}
});

chrome.tabs.onUpdated.addListener((tabId, changeInfo) => {
  if (changeInfo.status !== "complete" || !changeInfo.url) return;
  updateExtensionIcon(tabId, changeInfo.url);
});

chrome.runtime.onStartup.addListener(() => {
  chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    if (tabs[0]) updateExtensionIcon(tabs[0].id, tabs[0].url);
  });
});