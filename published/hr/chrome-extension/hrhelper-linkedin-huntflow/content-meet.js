/**
 * HR Helper — content script для Google Meet
 * Вынесено из content.js (декомпозиция по доменам).
 */
(function () {
  const HRH = window.__HRH__;
  if (!HRH) throw new Error("[HRHelper] shared/constants.js not loaded");
  const apiFetch = HRH.apiFetch;
  if (!apiFetch) throw new Error("[HRHelper] shared/api/client.js not loaded (apiFetch missing)");
  const debounce = HRH.debounce;
  const TIMING = HRH.TIMING || {};

  const DEBUG = false;
  const IS_GOOGLE_MEET = location.href.includes("meet.google.com");
  const log = (...args) => (DEBUG || IS_GOOGLE_MEET) && console.log("[HRHelper Meet]", ...args);
  const warn = (...args) => (DEBUG || IS_GOOGLE_MEET) && console.warn("[HRHelper Meet]", ...args);
  function logError(...args) {
    const serialized = args.map((a) => (a && typeof a === "object" && !(a instanceof Error) ? JSON.stringify(a) : a));
    console.error("[HRHelper Meet]", ...serialized);
  }

  const STATE = {
    meet: {
      scorecardLink: null,
      communicationLink: null,
      communicationLabel: null,
      level: null,
      vacancyName: null,
      huntflowUrl: null,
      reminderPhrase: null,
    },
  };

  const UI = {
    styleInjected: false,
    openAllInjected: false,
  };

  function makeWidgetDraggable(wrapper, storageKey) {
    if (!wrapper) return;
    try {
      const saved = localStorage.getItem(storageKey);
      if (saved) {
        const obj = JSON.parse(saved);
        if (typeof obj.top === "number" && typeof obj.left === "number") {
          const margin = 8;
          let top = obj.top;
          let left = obj.left;
          const maxTop = window.innerHeight - wrapper.offsetHeight - margin;
          const maxLeft = window.innerWidth - wrapper.offsetWidth - margin;
          top = Math.min(Math.max(margin, top), Math.max(margin, maxTop));
          left = Math.min(Math.max(margin, left), Math.max(margin, maxLeft));
          wrapper.style.top = top + "px";
          wrapper.style.left = left + "px";
          wrapper.style.right = "auto";
        }
      }
    } catch (_) {}

    let drag = null;
    const start = (ev) => {
      const e = ev.touches ? ev.touches[0] : ev;
      drag = {
        startX: e.clientX,
        startY: e.clientY,
        origTop: wrapper.getBoundingClientRect().top,
        origLeft: wrapper.getBoundingClientRect().left,
      };
      document.addEventListener("mousemove", move);
      document.addEventListener("mouseup", stop);
      document.addEventListener("touchmove", move, { passive: false });
      document.addEventListener("touchend", stop);
    };
    const move = (ev) => {
      if (!drag) return;
      const e = ev.touches ? ev.touches[0] : ev;
      if (ev.cancelable) ev.preventDefault();
      const dy = e.clientY - drag.startY;
      const dx = e.clientX - drag.startX;
      const margin = 8;
      const maxTop = window.innerHeight - wrapper.offsetHeight - margin;
      const maxLeft = window.innerWidth - wrapper.offsetWidth - margin;
      let top = drag.origTop + dy;
      let left = drag.origLeft + dx;
      top = Math.min(Math.max(margin, top), Math.max(margin, maxTop));
      left = Math.min(Math.max(margin, left), Math.max(margin, maxLeft));
      wrapper.style.top = top + "px";
      wrapper.style.left = left + "px";
      wrapper.style.right = "auto";
    };
    const stop = () => {
      if (!drag) return;
      document.removeEventListener("mousemove", move);
      document.removeEventListener("mouseup", stop);
      document.removeEventListener("touchmove", move);
      document.removeEventListener("touchend", stop);
      try {
        const rect = wrapper.getBoundingClientRect();
        localStorage.setItem(storageKey, JSON.stringify({ top: rect.top, left: rect.left }));
      } catch (_) {}
      drag = null;
    };

    wrapper.style.cursor = "move";
    wrapper.addEventListener("mousedown", start);
    wrapper.addEventListener("touchstart", start, { passive: true });
  }

  function getMeetCodeFromUrl() {
    try {
      const path = location.pathname || "";
      const match = path.match(/^\/([a-z]{3}-[a-z]{4}-[a-z]{3})/i);
      return match ? match[1].toLowerCase() : null;
    } catch (_) {
      return null;
    }
  }

  async function fetchMeetDataByMeetCode(meetCode) {
    try {
      const q = new URLSearchParams({ meet_code: meetCode });
      const res = await apiFetch(`/api/v1/huntflow/linkedin-applicants/by-meet/?${q.toString()}`, { method: "GET" });
      if (!res.ok) return null;
      const data = await res.json().catch(() => null);
      return data && data.success ? data : null;
    } catch (err) {
      if (err?.message && !err.message.includes("Extension context invalidated")) logError("fetchMeetDataByMeetCode:", err);
      return null;
    }
  }

  async function fetchReminderPhrase() {
    try {
      const res = await apiFetch("/api/v1/accounts/users/reminder-phrase/", { method: "GET" });
      if (!res.ok) return "";
      const data = await res.json().catch(() => null);
      if (data && data.success && data.data && typeof data.data.reminder_phrase === "string") {
        return (data.data.reminder_phrase || "").trim();
      }
      return "";
    } catch (err) {
      if (err?.message && !err.message.includes("Extension context invalidated")) logError("fetchReminderPhrase:", err);
      return "";
    }
  }

  async function fetchLevelText(level, vacancyName) {
    try {
      if (!level) return "";
      const q = new URLSearchParams({ level });
      if (vacancyName) q.set("vacancy_name", vacancyName);
      const res = await apiFetch(`/api/v1/huntflow/linkedin-applicants/level-text/?${q.toString()}`, { method: "GET" });
      if (!res.ok) return "";
      const data = await res.json().catch(() => null);
      if (data && data.success && typeof data.text === "string") return (data.text || "").trim();
      return "";
    } catch (err) {
      if (err?.message && !err.message.includes("Extension context invalidated")) logError("fetchLevelText:", err);
      return "";
    }
  }

  async function copyToClipboard(text) {
    const t = (text || "").toString();
    if (!t) return false;
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(t);
        return true;
      }
    } catch (_) {}
    try {
      const ta = document.createElement("textarea");
      ta.value = t;
      ta.setAttribute("readonly", "true");
      ta.style.position = "fixed";
      ta.style.top = "-1000px";
      ta.style.left = "-1000px";
      document.body.appendChild(ta);
      ta.select();
      ta.setSelectionRange(0, ta.value.length);
      const ok = document.execCommand("copy");
      document.body.removeChild(ta);
      return !!ok;
    } catch (_) {
      return false;
    }
  }

  function ensureMeetUiStyles() {
    if (UI.styleInjected) return;
    UI.styleInjected = true;
    const style = document.createElement("style");
    style.id = "hrhelper-meet-ui-style";
    style.textContent = `
      .hrh-meet-openall-btn{
        margin-left:8px!important;
        padding:2px 8px!important;
        min-height:0!important;
        border-radius:4px!important;
        border:1px solid rgba(255,255,255,.12)!important;
        background:#3c4043!important;
        color:rgba(255,255,255,.9)!important;
        font:500 11px/1.3 system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif!important;
        cursor:pointer!important;
        user-select:none!important;
      }
      .hrh-meet-openall-btn:hover{ background:#5f6368!important; }
      .hrh-meet-openall-btn:disabled{ opacity:.55!important; cursor:not-allowed!important; }
    `;
    (document.head || document.documentElement).appendChild(style);
  }

  function findGoogleMeetTitleNode() {
    // Ищем видимый текст "Google Meet" в хедере.
    // У Meet DOM часто меняется, поэтому делаем best-effort.
    const candidates = Array.from(document.querySelectorAll("span,div,h1,h2"));
    for (const el of candidates) {
      if (!el || !el.textContent) continue;
      const txt = el.textContent.trim();
      if (txt === "Google Meet") return el;
    }
    return null;
  }

  function injectOpenAllButton(titleNode) {
    if (!titleNode || UI.openAllInjected) return;
    const parent = titleNode.parentElement;
    if (!parent) return;
    ensureMeetUiStyles();

    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "hrh-meet-openall-btn";
    btn.textContent = "Открыть всё";
    btn.title = "Скопировать текст и открыть Huntflow + Scorecard";

    const onClick = async () => {
      try {
        btn.disabled = true;
        const { level, vacancyName, huntflowUrl, scorecardLink } = STATE.meet;
        const text = await fetchLevelText(level, vacancyName);
        if (text) await copyToClipboard(text);

        const urls = [];
        if (huntflowUrl) urls.push(huntflowUrl);
        if (scorecardLink) urls.push(scorecardLink);
        if (urls.length) {
          chrome.runtime.sendMessage({ type: "HRHELPER_OPEN_TABS", urls }, () => {});
        }
      } catch (err) {
        warn("OpenAll error", err);
      } finally {
        btn.disabled = false;
      }
    };
    btn.addEventListener("click", onClick);

    // Вставляем сразу после текста "Google Meet"
    titleNode.insertAdjacentElement("afterend", btn);
    UI.openAllInjected = true;
    log("OpenAll button injected");
  }

  function ensureOpenAllButton() {
    if (!IS_GOOGLE_MEET || UI.openAllInjected) return;
    const node = findGoogleMeetTitleNode();
    if (node) injectOpenAllButton(node);
  }

  function injectReminderBlock(phrase) {
    if (!phrase || document.getElementById("hrhelper-reminder-block")) return;
    const block = document.createElement("div");
    block.id = "hrhelper-reminder-block";
    block.style.cssText =
      "position:fixed!important;top:12px!important;left:12px!important;z-index:99998!important;max-width:320px!important;padding:10px 14px!important;background:rgba(0,0,0,0.88)!important;border-radius:8px!important;box-shadow:0 2px 12px rgba(0,0,0,0.4)!important;font-family:system-ui,sans-serif!important;font-size:13px!important;line-height:1.4!important;color:#fff!important;border-left:4px solid #0a66c2!important;user-select:none!important;";
    const label = document.createElement("div");
    label.textContent = "Напоминание";
    label.style.cssText = "font-size:11px!important;color:rgba(255,255,255,0.7)!important;margin-bottom:4px!important;";
    const text = document.createElement("div");
    text.textContent = phrase;
    text.style.cssText = "word-wrap:break-word!important;white-space:pre-wrap!important;";
    block.appendChild(label);
    block.appendChild(text);
    document.body.appendChild(block);
    makeWidgetDraggable(block, "hrhelper_meet_reminder_pos");
    chrome.storage.local.get({ hrhelper_meet_reminder_hidden: false }, (data) => {
      if (data.hrhelper_meet_reminder_hidden) block.style.display = "none";
    });
    log("Reminder block injected");
  }

  function getPageContext() {
    const pageUrl = location.href;
    const m = STATE.meet;
    return {
      url: true,
      pageUrl,
      scorecardLink: m.scorecardLink || undefined,
      communicationLink: m.communicationLink || undefined,
      communicationLabel: m.communicationLabel || undefined,
      level: m.level || undefined,
      vacancyName: m.vacancyName || undefined,
      huntflowUrl: m.huntflowUrl || undefined,
      reminderPhrase: m.reminderPhrase || undefined,
    };
  }

  chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
    if (msg && msg.action === "getPageContext") {
      try {
        sendResponse(getPageContext());
      } catch (_) {
        sendResponse({ url: false });
      }
      return true;
    }
    if (msg && msg.action === "copyLevelText") {
      const { level, vacancyName } = STATE.meet;
      if (!level || !IS_GOOGLE_MEET) {
        sendResponse({ success: false });
        return true;
      }
      const q = new URLSearchParams({ level });
      if (vacancyName) q.set("vacancy_name", vacancyName);
      chrome.runtime.sendMessage(
        { type: "HRHELPER_API", payload: { path: `/api/v1/huntflow/linkedin-applicants/level-text/?${q.toString()}`, method: "GET" } },
        (apiRes) => {
          try {
            if (!apiRes || !apiRes.ok) {
              sendResponse({ success: false });
              return;
            }
            const data = apiRes.json;
            if (data && data.success && data.text) sendResponse({ success: true, text: data.text });
            else sendResponse({ success: false });
          } catch (_) {
            sendResponse({ success: false });
          }
        }
      );
      return true;
    }
    if (msg && msg.action === "setMeetReminderVisible" && IS_GOOGLE_MEET) {
      const visible = msg.visible === true;
      chrome.storage.local.set({ hrhelper_meet_reminder_hidden: !visible }, () => {
        const block = document.getElementById("hrhelper-reminder-block");
        if (block) block.style.display = visible ? "" : "none";
        else if (visible && STATE.meet.reminderPhrase) injectReminderBlock(STATE.meet.reminderPhrase);
        sendResponse({ success: true });
      });
      return true;
    }
  });

  function initGoogleMeet() {
    if (!IS_GOOGLE_MEET) return;
    log("Google Meet detected, initializing...");

    fetchReminderPhrase().then((phrase) => {
      if (phrase) {
        STATE.meet.reminderPhrase = phrase;
        injectReminderBlock(phrase);
      }
    });

    const meetCode = getMeetCodeFromUrl();
    if (meetCode) {
      fetchMeetDataByMeetCode(meetCode).then((data) => {
        if (!data) return;
        STATE.meet.scorecardLink = data.scorecard_link || null;
        STATE.meet.communicationLink = data.communication_link || null;
        STATE.meet.communicationLabel = data.communication_label || "Контакт";
        STATE.meet.level = data.level || null;
        STATE.meet.vacancyName = data.vacancy_title || null;
        STATE.meet.huntflowUrl = data.huntflow_url || null;
        // После получения данных пробуем поставить кнопку (у нас появятся ссылки).
        ensureOpenAllButton();
      });
    }

    // Meet DOM подгружается/меняется — наблюдаем и пробуем вставить кнопку несколько раз (с debounce).
    ensureOpenAllButton();
    const debouncedEnsure = debounce(ensureOpenAllButton, TIMING.DEBOUNCE_CALENDAR_MEET || 500);
    const mo = new MutationObserver(() => debouncedEnsure());
    try {
      mo.observe(document.documentElement, { childList: true, subtree: true });
      setTimeout(() => {
        try { mo.disconnect(); } catch (_) {}
      }, 30_000);
    } catch (_) {}
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initGoogleMeet);
  } else {
    initGoogleMeet();
  }
})();

