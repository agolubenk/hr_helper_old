const HRH = window.__HRH__;
if (!HRH) {
  throw new Error("[HRHelper] shared/constants.js not loaded");
}
const DEFAULTS = HRH.DEFAULTS;
if (!DEFAULTS) {
  throw new Error("[HRHelper] shared/constants.js not loaded (DEFAULTS missing)");
}
const debounce = HRH.debounce;
const TIMING = HRH.TIMING || {};

const FLOATING_UI_STATE_KEY = "hrhelper_linkedin_floating_ui_state";
const LINKEDIN_FLOATING_HIDDEN_KEY = "hrhelper_linkedin_floating_hidden";
const DEFAULT_FLOATING_UI_STATE = { widgetCollapsed: false, candidateDataOpen: true, extraFieldsOpen: true, commentsOpen: true };
let floatingWidgetUIState = { ...DEFAULT_FLOATING_UI_STATE };

function loadFloatingUIState(cb) {
  try {
    chrome.storage.local.get({ [FLOATING_UI_STATE_KEY]: DEFAULT_FLOATING_UI_STATE }, (data) => {
      const s = data[FLOATING_UI_STATE_KEY] || {};
      floatingWidgetUIState = { ...DEFAULT_FLOATING_UI_STATE, ...s };
      if (typeof cb === "function") cb(floatingWidgetUIState);
    });
  } catch (e) {
    if (typeof cb === "function") cb(floatingWidgetUIState);
  }
}

function saveFloatingUIState(update) {
  Object.assign(floatingWidgetUIState, update);
  try {
    chrome.storage.local.set({ [FLOATING_UI_STATE_KEY]: { ...floatingWidgetUIState } });
  } catch (_) {}
}

// Debug mode - установи в false для production
const DEBUG = false;
// Для Google Calendar и Google Meet всегда включаем логирование
const IS_GOOGLE_CALENDAR = location.href.includes('calendar.google.com');
const IS_GOOGLE_MEET = location.href.includes('meet.google.com');
const log = (...args) => (DEBUG || IS_GOOGLE_CALENDAR || IS_GOOGLE_MEET) && console.log('[HRHelper]', ...args);
const warn = (...args) => (DEBUG || IS_GOOGLE_CALENDAR || IS_GOOGLE_MEET) && console.warn('[HRHelper]', ...args);
function logError(...args) {
  const serialized = args.map(a => (a && typeof a === 'object' && !(a instanceof Error)) ? JSON.stringify(a) : a);
  console.error('[HRHelper]', ...serialized);
}

function makeWidgetDraggable(wrapper, storageKey, headerSelector) {
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
      localStorage.setItem(storageKey, JSON.stringify({ top: rect.top, left: rect.left }));
    } catch (_) {}
    drag = null;
  };

  const handle = headerSelector ? (wrapper.querySelector(headerSelector) || wrapper) : wrapper;
  handle.style.cursor = "move";
  handle.addEventListener("mousedown", start);
  handle.addEventListener("touchstart", start, { passive: true });
}

const MAX_WIDGETS = 2;
const IS_MESSAGING_PAGE = location.href.includes('/messaging/');
const IS_PROFILE_PAGE = location.href.includes('/in/') && !location.href.includes('/search/');
const IS_LINKEDIN = IS_PROFILE_PAGE || IS_MESSAGING_PAGE;
const THROTTLE_MS = IS_MESSAGING_PAGE ? 500 : 1500; // Messaging быстрее, профиль медленнее

const STATE = {
  lastProfileUrl: null,
  lastThreadId: null, // Отслеживаем thread ID для messaging страницы
  buttons: new Map(),
  current: {
    mode: "idle",
    appUrl: null,
    text: "Huntflow",
    title: "",
    color: "#0a66c2",
    disabled: false,
    show: false,
    inputValue: "",
    originalAppUrl: null, // Сохраняем оригинальный URL перед редактированием
    statusName: null, // Название статуса для отображения в кнопке статуса
    vacancy_name: null,
    vacanciesCount: 0,
  },
  busy: false,
  suppressObserver: false,
  scheduled: false,
  lastScanAt: 0,
  apiCallsThisProfile: 0,
  statusFetchedFor: null,
  statusInFlight: null,
  messagingProfileCache: null, // Кэш для профиля на messaging-странице
  statusCache: new Map(), // Кэш статусов профилей (linkedin_url -> {status, timestamp})
  CACHE_TTL: 2 * 60 * 1000, // 2 минуты (уменьшено для более частого обновления статуса)
  // Данные для попапа на Google Meet (Scorecard, контакт, копирование уровня, фраза-напоминание)
  meet: { scorecardLink: null, communicationLink: null, communicationLabel: null, level: null, vacancyName: null, reminderPhrase: null },
  linkedinFull: {
    vacancies: [],
    candidateInfo: null,
    selectedVacancyId: null,
    defaultVacancyId: null,
    last_comment_datetime: null,
    rejection_reason_name: null,
    isProfileEmployee: false,
    isProfileEmployeeCurrentUser: false,
  },
};

const linkedinMessaging = HRH.linkedinMessaging;
const linkedinProfile = HRH.linkedinProfile;
if (!linkedinMessaging || !linkedinProfile) throw new Error("[HRHelper] modules linkedin-profile.js and linkedin-messaging.js must be loaded before content.js");
const extractThreadIdFromMessageButton = () => linkedinMessaging.extractThreadIdFromMessageButton();
const saveThreadMappingToBackend = (t, u) => linkedinMessaging.saveThreadMappingToBackend(t, u);
const captureProfileToThreadMapping = () => linkedinMessaging.captureProfileToThreadMapping();
const getProfileLinkFromMessaging = () => linkedinMessaging.getProfileLinkFromMessaging(STATE);
const findMessagingComposer = () => linkedinMessaging.findMessagingComposer();
const findAllMoreButtons = () => linkedinProfile.findAllMoreButtons();
const looksLikeProfileActionArea = (btn) => linkedinProfile.looksLikeProfileActionArea(btn);
const findActionContainer = () => linkedinProfile.findActionContainer();
const findActivitySection = () => linkedinProfile.findActivitySection();
const findCoverContainer = () => linkedinProfile.findCoverContainer();
const COVER_SELECTORS = linkedinProfile.COVER_SELECTORS;

const normalizeLinkedInProfileUrl = HRH.normalizeLinkedInProfileUrl;
if (!normalizeLinkedInProfileUrl) {
  throw new Error("[HRHelper] shared/utils/url.js not loaded (normalizeLinkedInProfileUrl missing)");
}

const isExtensionContextValid = HRH.isExtensionContextValid;
if (!isExtensionContextValid) {
  throw new Error("[HRHelper] shared/api/client.js not loaded (isExtensionContextValid missing)");
}

async function getConfig() {
  if (!isExtensionContextValid()) {
    return { baseUrl: (DEFAULTS.baseUrl || '').replace(/\/+$/, '') };
  }
  try {
    if (!chrome.storage?.sync) {
      return { baseUrl: (DEFAULTS.baseUrl || '').replace(/\/+$/, '') };
    }
    const cfg = await chrome.storage.sync.get(DEFAULTS);
    return { baseUrl: (cfg.baseUrl || DEFAULTS.baseUrl).replace(/\/+$/, '') };
  } catch (err) {
    if (err.message && (err.message.includes('Extension context invalidated') || err.message.includes("reading 'sync'"))) {
      return { baseUrl: (DEFAULTS.baseUrl || '').replace(/\/+$/, '') };
    }
    throw err;
  }
}

/** Ответ попапу: данные текущей страницы для контекстного блока (LinkedIn / Calendar / Meet). */
function getPageContext() {
  const pageUrl = location.href;
  if (IS_GOOGLE_CALENDAR) {
    const titleEl = document.querySelector('[data-event-title]') || document.querySelector('h1');
    return { url: true, pageUrl, eventTitle: titleEl ? titleEl.textContent.trim().slice(0, 80) : null };
  }
  if (IS_GOOGLE_MEET) {
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
  const profileUrl = normalizeLinkedInProfileUrl(pageUrl) || (STATE.messagingProfileCache || STATE.lastProfileUrl);
  const huntflowUrl = STATE.current && STATE.current.appUrl ? STATE.current.appUrl : undefined;
  return { url: true, pageUrl, profileUrl: profileUrl || undefined, huntflowUrl };
}

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg && msg.action === 'getPageContext') {
    try {
      sendResponse(getPageContext());
    } catch (e) {
      sendResponse({ url: false });
    }
    return true;
  }
  if (msg && msg.action === 'copyLevelText') {
    const { level, vacancyName } = STATE.meet;
    if (!level || !IS_GOOGLE_MEET) {
      sendResponse({ success: false });
      return true;
    }
    const q = new URLSearchParams({ level });
    if (vacancyName) q.set('vacancy_name', vacancyName);
    chrome.runtime.sendMessage(
      { type: 'HRHELPER_API', payload: { path: `/api/v1/huntflow/linkedin-applicants/level-text/?${q.toString()}`, method: 'GET' } },
      (apiRes) => {
        try {
          if (!apiRes || !apiRes.ok) {
            sendResponse({ success: false });
            return;
          }
          const data = apiRes.json;
          if (data && data.success && data.text) {
            sendResponse({ success: true, text: data.text });
          } else {
            sendResponse({ success: false });
          }
        } catch (_) {
          sendResponse({ success: false });
        }
      }
    );
    return true;
  }
  if (msg && msg.action === 'setMeetReminderVisible' && IS_GOOGLE_MEET) {
    const visible = msg.visible === true;
    chrome.storage.local.set({ hrhelper_meet_reminder_hidden: !visible }, () => {
      const block = document.getElementById('hrhelper-reminder-block');
      if (block) block.style.display = visible ? '' : 'none';
      else if (visible && STATE.meet.reminderPhrase) injectReminderBlock(STATE.meet.reminderPhrase);
      sendResponse({ success: true });
    });
    return true;
  }
  if (msg && msg.action === "setLinkedInFloatingVisible" && IS_LINKEDIN) {
    const visible = msg.visible === true;
    chrome.storage.local.set({ [LINKEDIN_FLOATING_HIDDEN_KEY]: !visible }, () => {
      const w = document.querySelector("[data-hrhelper-floating='true']");
      if (w) {
        w.style.display = visible ? "" : "none";
      } else if (visible) {
        insertFloatingWidget();
      }
      sendResponse({ success: true });
    });
    return true;
  }
});


function pluralize(n, one, few, many) {
  n = Math.abs(n) % 100;
  const n1 = n % 10;
  if (n > 10 && n < 20) return many;
  if (n1 > 1 && n1 < 5) return few;
  if (n1 === 1) return one;
  return many;
}

let floatingWidgetData = null;
let floatingEditEscHandler = null;

function removeFloatingEditEscHandler() {
  if (floatingEditEscHandler) {
    document.removeEventListener("keydown", floatingEditEscHandler);
    floatingEditEscHandler = null;
  }
}

const isNewStatusName = HRH.isNewStatusName;
const hasBlacklistLabel = HRH.hasBlacklistLabel;
if (!isNewStatusName || !hasBlacklistLabel) {
  throw new Error("[HRHelper] shared/domain/status-logic.js not loaded (isNewStatusName/hasBlacklistLabel missing)");
}

function getPrimaryVacancyForBorder(vacancies) {
  const items = Array.isArray(vacancies) ? vacancies : [];
  const selId = STATE.linkedinFull.selectedVacancyId ?? STATE.linkedinFull.defaultVacancyId;
  const bySel = selId != null ? items.find((v) => v && v.vacancy_id === selId) : null;
  if (bySel) return bySel;
  const active = items.find((v) => v && !v.is_hired && !v.is_archived && v.status_type !== "rejected");
  return active || items[0] || null;
}

/** Единственное исключение среди отказов: причина «Закрыли вакансию другим» — рамка синяя. */
function isRejectionReasonClosedByOther(reasonName) {
  const n = (reasonName || "").trim().toLowerCase().replace(/ё/g, "е");
  return n.includes("закрыли") && n.includes("вакансию") && n.includes("другим");
}

function computeFloatingBorderColorLinkedIn() {
  const info = STATE.linkedinFull.candidateInfo;
  if (hasBlacklistLabel(info)) return "#111"; // чёрный — всегда, вне зависимости от статуса и состояния

  // “Кандидат в базе” для LinkedIn: есть сохранённая ссылка / вакансии / открытый режим
  const inBase = (STATE.current.mode === "open" && !!STATE.current.appUrl) || (STATE.linkedinFull.vacancies || []).length > 0;
  if (!inBase) return null;

  const primary = getPrimaryVacancyForBorder(STATE.linkedinFull.vacancies || []);
  return computeBorderColorForVacancy(primary);
}

/** Цвет рамки для одной вакансии (та же логика, что для всего плавающего окна). */
function computeBorderColorForVacancy(v) {
  if (!v) return null;
  const statusType = v.status_type;
  const statusName = v.status_name || "";

  if (statusType === "rejected") {
    if (isRejectionReasonClosedByOther(v.rejection_reason_name)) return "#0a66c2";
    const ts = v.last_change_at || v.last_comment_at || null;
    const dt = ts ? new Date(ts) : null;
    const ms = dt && !isNaN(dt.getTime()) ? (Date.now() - dt.getTime()) : null;
    const halfYearMs = 183 * 24 * 60 * 60 * 1000;
    if (ms != null && ms < halfYearMs) return "#dc3545";
    return "#fd7e14";
  }
  if (!isNewStatusName(statusName)) return "#198754";
  return "#0a66c2";
}

const hexToRgba = HRH.hexToRgba;
if (!hexToRgba) {
  throw new Error("[HRHelper] shared/utils/color.js not loaded (hexToRgba missing)");
}

function applyFloatingBorder(wrapper, color) {
  if (!wrapper) return;
  if (!wrapper.dataset.hrhelperBaseBoxShadow) {
    wrapper.dataset.hrhelperBaseBoxShadow = wrapper.style.boxShadow || "";
  }
  const base = wrapper.dataset.hrhelperBaseBoxShadow || "";
  if (!color) {
    wrapper.style.boxShadow = base;
    return;
  }
  const shadowColor = hexToRgba(color, 0.28);
  wrapper.style.boxShadow = `0 0 0 2px ${color} inset, 0 4px 14px -2px ${shadowColor}, ${base}`;
}

/**
 * Определяет, что страница в тёмной теме.
 * При режиме «автоматически»: сначала тема сайта (LinkedIn), если не удалось — тема браузера (prefers-color-scheme).
 */
function isPageDarkMode() {
  if (typeof window === "undefined") return false;
  const html = document.documentElement;
  const theme = (html.getAttribute("data-theme") || html.getAttribute("data-mode") || "").toLowerCase();
  if (theme === "dark" || theme === "dark-mode") return true;
  if (theme === "light" || theme === "light-mode") return false;
  if (html.classList.contains("artdeco-dark-mode") || html.classList.contains("theme-dark") || html.classList.contains("dark")) return true;
  if (html.classList.contains("artdeco-light-mode") || html.classList.contains("theme-light") || html.classList.contains("light")) return false;
  try {
    const bg = getComputedStyle(document.body).backgroundColor;
    const m = bg.match(/rgba?\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)/);
    if (m) {
      const r = parseInt(m[1], 10), g = parseInt(m[2], 10), b = parseInt(m[3], 10);
      const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
      if (luminance < 0.4) return true;
      if (luminance > 0.6) return false;
    }
  } catch (_) {}
  if (window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches) return true;
  return false;
}

/** Ключ темы в настройках и текущая разрешённая тема виджетов (light | dark) */
const OPTIONS_THEME_KEY = HRH.OPTIONS_THEME_KEY;
if (!OPTIONS_THEME_KEY) {
  throw new Error("[HRHelper] shared/constants.js not loaded (OPTIONS_THEME_KEY missing)");
}
let resolvedWidgetTheme = "light";

/** Возвращает разрешённую тему виджетов: из настроек или system = по странице. */
function getResolvedWidgetTheme() {
  return new Promise((resolve) => {
    try {
      chrome.storage.sync.get({ [OPTIONS_THEME_KEY]: "system" }, (data) => {
        const theme = data[OPTIONS_THEME_KEY] || "system";
        if (theme === "light") { resolve("light"); return; }
        if (theme === "dark") { resolve("dark"); return; }
        resolve(isPageDarkMode() ? "dark" : "light");
      });
    } catch (_) {
      resolve(isPageDarkMode() ? "dark" : "light");
    }
  });
}

/** Обновляет кэш разрешённой темы и применяет ко всем виджетам. */
async function updateResolvedWidgetTheme() {
  resolvedWidgetTheme = await getResolvedWidgetTheme();
  document.querySelectorAll(".hrhelper-floating-widget").forEach(applyFloatingWidgetTheme);
  document.querySelectorAll(".hrhelper-messaging-bar").forEach(applyMessagingBarTheme);
}

function injectFloatingWidgetThemeStyles() {
  if (document.getElementById("hrhelper-floating-theme")) return;
  const style = document.createElement("style");
  style.id = "hrhelper-floating-theme";
  style.textContent = `
    .hrhelper-floating-widget {
      background: var(--hrhelper-bg) !important;
      color: var(--hrhelper-text) !important;
    }
    .hrhelper-floating-widget .hrhelper-widget-header { border-bottom-color: var(--hrhelper-border) !important; }
    .hrhelper-floating-widget .hrhelper-widget-title { color: var(--hrhelper-accent) !important; }
    .hrhelper-floating-widget .hrhelper-widget-title-text { color: inherit; }
    .hrhelper-floating-widget .hrhelper-toggle-btn { background: var(--hrhelper-btn-bg) !important; color: var(--hrhelper-muted) !important; transition: background .15s ease !important; }
    .hrhelper-floating-widget .hrhelper-toggle-btn:hover { background: var(--hrhelper-border) !important; }
    .hrhelper-floating-widget .hrhelper-toggle-btn:active { background: rgba(0,0,0,.15) !important; }
    .hrhelper-floating-widget.hrhelper-theme-dark .hrhelper-toggle-btn:active { background: rgba(255,255,255,.15) !important; }
    .hrhelper-floating-widget .hrhelper-floating-action-group button { transition: background .15s ease, opacity .15s ease !important; }
    .hrhelper-floating-widget .hrhelper-floating-action-group button:hover { background: var(--hrhelper-border) !important; }
    .hrhelper-floating-widget .hrhelper-floating-action-group button:active { background: rgba(0,0,0,.15) !important; }
    .hrhelper-floating-widget.hrhelper-theme-dark .hrhelper-floating-action-group button:active { background: rgba(255,255,255,.15) !important; }
    .hrhelper-floating-widget .hrhelper-floating-copy-btn.hrhelper-copy-btn-copied { background: var(--hrhelper-success-bg) !important; border-color: var(--hrhelper-success-border) !important; color: var(--hrhelper-success) !important; }
    .hrhelper-floating-widget .hrhelper-status-dropdown,
    .hrhelper-floating-widget .hrhelper-add-vacancy-dropdown { background: var(--hrhelper-bg) !important; border-color: var(--hrhelper-border) !important; }
    .hrhelper-floating-widget input { background: var(--hrhelper-input-bg) !important; color: var(--hrhelper-text) !important; border-color: var(--hrhelper-border) !important; }
    .hrhelper-floating-widget .hrhelper-widget-body,
    .hrhelper-floating-widget .hrhelper-widget-body * { color: var(--hrhelper-text) !important; }
    .hrhelper-floating-widget .hrhelper-widget-body .hrhelper-body-muted { color: var(--hrhelper-muted) !important; }
    .hrhelper-floating-widget .hrhelper-widget-body .hrhelper-body-accent { color: var(--hrhelper-accent) !important; }
    .hrhelper-floating-widget .hrhelper-widget-body .hrhelper-body-danger { color: var(--hrhelper-danger) !important; }
    .hrhelper-floating-widget .hrhelper-widget-body .hrhelper-body-success { color: var(--hrhelper-success) !important; }
    .hrhelper-floating-widget .hrhelper-ctx-status-block { border-top-color: var(--hrhelper-border) !important; }
    .hrhelper-floating-widget .hrhelper-ctx-label { color: var(--hrhelper-accent) !important; }
    .hrhelper-floating-widget select { background: var(--hrhelper-input-bg) !important; color: var(--hrhelper-text) !important; border-color: var(--hrhelper-border) !important; }
    .hrhelper-floating-widget .hrhelper-ctx-comment-wrap { background: var(--hrhelper-input-bg) !important; border-color: var(--hrhelper-border) !important; }
    .hrhelper-floating-widget .hrhelper-ctx-comment-toolbar { background: var(--hrhelper-btn-bg) !important; border-bottom-color: var(--hrhelper-border) !important; }
    .hrhelper-floating-widget .hrhelper-ctx-comment-editor { background: var(--hrhelper-input-bg) !important; color: var(--hrhelper-text) !important; }
    .hrhelper-floating-widget .hrhelper-ctx-status-block button:not(.hrhelper-toggle-btn) { background: var(--hrhelper-input-bg) !important; color: var(--hrhelper-accent) !important; border-color: var(--hrhelper-border) !important; }
    .hrhelper-floating-widget .hrhelper-ctx-comment-toolbar .hrhelper-ctx-comment-toolbar-btn,
    .hrhelper-floating-widget .hrhelper-ctx-apply-status { background: var(--hrhelper-input-bg) !important; color: var(--hrhelper-text) !important; border-color: var(--hrhelper-border) !important; }
    .hrhelper-floating-widget .hrhelper-ctx-comment-toolbar .hrhelper-ctx-comment-toolbar-btn *,
    .hrhelper-floating-widget .hrhelper-ctx-comment-toolbar .hrhelper-ctx-comment-toolbar-btn svg,
    .hrhelper-floating-widget .hrhelper-ctx-apply-status * { color: inherit !important; fill: currentColor !important; }
    .hrhelper-floating-widget .hrhelper-status-dropdown,
    .hrhelper-floating-widget .hrhelper-add-vacancy-dropdown { color: var(--hrhelper-text) !important; }
    .hrhelper-floating-widget .hrhelper-status-dropdown *,
    .hrhelper-floating-widget .hrhelper-add-vacancy-dropdown * { color: inherit; }
    .hrhelper-floating-widget .hrhelper-dropdown-msg { color: var(--hrhelper-muted); padding: 12px; }
    .hrhelper-floating-widget .hrhelper-dropdown-err { color: var(--hrhelper-danger); padding: 12px; }
    .hrhelper-add-vacancy-dropdown.hrhelper-theme-dark,
    .hrhelper-status-dropdown.hrhelper-theme-dark {
      background: #161b22 !important; color: #e6edf3 !important; border-color: rgba(255,255,255,.12) !important;
    }
    .hrhelper-add-vacancy-dropdown.hrhelper-theme-dark .hrhelper-dropdown-msg,
    .hrhelper-status-dropdown.hrhelper-theme-dark .hrhelper-dropdown-msg { color: #8b949e !important; }
    .hrhelper-add-vacancy-dropdown.hrhelper-theme-dark .hrhelper-dropdown-err,
    .hrhelper-status-dropdown.hrhelper-theme-dark .hrhelper-dropdown-err { color: #f85149 !important; }
    .hrhelper-add-vacancy-dropdown.hrhelper-theme-dark > div,
    .hrhelper-status-dropdown.hrhelper-theme-dark > div { color: inherit; }
    :root { --hrhelper-bg: rgba(255,255,255,.98); --hrhelper-text: #212529; --hrhelper-muted: #6c757d; --hrhelper-border: rgba(0,0,0,.08); --hrhelper-accent: #0a66c2; --hrhelper-btn-bg: rgba(0,0,0,.05); --hrhelper-input-bg: #fff; --hrhelper-danger: #842029; --hrhelper-danger-bg: #f8d7da; --hrhelper-danger-border: #f1aeb5; --hrhelper-success: #0f5132; --hrhelper-success-bg: #d1e7dd; --hrhelper-success-border: #a3cfbb; --hrhelper-card-border: #b6d4fe; --hrhelper-card-bg: #f0f7ff; --hrhelper-card-sel-border: #0a66c2; --hrhelper-card-sel-bg: #e7f1ff; }
    @media (prefers-color-scheme: dark) {
      :root { --hrhelper-bg: #161b22; --hrhelper-text: #e6edf3; --hrhelper-muted: #8b949e; --hrhelper-border: rgba(255,255,255,.12); --hrhelper-accent: #58a6ff; --hrhelper-btn-bg: rgba(255,255,255,.08); --hrhelper-input-bg: #0d1117; --hrhelper-danger: #f85149; --hrhelper-danger-bg: rgba(248,81,73,.15); --hrhelper-danger-border: rgba(248,81,73,.4); --hrhelper-success: #3fb950; --hrhelper-success-bg: rgba(63,185,80,.15); --hrhelper-success-border: rgba(63,185,80,.4); --hrhelper-card-border: rgba(88,166,255,.35); --hrhelper-card-bg: rgba(88,166,255,.08); --hrhelper-card-sel-border: #58a6ff; --hrhelper-card-sel-bg: rgba(88,166,255,.18); }
    }
    .hrhelper-floating-widget.hrhelper-theme-dark {
      --hrhelper-bg: #161b22; --hrhelper-text: #e6edf3; --hrhelper-muted: #8b949e; --hrhelper-border: rgba(255,255,255,.12); --hrhelper-accent: #58a6ff; --hrhelper-btn-bg: rgba(255,255,255,.08); --hrhelper-input-bg: #0d1117; --hrhelper-danger: #f85149; --hrhelper-danger-bg: rgba(248,81,73,.15); --hrhelper-danger-border: rgba(248,81,73,.4); --hrhelper-success: #3fb950; --hrhelper-success-bg: rgba(63,185,80,.15); --hrhelper-success-border: rgba(63,185,80,.4); --hrhelper-card-border: rgba(88,166,255,.35); --hrhelper-card-bg: rgba(88,166,255,.08); --hrhelper-card-sel-border: #58a6ff; --hrhelper-card-sel-bg: rgba(88,166,255,.18);
    }
    .hrhelper-floating-widget.hrhelper-theme-dark .hrhelper-floating-action-group button,
    .hrhelper-floating-widget.hrhelper-theme-dark .hrhelper-floating-copy-btn { background: var(--hrhelper-btn-bg) !important; color: var(--hrhelper-muted) !important; border-color: var(--hrhelper-border) !important; }
    .hrhelper-messaging-bar {
      background: var(--hrhelper-bg, #f3f6f8) !important;
      border-bottom-color: var(--hrhelper-border, rgba(0,0,0,.08)) !important;
    }
    .hrhelper-messaging-bar.hrhelper-theme-dark {
      --hrhelper-bg: #161b22; --hrhelper-text: #e6edf3; --hrhelper-border: rgba(255,255,255,.12); --hrhelper-accent: #58a6ff; --hrhelper-btn-bg: rgba(255,255,255,.08); --hrhelper-input-bg: #0d1117; --hrhelper-danger: #f85149;
    }
    .hrhelper-messaging-bar.hrhelper-theme-dark .hrhelper-action-btn {
      background: var(--hrhelper-accent) !important; color: #fff !important; border-color: var(--hrhelper-border) !important;
    }
    .hrhelper-messaging-bar.hrhelper-theme-dark .hrhelper-copy-btn {
      background: #17a2b8 !important; color: #fff !important; border-color: var(--hrhelper-border) !important;
    }
    .hrhelper-messaging-bar.hrhelper-theme-dark .hrhelper-edit-btn {
      background: #6c757d !important; color: #fff !important; border-color: var(--hrhelper-border) !important;
    }
    .hrhelper-messaging-bar.hrhelper-theme-dark .hrhelper-status-btn {
      background: var(--hrhelper-danger) !important; color: #fff !important; border-color: var(--hrhelper-border) !important;
    }
    .hrhelper-messaging-bar.hrhelper-theme-dark .hrhelper-add-vacancy-btn {
      background: var(--hrhelper-accent) !important; color: #fff !important; border-color: var(--hrhelper-border) !important;
    }
    .hrhelper-messaging-bar.hrhelper-theme-dark .hrhelper-input,
    .hrhelper-messaging-bar.hrhelper-theme-dark input.hrhelper-input {
      background: var(--hrhelper-input-bg) !important; color: var(--hrhelper-text) !important; border-color: var(--hrhelper-border) !important;
    }
    .hrhelper-messaging-bar.hrhelper-theme-dark .hrhelper-save-btn {
      background: var(--hrhelper-accent) !important; color: #fff !important; border-color: var(--hrhelper-border) !important;
    }
    .hrhelper-messaging-bar.hrhelper-theme-dark .hrhelper-cancel-btn {
      background: #6c757d !important; color: #fff !important; border-color: var(--hrhelper-border) !important;
    }
    .hrhelper-messaging-bar.hrhelper-theme-dark .hrhelper-add-vacancy-dropdown,
    .hrhelper-messaging-bar.hrhelper-theme-dark .hrhelper-status-dropdown {
      background: #161b22 !important; border-color: var(--hrhelper-border) !important; color: #e6edf3 !important;
    }
  `;
  (document.head || document.documentElement).appendChild(style);
}

function applyFloatingWidgetTheme(wrapper) {
  if (!wrapper || !wrapper.classList) return;
  if (resolvedWidgetTheme === "dark") wrapper.classList.add("hrhelper-theme-dark");
  else wrapper.classList.remove("hrhelper-theme-dark");
}

function applyMessagingBarTheme(wrapper) {
  if (!wrapper || !wrapper.classList) return;
  if (resolvedWidgetTheme === "dark") wrapper.classList.add("hrhelper-theme-dark");
  else wrapper.classList.remove("hrhelper-theme-dark");
}

