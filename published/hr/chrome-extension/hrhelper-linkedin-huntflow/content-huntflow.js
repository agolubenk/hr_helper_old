/**
 * HR Helper — content script для страниц Huntflow (huntflow.ru/my/...)
 * Под фотографией кандидата: квадратные кнопки соцсетей из поля «Где ведется коммуникация».
 * В правом верхнем углу каждой кнопки — кнопка копирования ссылки.
 */
(async function () {
  var HRH = window.__HRH__;
  if (!HRH) {
    throw new Error("[HRHelper] shared/constants.js not loaded");
  }
  var ACTIVE_PAGES_KEY = HRH.ACTIVE_PAGES_KEY;
  var DEFAULT_ACTIVE_PAGES = HRH.DEFAULT_ACTIVE_PAGES;
  if (!ACTIVE_PAGES_KEY || !DEFAULT_ACTIVE_PAGES) {
    throw new Error("[HRHelper] shared/constants.js not loaded (ACTIVE_PAGES_KEY/DEFAULT_ACTIVE_PAGES missing)");
  }
  try {
    var data = await chrome.storage.sync.get({ [ACTIVE_PAGES_KEY]: DEFAULT_ACTIVE_PAGES });
    var active = data[ACTIVE_PAGES_KEY] || DEFAULT_ACTIVE_PAGES;
    if (!active.huntflow) return;
  } catch (_) {
    return;
  }

  var DEFAULTS = HRH.DEFAULTS;
  const OPTIONS_THEME_KEY = HRH.OPTIONS_THEME_KEY;
  const DEFAULT_THEME = HRH.DEFAULT_THEME;
  if (!DEFAULTS || !OPTIONS_THEME_KEY || !DEFAULT_THEME) {
    throw new Error("[HRHelper] shared/constants.js not loaded (DEFAULTS/theme keys missing)");
  }
  const ATTR = "data-hrhelper-huntflow-buttons";
  const ATTR_FLOATING = "data-hrhelper-huntflow-floating";
  const ATTR_PHONE = "data-hrhelper-phone-copy";
  const ATTR_EMAIL = "data-hrhelper-email-copy";
  const ATTR_FIO = "data-hrhelper-fio-copy";
  const DEBUG = false;
  const log = (...args) => DEBUG && console.log("[HRHelper Huntflow]", ...args);

  const ICONS = {
    linkedin: '<svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor"><path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/></svg>',
    telegram: '<svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor"><path d="M11.944 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0a12 12 0 0 0-.056 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 0 1 .171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.48.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z"/></svg>',
    whatsapp: '<svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"/></svg>',
    viber: '<svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor"><path d="M11.4 0C9.5.1 5.4.5 3.3 2.5 1.5 4.3.8 7 .7 10.4c-.1 3.3-.2 9.5 5.8 11.1v2.6s0 1 .6 1.2c.8.3 1.2-.5 2-1.3l1.4-1.6c3.8.3 6.8-.4 7.1-.5.8-.2 5.2-.8 5.9-6.6.8-6-1-9.8-3.3-11.5C17.8 2 13.3.1 11.4 0zm.3 2c1.6.1 5.5.6 7.3 2 1.8 1.4 3.3 4.4 2.6 9.5-.6 4.6-3.8 5.2-4.5 5.4-.3.1-2.8.6-5.9.5 0 0-2.4 2.9-3.1 3.6-.1.1-.3.2-.4.1-.2-.1-.2-.4-.2-.6v-4c-4.8-1.3-4.5-6.2-4.4-9 .1-2.8.6-5 2-6.4C6.8 1.6 10.1 1.9 11.7 2zm-.3 3.2c-.2 0-.4.2-.4.4s.2.4.4.4c1.1 0 2.1.4 2.9 1.2.8.7 1.2 1.7 1.3 2.9 0 .2.2.4.4.4h.1c.2 0 .4-.2.3-.5 0-1.4-.5-2.6-1.5-3.5-.9-.9-2.2-1.3-3.5-1.3zm-2.8 1c-.3 0-.6 0-.9.2l-.2.1c-.3.2-.5.4-.7.7-.2.3-.3.6-.3.9 0 .1 0 .2.1.2l.1.5c.3 1 .8 2 1.5 2.8l.1.2c.6.8 1.4 1.5 2.2 2.1l.2.1c.8.5 1.6.9 2.5 1.2l.4.1h.3c.4 0 .7-.1 1-.4.2-.2.5-.5.6-.8l.1-.2c.1-.3 0-.6-.2-.8l-1.3-1c-.2-.2-.6-.2-.8 0l-.6.5c-.1.1-.3.1-.4 0-.4-.2-.9-.5-1.3-.9-.4-.3-.7-.7-1-1.1-.1-.1-.1-.3 0-.4l.5-.6c.2-.2.2-.5 0-.8l-1-1.4c-.2-.2-.4-.3-.7-.3z"/></svg>',
    communication: '<svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor"><path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm0 14H6l-2 2V4h16v12z"/></svg>'
  };

  const COLORS = {
    linkedin: "#0a66c2",
    telegram: "#0088cc",
    whatsapp: "#25d366",
    viber: "#7360f2",
    communication: "#0a66c2"
  };

  function extractUsernameFromUrl(url, type) {
    if (!url || !type) return null;
    const u = (url || "").trim();
    if (type === "telegram") {
      const m = u.match(/(?:t\.me|telegram\.me|telegram\.dog)\/([a-zA-Z0-9_]+)/i) || u.match(/@([a-zA-Z0-9_]{5,32})/);
      return m ? m[1] : null;
    }
    if (type === "viber") {
      const m = u.match(/viber:\/\/chat\?number=%2B?(\d+)/i) || u.match(/viber\.me\/(\+?\d+)/i);
      return m ? (m[1].startsWith("+") ? m[1] : "+" + m[1]) : null;
    }
    if (type === "whatsapp") {
      const m = u.match(/wa\.me\/(\+?\d+)/i);
      return m ? m[1] : null;
    }
    if (type === "linkedin") {
      const m = u.match(/linkedin\.com\/in\/([a-zA-Z0-9_-]+)/i);
      return m ? m[1] : null;
    }
    return null;
  }

  /** Определяет тип соцсети по URL (fallback, если бэкенд вернул communication) */
  function detectLinkType(url, backendType) {
    if (backendType && backendType !== "communication" && ICONS[backendType]) return backendType;
    const u = (url || "").toLowerCase();
    if (/viber\.me|viber:\/\/|viber\.chat/i.test(u)) return "viber";
    if (/t\.me|telegram\.me|telegram\.dog|telegram/i.test(u)) return "telegram";
    if (/wa\.me|whatsapp\.com|api\.whatsapp\.com/i.test(u)) return "whatsapp";
    if (/linkedin\.com|linked\.in/i.test(u)) return "linkedin";
    return "communication";
  }

  function getHuntflowUrl() {
    const u = window.location.href;
    if (!u || !u.includes("huntflow") || (!u.includes("/my/") && !u.includes("/my#"))) return null;
    return u.split("?")[0];
  }

  function extractApplicantId(url) {
    if (!url) return null;
    const m = url.match(/\/id\/(\d+)/);
    if (m) return m[1];
    const m2 = url.match(/#\/applicants\/filter\/[^/]+\/(\d+)/);
    if (m2) return m2[1];
    const m3 = url.match(/\/applicants\/(\d+)/);
    return m3 ? m3[1] : null;
  }

  function isApplicantPage() {
    const url = getHuntflowUrl();
    if (!url) return false;
    return !!extractApplicantId(url);
  }

  var apiFetch = HRH.apiFetch;
  if (!apiFetch) {
    throw new Error("[HRHelper] shared/api/client.js not loaded (apiFetch missing)");
  }

  async function fetchCandidateLinks(huntflowUrl) {
    const res = await apiFetch(
      `/api/v1/huntflow/linkedin-applicants/candidate-links/?huntflow_url=${encodeURIComponent(huntflowUrl)}`
    );
    const data = await res.json();
    if (!res.ok || !data?.success) return [];
    return data.links || [];
  }

  function getTelegramFromPage() {
    const applicantInfo = findApplicantInfo();
    if (!applicantInfo) return null;
    const dts = applicantInfo.querySelectorAll('dt[data-qa="applicant-info-table-key"], dt');
    for (const dt of dts) {
      const label = (dt.textContent || "").trim().toLowerCase();
      if (!label.includes("telegram") && !label.includes("телеграм")) continue;
      const dd = dt.nextElementSibling;
      if (!dd) continue;
      const link = dd.querySelector('a[href*="t.me"], a[href*="telegram"]');
      if (link) {
        const href = (link.getAttribute("href") || "").trim();
        if (href) return href;
      }
      const text = (dd.textContent || "").trim();
      const m = text.match(/@?([a-zA-Z0-9_]{5,32})/);
      if (m) return "https://t.me/" + m[1];
      return null;
    }
    return null;
  }

  function getPhoneFromPage() {
    const applicantInfo = findApplicantInfo();
    if (!applicantInfo) return null;
    const dts = applicantInfo.querySelectorAll('dt[data-qa="applicant-info-table-key"], dt');
    for (const dt of dts) {
      if ((dt.textContent || "").trim() !== "Телефон") continue;
      const dd = dt.nextElementSibling;
      if (!dd) continue;
      const phoneLink = dd.querySelector('a[href^="tel:"]');
      if (!phoneLink) continue;
      const href = (phoneLink.getAttribute("href") || "").replace(/^tel:/i, "").replace(/\D/g, "");
      const title = (phoneLink.getAttribute("title") || "").trim();
      return href ? "+" + href : (title && /^\+?[\d\s\-()]+$/.test(title) ? title : null);
    }
    return null;
  }

  function injectFioCopyButton() {
    const h1 =
      document.querySelector('h1[data-qa="applicant-card-title"]') ||
      document.querySelector('[data-qa="applicant-card-title"]') ||
      document.querySelector('h1.title--dumeD');
    if (!h1 || h1.closest(`[${ATTR_FIO}="1"]`)) return;
    const fio = (h1.getAttribute("title") || h1.textContent || "").trim();
    if (!fio) return;

    const copyBtn = document.createElement("button");
    copyBtn.type = "button";
    copyBtn.setAttribute(ATTR_FIO, "1");
    copyBtn.title = "Копировать ФИО";
    copyBtn.style.cssText =
      "display:inline-flex;align-items:center;justify-content:center;width:28px;height:28px;margin-left:8px;padding:0;border:1px solid rgba(0,0,0,.15);border-radius:6px;background:#fff;color:#495057;cursor:pointer;vertical-align:middle;transition:background .15s,color .15s;flex-shrink:0;";
    copyBtn.innerHTML = COPY_ICON_SVG;
    copyBtn.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      copyToClipboard(fio).then(() => {
        copyBtn.style.background = "#d4edda";
        copyBtn.style.borderColor = "#c3e6cb";
        copyBtn.title = "Скопировано";
        setTimeout(() => {
          copyBtn.style.background = "#fff";
          copyBtn.style.borderColor = "rgba(0,0,0,.15)";
          copyBtn.title = "Копировать ФИО";
        }, 800);
      });
    });
    copyBtn.addEventListener("mouseenter", () => { copyBtn.style.background = "#f8f9fa"; });
    copyBtn.addEventListener("mouseleave", () => { copyBtn.style.background = "#fff"; });

    const parent = h1.parentElement;
    if (!parent) return;

    const wrapper = document.createElement("div");
    wrapper.setAttribute(ATTR_FIO, "1");
    wrapper.style.cssText =
      "display:inline-flex;align-items:center;flex-wrap:nowrap;gap:8px;";
    parent.insertBefore(wrapper, h1);
    wrapper.appendChild(h1);
    wrapper.appendChild(copyBtn);
  }

  function injectPhoneCopyButton() {
    const applicantInfo = findApplicantInfo();
    if (!applicantInfo) return;
    if (applicantInfo.querySelector(`[${ATTR_PHONE}="1"]`)) return;

    const dts = applicantInfo.querySelectorAll('dt[data-qa="applicant-info-table-key"], dt');
    for (const dt of dts) {
      const label = (dt.textContent || "").trim();
      if (label !== "Телефон") continue;
      const dd = dt.nextElementSibling;
      if (!dd) continue;
      const phoneLink = dd.querySelector('a[href^="tel:"]');
      if (!phoneLink) continue;
      const href = (phoneLink.getAttribute("href") || "").replace(/^tel:/i, "").replace(/\D/g, "");
      const title = (phoneLink.getAttribute("title") || "").trim();
      const phone = href ? "+" + href : ((title && /^\+?[\d\s\-()]+$/.test(title)) ? title : "");
      if (!phone) continue;

      const copyBtn = document.createElement("button");
      copyBtn.type = "button";
      copyBtn.setAttribute(ATTR_PHONE, "1");
      copyBtn.title = "Копировать номер";
      copyBtn.style.cssText =
        "display:inline-flex;align-items:center;justify-content:center;width:28px;height:28px;margin-right:6px;padding:0;border:1px solid rgba(0,0,0,.15);border-radius:6px;background:#fff;color:#495057;cursor:pointer;vertical-align:middle;transition:background .15s,color .15s;";
      copyBtn.innerHTML = COPY_ICON_SVG;
      copyBtn.addEventListener("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        copyToClipboard(phone).then(() => {
          copyBtn.style.background = "#d4edda";
          copyBtn.style.borderColor = "#c3e6cb";
          copyBtn.title = "Скопировано";
          setTimeout(() => {
            copyBtn.style.background = "#fff";
            copyBtn.style.borderColor = "rgba(0,0,0,.15)";
            copyBtn.title = "Копировать номер";
          }, 800);
        });
      });
      copyBtn.addEventListener("mouseenter", () => { copyBtn.style.background = "#f8f9fa"; });
      copyBtn.addEventListener("mouseleave", () => { copyBtn.style.background = "#fff"; });

      const container = phoneLink.parentElement;
      const messengerWrapper = phoneLink.nextElementSibling;
      if (container) {
        container.insertBefore(copyBtn, messengerWrapper || phoneLink.nextSibling);
      }
      break;
    }
  }

  function injectEmailCopyButton() {
    const applicantInfo = findApplicantInfo();
    if (!applicantInfo) return;
    if (applicantInfo.querySelector(`[${ATTR_EMAIL}="1"]`)) return;

    const emailLabels = ["Email", "Почта", "E-mail", "e-mail", "Эл. почта", "эл. почта", "Электронная почта"];
    const tryInject = (labelEl, valueEl) => {
      if (!valueEl) return false;
      let email = "";
      const emailLink = valueEl.querySelector ? valueEl.querySelector('a[href^="mailto:"]') : null;
      if (emailLink) {
        email = (emailLink.getAttribute("href") || "").replace(/^mailto:/i, "").split("?")[0].trim();
      }
      if (!email) {
        const text = (valueEl.textContent || "").trim();
        const m = text.match(/[\w.+-]+@[\w.-]+\.\w+/);
        if (m) email = m[0];
      }
      if (!email) return false;

      const findEmailElement = (root) => {
        for (const c of root.children || []) {
          const found = findEmailElement(c);
          if (found) return found;
        }
        return (root.textContent || "").trim() === email ? root : null;
      };
      const emailEl = emailLink || findEmailElement(valueEl);

      const copyBtn = document.createElement("button");
      copyBtn.type = "button";
      copyBtn.setAttribute(ATTR_EMAIL, "1");
      copyBtn.title = "Копировать email";
      copyBtn.style.cssText =
        "display:inline-flex;align-items:center;justify-content:center;width:28px;height:28px;margin-left:6px;padding:0;border:1px solid rgba(0,0,0,.15);border-radius:6px;background:#fff;color:#495057;cursor:pointer;vertical-align:middle;flex-shrink:0;transition:background .15s,color .15s;";
      copyBtn.innerHTML = COPY_ICON_SVG;
      copyBtn.addEventListener("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        copyToClipboard(email).then(() => {
          copyBtn.style.background = "#d4edda";
          copyBtn.style.borderColor = "#c3e6cb";
          copyBtn.title = "Скопировано";
          setTimeout(() => {
            copyBtn.style.background = "#fff";
            copyBtn.style.borderColor = "rgba(0,0,0,.15)";
            copyBtn.title = "Копировать email";
          }, 800);
        });
      });
      copyBtn.addEventListener("mouseenter", () => { copyBtn.style.background = "#f8f9fa"; });
      copyBtn.addEventListener("mouseleave", () => { copyBtn.style.background = "#fff"; });

      const insertParent = emailEl ? emailEl.parentElement : valueEl;
      const insertBefore = emailEl ? emailEl.nextSibling : null;
      if (!insertParent) return true;

      const wrapper = document.createElement("span");
      wrapper.style.cssText = "display:inline-flex!important;align-items:center!important;flex-wrap:nowrap!important;white-space:nowrap!important;";
      insertParent.insertBefore(wrapper, emailEl);
      wrapper.appendChild(emailEl);
      wrapper.appendChild(copyBtn);

      if (valueEl?.style) {
        valueEl.style.display = valueEl.style.display || "flex";
        valueEl.style.flexWrap = "nowrap";
        valueEl.style.alignItems = "center";
      }
      if (insertParent?.style && insertParent !== valueEl) {
        insertParent.style.display = insertParent.style.display || "flex";
        insertParent.style.flexWrap = "nowrap";
        insertParent.style.alignItems = "center";
      }
      return true;
    };

    const dts = applicantInfo.querySelectorAll('dt[data-qa="applicant-info-table-key"], dt');
    for (const dt of dts) {
      const label = (dt.textContent || "").trim().toLowerCase();
      if (!emailLabels.some((l) => label === l.toLowerCase()) && !label.includes("почта")) continue;
      if (tryInject(dt, dt.nextElementSibling)) break;
    }
    if (!applicantInfo.querySelector(`[${ATTR_EMAIL}="1"]`)) {
      const all = applicantInfo.querySelectorAll('[class*="row"], [class*="field"], div');
      for (const el of all) {
        const txt = (el.textContent || "").trim();
        if ((txt === "Эл. почта" || txt === "Email" || txt.toLowerCase().includes("почта")) && txt.length < 30) {
          const next = el.nextElementSibling || el.parentElement?.nextElementSibling;
          if (tryInject(el, next || el.parentElement)) break;
        }
      }
    }
  }

  function findApplicantInfo() {
    return (
      document.querySelector('[data-qa="applicant-info"]') ||
      document.querySelector('[data-testid="applicant-info"]') ||
      document.querySelector('[class*="applicant-info"]')
    );
  }

  function getFioFromPage() {
    const h1 =
      document.querySelector('h1[data-qa="applicant-card-title"]') ||
      document.querySelector('[data-qa="applicant-card-title"]') ||
      document.querySelector('h1.title--dumeD');
    if (!h1) return null;
    return (h1.getAttribute("title") || h1.textContent || "").trim() || null;
  }

  function getEmailFromPage() {
    const applicantInfo = findApplicantInfo();
    if (!applicantInfo) return null;
    const emailLabels = ["Email", "Почта", "E-mail", "e-mail", "Эл. почта", "эл. почта", "Электронная почта"];
    const dts = applicantInfo.querySelectorAll('dt[data-qa="applicant-info-table-key"], dt');
    for (const dt of dts) {
      const label = (dt.textContent || "").trim().toLowerCase();
      if (!emailLabels.some((l) => label === l.toLowerCase()) && !label.includes("почта")) continue;
      const dd = dt.nextElementSibling;
      if (!dd) continue;
      const emailLink = dd.querySelector('a[href^="mailto:"]');
      if (emailLink) {
        const href = (emailLink.getAttribute("href") || "").replace(/^mailto:/i, "").split("?")[0].trim();
        if (href) return href;
      }
      const m = (dd.textContent || "").trim().match(/[\w.+-]+@[\w.-]+\.\w+/);
      if (m) return m[0];
    }
    return null;
  }

  /** Только внутри applicant-info — иначе попадаем в списки/сайдбары */
  function findPhotoContainer() {
    const applicantInfo = findApplicantInfo();
    if (!applicantInfo) return null;
    const photo = applicantInfo.querySelector('[data-qa="applicant_photo"]') || applicantInfo.querySelector('[data-testid="applicant_photo"]');
    if (photo && photo.offsetParent !== null) return photo;
    const photoWrapper = applicantInfo.querySelector('div[class*="photo"]');
    if (photoWrapper && photoWrapper.offsetParent !== null) return photoWrapper;
    const img = applicantInfo.querySelector('img[alt*="кандидат"], img[alt*="applicant"]');
    if (img && img.offsetParent !== null) return img.parentElement || img;
    return applicantInfo.querySelector('[class*="avatar"]') || applicantInfo.firstElementChild;
  }

  const COPY_ICON_SVG = '<svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor"><path d="M16 1H4c-1.1 0-2 .9-2 2v14h2V3h12V1zm3 4H8c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h11c1.1 0 2-.9 2-2V7c0-1.1-.9-2-2-2zm0 16H8V7h11v14z"/></svg>';

  function copyToClipboard(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      return navigator.clipboard.writeText(text);
    }
    return new Promise((resolve) => {
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      try {
        document.execCommand("copy");
      } finally {
        document.body.removeChild(ta);
      }
      resolve();
    });
  }

  const USER_ICON_SVG = '<svg viewBox="0 0 24 24" width="12" height="12" fill="currentColor"><path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"/></svg>';

  function createButtonEl(link, type, color, icon, username, fullFeatures) {
    const btn = document.createElement("a");
    btn.href = link.url;
    btn.target = "_blank";
    btn.rel = "noopener noreferrer";
    btn.title = link.label;
    btn.style.cssText =
      `position:relative;display:flex;align-items:center;justify-content:center;width:48px;height:48px;min-width:48px;flex-shrink:0;border-radius:8px;background:${color};color:#fff!important;text-decoration:none;transition:transform .15s,box-shadow .15s;`;
    btn.innerHTML = icon;
    btn.addEventListener("mouseenter", () => {
      btn.style.transform = "scale(1.05)";
      btn.style.boxShadow = "0 4px 12px rgba(0,0,0,.2)";
    });
    btn.addEventListener("mouseleave", () => {
      btn.style.transform = "scale(1)";
      btn.style.boxShadow = "none";
    });

    if (fullFeatures) {
      const copyLinkBtn = document.createElement("button");
      copyLinkBtn.type = "button";
      copyLinkBtn.className = "hrhelper-hf-social-copy-btn";
      copyLinkBtn.title = "Копировать ссылку";
      copyLinkBtn.style.cssText =
        "position:absolute;top:2px;right:2px;width:18px;height:18px;border-radius:4px;cursor:pointer;display:flex;align-items:center;justify-content:center;padding:0;transition:opacity .15s;";
      copyLinkBtn.innerHTML =
        '<svg viewBox="0 0 24 24" width="12" height="12" fill="currentColor"><path d="M16 1H4c-1.1 0-2 .9-2 2v14h2V3h12V1zm3 4H8c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h11c1.1 0 2-.9 2-2V7c0-1.1-.9-2-2-2zm0 16H8V7h11v14z"/></svg>';
      copyLinkBtn.addEventListener("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        copyToClipboard(link.url).then(() => {
          copyLinkBtn.classList.add("hrhelper-hf-copy-btn-copied");
          copyLinkBtn.title = "Скопировано";
          setTimeout(() => {
            copyLinkBtn.classList.remove("hrhelper-hf-copy-btn-copied");
            copyLinkBtn.title = "Копировать ссылку";
          }, 800);
        });
      });
      copyLinkBtn.addEventListener("mouseenter", () => { copyLinkBtn.style.opacity = "1"; });
      copyLinkBtn.addEventListener("mouseleave", () => { copyLinkBtn.style.opacity = ""; });
      btn.appendChild(copyLinkBtn);

      if (username) {
        const copyUserBtn = document.createElement("button");
        copyUserBtn.type = "button";
        copyUserBtn.className = "hrhelper-hf-social-copy-btn";
        copyUserBtn.title = "Копировать никнейм";
        copyUserBtn.style.cssText =
          "position:absolute;top:2px;left:2px;width:18px;height:18px;border-radius:4px;cursor:pointer;display:flex;align-items:center;justify-content:center;padding:0;transition:opacity .15s;";
        copyUserBtn.innerHTML = USER_ICON_SVG;
        copyUserBtn.addEventListener("click", (e) => {
          e.preventDefault();
          e.stopPropagation();
          copyToClipboard(username).then(() => {
            copyUserBtn.classList.add("hrhelper-hf-copy-btn-copied");
            copyUserBtn.title = "Скопировано";
            setTimeout(() => {
              copyUserBtn.classList.remove("hrhelper-hf-copy-btn-copied");
              copyUserBtn.title = "Копировать никнейм";
            }, 800);
          });
        });
        copyUserBtn.addEventListener("mouseenter", () => { copyUserBtn.style.opacity = "1"; });
        copyUserBtn.addEventListener("mouseleave", () => { copyUserBtn.style.opacity = ""; });
        btn.appendChild(copyUserBtn);
      }
    }
    return btn;
  }

  function createButtonsContainer(links, phone) {
    const wrap = document.createElement("div");
    wrap.setAttribute(ATTR, "1");
    wrap.style.cssText =
      "display:flex;flex-wrap:nowrap;align-items:center;gap:10px;margin-top:12px;padding-top:12px;border-top:1px solid rgba(0,0,0,.08);width:100%;flex-shrink:0;overflow-x:auto;overflow-y:hidden;";

    const seenUrls = new Set();
    const explicitLinks = [];
    const typesExplicit = new Set();
    const order = ["telegram", "linkedin"];
    const byType = { telegram: [], linkedin: [], other: [] };
    for (const link of links) {
      const norm = (link.url || "").trim().toLowerCase();
      if (seenUrls.has(norm)) continue;
      seenUrls.add(norm);
      const type = detectLinkType(link.url, link.type);
      typesExplicit.add(type);
      if (type === "telegram") byType.telegram.push(link);
      else if (type === "linkedin") byType.linkedin.push(link);
      else byType.other.push(link);
    }
    order.forEach((t) => explicitLinks.push(...byType[t]));
    explicitLinks.push(...byType.other);

    explicitLinks.forEach((link) => {
      const type = detectLinkType(link.url, link.type);
      const color = COLORS[type] || COLORS.communication;
      const icon = ICONS[type] || ICONS.communication;
      const username = link.username || extractUsernameFromUrl(link.url, type);
      wrap.appendChild(createButtonEl(link, type, color, icon, username, true));
    });

    const phoneDigits = phone ? phone.replace(/\D/g, "") : "";
    const phoneMessengers = [];
    if (phoneDigits) {
      phoneMessengers.push(
        { type: "whatsapp", url: `https://wa.me/${phoneDigits}`, label: "WhatsApp" },
        { type: "viber", url: `viber://chat?number=%2B${phoneDigits}`, label: "Viber" }
      );
      if (!typesExplicit.has("telegram")) {
        phoneMessengers.push({
          type: "telegram",
          url: `https://t.me/+${phoneDigits}`,
          label: "Telegram"
        });
      }
    }
    const potentialLinks = [];
    if (phoneDigits) {
      for (const m of phoneMessengers) {
        if (typesExplicit.has(m.type)) continue;
        potentialLinks.push({ url: m.url, label: m.label, type: m.type });
      }
    }

    if (explicitLinks.length > 0 && potentialLinks.length > 0) {
      const sep = document.createElement("span");
      sep.textContent = "|";
      sep.style.cssText = "color:rgba(0,0,0,.3);font-size:18px;line-height:1;flex-shrink:0;margin:0 2px;";
      wrap.appendChild(sep);
    }

    potentialLinks.forEach((m) => {
      const link = { url: m.url, label: m.label, type: m.type };
      const color = COLORS[m.type] || COLORS.communication;
      const icon = ICONS[m.type] || ICONS.communication;
      wrap.appendChild(createButtonEl(link, m.type, color, icon, null, true));
    });

    return wrap.children.length > 0 ? wrap : null;
  }

  const STORAGE_KEY_HUNTFLOW_POS = "hrhelper_huntflow_floating_pos";
  const HUNTFLOW_FLOATING_HIDDEN_KEY = "hrhelper_huntflow_floating_hidden";
  const HUNTFLOW_FLOATING_UI_STATE_KEY = "hrhelper_huntflow_floating_ui_state";
  const DEFAULT_HUNTFLOW_FLOATING_UI_STATE = { widgetCollapsed: false };
  let huntflowFloatingUIState = { ...DEFAULT_HUNTFLOW_FLOATING_UI_STATE };

  function getResolvedHuntflowTheme() {
    return new Promise(function (resolve) {
      chrome.storage.sync.get({ [OPTIONS_THEME_KEY]: DEFAULT_THEME }, function (data) {
        var t = (data[OPTIONS_THEME_KEY] || DEFAULT_THEME).toLowerCase();
        if (t === "light" || t === "dark") return resolve(t);
        var dark = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
        resolve(dark ? "dark" : "light");
      });
    });
  }

  function applyHuntflowFloatingTheme(wrapper) {
    if (!wrapper || !wrapper.classList) return;
    getResolvedHuntflowTheme().then(function (theme) {
      if (theme === "dark") wrapper.classList.add("hrhelper-theme-dark");
      else wrapper.classList.remove("hrhelper-theme-dark");
    });
  }

  function injectHuntflowFloatingThemeStyles() {
    if (document.getElementById("hrhelper-huntflow-floating-theme")) return;
    var style = document.createElement("style");
    style.id = "hrhelper-huntflow-floating-theme";
    style.textContent = `
      .hrhelper-huntflow-floating-widget { background: var(--hrhelper-hf-bg) !important; color: var(--hrhelper-hf-text) !important; }
      .hrhelper-huntflow-floating-widget .hrhelper-hf-header { border-bottom-color: var(--hrhelper-hf-border) !important; }
      .hrhelper-huntflow-floating-widget .hrhelper-hf-title { color: var(--hrhelper-hf-accent) !important; }
      .hrhelper-huntflow-floating-widget .hrhelper-hf-body,
      .hrhelper-huntflow-floating-widget .hrhelper-hf-body * { color: var(--hrhelper-hf-text) !important; }
      .hrhelper-huntflow-floating-widget .hrhelper-hf-section-title { color: var(--hrhelper-hf-text); border-top-color: var(--hrhelper-hf-border); }
      .hrhelper-huntflow-floating-widget .hrhelper-hf-vacancy-card { padding: 8px 10px; border-radius: 8px; border: 1px solid var(--hrhelper-hf-card-border); background: var(--hrhelper-hf-card-bg); display: flex; align-items: flex-start; gap: 8px; flex-wrap: nowrap; }
      .hrhelper-huntflow-floating-widget .hrhelper-hf-vacancy-line1 { font-size: 12px; color: var(--hrhelper-hf-text); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
      .hrhelper-huntflow-floating-widget .hrhelper-hf-vacancy-line2 { font-size: 11px; color: var(--hrhelper-hf-muted); }
      .hrhelper-huntflow-floating-widget .hrhelper-hf-copy-btn { border: 1px solid var(--hrhelper-hf-border) !important; background: var(--hrhelper-hf-input-bg) !important; color: var(--hrhelper-hf-text) !important; transition: background .15s, border-color .15s, color .15s; }
      .hrhelper-huntflow-floating-widget .hrhelper-hf-copy-btn:hover { background: var(--hrhelper-hf-btn-bg) !important; }
      .hrhelper-huntflow-floating-widget .hrhelper-hf-copy-btn.hrhelper-hf-copy-btn-copied { background: var(--hrhelper-hf-success-bg) !important; border-color: var(--hrhelper-hf-success-border) !important; color: var(--hrhelper-hf-success) !important; }
      .hrhelper-huntflow-floating-widget .hrhelper-hf-fio-text { color: var(--hrhelper-hf-text); }
      .hrhelper-huntflow-floating-widget .hrhelper-hf-row-text { color: var(--hrhelper-hf-muted); }
      .hrhelper-huntflow-floating-widget .hrhelper-hf-social-copy-btn { background: var(--hrhelper-hf-input-bg) !important; color: var(--hrhelper-hf-text) !important; border: 1px solid var(--hrhelper-hf-border); opacity: 0.95; }
      .hrhelper-huntflow-floating-widget .hrhelper-hf-social-copy-btn:hover { opacity: 1; }
      .hrhelper-huntflow-floating-widget .hrhelper-hf-social-copy-btn.hrhelper-hf-copy-btn-copied { background: var(--hrhelper-hf-success-bg) !important; color: var(--hrhelper-hf-success) !important; border-color: var(--hrhelper-hf-success-border); }
      .hrhelper-huntflow-floating-widget button[style*="border-radius:4px"] { background: var(--hrhelper-hf-btn-bg) !important; color: var(--hrhelper-hf-muted) !important; border-color: var(--hrhelper-hf-border) !important; transition: background .15s ease, opacity .15s ease !important; }
      .hrhelper-huntflow-floating-widget button[style*="border-radius:4px"]:hover { background: var(--hrhelper-hf-border) !important; }
      .hrhelper-huntflow-floating-widget button[style*="border-radius:4px"]:active { background: rgba(0,0,0,.15) !important; }
      .hrhelper-huntflow-floating-widget.hrhelper-theme-dark button[style*="border-radius:4px"]:active { background: rgba(255,255,255,.15) !important; }
      .hrhelper-huntflow-floating-widget .hrhelper-huntflow-toggle-btn { transition: background .15s ease !important; }
      .hrhelper-huntflow-floating-widget .hrhelper-huntflow-toggle-btn:hover { background: var(--hrhelper-hf-border) !important; }
      .hrhelper-huntflow-floating-widget .hrhelper-huntflow-toggle-btn:active { background: rgba(0,0,0,.15) !important; }
      .hrhelper-huntflow-floating-widget.hrhelper-theme-dark .hrhelper-huntflow-toggle-btn:active { background: rgba(255,255,255,.15) !important; }
      .hrhelper-huntflow-floating-widget { --hrhelper-hf-bg: rgba(255,255,255,.98); --hrhelper-hf-text: #212529; --hrhelper-hf-muted: #6c757d; --hrhelper-hf-border: rgba(0,0,0,.08); --hrhelper-hf-accent: #0a66c2; --hrhelper-hf-btn-bg: rgba(0,0,0,.05); --hrhelper-hf-input-bg: #fff; --hrhelper-hf-success: #0f5132; --hrhelper-hf-success-bg: #d1e7dd; --hrhelper-hf-success-border: #a3cfbb; --hrhelper-hf-card-bg: #e7f1ff; --hrhelper-hf-card-border: #b6d4fe; --hrhelper-hf-card-rejected-bg: #f8d7da; --hrhelper-hf-card-rejected-border: #f1aeb5; --hrhelper-hf-card-archived-bg: #e9ecef; --hrhelper-hf-card-archived-border: #dee2e6; }
      .hrhelper-huntflow-floating-widget.hrhelper-theme-dark {
        --hrhelper-hf-bg: #161b22; --hrhelper-hf-text: #e6edf3; --hrhelper-hf-muted: #8b949e; --hrhelper-hf-border: rgba(255,255,255,.12); --hrhelper-hf-accent: #58a6ff; --hrhelper-hf-btn-bg: rgba(255,255,255,.08); --hrhelper-hf-input-bg: #0d1117;
        --hrhelper-hf-success: #3fb950; --hrhelper-hf-success-bg: rgba(63,185,80,.2); --hrhelper-hf-success-border: rgba(63,185,80,.4);
        --hrhelper-hf-card-bg: rgba(88,166,255,.08); --hrhelper-hf-card-border: rgba(88,166,255,.35); --hrhelper-hf-card-rejected-bg: rgba(248,81,73,.15); --hrhelper-hf-card-rejected-border: rgba(248,81,73,.4); --hrhelper-hf-card-archived-bg: #21262d; --hrhelper-hf-card-archived-border: rgba(255,255,255,.12);
      }
      .hrhelper-huntflow-floating-widget .hrhelper-hf-vacancy-card-rejected { border-color: var(--hrhelper-hf-card-rejected-border); background: var(--hrhelper-hf-card-rejected-bg); }
      .hrhelper-huntflow-floating-widget .hrhelper-hf-vacancy-card-archived { border-color: var(--hrhelper-hf-card-archived-border); background: var(--hrhelper-hf-card-archived-bg); }
    `;
    (document.head || document.documentElement).appendChild(style);
  }

  function loadHuntflowFloatingUIState() {
    return new Promise((resolve) => {
      chrome.storage.local.get({ [HUNTFLOW_FLOATING_UI_STATE_KEY]: DEFAULT_HUNTFLOW_FLOATING_UI_STATE }, (data) => {
        const s = data[HUNTFLOW_FLOATING_UI_STATE_KEY] || {};
        huntflowFloatingUIState = { ...DEFAULT_HUNTFLOW_FLOATING_UI_STATE, ...s };
        resolve();
      });
    });
  }

  function saveHuntflowFloatingUIState(updates) {
    if (updates && typeof updates === "object") {
      huntflowFloatingUIState = { ...huntflowFloatingUIState, ...updates };
    }
    chrome.storage.local.set({ [HUNTFLOW_FLOATING_UI_STATE_KEY]: { ...huntflowFloatingUIState } });
  }

  function makeHuntflowWidgetDraggable(wrapper) {
    if (!wrapper) return;
    try {
      const saved = localStorage.getItem(STORAGE_KEY_HUNTFLOW_POS);
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
      let top = drag.origTop + dy;
      let left = drag.origLeft + dx;
      const margin = 8;
      const maxTop = window.innerHeight - wrapper.offsetHeight - margin;
      const maxLeft = window.innerWidth - wrapper.offsetWidth - margin;
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
        localStorage.setItem(STORAGE_KEY_HUNTFLOW_POS, JSON.stringify({ top: rect.top, left: rect.left }));
      } catch (_) {}
      drag = null;
    };

    const header = wrapper.querySelector("div:first-child");
    const handle = header || wrapper;
    handle.style.cursor = "move";
    handle.addEventListener("mousedown", start);
    handle.addEventListener("touchstart", start, { passive: true });
  }

  function createHuntflowFloatingWidget() {
    injectHuntflowFloatingThemeStyles();
    const wrapper = document.createElement("div");
    wrapper.setAttribute(ATTR_FLOATING, "1");
    wrapper.className = "hrhelper-huntflow-floating-widget";
    wrapper.style.cssText = `
      position: fixed;
      top: 60px;
      right: 12px;
      z-index: 99999;
      width: 320px;
      max-height: calc(100vh - 168px);
      border-radius: 12px;
      box-shadow: 0 4px 16px rgba(0, 0, 0, 0.15), 0 0 0 1px rgba(0, 0, 0, 0.05);
      padding: 16px;
      backdrop-filter: blur(8px);
      display: flex;
      flex-direction: column;
      overflow: hidden;
    `;
    applyHuntflowFloatingTheme(wrapper);

    const header = document.createElement("div");
    header.className = "hrhelper-hf-header";
    header.style.cssText = "display:flex;align-items:center;justify-content:space-between;gap:8px;padding-bottom:8px;border-bottom:1px solid var(--hrhelper-hf-border,rgba(0,0,0,.08));flex-shrink:0;";
    const title = document.createElement("div");
    title.className = "hrhelper-hf-title";
    title.style.cssText = "font-size:14px;font-weight:600;color:var(--hrhelper-hf-accent,#0a66c2);display:flex;align-items:center;gap:6px;";
    const titleIcon = document.createElement("img");
    titleIcon.src = chrome.runtime.getURL("icons/icon-32.png");
    titleIcon.alt = "";
    titleIcon.width = 20;
    titleIcon.height = 20;
    titleIcon.style.cssText = "flex-shrink:0;display:block;object-fit:contain;";
    titleIcon.onerror = function () {
      const svg = document.createElement("span");
      svg.innerHTML = '<svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor" style="flex-shrink:0;display:block;"><path d="M20 6h-4V4c0-1.11-.89-2-2-2h-4c-1.11 0-2 .89-2 2v2H4c-1.11 0-1.99.89-1.99 2L2 19c0 1.11.89 2 2 2h16c1.11 0 2-.89 2-2V8c0-1.11-.89-2-2-2zm-6 0h-4V4h4v2z"/></svg>';
      titleIcon.replaceWith(svg.firstElementChild || svg);
    };
    title.appendChild(titleIcon);
    title.appendChild(document.createTextNode(" HR Helper"));
    header.appendChild(title);

    const toggleBtn = document.createElement("button");
    toggleBtn.type = "button";
    toggleBtn.className = "hrhelper-huntflow-toggle-btn";
    toggleBtn.title = "Свернуть / развернуть";
    toggleBtn.setAttribute("aria-label", "Свернуть");
    toggleBtn.style.cssText = "width:24px;height:24px;border:none;background:var(--hrhelper-btn-bg,rgba(0,0,0,.05));border-radius:4px;cursor:pointer;color:var(--hrhelper-muted,#666);flex-shrink:0;padding:0;display:flex;align-items:center;justify-content:center;transition:background .15s ease;";
    toggleBtn.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path class="hrhelper-toggle-icon-path" d="M7.41 15.41L12 10.83l4.59 4.58L18 14l-6-6-6 6z"/></svg>';
    toggleBtn.addEventListener("mouseenter", () => { toggleBtn.style.background = "var(--hrhelper-border,rgba(0,0,0,.1))"; });
    toggleBtn.addEventListener("mouseleave", () => { toggleBtn.style.background = "var(--hrhelper-btn-bg,rgba(0,0,0,.05))"; });
    toggleBtn.addEventListener("mousedown", () => { toggleBtn.style.background = "var(--hrhelper-border,rgba(0,0,0,.15))"; });
    toggleBtn.addEventListener("mouseup", () => { toggleBtn.style.background = "var(--hrhelper-border,rgba(0,0,0,.1))"; });
    header.appendChild(toggleBtn);
    wrapper.appendChild(header);

    const body = document.createElement("div");
    body.className = "hrhelper-huntflow-widget-body hrhelper-hf-body";
    body.style.cssText = "display:flex;flex-direction:column;gap:8px;flex:1;min-height:0;overflow-y:auto;";
    wrapper.appendChild(body);

    const isCollapsed = !!huntflowFloatingUIState.widgetCollapsed;
    body.style.display = isCollapsed ? "none" : "flex";
    const togglePath = toggleBtn.querySelector(".hrhelper-toggle-icon-path");
    if (togglePath) togglePath.setAttribute("d", isCollapsed ? "M7.41 8.59L12 13.17l4.59-4.58L18 10l-6 6-6-6z" : "M7.41 15.41L12 10.83l4.59 4.58L18 14l-6-6-6 6z");
    toggleBtn.addEventListener("click", () => {
      const next = body.style.display === "none";
      body.style.display = next ? "flex" : "none";
      const pathEl = toggleBtn.querySelector(".hrhelper-toggle-icon-path");
      if (pathEl) pathEl.setAttribute("d", next ? "M7.41 15.41L12 10.83l4.59 4.58L18 14l-6-6-6 6z" : "M7.41 8.59L12 13.17l4.59-4.58L18 10l-6 6-6-6z");
      toggleBtn.setAttribute("aria-label", next ? "Свернуть" : "Развернуть");
      toggleBtn.title = next ? "Свернуть" : "Развернуть";
      saveHuntflowFloatingUIState({ widgetCollapsed: !next });
    });

    try {
      chrome.storage.onChanged.addListener(function (changes, areaName) {
        if (areaName === "sync" && changes[OPTIONS_THEME_KEY]) applyHuntflowFloatingTheme(wrapper);
      });
    } catch (_) {}

    return { wrapper, body };
  }

  function addCopyRow(body, label, value, title) {
    if (!value) return;
    const row = document.createElement("div");
    row.style.cssText = "display:flex;align-items:center;gap:8px;flex-wrap:nowrap;";
    const text = document.createElement("span");
    text.className = "hrhelper-hf-row-text";
    text.style.cssText = "font-size:12px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;flex:1;min-width:0;";
    text.textContent = value;
    text.title = value;
    const copyBtn = document.createElement("button");
    copyBtn.type = "button";
    copyBtn.className = "hrhelper-hf-copy-btn";
    copyBtn.title = title || "Копировать";
    copyBtn.style.cssText = "display:inline-flex;align-items:center;justify-content:center;width:28px;height:28px;padding:0;border-radius:6px;cursor:pointer;flex-shrink:0;";
    copyBtn.innerHTML = COPY_ICON_SVG;
    copyBtn.addEventListener("click", (e) => {
      e.preventDefault();
      copyToClipboard(value).then(() => {
        copyBtn.classList.add("hrhelper-hf-copy-btn-copied");
        copyBtn.title = "Скопировано";
        setTimeout(() => {
          copyBtn.classList.remove("hrhelper-hf-copy-btn-copied");
          copyBtn.title = title || "Копировать";
        }, 800);
      });
    });
    row.appendChild(text);
    row.appendChild(copyBtn);
    body.appendChild(row);
  }

  function addFioRow(body, fio, copyTitle) {
    if (!fio) return;
    const row = document.createElement("div");
    row.style.cssText = "display:flex;align-items:center;gap:8px;flex-wrap:nowrap;";
    const text = document.createElement("span");
    text.className = "hrhelper-hf-fio-text";
    text.style.cssText = "font-size:16px;font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;flex:1;min-width:0;";
    text.textContent = fio;
    text.title = fio;
    const copyBtn = document.createElement("button");
    copyBtn.type = "button";
    copyBtn.className = "hrhelper-hf-copy-btn";
    copyBtn.title = copyTitle || "Копировать ФИО";
    copyBtn.style.cssText = "display:inline-flex;align-items:center;justify-content:center;width:28px;height:28px;padding:0;border-radius:6px;cursor:pointer;flex-shrink:0;";
    copyBtn.innerHTML = COPY_ICON_SVG;
    copyBtn.addEventListener("click", (e) => {
      e.preventDefault();
      copyToClipboard(fio).then(() => {
        copyBtn.classList.add("hrhelper-hf-copy-btn-copied");
        copyBtn.title = "Скопировано";
        setTimeout(() => {
          copyBtn.classList.remove("hrhelper-hf-copy-btn-copied");
          copyBtn.title = copyTitle || "Копировать ФИО";
        }, 800);
      });
    });
    row.appendChild(text);
    row.appendChild(copyBtn);
    body.appendChild(row);
  }

  const COPY_LINK_ICON_SVG = '<svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor"><path d="M16 1H4c-1.1 0-2 .9-2 2v14h2V3h12V1zm3 4H8c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h11c1.1 0 2-.9 2-2V7c0-1.1-.9-2-2-2zm0 16H8V7h11v14z"/></svg>';

  function formatLastChangeAt(isoStr) {
    if (!isoStr || typeof isoStr !== "string") return "";
    const s = isoStr.trim().replace("Z", "+00:00");
    let d;
    try {
      d = new Date(s);
    } catch (_) {
      return "";
    }
    if (isNaN(d.getTime())) return "";
    const day = String(d.getDate()).padStart(2, "0");
    const month = String(d.getMonth() + 1).padStart(2, "0");
    const year = d.getFullYear();
    return `${day}.${month}.${year}`;
  }

  async function fetchStatusMultiByHuntflowUrl(huntflowUrl) {
    if (!huntflowUrl) return { items: [] };
    const shared = HRH.fetchStatusMulti;
    if (!shared) {
      throw new Error("[HRHelper] shared/api/status.js not loaded (fetchStatusMulti missing)");
    }
    const data = await shared({ huntflowUrl: huntflowUrl });
    if (!data || data.error || data.success === false) return { items: [] };
    return { items: data.items || [] };
  }

  function appendVacanciesSection(body, huntflowUrl) {
    if (!body || !huntflowUrl) return Promise.resolve();
    const sectionTitle = document.createElement("div");
    sectionTitle.className = "hrhelper-hf-section-title";
    sectionTitle.style.cssText = "font-size:12px;font-weight:600;margin-top:12px;margin-bottom:6px;padding-top:10px;border-top:1px solid var(--hrhelper-hf-border,rgba(0,0,0,.08));";
    sectionTitle.textContent = "Вакансии";
    body.appendChild(sectionTitle);

    const container = document.createElement("div");
    container.style.cssText = "display:flex;flex-direction:column;gap:6px;";
    body.appendChild(container);

    return fetchStatusMultiByHuntflowUrl(huntflowUrl).then(({ items }) => {
      if (!items || items.length === 0) {
        const empty = document.createElement("div");
        empty.style.cssText = "font-size:11px;color:var(--hrhelper-hf-muted,#6c757d);";
        empty.textContent = "Нет данных о вакансиях";
        container.appendChild(empty);
        return;
      }
      items.forEach((v) => {
        const isRejected = v.status_type === "rejected";
        const isArchived = v.is_archived;
        const card = document.createElement("div");
        card.className = "hrhelper-hf-vacancy-card" + (isRejected ? " hrhelper-hf-vacancy-card-rejected" : "") + (isArchived ? " hrhelper-hf-vacancy-card-archived" : "");
        
        const labelWrap = document.createElement("div");
        labelWrap.style.cssText = "flex:1;min-width:0;display:flex;flex-direction:column;gap:2px;";
        
        // Первая строка: название вакансии (+ статус рядом, если отказ)
        const line1 = document.createElement("div");
        line1.className = "hrhelper-hf-vacancy-line1";
        let mainText = v.vacancy_name || "—";
        if (isRejected && v.status_name) {
          mainText += " · " + v.status_name;
        }
        line1.textContent = mainText;
        line1.title = mainText;
        labelWrap.appendChild(line1);
        
        // Вторая строка: статус (если не отказ) или причина отказа (если отказ)
        const line2 = document.createElement("div");
        line2.className = "hrhelper-hf-vacancy-line2";
        if (isRejected) {
          const reason = (v.rejection_reason_name || "").trim();
          if (reason) {
            line2.textContent = reason;
            labelWrap.appendChild(line2);
          }
        } else if (v.status_name) {
          line2.textContent = v.status_name;
          labelWrap.appendChild(line2);
        }
        
        // Кнопка копирования с датой под ней
        const copyWrap = document.createElement("div");
        copyWrap.style.cssText = "display:flex;flex-direction:column;align-items:center;gap:2px;flex-shrink:0;";
        
        const copyBtn = document.createElement("button");
        copyBtn.type = "button";
        copyBtn.className = "hrhelper-hf-copy-btn";
        copyBtn.title = "Копировать ссылку на вакансию";
        copyBtn.style.cssText = "display:inline-flex;align-items:center;justify-content:center;width:28px;height:28px;padding:0;border-radius:6px;cursor:pointer;";
        copyBtn.innerHTML = COPY_LINK_ICON_SVG;
        const url = (v.appurl || "").trim();
        copyBtn.disabled = !url;
        if (url) {
          copyBtn.addEventListener("click", (e) => {
            e.preventDefault();
            copyToClipboard(url).then(() => {
              copyBtn.classList.add("hrhelper-hf-copy-btn-copied");
              copyBtn.title = "Скопировано";
              setTimeout(() => {
                copyBtn.classList.remove("hrhelper-hf-copy-btn-copied");
                copyBtn.title = "Копировать ссылку на вакансию";
              }, 800);
            });
          });
        }
        copyWrap.appendChild(copyBtn);
        
        // Дата под кнопкой
        const dateStr = formatLastChangeAt(v.last_change_at);
        if (dateStr) {
          const dateEl = document.createElement("div");
          dateEl.style.cssText = "font-size:9px;color:var(--hrhelper-hf-muted,#6c757d);white-space:nowrap;";
          dateEl.textContent = dateStr;
          copyWrap.appendChild(dateEl);
        }
        
        card.appendChild(labelWrap);
        card.appendChild(copyWrap);
        container.appendChild(card);
      });
    });
  }

  let injectButtonsLock = false;
  async function injectButtons(retryCount = 0) {
    if (!isApplicantPage()) return;
    const huntflowUrl = getHuntflowUrl();
    if (!huntflowUrl) return;
    if (injectButtonsLock) return;
    injectButtonsLock = true;

    let links = await fetchCandidateLinks(huntflowUrl);
    const phone = getPhoneFromPage();
    const pageTg = getTelegramFromPage();
    const hasTg = links.some((l) => detectLinkType(l.url, l.type) === "telegram");
    if (pageTg && !hasTg) {
      const username = extractUsernameFromUrl(pageTg, "telegram");
      links = [{ type: "telegram", url: pageTg, label: "Telegram", username }].concat(links);
    }

    const fio = getFioFromPage();
    const email = getEmailFromPage();
    const hasAnyContent = links.length > 0 || phone || fio || email;
    if (!hasAnyContent) {
      const existing = document.querySelector(`[${ATTR_FLOATING}="1"]`);
      if (existing) existing.remove();
      injectButtonsLock = false;
      return;
    }

    const hidden = await new Promise((resolve) => {
      chrome.storage.local.get({ [HUNTFLOW_FLOATING_HIDDEN_KEY]: false }, (data) => {
        resolve(!!data[HUNTFLOW_FLOATING_HIDDEN_KEY]);
      });
    });
    if (hidden) {
      const existing = document.querySelector(`[${ATTR_FLOATING}="1"]`);
      if (existing) existing.remove();
      injectButtonsLock = false;
      return;
    }

    let widgetEl = document.querySelector(`[${ATTR_FLOATING}="1"]`);
    let body;
    if (!widgetEl) {
      await loadHuntflowFloatingUIState();
      var resolvedTheme = await getResolvedHuntflowTheme();
      const created = createHuntflowFloatingWidget();
      widgetEl = created.wrapper;
      body = created.body;
      if (resolvedTheme === "dark") widgetEl.classList.add("hrhelper-theme-dark");
      else widgetEl.classList.remove("hrhelper-theme-dark");
      document.body.appendChild(widgetEl);
      applyHuntflowFloatingTheme(widgetEl);
      makeHuntflowWidgetDraggable(widgetEl);
    } else {
      body = widgetEl.querySelector(".hrhelper-huntflow-widget-body");
      applyHuntflowFloatingTheme(widgetEl);
    }
    if (!body) {
      injectButtonsLock = false;
      return;
    }

    body.innerHTML = "";
    addFioRow(body, fio, "Копировать ФИО");
    addCopyRow(body, "Телефон", phone || null, "Копировать номер");
    addCopyRow(body, "Email", email, "Копировать email");

    const buttonsWrap = createButtonsContainer(links, phone);
    if (buttonsWrap) {
      buttonsWrap.style.marginTop = "8px";
      buttonsWrap.style.paddingTop = "8px";
      buttonsWrap.style.borderTop = "1px solid rgba(0,0,0,.08)";
      body.appendChild(buttonsWrap);
    }

    await appendVacanciesSection(body, huntflowUrl);

    injectButtonsLock = false;
    log("Floating widget updated:", links.length);
  }

  function run() {
    if (!isApplicantPage()) {
      document.querySelectorAll(`[${ATTR}="1"]`).forEach((el) => el.remove());
      document.querySelectorAll(`[${ATTR_FLOATING}="1"]`).forEach((el) => el.remove());
      lastRunApplicantId = null;
      return;
    }
    lastRunApplicantId = extractApplicantId(getHuntflowUrl());
    try {
      injectButtons();
    } catch (e) {
      console.warn("[HRHelper Huntflow] injectButtons:", e);
    }
  }

  let debounceTimer = 0;
  let lastRunApplicantId = null;
  const floatingWidgetRoot = () => document.querySelector(`[${ATTR_FLOATING}="1"]`);

  const observer = new MutationObserver((mutations) => {
    if (!isApplicantPage()) return;
    if (!findApplicantInfo()) return;
    const root = floatingWidgetRoot();
    const isMutationInsideOurWidget = (node) => root && node && root.contains(node);
    const affectedByUs = mutations.some((m) => {
      if (isMutationInsideOurWidget(m.target)) return true;
      for (let i = 0; i < m.addedNodes.length; i++) {
        if (isMutationInsideOurWidget(m.addedNodes[i])) return true;
      }
      return false;
    });
    if (affectedByUs) return;
    const applicantId = extractApplicantId(getHuntflowUrl());
    if (applicantId === lastRunApplicantId) return;
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => {
      lastRunApplicantId = extractApplicantId(getHuntflowUrl());
      run();
    }, 500);
  });

  function scheduleRunsOnNavigation() {
    [150, 600, 1200].forEach((ms) => setTimeout(run, ms));
  }

  function init() {
    chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
      if (msg && msg.action === "setHuntflowFloatingVisible") {
        const visible = msg.visible === true;
        chrome.storage.local.set({ [HUNTFLOW_FLOATING_HIDDEN_KEY]: !visible }, () => {
          const widget = document.querySelector(`[${ATTR_FLOATING}="1"]`);
          if (widget) {
            widget.style.display = visible ? "" : "none";
          } else if (visible) {
            injectButtons();
          }
          sendResponse({ success: true });
        });
        return true;
      }
    });

    if (!isApplicantPage()) {
      document.querySelectorAll(`[${ATTR}="1"]`).forEach((el) => el.remove());
      document.querySelectorAll(`[${ATTR_FLOATING}="1"]`).forEach((el) => el.remove());
      return;
    }
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", run);
    } else {
      run();
    }
    [800, 1800].forEach((ms) => setTimeout(run, ms));
    if (document.body) {
      observer.observe(document.body, { childList: true, subtree: true });
    }
    window.addEventListener("popstate", scheduleRunsOnNavigation);
    window.addEventListener("hashchange", scheduleRunsOnNavigation);
    const origPush = history.pushState;
    const origReplace = history.replaceState;
    if (origPush) {
      history.pushState = function (...args) {
        origPush.apply(this, args);
        scheduleRunsOnNavigation();
      };
    }
    if (origReplace) {
      history.replaceState = function (...args) {
        origReplace.apply(this, args);
        scheduleRunsOnNavigation();
      };
    }
  }

  init();
})();
