/**
 * Модуль LinkedIn Messaging: thread ID, маппинг thread→profile, форма ввода сообщения.
 * Подключается до content.js; экспорт в window.__HRH__.linkedinMessaging.
 */
(function () {
  const g = typeof window !== "undefined" ? window : globalThis;
  g.__HRH__ = g.__HRH__ || {};
  const HRH = g.__HRH__;
  const normalizeLinkedInProfileUrl = HRH.normalizeLinkedInProfileUrl;
  const debounce = HRH.debounce;
  const TIMING = HRH.TIMING || {};
  const DEBUG = !!(HRH.DEBUG_CONTENT);
  const log = (...args) => DEBUG && console.log("[HRHelper]", ...args);
  const warn = (...args) => (DEBUG || true) && console.warn("[HRHelper]", ...args);
  const logError = (...args) => console.error("[HRHelper]", ...args);

  const IS_PROFILE_PAGE = typeof location !== "undefined" && location.href.includes("/in/") && !location.href.includes("/search/");

  function extractThreadIdFromMessageButton() {
    const urlMatch = location.href.match(/thread\/([^/?]+)/);
    if (urlMatch) {
      log(" extractThreadIdFromMessageButton: found in URL", urlMatch[1].substring(0, 10) + "...");
      return urlMatch[1];
    }
    const messageLinks = Array.from(document.querySelectorAll('a[href*="/messaging/thread/"]'));
    for (const messageLink of messageLinks) {
      if (messageLink?.href) {
        const threadMatch = messageLink.href.match(/thread\/([^/?]+)/);
        if (threadMatch) {
          log(" extractThreadIdFromMessageButton: found in link", threadMatch[1].substring(0, 10) + "...");
          return threadMatch[1];
        }
      }
    }
    const messageBtnSelectors = [
      'button[aria-label*="Message"]', 'button[aria-label*="message"]',
      'button[aria-label*="Сообщение"]', 'button[aria-label*="сообщение"]',
      'a[href*="/messaging/"]', '[data-control-name="send_inmail"]', '[data-control-name="message"]'
    ];
    for (const selector of messageBtnSelectors) {
      const elements = Array.from(document.querySelectorAll(selector));
      for (const element of elements) {
        let link = element.querySelector('a[href*="/messaging/"]') || element.closest('a[href*="/messaging/"]') || (element.href && element.href.includes("/messaging/") ? element : null);
        if (!link && element.href) link = element;
        if (link?.href) {
          const threadMatch = link.href.match(/thread\/([^/?]+)/);
          if (threadMatch) {
            log(" extractThreadIdFromMessageButton: found in button/link", threadMatch[1].substring(0, 10) + "...");
            return threadMatch[1];
          }
        }
      }
    }
    log(" extractThreadIdFromMessageButton: not found");
    return null;
  }

  async function saveThreadMappingToBackend(threadId, profileUrl) {
    if (!threadId || !profileUrl) {
      log(" saveThreadMappingToBackend: missing threadId or profileUrl", { threadId: !!threadId, profileUrl: !!profileUrl });
      return;
    }
    log(" saveThreadMappingToBackend: saving mapping", { threadId: threadId.substring(0, 10) + "...", profileUrl });
    try {
      const result = await HRH.apiFetch("/api/v1/linkedin/thread-mapping/", {
        method: "POST",
        body: JSON.stringify({ thread_id: threadId, profile_url: profileUrl })
      });
      log(" saveThreadMappingToBackend: API response", { ok: result.ok, status: result.status });
      if (result.ok) {
        const data = await result.json().catch(() => null);
        log(" Thread mapping saved successfully:", threadId.substring(0, 10) + "...", data);
      } else {
        const data = await result.json().catch(() => null);
        const msg = data?.message || data?.detail || (typeof data?.error === "string" ? data.error : null);
        const isContextInvalidated = (msg && typeof msg === "string" && msg.includes("Extension context invalidated")) || (data && typeof data === "object" && String(data.message || "").includes("Extension context invalidated"));
        if (!isContextInvalidated) {
          const hint = result.status === 401 ? " Укажите API-токен в настройках расширения." : "";
          logError(" Failed to save thread mapping. Status:", result.status, msg || "", hint, data ? JSON.stringify(data) : "");
        } else {
          log(" saveThreadMappingToBackend: extension context invalidated (reload), skipping error log");
        }
      }
    } catch (e) {
      const errMsg = e && e.message ? e.message : String(e);
      if (!errMsg.includes("Extension context invalidated")) {
        logError(" Exception saving thread mapping:", errMsg);
      } else {
        log(" saveThreadMappingToBackend: extension context invalidated (reload), skipping error log");
      }
    }
  }

  function captureProfileToThreadMapping() {
    if (!IS_PROFILE_PAGE) {
      log(" captureProfileToThreadMapping: not a profile page");
      return;
    }
    const profileUrl = normalizeLinkedInProfileUrl ? normalizeLinkedInProfileUrl(location.href) : null;
    if (!profileUrl) {
      log(" captureProfileToThreadMapping: could not normalize profile URL");
      return;
    }
    log(" captureProfileToThreadMapping: starting for", profileUrl);
    const saveMapping = (threadId) => {
      if (!threadId) return;
      log(" Found thread:", threadId.substring(0, 10) + "...", "for", profileUrl);
      try {
        const mapping = JSON.parse(localStorage.getItem("hrhelper_thread_profile_map") || "{}");
        mapping[threadId] = profileUrl;
        localStorage.setItem("hrhelper_thread_profile_map", JSON.stringify(mapping));
        log(" Saved thread mapping to localStorage");
      } catch (e) {
        logError(" Error saving thread mapping to localStorage:", e);
      }
      saveThreadMappingToBackend(threadId, profileUrl);
    };
    let threadId = extractThreadIdFromMessageButton();
    if (threadId) saveMapping(threadId);
    else log(" captureProfileToThreadMapping: threadId not found immediately, will retry");
    const delays = [500, 1000, 2000, 3000, 5000];
    delays.forEach((delay) => {
      setTimeout(() => {
        const delayedThreadId = extractThreadIdFromMessageButton();
        if (delayedThreadId && (!threadId || delayedThreadId !== threadId)) {
          log(" captureProfileToThreadMapping: found threadId after delay", delayedThreadId.substring(0, 10) + "...");
          threadId = delayedThreadId;
          saveMapping(delayedThreadId);
        }
      }, delay);
    });
    let lastThreadId = threadId;
    const trackMessageButtons = () => {
      const newThreadId = extractThreadIdFromMessageButton();
      if (newThreadId && newThreadId !== lastThreadId) {
        lastThreadId = newThreadId;
        log(" New thread detected:", newThreadId.substring(0, 10) + "...");
        try {
          const mapping = JSON.parse(localStorage.getItem("hrhelper_thread_profile_map") || "{}");
          mapping[newThreadId] = profileUrl;
          localStorage.setItem("hrhelper_thread_profile_map", JSON.stringify(mapping));
          log(" Saved new thread mapping to localStorage");
        } catch (e) {
          logError(" Error saving thread mapping to localStorage:", e);
        }
        saveThreadMappingToBackend(newThreadId, profileUrl);
      }
    };
    const debouncedTrack = debounce ? debounce(trackMessageButtons, TIMING.DEBOUNCE_MUTATION || 100) : trackMessageButtons;
    const obs = new MutationObserver(() => debouncedTrack());
    obs.observe(document.body, { childList: true, subtree: true });
    log(" captureProfileToThreadMapping: MutationObserver started");
  }

  async function getProfileLinkFromMessaging(state) {
    if (state && state.messagingProfileCache) return state.messagingProfileCache;
    let threadId = null;
    try {
      const threadMatch = location.href.match(/thread\/([^/?]+)/);
      if (threadMatch) threadId = threadMatch[1];
    } catch (e) {
      warn(" Error extracting thread_id from URL:", e);
    }
    const profileLinks = Array.from(document.querySelectorAll('a[href*="/in/"]'));
    for (const link of profileLinks) {
      if (link.href.includes("/me/") || link.href.includes("/jobs/")) continue;
      const normalized = normalizeLinkedInProfileUrl ? normalizeLinkedInProfileUrl(link.href) : null;
      if (normalized) {
        log(" Profile found in DOM:", normalized);
        if (state) state.messagingProfileCache = normalized;
        if (threadId) {
          try {
            const mapping = JSON.parse(localStorage.getItem("hrhelper_thread_profile_map") || "{}");
            mapping[threadId] = normalized;
            localStorage.setItem("hrhelper_thread_profile_map", JSON.stringify(mapping));
            log(" Saved thread mapping to localStorage:", threadId.substring(0, 10) + "... -> " + normalized);
            saveThreadMappingToBackend(threadId, normalized);
          } catch (e) {
            warn(" Error saving thread mapping to localStorage:", e);
          }
        }
        return normalized;
      }
    }
    if (threadId) {
      try {
        const mapping = JSON.parse(localStorage.getItem("hrhelper_thread_profile_map") || "{}");
        if (mapping[threadId]) {
          log(" Profile from localStorage:", mapping[threadId]);
          if (state) state.messagingProfileCache = mapping[threadId];
          return mapping[threadId];
        }
        const result = await HRH.apiFetch("/api/v1/linkedin/thread-mapping/?thread_id=" + threadId, { method: "GET" });
        if (result && result.ok) {
          const data = await result.json().catch(() => null);
          if (data?.profile_url) {
            log(" Profile from backend:", data.profile_url);
            if (state) state.messagingProfileCache = data.profile_url;
            try {
              const m = JSON.parse(localStorage.getItem("hrhelper_thread_profile_map") || "{}");
              m[threadId] = data.profile_url;
              localStorage.setItem("hrhelper_thread_profile_map", JSON.stringify(m));
            } catch (_) {}
            return data.profile_url;
          }
        }
        warn(" Thread not mapped:", threadId);
      } catch (e) {
        logError(" Error getting profile:", e);
      }
    }
    return null;
  }

  function findMessagingComposer() {
    const selectors = [
      ".msg-form__contenteditable", ".msg-form__composer", '[data-view-name="msg-form"]',
      "form.msg-form", ".msg-form__msg-content-container", '[role="textbox"][contenteditable="true"]'
    ];
    for (const sel of selectors) {
      const el = document.querySelector(sel);
      if (el) {
        const form = el.closest("form") || el.closest(".msg-form") || el.closest('[data-view-name="msg-form"]');
        return form || el.parentElement;
      }
    }
    return null;
  }

  HRH.linkedinMessaging = {
    extractThreadIdFromMessageButton,
    saveThreadMappingToBackend,
    captureProfileToThreadMapping,
    getProfileLinkFromMessaging,
    findMessagingComposer
  };
})();