let floatingThemeObserver = null;
let messagingBarThemeObserver = null;
const debouncedUpdateResolvedTheme = debounce(updateResolvedWidgetTheme, TIMING.DEBOUNCE_THEME || 50);
function startFloatingWidgetThemeObserver(wrapper) {
  if (floatingThemeObserver || !wrapper) return;
  floatingThemeObserver = new MutationObserver(() => debouncedUpdateResolvedTheme());
  floatingThemeObserver.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ["data-theme", "data-mode", "class"],
  });
}

function startMessagingBarThemeObserver() {
  if (messagingBarThemeObserver) return;
  messagingBarThemeObserver = new MutationObserver(() => debouncedUpdateResolvedTheme());
  messagingBarThemeObserver.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ["data-theme", "data-mode", "class"],
  });
}

try {
  chrome.storage.onChanged.addListener((changes, areaName) => {
    if (areaName === "sync" && changes[OPTIONS_THEME_KEY]) {
      updateResolvedWidgetTheme();
      if (typeof window._hrhelperApplyCalendarButtonTheme === "function") window._hrhelperApplyCalendarButtonTheme();
    }
  });
} catch (_) {}

function createFloatingWidget() {
  injectFloatingWidgetThemeStyles();
  const wrapper = document.createElement("div");
  wrapper.className = "hrhelper-floating-widget";
  wrapper.dataset.hrhelperHuntflow = "1";
  wrapper.dataset.hrhelperFloating = "true";
  const widgetWidth = (HRH.FLOATING_WIDGET_WIDTH != null ? HRH.FLOATING_WIDGET_WIDTH : 320);
  wrapper.style.cssText = `
    position: fixed;
    top: 60px;
    right: 12px;
    z-index: 99999;
    width: ${widgetWidth}px;
    min-width: 0;
    max-height: calc(100vh - 168px);
    border-radius: 12px;
    padding: 16px;
    backdrop-filter: blur(8px);
    transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
    display: flex;
    flex-direction: column;
    overflow: hidden;
    overflow-x: hidden;
  `;
  const baseShadow = "0 4px 16px rgba(0, 0, 0, 0.15), 0 0 0 1px rgba(0, 0, 0, 0.05)";
  wrapper.dataset.hrhelperBaseBoxShadow = baseShadow;
  wrapper.style.boxShadow = baseShadow;

  const header = document.createElement("div");
  header.className = "hrhelper-widget-header";
  header.style.cssText = "display:flex;align-items:center;justify-content:space-between;gap:8px;padding-bottom:8px;border-bottom:1px solid var(--hrhelper-border,rgba(0,0,0,.08));flex-shrink:0;";

  const headerLeft = document.createElement("div");
  headerLeft.className = "hrhelper-widget-header-left";
  headerLeft.style.cssText = "flex:1;min-width:0;display:flex;align-items:center;gap:6px;";

  const title = document.createElement("div");
  title.className = "hrhelper-widget-title";
  title.style.cssText = "font-size:14px;font-weight:600;color:var(--hrhelper-accent,#0a66c2);display:flex;align-items:center;gap:6px;flex:1;min-width:0;overflow:hidden;";
  const titleIcon = document.createElement("img");
  titleIcon.className = "hrhelper-title-icon";
  const iconSize = hasBlacklistLabel(STATE.linkedinFull.candidateInfo) ? 30 : 20;
  titleIcon.src = iconSize === 30 ? chrome.runtime.getURL("icons/dark-label.png") : chrome.runtime.getURL("icons/icon-32.png");
  titleIcon.alt = "";
  titleIcon.width = iconSize;
  titleIcon.height = iconSize;
  titleIcon.style.cssText = "flex-shrink:0;display:block;object-fit:contain;";
  titleIcon.onerror = function () {
    const svg = document.createElement("span");
    svg.innerHTML = '<svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor" style="flex-shrink:0;display:block;"><path d="M20 6h-4V4c0-1.11-.89-2-2-2h-4c-1.11 0-2 .89-2 2v2H4c-1.11 0-1.99.89-1.99 2L2 19c0 1.11.89 2 2 2h16c1.11 0 2-.89 2-2V8c0-1.11-.89-2-2-2zm-6 0h-4V4h4v2z"/></svg>';
    titleIcon.replaceWith(svg.firstElementChild || svg);
  };
  title.appendChild(titleIcon);
  const titleText = document.createElement("span");
  titleText.className = "hrhelper-widget-title-text";
  titleText.style.cssText = "overflow:hidden;text-overflow:ellipsis;white-space:nowrap;";
  titleText.textContent = "HR Helper";
  title.appendChild(titleText);
  headerLeft.appendChild(title);

  const actionGroup = document.createElement("div");
  actionGroup.className = "hrhelper-floating-action-group";
  actionGroup.style.cssText = "display:flex;align-items:stretch;gap:0;flex-shrink:0;";

  const addVacancyBtn = document.createElement("button");
  addVacancyBtn.type = "button";
  addVacancyBtn.className = "hrhelper-add-vacancy-btn";
  addVacancyBtn.textContent = "+";
  addVacancyBtn.title = "Взять на другую вакансию";
  addVacancyBtn.style.cssText = "width:24px;height:24px;border:1px solid var(--hrhelper-border,rgba(0,0,0,.15));border-right:none;border-radius:4px 0 0 4px;background:var(--hrhelper-btn-bg,rgba(0,0,0,.05));cursor:pointer;color:var(--hrhelper-muted,#666);font-size:16px;line-height:1;padding:0;display:none;align-items:center;justify-content:center;";
  addVacancyBtn.addEventListener("mouseenter", () => { addVacancyBtn.style.background = "var(--hrhelper-border,rgba(0,0,0,.1))"; });
  addVacancyBtn.addEventListener("mouseleave", () => { addVacancyBtn.style.background = "var(--hrhelper-btn-bg,rgba(0,0,0,.05))"; });
  actionGroup.appendChild(addVacancyBtn);

  const huntflowBtn = document.createElement("button");
  huntflowBtn.type = "button";
  huntflowBtn.className = "hrhelper-floating-huntflow-btn";
  huntflowBtn.title = "Открыть в Huntflow";
  huntflowBtn.setAttribute("aria-label", "Открыть в Huntflow");
  huntflowBtn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M19 19H5V5h7V3H5c-1.11 0-2 .9-2 2v14c0 1.1.89 2 2 2h14c1.1 0 2-.9 2-2v-7h-2v7zM14 3v2h3.59l-9.83 9.83 1.41 1.41L19 6.41V10h2V3h-7z"/></svg>';
  huntflowBtn.style.cssText = "width:24px;height:24px;border:1px solid var(--hrhelper-border,rgba(0,0,0,.15));border-radius:0;cursor:pointer;color:var(--hrhelper-muted,#666);flex-shrink:0;padding:0;display:none;align-items:center;justify-content:center;background:var(--hrhelper-btn-bg,rgba(0,0,0,.05));";
  huntflowBtn.addEventListener("mouseenter", () => { huntflowBtn.style.background = "var(--hrhelper-border,rgba(0,0,0,.1))"; });
  huntflowBtn.addEventListener("mouseleave", () => { huntflowBtn.style.background = "var(--hrhelper-btn-bg,rgba(0,0,0,.05))"; });
  actionGroup.appendChild(huntflowBtn);

  const floatingEditBtn = document.createElement("button");
  floatingEditBtn.type = "button";
  floatingEditBtn.className = "hrhelper-floating-edit-btn";
  floatingEditBtn.title = "Редактировать ссылку";
  floatingEditBtn.setAttribute("aria-label", "Редактировать ссылку");
  floatingEditBtn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zM20.71 7.04c.39-.39.39-1.02 0-1.41l-2.34-2.34c-.39-.39-1.02-.39-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z"/></svg>';
  floatingEditBtn.style.cssText = "width:24px;height:24px;border:1px solid var(--hrhelper-border,rgba(0,0,0,.15));border-radius:0 4px 4px 0;cursor:pointer;color:var(--hrhelper-muted,#666);flex-shrink:0;padding:0;display:none;align-items:center;justify-content:center;background:var(--hrhelper-btn-bg,rgba(0,0,0,.05));";
  floatingEditBtn.addEventListener("click", (e) => { e.stopPropagation(); onEditClick(e); });
  floatingEditBtn.addEventListener("mouseenter", () => { floatingEditBtn.style.background = "var(--hrhelper-border,rgba(0,0,0,.1))"; });
  floatingEditBtn.addEventListener("mouseleave", () => { floatingEditBtn.style.background = "var(--hrhelper-btn-bg,rgba(0,0,0,.05))"; });
  actionGroup.appendChild(floatingEditBtn);

  const copyVacancyBtn = document.createElement("button");
  copyVacancyBtn.type = "button";
  copyVacancyBtn.className = "hrhelper-floating-copy-btn";
  copyVacancyBtn.title = "Скопировать ссылку на вакансию";
  copyVacancyBtn.setAttribute("aria-label", "Скопировать ссылку на вакансию");
  copyVacancyBtn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M16 1H4c-1.1 0-2 .9-2 2v14h2V3h12V1zm3 4H8c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h11c1.1 0 2-.9 2-2V7c0-1.1-.9-2-2-2zm0 16H8V7h11v14z"/></svg>';
  copyVacancyBtn.style.cssText = "width:24px;height:24px;border:1px solid var(--hrhelper-border,rgba(0,0,0,.15));border-radius:4px;cursor:pointer;color:var(--hrhelper-muted,#666);flex-shrink:0;padding:0;display:flex;align-items:center;justify-content:center;background:var(--hrhelper-btn-bg,rgba(0,0,0,.05));margin-right:4px;";
  copyVacancyBtn.addEventListener("mouseenter", () => { if (!copyVacancyBtn.classList.contains("hrhelper-copy-btn-copied")) copyVacancyBtn.style.background = "var(--hrhelper-border,rgba(0,0,0,.1))"; });
  copyVacancyBtn.addEventListener("mouseleave", () => { if (!copyVacancyBtn.classList.contains("hrhelper-copy-btn-copied")) copyVacancyBtn.style.background = "var(--hrhelper-btn-bg,rgba(0,0,0,.05))"; });
  copyVacancyBtn.addEventListener("click", async (e) => {
    e.stopPropagation();
    try {
      const url = getSelectedVacancyUrl();
      if (!url) return;
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(url);
        copyVacancyBtn.classList.add("hrhelper-copy-btn-copied");
        copyVacancyBtn.style.borderColor = "var(--hrhelper-success-border, #a3cfbb)";
        copyVacancyBtn.style.color = "var(--hrhelper-success, #0f5132)";
        copyVacancyBtn.style.background = "var(--hrhelper-success-bg, #d1e7dd)";
        copyVacancyBtn.title = "Скопировано";
        setTimeout(() => {
          copyVacancyBtn.classList.remove("hrhelper-copy-btn-copied");
          copyVacancyBtn.style.borderColor = "var(--hrhelper-border, rgba(0,0,0,.15))";
          copyVacancyBtn.style.color = "var(--hrhelper-muted, #666)";
          copyVacancyBtn.style.background = "var(--hrhelper-btn-bg, rgba(0,0,0,.05))";
          copyVacancyBtn.title = "Скопировать ссылку на вакансию";
        }, 1500);
      }
    } catch (_) {}
  });

  const toggleBtn = document.createElement("button");
  toggleBtn.type = "button";
  toggleBtn.className = "hrhelper-toggle-btn";
  toggleBtn.title = "Свернуть / развернуть";
  toggleBtn.setAttribute("aria-label", "Свернуть");
  toggleBtn.style.cssText = "width:24px;height:24px;border:none;background:var(--hrhelper-btn-bg,rgba(0,0,0,.05));border-radius:4px;cursor:pointer;color:var(--hrhelper-muted,#666);flex-shrink:0;padding:0;display:flex;align-items:center;justify-content:center;";
  toggleBtn.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path class="hrhelper-toggle-icon-path" d="M7.41 15.41L12 10.83l4.59 4.58L18 14l-6-6-6 6z"/></svg>';
  toggleBtn.addEventListener("mouseenter", () => { toggleBtn.style.background = "var(--hrhelper-border,rgba(0,0,0,.1))"; });
  toggleBtn.addEventListener("mouseleave", () => { toggleBtn.style.background = "var(--hrhelper-btn-bg,rgba(0,0,0,.05))"; });

  header.appendChild(headerLeft);
  header.appendChild(copyVacancyBtn);
  header.appendChild(actionGroup);
  header.appendChild(toggleBtn);
  wrapper.appendChild(header);

  const body = document.createElement("div");
  body.className = "hrhelper-widget-body";
  body.style.cssText = "display:flex;flex-direction:column;gap:8px;flex:1;min-height:0;min-width:0;overflow-y:auto;overflow-x:hidden;word-break:break-word;overflow-wrap:break-word;color:inherit;";
  wrapper.appendChild(body);

  const statusDropdown = document.createElement("div");
  statusDropdown.className = "hrhelper-status-dropdown";
  statusDropdown.style.cssText = "display:none;position:absolute;background:var(--hrhelper-bg,#fff);border:1px solid var(--hrhelper-border,rgba(0,0,0,.2));border-radius:8px;box-shadow:0 4px 12px rgba(0,0,0,.15);z-index:100002;min-width:200px;max-width:300px;margin-top:4px;";
  wrapper.appendChild(statusDropdown);

  const addVacancyDropdown = document.createElement("div");
  addVacancyDropdown.className = "hrhelper-add-vacancy-dropdown";
  addVacancyDropdown.style.cssText = "display:none;position:absolute;background:var(--hrhelper-bg,#fff);border:1px solid var(--hrhelper-border,rgba(0,0,0,.2));border-radius:8px;box-shadow:0 4px 12px rgba(0,0,0,.15);z-index:100002;min-width:200px;max-width:280px;max-height:220px;overflow-y:auto;";
  wrapper.appendChild(addVacancyDropdown);

  const isCollapsed = !!floatingWidgetUIState.widgetCollapsed;
  body.style.display = isCollapsed ? "none" : "flex";
  const togglePath = toggleBtn.querySelector(".hrhelper-toggle-icon-path");
  if (togglePath) togglePath.setAttribute("d", isCollapsed ? "M7.41 8.59L12 13.17l4.59-4.58L18 10l-6 6-6-6z" : "M7.41 15.41L12 10.83l4.59 4.58L18 14l-6-6-6 6z");
  toggleBtn.addEventListener("click", () => {
    const willExpand = body.style.display === "none";
    body.style.display = willExpand ? "flex" : "none";
    const pathEl = toggleBtn.querySelector(".hrhelper-toggle-icon-path");
    if (pathEl) pathEl.setAttribute("d", willExpand ? "M7.41 15.41L12 10.83l4.59 4.58L18 14l-6-6-6 6z" : "M7.41 8.59L12 13.17l4.59-4.58L18 10l-6 6-6-6z");
    toggleBtn.setAttribute("aria-label", willExpand ? "Свернуть" : "Развернуть");
    toggleBtn.title = willExpand ? "Свернуть" : "Развернуть";
    saveFloatingUIState({ widgetCollapsed: !willExpand });
  });

  return { wrapper, body, statusDropdown, addVacancyDropdown, toggleBtn, titleText, titleIcon, actionGroup, addVacancyBtn, huntflowBtn, floatingEditBtn };
}

function getSelectedVacancyUrl() {
  const selId = STATE.linkedinFull.selectedVacancyId ?? STATE.linkedinFull.defaultVacancyId;
  const v = (STATE.linkedinFull.vacancies || []).find((i) => i.vacancy_id === selId);
  return v ? v.appurl : STATE.current.appUrl;
}

function repopulateFloatingWidgetBody() {
  if (!floatingWidgetData?.body) return;
  updateFloatingWidgetHeader();
  populateFloatingWidgetBody(floatingWidgetData.body);
}

function updateFloatingWidgetHeader() {
  try {
    if (!chrome.runtime?.id) return;
  } catch (_) {
    return;
  }
  const { titleText, actionGroup, addVacancyBtn, huntflowBtn, floatingEditBtn } = floatingWidgetData || {};
  if (!titleText) return;
  const info = STATE.linkedinFull.candidateInfo;
  const hasFio = info?.full_name && STATE.current.mode === "open";
  titleText.textContent = hasFio ? info.full_name : "HR Helper";
  const showActions = STATE.current.mode === "open" && !!STATE.current.appUrl;
  const showEditBtn = showActions || STATE.current.mode === "input";
  if (addVacancyBtn) {
    addVacancyBtn.style.display = showActions ? "flex" : "none";
    if (showActions && !addVacancyBtn._bound) {
      addVacancyBtn._bound = true;
      addVacancyBtn.addEventListener("click", (e) => onAddVacancyClickFloating(e, addVacancyBtn));
    }
  }
  if (huntflowBtn) {
    huntflowBtn.style.display = showActions ? "flex" : "none";
    const huntflowUrl = showActions ? (getSelectedVacancyUrl() || STATE.current.appUrl) : "";
    huntflowBtn.onclick = huntflowUrl ? () => window.open(huntflowUrl, "_blank", "noopener,noreferrer") : null;
  }
  if (floatingEditBtn) {
    floatingEditBtn.style.display = showEditBtn ? "flex" : "none";
  }
  if (actionGroup && addVacancyBtn && huntflowBtn && floatingEditBtn) {
    [addVacancyBtn, huntflowBtn, floatingEditBtn].forEach((b) => {
      b.style.borderRadius = "";
      b.style.borderRight = "1px solid var(--hrhelper-border,rgba(0,0,0,.15))";
    });
    const visible = [addVacancyBtn, huntflowBtn, floatingEditBtn].filter((b) => b && b.style.display === "flex");
    visible.forEach((b, i) => {
      if (visible.length === 1) b.style.borderRadius = "4px";
      else if (i === 0) b.style.borderRadius = "4px 0 0 4px";
      else if (i === visible.length - 1) b.style.borderRadius = "0 4px 4px 0";
      else b.style.borderRadius = "0";
      if (i < visible.length - 1) b.style.borderRight = "none";
    });
  }
}

