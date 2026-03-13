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

  try {
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
  } catch (_) {}

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
          box-shadow: 0 1px 3px rgba(0,0,0,.3), 0 2px 8px rgba(0,0,0,.25) !important;
        }
        .hrhelper-communication-btn.hrhelper-cal-theme-dark:hover { box-shadow: 0 2px 6px rgba(0,0,0,.35), 0 4px 12px rgba(0,0,0,.2) !important; }
        .hrhelper-communication-btn.hrhelper-cal-theme-dark .hrhelper-cal-sep { opacity: .85 !important; }
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

    function isExtensionContextValid() {
      try {
        return !!(chrome && chrome.runtime && chrome.runtime.id);
      } catch (_) {
        return false;
      }
    }

    function buildCalendarContactButtonPlaceholder() {
      if (!isExtensionContextValid()) return null;
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
      try {
        extIcon.src = chrome.runtime.getURL("icons/icon-32.png");
      } catch (_) {
        extIcon.src = "";
      }
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

    function getMessengerIconSvg(linkType) {
      const icons = {
        telegram: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm4.64 6.8c-.15 1.58-.8 5.42-1.13 7.19-.14.75-.42 1-.68 1.03-.58.05-1.02-.38-1.58-.75-.88-.58-1.38-.94-2.23-1.5-.99-.65-.35-1.01.22-1.59.15-.15 2.71-2.48 2.76-2.69a.2.2 0 00-.05-.18c-.06-.05-.14-.03-.21-.02-.09.02-1.49.95-4.22 2.79-.4.27-.76.41-1.08.4-.36-.01-1.04-.2-1.55-.37-.63-.2-1.12-.31-1.08-.66.02-.18.27-.36.74-.55 2.92-1.27 4.86-2.11 5.83-2.51 2.78-1.16 3.35-1.36 3.73-1.36.08 0 .27.02.39.12.1.08.13.19.14.27-.01.06.01.24 0 .38z"/></svg>',
        linkedin: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor"><path d="M19 3a2 2 0 012 2v14a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h14m-.5 15.5v-5.3a3.26 3.26 0 00-3.26-3.26c-.85 0-1.84.52-2.32 1.3v-1.11h-2.79v8.37h2.79v-4.93c0-.77.62-1.4 1.39-1.4a1.4 1.4 0 011.4 1.4v4.93h2.79M6.88 8.56a1.68 1.68 0 001.68-1.68c0-.93-.75-1.69-1.68-1.69a1.69 1.69 0 00-1.69 1.69c0 .93.76 1.68 1.69 1.68m1.39 9.94v-8.37H5.5v8.37h2.77z"/></svg>',
        whatsapp: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor"><path d="M12.04 2c-5.46 0-9.91 4.45-9.91 9.91 0 1.75.46 3.45 1.32 4.95L2.05 22l5.25-1.38c1.45.79 3.08 1.21 4.74 1.21 5.46 0 9.91-4.45 9.91-9.91 0-2.65-1.03-5.14-2.9-7.01A9.816 9.816 0 0012.04 2m.01 1.67c2.2 0 4.26.86 5.82 2.42a8.225 8.225 0 012.41 5.83c0 4.54-3.7 8.23-8.24 8.23-1.48 0-2.93-.39-4.19-1.15l-.3-.17-3.12.82.83-3.04-.2-.32a8.188 8.188 0 01-1.26-4.38c.01-4.54 3.7-8.24 8.25-8.24M8.53 7.33c-.16 0-.43.06-.66.31-.22.25-.87.86-.87 2.07 0 1.22.89 2.39 1 2.56.14.17 1.76 2.67 4.25 3.73.59.27 1.05.42 1.41.53.59.19 1.13.16 1.56.1.48-.07 1.46-.6 1.67-1.18.21-.58.21-1.07.15-1.18-.07-.1-.23-.16-.48-.27-.25-.14-1.47-.74-1.69-.82-.23-.08-.37-.12-.56.12-.16.25-.64.81-.78.97-.15.17-.29.19-.53.07-.26-.13-1.06-.39-2-1.23-.74-.66-1.23-1.47-1.38-1.72-.12-.24-.01-.39.11-.5.11-.11.27-.29.37-.44.13-.14.17-.25.25-.41.08-.17.04-.31-.02-.43-.06-.11-.56-1.35-.77-1.84-.2-.48-.4-.42-.56-.43-.14 0-.3-.01-.47-.01z"/></svg>',
        viber: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor"><path d="M11.4 0C9.5.1 5.4.5 3.3 2.5 1.5 4.3.8 7 .7 10.4c-.1 3.3-.2 9.5 5.8 11.1v2.6s0 1 .6 1.2c.8.3 1.2-.5 2-1.3l1.4-1.6c3.8.3 6.8-.4 7.1-.5.8-.2 5.2-.8 5.9-6.6.8-6-1-9.8-3.3-11.5C17.8 2 13.3.1 11.4 0zm.3 2c1.6.1 5.5.6 7.3 2 1.8 1.4 3.3 4.4 2.6 9.5-.6 4.6-3.8 5.2-4.5 5.4-.3.1-2.8.6-5.9.5 0 0-2.4 2.9-3.1 3.6-.1.1-.3.2-.4.1-.2-.1-.2-.4-.2-.6v-4c-4.8-1.3-4.5-6.2-4.4-9 .1-2.8.6-5 2-6.4C6.8 1.6 10.1 1.9 11.7 2zm-.3 3.2c-.2 0-.4.2-.4.4s.2.4.4.4c1.1 0 2.1.4 2.9 1.2.8.7 1.2 1.7 1.3 2.9 0 .2.2.4.4.4h.1c.2 0 .4-.2.3-.5 0-1.4-.5-2.6-1.5-3.5-.9-.9-2.2-1.3-3.5-1.3zm-2.8 1c-.3 0-.6 0-.9.2l-.2.1c-.3.2-.5.4-.7.7-.2.3-.3.6-.3.9 0 .1 0 .2.1.2l.1.5c.3 1 .8 2 1.5 2.8l.1.2c.6.8 1.4 1.5 2.2 2.1l.2.1c.8.5 1.6.9 2.5 1.2l.4.1h.3c.4 0 .7-.1 1-.4.2-.2.5-.5.6-.8l.1-.2c.1-.3 0-.6-.2-.8l-1.3-1c-.2-.2-.6-.2-.8 0l-.6.5c-.1.1-.3.1-.4 0-.4-.2-.9-.5-1.3-.9-.4-.3-.7-.7-1-1.1-.1-.1-.1-.3 0-.4l.5-.6c.2-.2.2-.5 0-.8l-1-1.4c-.2-.2-.4-.3-.7-.3zm5.5.7c-.2 0-.4.2-.4.4 0 .2.2.4.4.4.6 0 1.1.2 1.5.6.4.4.6.9.6 1.5 0 .2.2.4.4.4.2 0 .4-.2.4-.4 0-.8-.3-1.5-.9-2.1-.5-.5-1.2-.8-2-.8z"/></svg>',
        default: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor"><path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm0 14H6l-2 2V4h16v12z"/></svg>'
      };
      return icons[linkType] || icons.default;
    }

    function setCalendarButtonContent(button, linkType, labelText) {
      const labelEl = button.querySelector(".hrhelper-cal-label");
      if (labelEl) labelEl.textContent = labelText;
      
      let messengerIcon = button.querySelector(".hrhelper-cal-messenger-icon");
      if (!messengerIcon) {
        messengerIcon = document.createElement("span");
        messengerIcon.className = "hrhelper-cal-messenger-icon";
        button.appendChild(messengerIcon);
      }
      messengerIcon.innerHTML = getMessengerIconSvg(linkType);
      
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

      // Ищем контейнер «Уведомить гостей» / Notify guests — туда и будем добавлять кнопку
      const notifyContainer = findNotifyGuestsContainer();
      if (!notifyContainer || !notifyContainer.container) return;

      // Не создаём дубликаты кнопки
      const existing = notifyContainer.container.querySelector(
        ".hrhelper-communication-btn.hrhelper-cal-default, " +
          ".hrhelper-communication-btn.hrhelper-cal-telegram, " +
          ".hrhelper-communication-btn.hrhelper-cal-linkedin, " +
          ".hrhelper-communication-btn.hrhelper-cal-whatsapp, " +
          ".hrhelper-communication-btn.hrhelper-cal-viber"
      );
      if (existing) return;

      // Пытаемся найти ссылку Huntflow в событии (если есть — настраиваем кнопку по API)
      const allLinks = Array.from(document.querySelectorAll("a"));
      const huntflowLink = allLinks.find((a) => {
        const href = (a.href || "").toLowerCase();
        const text = (a.textContent || "").toLowerCase();
        return href.includes("huntflow.ru") || href.includes("huntflow.dev") || text.includes("huntflow.ru") || text.includes("huntflow.dev");
      });

      const button = buildCalendarContactButtonPlaceholder();
      if (!button) return;
      const targetContainer = notifyContainer.container;
      const insertAfter = notifyContainer.buttons?.[notifyContainer.buttons.length - 1] || null;
      if (insertAfter && insertAfter.nextSibling) targetContainer.insertBefore(button, insertAfter.nextSibling);
      else targetContainer.appendChild(button);

      if (!huntflowLink) {
        // Линки Huntflow не нашли — показываем капсулу, но без рабочей ссылки
        setCalendarButtonContent(button, "default", "Ссылка не найдена");
        button.style.cursor = "not-allowed";
        button.href = "#";
        applyCalendarButtonTheme();
        startCalendarThemeObserver();
        return;
      }

      const huntflowUrl = huntflowLink.href;

      // Просим backend сам разобрать huntflow_url; не валидируем формат на фронте,
      // чтобы не ломаться, если изменилась структура hash/URL.
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

