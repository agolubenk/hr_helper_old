/**
 * HR Helper — content script для Google Calendar
 * Вынесено из content.js (декомпозиция по доменам).
 */
(function () {
  const HRH = window.__HRH__;
  if (!HRH) throw new Error("[HRHelper] shared/constants.js not loaded");
  const apiFetch = HRH.apiFetch;
  if (!apiFetch) throw new Error("[HRHelper] shared/api/client.js not loaded (apiFetch missing)");
  const debounce = HRH.debounce;
  const TIMING = HRH.TIMING || {};
  const OPTIONS_THEME_KEY = HRH.OPTIONS_THEME_KEY;
  if (!OPTIONS_THEME_KEY) throw new Error("[HRHelper] shared/constants.js not loaded (OPTIONS_THEME_KEY missing)");

  const DEBUG = false;
  const IS_GOOGLE_CALENDAR = location.href.includes("calendar.google.com");
  const log = (...args) => (DEBUG || IS_GOOGLE_CALENDAR) && console.log("[HRHelper Calendar]", ...args);
  const warn = (...args) => (DEBUG || IS_GOOGLE_CALENDAR) && console.warn("[HRHelper Calendar]", ...args);
  function logError(...args) {
    const serialized = args.map((a) => (a && typeof a === "object" && !(a instanceof Error) ? JSON.stringify(a) : a));
    console.error("[HRHelper Calendar]", ...serialized);
  }

  function getPageContext() {
    const pageUrl = location.href;
    const titleEl = document.querySelector("[data-event-title]") || document.querySelector("h1");
    return { url: true, pageUrl, eventTitle: titleEl ? titleEl.textContent.trim().slice(0, 80) : null };
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
  });

  function initGoogleCalendar() {
    if (!IS_GOOGLE_CALENDAR) return;

    log("Google Calendar detected, initializing...");

    function findNotifyGuestsContainer() {
      const searchTexts = ["Уведомить гостей", "уведомить гостей", "Notify guests", "notify guests", "Уведомить", "Notify"];
      const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null);
      let textNode;
      while ((textNode = walker.nextNode())) {
        const text = (textNode.textContent || "").trim();
        for (const searchText of searchTexts) {
          if (!text.includes(searchText)) continue;
          let element = textNode.parentElement;
          for (let i = 0; i < 15 && element; i++) {
            const buttons = Array.from(element.querySelectorAll("button, a, [role='button']"));
            if (buttons.length > 0) {
              const style = window.getComputedStyle(element);
              if (style.display !== "none") return { container: element, buttons, referenceElement: textNode };
            }
            const parent = element.parentElement;
            if (parent) {
              const parentButtons = Array.from(parent.querySelectorAll("button, a, [role='button']"));
              if (parentButtons.length > buttons.length && parentButtons.length > 0) {
                const parentStyle = window.getComputedStyle(parent);
                if (parentStyle.display !== "none") return { container: parent, buttons: parentButtons, referenceElement: element };
              }
            }
            element = element.parentElement;
          }
        }
      }
      return null;
    }

    function ensureCalendarButtonStyles() {
      if (document.getElementById("hrhelper-calendar-btn-styles")) return;
      const style = document.createElement("style");
      style.id = "hrhelper-calendar-btn-styles";
      style.textContent = `
        .hrhelper-communication-btn {
          display: inline-flex !important;
          align-items: center !important;
          gap: 4px !important;
          margin-left: 8px !important;
          padding: 4px 10px 4px 6px !important;
          text-decoration: none !important;
          border-radius: 999px !important;
          font-size: 12px !important;
          font-weight: 500 !important;
          white-space: nowrap !important;
          border: 1px solid rgba(0,0,0,.12) !important;
          background: #fff !important;
          color: #333 !important;
          box-shadow: 0 1px 3px rgba(0,0,0,.08), 0 2px 6px rgba(0,0,0,.06) !important;
          transition: opacity .2s, box-shadow .2s !important;
        }
        .hrhelper-communication-btn:hover { opacity: .9; box-shadow: 0 2px 6px rgba(0,0,0,.12), 0 3px 10px rgba(0,0,0,.08) !important; }
        .hrhelper-communication-btn .hrhelper-cal-ext-icon { width: 16px; height: 16px; flex-shrink: 0; display: block !important; }
        .hrhelper-communication-btn .hrhelper-cal-sep { color: rgba(0,0,0,.25); font-weight: 400; margin: 0 1px !important; padding: 0 !important; }
        .hrhelper-communication-btn .hrhelper-cal-label { flex: 0 1 auto; overflow: hidden; text-overflow: ellipsis !important; }
        .hrhelper-communication-btn .hrhelper-cal-messenger-icon { width: 16px; height: 16px; flex-shrink: 0; display: flex; align-items: center; justify-content: center !important; }
        .hrhelper-communication-btn .hrhelper-cal-messenger-icon svg { width: 14px; height: 14px; }
        .hrhelper-communication-btn.hrhelper-cal-telegram { border-color: #0088cc !important; color: #0088cc !important; box-shadow: 0 1px 3px rgba(0,0,0,.08), 0 2px 6px rgba(0,0,0,.06), 0 0 0 1px rgba(0,136,204,.15) !important; }
        .hrhelper-communication-btn.hrhelper-cal-telegram .hrhelper-cal-sep { color: rgba(0,136,204,.5) !important; }
        .hrhelper-communication-btn.hrhelper-cal-linkedin { border-color: #0a66c2 !important; color: #0a66c2 !important; box-shadow: 0 1px 3px rgba(0,0,0,.08), 0 2px 6px rgba(0,0,0,.06), 0 0 0 1px rgba(10,102,194,.15) !important; }
        .hrhelper-communication-btn.hrhelper-cal-linkedin .hrhelper-cal-sep { color: rgba(10,102,194,.5) !important; }
        .hrhelper-communication-btn.hrhelper-cal-whatsapp { border-color: #25D366 !important; color: #25D366 !important; box-shadow: 0 1px 3px rgba(0,0,0,.08), 0 2px 6px rgba(0,0,0,.06), 0 0 0 1px rgba(37,211,102,.2) !important; }
        .hrhelper-communication-btn.hrhelper-cal-whatsapp .hrhelper-cal-sep { color: rgba(37,211,102,.5) !important; }
        .hrhelper-communication-btn.hrhelper-cal-viber { border-color: #7360f2 !important; color: #7360f2 !important; box-shadow: 0 1px 3px rgba(0,0,0,.08), 0 2px 6px rgba(0,0,0,.06), 0 0 0 1px rgba(115,96,242,.2) !important; }
        .hrhelper-communication-btn.hrhelper-cal-viber .hrhelper-cal-sep { color: rgba(115,96,242,.5) !important; }
        .hrhelper-communication-btn.hrhelper-cal-default { border-color: #6c757d !important; color: #6c757d !important; box-shadow: 0 1px 3px rgba(0,0,0,.08), 0 2px 6px rgba(0,0,0,.06) !important; }
        .hrhelper-communication-btn.hrhelper-cal-default .hrhelper-cal-sep { color: rgba(108,117,125,.5) !important; }
        .hrhelper-communication-btn.hrhelper-cal-theme-dark {
          background: #3c4043 !important;
          border-color: rgba(255,255,255,.2) !important;
          color: #e8eaed !important;
          box-shadow: 0 1px 3px rgba(0,0,0,.3), 0 2px 8px rgba(0,0,0,.25) !important;
        }
        .hrhelper-communication-btn.hrhelper-cal-theme-dark:hover { box-shadow: 0 2px 6px rgba(0,0,0,.35), 0 4px 12px rgba(0,0,0,.2) !important; }
        .hrhelper-communication-btn.hrhelper-cal-theme-dark .hrhelper-cal-sep { color: rgba(255,255,255,.4) !important; }
      `;
      (document.head || document.documentElement).appendChild(style);
    }

    function parseRgbLuminance(cssColor) {
      if (!cssColor || cssColor === "transparent") return null;
      const m = cssColor.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/);
      if (m) {
        const r = parseInt(m[1], 10),
          g = parseInt(m[2], 10),
          b = parseInt(m[3], 10);
        return (0.299 * r + 0.587 * g + 0.114 * b) / 255;
      }
      return null;
    }

    function getCalendarSiteTheme() {
      const html = document.documentElement;
      const body = document.body;
      if (html.getAttribute("data-theme") === "dark" || html.getAttribute("data-theme") === "dark_theme") return "dark";
      if (html.getAttribute("data-theme") === "light" || html.getAttribute("data-theme") === "light_theme") return "light";
      try {
        const sampleLuminance = (el) => {
          if (!el) return null;
          const bg = window.getComputedStyle(el).backgroundColor;
          return parseRgbLuminance(bg);
        };
        const bodyLum = sampleLuminance(body);
        if (bodyLum != null) {
          if (bodyLum < 0.45) return "dark";
          if (bodyLum > 0.6) return "light";
        }
        const htmlLum = sampleLuminance(html);
        if (htmlLum != null) {
          if (htmlLum < 0.45) return "dark";
          if (htmlLum > 0.6) return "light";
        }
      } catch (_) {}
      return null;
    }

    function getCalendarResolvedTheme() {
      return new Promise((resolve) => {
        try {
          chrome.storage.sync.get({ [OPTIONS_THEME_KEY]: "system" }, (data) => {
            const theme = data[OPTIONS_THEME_KEY] || "system";
            if (theme === "light") {
              resolve("light");
              return;
            }
            if (theme === "dark") {
              resolve("dark");
              return;
            }
            const siteTheme = getCalendarSiteTheme();
            if (siteTheme === "dark" || siteTheme === "light") {
              resolve(siteTheme);
              return;
            }
            resolve(window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
          });
        } catch (_) {
          resolve("light");
        }
      });
    }

    function applyCalendarButtonTheme() {
      getCalendarResolvedTheme().then((resolved) => {
        const dark = resolved === "dark";
        document.querySelectorAll(".hrhelper-communication-btn").forEach((btn) => {
          if (dark) btn.classList.add("hrhelper-cal-theme-dark");
          else btn.classList.remove("hrhelper-cal-theme-dark");
        });
      });
    }

    function startCalendarThemeObserver() {
      if (window._hrhelperCalendarThemeObserver) return;
      const run = () => applyCalendarButtonTheme();
      run();
      const debouncedRun = debounce(run, (TIMING && TIMING.DEBOUNCE_THEME) || 50);
      const observer = new MutationObserver(() => debouncedRun());
      observer.observe(document.documentElement, { attributes: true, attributeFilter: ["class", "data-theme", "style"] });
      if (document.body) observer.observe(document.body, { attributes: true, attributeFilter: ["class", "style"] });
      window._hrhelperCalendarThemeObserver = observer;
    }

    function buildCalendarContactButtonPlaceholder() {
      ensureCalendarButtonStyles();
      const a = document.createElement("a");
      a.className = "hrhelper-communication-btn hrhelper-cal-default";
      a.href = "#";
      a.setAttribute("aria-label", "Загрузка...");
      a.onclick = (e) => {
        e.preventDefault();
        return false;
      };
      const extIcon = document.createElement("img");
      extIcon.className = "hrhelper-cal-ext-icon";
      extIcon.src = chrome.runtime.getURL("icons/icon-32.png");
      extIcon.alt = "";
      const sep = document.createElement("span");
      sep.className = "hrhelper-cal-sep";
      sep.textContent = "|";
      const label = document.createElement("span");
      label.className = "hrhelper-cal-label";
      label.textContent = "Загрузка...";
      a.appendChild(extIcon);
      a.appendChild(sep);
      a.appendChild(label);
      return a;
    }

    function setCalendarButtonContent(button, linkType, labelText) {
      const labelEl = button.querySelector(".hrhelper-cal-label");
      if (labelEl) labelEl.textContent = labelText;
      const classes = ["hrhelper-cal-telegram", "hrhelper-cal-linkedin", "hrhelper-cal-whatsapp", "hrhelper-cal-viber", "hrhelper-cal-default"];
      button.classList.remove(...classes);
      if (linkType === "telegram") button.classList.add("hrhelper-cal-telegram");
      else if (linkType === "linkedin") button.classList.add("hrhelper-cal-linkedin");
      else if (linkType === "whatsapp") button.classList.add("hrhelper-cal-whatsapp");
      else if (linkType === "viber") button.classList.add("hrhelper-cal-viber");
      else button.classList.add("hrhelper-cal-default");
    }

    function extractHuntflowIds(url) {
      const result = { account_name: null, applicant_id: null, vacancy_id: null };
      const m1a = url.match(/\/my\/([^/#]+)#\/applicants\/filter\/[^/]+\/id\/(\d+)/);
      if (m1a) {
        result.account_name = m1a[1];
        result.applicant_id = parseInt(m1a[2]);
        return result;
      }
      const m1 = url.match(/\/my\/([^/#]+)#\/applicants\/filter\/[^/]+\/(\d+)/);
      if (m1) {
        result.account_name = m1[1];
        result.applicant_id = parseInt(m1[2]);
        return result;
      }
      const m2 = url.match(/\/my\/([^/#]+)#\/vacancy\/(\d+)\/filter\/[^/]+\/id\/(\d+)/);
      if (m2) {
        result.account_name = m2[1];
        result.vacancy_id = parseInt(m2[2]);
        result.applicant_id = parseInt(m2[3]);
        return result;
      }
      return result;
    }

    async function getCommunicationLink(huntflowUrl) {
      try {
        const qp = new URLSearchParams({ huntflow_url: huntflowUrl });
        const res = await apiFetch(`/api/v1/huntflow/linkedin-applicants/communication-link/?${qp.toString()}`, { method: "GET" });
        if (!res.ok) return null;
        return await res.json().catch(() => null);
      } catch (err) {
        if (err?.message && !err.message.includes("Extension context invalidated")) logError("getCommunicationLink:", err);
        return null;
      }
    }

    function processInterviewerLinks() {
      ensureCalendarButtonStyles();
      const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null);
      let textNode;
      const interviewerNodes = [];
      const interviewerSearchTexts = ["Для интервьюеров:", "For interviewers:"];
      while ((textNode = walker.nextNode())) {
        const t = textNode.textContent || "";
        if (interviewerSearchTexts.some((s) => t.includes(s))) interviewerNodes.push(textNode);
      }

      interviewerNodes.forEach((node) => {
        const parent = node.parentElement;
        if (!parent) return;
        if (parent.dataset.hrhelperProcessed === "true") return;
        parent.dataset.hrhelperProcessed = "true";

        // Ищем ссылку Huntflow в документе/контейнере
        const allLinks = Array.from(document.querySelectorAll("a"));
        const huntflowLink = allLinks.find((a) => {
          const href = (a.href || "").toLowerCase();
          const text = (a.textContent || "").toLowerCase();
          return href.includes("huntflow.ru") || href.includes("huntflow.dev") || text.includes("huntflow.ru") || text.includes("huntflow.dev");
        });
        if (!huntflowLink) return;
        const huntflowUrl = huntflowLink.href;
        const ids = extractHuntflowIds(huntflowUrl);
        if (!ids.account_name || !ids.applicant_id) return;

        const notifyContainer = findNotifyGuestsContainer();
        const button = buildCalendarContactButtonPlaceholder();
        const targetContainer = notifyContainer?.container || huntflowLink.parentElement || parent;
        const insertAfter = notifyContainer?.buttons?.[notifyContainer.buttons.length - 1] || null;
        if (insertAfter && insertAfter.nextSibling) targetContainer.insertBefore(button, insertAfter.nextSibling);
        else targetContainer.appendChild(button);

        getCommunicationLink(huntflowUrl).then((linkData) => {
          if (linkData && linkData.success && linkData.communication_link) {
            button.href = linkData.communication_link;
            button.target = "_blank";
            button.rel = "noopener noreferrer";
            button.onclick = null;
            let linkType = linkData.link_type || "default";
            if (linkType === "unknown" && linkData.communication_link) {
              const u = String(linkData.communication_link).toLowerCase();
              if (u.includes("wa.me") || u.includes("whatsapp")) linkType = "whatsapp";
              else if (u.includes("viber")) linkType = "viber";
            }
            const labels = { telegram: "Telegram", linkedin: "LinkedIn", whatsapp: "WhatsApp", viber: "Viber" };
            setCalendarButtonContent(button, linkType, labels[linkType] || "Связаться");
            button.setAttribute("aria-label", labels[linkType] || "Связаться");
            applyCalendarButtonTheme();
          } else {
            setCalendarButtonContent(button, "default", "Ссылка не найдена");
            button.style.cursor = "not-allowed";
            button.href = "#";
          }
        });

        applyCalendarButtonTheme();
        startCalendarThemeObserver();
      });
    }

    setTimeout(() => processInterviewerLinks(), 1000);
    processInterviewerLinks();

    let processTimeout = null;
    const observer = new MutationObserver(() => {
      if (processTimeout) clearTimeout(processTimeout);
      processTimeout = setTimeout(() => processInterviewerLinks(), 500);
    });
    if (document.body) observer.observe(document.body, { childList: true, subtree: true });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initGoogleCalendar);
  } else {
    initGoogleCalendar();
  }
})();