function populateFloatingWidgetBody(body) {
  body.innerHTML = "";
  const btnStyle = "padding:6px 10px;border-radius:6px;font-size:12px;font-weight:600;cursor:pointer;border:none;transition:background .2s;";
  const rowStyle = "display:flex;align-items:center;gap:6px;flex-wrap:wrap;";

  if (STATE.current.mode === "input") {
    const label = document.createElement("label");
    label.className = "hrhelper-body-accent";
    label.style.cssText = "font-size:12px;font-weight:600;display:block;margin-bottom:4px;";
    label.textContent = "Ссылка на кандидата в Huntflow";
    body.appendChild(label);
    const inputRow = document.createElement("div");
    inputRow.style.cssText = rowStyle + "margin-bottom:8px;";
    const input = document.createElement("input");
    input.type = "url";
    input.className = "hrhelper-widget-input";
    input.placeholder = "https://huntflow.ru/my/...";
    input.value = STATE.current.inputValue || "";
    input.style.cssText = "flex:1;min-width:0;padding:8px 10px;font-size:12px;border:1px solid var(--hrhelper-border,#ccc);border-radius:6px;";
    input.addEventListener("input", () => { STATE.current.inputValue = input.value; });
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        onSaveLinkClick();
      } else if (e.key === "Escape") {
        e.preventDefault();
        removeFloatingEditEscHandler();
        STATE.current.mode = "open";
        STATE.current.appUrl = STATE.current.originalAppUrl;
        STATE.current.inputValue = "";
        STATE.current.disabled = false;
        STATE.current.title = "Открыть в Huntflow";
        STATE.current.originalAppUrl = null;
        applyStateToAllButtons();
      }
    });
    const saveBtn = document.createElement("button");
    saveBtn.type = "button";
    saveBtn.textContent = "Сохранить";
    saveBtn.style.cssText = btnStyle + "background:var(--hrhelper-accent,#0a66c2);color:#fff;";
    saveBtn.addEventListener("click", () => { onSaveLinkClick(); });
    inputRow.appendChild(input);
    inputRow.appendChild(saveBtn);
    body.appendChild(inputRow);
    const desc = document.createElement("div");
    desc.className = "hrhelper-body-muted";
    desc.style.cssText = "font-size:11px;";
    desc.textContent = "Вставьте ссылку и нажмите «Сохранить».";
    body.appendChild(desc);
    if (STATE.linkedinFull.isProfileEmployee) {
      const badge = document.createElement("div");
      badge.className = "hrhelper-body-success";
      badge.style.cssText = "padding:8px;margin-top:8px;background:var(--hrhelper-success-bg);border:1px solid var(--hrhelper-success-border);border-radius:6px;font-size:12px;font-weight:600;";
      badge.textContent = "✅ Сотрудник";
      body.appendChild(badge);
    }
    return;
  }

  const info = STATE.linkedinFull.candidateInfo;
  const vacancies = STATE.linkedinFull.vacancies || [];
  const { active, rejected, archived, hired } = categorizeVacancies(vacancies);

  const hasContacts = info && (info.phone || info.email || info.telegram || info.communication);
  if (hasContacts) {
    const open = !!floatingWidgetUIState.candidateDataOpen;
    const toggle = document.createElement("button");
    toggle.type = "button";
    toggle.className = "hrhelper-body-accent";
    toggle.style.cssText = "font-size:12px;background:none;border:none;cursor:pointer;padding:4px 0;margin-bottom:4px;text-align:left;";
    toggle.textContent = open ? "Контакты и коммуникация ▲" : "Контакты и коммуникация ▼";
    const details = document.createElement("div");
    details.className = "hrhelper-body-muted";
    details.style.cssText = "font-size:11px;margin-bottom:8px;padding:8px;background:var(--hrhelper-btn-bg,rgba(0,0,0,.03));border-radius:6px;display:" + (open ? "block" : "none") + ";";
    const escapeHtml = (s) => String(s).replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
    const contactRows = [];
    if (info.phone) contactRows.push({ label: "Телефон", html: "<a href=\"tel:" + escapeHtml(info.phone) + "\">" + escapeHtml(info.phone) + "</a>" });
    if (info.email) contactRows.push({ label: "Email", html: "<a href=\"mailto:" + escapeHtml(info.email) + "\">" + escapeHtml(info.email) + "</a>" });
    let linkedinUrl = null;
    try { linkedinUrl = normalizeLinkedInProfileUrl(location.href) || location.href; } catch (_) { linkedinUrl = location.href; }
    contactRows.push({ label: "LinkedIn", html: "<a href=\"" + escapeHtml(linkedinUrl) + "\" target=\"_blank\" rel=\"noopener\">" + escapeHtml(linkedinUrl) + "</a>" });
    if (info.telegram) {
      const t = String(info.telegram).trim();
      const telegramHref = /^https?:\/\//i.test(t) ? t : "https://t.me/" + t.replace(/^@/, "");
      contactRows.push({ label: "Telegram", html: "<a href=\"" + escapeHtml(telegramHref) + "\" target=\"_blank\" rel=\"noopener\">" + escapeHtml(t) + "</a>" });
    }
    if (info.communication) {
      const comm = String(info.communication).trim();
      const commLower = comm.toLowerCase();
      let label = "Коммуникация";
      let href = null;
      if (/^https?:\/\//i.test(comm)) {
        href = comm;
        if (commLower.includes("t.me") || commLower.includes("telegram")) label = "Telegram";
        else if (commLower.includes("wa.me") || commLower.includes("whatsapp")) label = "WhatsApp";
        else if (commLower.includes("vk.com") || commLower.includes("vkontakte")) label = "VK";
        else if (commLower.includes("facebook") || commLower.includes("fb.")) label = "Facebook";
        else if (commLower.includes("linkedin")) label = "LinkedIn";
      } else {
        if (/telegram|tg|тг/i.test(comm)) { label = "Telegram"; href = info.telegram ? (/^https?:\/\//i.test(String(info.telegram)) ? info.telegram : "https://t.me/" + String(info.telegram).replace(/^@/, "")) : null; }
        else if (/whatsapp|wa\.me/i.test(comm)) label = "WhatsApp";
        else if (/vk\.|vkontakte|вк/i.test(comm)) label = "VK";
        else label = comm.length > 30 ? comm.slice(0, 30) + "…" : comm;
      }
      const html = href ? "<a href=\"" + escapeHtml(href) + "\" target=\"_blank\" rel=\"noopener\">" + escapeHtml(label === "Коммуникация" ? comm : label) + "</a>" : escapeHtml(comm);
      if (label === "Telegram" && info.telegram) { /* уже есть строка Telegram выше */ } else contactRows.push({ label: label, html: html });
    }
    details.innerHTML = contactRows.map((r) => "<div><b>" + escapeHtml(r.label) + ":</b> " + r.html + "</div>").join("");
    toggle.addEventListener("click", () => {
      const nowOpen = details.style.display !== "none";
      details.style.display = nowOpen ? "none" : "block";
      toggle.textContent = nowOpen ? "Контакты и коммуникация ▼" : "Контакты и коммуникация ▲";
      saveFloatingUIState({ candidateDataOpen: !nowOpen });
    });
    body.appendChild(toggle);
    body.appendChild(details);
  }

  const excludeLevelKey = /^уровень$|^level$/i;
  const extraFieldsEntries = info && info.extra_fields && typeof info.extra_fields === "object"
    ? Object.entries(info.extra_fields).filter(([k, v]) => v != null && v !== "" && !excludeLevelKey.test(String(k).trim()))
    : [];
  if (extraFieldsEntries.length > 0) {
    const openExtra = !!floatingWidgetUIState.extraFieldsOpen;
    const toggleExtra = document.createElement("button");
    toggleExtra.type = "button";
    toggleExtra.className = "hrhelper-body-accent";
    toggleExtra.style.cssText = "font-size:12px;background:none;border:none;cursor:pointer;padding:4px 0;margin-bottom:4px;text-align:left;";
    toggleExtra.textContent = openExtra ? "Дополнительные поля ▲" : "Дополнительные поля ▼";
    const extraBlock = document.createElement("div");
    extraBlock.className = "hrhelper-body-muted";
    extraBlock.style.cssText = "font-size:11px;margin-bottom:8px;padding:8px;background:var(--hrhelper-btn-bg,rgba(0,0,0,.03));border-radius:6px;display:" + (openExtra ? "block" : "none") + ";";
    extraBlock.innerHTML = extraFieldsEntries.map(([l, v]) => "<div><b>" + String(l).replace(/</g, "&lt;") + ":</b> " + String(v).replace(/</g, "&lt;") + "</div>").join("");
    toggleExtra.addEventListener("click", () => {
      const nowOpen = extraBlock.style.display !== "none";
      extraBlock.style.display = nowOpen ? "none" : "block";
      toggleExtra.textContent = nowOpen ? "Дополнительные поля ▼" : "Дополнительные поля ▲";
      saveFloatingUIState({ extraFieldsOpen: !nowOpen });
    });
    body.appendChild(toggleExtra);
    body.appendChild(extraBlock);
  }

  if (info && info.labels && info.labels.length > 0) {
    const normalizeLabelColor = HRH.normalizeLabelColor || ((v) => (v && typeof v === "string" ? (v.indexOf("#") === 0 ? v : "#" + v.replace(/^#/, "")) : ""));
    const labelsWrap = document.createElement("div");
    labelsWrap.style.cssText = "display:flex;flex-wrap:wrap;gap:4px;margin-bottom:8px;";
    info.labels.forEach((lbl) => {
      const name = (typeof lbl === "string" ? lbl : (lbl && (lbl.name || lbl.title)) || "").trim();
      if (!name) return;
      const tag = document.createElement("span");
      tag.style.cssText = "font-size:11px;padding:2px 8px;border-radius:4px;background:var(--hrhelper-btn-bg,rgba(0,0,0,.06));border:1px solid var(--hrhelper-border,rgba(0,0,0,.1));";
      const rawColor = (lbl && typeof lbl === "object" && (lbl.color || lbl.background_color || lbl.bg_color || lbl.border_color || lbl.hex)) || "";
      const color = rawColor ? normalizeLabelColor(String(rawColor)) : "";
      if (color) {
        tag.style.borderColor = color;
        tag.style.color = color;
      }
      tag.textContent = name || "—";
      labelsWrap.appendChild(tag);
    });
    body.appendChild(labelsWrap);
  }

  const isProfileEmployee = !!STATE.linkedinFull.isProfileEmployee;
  if (hired.length > 0 || isProfileEmployee) {
    const badge = document.createElement("div");
    badge.className = "hrhelper-body-success";
    badge.style.cssText = "padding:8px;background:var(--hrhelper-success-bg);border:1px solid var(--hrhelper-success-border);border-radius:6px;font-size:12px;font-weight:600;";
    badge.textContent = "✅ Сотрудник";
    body.appendChild(badge);
  }
  if (!(hired.length > 0 || isProfileEmployee) && (active.length > 0 || rejected.length > 0 || archived.length > 0 || STATE.current.vacancy_name)) {
    const selId = STATE.linkedinFull.selectedVacancyId ?? STATE.linkedinFull.defaultVacancyId;
    if (active.length > 0) {
      const activeTitle = document.createElement("div");
      activeTitle.className = "hrhelper-body-muted";
      activeTitle.style.cssText = "font-size:11px;font-weight:600;margin:8px 0 4px 0;";
      activeTitle.textContent = "Активные вакансии";
      body.appendChild(activeTitle);
      active.forEach((v) => {
        const card = document.createElement("div");
        const isSel = v.vacancy_id === selId;
        const cardBorderColor = computeBorderColorForVacancy(v) || (isSel ? "var(--hrhelper-card-sel-border)" : "var(--hrhelper-card-border)");
        const cardBg = isSel ? "var(--hrhelper-card-sel-bg)" : "var(--hrhelper-card-bg)";
        card.style.cssText = "padding:8px 10px;margin-bottom:4px;border-radius:6px;font-size:12px;cursor:pointer;border:1px solid " + cardBorderColor + ";background:" + cardBg + ";display:flex;align-items:center;justify-content:space-between;gap:8px;";
        const left = document.createElement("span");
        left.style.cssText = "min-width:0;flex:1;";
        left.textContent = (isSel ? "✓ " : "") + (v.vacancy_name || "—") + (v.status_name ? " (" + v.status_name + ")" : "");
        const dateSpan = document.createElement("span");
        dateSpan.className = "hrhelper-body-muted";
        dateSpan.style.cssText = "font-size:10px;flex-shrink:0;";
        dateSpan.textContent = (v.last_change_at && formatVacancyDate) ? formatVacancyDate(v.last_change_at) : "";
        card.appendChild(left);
        card.appendChild(dateSpan);
        card.dataset.vacancyId = v.vacancy_id;
        card.addEventListener("click", () => {
          STATE.linkedinFull.selectedVacancyId = v.vacancy_id;
          STATE.current.appUrl = v.appurl;
          STATE.current.statusName = v.status_name;
          STATE.current.status_id = v.status_id ?? null;
          STATE.current.rejection_reason_id = v.rejection_reason_id ?? null;
          STATE.current.vacancy_name = v.vacancy_name;
          STATE.current.rejection_reason_name = v.rejection_reason_name;
          repopulateFloatingWidgetBody();
          updateFloatingWidget();
        });
        body.appendChild(card);
      });
    }
    if (rejected.length > 0) {
      const rejTitle = document.createElement("div");
      rejTitle.className = "hrhelper-body-danger";
      rejTitle.style.cssText = "font-size:11px;font-weight:600;margin:8px 0 4px 0;";
      rejTitle.textContent = "❌ Отказы";
      body.appendChild(rejTitle);
      rejected.forEach((v) => {
        const card = document.createElement("div");
        card.style.cssText = "padding:8px 10px;margin-bottom:4px;border-radius:6px;font-size:12px;cursor:pointer;border:1px solid var(--hrhelper-danger-border);background:var(--hrhelper-danger-bg);color:var(--hrhelper-danger);display:flex;align-items:center;justify-content:space-between;gap:8px;";
        const left = document.createElement("div");
        left.textContent = (v.vacancy_name || "—") + (v.rejection_reason_name ? " — " + v.rejection_reason_name : "");
        const dateSpan = document.createElement("span");
        dateSpan.style.cssText = "font-size:10px;opacity:.9;flex-shrink:0;";
        dateSpan.textContent = (v.last_change_at && formatVacancyDate) ? formatVacancyDate(v.last_change_at) : "";
        card.appendChild(left);
        card.appendChild(dateSpan);
        card.dataset.vacancyId = v.vacancy_id;
        card.addEventListener("click", () => {
          STATE.linkedinFull.selectedVacancyId = v.vacancy_id;
          STATE.current.appUrl = v.appurl;
          STATE.current.statusName = v.status_name;
          STATE.current.status_id = v.status_id ?? null;
          STATE.current.rejection_reason_id = v.rejection_reason_id ?? null;
          STATE.current.vacancy_name = v.vacancy_name;
          STATE.current.rejection_reason_name = v.rejection_reason_name;
          repopulateFloatingWidgetBody();
          updateFloatingWidget();
        });
        body.appendChild(card);
      });
    }
    if (archived.length > 0) {
      const archTitle = document.createElement("div");
      archTitle.className = "hrhelper-body-muted";
      archTitle.style.cssText = "font-size:11px;font-weight:600;margin:8px 0 4px 0;";
      archTitle.textContent = "Архивные вакансии";
      body.appendChild(archTitle);
      archived.forEach((v) => {
        const card = document.createElement("div");
        const isSel = v.vacancy_id === selId;
        card.className = "hrhelper-archived-vacancy-card";
        const borderColor = isSel ? "var(--hrhelper-card-sel-border)" : "var(--hrhelper-border)";
        const bgColor = isSel ? "var(--hrhelper-card-sel-bg)" : "var(--hrhelper-btn-bg)";
        card.style.cssText = "padding:8px 10px;margin-bottom:4px;border-radius:6px;font-size:12px;cursor:pointer;border:1px solid " + borderColor + ";background:" + bgColor + ";color:var(--hrhelper-text);display:flex;align-items:center;justify-content:space-between;gap:8px;";
        const left = document.createElement("span");
        left.style.cssText = "min-width:0;flex:1;";
        left.textContent = (isSel ? "✓ " : "") + (v.vacancy_name || "—") + (v.status_name ? " (" + v.status_name + ")" : "");
        const dateSpan = document.createElement("span");
        dateSpan.className = "hrhelper-body-muted";
        dateSpan.style.cssText = "font-size:10px;flex-shrink:0;";
        dateSpan.textContent = (v.last_change_at && formatVacancyDate) ? formatVacancyDate(v.last_change_at) : "";
        card.appendChild(left);
        card.appendChild(dateSpan);
        card.dataset.vacancyId = v.vacancy_id;
        card.addEventListener("click", () => {
          STATE.linkedinFull.selectedVacancyId = v.vacancy_id;
          STATE.current.appUrl = v.appurl;
          STATE.current.statusName = v.status_name;
          STATE.current.status_id = v.status_id ?? null;
          STATE.current.rejection_reason_id = v.rejection_reason_id ?? null;
          STATE.current.vacancy_name = v.vacancy_name;
          STATE.current.rejection_reason_name = v.rejection_reason_name;
          repopulateFloatingWidgetBody();
          updateFloatingWidget();
        });
        body.appendChild(card);
      });
    }
  }

  appendFloatingStatusBlock(body, btnStyle);
  appendFloatingCommentsBlock(body);
}

function appendFloatingCommentsBlock(body) {
  const selId = STATE.linkedinFull.selectedVacancyId ?? STATE.linkedinFull.defaultVacancyId;
  const vacancies = STATE.linkedinFull.vacancies || [];
  const vacancy = vacancies.find((v) => v.vacancy_id === selId);
  const comments = vacancy?.comments || [];
  if (comments.length === 0) return;

  const isArchived = !!(vacancy && vacancy.is_archived);
  const vacancyNameForTitle = (vacancy.vacancy_name && String(vacancy.vacancy_name).trim()) || "вакансии";
  const commentsTitle = isArchived
    ? "Комментарии к " + vacancyNameForTitle + " (архив)"
    : "Последние комментарии";
  const expanded = isArchived ? false : !!floatingWidgetUIState.commentsOpen;

  const block = document.createElement("div");
  block.className = "hrhelper-comments-block";
  block.style.cssText = "margin-top:12px;padding-top:10px;border-top:1px solid var(--hrhelper-border,rgba(0,0,0,.1));";

  const header = document.createElement("div");
  header.className = "hrhelper-body-accent";
  header.style.cssText = "display:flex;align-items:center;gap:6px;cursor:pointer;user-select:none;font-size:12px;font-weight:600;margin-bottom:8px;";
  const chevronSpan = document.createElement("span");
  chevronSpan.className = "hrhelper-comments-chevron";
  chevronSpan.style.cssText = "transition:transform .2s;";
  chevronSpan.textContent = "▼";
  header.appendChild(chevronSpan);
  header.appendChild(document.createTextNode(" " + commentsTitle));
  const chevron = header.querySelector(".hrhelper-comments-chevron");
  const list = document.createElement("div");
  list.style.cssText = "display:flex;flex-direction:column;gap:8px;";
  list.style.display = expanded ? "flex" : "none";
  if (chevron) chevron.style.transform = expanded ? "rotate(0deg)" : "rotate(-90deg)";
  header.addEventListener("click", () => {
    const next = list.style.display === "none";
    list.style.display = next ? "flex" : "none";
    if (chevron) chevron.style.transform = next ? "rotate(0deg)" : "rotate(-90deg)";
    saveFloatingUIState({ commentsOpen: next });
  });
  block.appendChild(header);
  comments.forEach((c) => {
    const item = document.createElement("div");
    item.style.cssText = "font-size:11px;padding:8px;background:var(--hrhelper-btn-bg,rgba(0,0,0,.03));border-radius:6px;border-left:3px solid var(--hrhelper-accent,#0a66c2);color:var(--hrhelper-text);";
    const meta = document.createElement("div");
    meta.className = "hrhelper-body-muted";
    meta.style.cssText = "font-size:10px;margin-bottom:4px;";
    const metaParts = [];
    if (c.author) metaParts.push(c.author);
    if (c.created) metaParts.push(formatCommentDate(c.created));
    meta.textContent = metaParts.join(" · ");
    item.appendChild(meta);
    const text = document.createElement("div");
    text.style.cssText = "line-height:1.4;word-break:break-word;white-space:pre-wrap;";
    let raw = (c.text || "").replace(/<[^>]*>/g, "").replace(/&nbsp;/g, " ").trim();
    try {
      const tmp = document.createElement("textarea");
      tmp.innerHTML = raw;
      raw = tmp.value;
    } catch (_) {}
    text.textContent = raw || "—";
    item.appendChild(text);
    list.appendChild(item);
  });
  block.appendChild(list);
  body.appendChild(block);
}

const formatCommentDate = HRH.formatCommentDate;
if (!formatCommentDate) {
  throw new Error("[HRHelper] shared/utils/date.js not loaded (formatCommentDate missing)");
}

function isRejectionStatusOption(opt) {
  return HRH.isRejectionStatus ? HRH.isRejectionStatus(opt) : false;
}

function appendFloatingStatusBlock(body, btnStyle) {
  const block = document.createElement("div");
  block.className = "hrhelper-ctx-status-block";
  block.style.cssText = "margin-top:12px;padding-top:10px;border-top:1px solid var(--hrhelper-border,rgba(0,0,0,.1));";

  const formLabel = document.createElement("span");
  formLabel.className = "hrhelper-ctx-label";
  formLabel.style.cssText = "display:block;margin-bottom:6px;font-size:12px;font-weight:600;";
  formLabel.textContent = "Изменение статуса / Причина";
  block.appendChild(formLabel);

  const loadMsg = document.createElement("p");
  loadMsg.className = "hrhelper-status-load-msg hrhelper-body-muted";
  loadMsg.style.cssText = "margin:0 0 6px 0;font-size:11px;display:none;";
  block.appendChild(loadMsg);

  const statusRow = document.createElement("div");
  statusRow.style.cssText = "display:flex;align-items:center;gap:8px;margin-bottom:8px;";
  const statusSelect = document.createElement("select");
  statusSelect.className = "hrhelper-ctx-status-select";
  statusSelect.innerHTML = '<option value="">— Статус —</option>';
  statusSelect.style.cssText = "flex:1;min-width:0;padding:8px 10px;font-size:12px;border:1px solid var(--hrhelper-border);border-radius:6px;background:var(--hrhelper-input-bg);color:var(--hrhelper-text);";
  const nextBtn = document.createElement("button");
  nextBtn.type = "button";
  nextBtn.className = "hrhelper-ctx-status-next";
  nextBtn.title = "Следующий статус";
  nextBtn.style.cssText = "width:36px;height:36px;padding:0;border:1px solid var(--hrhelper-border);border-radius:6px;background:var(--hrhelper-input-bg);color:var(--hrhelper-accent);cursor:pointer;flex-shrink:0;";
  nextBtn.innerHTML = '<svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor"><path d="M10 6L8.59 7.41 13.17 12l-4.58 4.59L10 18l6-6z"/></svg>';
  statusRow.appendChild(statusSelect);
  statusRow.appendChild(nextBtn);
  block.appendChild(statusRow);

  const reasonRow = document.createElement("div");
  reasonRow.className = "hrhelper-ctx-reason-row";
  reasonRow.style.cssText = "margin-bottom:8px;display:none;";
  const reasonSelect = document.createElement("select");
  reasonSelect.className = "hrhelper-ctx-reason-select";
  reasonSelect.innerHTML = '<option value="">— Причина отказа —</option>';
  reasonSelect.style.cssText = "width:100%;padding:8px 10px;font-size:12px;border:1px solid var(--hrhelper-border);border-radius:6px;background:var(--hrhelper-input-bg);color:var(--hrhelper-text);box-sizing:border-box;";
  reasonRow.appendChild(reasonSelect);
  block.appendChild(reasonRow);

  const commentRow = document.createElement("div");
  commentRow.style.cssText = "margin-bottom:8px;";
  const commentLabel = document.createElement("label");
  commentLabel.className = "hrhelper-ctx-label";
  commentLabel.style.cssText = "display:block;margin-bottom:6px;font-size:12px;font-weight:600;";
  commentLabel.textContent = "Комментарий";
  commentRow.appendChild(commentLabel);
  const commentWrap = document.createElement("div");
  commentWrap.className = "hrhelper-ctx-comment-wrap";
  commentWrap.style.cssText = "border:1px solid var(--hrhelper-border);border-radius:6px;overflow:hidden;background:var(--hrhelper-input-bg);";
  const toolbar = document.createElement("div");
  toolbar.className = "hrhelper-ctx-comment-toolbar";
  toolbar.style.cssText = "display:flex;gap:4px;padding:4px 6px;border-bottom:1px solid var(--hrhelper-border);flex-wrap:wrap;";
  const toolbarBtns = [
    { cmd: "bold", title: "Жирный", html: "<b>B</b>" },
    { cmd: "italic", title: "Курсив", html: "<i>I</i>" },
    { cmd: "insertUnorderedList", title: "Маркированный список", html: "•" },
    { cmd: "insertOrderedList", title: "Нумерованный список", html: "1." },
    { cmd: "createLink", title: "Вставить ссылку", html: "🔗" }
  ];
  toolbarBtns.forEach(({ cmd, title, html }) => {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "hrhelper-ctx-comment-toolbar-btn";
    b.style.cssText = "width:28px;height:24px;padding:0;border:1px solid var(--hrhelper-border);border-radius:4px;background:var(--hrhelper-input-bg);color:var(--hrhelper-text);cursor:pointer;font-size:11px;display:inline-flex;align-items:center;justify-content:center;";
    b.title = title;
    b.innerHTML = html;
    b.addEventListener("click", (e) => {
      e.preventDefault();
      document.execCommand(cmd, false, null);
      commentEditor.focus();
    });
    toolbar.appendChild(b);
  });
  const commentEditor = document.createElement("div");
  commentEditor.className = "hrhelper-ctx-comment-editor";
  commentEditor.contentEditable = "true";
  commentEditor.dataset.placeholder = "Добавить комментарий к статусу...";
  commentEditor.style.cssText = "min-height:60px;max-height:120px;overflow-y:auto;padding:8px 10px;font-size:12px;border:none;background:var(--hrhelper-input-bg);color:var(--hrhelper-text);line-height:1.5;box-sizing:border-box;";
  commentWrap.appendChild(toolbar);
  commentWrap.appendChild(commentEditor);
  commentRow.appendChild(commentWrap);
  block.appendChild(commentRow);

  const applyBtn = document.createElement("button");
  applyBtn.type = "button";
  applyBtn.className = "hrhelper-ctx-apply-status";
  applyBtn.textContent = "Применить статус";
  applyBtn.style.cssText = btnStyle + "background:var(--hrhelper-input-bg);color:var(--hrhelper-text);width:100%;border:1px solid var(--hrhelper-border);";
  block.appendChild(applyBtn);

  const toggleReasonRow = () => {
    const sel = statusSelect.options[statusSelect.selectedIndex];
    reasonRow.style.display = (sel && sel.value && isRejectionStatusOption(sel)) ? "block" : "none";
  };
  statusSelect.addEventListener("change", toggleReasonRow);

  nextBtn.addEventListener("click", () => {
    const opts = Array.from(statusSelect.options).filter((o) => o.value !== "");
    if (opts.length < 2) return;
    const idx = opts.findIndex((o) => o.value === statusSelect.value);
    const nextIdx = idx < 0 ? 0 : (idx + 1) % opts.length;
    statusSelect.value = opts[nextIdx].value;
    toggleReasonRow();
  });

  applyBtn.addEventListener("click", async () => {
    let canonical = normalizeLinkedInProfileUrl(location.href);
    if (!canonical && IS_MESSAGING_PAGE) {
      try { canonical = await getProfileLinkFromMessaging(); } catch (_) {}
    }
    if (!canonical || !statusSelect.value) {
      loadMsg.textContent = statusSelect.value ? "Не найден URL профиля." : "Выберите статус.";
      loadMsg.style.display = "block";
      loadMsg.style.color = "#842029";
      return;
    }
    const sel = statusSelect.options[statusSelect.selectedIndex];
    const needReason = sel && isRejectionStatusOption(sel);
    const rejectionReasonId = reasonSelect.value?.trim() || null;
    if (needReason && !rejectionReasonId) {
      loadMsg.textContent = "Для статуса отказа выберите причину.";
      loadMsg.style.display = "block";
      loadMsg.style.color = "#842029";
      return;
    }
    const commentHtml = (commentEditor.innerHTML || "").trim();
    const comment = commentHtml === "<br>" || commentHtml === "<br/>" ? "" : commentHtml;
    applyBtn.disabled = true;
    applyBtn.textContent = "Сохранение…";
    loadMsg.style.display = "none";
    try {
      const vid = STATE.linkedinFull?.selectedVacancyId ?? STATE.linkedinFull?.defaultVacancyId;
      await updateStatus(canonical, parseInt(statusSelect.value, 10), rejectionReasonId ? parseInt(rejectionReasonId, 10) : null, vid, comment);
      commentEditor.innerHTML = "";
      loadMsg.textContent = "Статус обновлён.";
      loadMsg.style.color = "#0f5132";
      loadMsg.style.display = "block";
      setTimeout(() => { loadMsg.style.display = "none"; }, 2000);
    } catch (e) {
      loadMsg.textContent = e.message || "Ошибка";
      loadMsg.style.color = "#842029";
      loadMsg.style.display = "block";
    }
    applyBtn.disabled = false;
    applyBtn.textContent = "Применить статус";
  });

  body.appendChild(block);
  loadFloatingStatusOptions(statusSelect, reasonSelect, loadMsg);
}

async function loadFloatingStatusOptions(statusSelect, reasonSelect, loadMsg) {
  let canonical = normalizeLinkedInProfileUrl(location.href);
  if (!canonical && IS_MESSAGING_PAGE) {
    try { canonical = await getProfileLinkFromMessaging(); } catch (_) {}
  }
  if (!canonical || !STATE.current.appUrl) return;
  loadMsg.textContent = "Загрузка списка статусов...";
  loadMsg.style.display = "block";
  loadMsg.style.color = "#6c757d";
  try {
    const qp = new URLSearchParams({ linkedin_url: canonical });
    const res = await apiFetch("/api/v1/huntflow/linkedin-applicants/status-options/?" + qp.toString(), { method: "GET" });
    const data = await res.json().catch(() => ({}));
    if (!res.ok || !data?.success) {
      loadMsg.textContent = data?.message || "Не удалось загрузить список статусов.";
      loadMsg.style.color = "#842029";
      return;
    }
    const statuses = data.statuses || [];
    const rejectionReasons = data.rejection_reasons || [];
    statusSelect.innerHTML = '<option value="">— Статус —</option>';
    reasonSelect.innerHTML = '<option value="">— Причина отказа —</option>';
    statuses.forEach((s) => {
      const opt = document.createElement("option");
      opt.value = s.id;
      opt.textContent = s.name || `Статус #${s.id}`;
      opt.dataset.type = (s.type || "").toLowerCase();
      opt.dataset.name = (s.name || "").toLowerCase();
      statusSelect.appendChild(opt);
    });
    if (STATE.current.status_id != null) {
      const hasOpt = Array.from(statusSelect.options).some((o) => o.value === String(STATE.current.status_id));
      if (hasOpt) statusSelect.value = String(STATE.current.status_id);
    }
    rejectionReasons.forEach((r) => {
      const opt = document.createElement("option");
      opt.value = r.id;
      opt.textContent = r.name || `Причина #${r.id}`;
      reasonSelect.appendChild(opt);
    });
    if (STATE.current.rejection_reason_id != null) {
      const hasOpt = Array.from(reasonSelect.options).some((o) => o.value === String(STATE.current.rejection_reason_id));
      if (hasOpt) reasonSelect.value = String(STATE.current.rejection_reason_id);
    }
    loadMsg.style.display = "none";
  } catch (e) {
    loadMsg.textContent = "Ошибка загрузки статусов.";
    loadMsg.style.color = "#842029";
  }
}

async function onAddVacancyClickFloating(e, btn) {
  e.stopPropagation();
  let canonical = normalizeLinkedInProfileUrl(location.href);
  if (!canonical && IS_MESSAGING_PAGE) {
    try { canonical = await getProfileLinkFromMessaging(); } catch (_) {}
  }
  if (!canonical) return;
  const dropdown = floatingWidgetData?.addVacancyDropdown;
  if (!dropdown) return;
  const isVisible = dropdown.style.display !== "none";
  if (isVisible) {
    dropdown.style.display = "none";
    return;
  }
  dropdown.innerHTML = "<div class='hrhelper-dropdown-msg' style='text-align:center;'>Загрузка...</div>";
  dropdown.style.display = "block";
  if (resolvedWidgetTheme === "dark") dropdown.classList.add("hrhelper-theme-dark"); else dropdown.classList.remove("hrhelper-theme-dark");
  if (dropdown.parentNode !== document.body) {
    document.body.appendChild(dropdown);
  }
  const rect = btn.getBoundingClientRect();
  dropdown.style.position = "fixed";
  dropdown.style.top = (rect.bottom + 4) + "px";
  dropdown.style.right = "12px";
  dropdown.style.left = "auto";
  dropdown.style.width = "280px";

  try {
    const qp = new URLSearchParams({ linkedin_url: canonical });
    const res = await apiFetch("/api/v1/huntflow/linkedin-applicants/available-vacancies/?" + qp.toString(), { method: "GET" });
    const data = await res.json().catch(() => null);
    if (!res.ok || !data?.success) {
      dropdown.innerHTML = "<div class='hrhelper-dropdown-err'>" + (data?.message || "Ошибка") + "</div>";
      return;
    }
    const items = data.items || [];
    if (items.length === 0) {
      dropdown.innerHTML = "<div class='hrhelper-dropdown-msg'>Нет доступных вакансий</div>";
      return;
    }
    dropdown.innerHTML = "";
    items.forEach((v) => {
      const el = document.createElement("div");
      el.style.cssText = "padding:8px 12px;cursor:pointer;font-size:12px;";
      el.textContent = v.vacancy_name || "Вакансия #" + v.vacancy_id;
      el.addEventListener("click", async (ev) => {
        ev.stopPropagation();
        dropdown.style.display = "none";
        await addToVacancyContent(canonical, v.vacancy_id);
        refreshButtonForCurrentProfile();
      });
      el.addEventListener("mouseenter", () => { el.style.background = "var(--hrhelper-btn-bg)"; });
      el.addEventListener("mouseleave", () => { el.style.background = ""; });
      dropdown.appendChild(el);
    });
    setTimeout(() => {
      const closeHandler = (ev) => {
        if (!dropdown.contains(ev.target) && !btn.contains(ev.target)) {
          dropdown.style.display = "none";
          document.removeEventListener("click", closeHandler);
        }
      };
      document.addEventListener("click", closeHandler);
    }, 100);
  } catch (err) {
    logError(" onAddVacancyClickFloating:", err);
    dropdown.innerHTML = "<div class='hrhelper-dropdown-err'>Ошибка</div>";
  }
}

function insertFloatingWidget() {
  if (document.querySelector("[data-hrhelper-floating='true']")) {
    log(" Floating widget already exists");
    return;
  }

  chrome.storage.local.get({ [LINKEDIN_FLOATING_HIDDEN_KEY]: false }, (data) => {
    if (data[LINKEDIN_FLOATING_HIDDEN_KEY]) {
      log(" LinkedIn floating widget hidden by user");
      return;
    }
    loadFloatingUIState(() => {
      const created = createFloatingWidget();
      floatingWidgetData = { wrapper: created.wrapper, body: created.body, statusDropdown: created.statusDropdown, addVacancyDropdown: created.addVacancyDropdown, toggleBtn: created.toggleBtn, titleText: created.titleText, titleIcon: created.titleIcon, actionGroup: created.actionGroup, addVacancyBtn: created.addVacancyBtn, huntflowBtn: created.huntflowBtn, floatingEditBtn: created.floatingEditBtn };
      const wrapper = created.wrapper;
      const body = created.body;
      updateResolvedWidgetTheme().then(() => {
        try {
          if (!chrome.runtime?.id) return;
          applyFloatingWidgetTheme(wrapper);
          applyFloatingBorder(wrapper, computeFloatingBorderColorLinkedIn());
          updateFloatingWidgetTitleIcon(wrapper);
          updateFloatingWidgetHeader();
          populateFloatingWidgetBody(body);
          document.body.appendChild(wrapper);
          makeWidgetDraggable(wrapper, "hrhelper_linkedin_floating_pos", ".hrhelper-widget-header");
          startFloatingWidgetThemeObserver(wrapper);
          log(" Floating widget inserted");
        } catch (e) {
          if (e?.message !== "Extension context invalidated") throw e;
        }
      });
    });
  });
}

function updateFloatingWidgetTitleIcon(w) {
  const icon = w && w.querySelector(".hrhelper-title-icon");
  if (!icon) return;
  const isBlacklist = hasBlacklistLabel(STATE.linkedinFull.candidateInfo);
  icon.src = isBlacklist ? chrome.runtime.getURL("icons/dark-label.png") : chrome.runtime.getURL("icons/icon-32.png");
  const size = isBlacklist ? 30 : 20;
  icon.width = size;
  icon.height = size;
}

function updateFloatingWidget() {
  try {
    if (!chrome.runtime?.id) return;
  } catch (_) {
    return;
  }
  const w = document.querySelector("[data-hrhelper-floating='true']");
  if (!w || !floatingWidgetData) return;
  try {
    applyFloatingWidgetTheme(w);
    applyFloatingBorder(w, computeFloatingBorderColorLinkedIn());
    updateFloatingWidgetTitleIcon(w);
    updateFloatingWidgetHeader();
    if (floatingWidgetData.body) {
      repopulateFloatingWidgetBody();
    }
  } catch (e) {
    if (e?.message !== "Extension context invalidated") throw e;
  }
}

function createWidget(anchorEl, container, isMessaging = false, insertBeforeEl = null) {
  const wrapper = document.createElement("div");
  wrapper.dataset.hrhelperHuntflow = "1";
  
  if (isMessaging) {
    injectFloatingWidgetThemeStyles();
    wrapper.className = "hrhelper-messaging-bar";
    wrapper.style.cssText = "padding:12px 16px;border-bottom:1px solid var(--hrhelper-border,rgba(0,0,0,.08));background:var(--hrhelper-bg,#f3f6f8);display:flex;align-items:center;gap:8px;position:relative;";
    applyMessagingBarTheme(wrapper);
    startMessagingBarThemeObserver();
  } else if (insertBeforeEl) {
    // На странице профиля — блок над "Activity" / "Действия"
    wrapper.style.cssText = "padding:12px 0;margin-bottom:8px;display:flex;align-items:center;gap:8px;flex-wrap:wrap;position:relative;";
  } else {
    // На странице профиля — inline рядом с кнопкой More (fallback)
    wrapper.style.cssText = "margin-left:8px;display:inline-flex;align-items:center;gap:6px;position:relative;";
  }

  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "hrhelper-action-btn";
  btn.style.cssText = "padding:8px 12px;border-radius:999px;border:1px solid rgba(0,0,0,.15);color:#fff;font-weight:600;cursor:pointer;line-height:1;";
  btn.addEventListener("click", onButtonClick);
  wrapper.appendChild(btn);
  
  // Кнопка копирования ссылки (только в режиме "open")
  const copyBtn = document.createElement("button");
  copyBtn.type = "button";
  copyBtn.className = "hrhelper-copy-btn";
  copyBtn.innerHTML = "📋"; // Иконка копирования
  copyBtn.title = "Копировать ссылку на Huntflow";
  copyBtn.style.cssText = "display:none;width:32px;height:32px;border-radius:50%;border:1px solid rgba(0,0,0,.15);background:#17a2b8;color:#fff;font-size:14px;cursor:pointer;padding:0;line-height:1;";
  copyBtn.addEventListener("click", onCopyClick);
  wrapper.appendChild(copyBtn);
  
  // Кнопка редактирования (только в режиме "open")
  const editBtn = document.createElement("button");
  editBtn.type = "button";
  editBtn.className = "hrhelper-edit-btn";
  editBtn.innerHTML = "✏️"; // Иконка карандаша
  editBtn.title = "Редактировать ссылку";
  editBtn.style.cssText = "display:none;width:32px;height:32px;border-radius:50%;border:1px solid rgba(0,0,0,.15);background:#6c757d;color:#fff;font-size:14px;cursor:pointer;padding:0;line-height:1;";
  editBtn.addEventListener("click", onEditClick);
  wrapper.appendChild(editBtn);
  
  // Кнопка изменения статуса (только в режиме "open")
  const statusBtn = document.createElement("button");
  statusBtn.type = "button";
  statusBtn.className = "hrhelper-status-btn";
  statusBtn.title = "Изменить статус";
  statusBtn.style.cssText = "display:none;padding:8px 12px;border-radius:999px;border:1px solid rgba(0,0,0,.15);color:#fff;font-weight:600;cursor:pointer;line-height:1;font-size:12px;white-space:nowrap;";
  statusBtn.addEventListener("click", onStatusClick);
  wrapper.appendChild(statusBtn);

  // Кнопка «+ Взять на другую вакансию» (как в мультивакантном попапе)
  const addVacancyBtn = document.createElement("button");
  addVacancyBtn.type = "button";
  addVacancyBtn.className = "hrhelper-add-vacancy-btn";
  addVacancyBtn.textContent = "+";
  addVacancyBtn.title = "Взять на другую вакансию";
  addVacancyBtn.style.cssText = "display:none;width:32px;height:32px;border-radius:50%;border:1px solid rgba(0,0,0,.15);background:#0a66c2;color:#fff;font-size:18px;font-weight:600;cursor:pointer;padding:0;line-height:1;";
  addVacancyBtn.addEventListener("click", onAddVacancyClick);
  wrapper.appendChild(addVacancyBtn);
  
  // Контейнер для выпадающего списка вакансий
  const addVacancyDropdown = document.createElement("div");
  addVacancyDropdown.className = "hrhelper-add-vacancy-dropdown";
  addVacancyDropdown.style.cssText = "display:none;position:absolute;background:#fff;border:1px solid rgba(0,0,0,.2);border-radius:8px;box-shadow:0 4px 12px rgba(0,0,0,.15);z-index:10000;min-width:200px;max-width:300px;max-height:280px;overflow-y:auto;margin-top:4px;";
  wrapper.appendChild(addVacancyDropdown);
  
  // Контейнер для выпадающих списков статуса
  const statusDropdown = document.createElement("div");
  statusDropdown.className = "hrhelper-status-dropdown";
  statusDropdown.style.cssText = "display:none;position:absolute;background:#fff;border:1px solid rgba(0,0,0,.2);border-radius:8px;box-shadow:0 4px 12px rgba(0,0,0,.15);z-index:10000;min-width:200px;max-width:300px;margin-top:4px;";
  wrapper.appendChild(statusDropdown);

  const inputGroup = document.createElement("div");
  inputGroup.className = "hrhelper-input-group";
  inputGroup.style.cssText = "display:none;align-items:center;gap:8px;flex:1;";

  const input = document.createElement("input");
  input.type = "text";
  input.placeholder = "Ссылка на кандидата (Huntflow или HRHelper)";
  input.className = "hrhelper-input";
  input.style.cssText = isMessaging 
    ? "flex:1;padding:8px 12px;border-radius:8px;border:1px solid rgba(0,0,0,.2);font-size:13px;"
    : "width:260px;max-width:35vw;padding:6px 10px;border-radius:8px;border:1px solid rgba(0,0,0,.2);font-size:12px;";
  input.addEventListener("input", (e) => {
    STATE.current.inputValue = e.target.value;
    document.querySelectorAll(".hrhelper-input").forEach(other => {
      if (other !== input) other.value = STATE.current.inputValue;
    });
  });
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      onSaveLinkClick();
    }
  });

  const saveBtn = document.createElement("button");
  saveBtn.type = "button";
  saveBtn.textContent = "Сохранить";
  saveBtn.className = "hrhelper-save-btn";
  saveBtn.style.cssText = "padding:8px 16px;border-radius:999px;border:1px solid rgba(0,0,0,.15);background:#0a66c2;color:#fff;font-weight:600;cursor:pointer;line-height:1;font-size:13px;";
  saveBtn.addEventListener("click", (e) => {
    e.preventDefault();
    e.stopPropagation();
    log(' Save button clicked');
    onSaveLinkClick();
  });

  const cancelBtn = document.createElement("button");
  cancelBtn.type = "button";
  cancelBtn.textContent = "Отмена";
  cancelBtn.className = "hrhelper-cancel-btn";
  cancelBtn.style.cssText = "padding:8px 16px;border-radius:999px;border:1px solid rgba(0,0,0,.15);background:#6c757d;color:#fff;font-weight:600;cursor:pointer;line-height:1;font-size:13px;";
  cancelBtn.addEventListener("click", onCancelClick);

  inputGroup.appendChild(input);
  inputGroup.appendChild(saveBtn);
  inputGroup.appendChild(cancelBtn);
  wrapper.appendChild(inputGroup);
  
  if (isMessaging) {
    container.insertBefore(wrapper, container.firstChild);
  } else if (insertBeforeEl) {
    container.insertBefore(wrapper, insertBeforeEl);
  } else {
    container.insertBefore(wrapper, anchorEl.nextSibling);
  }

  return { wrapper, btn, input, inputGroup, saveBtn, cancelBtn, editBtn, copyBtn, statusBtn, addVacancyBtn, addVacancyDropdown, statusDropdown };
}

// Функция для определения, является ли статус отказом
const isRejectionStatus = HRH.isRejectionStatus;
if (!isRejectionStatus) {
  throw new Error("[HRHelper] shared/domain/status-logic.js not loaded (isRejectionStatus missing)");
}

function updateWidget(widgets, force) {
  if (!widgets) return;
  const { btn, input, inputGroup, saveBtn, cancelBtn, editBtn, copyBtn, statusBtn, addVacancyBtn, addVacancyDropdown, statusDropdown } = widgets;
  if (!btn || !input || !saveBtn || !inputGroup) return;

  const stateKey = STATE.current.mode + '|' + (STATE.current.appUrl || '') + STATE.current.disabled;
  if (!force && btn.dataset.lastStateKey === stateKey) return;
  btn.dataset.lastStateKey = stateKey;

  if (STATE.current.mode === "open") {
    btn.style.display = "block";
    inputGroup.style.display = "none";
    btn.textContent = STATE.current.text || "Huntflow";
    btn.title = STATE.current.title || "";
    btn.disabled = !!STATE.current.disabled;
    btn.style.background = STATE.current.color || "#0a66c2";
    btn.style.opacity = btn.disabled ? "0.7" : "1";
    
    // Показываем кнопку копирования
    if (copyBtn) {
      copyBtn.style.display = STATE.current.appUrl ? "block" : "none";
    }
    
    // Показываем кнопку редактирования
    if (editBtn) {
      editBtn.style.display = "block";
    }
    
    // Кнопка «Изменить статус»: показываем при любой сохранённой ссылке (приоритет — представление на странице)
    if (statusBtn) {
      if (STATE.current.appUrl) {
        statusBtn.style.display = "block";
        statusBtn.textContent = STATE.current.statusName || "Изменить статус";
        const isRejection = STATE.current.statusName ? isRejectionStatus(STATE.current.statusName) : false;
        statusBtn.style.background = isRejection ? "#dc3545" : "#28a745";
      } else {
        statusBtn.style.display = "none";
      }
    }

    // Кнопка «+ Взять на другую вакансию»: как в мультивакантном попапе
    if (addVacancyBtn) {
      addVacancyBtn.style.display = STATE.current.appUrl ? "block" : "none";
    }
    if (addVacancyDropdown) {
      addVacancyDropdown.style.display = "none";
    }
    
    // Скрываем выпадающий список статуса
    if (statusDropdown) {
      statusDropdown.style.display = "none";
    }
  } else {
    btn.style.display = "none";
    inputGroup.style.display = "flex";
    input.value = STATE.current.inputValue || "";
    input.placeholder = STATE.current.title || "Ссылка на кандидата (Huntflow или HRHelper)";
    saveBtn.disabled = !!STATE.current.disabled;
    saveBtn.style.opacity = saveBtn.disabled ? "0.6" : "1";
    
    // Показываем/скрываем кнопку отмены в зависимости от того, редактируем ли мы существующую ссылку
    if (cancelBtn) {
      // Показываем "Отмена" только если это редактирование (есть сохранённый app_url)
      cancelBtn.style.display = STATE.current.appUrl ? "block" : "none";
    }
    
    // Скрываем кнопку редактирования
    if (editBtn) {
      editBtn.style.display = "none";
    }
    
    // Скрываем кнопку копирования
    if (copyBtn) {
      copyBtn.style.display = "none";
    }
    
    // Скрываем кнопку изменения статуса
    if (statusBtn) {
      statusBtn.style.display = "none";
    }

    // Скрываем кнопку «+ Взять на другую вакансию»
    if (addVacancyBtn) {
      addVacancyBtn.style.display = "none";
    }
    if (addVacancyDropdown) {
      addVacancyDropdown.style.display = "none";
    }
    
    // Скрываем выпадающий список статуса
    if (statusDropdown) {
      statusDropdown.style.display = "none";
    }
  }
}

function ensureButtons(force = false) {
  log(' ensureButtons called, show:', STATE.current.show);
  
  const now = Date.now();
  if (!force && now - STATE.lastScanAt < THROTTLE_MS) {
    log(' Throttled, skipping');
    return;
  }
  STATE.lastScanAt = now;
  
  log(' Creating/updating buttons...');

  Array.from(STATE.buttons.entries()).forEach(([anchorEl, widgetsData]) => {
    if (!anchorEl?.isConnected || !widgetsData?.wrapper?.isConnected) {
      STATE.buttons.delete(anchorEl);
    }
  });

  STATE.suppressObserver = true;
  try {
    if (IS_LINKEDIN) {
      document.querySelectorAll("[data-hrhelper-huntflow='1']").forEach((el) => {
        if (el.getAttribute("data-hrhelper-floating") !== "true" && el.parentNode) el.remove();
      });
      const existingFloating = document.querySelector("[data-hrhelper-floating='true']");
      if (existingFloating) updateFloatingWidget();
      return;
    }
    if (IS_MESSAGING_PAGE) {
      const composer = findMessagingComposer();
      if (composer) {
        if (STATE.buttons.has(composer)) {
          const existing = STATE.buttons.get(composer);
          if (existing?.wrapper?.isConnected) {
            updateWidget(existing, false);
          } else {
            STATE.buttons.delete(composer);
            const widgets = createWidget(null, composer, true);
            STATE.buttons.set(composer, widgets);
            updateWidget(widgets, true);
          }
        } else {
          const widgets = createWidget(null, composer, true);
          STATE.buttons.set(composer, widgets);
          updateWidget(widgets, true);
        }
      }
    }
    if (!IS_MESSAGING_PAGE) {
      const activitySection = findActivitySection();
      if (activitySection && activitySection.parentElement) {
        const container = activitySection.parentElement;
        if (STATE.buttons.has(activitySection)) {
          const existing = STATE.buttons.get(activitySection);
          if (existing?.wrapper?.isConnected) {
            updateWidget(existing, false);
            return;
          }
          STATE.buttons.delete(activitySection);
        }
        const widgets = createWidget(null, container, false, activitySection);
        STATE.buttons.set(activitySection, widgets);
        updateWidget(widgets, true);
      } else {
        let moreButtons = findAllMoreButtons().filter(looksLikeProfileActionArea);
        if (!moreButtons.length) return;

        moreButtons = moreButtons.map(b => {
          const inTop = !!b.closest('[data-view-name="profile-top-card"]') ||
                        !!b.closest(".pv-top-card") ||
                        !!b.closest(".pv-top-card__actions") ||
                        !!b.closest(".pv-top-card-v2-ctas");
          const inSticky = !!b.closest(".scaffold-layout__sticky");
          return { b, weight: inTop ? 0 : inSticky ? 1 : 2 };
        }).sort((x, y) => x.weight - y.weight).slice(0, MAX_WIDGETS).map(x => x.b);

        moreButtons.forEach(moreBtn => {
          if (STATE.buttons.has(moreBtn)) {
            const existing = STATE.buttons.get(moreBtn);
            if (existing?.wrapper?.isConnected) {
              updateWidget(existing, false);
              return;
            }
            STATE.buttons.delete(moreBtn);
          }

          const container = moreBtn?.parentElement || findActionContainer();
          if (!container) return;

          const widgets = createWidget(moreBtn, container, false);
          STATE.buttons.set(moreBtn, widgets);
          updateWidget(widgets, true);
        });
      }
    }
  } finally {
    requestAnimationFrame(() => {
      STATE.suppressObserver = false;
    });
  }
}

// Быстрая проверка: есть ли уже виджет на странице
function hasExistingWidget() {
  return STATE.buttons.size > 0 && Array.from(STATE.buttons.values()).some(w => w?.wrapper?.isConnected);
}

function setButtonState(obj) {
  if (obj.text != null) STATE.current.text = obj.text;
  if (obj.title != null) STATE.current.title = obj.title;
  if (obj.color != null) STATE.current.color = obj.color;
  if (obj.disabled != null) STATE.current.disabled = !!obj.disabled;
  if (obj.statusName != null) STATE.current.statusName = obj.statusName;
  if (obj.status_id !== undefined) STATE.current.status_id = obj.status_id;
  if (obj.rejection_reason_id !== undefined) STATE.current.rejection_reason_id = obj.rejection_reason_id;
  if (obj.vacancy_name !== undefined) STATE.current.vacancy_name = obj.vacancy_name;
  if (obj.vacanciesCount !== undefined) STATE.current.vacanciesCount = obj.vacanciesCount;
  applyStateToAllButtons();
}

function applyStateToAllButtons() {
  STATE.buttons.forEach(widgets => {
    if (!widgets?.wrapper?.isConnected) return;
    updateWidget(widgets, true);
  });
  if (IS_LINKEDIN) updateFloatingWidget();
}

// Кэш статусов в localStorage
function getCachedStatus(linkedinUrl) {
  try {
    const cacheKey = `hrhelper_status_${linkedinUrl}`;
    const cached = localStorage.getItem(cacheKey);
    if (!cached) return null;
    
    const { status, timestamp } = JSON.parse(cached);
    const age = Date.now() - timestamp;
    
    // Кэш валиден 5 минут
    if (age < STATE.CACHE_TTL) {
      return status;
    }
    
    // Устаревший кэш — удаляем
    localStorage.removeItem(cacheKey);
    return null;
  } catch (e) {
    return null;
  }
}

function setCachedStatus(linkedinUrl, status) {
  try {
    const cacheKey = `hrhelper_status_${linkedinUrl}`;
    localStorage.setItem(cacheKey, JSON.stringify({
      status,
      timestamp: Date.now()
    }));
  } catch (e) {
    // Игнорируем ошибки localStorage
  }
}

const apiFetch = HRH.apiFetch;
if (!apiFetch) {
  throw new Error("[HRHelper] shared/api/client.js not loaded (apiFetch missing)");
}

async function checkStatus(linkedinUrl, forceRefresh = false) {
  // Проверяем кэш только если не требуется принудительное обновление
  if (!forceRefresh) {
    const cached = getCachedStatus(linkedinUrl);
    if (cached) {
      return cached;
    }
  } else {
    // При принудительном обновлении очищаем кэш
    try {
      const cacheKey = `hrhelper_status_${linkedinUrl}`;
      localStorage.removeItem(cacheKey);
      log(' Cache cleared for force refresh');
    } catch (e) {
      // Игнорируем ошибки
    }
  }
  
  // Запрашиваем с сервера
  const qp = new URLSearchParams({ linkedin_url: linkedinUrl });
  if (forceRefresh) {
    qp.append('force_refresh', 'true');
  }
  const res = await apiFetch('/api/v1/huntflow/linkedin-applicants/status/?' + qp.toString(), { method: "GET" });

  if (res.status === 401 || res.status === 403) {
    return { authRequired: true };
  }

  const data = await res.json().catch(() => null);
  if (!res.ok) {
    return { error: data?.message || data?.error || 'HTTP ' + res.status };
  }
  
  // Сохраняем в кэш
  setCachedStatus(linkedinUrl, data);
  
  return data;
}

/** GET status-multi: все вакансии кандидата */
async function fetchStatusMulti(linkedinUrl) {
  const fetchStatusMultiShared = HRH.fetchStatusMulti;
  if (!fetchStatusMultiShared) {
    throw new Error("[HRHelper] shared/api/status.js not loaded (fetchStatusMulti missing)");
  }
  const data = await fetchStatusMultiShared({ linkedinUrl });
  if (!data || data.error) return { error: data?.error || "Ошибка" };
  const items = data.items || [];
  const defaultId = data.default_vacancy_id;
  const defaultItem = items.find((i) => i.vacancy_id === defaultId) || items.find((i) => !i.is_hired && !i.is_archived && i.status_type !== "rejected") || items[0];
  return {
    vacancies: items,
    defaultVacancyId: defaultId,
    huntflowUrl: defaultItem?.appurl || null,
    vacancy_name: defaultItem?.vacancy_name ?? null,
    status_name: defaultItem?.status_name ?? null,
    status_id: defaultItem?.status_id ?? null,
    rejection_reason_name: defaultItem?.rejection_reason_name ?? null,
    last_comment_datetime: defaultItem?.last_comment_at ?? null,
  };
}

/**
 * Проверка: является ли LinkedIn-профиль профилем сотрудника (linkedin_url в профиле пользователя).
 * Результат пишется в STATE.linkedinFull.isProfileEmployee и isProfileEmployeeCurrentUser.
 */
async function fetchProfileEmployeeCheck(linkedinUrl) {
  if (!linkedinUrl) return { is_employee_profile: false, is_current_user: false };
  try {
    const qp = new URLSearchParams({ linkedin_url: linkedinUrl });
    const res = await apiFetch("/api/v1/accounts/users/profile-linkedin-check/?" + qp.toString(), { method: "GET" });
    const data = await res.json().catch(() => null);
    if (!res.ok || !data) return { is_employee_profile: false, is_current_user: false };
    STATE.linkedinFull.isProfileEmployee = !!data.is_employee_profile;
    STATE.linkedinFull.isProfileEmployeeCurrentUser = !!data.is_current_user;
    return { is_employee_profile: !!data.is_employee_profile, is_current_user: !!data.is_current_user };
  } catch (e) {
    log(" fetchProfileEmployeeCheck error:", e);
    STATE.linkedinFull.isProfileEmployee = false;
    STATE.linkedinFull.isProfileEmployeeCurrentUser = false;
    return { is_employee_profile: false, is_current_user: false };
  }
}

/** GET candidate-info: ФИО, контакты */
async function fetchCandidateInfo(huntflowUrl) {
  if (!huntflowUrl) return null;
  const qp = new URLSearchParams({ huntflow_url: huntflowUrl });
  const res = await apiFetch("/api/v1/huntflow/linkedin-applicants/candidate-info/?" + qp.toString(), { method: "GET" });
  const data = await res.json().catch(() => null);
  if (!res.ok || !data?.success) return null;
  // Метки: для цвета границы/текста в UI ожидаются объекты с полем color (или background_color, bg_color, border_color, hex)
  const labels = Array.isArray(data.labels) ? data.labels : [];
  return {
    full_name: data.full_name ?? null,
    phone: data.phone ?? null,
    email: data.email ?? null,
    telegram: data.telegram ?? null,
    communication: data.communication ?? null,
    office_readiness: data.office_readiness ?? null,
    level: data.level ?? null,
    labels,
    extra_fields: data.extra_fields && typeof data.extra_fields === "object" ? data.extra_fields : {},
  };
}

function categorizeVacancies(items) {
  return {
    active: (items || []).filter((i) => !i.is_hired && !i.is_archived && i.status_type !== "rejected"),
    rejected: (items || []).filter((i) => i.status_type === "rejected" && !i.is_hired && !i.is_archived),
    archived: (items || []).filter((i) => i.is_archived),
    hired: (items || []).filter((i) => i.is_hired),
  };
}

const formatVacancyDate = HRH.formatVacancyDate;
const formatRejectionDateTime = HRH.formatRejectionDateTime;
if (!formatVacancyDate || !formatRejectionDateTime) {
  throw new Error("[HRHelper] shared/utils/date.js not loaded (formatVacancyDate/formatRejectionDateTime missing)");
}

async function setLink(linkedinUrl, targetUrl) {
  log(' setLink called:', { linkedinUrl, targetUrl });
  // Фрагмент после # в HTTP часто не доходит до сервера — отправляем отдельно
  const payload = { linkedin_url: linkedinUrl, target_url: targetUrl };
  if (targetUrl && targetUrl.includes('#')) {
    const idx = targetUrl.indexOf('#');
    payload.target_url = targetUrl.slice(0, idx);
    payload.target_url_fragment = targetUrl.slice(idx + 1);
  }
  const res = await apiFetch('/api/v1/huntflow/linkedin-applicants/set-link/', {
    method: "POST",
    body: JSON.stringify(payload)
  });
  log(' setLink response:', { ok: res.ok, status: res.status });
  const data = await res.json().catch(() => null);
  log(' setLink data:', data);
  if (!res.ok) {
    const error = data?.message || data?.error || 'HTTP ' + res.status;
    logError(' setLink error:', error);
    return { error };
  }
  
  // Обновляем кэш после сохранения
  // Сохраняем данные, но с пометкой времени, чтобы при следующей проверке
  // (если прошло больше 30 секунд) было принудительное обновление
  if (data && data.success) {
    setCachedStatus(linkedinUrl, data);
    log(' Cache updated after saving link');
  }
  
  return data;
}

async function refreshButtonForCurrentProfile() {
  log(' refreshButtonForCurrentProfile called');
  
  let canonical = normalizeLinkedInProfileUrl(location.href);
  log(' Canonical URL:', canonical);

  // Сначала показываем кнопки в режиме загрузки для мгновенного отображения
  const showLoadingState = () => {
    STATE.current.show = true;
    STATE.current.mode = "input";
    STATE.current.appUrl = null;
    STATE.current.disabled = false;
    STATE.current.title = "Загрузка...";
    STATE.current.text = "Huntflow";
    ensureButtons();
    if (IS_LINKEDIN) insertFloatingWidget();
  };

  // Показываем кнопки сразу, если еще не показаны
  if (!STATE.current.show) {
    showLoadingState();
  }

  if (!canonical && IS_MESSAGING_PAGE) {
    log(' Messaging page, trying to get profile...');
    try {
      canonical = await getProfileLinkFromMessaging();
      log(' Profile from messaging:', canonical);
    } catch (e) {
      logError(' Error getting profile from messaging:', e);
    }
  }

  if (!canonical) {
    warn(' No canonical URL, showing input form');
    STATE.current.show = true;
    STATE.current.mode = "input";
    STATE.current.appUrl = null;
    STATE.current.disabled = false;
    STATE.current.title = "Укажи ссылку на кандидата";
    ensureButtons();
    if (IS_LINKEDIN) insertFloatingWidget();
    return;
  }
  
  // Проверяем кэш для мгновенного отображения
  // При перезагрузке страницы делаем принудительное обновление, если кэш старше 30 секунд
  const cached = getCachedStatus(canonical);
  let shouldForceRefresh = false;
  if (cached) {
    try {
      const cacheKey = `hrhelper_status_${canonical}`;
      const cachedData = localStorage.getItem(cacheKey);
      if (cachedData) {
        const { timestamp } = JSON.parse(cachedData);
        const age = Date.now() - timestamp;
        // Если кэш старше 30 секунд, делаем принудительное обновление при перезагрузке
        if (age > 30 * 1000) {
          shouldForceRefresh = true;
          log(' Cache is older than 30 seconds, forcing refresh');
        }
      }
    } catch (e) {
      // Игнорируем ошибки
    }
  }
  
  // Проверяем, есть ли в кэше vacancy_name и status_name
  // Если их нет, делаем принудительное обновление
  if (cached && cached.exists && cached.app_url) {
    const hasVacancyOrStatus = cached.vacancy_name !== undefined || cached.status_name !== undefined;
    if (!hasVacancyOrStatus && !shouldForceRefresh) {
      log(' Cached data missing vacancy_name or status_name, forcing refresh');
      shouldForceRefresh = true;
    }
  }
  
  if (cached && cached.exists !== undefined && !shouldForceRefresh) {
    log(' Using cached status for instant display');
    STATE.current.show = true;
    if (cached.exists && cached.app_url) {
      STATE.current.mode = "open";
      STATE.current.appUrl = cached.app_url;
      STATE.current.disabled = false;
      // Формируем текст кнопки: "Huntflow | Название вакансии" (без статуса)
      let buttonText = "Huntflow";
      if (cached.vacancy_name) {
        buttonText = `Huntflow | ${cached.vacancy_name}`;
      }
      setButtonState({ text: buttonText, disabled: false, title: "Открыть в Huntflow", color: "#0a66c2", statusName: cached.status_name, vacancy_name: cached.vacancy_name ?? null, vacanciesCount: cached.vacancies_count ?? 1 });
      (async () => {
        const multi = await fetchStatusMulti(canonical);
        if (!multi.error && multi.vacancies) {
          STATE.linkedinFull.vacancies = multi.vacancies;
          STATE.linkedinFull.defaultVacancyId = multi.defaultVacancyId;
          STATE.linkedinFull.selectedVacancyId = multi.defaultVacancyId ?? multi.vacancies[0]?.vacancy_id;
          STATE.linkedinFull.last_comment_datetime = multi.last_comment_datetime;
          STATE.linkedinFull.rejection_reason_name = multi.rejection_reason_name;
          STATE.current.vacanciesCount = multi.vacancies.length;
          const selId = STATE.linkedinFull.selectedVacancyId ?? STATE.linkedinFull.defaultVacancyId;
          const selectedItem = multi.vacancies.find((v) => v.vacancy_id === selId) || multi.vacancies[0];
          if (selectedItem) {
            STATE.current.statusName = selectedItem.status_name ?? STATE.current.statusName ?? null;
            STATE.current.status_id = selectedItem.status_id ?? STATE.current.status_id ?? null;
            STATE.current.rejection_reason_id = selectedItem.rejection_reason_id ?? STATE.current.rejection_reason_id ?? null;
            STATE.current.vacancy_name = selectedItem.vacancy_name ?? STATE.current.vacancy_name ?? null;
            STATE.current.appUrl = selectedItem.appurl ?? STATE.current.appUrl ?? null;
          }
          const info = await fetchCandidateInfo(multi.huntflowUrl || cached.app_url);
          STATE.linkedinFull.candidateInfo = info;
          await fetchProfileEmployeeCheck(canonical);
          if (IS_LINKEDIN) { repopulateFloatingWidgetBody(); updateFloatingWidget(); }
        }
      })();
    } else {
      STATE.current.mode = "input";
      STATE.current.appUrl = null;
      STATE.current.disabled = false;
      STATE.linkedinFull.vacancies = [];
      STATE.linkedinFull.candidateInfo = null;
      setButtonState({ text: "Huntflow", disabled: false, title: "Укажи ссылку на кандидата", color: "#0a66c2", vacancy_name: null, vacanciesCount: 0 });
      (async () => {
        await fetchProfileEmployeeCheck(canonical);
        if (IS_LINKEDIN) { repopulateFloatingWidgetBody(); updateFloatingWidget(); }
      })();
    }
    ensureButtons();
    if (IS_LINKEDIN) insertFloatingWidget();
    // Продолжаем обновление в фоне
  }
  
  if (STATE.statusFetchedFor === canonical) {
    log(' Status already fetched, applying state');
    applyStateToAllButtons();
    return;
  }
  
  if (STATE.apiCallsThisProfile >= 1) {
    log(' API call limit reached');
    return;
  }

  log(' Fetching status from API...');
  
  if (!STATE.statusInFlight) {
    STATE.apiCallsThisProfile += 1;
    // Используем принудительное обновление, если кэш устарел
    STATE.statusInFlight = checkStatus(canonical, shouldForceRefresh).finally(() => {
      STATE.statusInFlight = null;
    });
  }

  const status = await STATE.statusInFlight;
  
  log(' Status received:', status);
  log(' Status fields:', { 
    vacancy_name: status?.vacancy_name, 
    status_name: status?.status_name,
    exists: status?.exists,
    app_url: status?.app_url 
  });
  
  if (status.authRequired || status.error) {
    warn(' Auth required or error:', status.error || 'No token');
    STATE.current.show = true;
    STATE.current.mode = "input";
    STATE.current.appUrl = null;
    STATE.current.disabled = true;
    STATE.current.title = status.error || "Нужна авторизация (проверь API Token в настройках расширения)";
    ensureButtons();
    if (IS_LINKEDIN) insertFloatingWidget();
    STATE.statusFetchedFor = canonical;
    return;
  }

  STATE.current.show = true;
  if (status.exists && status.app_url) {
    log(' Candidate exists, showing button');
    log(' Status data:', { vacancy_name: status.vacancy_name, status_name: status.status_name, app_url: status.app_url });
    STATE.current.mode = "open";
    STATE.current.appUrl = status.app_url;
    STATE.current.disabled = false;
    
    // Формируем текст кнопки: "Huntflow | Название вакансии" (без статуса)
    let buttonText = "Huntflow";
    if (status.vacancy_name) {
      buttonText = `Huntflow | ${status.vacancy_name}`;
    }
    
    log(' Button text:', buttonText);
    setButtonState({ text: buttonText, disabled: false, title: "Открыть в Huntflow", color: "#0a66c2", statusName: status.status_name, vacancy_name: status.vacancy_name ?? null, vacanciesCount: status.vacancies_count ?? 1 });
    (async () => {
      const multi = await fetchStatusMulti(canonical);
      if (!multi.error && multi.vacancies) {
        STATE.linkedinFull.vacancies = multi.vacancies;
        STATE.linkedinFull.defaultVacancyId = multi.defaultVacancyId;
        STATE.linkedinFull.selectedVacancyId = multi.defaultVacancyId ?? multi.vacancies[0]?.vacancy_id;
        STATE.linkedinFull.last_comment_datetime = multi.last_comment_datetime;
        STATE.linkedinFull.rejection_reason_name = multi.rejection_reason_name;
        STATE.current.vacanciesCount = multi.vacancies.length;
        const selId = STATE.linkedinFull.selectedVacancyId ?? STATE.linkedinFull.defaultVacancyId;
        const selectedItem = multi.vacancies.find((v) => v.vacancy_id === selId) || multi.vacancies[0];
        if (selectedItem) {
          STATE.current.statusName = selectedItem.status_name ?? STATE.current.statusName ?? null;
          STATE.current.status_id = selectedItem.status_id ?? STATE.current.status_id ?? null;
          STATE.current.rejection_reason_id = selectedItem.rejection_reason_id ?? STATE.current.rejection_reason_id ?? null;
          STATE.current.vacancy_name = selectedItem.vacancy_name ?? STATE.current.vacancy_name ?? null;
          STATE.current.appUrl = selectedItem.appurl ?? STATE.current.appUrl ?? null;
        }
        const info = await fetchCandidateInfo(multi.huntflowUrl || status.app_url);
        STATE.linkedinFull.candidateInfo = info;
        await fetchProfileEmployeeCheck(canonical);
        if (IS_LINKEDIN) { repopulateFloatingWidgetBody(); updateFloatingWidget(); }
      }
    })();
    } else {
      log(' Candidate not found, showing input');
    STATE.current.mode = "input";
    STATE.current.appUrl = null;
    STATE.current.disabled = false;
    STATE.linkedinFull.vacancies = [];
    STATE.linkedinFull.candidateInfo = null;
    STATE.linkedinFull.selectedVacancyId = null;
    setButtonState({ text: "Huntflow", disabled: false, title: "Укажи ссылку на кандидата", color: "#0a66c2", vacancy_name: null, vacanciesCount: 0 });
    (async () => {
      await fetchProfileEmployeeCheck(canonical);
      if (IS_LINKEDIN) { repopulateFloatingWidgetBody(); updateFloatingWidget(); }
    })();
  }
  ensureButtons();
  if (IS_LINKEDIN) insertFloatingWidget();
  STATE.statusFetchedFor = canonical;
}

async function onSaveLinkClick() {
  log(' onSaveLinkClick called');

  if (STATE.busy) {
    log(' Already busy, ignoring click');
    return;
  }

  removeFloatingEditEscHandler();

  let canonical = normalizeLinkedInProfileUrl(location.href);
  log(' Canonical URL:', canonical);
  
  if (!canonical && IS_MESSAGING_PAGE) {
    try {
      canonical = await getProfileLinkFromMessaging();
      log(' Profile from messaging:', canonical);
    } catch (e) {
      logError(' Error getting profile from messaging:', e);
    }
  }

  if (!canonical) {
    logError(' No canonical URL found');
    STATE.current.title = "Не удалось определить профиль LinkedIn";
    applyStateToAllButtons();
    return;
  }
  
  if (STATE.apiCallsThisProfile >= 2) {
    warn(' API call limit reached');
    return;
  }

  const target = (STATE.current.inputValue || "").trim();
  log(' Target URL:', target);
  
  if (!target) {
    log(' No target URL provided');
    STATE.current.title = "Вставь ссылку на кандидата";
    applyStateToAllButtons();
    return;
  }

  try {
    STATE.busy = true;
    
    // Показываем индикатор загрузки
    STATE.current.title = "Сохранение...";
    STATE.current.disabled = true;
    applyStateToAllButtons();
    
    STATE.apiCallsThisProfile += 1;
    log(' Calling setLink...');
    const saved = await setLink(canonical, target);
    log(' setLink result:', saved);
    log(' setLink fields:', { 
      vacancy_name: saved?.vacancy_name, 
      status_name: saved?.status_name,
      app_url: saved?.app_url 
    });
    
    if (saved?.error) {
      logError(' Save error:', saved.error);
      STATE.current.title = saved.error;
      STATE.current.disabled = false;
      applyStateToAllButtons();
      return;
    }
    
    if (!saved || (!saved.app_url && !saved.target_url)) {
      logError(' Save failed: no URL in response', saved);
      STATE.current.title = "Ошибка сохранения: нет ссылки в ответе";
      STATE.current.disabled = false;
      applyStateToAllButtons();
      return;
    }
    
    const finalUrl = saved.app_url || saved.target_url;
    log(' Saved! Final URL:', finalUrl);
    
    // Сохраняем маппинг thread_id -> profile_url, если мы на странице профиля
    if (IS_PROFILE_PAGE && canonical) {
      log(' onSaveLinkClick: attempting to save thread mapping for profile page');
      const saveThreadMapping = (threadId) => {
        if (!threadId) {
          log(' saveThreadMapping: threadId is empty');
          return false;
        }
        
        log(' Saving thread mapping after link save:', threadId.substring(0, 10) + '... -> ' + canonical);
        try {
          const mapping = JSON.parse(localStorage.getItem('hrhelper_thread_profile_map') || '{}');
          mapping[threadId] = canonical;
          localStorage.setItem('hrhelper_thread_profile_map', JSON.stringify(mapping));
          saveThreadMappingToBackend(threadId, canonical);
          return true;
        } catch (e) {
          logError(' Error saving thread mapping after link save:', e);
          return false;
        }
      };
      
      // Пробуем найти thread_id сразу
      let threadId = extractThreadIdFromMessageButton();
      if (threadId) {
        saveThreadMapping(threadId);
      } else {
        log(' Thread ID not found immediately, will retry with delays');
        // Если thread_id не найден сразу, пробуем найти его через задержки
        // (кнопка Message может появиться позже при динамической загрузке)
        const delays = [500, 1000, 2000, 3000, 5000];
        delays.forEach(delay => {
          setTimeout(() => {
            const delayedThreadId = extractThreadIdFromMessageButton();
            if (delayedThreadId) {
              log(' Found thread_id after delay, saving mapping:', delayedThreadId.substring(0, 10) + '... -> ' + canonical);
              saveThreadMapping(delayedThreadId);
            }
          }, delay);
        });
      }
    }
    
    STATE.current.mode = "open";
    STATE.current.appUrl = finalUrl;
    STATE.current.title = "Открыть в Huntflow";
    STATE.current.disabled = false;
    
    // Обновляем текст кнопки с названием вакансии (без статуса)
    let buttonText = "Huntflow";
    if (saved.vacancy_name) {
      buttonText = `Huntflow | ${saved.vacancy_name}`;
    }
    log(' Button text after save:', buttonText);
    setButtonState({ text: buttonText, disabled: false, title: "Открыть в Huntflow", color: "#0a66c2", statusName: saved.status_name, vacancy_name: saved.vacancy_name ?? null, vacanciesCount: saved.vacancies_count ?? 1 });

    (async () => {
      const multi = await fetchStatusMulti(canonical);
      if (!multi.error && multi.vacancies) {
        STATE.linkedinFull.vacancies = multi.vacancies;
        STATE.linkedinFull.defaultVacancyId = multi.defaultVacancyId;
        STATE.linkedinFull.selectedVacancyId = multi.defaultVacancyId ?? multi.vacancies[0]?.vacancy_id;
        STATE.linkedinFull.last_comment_datetime = multi.last_comment_datetime;
        STATE.linkedinFull.rejection_reason_name = multi.rejection_reason_name;
        STATE.current.vacanciesCount = multi.vacancies.length;
        const selId = STATE.linkedinFull.selectedVacancyId ?? STATE.linkedinFull.defaultVacancyId;
        const selectedItem = multi.vacancies.find((v) => v.vacancy_id === selId) || multi.vacancies[0];
        if (selectedItem) {
          STATE.current.statusName = selectedItem.status_name ?? STATE.current.statusName ?? null;
          STATE.current.status_id = selectedItem.status_id ?? STATE.current.status_id ?? null;
          STATE.current.rejection_reason_id = selectedItem.rejection_reason_id ?? STATE.current.rejection_reason_id ?? null;
          STATE.current.vacancy_name = selectedItem.vacancy_name ?? STATE.current.vacancy_name ?? null;
          STATE.current.appUrl = selectedItem.appurl ?? STATE.current.appUrl ?? null;
        }
        const info = await fetchCandidateInfo(multi.huntflowUrl || finalUrl);
        STATE.linkedinFull.candidateInfo = info;
        await fetchProfileEmployeeCheck(canonical);
        if (IS_LINKEDIN) { repopulateFloatingWidgetBody(); updateFloatingWidget(); }
      }
    })();

    // Сбрасываем счетчик API вызовов для этого профиля, чтобы можно было обновить статус
    STATE.apiCallsThisProfile = 0;
    STATE.statusFetchedFor = null;

    applyStateToAllButtons();
  } catch (e) {
    logError(' Exception in onSaveLinkClick:', e);
    STATE.current.title = "Ошибка: " + (e.message || String(e));
    STATE.current.disabled = false;
    applyStateToAllButtons();
  } finally {
    STATE.busy = false;
  }
}

async function onButtonClick() {
  if (STATE.busy) return;
  let canonical = normalizeLinkedInProfileUrl(location.href);

  if (!canonical && IS_MESSAGING_PAGE) {
    try {
      canonical = await getProfileLinkFromMessaging();
    } catch (e) {
      logError(' Error getting profile from messaging:', e);
    }
  }

  if (!canonical) return;
  const mode = STATE.current.mode || "idle";
  if (mode === "open" && STATE.current.appUrl) {
    window.open(STATE.current.appUrl, "_blank", "noopener,noreferrer");
  }
}

async function onEditClick(e) {
  e.stopPropagation();

  log(' Edit button clicked');

  if (STATE.current.mode === "input") {
    removeFloatingEditEscHandler();
    STATE.current.mode = "open";
    STATE.current.appUrl = STATE.current.originalAppUrl;
    STATE.current.inputValue = "";
    STATE.current.disabled = false;
    STATE.current.title = "Открыть в Huntflow";
    STATE.current.originalAppUrl = null;
    applyStateToAllButtons();
    return;
  }

  STATE.current.originalAppUrl = STATE.current.appUrl;
  STATE.current.mode = "input";
  STATE.current.inputValue = STATE.current.appUrl || "";
  STATE.current.disabled = false;
  STATE.current.title = "Редактировать ссылку";

  removeFloatingEditEscHandler();
  floatingEditEscHandler = (ev) => {
    if (ev.key !== "Escape") return;
    removeFloatingEditEscHandler();
    STATE.current.mode = "open";
    STATE.current.appUrl = STATE.current.originalAppUrl;
    STATE.current.inputValue = "";
    STATE.current.disabled = false;
    STATE.current.title = "Открыть в Huntflow";
    STATE.current.originalAppUrl = null;
    applyStateToAllButtons();
  };
  document.addEventListener("keydown", floatingEditEscHandler);

  applyStateToAllButtons();
}

async function onCancelClick(e) {
  e.stopPropagation();

  log(' Cancel button clicked');

  removeFloatingEditEscHandler();
  STATE.current.mode = "open";
  STATE.current.appUrl = STATE.current.originalAppUrl;
  STATE.current.inputValue = "";
  STATE.current.disabled = false;
  STATE.current.title = "Открыть в Huntflow";
  STATE.current.originalAppUrl = null;

  applyStateToAllButtons();
}

async function onCopyClick(e) {
  e.stopPropagation();

  log(' Copy button clicked');

  if (!STATE.current.appUrl) {
    log(' No URL to copy');
    return;
  }

  try {
    await navigator.clipboard.writeText(STATE.current.appUrl);
    log(' URL copied to clipboard:', STATE.current.appUrl);
    
    // Визуальная обратная связь - временно меняем иконку
    const copyBtn = e.target.closest('.hrhelper-copy-btn');
    if (copyBtn) {
      const originalHTML = copyBtn.innerHTML;
      copyBtn.innerHTML = "✓";
      copyBtn.style.background = "#28a745";
      setTimeout(() => {
        copyBtn.innerHTML = originalHTML;
      }, 1000);
    }
  } catch (err) {
    logError(' Failed to copy URL:', err);
    // Fallback для старых браузеров
    const textArea = document.createElement("textarea");
    textArea.value = STATE.current.appUrl;
    textArea.style.position = "fixed";
    textArea.style.left = "-999999px";
    document.body.appendChild(textArea);
    textArea.focus();
    textArea.select();
    try {
      document.execCommand('copy');
      log(' URL copied using fallback method');
    } catch (fallbackErr) {
      logError(' Fallback copy also failed:', fallbackErr);
    }
    document.body.removeChild(textArea);
  }
}

async function onStatusClick(e) {
  if (!e || !e.target) return;
  if (typeof e.stopPropagation === 'function') e.stopPropagation();
  
  log(' Status button clicked');
  
  let canonical = normalizeLinkedInProfileUrl(location.href);
  if (!canonical && IS_MESSAGING_PAGE) {
    try {
      canonical = await getProfileLinkFromMessaging();
    } catch (err) {
      logError(' Error getting profile from messaging:', err);
    }
  }
  
  if (!canonical) {
    logError(' No canonical URL found');
    return;
  }
  
  // Находим выпадающий список для этого виджета
  const statusBtn = e.target.closest('.hrhelper-status-btn');
  if (!statusBtn) return;
  
  const wrapper = statusBtn.closest('[data-hrhelper-huntflow="1"]');
  if (!wrapper) return;
  
  const statusDropdown = wrapper.querySelector('.hrhelper-status-dropdown');
  if (!statusDropdown) return;
  
  // Переключаем видимость выпадающего списка
  const isVisible = statusDropdown.style.display !== 'none';
  if (isVisible) {
    statusDropdown.style.display = 'none';
    return;
  }
  
  // Показываем загрузку
  statusDropdown.innerHTML = '<div class="hrhelper-dropdown-msg" style="text-align:center;">Загрузка...</div>';
  statusDropdown.style.display = 'block';
  
  // Позиционируем выпадающий список (position: fixed — координаты относительно viewport)
  const rect = statusBtn.getBoundingClientRect();
  const viewportWidth = window.innerWidth;
  const viewportHeight = window.innerHeight;
  
  let left = rect.left;
  let top = rect.bottom + 4;
  
  // Проверяем, не выходит ли список за правую границу экрана
  if (left + 300 > viewportWidth) {
    left = viewportWidth - 300 - 10;
  }
  
  // Проверяем, не выходит ли список за нижнюю границу экрана
  if (top + 300 > viewportHeight) {
    top = rect.top - 300 - 4;
  }
  
  statusDropdown.style.position = 'fixed';
  statusDropdown.style.top = `${top}px`;
  statusDropdown.style.left = `${left}px`;
  
  try {
    // Получаем список статусов и причин отказа
    const qp = new URLSearchParams({ linkedin_url: canonical });
    const res = await apiFetch('/api/v1/huntflow/linkedin-applicants/status-options/?' + qp.toString(), { method: "GET" });
    
    if (!res.ok) {
      const data = await res.json().catch(() => null);
      statusDropdown.innerHTML = `<div class="hrhelper-dropdown-err">Ошибка: ${data?.message || 'Не удалось загрузить статусы'}</div>`;
      return;
    }
    
    const data = await res.json().catch(() => null);
    if (!data || !data.success) {
      statusDropdown.innerHTML = '<div class="hrhelper-dropdown-err">Ошибка загрузки статусов</div>';
      return;
    }
    
    const statuses = data.statuses || [];
    const rejectionReasons = data.rejection_reasons || [];
    
    // Создаем выпадающий список
    createStatusDropdown(statusDropdown, statuses, rejectionReasons, canonical);
    
    // Закрываем выпадающий список при клике вне его
    setTimeout(() => {
      const closeHandler = (event) => {
        if (!statusDropdown.contains(event.target) && !statusBtn.contains(event.target)) {
          statusDropdown.style.display = 'none';
          document.removeEventListener('click', closeHandler);
        }
      };
      document.addEventListener('click', closeHandler);
    }, 100);
    
  } catch (err) {
    logError(' Error loading status options:', err);
    statusDropdown.innerHTML = '<div class="hrhelper-dropdown-err">Ошибка загрузки</div>';
  }
}

async function onAddVacancyClick(e) {
  e.stopPropagation();

  let canonical = normalizeLinkedInProfileUrl(location.href);
  if (!canonical && IS_MESSAGING_PAGE) {
    try {
      canonical = await getProfileLinkFromMessaging();
    } catch (err) {
      logError(' Error getting profile from messaging:', err);
    }
  }

  if (!canonical) {
    logError(' No canonical URL found');
    return;
  }

  const addVacancyBtn = e.target.closest('.hrhelper-add-vacancy-btn');
  if (!addVacancyBtn) return;

  const wrapper = addVacancyBtn.closest('[data-hrhelper-huntflow="1"]');
  if (!wrapper) return;

  const addVacancyDropdown = wrapper.querySelector('.hrhelper-add-vacancy-dropdown');
  if (!addVacancyDropdown) return;

  const isVisible = addVacancyDropdown.style.display !== 'none';
  if (isVisible) {
    addVacancyDropdown.style.display = 'none';
    return;
  }

  addVacancyDropdown.innerHTML = '<div class="hrhelper-dropdown-msg" style="text-align:center;">Загрузка…</div>';
  addVacancyDropdown.style.display = 'block';

  const rect = addVacancyBtn.getBoundingClientRect();
  const viewportWidth = window.innerWidth;
  const viewportHeight = window.innerHeight;
  let left = rect.left + window.scrollX;
  let top = rect.bottom + window.scrollY + 4;
  if (left + 300 > viewportWidth) left = viewportWidth - 300 - 10;
  if (top + 280 > viewportHeight + window.scrollY) top = rect.top + window.scrollY - 280 - 4;
  addVacancyDropdown.style.position = 'fixed';
  addVacancyDropdown.style.top = `${top}px`;
  addVacancyDropdown.style.left = `${left}px`;

  try {
    const qp = new URLSearchParams({ linkedin_url: canonical });
    const res = await apiFetch('/api/v1/huntflow/linkedin-applicants/available-vacancies/?' + qp.toString(), { method: "GET" });

    const data = await res.json().catch(() => null);
    if (!res.ok || !data?.success) {
      addVacancyDropdown.innerHTML = '<div class="hrhelper-dropdown-err">' + (data?.message || 'Ошибка загрузки') + '</div>';
      return;
    }

    const items = data.items || [];
    if (items.length === 0) {
      addVacancyDropdown.innerHTML = '<div class="hrhelper-dropdown-msg">Нет доступных вакансий</div>';
      return;
    }

    addVacancyDropdown.innerHTML = '';
    items.forEach((v) => {
      const el = document.createElement("div");
      el.style.cssText = "padding:8px 12px;cursor:pointer;border-bottom:1px solid rgba(0,0,0,.05);";
      el.textContent = v.vacancy_name || `Вакансия #${v.vacancy_id}`;
      el.addEventListener("click", async (ev) => {
        ev.stopPropagation();
        addVacancyDropdown.style.display = "none";
        await addToVacancyContent(canonical, v.vacancy_id);
      });
      el.addEventListener("mouseenter", () => { el.style.background = "var(--hrhelper-btn-bg)"; });
      el.addEventListener("mouseleave", () => { el.style.background = ""; });
      addVacancyDropdown.appendChild(el);
    });

    setTimeout(() => {
      const closeHandler = (ev) => {
        if (!addVacancyDropdown.contains(ev.target) && !addVacancyBtn.contains(ev.target)) {
          addVacancyDropdown.style.display = "none";
          document.removeEventListener("click", closeHandler);
        }
      };
      document.addEventListener("click", closeHandler);
    }, 100);
  } catch (err) {
    logError(' Error loading available vacancies:', err);
    addVacancyDropdown.innerHTML = '<div class="hrhelper-dropdown-err">Ошибка загрузки</div>';
  }
}

async function addToVacancyContent(linkedinUrl, vacancyId) {
  try {
    const res = await apiFetch('/api/v1/huntflow/linkedin-applicants/add-to-vacancy/', {
      method: "POST",
      body: JSON.stringify({ linkedin_url: linkedinUrl, vacancy_id: vacancyId }),
    });
    const data = await res.json().catch(() => null);
    if (res.ok && data?.success) {
      log(' Candidate added to vacancy successfully');
      try {
        localStorage.removeItem(`hrhelper_status_${linkedinUrl}`);
      } catch (_) {}
      refreshButtonForCurrentProfile();
    } else {
      logError(' addToVacancy error:', data?.message || 'Ошибка добавления');
    }
  } catch (err) {
    logError(' addToVacancy error:', err);
  }
}

function createStatusDropdown(container, statuses, rejectionReasons, linkedinUrl) {
  // Сохраняем данные в контейнере для возможности возврата
  container.dataset.statuses = JSON.stringify(statuses);
  container.dataset.rejectionReasons = JSON.stringify(rejectionReasons);
  container.dataset.linkedinUrl = linkedinUrl;
  container.dataset.currentView = 'statuses';
  
  showStatusesList(container, statuses, rejectionReasons, linkedinUrl);
}

function showStatusesList(container, statuses, rejectionReasons, linkedinUrl) {
  container.innerHTML = '';
  container.dataset.currentView = 'statuses';
  
  if (statuses.length === 0) {
    container.innerHTML = '<div class="hrhelper-dropdown-msg">Нет доступных статусов</div>';
    return;
  }
  
  // Создаем список статусов
  const statusList = document.createElement('div');
  statusList.style.cssText = "max-height:300px;overflow-y:auto;";
  
  statuses.forEach(status => {
    const statusItem = document.createElement('div');
    statusItem.className = 'hrhelper-status-item';
    statusItem.dataset.statusId = status.id;
    statusItem.dataset.statusName = status.name || '';
    statusItem.style.cssText = "padding:8px 12px;cursor:pointer;border-bottom:1px solid var(--hrhelper-border);";
    statusItem.textContent = status.name || `Статус #${status.id}`;
    
    // Определяем, является ли статус отказом
    // Проверяем тип статуса и название
    const statusType = status.type || '';
    const statusName = (status.name || '').toLowerCase();
    const isRejection = statusType === 'rejected' || 
                       statusType === 'rejection' ||
                       statusName.includes('отказ') || 
                       statusName.includes('reject') ||
                       statusName.includes('rejected') ||
                       statusName.includes('отклонен');
    
    if (isRejection && rejectionReasons.length > 0) {
      // Для статуса отказа при клике показываем список причин отказа
      statusItem.addEventListener('click', (e) => {
        e.stopPropagation();
        showRejectionReasonsList(container, rejectionReasons, status.id, linkedinUrl);
      });
    } else {
      // Для обычных статусов добавляем обработчик клика
      statusItem.addEventListener('click', async (e) => {
        e.stopPropagation();
        const vid = STATE.linkedinFull?.selectedVacancyId ?? STATE.linkedinFull?.defaultVacancyId;
        await updateStatus(linkedinUrl, status.id, null, vid);
        container.style.display = 'none';
      });
    }
    
    statusItem.addEventListener('mouseenter', () => {
      statusItem.style.background = 'var(--hrhelper-btn-bg)';
    });
    
    statusItem.addEventListener('mouseleave', () => {
      statusItem.style.background = '';
    });
    
    statusList.appendChild(statusItem);
  });
  
  container.appendChild(statusList);
}

function showRejectionReasonsList(container, rejectionReasons, statusId, linkedinUrl) {
  container.innerHTML = '';
  container.dataset.currentView = 'rejection_reasons';
  container.dataset.selectedStatusId = statusId;
  
  if (rejectionReasons.length === 0) {
    container.innerHTML = '<div class="hrhelper-dropdown-msg">Нет доступных причин отказа</div>';
    return;
  }
  
  // Кнопка "Назад"
  const backButton = document.createElement('div');
  backButton.className = 'hrhelper-back-button';
  backButton.style.cssText = "padding:8px 12px;cursor:pointer;border-bottom:2px solid var(--hrhelper-border);background:var(--hrhelper-btn-bg);font-weight:600;display:flex;align-items:center;gap:8px;";
  backButton.innerHTML = '← Назад';
  
  backButton.addEventListener('click', (e) => {
    e.stopPropagation();
    const statuses = JSON.parse(container.dataset.statuses || '[]');
    const rejectionReasonsData = JSON.parse(container.dataset.rejectionReasons || '[]');
    const linkedinUrlData = container.dataset.linkedinUrl;
    showStatusesList(container, statuses, rejectionReasonsData, linkedinUrlData);
  });
  
  backButton.addEventListener('mouseenter', () => {
    backButton.style.background = 'var(--hrhelper-border)';
  });
  
  backButton.addEventListener('mouseleave', () => {
    backButton.style.background = 'var(--hrhelper-btn-bg)';
  });
  
  container.appendChild(backButton);
  
  // Создаем список причин отказа
  const reasonsList = document.createElement('div');
  reasonsList.style.cssText = "max-height:300px;overflow-y:auto;";
  
  rejectionReasons.forEach(reason => {
    const reasonItem = document.createElement('div');
    reasonItem.className = 'hrhelper-rejection-reason-item';
    reasonItem.dataset.reasonId = reason.id;
    reasonItem.style.cssText = "padding:8px 12px;cursor:pointer;border-bottom:1px solid var(--hrhelper-border);";
    reasonItem.textContent = reason.name || `Причина #${reason.id}`;
    
    reasonItem.addEventListener('click', async (e) => {
      e.stopPropagation();
      const vid = STATE.linkedinFull?.selectedVacancyId ?? STATE.linkedinFull?.defaultVacancyId;
      await updateStatus(linkedinUrl, statusId, reason.id, vid);
      container.style.display = 'none';
    });
    
    reasonItem.addEventListener('mouseenter', () => {
      reasonItem.style.background = 'var(--hrhelper-btn-bg)';
    });
    
    reasonItem.addEventListener('mouseleave', () => {
      reasonItem.style.background = '';
    });
    
    reasonsList.appendChild(reasonItem);
  });
  
  container.appendChild(reasonsList);
}


async function updateStatus(linkedinUrl, statusId, rejectionReasonId, vacancyId, comment) {
  log(' Updating status:', { linkedinUrl, statusId, rejectionReasonId, vacancyId });
  const body = {
    linkedin_url: linkedinUrl,
    status_id: statusId,
    rejection_reason_id: rejectionReasonId || null
  };
  if (vacancyId != null) body.vacancy_id = vacancyId;
  if (comment && String(comment).trim()) body.comment = String(comment).trim();
  try {
    const res = await apiFetch('/api/v1/huntflow/linkedin-applicants/update-status/', {
      method: "POST",
      body: JSON.stringify(body)
    });
    
    if (!res.ok) {
      const data = await res.json().catch(() => null);
      logError(' Failed to update status:', data?.message || 'Unknown error');
      alert(`Ошибка обновления статуса: ${data?.message || 'Неизвестная ошибка'}`);
      return;
    }
    
    const data = await res.json().catch(() => null);
    if (data && data.success) {
      log(' Status updated successfully');
      
      // Очищаем кэш и обновляем статус
      try {
        const cacheKey = `hrhelper_status_${linkedinUrl}`;
        localStorage.removeItem(cacheKey);
      } catch (e) {
        // Игнорируем ошибки
      }
      
      // Обновляем кнопку с новым статусом
      STATE.statusFetchedFor = null;
      STATE.apiCallsThisProfile = 0;
      await refreshButtonForCurrentProfile();
      
      // Обновление кнопки статуса произойдет автоматически через refreshButtonForCurrentProfile
    } else {
      logError(' Status update failed:', data);
      alert('Не удалось обновить статус');
    }
  } catch (err) {
    logError(' Exception updating status:', err);
    alert(`Ошибка: ${err.message || String(err)}`);
  }
}

function startObserver() {
  // Отслеживаем текущий URL
  let currentUrl = location.href;
  
  const resetState = () => {
    log(' Resetting state due to URL change');
    STATE.apiCallsThisProfile = 0;
    STATE.statusFetchedFor = null;
    STATE.statusInFlight = null;
    STATE.current.mode = "idle";
    STATE.current.appUrl = null;
    STATE.current.show = false;
    STATE.current.inputValue = "";
    STATE.messagingProfileCache = null;
    STATE.lastProfileUrl = null;
    STATE.lastThreadId = null;
    STATE.linkedinFull.vacancies = [];
    STATE.linkedinFull.candidateInfo = null;
    STATE.linkedinFull.selectedVacancyId = null;
    STATE.linkedinFull.defaultVacancyId = null;
    STATE.linkedinFull.last_comment_datetime = null;
    STATE.linkedinFull.rejection_reason_name = null;

    const floatingEl = document.querySelector("[data-hrhelper-floating='true']");
    if (floatingEl?.parentNode) floatingEl.parentNode.removeChild(floatingEl);
    const addVacDropdown = floatingWidgetData?.addVacancyDropdown;
    if (addVacDropdown?.parentNode) addVacDropdown.parentNode.removeChild(addVacDropdown);
    floatingWidgetData = null;

    STATE.buttons.forEach((widgets) => {
      if (widgets?.wrapper?.parentNode) {
        widgets.wrapper.parentNode.removeChild(widgets.wrapper);
      }
    });
    STATE.buttons.clear();
  };
  
  const schedule = () => {
    if (STATE.scheduled) return;
    STATE.scheduled = true;
    requestAnimationFrame(() => {
      STATE.scheduled = false;
      
      // Проверяем изменение URL
      const urlChanged = location.href !== currentUrl;
      if (urlChanged) {
        log(' URL changed detected:', location.href);
        currentUrl = location.href;
        resetState();
      }
      
      let canonical = normalizeLinkedInProfileUrl(location.href);
      
      if (!canonical && IS_MESSAGING_PAGE) {
        // На messaging-странице проверяем изменение thread ID
        const currentThreadId = extractThreadIdFromMessageButton();
        const threadChanged = currentThreadId && currentThreadId !== STATE.lastThreadId;
        
        if (threadChanged || urlChanged) {
          log(' Thread changed or URL changed, resetting state');
          resetState();
          STATE.lastThreadId = currentThreadId;
          
          // Показываем кнопки сразу (force=true при смене URL/тредса)
          STATE.current.show = true;
          STATE.current.mode = "input";
          STATE.current.title = "Загрузка...";
          ensureButtons(urlChanged || threadChanged);
          
          // Запускаем проверку профиля для нового чата в фоне
          refreshButtonForCurrentProfile();
          return;
        }
        
        // Если thread не изменился, но профиль еще не определен
        if (!STATE.statusFetchedFor) {
          // Показываем кнопки сразу
          if (!STATE.current.show) {
            STATE.current.show = true;
            STATE.current.mode = "input";
            STATE.current.title = "Загрузка...";
            ensureButtons(false);
          }
          refreshButtonForCurrentProfile();
        } else {
          ensureButtons(false);
        }
        return;
      }
      
      // Для профилей показываем кнопки сразу
      if (!canonical) {
        STATE.current.show = true;
        STATE.current.mode = "input";
        STATE.current.title = "Укажи ссылку на кандидата";
        ensureButtons(false);
        return;
      }

      const changed = STATE.lastProfileUrl !== canonical || urlChanged;
      if (changed) {
        resetState();
        STATE.lastProfileUrl = canonical;
        
        // Показываем кнопки сразу (force=true при смене профиля)
        STATE.current.show = true;
        STATE.current.mode = "input";
        STATE.current.title = "Загрузка...";
        ensureButtons(true);
        
        // Загружаем данные в фоне
        refreshButtonForCurrentProfile();
      } else {
        ensureButtons(false);
      }
    });
  };

  const debouncedSchedule = debounce(function () {
    if (STATE.suppressObserver) return;
    schedule();
  }, TIMING.DEBOUNCE_MUTATION || 100);
  const obs = new MutationObserver(() => debouncedSchedule());

  // Наблюдаем только за конкретными контейнерами, а не за всем body
  const observeTargets = IS_MESSAGING_PAGE
    ? [
        document.querySelector('.msg-form'),
        document.querySelector('.msg-s-message-list-container'),
        document.querySelector('main')
      ].filter(Boolean)
    : [
        document.querySelector('[data-view-name="profile-top-card"]'),
        document.querySelector('.scaffold-layout__sticky'),
        document.querySelector('main')
      ].filter(Boolean);

  if (observeTargets.length > 0) {
    observeTargets.forEach(target => {
      obs.observe(target, { childList: true, subtree: true });
    });
  } else if (document.body) {
    obs.observe(document.body, { childList: true, subtree: true });
  } else {
    obs.observe(document.documentElement, { childList: true, subtree: true });
  }

  schedule();

  // Отслеживаем изменения URL для всех страниц
  // Отслеживаем изменения через popstate (назад/вперед в истории)
  window.addEventListener('popstate', () => {
    log(' URL changed (popstate)');
    currentUrl = location.href;
    schedule();
  });
  
  // Отслеживаем изменения через pushState/replaceState (SPA навигация)
  const originalPushState = history.pushState;
  const originalReplaceState = history.replaceState;
  
  history.pushState = function(...args) {
    originalPushState.apply(history, args);
    log(' URL changed (pushState)');
    currentUrl = location.href;
    schedule();
  };
  
  history.replaceState = function(...args) {
    originalReplaceState.apply(history, args);
    log(' URL changed (replaceState)');
    currentUrl = location.href;
    schedule();
  };
  
  // Для messaging страницы также периодически проверяем URL и сохраняем маппинг
  if (IS_MESSAGING_PAGE) {
    // Функция для сохранения маппинга thread_id -> profile_url
    const saveThreadMappingIfFound = async () => {
      try {
        const currentUrl = location.href;
        const threadMatch = currentUrl.match(/thread\/([^/?]+)/);
        if (!threadMatch) return;
        
        const threadId = threadMatch[1];
        
        // Ищем профиль в DOM
        const profileLinks = Array.from(document.querySelectorAll('a[href*="/in/"]'));
        for (const link of profileLinks) {
          if (link.href.includes('/me/') || link.href.includes('/jobs/')) continue;
          const normalized = normalizeLinkedInProfileUrl(link.href);
          if (normalized) {
            // Проверяем, есть ли уже маппинг
            const mapping = JSON.parse(localStorage.getItem('hrhelper_thread_profile_map') || '{}');
            if (mapping[threadId] !== normalized) {
              // Сохраняем новый маппинг
              mapping[threadId] = normalized;
              localStorage.setItem('hrhelper_thread_profile_map', JSON.stringify(mapping));
              log(' Saved thread mapping from messaging page:', threadId.substring(0, 10) + '... -> ' + normalized);
              
              // Сохраняем на backend
              saveThreadMappingToBackend(threadId, normalized);
            }
            break;
          }
        }
      } catch (e) {
        warn(' Error saving thread mapping from messaging page:', e);
      }
    };
    
    // Вызываем сразу и периодически
    saveThreadMappingIfFound();
    setInterval(saveThreadMappingIfFound, 5000); // Каждые 5 секунд
    
    setInterval(() => {
      if (location.href !== currentUrl) {
        log(' URL changed (interval check)');
        currentUrl = location.href;
        STATE.messagingProfileCache = null; // Сбрасываем кэш при смене тредса
        schedule();
        saveThreadMappingIfFound(); // Сохраняем маппинг для нового тредса
      } else {
        // Даже если URL не изменился, проверяем thread ID
        const currentThreadId = extractThreadIdFromMessageButton();
        if (currentThreadId && currentThreadId !== STATE.lastThreadId) {
          log(' Thread ID changed (interval check)');
          schedule();
        }
      }
    }, 300); // Проверяем каждые 300мс для более быстрой реакции
  }

  // Для профилей — периодическая проверка URL (LinkedIn SPA может не вызывать pushState)
  if (IS_PROFILE_PAGE) {
    setInterval(() => {
      if (location.href !== currentUrl) {
        log(' URL changed (profile interval check)');
        schedule();
      }
    }, 400);
  }

  log(' Observer started');
  log(' IS_MESSAGING_PAGE:', IS_MESSAGING_PAGE);
  log(' IS_PROFILE_PAGE:', IS_PROFILE_PAGE);
  log(' Location:', location.href);
  
  // Показываем кнопки сразу при загрузке страницы
  STATE.current.show = true;
  STATE.current.mode = "input";
  STATE.current.title = "Загрузка...";
  ensureButtons();
  
  const canonical = normalizeLinkedInProfileUrl(location.href);
  if (canonical) {
    log(' Found canonical URL on init:', canonical);
    STATE.lastProfileUrl = canonical;
    // Загружаем данные в фоне
    refreshButtonForCurrentProfile();
  } else if (IS_MESSAGING_PAGE) {
    log(' Messaging page detected, resolving profile...');
    STATE.lastThreadId = extractThreadIdFromMessageButton();
    // Загружаем данные в фоне
    refreshButtonForCurrentProfile();
  } else if (IS_PROFILE_PAGE) {
    log(' Profile page detected');
    STATE.current.title = "Укажи ссылку на кандидата";
    ensureButtons();
  } else {
    warn(' Unknown page type');
    STATE.current.title = "Укажи ссылку на кандидата";
    ensureButtons();
  }
}

// Функция для работы с Google Calendar
function initGoogleCalendar() {
  if (!IS_GOOGLE_CALENDAR) return;
  
  log(' Google Calendar detected, initializing...');
  log(' Current URL:', location.href);
  
  // Функция для поиска контейнера с кнопками рядом с текстом "Уведомить гостей"
  function findNotifyGuestsContainer() {
    log(' Searching for "Notify guests" / "Уведомить гостей" container...');
    const searchTexts = [
      'Уведомить гостей',
      'уведомить гостей',
      'Notify guests',
      'notify guests',
      'Уведомить',
      'Notify'
    ];
    const walker = document.createTreeWalker(
      document.body,
      NodeFilter.SHOW_TEXT,
      null
    );
    let textNode;
    while (textNode = walker.nextNode()) {
      const text = textNode.textContent.trim();
      for (const searchText of searchTexts) {
        if (text.includes(searchText)) {
          log(' Found text node with "Notify guests":', text.substring(0, 50));
          let element = textNode.parentElement;
          for (let i = 0; i < 15 && element; i++) {
            const buttons = Array.from(element.querySelectorAll('button, a, [role="button"]'));
            if (buttons.length > 0) {
              const style = window.getComputedStyle(element);
              if (style.display !== 'none') {
                log(' Found container with buttons near "Notify guests", buttons count:', buttons.length);
                return { container: element, buttons, referenceElement: textNode };
              }
            }
            const parent = element.parentElement;
            if (parent) {
              const parentButtons = Array.from(parent.querySelectorAll('button, a, [role="button"]'));
              if (parentButtons.length > buttons.length && parentButtons.length > 0) {
                const parentStyle = window.getComputedStyle(parent);
                if (parentStyle.display !== 'none') {
                  log(' Found parent container with more buttons near "Notify guests", buttons count:', parentButtons.length);
                  return { container: parent, buttons: parentButtons, referenceElement: element };
                }
              }
            }
            element = element.parentElement;
          }
        }
      }
    }
    log(' "Notify guests" container not found');
    return null;
  }
  
  // Стили для кнопок контактов на Calendar (капсула, иконки)
  function ensureCalendarButtonStyles() {
    if (document.getElementById('hrhelper-calendar-btn-styles')) return;
    const style = document.createElement('style');
    style.id = 'hrhelper-calendar-btn-styles';
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
      .hrhelper-communication-btn.hrhelper-cal-theme-dark.hrhelper-cal-telegram { border-color: #5eb8f0 !important; color: #5eb8f0 !important; box-shadow: 0 1px 3px rgba(0,0,0,.3), 0 2px 8px rgba(0,0,0,.25), 0 0 0 1px rgba(94,184,240,.25) !important; }
      .hrhelper-communication-btn.hrhelper-cal-theme-dark.hrhelper-cal-telegram .hrhelper-cal-sep { color: rgba(94,184,240,.6) !important; }
      .hrhelper-communication-btn.hrhelper-cal-theme-dark.hrhelper-cal-linkedin { border-color: #6eb3f7 !important; color: #6eb3f7 !important; box-shadow: 0 1px 3px rgba(0,0,0,.3), 0 2px 8px rgba(0,0,0,.25), 0 0 0 1px rgba(110,179,247,.25) !important; }
      .hrhelper-communication-btn.hrhelper-cal-theme-dark.hrhelper-cal-linkedin .hrhelper-cal-sep { color: rgba(110,179,247,.6) !important; }
      .hrhelper-communication-btn.hrhelper-cal-theme-dark.hrhelper-cal-whatsapp { border-color: #7ee081 !important; color: #7ee081 !important; box-shadow: 0 1px 3px rgba(0,0,0,.3), 0 2px 8px rgba(0,0,0,.25), 0 0 0 1px rgba(126,224,129,.25) !important; }
      .hrhelper-communication-btn.hrhelper-cal-theme-dark.hrhelper-cal-whatsapp .hrhelper-cal-sep { color: rgba(126,224,129,.6) !important; }
      .hrhelper-communication-btn.hrhelper-cal-theme-dark.hrhelper-cal-viber { border-color: #9d8ef7 !important; color: #9d8ef7 !important; box-shadow: 0 1px 3px rgba(0,0,0,.3), 0 2px 8px rgba(0,0,0,.25), 0 0 0 1px rgba(157,142,247,.25) !important; }
      .hrhelper-communication-btn.hrhelper-cal-theme-dark.hrhelper-cal-viber .hrhelper-cal-sep { color: rgba(157,142,247,.6) !important; }
      .hrhelper-communication-btn.hrhelper-cal-theme-dark.hrhelper-cal-default { border-color: #9aa0a6 !important; color: #9aa0a6 !important; box-shadow: 0 1px 3px rgba(0,0,0,.3), 0 2px 8px rgba(0,0,0,.25) !important; }
      .hrhelper-communication-btn.hrhelper-cal-theme-dark.hrhelper-cal-default .hrhelper-cal-sep { color: rgba(154,160,166,.7) !important; }
    `;
    (document.head || document.documentElement).appendChild(style);
  }

  function parseRgbLuminance(cssColor) {
    if (!cssColor || cssColor === 'transparent') return null;
    const m = cssColor.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/);
    if (m) {
      const r = parseInt(m[1], 10), g = parseInt(m[2], 10), b = parseInt(m[3], 10);
      return (0.299 * r + 0.587 * g + 0.114 * b) / 255;
    }
    if (cssColor.indexOf('rgb') === 0) return null;
    const hex = cssColor.replace(/^#/, '');
    if (hex.length === 6 || hex.length === 3) {
      const r = parseInt(hex.slice(0, 2), 16) || parseInt(hex[0] + hex[0], 16);
      const g = parseInt(hex.slice(2, 4), 16) || parseInt(hex[1] + hex[1], 16);
      const b = parseInt(hex.slice(4, 6), 16) || parseInt(hex[2] + hex[2], 16);
      return (0.299 * r + 0.587 * g + 0.114 * b) / 255;
    }
    return null;
  }

  /** Возвращает тему сайта календаря: "dark" | "light" | null. Сначала общий фон страницы (body/html), затем контейнер кнопки. */
  function getCalendarSiteTheme() {
    const html = document.documentElement;
    const body = document.body;
    if (html.getAttribute('data-theme') === 'dark' || html.getAttribute('data-theme') === 'dark_theme') return 'dark';
    if (html.getAttribute('data-theme') === 'light' || html.getAttribute('data-theme') === 'light_theme') return 'light';
    if (html.classList && (html.classList.contains('dark') || html.classList.contains('theme-dark') || html.classList.contains('dark-theme'))) return 'dark';
    if (html.classList && (html.classList.contains('light') || html.classList.contains('theme-light') || html.classList.contains('light-theme'))) return 'light';
    if (body.classList && (body.classList.contains('dark') || body.classList.contains('theme-dark'))) return 'dark';
    if (body.classList && (body.classList.contains('light') || body.classList.contains('theme-light'))) return 'light';
    try {
      const sampleLuminance = (el) => {
        if (!el) return null;
        const bg = window.getComputedStyle(el).backgroundColor;
        return parseRgbLuminance(bg);
      };
      const bodyLum = sampleLuminance(body);
      if (bodyLum != null) { if (bodyLum < 0.45) return 'dark'; if (bodyLum > 0.6) return 'light'; }
      const htmlLum = sampleLuminance(html);
      if (htmlLum != null) { if (htmlLum < 0.45) return 'dark'; if (htmlLum > 0.6) return 'light'; }
      const firstBtn = document.querySelector('.hrhelper-communication-btn');
      if (firstBtn) {
        let el = firstBtn.parentElement;
        for (let i = 0; i < 20 && el; i++) {
          const lum = sampleLuminance(el);
          if (lum != null) {
            if (lum < 0.45) return 'dark';
            if (lum > 0.6) return 'light';
          }
          el = el.parentElement;
        }
      }
    } catch (_) {}
    return null;
  }

  /** Разрешённая тема для кнопок календаря с учётом настроек: при "system" — тема сайта, иначе тема браузера. */
  function getCalendarResolvedTheme() {
    return new Promise((resolve) => {
      const themeKey = HRH.OPTIONS_THEME_KEY;
      try {
        chrome.storage.sync.get({ [themeKey]: 'system' }, (data) => {
          const theme = data[themeKey] || 'system';
          if (theme === 'light') { resolve('light'); return; }
          if (theme === 'dark') { resolve('dark'); return; }
          const siteTheme = getCalendarSiteTheme();
          if (siteTheme === 'dark' || siteTheme === 'light') { resolve(siteTheme); return; }
          if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) { resolve('dark'); return; }
          resolve('light');
        });
      } catch (_) {
        const siteTheme = getCalendarSiteTheme();
        if (siteTheme === 'dark' || siteTheme === 'light') { resolve(siteTheme); return; }
        resolve(window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
      }
    });
  }

  function applyCalendarButtonTheme() {
    getCalendarResolvedTheme().then((resolved) => {
      const dark = resolved === 'dark';
      document.querySelectorAll('.hrhelper-communication-btn').forEach((btn) => {
        if (dark) btn.classList.add('hrhelper-cal-theme-dark');
        else btn.classList.remove('hrhelper-cal-theme-dark');
      });
    });
  }

  function startCalendarThemeObserver() {
    if (window._hrhelperCalendarThemeObserver) return;
    window._hrhelperApplyCalendarButtonTheme = applyCalendarButtonTheme;
    const run = () => {
      applyCalendarButtonTheme();
    };
    run();
    const observer = new MutationObserver(() => run());
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['class', 'data-theme', 'style'] });
    if (document.body) observer.observe(document.body, { attributes: true, attributeFilter: ['class', 'style'] });
    window._hrhelperCalendarThemeObserver = observer;
  }

  function getTelegramIconSVG() {
    const s = document.createElement('span');
    s.className = 'hrhelper-cal-messenger-icon';
    s.innerHTML = '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M11.944 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0a12 12 0 0 0-.056 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 0 1 .171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.48.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z"/></svg>';
    return s;
  }
  function getLinkedInIconSVG() {
    const s = document.createElement('span');
    s.className = 'hrhelper-cal-messenger-icon';
    s.innerHTML = '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/></svg>';
    return s;
  }
  function getWhatsAppIconSVG() {
    const s = document.createElement('span');
    s.className = 'hrhelper-cal-messenger-icon';
    s.innerHTML = '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"/></svg>';
    return s;
  }
  function getViberIconSVG() {
    const s = document.createElement('span');
    s.className = 'hrhelper-cal-messenger-icon';
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('viewBox', '0 0 24 24');
    svg.setAttribute('fill', 'currentColor');
    const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    // Simple Icons: viber (монохром, хорошо читается в 14x14)
    path.setAttribute('d', 'M11.4 0C9.473.028 5.333.344 3.02 2.467 1.302 4.187.696 6.7.633 9.817.57 12.933.488 18.776 6.12 20.36h.003l-.004 2.416s-.037.977.61 1.177c.777.242 1.234-.5 1.98-1.302.407-.44.972-1.084 1.397-1.58 3.85.326 6.812-.416 7.15-.525.776-.252 5.176-.816 5.892-6.657.74-6.02-.36-9.83-2.34-11.546-.596-.55-3.006-2.3-8.375-2.323 0 0-.395-.025-1.037-.017zm.058 1.693c.545-.004.88.017.88.017 4.542.02 6.717 1.388 7.222 1.846 1.675 1.435 2.53 4.868 1.906 9.897v.002c-.604 4.878-4.174 5.184-4.832 5.395-.28.09-2.882.737-6.153.524 0 0-2.436 2.94-3.197 3.704-.12.12-.26.167-.352.144-.13-.033-.166-.188-.165-.414l.02-4.018c-4.762-1.32-4.485-6.292-4.43-8.895.054-2.604.543-4.738 1.996-6.173 1.96-1.773 5.474-2.018 7.11-2.03zm.38 2.602c-.167 0-.303.135-.304.302 0 .167.133.303.3.305 1.624.01 2.946.537 4.028 1.592 1.073 1.046 1.62 2.468 1.633 4.334.002.167.14.3.307.3.166-.002.3-.138.3-.304-.014-1.984-.618-3.596-1.816-4.764-1.19-1.16-2.692-1.753-4.447-1.765zm-3.96.695c-.19-.032-.4.005-.616.117l-.01.002c-.43.247-.816.562-1.146.932-.002.004-.006.004-.008.008-.267.323-.42.638-.46.948-.008.046-.01.093-.007.14 0 .136.022.27.065.4l.013.01c.135.48.473 1.276 1.205 2.604.42.768.903 1.5 1.446 2.186.27.344.56.673.87.984l.132.132c.31.308.64.6.984.87.686.543 1.418 1.027 2.186 1.447 1.328.733 2.126 1.07 2.604 1.206l.01.014c.13.042.265.064.402.063.046.002.092 0 .138-.008.31-.036.627-.19.948-.46.004 0 .003-.002.008-.005.37-.33.683-.72.93-1.148l.003-.01c.225-.432.15-.842-.18-1.12-.004 0-.698-.58-1.037-.83-.36-.255-.73-.492-1.113-.71-.51-.285-1.032-.106-1.248.174l-.447.564c-.23.283-.657.246-.657.246-3.12-.796-3.955-3.955-3.955-3.955s-.037-.426.248-.656l.563-.448c.277-.215.456-.737.17-1.248-.217-.383-.454-.756-.71-1.115-.25-.34-.826-1.033-.83-1.035-.137-.165-.31-.265-.502-.297zm4.49.88c-.158.002-.29.124-.3.282-.01.167.115.312.282.324 1.16.085 2.017.466 2.645 1.15.63.688.93 1.524.906 2.57-.002.168.13.306.3.31.166.003.305-.13.31-.297.025-1.175-.334-2.193-1.067-2.994-.74-.81-1.777-1.253-3.05-1.346h-.024zm.463 1.63c-.16.002-.29.127-.3.287-.008.167.12.31.288.32.523.028.875.175 1.113.422.24.245.388.62.416 1.164.01.167.15.295.318.287.167-.008.295-.15.287-.317-.03-.644-.215-1.178-.58-1.557-.367-.378-.893-.574-1.52-.607h-.018z');
    svg.appendChild(path);
    s.appendChild(svg);
    return s;
  }
  function getDefaultContactIconSVG() {
    const s = document.createElement('span');
    s.className = 'hrhelper-cal-messenger-icon';
    s.innerHTML = '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M20 4H4c-1.1 0-1.99.9-1.99 2L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 4l-8 5-8-5V6l8 5 8-5v2z"/></svg>';
    return s;
  }

  function buildCalendarContactButtonPlaceholder() {
    ensureCalendarButtonStyles();
    const a = document.createElement('a');
    a.className = 'hrhelper-communication-btn hrhelper-cal-default';
    a.href = '#';
    a.setAttribute('aria-label', 'Загрузка...');
    a.onclick = (e) => { e.preventDefault(); return false; };
    const extIcon = document.createElement('img');
    extIcon.className = 'hrhelper-cal-ext-icon';
    extIcon.src = chrome.runtime.getURL('icons/icon-32.png');
    extIcon.alt = '';
    const sep = document.createElement('span');
    sep.className = 'hrhelper-cal-sep';
    sep.textContent = '|';
    const label = document.createElement('span');
    label.className = 'hrhelper-cal-label';
    label.textContent = 'Загрузка...';
    a.appendChild(extIcon);
    a.appendChild(sep);
    a.appendChild(label);
    a.appendChild(getDefaultContactIconSVG());
    return a;
  }

  function setCalendarButtonContent(button, linkType, labelText) {
    const labelEl = button.querySelector('.hrhelper-cal-label');
    const lastIcon = button.querySelector('.hrhelper-cal-messenger-icon');
    if (labelEl) labelEl.textContent = labelText;
    if (lastIcon) lastIcon.remove();
    const classes = ['hrhelper-cal-telegram', 'hrhelper-cal-linkedin', 'hrhelper-cal-whatsapp', 'hrhelper-cal-viber', 'hrhelper-cal-default'];
    button.classList.remove(...classes);
    if (linkType === 'telegram') {
      button.classList.add('hrhelper-cal-telegram');
      button.appendChild(getTelegramIconSVG());
    } else if (linkType === 'linkedin') {
      button.classList.add('hrhelper-cal-linkedin');
      button.appendChild(getLinkedInIconSVG());
    } else if (linkType === 'whatsapp') {
      button.classList.add('hrhelper-cal-whatsapp');
      button.appendChild(getWhatsAppIconSVG());
    } else if (linkType === 'viber') {
      button.classList.add('hrhelper-cal-viber');
      button.appendChild(getViberIconSVG());
    } else {
      button.classList.add('hrhelper-cal-default');
      button.appendChild(getDefaultContactIconSVG());
    }
  }

  // Обработка ссылок «Для интервьюеров» и вставка кнопки контакта на Calendar
  function processInterviewerLinks() {
    ensureCalendarButtonStyles();
    log(' Processing interviewer links...');
    
    // Ищем все элементы, содержащие текст "Для интервьюеров:"
    const walker = document.createTreeWalker(
      document.body,
      NodeFilter.SHOW_TEXT,
      null
    );
    
    let textNode;
    const interviewerNodes = [];
    
    const interviewerSearchTexts = ['Для интервьюеров:', 'For interviewers:'];
    while (textNode = walker.nextNode()) {
      const t = textNode.textContent || '';
      if (interviewerSearchTexts.some(s => t.includes(s))) {
        interviewerNodes.push(textNode);
      }
    }
    
    log(` Found ${interviewerNodes.length} text nodes with "Для интервьюеров:" / "For interviewers:"`);
    
    // Также ищем через поиск по всему документу
    const allText = document.body.innerText || document.body.textContent || '';
    const foundInBody = interviewerSearchTexts.some(s => allText.includes(s));
    if (foundInBody) {
      log(' Text "Для интервьюеров:" / "For interviewers:" found in document body');
    } else {
      log(' Text "Для интервьюеров:" / "For interviewers:" NOT found in document body');
    }
    
    // Ищем все ссылки на Huntflow
    const allLinks = Array.from(document.querySelectorAll('a[href*="huntflow"]'));
    log(` Found ${allLinks.length} links containing "huntflow"`);
    allLinks.forEach((link, idx) => {
      log(` Link ${idx + 1}: ${link.href}`);
    });
    
    // Обрабатываем каждый найденный узел
    interviewerNodes.forEach((textNode, idx) => {
      log(` Processing text node ${idx + 1}`);
      const parent = textNode.parentElement;
      if (!parent) {
        log('  No parent element');
        return;
      }
      
      // Проверяем, не обработали ли мы уже этот элемент
      if (parent.dataset.hrhelperProcessed === 'true') {
        log('  Already processed');
        return;
      }
      parent.dataset.hrhelperProcessed = 'true';
      
      // Ищем ссылку на Huntflow в том же контейнере или рядом
      let container = parent;
      let huntflowLink = null;
      
      // Функция для извлечения реального URL из Google redirect
      function extractRealUrl(url) {
        if (!url) return null;
        try {
          // Если это Google redirect URL
          if (url.includes('google.com/url') && url.includes('q=')) {
            const urlObj = new URL(url);
            const realUrl = urlObj.searchParams.get('q');
            if (realUrl) {
              return decodeURIComponent(realUrl);
            }
          }
          return url;
        } catch (e) {
          return url;
        }
      }
      
      // Функция для проверки, является ли ссылка ссылкой на Huntflow
      function isHuntflowLink(link) {
        if (!link || !link.href) return false;
        // Проверяем href
        const realUrl = extractRealUrl(link.href);
        if (realUrl && (realUrl.includes('huntflow.ru') || realUrl.includes('huntflow.dev'))) {
          return true;
        }
        // Также проверяем текст ссылки (может содержать реальный URL)
        const linkText = link.textContent || link.innerText || '';
        if (linkText.includes('huntflow.ru') || linkText.includes('huntflow.dev')) {
          return true;
        }
        return false;
      }
      
      // Пробуем найти в родительских элементах
      for (let i = 0; i < 10 && container; i++) {
        // Ищем все ссылки и проверяем каждую
        const allLinks = Array.from(container.querySelectorAll('a'));
        huntflowLink = allLinks.find(isHuntflowLink);
        if (huntflowLink) {
          log(`  Found Huntflow link in container level ${i}`);
          break;
        }
        container = container.parentElement;
      }
      
      // Если не нашли в контейнере, ищем во всем документе
      if (!huntflowLink) {
        const allLinks = Array.from(document.querySelectorAll('a'));
        huntflowLink = allLinks.find(isHuntflowLink);
        if (huntflowLink) {
          log('  Found Huntflow link in document');
        }
      }
      
      if (!huntflowLink) {
        log('  No Huntflow link found');
        return;
      }
      
      // Извлекаем реальный URL (может быть в Google redirect)
      let huntflowUrl = extractRealUrl(huntflowLink.href);
      log('  Found Huntflow link (original):', huntflowLink.href);
      log('  Found Huntflow link (extracted):', huntflowUrl);
      
      // Извлекаем данные из URL (используем реальный URL, если был Google redirect)
      const ids = extractHuntflowIds(huntflowUrl);
      log('  Extracted IDs:', ids);
      if (!ids.account_name || !ids.applicant_id) {
        log('  Could not extract IDs from Huntflow URL');
        return;
      }
      
      // Используем реальный URL для API запроса
      const realHuntflowUrl = huntflowUrl;
      
      // Определяем контейнер для вставки кнопки (родитель ссылки)
      const buttonContainer = huntflowLink.parentElement;
      if (!buttonContainer) {
        log('  No container for button');
        return;
      }
      
      // Проверяем, есть ли уже кнопка рядом с этой ссылкой
      const existingButton = buttonContainer.querySelector('.hrhelper-communication-btn');
      if (existingButton) {
        log('  Button already exists');
        return;
      }
      
      log('  Creating button...');
      
      // Пытаемся найти контейнер с кнопками рядом с "Уведомить гостей" (как в fullstack — расположение кнопки)
      const notifyContainer = findNotifyGuestsContainer();
      let targetContainer = buttonContainer;
      let insertAfter = null;
      if (notifyContainer && notifyContainer.buttons.length > 0) {
        log('  Found "Notify guests" container, placing button nearby');
        const lastButton = notifyContainer.buttons[notifyContainer.buttons.length - 1];
        targetContainer = notifyContainer.container;
        insertAfter = lastButton;
        log('  Will insert after button:', lastButton.textContent || lastButton.getAttribute('aria-label') || 'button');
      }
      
      const button = buildCalendarContactButtonPlaceholder();
      
      // Вставляем кнопку рядом с "Уведомить гостей" (после последней кнопки в том контейнере) или после ссылки на Huntflow
      if (insertAfter) {
        if (insertAfter.nextSibling) {
          targetContainer.insertBefore(button, insertAfter.nextSibling);
          log('  Button inserted after "Notify guests" button');
        } else {
          targetContainer.appendChild(button);
          log('  Button appended to container with "Notify guests" button');
        }
      } else if (huntflowLink.nextSibling) {
        buttonContainer.insertBefore(button, huntflowLink.nextSibling);
        log('  Button inserted after Huntflow link');
      } else {
        buttonContainer.appendChild(button);
        log('  Button appended to container');
      }
      
      log('  Button created, fetching communication link...');
      
      // Получаем ссылку на коммуникацию через API (используем реальный URL)
      getCommunicationLink(realHuntflowUrl).then(linkData => {
        log('  Communication link response:', linkData);
        if (linkData && linkData.success && linkData.communication_link) {
          button.href = linkData.communication_link;
          button.target = '_blank';
          button.rel = 'noopener noreferrer';
          button.onclick = null;
          let linkType = linkData.link_type || 'default';
          if (linkType === 'unknown' && linkData.communication_link) {
            const url = String(linkData.communication_link).toLowerCase();
            if (url.includes('wa.me') || url.includes('whatsapp')) linkType = 'whatsapp';
            else if (url.includes('viber')) linkType = 'viber';
          }
          const labels = { telegram: 'Telegram', linkedin: 'LinkedIn', whatsapp: 'WhatsApp', viber: 'Viber' };
          setCalendarButtonContent(button, linkType, labels[linkType] || 'Связаться');
          button.setAttribute('aria-label', labels[linkType] || 'Связаться');
          applyCalendarButtonTheme();
          log('  Button updated successfully');
        } else {
          setCalendarButtonContent(button, 'default', 'Ссылка не найдена');
          button.style.cursor = 'not-allowed';
          button.href = '#';
          log('  Communication link not found');
        }
      }).catch(err => {
        if (err.message && !err.message.includes('Extension context invalidated')) {
          logError('  Error getting communication link:', err);
        }
        setCalendarButtonContent(button, 'default', 'Ошибка');
        button.style.cursor = 'not-allowed';
        button.href = '#';
        applyCalendarButtonTheme();
      });
    });
    applyCalendarButtonTheme();
    startCalendarThemeObserver();
  }
  
  // Функция для извлечения данных из Huntflow URL
  function extractHuntflowIds(url) {
    const result = { account_name: null, applicant_id: null, vacancy_id: null };
    
    // Формат 1a: /my/{account}#/applicants/filter/all/id/{applicant_id}
    const m1a = url.match(/\/my\/([^/#]+)#\/applicants\/filter\/[^/]+\/id\/(\d+)/);
    if (m1a) {
      result.account_name = m1a[1];
      result.applicant_id = parseInt(m1a[2]);
      return result;
    }
    // Формат 1b: /my/{account}#/applicants/filter/all/{applicant_id}
    const m1 = url.match(/\/my\/([^/#]+)#\/applicants\/filter\/[^/]+\/(\d+)/);
    if (m1) {
      result.account_name = m1[1];
      result.applicant_id = parseInt(m1[2]);
      return result;
    }
    
    // Формат 2: /my/{account}#/vacancy/{vacancy_id}/filter/{status}/id/{applicant_id}
    const m2 = url.match(/\/my\/([^/#]+)#\/vacancy\/(\d+)\/filter\/[^/]+\/id\/(\d+)/);
    if (m2) {
      result.account_name = m2[1];
      result.vacancy_id = parseInt(m2[2]);
      result.applicant_id = parseInt(m2[3]);
      return result;
    }
    
    return result;
  }
  
  // Функция для получения ссылки на коммуникацию через API
  async function getCommunicationLink(huntflowUrl) {
    try {
      const config = await getConfig();
      const qp = new URLSearchParams({ huntflow_url: huntflowUrl });
      const res = await apiFetch(`/api/v1/huntflow/linkedin-applicants/communication-link/?${qp.toString()}`, {
        method: "GET"
      });
      
      if (!res.ok) {
        const data = await res.json().catch(() => null);
        const msg = data?.message || '';
        const isContextInvalidated = msg.includes('Extension context invalidated');
        const isFieldNotFilled = /Где ведется коммуникация|не заполнено/i.test(msg);
        if (!isContextInvalidated && !isFieldNotFilled) {
          logError(' Failed to get communication link:', msg || 'Unknown error');
        }
        return null;
      }
      
      const data = await res.json().catch(() => null);
      return data;
    } catch (err) {
      if (err.message && !err.message.includes('Extension context invalidated')) {
        logError(' Exception getting communication link:', err);
      }
      return null;
    }
  }
  
  // Обрабатываем при загрузке с задержкой (Google Calendar загружается динамически)
  setTimeout(() => {
    log(' Initial processing after delay...');
    processInterviewerLinks();
  }, 1000);
  
  // Также обрабатываем сразу
  processInterviewerLinks();
  
  // Наблюдаем за изменениями DOM с debounce
  let processTimeout = null;
  const observer = new MutationObserver(() => {
    if (processTimeout) clearTimeout(processTimeout);
    processTimeout = setTimeout(() => {
      processInterviewerLinks();
    }, 500);
  });
  
  if (document.body) {
    observer.observe(document.body, {
      childList: true,
      subtree: true
    });
    log(' MutationObserver started');
  } else {
    log(' document.body not ready, waiting...');
    setTimeout(() => {
      if (document.body) {
        observer.observe(document.body, {
          childList: true,
          subtree: true
        });
        log(' MutationObserver started (delayed)');
      }
    }, 1000);
  }
}

// Извлечь код встречи из URL (например xim-pyga-awt из meet.google.com/xim-pyga-awt)
function getMeetCodeFromUrl() {
  try {
    const path = location.pathname || "";
    const match = path.match(/^\/([a-z]{3}-[a-z]{4}-[a-z]{3})/i);
    return match ? match[1].toLowerCase() : null;
  } catch (_) {
    return null;
  }
}

// Загрузить данные кандидата по коду Meet из API (связка создаётся при создании инвайта)
async function fetchMeetDataByMeetCode(meetCode) {
  try {
    const q = new URLSearchParams({ meet_code: meetCode });
    const res = await apiFetch(`/api/v1/huntflow/linkedin-applicants/by-meet/?${q.toString()}`, { method: "GET" });
    if (!res.ok) return null;
    const data = await res.json().catch(() => null);
    return data && data.success ? data : null;
  } catch (err) {
    if (err.message && !err.message.includes("Extension context invalidated")) logError(" fetchMeetDataByMeetCode:", err);
    return null;
  }
}

// Загрузить фразу-напоминание пользователя (для блока на Meet)
async function fetchReminderPhrase() {
  try {
    const res = await apiFetch('/api/v1/accounts/users/reminder-phrase/', { method: "GET" });
    if (!res.ok) return "";
    const data = await res.json().catch(() => null);
    if (data && data.success && data.data && typeof data.data.reminder_phrase === "string") {
      return (data.data.reminder_phrase || "").trim();
    }
    return "";
  } catch (err) {
    if (err.message && !err.message.includes("Extension context invalidated")) logError(" fetchReminderPhrase:", err);
    return "";
  }
}

// Блок фразы-напоминания на странице Google Meet (перетаскиваемый, позиция сохраняется)
function injectReminderBlock(phrase) {
  if (!phrase || document.getElementById('hrhelper-reminder-block')) return;
  const block = document.createElement('div');
  block.id = 'hrhelper-reminder-block';
  block.style.cssText = 'position:fixed!important;top:12px!important;left:12px!important;z-index:99998!important;max-width:320px!important;padding:10px 14px!important;background:rgba(0,0,0,0.88)!important;border-radius:8px!important;box-shadow:0 2px 12px rgba(0,0,0,0.4)!important;font-family:system-ui,sans-serif!important;font-size:13px!important;line-height:1.4!important;color:#fff!important;border-left:4px solid #0a66c2!important;user-select:none!important;';
  const label = document.createElement('div');
  label.textContent = 'Напоминание';
  label.style.cssText = 'font-size:11px!important;color:rgba(255,255,255,0.7)!important;margin-bottom:4px!important;';
  const text = document.createElement('div');
  text.textContent = phrase;
  text.style.cssText = 'word-wrap:break-word!important;white-space:pre-wrap!important;';
  block.appendChild(label);
  block.appendChild(text);
  document.body.appendChild(block);
  makeWidgetDraggable(block, 'hrhelper_meet_reminder_pos', null);
  chrome.storage.local.get({ hrhelper_meet_reminder_hidden: false }, (data) => {
    if (data.hrhelper_meet_reminder_hidden) block.style.display = 'none';
  });
  log(' Reminder block injected');
}

// Функция для работы с Google Meet (аналогична Google Calendar)
function initGoogleMeet() {
  if (!IS_GOOGLE_MEET) return;
  
  log(' Google Meet detected, initializing...');
  log(' Current URL:', location.href);
  
  // Блок фразы-напоминания (не зависит от meet code)
  fetchReminderPhrase().then((phrase) => {
    if (phrase) {
      STATE.meet.reminderPhrase = phrase;
      injectReminderBlock(phrase);
    }
  });
  
  const meetCode = getMeetCodeFromUrl();
  if (meetCode) {
    log(' Meet code:', meetCode);
    fetchMeetDataByMeetCode(meetCode).then((data) => {
      if (data) {
        STATE.meet.scorecardLink = data.scorecard_link || null;
        STATE.meet.communicationLink = data.communication_link || null;
        STATE.meet.communicationLabel = data.communication_label || "Контакт";
        STATE.meet.level = data.level || null;
        STATE.meet.vacancyName = data.vacancy_title || null;
        STATE.meet.huntflowUrl = data.huntflow_url || null;
        log(' Meet data from API:', STATE.meet);
        injectMeetPanel();
      }
    });
  }

  // Панель HR Helper на странице Meet отключена — все кнопки только в попапе расширения
  function injectMeetPanel() {
    return;
    if (document.getElementById('hrhelper-meet-panel')) return;
    const m = STATE.meet;
    const btnStyle = 'display:inline-flex!important;align-items:center!important;justify-content:center!important;padding:6px 12px!important;min-height:32px!important;background:#0a66c2!important;color:#fff!important;text-decoration:none!important;border:none!important;border-radius:6px!important;font-size:13px!important;font-weight:500!important;white-space:nowrap!important;cursor:pointer!important;margin:0 4px!important;';
    const panel = document.createElement('div');
    panel.id = 'hrhelper-meet-panel';
    panel.style.cssText = 'position:fixed!important;top:12px!important;right:12px!important;z-index:99999!important;display:flex!important;gap:6px!important;flex-wrap:wrap!important;align-items:center!important;padding:8px!important;background:rgba(0,0,0,0.85)!important;border-radius:8px!important;box-shadow:0 2px 8px rgba(0,0,0,0.3)!important;font-family:system-ui,sans-serif!important;';
    const label = document.createElement('span');
    label.textContent = 'HR Helper';
    label.style.cssText = 'color:#fff!important;font-size:12px!important;margin-right:4px!important;';
    panel.appendChild(label);
    if (m.scorecardLink) {
      const a = document.createElement('a');
      a.href = m.scorecardLink;
      a.target = '_blank';
      a.rel = 'noopener noreferrer';
      a.textContent = 'Scorecard';
      a.style.cssText = btnStyle;
      panel.appendChild(a);
    }
    if (m.communicationLink) {
      const a = document.createElement('a');
      a.href = m.communicationLink;
      a.target = '_blank';
      a.rel = 'noopener noreferrer';
      a.textContent = m.communicationLabel || 'Контакт';
      a.style.cssText = btnStyle;
      panel.appendChild(a);
    }
    const levelBtn = document.createElement('button');
    levelBtn.type = 'button';
    levelBtn.className = 'hrhelper-meet-level-btn';
    levelBtn.textContent = 'Уровень';
    levelBtn.style.cssText = btnStyle + (m.level ? '' : 'opacity:0.6!important;cursor:not-allowed!important;');
    levelBtn.disabled = !m.level;
    levelBtn.onclick = () => {
      if (!m.level) return;
      chrome.runtime.sendMessage({ action: 'copyLevelText' }, (r) => {
        if (r && r.success && levelBtn) {
          const t = levelBtn.textContent;
          levelBtn.textContent = 'Скопировано!';
          setTimeout(() => { levelBtn.textContent = t; }, 1500);
        }
      });
    };
    panel.appendChild(levelBtn);
    document.body.appendChild(panel);
    log(' Meet panel injected');
  }
  
  // Функция для получения ссылки на Scorecard через API
  async function getScorecardLink(huntflowUrl) {
    try {
      const config = await getConfig();
      const qp = new URLSearchParams({ huntflow_url: huntflowUrl });
      const res = await apiFetch(`/api/v1/huntflow/linkedin-applicants/scorecard-link/?${qp.toString()}`, {
        method: "GET"
      });
      
      if (!res.ok) {
        const data = await res.json().catch(() => null);
        // Не логируем ошибку, если это Extension context invalidated - это нормально при перезагрузке расширения
        if (data?.message && !data.message.includes('Extension context invalidated')) {
          log(' Failed to get scorecard link:', data.message || 'Unknown error');
        }
        return null;
      }
      
      const data = await res.json().catch(() => null);
      return data;
    } catch (err) {
      // Не логируем ошибку, если это Extension context invalidated - это нормально при перезагрузке расширения
      if (err.message && !err.message.includes('Extension context invalidated')) {
        logError(' Exception getting scorecard link:', err);
      }
      return null;
    }
  }
  
  // Кнопки на странице Meet отключены — все действия только в попапе расширения
  function processInterviewerLinks() {
    return;
    log(' Processing interviewer links...');
    
    // Ищем все элементы, содержащие текст "Для интервьюеров:"
    const walker = document.createTreeWalker(
      document.body,
      NodeFilter.SHOW_TEXT,
      null
    );
    
    let textNode;
    const interviewerNodes = [];
    
    const interviewerSearchTexts = ['Для интервьюеров:', 'For interviewers:'];
    while (textNode = walker.nextNode()) {
      const t = textNode.textContent || '';
      if (interviewerSearchTexts.some(s => t.includes(s))) {
        interviewerNodes.push(textNode);
      }
    }
    
    log(` Found ${interviewerNodes.length} text nodes with "Для интервьюеров:" / "For interviewers:"`);
    
    // Также ищем через поиск по всему документу
    const allText = document.body.innerText || document.body.textContent || '';
    const foundInBody = interviewerSearchTexts.some(s => allText.includes(s));
    if (foundInBody) {
      log(' Text "Для интервьюеров:" / "For interviewers:" found in document body');
    } else {
      log(' Text "Для интервьюеров:" / "For interviewers:" NOT found in document body');
    }
    
    // Ищем все ссылки на Huntflow
    const allLinks = Array.from(document.querySelectorAll('a[href*="huntflow"]'));
    log(` Found ${allLinks.length} links containing "huntflow"`);
    allLinks.forEach((link, idx) => {
      log(` Link ${idx + 1}: ${link.href}`);
    });
    
    // Обрабатываем каждый найденный узел
    interviewerNodes.forEach((textNode, idx) => {
      log(` Processing text node ${idx + 1}`);
      const parent = textNode.parentElement;
      if (!parent) {
        log('  No parent element');
        return;
      }
      
      // Проверяем, не обработали ли мы уже этот элемент
      if (parent.dataset.hrhelperProcessed === 'true') {
        log('  Already processed');
        return;
      }
      parent.dataset.hrhelperProcessed = 'true';
      
      // Ищем ссылку на Huntflow в том же контейнере или рядом
      let container = parent;
      let huntflowLink = null;
      
      // Функция для извлечения реального URL из Google redirect
      function extractRealUrl(url) {
        if (!url) return null;
        try {
          // Если это Google redirect URL
          if (url.includes('google.com/url') && url.includes('q=')) {
            const urlObj = new URL(url);
            const realUrl = urlObj.searchParams.get('q');
            if (realUrl) {
              return decodeURIComponent(realUrl);
            }
          }
          return url;
        } catch (e) {
          return url;
        }
      }
      
      // Функция для проверки, является ли ссылка ссылкой на Huntflow
      function isHuntflowLink(link) {
        if (!link || !link.href) return false;
        // Проверяем href
        const realUrl = extractRealUrl(link.href);
        if (realUrl && (realUrl.includes('huntflow.ru') || realUrl.includes('huntflow.dev'))) {
          return true;
        }
        // Также проверяем текст ссылки (может содержать реальный URL)
        const linkText = link.textContent || link.innerText || '';
        if (linkText.includes('huntflow.ru') || linkText.includes('huntflow.dev')) {
          return true;
        }
        return false;
      }
      
      // Пробуем найти в родительских элементах
      for (let i = 0; i < 10 && container; i++) {
        // Ищем все ссылки и проверяем каждую
        const allLinks = Array.from(container.querySelectorAll('a'));
        huntflowLink = allLinks.find(isHuntflowLink);
        if (huntflowLink) {
          log(`  Found Huntflow link in container level ${i}`);
          break;
        }
        container = container.parentElement;
      }
      
      // Если не нашли в контейнере, ищем во всем документе
      if (!huntflowLink) {
        const allLinks = Array.from(document.querySelectorAll('a'));
        huntflowLink = allLinks.find(isHuntflowLink);
        if (huntflowLink) {
          log('  Found Huntflow link in document');
        }
      }
      
      // Если не нашли как ссылку, ищем как текст под "Для интервьюеров:"
      let huntflowUrl = null;
      if (!huntflowLink) {
        log('  No Huntflow link found as <a> tag, searching as text...');
        // Ищем текст, содержащий huntflow.ru или huntflow.dev
        const textWalker = document.createTreeWalker(
          container || document.body,
          NodeFilter.SHOW_TEXT,
          null
        );
        
        let textNodeForUrl;
        while (textNodeForUrl = textWalker.nextNode()) {
          const text = textNodeForUrl.textContent || '';
          // Ищем URL в тексте
          const urlMatch = text.match(/https?:\/\/[^\s]*huntflow\.(ru|dev)[^\s]*/i);
          if (urlMatch) {
            huntflowUrl = urlMatch[0];
            log('  Found Huntflow URL in text:', huntflowUrl);
            // Создаем виртуальную ссылку для дальнейшей обработки
            huntflowLink = {
              href: huntflowUrl,
              parentElement: textNodeForUrl.parentElement || container || document.body
            };
            break;
          }
        }
      }
      
      if (!huntflowLink && !huntflowUrl) {
        log('  No Huntflow link found');
        return;
      }
      
      // Извлекаем реальный URL (может быть в Google redirect или из текста)
      if (!huntflowUrl) {
        huntflowUrl = extractRealUrl(huntflowLink.href);
      }
      log('  Found Huntflow link (original):', huntflowLink?.href || huntflowUrl);
      log('  Found Huntflow link (extracted):', huntflowUrl);
      
      // Извлекаем данные из URL (используем реальный URL, если был Google redirect)
      const ids = extractHuntflowIds(huntflowUrl);
      log('  Extracted IDs:', ids);
      if (!ids.account_name || !ids.applicant_id) {
        log('  Could not extract IDs from Huntflow URL');
        return;
      }
      
      // Используем реальный URL для API запроса
      const realHuntflowUrl = huntflowUrl;
      
      // Определяем контейнер для вставки кнопок - под текстом "Для интервьюеров:"
      // Используем родительский элемент текста "Для интервьюеров:" как контейнер
      let buttonContainer = parent;
      
      // Ищем подходящий контейнер (div, p, span и т.д.) для размещения кнопок
      // Обычно это блок, содержащий текст "Для интервьюеров:" и ссылку
      for (let i = 0; i < 5 && buttonContainer; i++) {
        // Проверяем, является ли контейнер подходящим для размещения кнопок
        const computedStyle = window.getComputedStyle(buttonContainer);
        if (computedStyle.display !== 'none' && 
            (computedStyle.display === 'block' || 
             computedStyle.display === 'flex' || 
             computedStyle.display === 'inline-block')) {
          break;
        }
        buttonContainer = buttonContainer.parentElement;
      }
      
      if (!buttonContainer) {
        log('  No container for buttons');
        return;
      }
      
      // Проверяем, есть ли уже кнопки в этом контейнере
      const existingCommButton = buttonContainer.querySelector('.hrhelper-communication-btn');
      const existingScorecardButton = buttonContainer.querySelector('.hrhelper-scorecard-btn');
      const existingLevelButton = buttonContainer.querySelector('.hrhelper-meet-level-btn');
      if (existingCommButton && existingScorecardButton && existingLevelButton) {
        log('  All buttons already exist');
        return;
      }
      
      log('  Creating buttons container under "Для интервьюеров:"...');
      
      // Создаем контейнер для всех кнопок, если его еще нет
      let buttonsContainer = buttonContainer.querySelector('.hrhelper-buttons-container');
      if (!buttonsContainer) {
        buttonsContainer = document.createElement('div');
        buttonsContainer.className = 'hrhelper-buttons-container';
        buttonsContainer.style.cssText = 'display:flex;gap:8px;margin-top:8px;flex-wrap:wrap;align-items:center;';
        
        // Вставляем контейнер после текста "Для интервьюеров:" и ссылки
        // Ищем место для вставки - после текста или после ссылки
        if (huntflowLink && huntflowLink.nextSibling) {
          buttonContainer.insertBefore(buttonsContainer, huntflowLink.nextSibling);
        } else if (textNode && textNode.nextSibling) {
          buttonContainer.insertBefore(buttonsContainer, textNode.nextSibling);
        } else {
          buttonContainer.appendChild(buttonsContainer);
        }
        log('  Buttons container created');
      }
      
      const HRHELPER_MEET_BTN_STYLE = 'display:inline-flex!important;align-items:center!important;justify-content:center!important;padding:6px 12px!important;min-height:32px!important;background:#0a66c2!important;color:#fff!important;text-decoration:none!important;border:none!important;border-radius:6px!important;font-size:13px!important;font-weight:500!important;white-space:nowrap!important;';
      const HRHELPER_MEET_BTN_DISABLED = 'opacity:0.6!important;cursor:not-allowed!important;pointer-events:none!important;background:#6c757d!important;';

      let button = null;
      if (!existingCommButton) {
        button = document.createElement('a');
        button.className = 'hrhelper-communication-btn';
        button.setAttribute('data-hrhelper', 'social-button');
        button.textContent = 'Контакт';
        button.style.cssText = HRHELPER_MEET_BTN_STYLE + HRHELPER_MEET_BTN_DISABLED;
        button.href = '#';
        button.onclick = (e) => { e.preventDefault(); return false; };
        buttonsContainer.appendChild(button);
        log('  Communication button inserted');
      } else {
        button = existingCommButton;
      }

      let scorecardButton = null;
      if (!existingScorecardButton) {
        scorecardButton = document.createElement('a');
        scorecardButton.className = 'hrhelper-scorecard-btn';
        scorecardButton.textContent = 'Scorecard';
        scorecardButton.style.cssText = HRHELPER_MEET_BTN_STYLE + HRHELPER_MEET_BTN_DISABLED;
        scorecardButton.href = '#';
        scorecardButton.onclick = (e) => { e.preventDefault(); return false; };
        buttonsContainer.appendChild(scorecardButton);
        log('  Scorecard button inserted');
      } else {
        scorecardButton = existingScorecardButton;
      }

      log('  Buttons created, fetching links...');

      if (!existingCommButton) {
        getCommunicationLink(realHuntflowUrl).then(linkData => {
          log('  Communication link response:', linkData);
          if (linkData && linkData.success && linkData.communication_link) {
            button.href = linkData.communication_link;
            button.target = '_blank';
            button.rel = 'noopener noreferrer';
            button.style.cssText = HRHELPER_MEET_BTN_STYLE;
            button.style.pointerEvents = '';
            button.style.cursor = 'pointer';
            STATE.meet.communicationLink = linkData.communication_link;
            const meetLabels = { telegram: '💬 Telegram', linkedin: '💼 LinkedIn', whatsapp: 'WhatsApp', viber: 'Viber' };
            STATE.meet.communicationLabel = meetLabels[linkData.link_type] || 'Связаться';
            button.textContent = STATE.meet.communicationLabel;
            button.onclick = null;
            log('  Communication button updated successfully');
          } else {
            button.textContent = 'Контакт';
            button.style.cssText = HRHELPER_MEET_BTN_STYLE + HRHELPER_MEET_BTN_DISABLED;
            log('  Communication link not found');
          }
        }).catch(err => {
          if (err.message && !err.message.includes('Extension context invalidated')) {
            logError('  Error getting communication link:', err);
          }
          button.textContent = 'Контакт';
          button.style.cssText = HRHELPER_MEET_BTN_STYLE + HRHELPER_MEET_BTN_DISABLED;
        });
      }

      if (!existingScorecardButton) {
        getScorecardLink(realHuntflowUrl).then(scorecardData => {
          log('  Scorecard link response:', scorecardData);
          if (scorecardData && scorecardData.success && scorecardData.scorecard_link) {
            scorecardButton.href = scorecardData.scorecard_link;
            scorecardButton.target = '_blank';
            scorecardButton.rel = 'noopener noreferrer';
            scorecardButton.textContent = 'Scorecard';
            scorecardButton.style.cssText = HRHELPER_MEET_BTN_STYLE;
            scorecardButton.style.pointerEvents = '';
            scorecardButton.style.cursor = 'pointer';
            scorecardButton.onclick = null;
            STATE.meet.scorecardLink = scorecardData.scorecard_link;
            log('  Scorecard button updated successfully');
          } else {
            scorecardButton.textContent = 'Scorecard';
            scorecardButton.style.cssText = HRHELPER_MEET_BTN_STYLE + HRHELPER_MEET_BTN_DISABLED;
            log('  Scorecard link not found');
          }
        }).catch(err => {
          if (err.message && !err.message.includes('Extension context invalidated')) {
            logError('  Error getting scorecard link:', err);
          }
          scorecardButton.textContent = 'Scorecard';
          scorecardButton.style.cssText = HRHELPER_MEET_BTN_STYLE + HRHELPER_MEET_BTN_DISABLED;
        });
      }
    });
  }
  
  // Функция для извлечения данных из Huntflow URL
  function extractHuntflowIds(url) {
    const result = { account_name: null, applicant_id: null, vacancy_id: null };
    
    // Формат 1a: /my/{account}#/applicants/filter/all/id/{applicant_id}
    const m1a = url.match(/\/my\/([^/#]+)#\/applicants\/filter\/[^/]+\/id\/(\d+)/);
    if (m1a) {
      result.account_name = m1a[1];
      result.applicant_id = parseInt(m1a[2]);
      return result;
    }
    // Формат 1b: /my/{account}#/applicants/filter/all/{applicant_id}
    const m1 = url.match(/\/my\/([^/#]+)#\/applicants\/filter\/[^/]+\/(\d+)/);
    if (m1) {
      result.account_name = m1[1];
      result.applicant_id = parseInt(m1[2]);
      return result;
    }
    
    // Формат 2: /my/{account}#/vacancy/{vacancy_id}/filter/{status}/id/{applicant_id}
    const m2 = url.match(/\/my\/([^/#]+)#\/vacancy\/(\d+)\/filter\/[^/]+\/id\/(\d+)/);
    if (m2) {
      result.account_name = m2[1];
      result.vacancy_id = parseInt(m2[2]);
      result.applicant_id = parseInt(m2[3]);
      return result;
    }
    
    return result;
  }
  
  // Функция для получения ссылки на коммуникацию через API
  async function getCommunicationLink(huntflowUrl) {
    try {
      const config = await getConfig();
      const qp = new URLSearchParams({ huntflow_url: huntflowUrl });
      const res = await apiFetch(`/api/v1/huntflow/linkedin-applicants/communication-link/?${qp.toString()}`, {
        method: "GET"
      });
      
      if (!res.ok) {
        const data = await res.json().catch(() => null);
        const msg = data?.message || '';
        const isContextInvalidated = msg.includes('Extension context invalidated');
        const isFieldNotFilled = /Где ведется коммуникация|не заполнено/i.test(msg);
        if (!isContextInvalidated && !isFieldNotFilled) {
          logError(' Failed to get communication link:', msg || 'Unknown error');
        }
        return null;
      }
      
      const data = await res.json().catch(() => null);
      return data;
    } catch (err) {
      if (err.message && !err.message.includes('Extension context invalidated')) {
        logError(' Exception getting communication link:', err);
      }
      return null;
    }
  }
  
  // Функция для получения уровня кандидата через API
  async function getCandidateLevel(huntflowUrl) {
    try {
      log(' Getting candidate level for URL:', huntflowUrl);
      const config = await getConfig();
      const qp = new URLSearchParams({ huntflow_url: huntflowUrl });
      const apiUrl = `/api/v1/huntflow/linkedin-applicants/candidate-level/?${qp.toString()}`;
      log(' API URL:', apiUrl);
      
      const res = await apiFetch(apiUrl, {
        method: "GET"
      });
      
      log(' API response status:', res.status, res.ok);
      
      if (!res.ok) {
        const data = await res.json().catch(() => null);
        logError(' Failed to get candidate level:', data?.message || `HTTP ${res.status}`);
        return { success: false, message: data?.message || `HTTP ${res.status}` };
      }
      
      const data = await res.json().catch(() => null);
      log(' API response data:', data);
      return data;
    } catch (err) {
      logError(' Exception getting candidate level:', err);
      return { success: false, message: err.message || 'Unknown error' };
    }
  }
  
  // Кнопка «Уровень» на странице Meet отключена — только в попапе расширения
  function addLevelButtonToMeetControls() {
    return true;
    try {
      log(' ===== addLevelButtonToMeetControls START =====');
      log(' Current URL:', location.href);
      log(' Available buttons on page:', document.querySelectorAll('button').length);
      
      // Проверяем, не добавили ли мы уже кнопку
      const existingLevelBtn = document.querySelector('.hrhelper-meet-level-btn');
      if (existingLevelBtn) {
        log(' Level button already exists');
        return true; // Успешно - кнопка уже есть
      }
      
      // Ищем панель с кнопками управления (обычно это нижняя панель)
      // Пробуем разные подходы для поиска контейнера с кнопками
      let buttonContainer = null;
      let infoButton = null;
      
      // Способ 0: Ищем рядом с уже созданной кнопкой соцсети (если она есть)
      const socialButton = document.querySelector('[data-hrhelper="social-button"], .hrhelper-communication-btn');
      if (socialButton) {
        log(' ✅ Found social button, looking for Meet controls nearby...');
        log(' Social button:', socialButton);
        log(' Social button parent:', socialButton.parentElement);
        
        // Ищем контейнер с кнопками управления рядом
        let container = socialButton.parentElement;
        let foundContainer = false;
        
        for (let i = 0; i < 10 && container; i++) {
          const buttons = Array.from(container.querySelectorAll('button'));
          log(` Checking container level ${i}, found ${buttons.length} buttons`);
          
          if (buttons.length >= 2) {
            const rect = container.getBoundingClientRect();
            const isBottom = rect.bottom > window.innerHeight * 0.5;
            const isVisible = rect.width > 0 && rect.height > 0;
            
            log(` Container at level ${i}: bottom=${rect.bottom.toFixed(0)}, visible=${isVisible}, buttons=${buttons.length}`);
            
            if (isBottom && isVisible) {
              log(` ✅ Found container with ${buttons.length} buttons near social button`);
              buttonContainer = container;
              
              // Ищем кнопку инфо
              infoButton = buttons.find(btn => {
                const label = (btn.getAttribute('aria-label') || '').toLowerCase();
                const tooltip = (btn.getAttribute('data-tooltip') || '').toLowerCase();
                return label.includes('info') || label.includes('инфо') || 
                       label.includes('details') || label.includes('детали') ||
                       tooltip.includes('info') || tooltip.includes('инфо');
              });
              
              if (!infoButton && buttons.length > 0) {
                infoButton = buttons[0];
                log(' Using first button as info button');
              }
              
              if (buttonContainer && infoButton) {
                foundContainer = true;
                break;
              }
            }
          }
          container = container.parentElement;
        }
        
        if (foundContainer) {
          log(' ✅ Successfully found Meet controls using social button method');
        } else {
          log(' ⚠️ Could not find Meet controls near social button, will try other methods');
        }
      } else {
        log(' Social button not found, will search using other methods');
      }
      
      // Ищем панель с кнопками управления (обычно это нижняя панель)
      // Пробуем разные подходы для поиска контейнера с кнопками
      if (!buttonContainer || !infoButton) {
        // Способ 1: Ищем контейнер с кнопками по общим селекторам
        log(' Trying method 1: searching by container selectors...');
      const containerSelectors = [
        '[role="toolbar"]',
        'div[data-view-name="meeting-controls"]',
        '.VfPpkd-Bz112c',
        '[jsname="BOHaEe"]',
        'div[aria-label*="meeting"]',
        'div[aria-label*="встреча"]',
      ];
      
      for (const selector of containerSelectors) {
        const containers = Array.from(document.querySelectorAll(selector));
        for (const container of containers) {
          const buttons = Array.from(container.querySelectorAll('button'));
          if (buttons.length >= 2) {
            buttonContainer = container;
            // Ищем кнопку инфо
            for (const btn of buttons) {
              const ariaLabel = (btn.getAttribute('aria-label') || '').toLowerCase();
              const tooltip = (btn.getAttribute('data-tooltip') || '').toLowerCase();
              const jsname = (btn.getAttribute('jsname') || '').toLowerCase();
              if (ariaLabel.includes('info') || ariaLabel.includes('инфо') || 
                  tooltip.includes('info') || tooltip.includes('инфо') ||
                  jsname.includes('info')) {
                infoButton = btn;
                log(` Found info button in container (${buttons.length} buttons)`);
                break;
              }
            }
            // Если не нашли кнопку инфо, берем первую кнопку
            if (!infoButton && buttons.length > 0) {
              infoButton = buttons[0];
              log(` Using first button as reference (${buttons.length} buttons)`);
            }
            if (buttonContainer && infoButton) break;
          }
        }
        if (buttonContainer && infoButton) break;
      }
      
      // Способ 2: Если не нашли, ищем кнопку инфо напрямую
      if (!infoButton || !buttonContainer) {
        log(' Trying method 2: searching for info button directly...');
        const infoSelectors = [
          '[data-tooltip*="Info" i]',
          '[data-tooltip*="инфо" i]',
          '[aria-label*="Info" i]',
          '[aria-label*="инфо" i]',
          'button[jsname*="info" i]',
          'button[aria-label*="Meeting details" i]',
          'button[aria-label*="Детали встречи" i]',
        ];
        
        for (const selector of infoSelectors) {
          try {
            const buttons = Array.from(document.querySelectorAll(selector));
            if (buttons.length > 0) {
              infoButton = buttons[0];
              buttonContainer = infoButton.parentElement;
              log(` Found info button directly with selector: ${selector}`);
              break;
            }
          } catch (e) {
            // Игнорируем ошибки селекторов
          }
        }
      }
      
      // Способ 3: Ищем любую панель с кнопками внизу экрана
      if (!infoButton || !buttonContainer) {
        log(' Trying method 3: searching for bottom toolbar...');
        // Ищем все контейнеры с кнопками
        const allContainers = Array.from(document.querySelectorAll('div, section, nav'));
        log(` Checking ${allContainers.length} containers for buttons...`);
        
        for (const container of allContainers) {
          const buttons = Array.from(container.querySelectorAll('button'));
          if (buttons.length >= 2) {
            // Проверяем, находится ли контейнер внизу экрана
            const rect = container.getBoundingClientRect();
            const isBottom = rect.bottom > window.innerHeight * 0.6;
            const isVisible = rect.width > 0 && rect.height > 0;
            
            if (isBottom && isVisible) {
              buttonContainer = container;
              // Пробуем найти кнопку инфо среди кнопок
              for (const btn of buttons) {
                const ariaLabel = (btn.getAttribute('aria-label') || '').toLowerCase();
                const tooltip = (btn.getAttribute('data-tooltip') || '').toLowerCase();
                if (ariaLabel.includes('info') || ariaLabel.includes('инфо') || 
                    tooltip.includes('info') || tooltip.includes('инфо') ||
                    ariaLabel.includes('details') || ariaLabel.includes('детали')) {
                  infoButton = btn;
                  log(` Found info button in bottom toolbar (${buttons.length} buttons)`);
                  break;
                }
              }
              // Если не нашли инфо, берем первую кнопку
              if (!infoButton && buttons.length > 0) {
                infoButton = buttons[0];
                log(` Using first button from bottom toolbar (${buttons.length} buttons)`);
              }
              if (buttonContainer && infoButton) break;
            }
          }
        }
      }
      
      // Способ 4: Ищем любые кнопки внизу экрана (последняя попытка)
      if (!infoButton || !buttonContainer) {
        log(' Trying method 4: finding any buttons at bottom of screen...');
        const allButtons = Array.from(document.querySelectorAll('button'));
        const buttonsAtBottom = allButtons.filter(btn => {
          const rect = btn.getBoundingClientRect();
          return rect.bottom > window.innerHeight * 0.7 && 
                 rect.width > 0 && 
                 rect.height > 0 &&
                 rect.top < window.innerHeight;
        });
        
        if (buttonsAtBottom.length >= 2) {
          log(` Found ${buttonsAtBottom.length} buttons at bottom of screen`);
          buttonContainer = buttonsAtBottom[0].parentElement;
          // Ищем кнопку инфо
          for (const btn of buttonsAtBottom) {
            const ariaLabel = (btn.getAttribute('aria-label') || '').toLowerCase();
            const tooltip = (btn.getAttribute('data-tooltip') || '').toLowerCase();
            if (ariaLabel.includes('info') || ariaLabel.includes('инфо') || 
                tooltip.includes('info') || tooltip.includes('инфо')) {
              infoButton = btn;
              log(' Found info button at bottom of screen');
              break;
            }
          }
          // Если не нашли, берем первую кнопку
          if (!infoButton && buttonsAtBottom.length > 0) {
            infoButton = buttonsAtBottom[0];
            log(' Using first button at bottom of screen');
          }
        }
      }
      } // Закрываем блок if (!buttonContainer || !infoButton)
      
      if (!infoButton || !buttonContainer) {
        log(' ❌ Info button or container not found after all methods');
        log(' Available buttons on page:', document.querySelectorAll('button').length);
        // Логируем все кнопки для отладки
        const allButtons = Array.from(document.querySelectorAll('button'));
        log(' Sample button attributes (first 10):', allButtons.slice(0, 10).map(btn => {
          const rect = btn.getBoundingClientRect();
          return {
            ariaLabel: btn.getAttribute('aria-label'),
            tooltip: btn.getAttribute('data-tooltip'),
            jsname: btn.getAttribute('jsname'),
            className: btn.className?.substring(0, 50),
            position: `bottom: ${rect.bottom.toFixed(0)}, top: ${rect.top.toFixed(0)}`,
            visible: rect.width > 0 && rect.height > 0
          };
        }));
        
        // Пробуем найти любую кнопку внизу экрана и использовать её родителя
        const buttonsAtBottom = allButtons.filter(btn => {
          const rect = btn.getBoundingClientRect();
          return rect.bottom > window.innerHeight * 0.8 && 
                 rect.width > 20 && 
                 rect.height > 20 &&
                 rect.top < window.innerHeight;
        }).sort((a, b) => {
          const rectA = a.getBoundingClientRect();
          const rectB = b.getBoundingClientRect();
          return rectB.bottom - rectA.bottom; // Сортируем по позиции снизу
        });
        
        if (buttonsAtBottom.length > 0) {
          log(` Found ${buttonsAtBottom.length} buttons at bottom, using first one's container`);
          infoButton = buttonsAtBottom[0];
          buttonContainer = infoButton.parentElement;
          log(' Using fallback: first bottom button container');
        } else {
          log(' ===== addLevelButtonToMeetControls FAILED =====');
          return false; // Не удалось найти кнопки
        }
      }
      
      log(' ✅ Found button container and info button!');
      log(' Container:', buttonContainer);
      log(' Info button:', infoButton);
    
      log(' Creating level button...');
      
      // Сначала проверяем, есть ли контейнер для кнопок под "Для интервьюеров:"
      let targetContainer = document.querySelector('.hrhelper-buttons-container');
      if (targetContainer) {
        log(' ✅ Found existing buttons container under "Для интервьюеров:", will place level button there');
        buttonContainer = targetContainer;
      } else {
        log(' No buttons container found, will place level button next to info button');
      }
      
      // Создаем кнопку уровня
      const levelButton = document.createElement('button');
      levelButton.className = 'hrhelper-meet-level-btn';
      levelButton.textContent = 'Уровень';
      levelButton.style.cssText = 'display:inline-flex!important;align-items:center!important;justify-content:center!important;padding:6px 12px!important;min-height:32px!important;background:#6c757d!important;color:#fff!important;border:none!important;border-radius:6px!important;font-size:13px!important;font-weight:500!important;cursor:not-allowed!important;margin-left:8px!important;min-width:60px!important;opacity:0.6!important;z-index:99999!important;position:relative!important;';
      levelButton.title = 'Уровень кандидата';
      levelButton.setAttribute('data-hrhelper', 'level-button');
      levelButton.setAttribute('aria-label', 'Уровень кандидата');
      levelButton.disabled = true;
      
      log(' Level button created:', levelButton);
      
      // Ищем название встречи (meeting title)
      // Обычно это элемент с текстом названия встречи в верхней части экрана
      let meetingTitleElement = null;
      
      // Пробуем разные селекторы для названия встречи
      const titleSelectors = [
        '[data-meeting-title]',
        '[aria-label*="meeting"]',
        '[aria-label*="встреча"]',
        'div[role="heading"]',
        'h1',
        'h2',
        '.meeting-title',
        '[jsname*="title"]',
      ];
      
      for (const selector of titleSelectors) {
        try {
          const elements = Array.from(document.querySelectorAll(selector));
          for (const el of elements) {
            const text = (el.textContent || '').trim();
            // Название встречи обычно не пустое и не слишком длинное
            if (text && text.length > 0 && text.length < 200 && 
                !text.includes('Google Meet') && !text.includes('meet.google.com')) {
              const rect = el.getBoundingClientRect();
              // Название обычно в верхней части экрана
              if (rect.top < window.innerHeight * 0.3 && rect.width > 0 && rect.height > 0) {
                meetingTitleElement = el;
                log(` ✅ Found meeting title with selector: ${selector}`, text);
                break;
              }
            }
          }
          if (meetingTitleElement) break;
        } catch (e) {
          // Игнорируем ошибки селекторов
        }
      }
      
      // Если не нашли по селекторам, ищем текстовые элементы в верхней части
      if (!meetingTitleElement) {
        const allElements = Array.from(document.querySelectorAll('div, span, p, h1, h2, h3'));
        for (const el of allElements) {
          const text = (el.textContent || '').trim();
          if (text && text.length > 0 && text.length < 200) {
            const rect = el.getBoundingClientRect();
            // Ищем в верхней части экрана
            if (rect.top < window.innerHeight * 0.2 && 
                rect.width > 50 && rect.height > 10 &&
                rect.left < window.innerWidth * 0.5) {
              meetingTitleElement = el;
              log(' ✅ Found meeting title by position:', text);
              break;
            }
          }
        }
      }
      
      // Вставляем кнопку в контейнер под "Для интервьюеров:" (если он существует)
      let inserted = false;
      if (targetContainer) {
        try {
          // Вставляем в контейнер кнопок под "Для интервьюеров:"
          targetContainer.appendChild(levelButton);
          log(' ✅ Level button inserted into buttons container under "Для интервьюеров:"');
          inserted = true;
        } catch (e) {
          log(' ⚠️ Failed to insert into buttons container:', e);
        }
      }
      
      // Если контейнера нет, пробуем вставить после названия встречи
      if (!inserted && meetingTitleElement) {
        try {
          // Ищем родительский контейнер названия
          let container = meetingTitleElement.parentElement;
          if (container) {
            // Вставляем после элемента с названием
            if (meetingTitleElement.nextSibling) {
              container.insertBefore(levelButton, meetingTitleElement.nextSibling);
            } else {
              container.appendChild(levelButton);
            }
            log(' ✅ Level button inserted after meeting title');
            inserted = true;
          }
        } catch (e) {
          log(' ⚠️ Failed to insert after meeting title:', e);
        }
      }
      
      // Если не удалось вставить после названия, пробуем вставить в контейнер кнопок управления
      // ВАЖНО: вставляем сразу ПОСЛЕ кнопки информации
      if (!inserted) {
        try {
          if (buttonContainer && infoButton && infoButton.parentNode === buttonContainer) {
            // Вставляем сразу после кнопки информации
            if (infoButton.nextSibling) {
              buttonContainer.insertBefore(levelButton, infoButton.nextSibling);
            } else {
              buttonContainer.appendChild(levelButton);
            }
            log(' ✅ Level button inserted after info button');
            inserted = true;
          } else if (buttonContainer) {
            buttonContainer.appendChild(levelButton);
            log(' ✅ Level button appended to container (fallback)');
            inserted = true;
          }
        } catch (e) {
          log(' ⚠️ Failed to insert in button container:', e);
        }
      }
      
      // Если все еще не удалось, пробуем вставить в body
      if (!inserted) {
        try {
          document.body.appendChild(levelButton);
          levelButton.style.position = 'fixed';
          levelButton.style.top = '20px';
          levelButton.style.right = '20px';
          levelButton.style.zIndex = '99999';
          log(' ✅ Level button inserted in body as fallback (fixed position)');
          inserted = true;
        } catch (e2) {
          logError(' ❌ Failed to insert level button even in body:', e2);
          return false;
        }
      }
      
      if (!inserted) {
        logError(' ❌ Could not insert level button anywhere!');
        return false;
      }
      
      // Проверяем, что кнопка действительно в DOM
      if (!document.contains(levelButton)) {
        logError(' ❌ Level button was not inserted into DOM!');
        return false;
      }
      
      log(' ✅ Level button successfully inserted into DOM');
      log(' Level button parent:', levelButton.parentElement);
      log(' Level button computed style display:', window.getComputedStyle(levelButton).display);
      log(' Level button offsetParent:', levelButton.offsetParent);
      const rect = levelButton.getBoundingClientRect();
      log(' Level button getBoundingClientRect:', { 
        top: rect.top, 
        left: rect.left, 
        bottom: rect.bottom, 
        right: rect.right, 
        width: rect.width, 
        height: rect.height,
        visible: rect.width > 0 && rect.height > 0
      });
      
      // Проверяем видимость кнопки
      const isVisible = rect.width > 0 && rect.height > 0 && 
                        rect.top >= 0 && rect.left >= 0 &&
                        rect.top < window.innerHeight && rect.left < window.innerWidth;
      
      if (!isVisible) {
        log(' ⚠️ Level button is not visible! Moving it to a visible location...');
        
        // Пробуем найти кнопку соцсети и вставить рядом с ней
        const socialButton = document.querySelector('[data-hrhelper="social-button"], .hrhelper-communication-btn');
        if (socialButton && socialButton.parentElement) {
          try {
            // Удаляем кнопку из текущего места
            if (levelButton.parentElement) {
              levelButton.parentElement.removeChild(levelButton);
            }
            
            // Вставляем после кнопки соцсети
            if (socialButton.nextSibling) {
              socialButton.parentElement.insertBefore(levelButton, socialButton.nextSibling);
            } else {
              socialButton.parentElement.appendChild(levelButton);
            }
            
            log(' ✅ Level button moved next to social button');
          } catch (e) {
            log(' ⚠️ Failed to move button:', e);
          }
        } else {
          // Если кнопки соцсети нет, вставляем в body с фиксированной позицией
          try {
            if (levelButton.parentElement) {
              levelButton.parentElement.removeChild(levelButton);
            }
            document.body.appendChild(levelButton);
            levelButton.style.position = 'fixed';
            levelButton.style.bottom = '80px';
            levelButton.style.right = '20px';
            levelButton.style.zIndex = '99999';
            log(' ✅ Level button moved to fixed position in body');
          } catch (e) {
            log(' ⚠️ Failed to move button to body:', e);
          }
        }
      }
      
      // Принудительно показываем кнопку
      levelButton.style.display = 'inline-flex';
      levelButton.style.visibility = 'visible';
      levelButton.style.opacity = '1';
      
      // Проверяем видимость еще раз после перемещения
      const newRect = levelButton.getBoundingClientRect();
      const nowVisible = newRect.width > 0 && newRect.height > 0;
      log(' Level button visibility after fix:', nowVisible);
      if (nowVisible) {
        log(' ✅ Level button should be visible now!');
      } else {
        log(' ❌ Level button is still not visible');
      }
      
      log(' Level button inserted, will fetch level when Huntflow link appears...');
      
      // Функция для поиска ссылки на Huntflow и обновления кнопки
      const updateLevelFromHuntflowLink = () => {
        // Ищем ссылку на Huntflow
        let huntflowLink = null;
        
        // Сначала ищем в тексте "Для интервьюеров:"
        const walker = document.createTreeWalker(
          document.body,
          NodeFilter.SHOW_TEXT,
          null
        );
        
        let textNode;
        while (textNode = walker.nextNode()) {
          if (textNode.textContent && textNode.textContent.includes('Для интервьюеров:')) {
            // Ищем ссылку на Huntflow рядом с этим текстом
            let container = textNode.parentElement;
            for (let i = 0; i < 10 && container; i++) {
              const links = Array.from(container.querySelectorAll('a'));
              huntflowLink = links.find(link => {
                const href = link.href || link.textContent || '';
                return href.includes('huntflow.ru') || href.includes('huntflow.dev');
              });
              if (huntflowLink) break;
              container = container.parentElement;
            }
            if (huntflowLink) break;
          }
        }
        
        // Если не нашли, ищем во всем документе
        if (!huntflowLink) {
          huntflowLink = Array.from(document.querySelectorAll('a[href*="huntflow"]')).find(link => {
            const href = link.href || link.textContent || '';
            return href.includes('huntflow.ru') || href.includes('huntflow.dev');
          });
        }
        
        if (!huntflowLink) {
          log(' No Huntflow link found yet, will retry...');
          return false; // Ссылка еще не появилась
        }
        
        log(' ✅ Found Huntflow link:', huntflowLink.href);
      
        // Извлекаем URL Huntflow
        let huntflowUrl = huntflowLink.href;
        if (huntflowUrl.includes('google.com/url')) {
          // Если это Google redirect URL
          try {
            const urlObj = new URL(huntflowUrl);
            const realUrl = urlObj.searchParams.get('q');
            if (realUrl) {
              huntflowUrl = decodeURIComponent(realUrl);
            }
          } catch (e) {
            log(' Error extracting real URL from Google redirect:', e);
          }
        }
        
        // Если не нашли в href, пробуем из текста
        if (!huntflowUrl || !huntflowUrl.includes('huntflow')) {
          const linkText = huntflowLink.textContent || '';
          const urlMatch = linkText.match(/https?:\/\/[^\s]+huntflow[^\s]*/);
          if (urlMatch) {
            huntflowUrl = urlMatch[0];
          }
        }
        
        if (!huntflowUrl || !huntflowUrl.includes('huntflow')) {
          log(' Could not extract Huntflow URL');
          return false;
        }
        
        log(' Extracted Huntflow URL:', huntflowUrl);
        
        // Проверяем, что функция getCandidateLevel доступна
        if (typeof getCandidateLevel !== 'function') {
          logError(' getCandidateLevel is not a function!');
          return false;
        }
        
        log(' Calling getCandidateLevel with URL:', huntflowUrl);
        
        // Получаем уровень и вакансию через API
        getCandidateLevel(huntflowUrl).then(levelData => {
        log(' Candidate level response:', levelData);
        if (levelData && levelData.success && levelData.level) {
          const level = levelData.level;
          const vacancyName = (levelData.vacancy_name || '').trim();
          STATE.meet.level = level;
          STATE.meet.vacancyName = vacancyName;
          levelButton.textContent = vacancyName ? `${vacancyName}: ${level}` : level;
          levelButton.title = vacancyName
            ? `${vacancyName}: ${level} (нажмите для копирования текста)`
            : `Уровень кандидата: ${level} (нажмите для копирования текста)`;
          levelButton.setAttribute('data-level', level);
          levelButton.setAttribute('data-vacancy', vacancyName);
          levelButton.disabled = false;
          levelButton.style.opacity = '1';
          levelButton.style.cursor = 'pointer';
          levelButton.style.background = '#0a66c2';
          log(' ✅ Level button updated with level:', level, 'vacancy:', vacancyName);
          
          // Обработчик клика: копируем текст для (вакансия, грейд) из LevelText
          levelButton.addEventListener('click', async function(e) {
            e.preventDefault();
            e.stopPropagation();
            
            const buttonLevel = this.getAttribute('data-level');
            const buttonVacancy = this.getAttribute('data-vacancy') || '';
            if (!buttonLevel) {
              log(' ⚠️ No level data on button');
              return;
            }
            
            log(' Level button clicked, fetching text for vacancy:', buttonVacancy, 'level:', buttonLevel);
            
            try {
              const q = new URLSearchParams({ level: buttonLevel });
              if (buttonVacancy) q.set('vacancy_name', buttonVacancy);
              const apiUrl = `/api/v1/huntflow/linkedin-applicants/level-text/?${q.toString()}`;
              log(' Fetching level text from:', apiUrl);
              
              const res = await apiFetch(apiUrl, { method: 'GET' });
              const data = await res.json();
              log(' Level text response:', data);
              
              if (data && data.success && data.text) {
                await navigator.clipboard.writeText(data.text);
                log(' ✅ Text copied to clipboard');
                const originalText = this.textContent;
                this.textContent = 'Скопировано!';
                this.style.background = '#28a745';
                setTimeout(() => {
                  this.textContent = originalText;
                  this.style.background = '#0a66c2';
                }, 2000);
              } else {
                log(' ⚠️ No text for vacancy:', buttonVacancy, 'level:', buttonLevel);
                const originalText = this.textContent;
                this.textContent = 'Нет текста';
                this.style.background = '#dc3545';
                setTimeout(() => {
                  this.textContent = originalText;
                  this.style.background = '#0a66c2';
                }, 2000);
              }
            } catch (err) {
              logError(' Error copying level text:', err);
              const originalText = this.textContent;
              this.textContent = 'Ошибка';
              this.style.background = '#dc3545';
              setTimeout(() => {
                this.textContent = originalText;
                this.style.background = '#0a66c2';
              }, 2000);
            }
          });
          
          // Проверяем видимость еще раз после обновления
          const rect = levelButton.getBoundingClientRect();
          if (rect.width === 0 || rect.height === 0) {
            log(' ⚠️ Button is still not visible after update, trying to move it...');
            // Пробуем переместить кнопку рядом с кнопкой соцсети
            const socialButton = document.querySelector('[data-hrhelper="social-button"], .hrhelper-communication-btn');
            if (socialButton && socialButton.parentElement) {
              try {
                if (levelButton.parentElement) {
                  levelButton.parentElement.removeChild(levelButton);
                }
                if (socialButton.nextSibling) {
                  socialButton.parentElement.insertBefore(levelButton, socialButton.nextSibling);
                } else {
                  socialButton.parentElement.appendChild(levelButton);
                }
                log(' ✅ Level button moved next to social button after update');
              } catch (e) {
                log(' ⚠️ Failed to move button after update:', e);
              }
            }
          }
        } else {
          levelButton.textContent = 'Уровень';
          levelButton.disabled = true;
          levelButton.style.opacity = '0.6';
          levelButton.style.cursor = 'not-allowed';
          levelButton.style.background = '#6c757d';
          levelButton.style.opacity = '0.6';
          log(' Level not found or empty. Response:', levelData);
        }
      }).catch(err => {
          logError(' Error getting candidate level:', err);
          levelButton.textContent = 'Уровень';
          levelButton.disabled = true;
          levelButton.style.cursor = 'not-allowed';
          levelButton.style.opacity = '0.6';
          levelButton.style.background = '#6c757d';
        });

        return true; // Успешно обновлено
      };
      
      if (!updateLevelFromHuntflowLink()) {
        levelButton.textContent = 'Уровень';
        levelButton.disabled = true;
        const fastDelays = [150, 400, 800, 1200];
        fastDelays.forEach((delay, i) => {
          setTimeout(() => {
            if (levelButton.disabled && updateLevelFromHuntflowLink()) {
              log(' Level updated at fast delay', delay, 'ms');
            }
          }, delay);
        });
        const checkInterval = setInterval(() => {
          if (updateLevelFromHuntflowLink()) {
            clearInterval(checkInterval);
          }
        }, 1500);
        setTimeout(() => clearInterval(checkInterval), 45000);
      }
      
      return true; // Успешно создана и вставлена кнопка
    } catch (err) {
      logError(' Error in addLevelButtonToMeetControls:', err);
      return false; // Ошибка при выполнении
    }
  }
  
  // Функция для обработки с повторными попытками
  function processWithRetries() {
    log(' ========== Starting Google Meet processing ==========');
    log(' getCandidateLevel available:', typeof getCandidateLevel === 'function');
    log(' processInterviewerLinks available:', typeof processInterviewerLinks === 'function');
    log(' addLevelButtonToMeetControls available:', typeof addLevelButtonToMeetControls === 'function');
    log(' Current URL:', location.href);
    log(' Document ready state:', document.readyState);
    log(' Body exists:', !!document.body);
    log(' Total buttons on page:', document.querySelectorAll('button').length);
    
    // Пробуем сразу
    log(' === Attempt 1: Immediate ===');
    processInterviewerLinks();
    const result1 = addLevelButtonToMeetControls();
    log(' addLevelButtonToMeetControls result (immediate):', result1);
    
    // Пробуем с разными задержками (Google Meet загружается очень долго)
    const delays = [500, 1000, 2000, 3000, 5000, 8000, 12000, 15000, 20000];
    delays.forEach((delay, index) => {
      setTimeout(() => {
        log(` === Attempt ${index + 2}: After ${delay}ms delay ===`);
        log(' Buttons on page:', document.querySelectorAll('button').length);
        log(' Level button exists:', !!document.querySelector('.hrhelper-meet-level-btn'));
        processInterviewerLinks();
        const result = addLevelButtonToMeetControls();
        log(' addLevelButtonToMeetControls result:', result);
        if (result) {
          log(' ✅ SUCCESS! Level button should be visible now');
        }
      }, delay);
    });
  }
  
  // Обрабатываем с повторными попытками
  processWithRetries();
  
  // Наблюдаем за изменениями DOM с debounce
  let processTimeout = null;
  const observer = new MutationObserver(() => {
    if (processTimeout) clearTimeout(processTimeout);
    processTimeout = setTimeout(() => {
      processInterviewerLinks();
      addLevelButtonToMeetControls();
    }, 1000);
  });
  
  if (document.body) {
    observer.observe(document.body, {
      childList: true,
      subtree: true
    });
    log(' MutationObserver started');
  } else {
    log(' document.body not ready, waiting...');
    setTimeout(() => {
      if (document.body) {
        observer.observe(document.body, {
          childList: true,
          subtree: true
        });
        log(' MutationObserver started (delayed)');
      }
    }, 1000);
  }
}

log(' Content script loaded');

(async function runWhenPageEnabled() {
  const ACTIVE_PAGES_KEY = HRH.ACTIVE_PAGES_KEY;
  const DEFAULT_ACTIVE_PAGES = HRH.DEFAULT_ACTIVE_PAGES;
  if (!ACTIVE_PAGES_KEY || !DEFAULT_ACTIVE_PAGES) {
    throw new Error("[HRHelper] shared/constants.js not loaded (ACTIVE_PAGES_KEY/DEFAULT_ACTIVE_PAGES missing)");
  }
  function getPageType() {
    const h = location.hostname.toLowerCase();
    if (h.includes('linkedin.com')) return 'linkedin';
    if (h.includes('calendar.google.com')) return 'calendar';
    if (h.includes('meet.google.com')) return 'meet';
    return null;
  }
  const pageType = getPageType();
  if (pageType) {
    try {
      const data = await chrome.storage.sync.get({ [ACTIVE_PAGES_KEY]: DEFAULT_ACTIVE_PAGES });
      const active = data[ACTIVE_PAGES_KEY] || DEFAULT_ACTIVE_PAGES;
      if (!active[pageType]) return;
    } catch (_) {
      return;
    }
  }

  updateResolvedWidgetTheme();

  if (IS_GOOGLE_CALENDAR) {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', initGoogleCalendar);
    } else {
      initGoogleCalendar();
    }
  }
  if (IS_GOOGLE_MEET) {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', initGoogleMeet);
    } else {
      initGoogleMeet();
    }
  }
  if (!IS_GOOGLE_CALENDAR && !IS_GOOGLE_MEET) {
    log(' Starting initialization...');
    captureProfileToThreadMapping();
    startObserver();
  }
})();
