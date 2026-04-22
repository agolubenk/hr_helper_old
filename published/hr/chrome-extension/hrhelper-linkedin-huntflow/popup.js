const HRH = window.__HRH__;
if (!HRH) {
  throw new Error("[HRHelper] shared/constants.js not loaded");
}
const DEFAULTS = HRH.DEFAULTS;
if (!DEFAULTS) {
  throw new Error("[HRHelper] shared/constants.js not loaded (DEFAULTS missing)");
}

const eventBus = (HRH.eventBus) || { on:function(){}, once:function(){}, off:function(){}, emit:function(){} };
const apiFetch = HRH.apiFetch;
if (!apiFetch) {
  throw new Error("[HRHelper] shared/api/client.js not loaded (apiFetch missing)");
}

const CONTEXT = {
  LINKEDIN: 'linkedin',
  CALENDAR: 'calendar',
  MEET: 'meet',
  RESUME: 'resume',
  HUNTFLOW: 'huntflow',
  GDRIVE: 'gdrive',
  OTHER: 'other',
};

let currentGDriveFileId = null;
let parsedCandidateData = null;
let selectedVacancyId = null;

/** Базовая часть URL (до ? и #) для сопоставления и хранения */
var getBaseUrl = HRH.getBaseUrl;
if (!getBaseUrl) {
  throw new Error("[HRHelper] shared/utils/url.js not loaded (getBaseUrl missing)");
}

/** ID резюме из пути /resume/{id} — один ключ для всех доменов */
function getResumeIdFromUrl(url) {
  if (!url || typeof url !== 'string') return null;
  try {
    const path = new URL(url.trim()).pathname || '';
    const m = path.match(/\/resume\/([^/?#]+)/i);
    return m ? m[1] : null;
  } catch (_) {
    return null;
  }
}

/** Проверка и нормализация ссылки Huntflow (huntflow.ru и поддомены) */
function normalizeHuntflowUrl(url) {
  if (!url || typeof url !== 'string') return null;
  try {
    const raw = url.trim();
    if (!raw) return null;
    const u = new URL(raw.startsWith('http') ? raw : 'https://' + raw);
    const host = u.hostname.toLowerCase();
    if (!host.includes('huntflow')) return null;
    return u.href;
  } catch (_) {
    return null;
  }
}

/** Нормализация ссылки на профиль LinkedIn */
var normalizeLinkedInProfileUrl = HRH.normalizeLinkedInProfileUrl;
if (!normalizeLinkedInProfileUrl) {
  throw new Error("[HRHelper] shared/utils/url.js not loaded (normalizeLinkedInProfileUrl missing)");
}

/** Ключ настроек «активных страниц» для контекста */
function getActivePageKeyFromContext(ctx) {
  if (ctx === CONTEXT.LINKEDIN) return 'linkedin';
  if (ctx === CONTEXT.RESUME) return 'hh_ecosystem';
  if (ctx === CONTEXT.HUNTFLOW) return 'huntflow';
  if (ctx === CONTEXT.MEET) return 'meet';
  if (ctx === CONTEXT.CALENDAR) return 'calendar';
  if (ctx === CONTEXT.GDRIVE) return 'gdrive';
  return null;
}

var ACTIVE_PAGES_KEY = HRH.ACTIVE_PAGES_KEY;
var DEFAULT_ACTIVE_PAGES = HRH.DEFAULT_ACTIVE_PAGES;
var OPTIONS_THEME_KEY = HRH.OPTIONS_THEME_KEY;
if (!ACTIVE_PAGES_KEY || !DEFAULT_ACTIVE_PAGES || !OPTIONS_THEME_KEY) {
  throw new Error("[HRHelper] shared/constants.js not loaded (active/theme keys missing)");
}

/** Применяет тему попапа из настроек: light | dark | system */
function applyPopupTheme(theme) {
  var t = (theme === 'light' || theme === 'dark') ? theme : 'system';
  document.body.classList.remove('popup-theme-light', 'popup-theme-dark', 'popup-theme-system');
  document.body.classList.add('popup-theme-' + t);
}

/** Загружает тему из storage и применяет к попапу */
function loadAndApplyPopupTheme() {
  chrome.storage.sync.get({ [OPTIONS_THEME_KEY]: 'system' }, function (data) {
    applyPopupTheme(data[OPTIONS_THEME_KEY]);
  });
}

/** Определяет контекст по URL вкладки */
function getContextFromUrl(url) {
  if (!url) return CONTEXT.OTHER;
  try {
    const u = new URL(url);
    const host = u.hostname.toLowerCase();
    const path = (u.pathname || '').toLowerCase();
    const hash = (u.hash || '').toLowerCase();
    if (host.includes('linkedin.com')) return CONTEXT.LINKEDIN;
    if (host.includes('calendar.google.com')) return CONTEXT.CALENDAR;
    if (host.includes('meet.google.com')) return CONTEXT.MEET;
    if (host.includes('drive.google.com') && (path.includes('/file/d/') || path.includes('/open'))) return CONTEXT.GDRIVE;
    if ((host === 'rabota.by' || host === 'www.rabota.by' || host.endsWith('.rabota.by') || host.endsWith('.hh.ru')) && path.includes('/resume/')) return CONTEXT.RESUME;
    if (host === 'hh.ru' && path.includes('/resume/')) return CONTEXT.RESUME;
    if (host.includes('huntflow') && (path.includes('/my') || hash.includes('/my')) && (hash.includes('applicants/filter/all') || (hash.includes('applicants') && hash.includes('/id/')) || (hash.includes('vacancy') && hash.includes('/id/')) || (hash.includes('applicants') && /\/filter\/[\d]+\/[\d]+/.test(hash)))) return CONTEXT.HUNTFLOW;
  } catch (_) {}
  return CONTEXT.OTHER;
}

/** Иконка для кнопки контакта Meet по типу ресурса (Telegram, Viber, LinkedIn, WhatsApp) */
function getMeetContactIcon(label, url) {
  const l = (label || '').toLowerCase();
  const u = (url || '').toLowerCase();
  let type = '';
  if (l.includes('telegram') || u.includes('t.me') || u.includes('telegram')) type = 'telegram';
  else if (l.includes('viber') || u.includes('viber')) type = 'viber';
  else if (l.includes('linkedin') || u.includes('linkedin')) type = 'linkedin';
  else if (l.includes('whatsapp') || u.includes('wa.me') || u.includes('whatsapp')) type = 'whatsapp';
  const size = 20;
  const svg = (path, viewBox = '0 0 24 24') => `<svg viewBox="${viewBox}" width="${size}" height="${size}" fill="currentColor" aria-hidden="true"><path d="${path}"/></svg>`;
  switch (type) {
    case 'telegram':
      return svg('M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm4.64 6.8c-.15 1.58-.8 5.42-1.13 7.19-.14.75-.42 1-.68 1.03-.58.05-1.02-.38-1.58-.75-.88-.58-1.38-.94-2.23-1.5-.99-.65-.35-1.01.22-1.59.15-.15 2.71-2.48 2.76-2.69a.2.2 0 00-.05-.18c-.06-.05-.14-.03-.21-.02-.09.02-1.49.95-4.22 2.79-.4.27-.76.41-1.08.4-.36-.01-1.04-.2-1.55-.37-.63-.2-1.12-.31-1.08-.66.02-.18.27-.36.74-.55 2.92-1.27 4.86-2.11 5.83-2.53 2.78-1.16 3.35-1.36 3.73-1.36.08 0 .27.02.39.12.1.08.13.19.14.27-.01.06.01.24 0 .38z');
    case 'viber':
      return svg('M11.4 0C9.473.028 5.333.344 2.986 2.458 1.244 4.244.387 6.627.258 9.377c-.124 2.648.387 5.21 1.502 7.35L0 24l7.373-1.932a11.4 11.4 0 005.56 1.446h.004c2.99 0 5.848-1.166 7.958-3.273 2.11-2.108 3.276-4.966 3.273-7.958C24 5.25 18.75 0 11.4 0zm6.694 16.12c-.478.478-1.134.745-1.826.84-.378.052-1.726.158-5.006-.588-.963-.22-2.01-.55-3.116-1.004-3.94-1.61-6.81-4.69-6.93-4.81-.12-.12-.95-1.26-.95-2.4s.6-1.72.85-1.96c.22-.22.48-.33.76-.33.12 0 .23.01.34.02.11.01.26-.02.41.14.14.14.54.53.74.73.2.2.34.44.44.7.1.26.17.56.01.88-.16.32-.74 1.24-1.01 1.67-.27.43-.54.48-.9.48h-.34c-.17 0-.43.07-.7.34-.27.27-1.04 1.02-1.95 1.95-.76.77-1.44 1.28-1.94 1.63-.57.39-.99.6-1.36.62-.36.02-.85-.17-1.3-.62-.45-.45-1.05-1.17-1.63-1.94-.58-.77-1.08-1.44-1.28-1.7-.2-.27-.2-.5-.2-.67 0-.17.09-.43.24-.58.24-.24.5-.53.75-.82.25-.3.5-.58.67-.78.16-.2.36-.43.6-.43.2 0 .4.1.61.3.2.2.86.82 1.18 1.13.32.31.64.65.96.98.32.33.64.63.96.93.32.3.67.56.93.56.26 0 .43-.21.64-.42.2-.21.43-.46.7-.73.26-.27.55-.4.88-.4.33 0 .66.17.99.5z');
    case 'linkedin':
      return svg('M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z');
    case 'whatsapp':
      return svg('M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z');
    default:
      return svg('M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm0 14H5.17L4 17.17V4h16v12z');
  }
}

let currentTabId = null;

const RESUME_STORAGE_KEY = 'hrhelper_resume_state';

/** Загрузить сохранённое состояние для страницы резюме. Ключ — resume_id (часть после /resume/). */
async function loadResumeState(pageUrl) {
  const rid = getResumeIdFromUrl(pageUrl);
  if (!rid) return null;
  try {
    const data = await chrome.storage.local.get(RESUME_STORAGE_KEY);
    const map = data[RESUME_STORAGE_KEY];
    const state = map && map[rid] && map[rid].huntflowUrl ? map[rid] : null;
    return state;
  } catch (_) {
    return null;
  }
}

/** Сохранить состояние для страницы резюме. Ключ — resume_id. */
async function saveResumeState(pageUrl, state) {
  const key = getResumeIdFromUrl(pageUrl);
  if (!key) return;
  try {
    const data = await chrome.storage.local.get(RESUME_STORAGE_KEY);
    const map = data[RESUME_STORAGE_KEY] || {};
    map[key] = {
      huntflowUrl: state.huntflowUrl ?? null,
      saved: !!state.saved,
      candidateInfo: state.candidateInfo ?? null,
      vacancy_name: state.vacancy_name ?? null,
      status_name: state.status_name ?? null,
      status_id: state.status_id ?? null,
      rejection_reason_id: state.rejection_reason_id ?? null,
      rejection_reason_name: state.rejection_reason_name ?? null,
      last_comment_datetime: state.last_comment_datetime ?? null,
    };
    await chrome.storage.local.set({ [RESUME_STORAGE_KEY]: map });
  } catch (_) {}
}

/** Состояние блока LinkedIn/Resume: профиль, ссылка Huntflow, сохранение, данные кандидата */
let linkedinState = {
  profileUrl: null,
  huntflowUrl: null,
  saved: false,
  candidateInfo: null,
  vacancies: [],
  defaultVacancyId: null,
  selectedVacancyId: null,
};

/** Текущий контекст вкладки (linkedin | resume | other | ...) для логики Apply */
const createStateManager = HRH.createStateManager;
const popupState = createStateManager ? createStateManager({ currentContext: CONTEXT.OTHER }) : {
  _s: { currentContext: CONTEXT.OTHER },
  getState: function () { return this._s; },
  setState: function (patch) { if (patch && typeof patch === 'object') { this._s = Object.assign({}, this._s, patch); } },
  subscribe: function () { return function () {}; }
};

let currentContext = CONTEXT.OTHER;

/** Панель добавления на вакансию: открыта/закрыта */
let addVacancyPanelOpen = false;

/** Конфиг API из storage */
async function getApiConfig() {
  const cfg = await chrome.storage.sync.get(DEFAULTS);
  const baseUrl = (cfg.baseUrl || DEFAULTS.baseUrl).replace(/\/+$/, '');
  const apiToken = normalizeToken((cfg.apiToken || '').trim());
  return { baseUrl, apiToken };
}

/** Отправить связь резюме → Huntflow на сервер (для отображения на /extension/). resume_url — base (до ?). */
async function saveResumeLinkToBackend(pageUrl, state) {
  if (!pageUrl || !state?.huntflowUrl) return;
  const resumeUrl = getBaseUrl(pageUrl);
  if (!resumeUrl) return;
  try {
    await apiFetch('/api/v1/huntflow/resume-links/', {
      method: 'POST',
      body: {
        resume_url: resumeUrl,
        huntflow_url: state.huntflowUrl,
        vacancy_name: state.vacancy_name || '',
      },
    });
  } catch (_) {}
}

/** GET status по LinkedIn-профилю (есть ли сохранённая ссылка Huntflow) */
async function fetchStatus(linkedinUrl) {
  const normalized = normalizeLinkedInProfileUrl(linkedinUrl);
  if (!normalized) return { error: 'Некорректная ссылка на профиль LinkedIn' };
  try {
    const q = new URLSearchParams({ linkedin_url: normalized });
    const res = await apiFetch('/api/v1/huntflow/linkedin-applicants/status/?' + q.toString(), { method: 'GET' });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) return { error: data?.message || data?.error || 'Ошибка ' + res.status };
    const appUrl = data?.app_url || data?.data?.app_url;
    return {
      profileUrl: normalized,
      huntflowUrl: appUrl || null,
      saved: !!appUrl,
      vacancy_name: data?.vacancy_name ?? null,
      status_name: data?.status_name ?? null,
      status_id: data?.status_id != null ? data.status_id : null,
      rejection_reason_id: data?.rejection_reason_id != null ? data.rejection_reason_id : null,
      rejection_reason_name: data?.rejection_reason_name ?? null,
      last_comment_datetime: data?.last_comment_datetime ?? null,
    };
  } catch (e) {
    return { error: e.message || 'Ошибка сети' };
  }
}

/** GET status-multi: все вакансии кандидата (для множественных вакансий) */
async function fetchStatusMulti(linkedinUrl, huntflowUrl) {
  const normalized = linkedinUrl ? normalizeLinkedInProfileUrl(linkedinUrl) : null;
  const huntNorm = huntflowUrl ? normalizeHuntflowUrl(huntflowUrl) : null;
  if (!normalized && !huntNorm) return { error: 'Нужен linkedin_url или huntflow_url' };
  try {
    const shared = HRH.fetchStatusMulti;
    if (!shared) throw new Error("shared/api/status.js not loaded");
    const data = await shared({ linkedinUrl: normalized || null, huntflowUrl: huntNorm || null });
    if (!data || data.error) return { error: data?.error || 'Ошибка' };
    const items = data.items || [];
    const defaultItem = getDefaultVacancyItem(items, data.default_vacancy_id);
    const legacy = convertMultiToLegacyFormat(data);
    return {
      profileUrl: normalized,
      saved: items.length > 0,
      vacancies: items,
      defaultVacancyId: data.default_vacancy_id,
      huntflowUrl: legacy.appurl || null,
      vacancy_name: legacy.vacancyname ?? null,
      status_name: legacy.statusname ?? null,
      status_id: legacy.statusid ?? null,
      rejection_reason_id: legacy.rejectionreasonid ?? null,
      rejection_reason_name: legacy.rejectionreasonname ?? null,
      last_comment_datetime: legacy.lastcommentdatetime ?? null,
    };
  } catch (e) {
    return { error: e.message || 'Ошибка сети' };
  }
}

/** GET status по ссылке Huntflow (для страниц резюме rabota.by / hh.ru) */
async function fetchStatusByHuntflowUrl(huntflowUrl) {
  const normalized = normalizeHuntflowUrl(huntflowUrl);
  if (!normalized) return { error: 'Некорректная ссылка Huntflow' };
  try {
    const q = new URLSearchParams({ huntflow_url: normalized });
    const res = await apiFetch('/api/v1/huntflow/linkedin-applicants/status/?' + q.toString(), { method: 'GET' });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) return { error: data?.message || data?.error || 'Ошибка ' + res.status };
    const appUrl = data?.app_url || data?.huntflow_url;
    return {
      profileUrl: null,
      huntflowUrl: appUrl || normalized,
      saved: true,
      vacancy_name: data?.vacancy_name ?? null,
      status_name: data?.status_name ?? null,
      status_id: data?.status_id != null ? data.status_id : null,
      rejection_reason_id: data?.rejection_reason_id != null ? data.rejection_reason_id : null,
      rejection_reason_name: data?.rejection_reason_name ?? null,
      last_comment_datetime: data?.last_comment_datetime ?? null,
    };
  } catch (e) {
    return { error: e.message || 'Ошибка сети' };
  }
}

/** GET candidate-info по ссылке Huntflow (ФИО, контакты, вакансия и т.д.) */
async function fetchCandidateInfo(huntflowUrl) {
  const normalized = normalizeHuntflowUrl(huntflowUrl);
  if (!normalized) return null;
  try {
    const q = new URLSearchParams({ huntflow_url: normalized });
    const res = await apiFetch('/api/v1/huntflow/linkedin-applicants/candidate-info/?' + q.toString(), { method: 'GET' });
    const data = await res.json().catch(() => ({}));
    if (!res.ok || !data?.success) return null;
    return {
      full_name: data.full_name ?? null,
      vacancy_name: data.vacancy_name ?? null,
      phone: data.phone ?? null,
      email: data.email ?? null,
      telegram: data.telegram ?? null,
      communication: data.communication ?? null,
      office_readiness: data.office_readiness ?? null,
      level: data.level ?? null,
      status_name: data.status_name ?? null,
    };
  } catch (_) {
    return null;
  }
}

/** POST set-link: сохранить или обновить связь LinkedIn ↔ Huntflow */
async function fetchSetLink(linkedinUrl, huntflowUrl) {
  const profileNorm = normalizeLinkedInProfileUrl(linkedinUrl);
  const huntNorm = normalizeHuntflowUrl(huntflowUrl);
  if (!profileNorm) return { error: 'Некорректная ссылка на профиль LinkedIn' };
  if (!huntNorm) return { error: 'Введите ссылку на Huntflow (например https://huntflow.ru/my/...)' };
  try {
    const payload = { linkedin_url: profileNorm, target_url: huntNorm };
    if (huntNorm.includes('#')) {
      const idx = huntNorm.indexOf('#');
      payload.target_url = huntNorm.slice(0, idx);
      payload.target_url_fragment = huntNorm.slice(idx + 1);
    }
    const res = await apiFetch('/api/v1/huntflow/linkedin-applicants/set-link/', {
      method: 'POST',
      body: payload,
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) return { error: data?.message || data?.error || 'Ошибка ' + res.status };
    return { success: true };
  } catch (e) {
    return { error: e.message || 'Ошибка сети' };
  }
}

const formRow = () => document.getElementById('ctx-linkedin-form-row');
const statusBlock = () => document.getElementById('ctx-linkedin-status-block');

/**
 * Построить массив vacancies из linkedinState, если он пуст (legacy/single-vacancy format).
 * Нужно для единого UI с карточками при одной вакансии.
 */
function ensureVacanciesForMultiUI() {
  if ((linkedinState.vacancies || []).length > 0) return;
  if (!linkedinState.huntflowUrl || !linkedinState.saved) return;
  const isRejected = linkedinState.status_name && /отказ|reject|trash/i.test(String(linkedinState.status_name));
  linkedinState.vacancies = [{
    vacancy_id: 0,
    appurl: linkedinState.huntflowUrl,
    vacancy_name: linkedinState.vacancy_name || '—',
    status_name: linkedinState.status_name || null,
    status_id: linkedinState.status_id,
    last_change_at: new Date().toISOString(),
    status_type: isRejected ? 'rejected' : 'active',
    rejection_reason_name: linkedinState.rejection_reason_name || null,
    is_hired: false,
    is_archived: false,
  }];
  linkedinState.defaultVacancyId = 0;
  if (linkedinState.selectedVacancyId == null) linkedinState.selectedVacancyId = 0;
}

/**
 * Обновить кнопки в header: Huntflow рядом с настройками.
 * Показывать только когда есть сохранённая связь и НЕ календарь.
 * @param {boolean} show - показывать header-actions
 * @param {string|null} huntflowUrl - ссылка Huntflow
 * @param {boolean} showAddBtn - показывать кнопку «+» (добавить на вакансию)
 * @param {boolean} isRejection - класс rejection для кнопки Huntflow
 */
function updateHeaderActions(show, huntflowUrl, showAddBtn, isRejection) {
  const headerActions = document.getElementById('header-actions');
  const headerHuntflowBtn = document.getElementById('headerHuntflowBtn');
  const headerAddVacancyBtn = document.getElementById('headerAddVacancyBtn');
  const headerCopyBtn = document.getElementById('headerCopyHuntflowBtn');
  if (!headerActions || !headerHuntflowBtn) return;
  if (show && huntflowUrl) {
    headerActions.style.display = 'flex';
    headerHuntflowBtn.href = huntflowUrl;
    headerHuntflowBtn.style.display = 'inline-flex';
    headerHuntflowBtn.classList.toggle('rejection', !!isRejection);
    if (headerAddVacancyBtn) {
      headerAddVacancyBtn.style.display = showAddBtn ? 'inline-flex' : 'none';
    }
    if (headerCopyBtn) {
      headerCopyBtn.dataset.copyUrl = huntflowUrl;
      headerCopyBtn.style.display = 'inline-flex';
    }
    if (currentContext === CONTEXT.LINKEDIN) {
      const headerLinkedInFloatingBtn = document.getElementById('headerLinkedInFloatingBtn');
      if (headerLinkedInFloatingBtn) headerLinkedInFloatingBtn.style.display = 'inline-flex';
    }
  } else {
    headerActions.style.display = 'none';
    headerHuntflowBtn.href = '#';
    headerHuntflowBtn.classList.remove('rejection');
    if (headerCopyBtn) headerCopyBtn.style.display = 'none';
    if (currentContext === CONTEXT.LINKEDIN) {
      headerActions.style.display = 'flex';
      headerHuntflowBtn.style.display = 'none';
      if (headerAddVacancyBtn) headerAddVacancyBtn.style.display = 'none';
      if (headerCopyBtn) headerCopyBtn.style.display = 'none';
      const headerLinkedInFloatingBtn = document.getElementById('headerLinkedInFloatingBtn');
      if (headerLinkedInFloatingBtn) headerLinkedInFloatingBtn.style.display = 'inline-flex';
    }
    if (currentContext === CONTEXT.RESUME) {
      headerActions.style.display = 'flex';
      headerHuntflowBtn.style.display = 'none';
      if (headerAddVacancyBtn) headerAddVacancyBtn.style.display = 'none';
      const headerResumeFloatingBtn = document.getElementById('headerResumeFloatingBtn');
      if (headerResumeFloatingBtn) headerResumeFloatingBtn.style.display = 'inline-flex';
    }
    if (currentContext === CONTEXT.HUNTFLOW) {
      headerActions.style.display = 'flex';
      headerHuntflowBtn.style.display = 'none';
      if (headerAddVacancyBtn) headerAddVacancyBtn.style.display = 'none';
      if (headerCopyBtn) headerCopyBtn.style.display = 'none';
      const headerHuntflowFloatingBtn = document.getElementById('headerHuntflowFloatingBtn');
      if (headerHuntflowFloatingBtn) headerHuntflowFloatingBtn.style.display = 'inline-flex';
    }
  }
}

/** Показать/скрыть кнопки и сообщения в зависимости от контекста и наличия сохранения */
function renderLinkedInUI() {
  const input = document.getElementById('ctx-linkedin-input');
  const messageEl = document.getElementById('ctx-linkedin-message');
  const descEl = document.getElementById('ctx-linkedin-desc');
  const saveBtn = document.getElementById('ctx-linkedin-save');
  const applyBtn = document.getElementById('ctx-linkedin-apply');
  const huntflowBtn = document.getElementById('ctx-linkedin-huntflow');
  const copyBtn = document.getElementById('ctx-linkedin-copy');
  const editBtn = document.getElementById('ctx-linkedin-edit');
  const formRowEl = formRow();
  const statusBlockEl = statusBlock();
  const titleEl = document.getElementById('ctx-linkedin-title');
  const fioEl = document.getElementById('ctx-linkedin-fio');
  const candidateBlockEl = document.getElementById('ctx-linkedin-candidate-block');
  const candidateBodyEl = document.getElementById('ctx-linkedin-candidate-body');
  const candidateToggleEl = document.getElementById('ctx-linkedin-candidate-toggle');

  const hasProfile = !!linkedinState.profileUrl;
  const saved = linkedinState.saved && linkedinState.huntflowUrl;
  const showSavedUI = (hasProfile && saved) || (currentContext === CONTEXT.RESUME && saved) || (currentContext === CONTEXT.HUNTFLOW && saved);

  if (showSavedUI) {
    ensureVacanciesForMultiUI();
    renderMultiVacancyUI();
    return;
  }
  // В остальных состояниях не показываем блок быстрых кнопок (нужно наличие выбранной вакансии)
  setCopyButtonsVisible(false);
  updateCopyButtonsDisabledState();

  const statusBlockElForClass = statusBlock();
  if (statusBlockElForClass) statusBlockElForClass.classList.remove('has-vacancies');

  if (titleEl) {
    if (currentContext === CONTEXT.RESUME || currentContext === CONTEXT.HUNTFLOW) {
      titleEl.textContent = linkedinState.candidateInfo?.full_name || 'Кандидат';
      titleEl.style.display = 'block';
    } else {
      titleEl.textContent = 'LinkedIn';
      titleEl.style.display = 'block';
    }
  }

  if (messageEl) messageEl.style.display = 'none';
  if (descEl) {
    if (currentContext === CONTEXT.RESUME) {
      descEl.style.display = 'none';
    } else if (hasProfile && !saved) {
      descEl.textContent = 'Ссылка на кандидата в Huntflow не сохранена. Вставьте ссылку и нажмите «Сохранить».';
      descEl.style.display = 'block';
    } else if (hasProfile && saved) {
      descEl.textContent = '';
      descEl.style.display = 'none';
    } else {
      descEl.style.display = 'none';
    }
  }

  if (hasProfile && !saved) {
    linkedinState.vacancy_name = null;
    linkedinState.status_name = null;
    linkedinState.status_id = null;
    linkedinState.rejection_reason_id = null;
    linkedinState.rejection_reason_name = null;
    linkedinState.last_comment_datetime = null;
    updateHeaderActions(false);
    if (messageEl) {
      messageEl.textContent = 'Вставьте ссылку на кандидата в Huntflow и нажмите «Сохранить».';
      messageEl.style.display = 'block';
    }
    if (formRowEl) formRowEl.style.display = 'block';
    if (statusBlockEl) statusBlockEl.style.display = 'none';
    if (input) input.value = '';
    if (saveBtn) saveBtn.style.display = 'inline-block';
    if (applyBtn) applyBtn.style.display = 'none';
    if (huntflowBtn) huntflowBtn.style.display = 'none';
    if (copyBtn) copyBtn.style.display = 'none';
    if (editBtn) editBtn.style.display = 'none';
    return;
  }

  const vacancyEl = document.getElementById('ctx-linkedin-vacancy');
  const lastCommentEl = document.getElementById('ctx-linkedin-last-comment');
  const reasonRowEl = document.getElementById('ctx-linkedin-reason-row');
  if (fioEl) {
    if (currentContext === CONTEXT.RESUME && linkedinState.candidateInfo?.full_name) {
      fioEl.style.display = 'none';
    } else if (linkedinState.candidateInfo?.full_name) {
      fioEl.textContent = linkedinState.candidateInfo.full_name;
      fioEl.style.display = 'block';
    } else {
      fioEl.style.display = 'none';
    }
  }
  if (vacancyEl) {
    if (linkedinState.vacancy_name) {
      vacancyEl.textContent = 'Вакансия: ' + linkedinState.vacancy_name;
      vacancyEl.style.display = 'block';
    } else {
      vacancyEl.style.display = 'none';
    }
  }
  if (lastCommentEl) {
    if (linkedinState.last_comment_datetime) {
      lastCommentEl.innerHTML = '';
      lastCommentEl.appendChild(document.createTextNode('Последний комментарий: '));
      lastCommentEl.appendChild(document.createElement('br'));
      lastCommentEl.appendChild(document.createTextNode(linkedinState.last_comment_datetime));
      lastCommentEl.style.display = 'block';
    } else {
      lastCommentEl.style.display = 'none';
    }
  }
  if (reasonRowEl) reasonRowEl.style.display = 'none';

  if (candidateBlockEl && candidateBodyEl && candidateToggleEl) {
    const info = linkedinState.candidateInfo;
    const comm = info?.communication;
    const isCommTelegram = comm && /t\.me|telegram/i.test(String(comm));
    const rows = [
      ['Телефон', info?.phone],
      ['Email', info?.email],
      ['Telegram', info?.telegram],
      ['Где ведётся коммуникация', !isCommTelegram ? comm : null],
      ['Готовность к офису', info?.office_readiness],
      ['Уровень', info?.level],
    ].filter(([, v]) => v != null && v !== '');
    if (info && (info.phone || info.email || info.telegram || info.communication || info.office_readiness || info.level || rows.length > 0)) {
      candidateBlockEl.style.display = 'block';
      candidateBodyEl.innerHTML = rows.map(([label, value]) =>
        `<div class="ctx-candidate-row"><span class="ctx-candidate-label">${escapeHtml(label)}:</span> ${escapeHtml(String(value))}</div>`
      ).join('');
      candidateBodyEl.hidden = true;
      candidateToggleEl.setAttribute('aria-expanded', 'false');
    } else {
      candidateBlockEl.style.display = 'none';
    }
  }

  // Страница не LinkedIn / резюме без загруженной ссылки: ввод Huntflow и Применить / Открыть / Копировать
  updateHeaderActions(false);
  if (formRowEl) formRowEl.style.display = 'block';
  if (statusBlockEl) statusBlockEl.style.display = 'none';
  if (input) input.value = linkedinState.huntflowUrl || '';
  if (saveBtn) saveBtn.style.display = 'none';
  if (applyBtn) applyBtn.style.display = (currentContext === CONTEXT.RESUME || !linkedinState.huntflowUrl) ? 'inline-block' : 'none';
  if (huntflowBtn) {
    huntflowBtn.href = linkedinState.huntflowUrl || '#';
    huntflowBtn.style.display = linkedinState.huntflowUrl ? 'inline-flex' : 'none';
  }
  if (copyBtn) {
    copyBtn.dataset.copyUrl = linkedinState.huntflowUrl || '';
    copyBtn.style.display = linkedinState.huntflowUrl ? 'inline-flex' : 'none';
  }
  if (editBtn) editBtn.style.display = 'none';
}

function escapeHtml(s) {
  const div = document.createElement('div');
  div.textContent = s;
  return div.innerHTML;
}

// ===== Кнопки быстрого копирования (вакансия/вопросы/слоты) =====
const copyButtonsState = {
  externalId: null,
  vacancy: null, // данные Vacancy из HR Helper (id, links, questions)
  slotsSettings: null, // { currentWeekPrefix, nextWeekPrefix, allSlotsPrefix, separatorText }
  slotsCache: null, // { current: Slot[], next: Slot[] }
  thirdWeekSlots: null, // Slot[]
};

function getCopyButtonsContainer() {
  return document.getElementById('popup-copy-buttons');
}

function setCopyButtonsVisible(visible) {
  const el = getCopyButtonsContainer();
  if (!el) return;
  el.classList.toggle('visible', !!visible);
}

function flashCopySuccess(btn) {
  if (!btn) return;
  btn.classList.add('copy-success');
  const prevTitle = btn.title;
  btn.title = 'Скопировано';
  setTimeout(() => {
    btn.classList.remove('copy-success');
    btn.title = prevTitle;
  }, 1200);
}

async function copyToClipboard(text) {
  const t = (text || '').trim();
  if (!t) return false;
  try {
    await navigator.clipboard.writeText(t);
    return true;
  } catch (_) {
    return false;
  }
}

function parseDateStrDDMMYYYY(dateStr) {
  const m = String(dateStr || '').match(/^(\d{2})\.(\d{2})\.(\d{4})$/);
  if (!m) return null;
  const dd = parseInt(m[1], 10);
  const mm = parseInt(m[2], 10) - 1;
  const yyyy = parseInt(m[3], 10);
  // Полдень локального TZ — чтобы избежать сдвигов на границах суток.
  const d = new Date(yyyy, mm, dd, 12, 0, 0, 0);
  return isNaN(d.getTime()) ? null : d;
}

function weekStartMondayLocal(dateObj) {
  const d = new Date(dateObj.getFullYear(), dateObj.getMonth(), dateObj.getDate(), 12, 0, 0, 0);
  // JS: 0 = Sunday, 1 = Monday...
  const jsDay = d.getDay();
  const daysSinceMonday = (jsDay + 6) % 7;
  d.setDate(d.getDate() - daysSinceMonday);
  d.setHours(12, 0, 0, 0);
  return d;
}

function groupSlotsByWeek(slots) {
  const list = Array.isArray(slots) ? slots : [];
  if (list.length === 0) return { current: [], next: [] };
  const first = list[0];
  const baseDate = parseDateStrDDMMYYYY(first.dateStr) || (first.date ? new Date(first.date) : null);
  if (!baseDate || isNaN(baseDate.getTime())) return { current: list, next: [] };
  const baseWeekStart = weekStartMondayLocal(baseDate).getTime();
  const current = [];
  const next = [];
  for (const s of list) {
    const d = parseDateStrDDMMYYYY(s.dateStr) || (s.date ? new Date(s.date) : null);
    if (!d || isNaN(d.getTime())) {
      current.push(s);
      continue;
    }
    const ws = weekStartMondayLocal(d).getTime();
    if (ws === baseWeekStart) current.push(s);
    else next.push(s);
  }
  return { current, next };
}

async function fetchVacancyByExternalId(externalId) {
  const ext = String(externalId || '').trim();
  if (!ext) return null;
  const { baseUrl, apiToken } = await getApiConfig();
  if (!apiToken) return null;
  const url = `${baseUrl}/api/v1/vacancies/vacancies/by-external-id/?external_id=${encodeURIComponent(ext)}`;
  try {
    const res = await fetch(url, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json', 'Authorization': `Token ${apiToken}` },
    });
    const json = await res.json().catch(() => ({}));
    if (!res.ok || !json?.success) return null;
    return json.data || null;
  } catch (_) {
    return null;
  }
}

async function fetchSlotsSettings() {
  const { baseUrl, apiToken } = await getApiConfig();
  if (!apiToken) return null;
  try {
    const res = await fetch(`${baseUrl}/api/v1/google-oauth/slots-settings/`, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json', 'Authorization': `Token ${apiToken}` },
    });
    const json = await res.json().catch(() => ({}));
    if (!res.ok) return null;
    const data = json?.results || json?.data || json;
    const item = Array.isArray(data) ? data[0] : (Array.isArray(data?.results) ? data.results[0] : null);
    // Ожидаемые поля: current_week_prefix / next_week_prefix / all_slots_prefix / separator_text
    const s = item || null;
    if (!s) return null;
    return {
      currentWeekPrefix: s.current_week_prefix || '',
      nextWeekPrefix: s.next_week_prefix || '',
      allSlotsPrefix: s.all_slots_prefix || '',
      separatorText: s.separator_text || '---',
    };
  } catch (_) {
    return null;
  }
}

async function fetchInterviewSlotsViaSession(vacancyId) {
  const { baseUrl } = await getApiConfig();
  if (!baseUrl) return null;
  const url = `${baseUrl}/google-oauth/api/interview-slots/?vacancy_id=${encodeURIComponent(String(vacancyId || ''))}&include_user=1`;
  try {
    const res = await fetch(url, {
      method: 'GET',
      credentials: 'include',
      headers: { 'X-Requested-With': 'XMLHttpRequest' },
    });
    const contentType = res.headers.get('content-type') || '';
    if (!contentType.includes('application/json')) return { error: 'Нужно войти в HR Helper (сессия) для слотов.' };
    const json = await res.json().catch(() => ({}));
    if (!res.ok || !json?.success) return { error: json?.message || 'Не удалось получить слоты.' };
    return { slots: json.slots || [] };
  } catch (_) {
    return { error: 'Ошибка сети при получении слотов.' };
  }
}

async function fetchThirdWeekSlotsViaSession(vacancyId) {
  const { baseUrl } = await getApiConfig();
  if (!baseUrl) return null;
  const url = `${baseUrl}/google-oauth/api/third-week-slots/?vacancy_id=${encodeURIComponent(String(vacancyId || ''))}&meeting_type=screening`;
  try {
    const res = await fetch(url, {
      method: 'GET',
      credentials: 'include',
      headers: { 'X-Requested-With': 'XMLHttpRequest' },
    });
    const contentType = res.headers.get('content-type') || '';
    if (!contentType.includes('application/json')) return { error: 'Нужно войти в HR Helper (сессия) для 3-й недели.' };
    const json = await res.json().catch(() => ({}));
    if (!res.ok || !json?.success) return { error: json?.message || 'Не удалось получить 3-ю неделю.' };
    return { slots: json.slots || [] };
  } catch (_) {
    return { error: 'Ошибка сети при получении 3-й недели.' };
  }
}

function getSelectedCandidateVacancyExternalId() {
  const vids = (linkedinState.vacancies || []).map((v) => v.vacancy_id).filter((x) => x != null);
  if (vids.length === 0) return null;
  const sel = linkedinState.selectedVacancyId ?? linkedinState.defaultVacancyId ?? vids[0];
  if (sel == null) return null;
  // Важно: это Huntflow vacancy_id, который используем как external_id в HR Helper Vacancy.
  return String(sel);
}

function getSelectedHrhelperVacancyId() {
  return copyButtonsState.vacancy?.id || null;
}

function updateCopyButtonsDisabledState() {
  const v = copyButtonsState.vacancy;
  const hasVacancy = !!v?.id;
  const qBY = (v?.questions_belarus || '').trim();
  const qPL = (v?.questions_poland || '').trim();
  const lBY = (v?.vacancy_link_belarus || '').trim();
  const lPL = (v?.vacancy_link_poland || '').trim();

  const btn = (id) => document.getElementById(id);
  if (btn('btn-copy-vacancy-link-belarus')) btn('btn-copy-vacancy-link-belarus').disabled = !(hasVacancy && lBY);
  if (btn('btn-copy-vacancy-link-poland')) btn('btn-copy-vacancy-link-poland').disabled = !(hasVacancy && lPL);
  if (btn('btn-copy-questions-belarus')) btn('btn-copy-questions-belarus').disabled = !(hasVacancy && qBY);
  if (btn('btn-copy-questions-poland')) btn('btn-copy-questions-poland').disabled = !(hasVacancy && qPL);

  // Слоты требуют vacancy.id + активную сессию на сайте.
  const slotsBtnsDisabled = !hasVacancy;
  if (btn('btn-copy-current-week')) btn('btn-copy-current-week').disabled = slotsBtnsDisabled;
  if (btn('btn-copy-next-week')) btn('btn-copy-next-week').disabled = slotsBtnsDisabled;
  if (btn('btn-add-third-week')) btn('btn-add-third-week').disabled = slotsBtnsDisabled;
  if (btn('btn-copy-all-slots')) btn('btn-copy-all-slots').disabled = slotsBtnsDisabled;
}

async function syncCopyButtonsForSelectedVacancy() {
  const ext = getSelectedCandidateVacancyExternalId();
  if (!ext || ext === '0') {
    copyButtonsState.externalId = null;
    copyButtonsState.vacancy = null;
    copyButtonsState.slotsCache = null;
    copyButtonsState.thirdWeekSlots = null;
    setCopyButtonsVisible(false);
    updateCopyButtonsDisabledState();
    return;
  }

  // Не делаем лишние запросы
  if (copyButtonsState.externalId === ext && copyButtonsState.vacancy) {
    setCopyButtonsVisible(true);
    updateCopyButtonsDisabledState();
    return;
  }

  copyButtonsState.externalId = ext;
  copyButtonsState.vacancy = null;
  copyButtonsState.slotsCache = null;
  copyButtonsState.thirdWeekSlots = null;
  setCopyButtonsVisible(false);

  const vacancy = await fetchVacancyByExternalId(ext);
  copyButtonsState.vacancy = vacancy;
  if (!copyButtonsState.slotsSettings) {
    copyButtonsState.slotsSettings = await fetchSlotsSettings();
  }
  const selectedFromList = (linkedinState.vacancies || []).find((v) => String(v.vacancy_id) === String(ext));
  const isActiveVacancy = selectedFromList && selectedFromList.status_type !== 'rejected';
  setCopyButtonsVisible(!!vacancy || !!isActiveVacancy);
  updateCopyButtonsDisabledState();
}

function formatSlotsText(weekType, groups, settings, includeThirdWeek) {
  const s = settings || { currentWeekPrefix: '', nextWeekPrefix: '', allSlotsPrefix: '', separatorText: '---' };
  const nonEmpty = (arr) => (arr || []).filter((x) => x && x.availableSlots && x.availableSlots !== 'Нет свободных слотов');
  const current = nonEmpty(groups?.current);
  const next = nonEmpty(groups?.next);
  const third = includeThirdWeek ? nonEmpty(copyButtonsState.thirdWeekSlots || []) : [];

  const lineCurrent = (slot) => `${slot.weekday} ${slot.availableSlots}`;
  const lineNext = (slot) => `${slot.weekday} (${slot.dateStr}) ${slot.availableSlots}`;

  if (weekType === 'current') {
    const lines = [];
    if (s.currentWeekPrefix) lines.push(s.currentWeekPrefix);
    current.forEach((slot) => lines.push(lineCurrent(slot)));
    return lines.join('\n').trim();
  }
  if (weekType === 'next') {
    const lines = [];
    if (s.nextWeekPrefix) lines.push(s.nextWeekPrefix);
    next.forEach((slot) => lines.push(lineNext(slot)));
    return lines.join('\n').trim();
  }

  // all
  const lines = [];
  if (s.allSlotsPrefix) lines.push(s.allSlotsPrefix);
  current.forEach((slot) => lines.push(lineCurrent(slot)));
  if (next.length > 0) {
    lines.push('');
    lines.push(s.separatorText || '---');
    next.forEach((slot) => lines.push(lineNext(slot)));
  }
  if (third.length > 0) {
    lines.push('');
    lines.push(s.separatorText || '---');
    third.forEach((slot) => lines.push(lineNext(slot)));
  }
  return lines.join('\n').trim();
}

async function ensureSlotsLoaded() {
  const vacancyId = getSelectedHrhelperVacancyId();
  if (!vacancyId) return { error: 'Вакансия не определена.' };
  if (copyButtonsState.slotsCache) return { ok: true };

  const res = await fetchInterviewSlotsViaSession(vacancyId);
  if (res?.error) return { error: res.error };
  const slots = Array.isArray(res?.slots) ? res.slots : [];
  const groups = groupSlotsByWeek(slots);
  copyButtonsState.slotsCache = groups;
  return { ok: true };
}

async function handleCopySlots(weekType, btnEl) {
  const settings = copyButtonsState.slotsSettings || (await fetchSlotsSettings()) || null;
  if (!copyButtonsState.slotsSettings) copyButtonsState.slotsSettings = settings;
  const loaded = await ensureSlotsLoaded();
  if (loaded?.error) return { error: loaded.error };
  const text = formatSlotsText(weekType, copyButtonsState.slotsCache, settings, weekType === 'all');
  if (!text) return { error: 'Нет доступных слотов для копирования.' };
  const ok = await copyToClipboard(text);
  if (ok) flashCopySuccess(btnEl);
  return ok ? { ok: true } : { error: 'Не удалось скопировать в буфер обмена.' };
}

async function handleAddThirdWeek(btnEl) {
  const vacancyId = getSelectedHrhelperVacancyId();
  if (!vacancyId) return { error: 'Вакансия не определена.' };
  const res = await fetchThirdWeekSlotsViaSession(vacancyId);
  if (res?.error) return { error: res.error };
  copyButtonsState.thirdWeekSlots = Array.isArray(res?.slots) ? res.slots : [];
  flashCopySuccess(btnEl);
  return { ok: true };
}

/** Форматирование даты для карточки вакансии: число.месяц.год */
const formatVacancyDate = HRH.formatVacancyDate;

/** Форматирование даты/времени отказа: число.месяц.год ЧЧ:ММ */
const formatRejectionDateTime = HRH.formatRejectionDateTime;

if (!formatVacancyDate || !formatRejectionDateTime) {
  throw new Error("[HRHelper] shared/utils/date.js not loaded (formatVacancyDate/formatRejectionDateTime missing)");
}

/** Рендер UI для кандидата с несколькими вакансиями */
function renderMultiVacancyUI() {
  const formRowEl = formRow();
  const statusBlockEl = statusBlock();
  const titleEl = document.getElementById('ctx-linkedin-title');
  const fioEl = document.getElementById('ctx-linkedin-fio');
  const candidateBlockEl = document.getElementById('ctx-linkedin-candidate-block');
  const vacanciesContainer = document.getElementById('ctx-linkedin-vacancies-list') || createVacanciesListContainer();
  const headerActions = document.getElementById('header-actions');
  const headerHuntflowBtn = document.getElementById('headerHuntflowBtn');
  const headerAddVacancyBtn = document.getElementById('headerAddVacancyBtn');

  if (formRowEl) formRowEl.style.display = 'none';

  const { active, rejected, hired, archived } = categorizeVacancies(linkedinState.vacancies || []);
  const hasRealVacancy = (linkedinState.vacancies || []).some((v) => v.vacancy_id != null && v.vacancy_id !== 0);
  if (hasRealVacancy) setCopyButtonsVisible(true);
  const isHuntflowContext = currentContext === CONTEXT.HUNTFLOW;
  const allRejected = active.length === 0 && rejected.length > 0;
  if (statusBlockEl) {
    statusBlockEl.style.display = 'block';
    statusBlockEl.classList.add('has-vacancies');
    const statusFormEl = document.getElementById('ctx-linkedin-status-form');
    if (statusFormEl) statusFormEl.style.display = (allRejected || isHuntflowContext) ? 'none' : 'block';
  }
  const hasActiveOrRejected = active.length > 0 || rejected.length > 0;

  if (headerActions && headerHuntflowBtn && headerAddVacancyBtn) {
    if (isHuntflowContext) {
      updateHeaderActions(false);
      headerAddVacancyBtn.style.display = 'none';
    } else if (hasActiveOrRejected) {
      const selId = linkedinState.selectedVacancyId ?? linkedinState.defaultVacancyId;
      const selVacancy = (linkedinState.vacancies || []).find((v) => v.vacancy_id === selId);
      const huntflowUrl = selVacancy ? selVacancy.appurl : (linkedinState.huntflowUrl || '#');
      const selVacRejected = selVacancy && selVacancy.status_type === 'rejected';
      updateHeaderActions(true, huntflowUrl, true, selVacRejected);
      headerAddVacancyBtn.onclick = toggleAddVacancyPanel;
      headerAddVacancyBtn.textContent = addVacancyPanelOpen ? '−' : '+';
      headerAddVacancyBtn.classList.toggle('expanded', addVacancyPanelOpen);
    } else {
      updateHeaderActions(false);
      addVacancyPanelOpen = false;
      const panel = document.getElementById('add-vacancy-panel');
      if (panel) panel.classList.remove('visible');
    }
  }

  if (linkedinState.selectedVacancyId == null) {
    linkedinState.selectedVacancyId = linkedinState.defaultVacancyId ?? (active[0]?.vacancy_id) ?? (rejected[0]?.vacancy_id);
  }

  const selId = linkedinState.selectedVacancyId;
  const selVac = (active.concat(rejected)).find((v) => v.vacancy_id === selId);
  if (selVac) {
    loadLinkedInStatusOptions().then(() => {
      const sel = document.getElementById('ctx-linkedin-status');
      if (sel && selVac.status_id) {
        sel.value = String(selVac.status_id);
        updateHuntflowButtonRejectionClass();
      }
    });
  }

  if (titleEl) {
    titleEl.textContent = linkedinState.candidateInfo?.full_name || 'Кандидат';
    titleEl.style.display = 'block';
  }
  if (fioEl) {
    if (currentContext === CONTEXT.RESUME && linkedinState.candidateInfo?.full_name) fioEl.style.display = 'none';
    else if (linkedinState.candidateInfo?.full_name) {
      fioEl.textContent = linkedinState.candidateInfo.full_name;
      fioEl.style.display = 'block';
    } else fioEl.style.display = 'none';
  }

  if (candidateBlockEl && linkedinState.candidateInfo) {
    const info = linkedinState.candidateInfo;
    const bodyEl = document.getElementById('ctx-linkedin-candidate-body');
    const toggleEl = document.getElementById('ctx-linkedin-candidate-toggle');
    const comm = info.communication;
    const isCommTelegram = comm && /t\.me|telegram/i.test(String(comm));
    const rows = [
      ['Телефон', info.phone],
      ['Email', info.email],
      ['Telegram', info.telegram],
      ['Где ведётся коммуникация', !isCommTelegram ? comm : null],
      ['Готовность к офису', info.office_readiness],
      ['Уровень', info.level],
    ].filter(([, v]) => v != null && v !== '');
    if (rows.length > 0 && bodyEl && toggleEl) {
      candidateBlockEl.style.display = 'block';
      bodyEl.innerHTML = rows.map(([label, value]) =>
        '<div class="ctx-candidate-row"><span class="ctx-candidate-label">' + escapeHtml(label) + ':</span> ' + escapeHtml(String(value)) + '</div>'
      ).join('');
      bodyEl.hidden = true;
      toggleEl.setAttribute('aria-expanded', 'false');
    } else candidateBlockEl.style.display = 'none';
  } else if (candidateBlockEl) candidateBlockEl.style.display = 'none';

  vacanciesContainer.innerHTML = '';

  if (hired.length > 0) {
    if (headerActions) headerActions.style.display = 'none';
    if (currentContext === CONTEXT.RESUME && headerActions) {
      headerActions.style.display = 'flex';
      const headerResumeFloatingBtn = document.getElementById('headerResumeFloatingBtn');
      if (headerResumeFloatingBtn) headerResumeFloatingBtn.style.display = 'inline-flex';
      if (headerHuntflowBtn) headerHuntflowBtn.style.display = 'none';
      if (headerAddVacancyBtn) headerAddVacancyBtn.style.display = 'none';
    }
    setCopyButtonsVisible(false);
    updateCopyButtonsDisabledState();
    const badge = document.createElement('div');
    badge.className = 'ctx-employee-badge';
    badge.innerHTML = '✅ Сотрудник<br><span style="font-size:12px;font-weight:400;">Вакансия: ' + escapeHtml(hired[0].vacancy_name) + '</span>';
    vacanciesContainer.appendChild(badge);
    const hint = document.createElement('p');
    hint.className = 'ctx-desc';
    hint.style.cssText = 'margin-top:8px;color:#6c757d;font-size:12px;';
    hint.textContent = 'Нанятые кандидаты не могут быть добавлены на другие вакансии.';
    vacanciesContainer.appendChild(hint);
    return;
  }

  if (isHuntflowContext) {
    const allForCopy = [...active, ...rejected, ...archived];
    if (allForCopy.length > 0) {
      const h4 = document.createElement('h4');
      h4.style.cssText = 'margin:0 0 8px 0;font-size:13px;font-weight:600;color:#084298;';
      h4.textContent = '📋 Вакансии';
      vacanciesContainer.appendChild(h4);
      allForCopy.forEach((v) => vacanciesContainer.appendChild(createVacancyCard(v, v.is_archived ? 'archived' : v.status_type === 'rejected' ? 'rejected' : 'active', true)));
    } else {
      const hint = document.createElement('p');
      hint.className = 'ctx-desc';
      hint.style.cssText = 'margin-top:8px;color:#6c757d;font-size:12px;';
      hint.textContent = 'Нет вакансий для отображения.';
      vacanciesContainer.appendChild(hint);
    }
  } else if (active.length > 0) {
    const h4 = document.createElement('h4');
    h4.style.cssText = 'margin:0 0 8px 0;font-size:13px;font-weight:600;color:#084298;';
    h4.textContent = '📌 Активные вакансии';
    vacanciesContainer.appendChild(h4);
    active.forEach((v) => vacanciesContainer.appendChild(createVacancyCard(v, 'active')));
  }
  if (!isHuntflowContext && rejected.length > 0) {
    const rejectedWrap = document.createElement('div');
    rejectedWrap.className = 'ctx-rejected-wrap';
    const title = (active.length === 0 ? '🗂️ История отказов' : '❌ Отказы') + (rejected.length > 1 ? ` (${rejected.length})` : '');
    if (rejected.length > 1) {
      const toggleBtn = document.createElement('button');
      toggleBtn.type = 'button';
      toggleBtn.className = 'ctx-rejected-toggle';
      toggleBtn.style.cssText = 'background:none;border:none;padding:0;cursor:pointer;text-align:left;width:100%;font:inherit;color:inherit;display:flex;align-items:center;gap:6px;margin:16px 0 8px 0;font-size:13px;font-weight:600;color:#842029;';
      toggleBtn.innerHTML = '▶ ' + title;
      const cardsWrap = document.createElement('div');
      cardsWrap.className = 'ctx-rejected-cards';
      cardsWrap.style.display = 'none';
      rejected.forEach((v) => cardsWrap.appendChild(createVacancyCard(v, 'rejected', false)));
      toggleBtn.addEventListener('click', () => {
        const open = cardsWrap.style.display !== 'none';
        cardsWrap.style.display = open ? 'none' : 'block';
        toggleBtn.innerHTML = (open ? '▶ ' : '▼ ') + title;
      });
      rejectedWrap.appendChild(toggleBtn);
      rejectedWrap.appendChild(cardsWrap);
      vacanciesContainer.appendChild(rejectedWrap);
    } else {
      const h4 = document.createElement('h4');
      h4.style.cssText = 'margin:16px 0 8px 0;font-size:13px;font-weight:600;color:#842029;';
      h4.textContent = title;
      vacanciesContainer.appendChild(h4);
      rejected.forEach((v) => vacanciesContainer.appendChild(createVacancyCard(v, 'rejected', false)));
    }
  }
  if (!isHuntflowContext && archived.length > 0) {
    const h4 = document.createElement('h4');
    h4.style.cssText = 'margin:16px 0 8px 0;font-size:13px;font-weight:600;color:#6c757d;';
    h4.textContent = '📁 Архивные вакансии';
    vacanciesContainer.appendChild(h4);
    archived.forEach((v) => vacanciesContainer.appendChild(createVacancyCard(v, 'archived', false)));
  }

  // Обновляем блок круглых кнопок под выбранную вакансию
  syncCopyButtonsForSelectedVacancy().catch(() => {});
}

function createVacanciesListContainer() {
  const c = document.createElement('div');
  c.id = 'ctx-linkedin-vacancies-list';
  const statusBlockEl = document.getElementById('ctx-linkedin-status-block');
  if (statusBlockEl) statusBlockEl.insertBefore(c, statusBlockEl.firstChild);
  return c;
}

const RESTART_ICON_SVG = '<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M17.65 6.35C16.2 4.9 14.21 4 12 4c-4.42 0-7.99 3.58-7.99 8s3.57 8 7.99 8c3.73 0 6.84-2.55 7.73-6h-2.08c-.82 2.33-3.04 4-5.65 4-3.31 0-6-2.69-6-6s2.69-6 6-6c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35z"/></svg>';
const COPY_LINK_ICON_SVG = '<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M16 1H4c-1.1 0-2 .9-2 2v14h2V3h12V1zm3 4H8c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h11c1.1 0 2-.9 2-2V7c0-1.1-.9-2-2-2zm0 16H8V7h11v14z"/></svg>';

function createVacancyCard(vacancy, type, showCopyBtn) {
  showCopyBtn = !!showCopyBtn;
  const card = document.createElement('div');
  const isArchived = type === 'archived';
  const isRejected = type === 'rejected';
  card.className = 'ctx-vacancy-card' + (isRejected ? ' ctx-vacancy-card-rejected' : '') + (isArchived ? ' ctx-vacancy-card-archived' : '');
  card.dataset.vacancyId = vacancy.vacancy_id;
  const isSelected = linkedinState.selectedVacancyId === vacancy.vacancy_id;
  card.style.cssText = 'padding:12px;margin-bottom:8px;border-radius:8px;';
  if (type === 'active' && !showCopyBtn) {
    card.classList.add('selectable');
    if (isSelected) card.classList.add('selected');
    card.addEventListener('click', () => {
      linkedinState.selectedVacancyId = vacancy.vacancy_id;
      loadLinkedInStatusOptions().then(() => {
        const sel = document.getElementById('ctx-linkedin-status');
        if (sel && vacancy.status_id) {
          sel.value = String(vacancy.status_id);
          updateHuntflowButtonRejectionClass();
        }
      });
      const headerHuntflowBtn = document.getElementById('headerHuntflowBtn');
      if (headerHuntflowBtn) headerHuntflowBtn.href = vacancy.appurl;
      renderMultiVacancyUI();
    });
  }
  if (isRejected) {
    const content = document.createElement('div');
    content.className = 'ctx-rejected-content';
    const nameEl = document.createElement('div');
    nameEl.className = 'ctx-rejected-name';
    const dateTimeStr = formatRejectionDateTime(vacancy.last_change_at);
    nameEl.textContent = (vacancy.vacancy_name || '—') + (dateTimeStr ? ' (' + dateTimeStr + ')' : '');
    const statusLine = document.createElement('div');
    statusLine.className = 'ctx-rejected-status';
    statusLine.textContent = vacancy.status_name ? 'Статус: ' + vacancy.status_name : '';
    const reasonEl = document.createElement('div');
    reasonEl.className = 'ctx-rejected-reason';
    reasonEl.textContent = vacancy.rejection_reason_name || '—';
    content.appendChild(nameEl);
    if (vacancy.status_name) content.appendChild(statusLine);
    content.appendChild(reasonEl);
    card.appendChild(content);
    if (showCopyBtn) {
      const copyBtn = document.createElement('button');
      copyBtn.type = 'button';
      copyBtn.className = 'ctx-vacancy-copy-btn';
      copyBtn.title = 'Копировать ссылку Huntflow';
      copyBtn.setAttribute('aria-label', 'Копировать ссылку Huntflow');
      copyBtn.innerHTML = COPY_LINK_ICON_SVG;
      copyBtn.addEventListener('click', (e) => { e.stopPropagation(); copyVacancyUrlToClipboard(vacancy.appurl, copyBtn); });
      card.appendChild(copyBtn);
    } else {
      const restartBtn = document.createElement('button');
      restartBtn.type = 'button';
      restartBtn.className = 'ctx-rejected-restart-btn';
      restartBtn.title = 'В новый цикл';
      restartBtn.setAttribute('aria-label', 'В новый цикл');
      restartBtn.innerHTML = RESTART_ICON_SVG;
      restartBtn.addEventListener('click', (e) => { e.stopPropagation(); restartVacancyCycle(vacancy); });
      card.appendChild(restartBtn);
    }
  } else if (isArchived) {
    const content = document.createElement('div');
    content.className = 'ctx-rejected-content';
    const nameEl = document.createElement('div');
    nameEl.className = 'ctx-rejected-name';
    nameEl.textContent = (vacancy.vacancy_name || '—') + (vacancy.status_name ? ' (' + vacancy.status_name + ')' : '');
    content.appendChild(nameEl);
    card.appendChild(content);
    const copyBtn = document.createElement('button');
    copyBtn.type = 'button';
    copyBtn.className = 'ctx-vacancy-copy-btn';
    copyBtn.title = 'Копировать ссылку Huntflow';
    copyBtn.setAttribute('aria-label', 'Копировать ссылку Huntflow');
    copyBtn.innerHTML = COPY_LINK_ICON_SVG;
    copyBtn.addEventListener('click', (e) => { e.stopPropagation(); copyVacancyUrlToClipboard(vacancy.appurl, copyBtn); });
    card.appendChild(copyBtn);
  } else {
    const row = document.createElement('div');
    row.className = 'ctx-vacancy-card-row';
    const nameEl = document.createElement('div');
    nameEl.className = 'ctx-vacancy-card-name';
    const namePart = (isSelected ? '✓ ' : '') + vacancy.vacancy_name;
    nameEl.textContent = vacancy.status_name ? namePart + ' (' + vacancy.status_name + ')' : namePart;
    const dateEl = document.createElement('div');
    dateEl.className = 'ctx-vacancy-card-date';
    dateEl.textContent = formatVacancyDate(vacancy.last_change_at);
    row.appendChild(nameEl);
    row.appendChild(dateEl);
    card.appendChild(row);
    if (showCopyBtn) {
      const copyBtn = document.createElement('button');
      copyBtn.type = 'button';
      copyBtn.className = 'ctx-vacancy-copy-btn ctx-vacancy-copy-btn-inline';
      copyBtn.title = 'Копировать ссылку Huntflow';
      copyBtn.setAttribute('aria-label', 'Копировать ссылку Huntflow');
      copyBtn.innerHTML = COPY_LINK_ICON_SVG;
      copyBtn.addEventListener('click', (e) => { e.stopPropagation(); copyVacancyUrlToClipboard(vacancy.appurl, copyBtn); });
      card.appendChild(copyBtn);
    }
  }
  return card;
}

function copyVacancyUrlToClipboard(url, btnEl) {
  const u = url || '';
  if (!u) return;
  navigator.clipboard.writeText(u).then(() => {
    if (btnEl) {
      const oldTitle = btnEl.title;
      btnEl.title = 'Скопировано';
      btnEl.classList.add('copied');
      setTimeout(() => { btnEl.title = oldTitle; btnEl.classList.remove('copied'); }, 1500);
    }
  }).catch(() => {});
}

async function restartVacancyCycle(vacancy) {
  const statusEl = document.getElementById('status');
  const hasProfile = !!linkedinState.profileUrl;
  const hasHuntflow = !!linkedinState.huntflowUrl;
  if (!hasProfile && !hasHuntflow) {
    if (statusEl) { statusEl.textContent = 'Нет данных кандидата (LinkedIn или Huntflow)'; statusEl.className = 'status err'; }
    return;
  }
  if (statusEl) { statusEl.textContent = 'Возобновление цикла…'; statusEl.className = 'status'; }
  try {
    const { baseUrl, apiToken } = await getApiConfig();
    const newStatusId = await getNewStatusId(baseUrl, apiToken, linkedinState.profileUrl, linkedinState.huntflowUrl);
    if (!newStatusId) throw new Error('Не удалось определить статус «New»');
    const body = {
      status_id: newStatusId,
      vacancy_id: vacancy.vacancy_id,
      rejection_reason_id: null,
      comment: '<p>Цикл возобновлён через HR Helper</p>',
    };
    if (hasProfile) body.linkedin_url = linkedinState.profileUrl;
    else body.huntflow_url = linkedinState.huntflowUrl;
    const res = await apiFetch('/api/v1/huntflow/linkedin-applicants/update-status/', {
      method: 'POST',
      body: body,
    });
    const data = await res.json().catch(() => ({}));
    if (res.ok && data.success) {
      if (statusEl) { statusEl.textContent = '✅ Цикл возобновлён'; statusEl.className = 'status ok'; setTimeout(() => { statusEl.textContent = ''; statusEl.className = 'status'; }, 2000); }
      await refreshLinkedInState();
      renderLinkedInUI();
    } else throw new Error(data?.message || 'Ошибка при обновлении статуса');
  } catch (e) {
    if (statusEl) { statusEl.textContent = e.message; statusEl.className = 'status err'; }
  }
}

async function getNewStatusId(baseUrl, apiToken, linkedinUrl, huntflowUrl) {
  try {
    const q = new URLSearchParams();
    if (linkedinUrl) q.set('linkedin_url', linkedinUrl);
    else if (huntflowUrl) q.set('huntflow_url', huntflowUrl);
    else return null;
    const res = await apiFetch('/api/v1/huntflow/linkedin-applicants/status-options/?' + q.toString(), { method: 'GET' });
    const data = await res.json().catch(() => ({}));
    if (data.success && data.statuses) {
      const s = data.statuses.find((x) => (x.type === 'new' || (x.name || '').toLowerCase() === 'new' || (x.name || '').toLowerCase() === 'новый'));
      return s ? s.id : (data.statuses[0] ? data.statuses[0].id : null);
    }
    return null;
  } catch (_) { return null; }
}

async function toggleAddVacancyPanel() {
  addVacancyPanelOpen = !addVacancyPanelOpen;
  const panel = document.getElementById('add-vacancy-panel');
  const btn = document.getElementById('headerAddVacancyBtn');
  if (!panel || !btn) return;
  if (addVacancyPanelOpen) {
    panel.classList.add('visible');
    btn.textContent = '−';
    btn.classList.add('expanded');
    await loadAddVacancyPanel();
  } else {
    panel.classList.remove('visible');
    btn.textContent = '+';
    btn.classList.remove('expanded');
  }
}

async function loadAddVacancyPanel() {
  const listEl = document.getElementById('add-vacancy-list');
  if (!listEl) return;
  listEl.innerHTML = '<div style="padding:8px;color:#6c757d;font-size:12px;">Загрузка…</div>';
  try {
    const q = new URLSearchParams();
    if (linkedinState.profileUrl) q.set('linkedin_url', linkedinState.profileUrl);
    else if (linkedinState.huntflowUrl) q.set('huntflow_url', linkedinState.huntflowUrl);
    else {
      listEl.innerHTML = '<div style="padding:8px;color:#842029;font-size:12px;">Нет данных кандидата</div>';
      return;
    }
    const res = await apiFetch('/api/v1/huntflow/linkedin-applicants/available-vacancies/?' + q.toString(), { method: 'GET' });
    const data = await res.json().catch(() => ({}));
    if (!res.ok || !data.success) {
      listEl.innerHTML = '<div style="padding:8px;color:#842029;font-size:12px;">' + escapeHtml(data?.message || 'Ошибка загрузки') + '</div>';
      return;
    }
    const items = data.items || [];
    if (items.length === 0) {
      listEl.innerHTML = '<div style="padding:8px;color:#6c757d;font-size:12px;">Нет доступных вакансий</div>';
      return;
    }
    listEl.innerHTML = '';
    items.forEach((v) => {
      const el = document.createElement('div');
      el.className = 'add-vacancy-item';
      el.textContent = v.vacancy_name;
      el.addEventListener('click', async () => {
        await addToVacancy(v.vacancy_id);
        addVacancyPanelOpen = false;
        const panel = document.getElementById('add-vacancy-panel');
        const btn = document.getElementById('headerAddVacancyBtn');
        if (panel) panel.classList.remove('visible');
        if (btn) { btn.textContent = '+'; btn.classList.remove('expanded'); }
        renderLinkedInUI();
      });
      listEl.appendChild(el);
    });
  } catch (e) {
    listEl.innerHTML = '<div style="padding:8px;color:#842029;font-size:12px;">' + escapeHtml(e.message) + '</div>';
  }
}

async function showAddToVacancyModal() {
  const statusEl = document.getElementById('status');
  if (statusEl) { statusEl.textContent = 'Загрузка доступных вакансий…'; statusEl.className = 'status'; }
  try {
    const q = new URLSearchParams({ linkedin_url: linkedinState.profileUrl });
    const res = await apiFetch('/api/v1/huntflow/linkedin-applicants/available-vacancies/?' + q.toString(), { method: 'GET' });
    const data = await res.json().catch(() => ({}));
    if (statusEl) statusEl.textContent = '';
    if (!res.ok || !data.success) throw new Error(data?.message || 'Ошибка загрузки вакансий');
    if (!data.items || data.items.length === 0) {
      alert('Нет доступных вакансий для добавления');
      return;
    }
    const list = data.items.map((v) => v.vacancy_id + ': ' + v.vacancy_name).join('\n');
    const selected = prompt('Доступные вакансии:\n' + list + '\n\nВведите ID вакансии:');
    if (!selected) return;
    const vid = parseInt(selected.trim(), 10);
    const v = data.items.find((x) => x.vacancy_id === vid);
    if (!v) { alert('Неверный ID вакансии'); return; }
    await addToVacancy(vid);
  } catch (e) {
    if (statusEl) { statusEl.textContent = e.message; statusEl.className = 'status err'; }
  }
}

async function addToVacancy(vacancyId) {
  const statusEl = document.getElementById('status');
  if (statusEl) { statusEl.textContent = 'Добавление на вакансию…'; statusEl.className = 'status'; }
  try {
    const body = { vacancy_id: vacancyId };
    if (linkedinState.profileUrl) body.linkedin_url = linkedinState.profileUrl;
    else if (linkedinState.huntflowUrl) body.huntflow_url = linkedinState.huntflowUrl;
    const res = await apiFetch('/api/v1/huntflow/linkedin-applicants/add-to-vacancy/', {
      method: 'POST',
      body: body,
    });
    const data = await res.json().catch(() => ({}));
    if (res.ok && data.success) {
      if (statusEl) { statusEl.textContent = '✅ Кандидат добавлен на вакансию'; statusEl.className = 'status ok'; setTimeout(() => { statusEl.textContent = ''; statusEl.className = 'status'; }, 2000); }
      await refreshLinkedInState();
    } else throw new Error(data?.message || 'Ошибка добавления');
  } catch (e) {
    if (statusEl) { statusEl.textContent = e.message; statusEl.className = 'status err'; }
  }
}

async function refreshLinkedInState() {
  const url = linkedinState.profileUrl || linkedinState.huntflowUrl;
  if (!url) return;
  const result = await fetchStatusMulti(linkedinState.profileUrl || null, linkedinState.huntflowUrl || null);
  if (result.error) return;
  Object.assign(linkedinState, result);
}

/** Показывает контекстный блок и запрашивает данные у content script */
async function showContextForTab() {
  const blocks = document.querySelectorAll('.context-block');
  blocks.forEach((el) => el.classList.remove('visible'));

  // Кнопки Meet: сброс в неактивное состояние, пока не получим данные
  const meetScorecard = document.getElementById('ctx-meet-scorecard');
  const meetContact = document.getElementById('ctx-meet-contact');
  const meetCopy = document.getElementById('ctx-meet-copy');
  const meetHuntflow = document.getElementById('ctx-meet-huntflow');
  const meetSettingsLink = document.getElementById('ctx-meet-settings-link');
  const meetHint = document.getElementById('ctx-meet-hint');
  const meetOpenAll = document.getElementById('ctx-meet-open-all');
  const headerMeetReminderBtn = document.getElementById('headerMeetReminderBtn');
  const headerLinkedInFloatingBtn = document.getElementById('headerLinkedInFloatingBtn');
  const headerResumeFloatingBtn = document.getElementById('headerResumeFloatingBtn');
  const headerHuntflowFloatingBtn = document.getElementById('headerHuntflowFloatingBtn');
  if (headerMeetReminderBtn) headerMeetReminderBtn.style.display = 'none';
  if (headerLinkedInFloatingBtn) headerLinkedInFloatingBtn.style.display = 'none';
  if (headerResumeFloatingBtn) headerResumeFloatingBtn.style.display = 'none';
  if (headerHuntflowFloatingBtn) headerHuntflowFloatingBtn.style.display = 'none';
  if (meetHuntflow) {
    meetHuntflow.style.display = 'none';
    meetHuntflow.href = '#';
    meetHuntflow.setAttribute('aria-disabled', 'true');
  }
  if (meetScorecard) {
    meetScorecard.style.display = 'inline-flex';
    meetScorecard.href = '#';
    meetScorecard.setAttribute('aria-disabled', 'true');
  }
  if (meetContact) {
    meetContact.style.display = 'inline-flex';
    meetContact.href = '#';
    meetContact.setAttribute('aria-disabled', 'true');
  }
  if (meetCopy) {
    meetCopy.style.display = 'inline-flex';
    meetCopy.disabled = true;
    meetCopy.textContent = 'Вакансия и грейд';
  }
  if (meetSettingsLink) meetSettingsLink.style.display = 'none';
  if (meetHint) meetHint.style.display = 'none';

  let tab;
  try {
    [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  } catch (_) {}
  currentTabId = tab?.id ?? null;

  const url = tab?.url || '';
  let ctx = getContextFromUrl(url);
  const pageKey = getActivePageKeyFromContext(ctx);

  // Batch: sync (active pages) + local (floating hidden) — один раз вместо отдельных вызовов в ветках
  let syncData = { [ACTIVE_PAGES_KEY]: DEFAULT_ACTIVE_PAGES };
  let floatingData = {};
  try {
    [syncData, floatingData] = await Promise.all([
      chrome.storage.sync.get({ [ACTIVE_PAGES_KEY]: DEFAULT_ACTIVE_PAGES }),
      getFloatingHiddenStates()
    ]);
  } catch (_) {}

  if (pageKey) {
    const active = syncData[ACTIVE_PAGES_KEY] || DEFAULT_ACTIVE_PAGES;
    if (!active[pageKey]) ctx = CONTEXT.OTHER;
  }
  currentContext = ctx;
  if (popupState && popupState.setState) popupState.setState({ currentContext: ctx });
  if (eventBus && eventBus.emit) eventBus.emit('popup:contextChanged', { context: ctx });

  if (ctx === CONTEXT.CALENDAR) {
    updateHeaderActions(false);
  }

  if (ctx === CONTEXT.LINKEDIN) {
    const headerActions = document.getElementById('header-actions');
    if (headerActions) headerActions.style.display = 'flex';
    if (headerLinkedInFloatingBtn) headerLinkedInFloatingBtn.style.display = 'inline-flex';
    updateLinkedInFloatingToggle(floatingData);
  }
  if (ctx === CONTEXT.RESUME) {
    const headerActions = document.getElementById('header-actions');
    if (headerActions) headerActions.style.display = 'flex';
    if (headerResumeFloatingBtn) headerResumeFloatingBtn.style.display = 'inline-flex';
    updateResumeFloatingToggle(floatingData);
  }
  if (ctx === CONTEXT.HUNTFLOW) {
    const headerActions = document.getElementById('header-actions');
    if (headerActions) headerActions.style.display = 'flex';
    if (headerHuntflowFloatingBtn) headerHuntflowFloatingBtn.style.display = 'inline-flex';
    updateHuntflowFloatingToggle(floatingData);
  }

  if (ctx === CONTEXT.GDRIVE) {
    const gdriveBlock = document.getElementById('context-gdrive');
    if (gdriveBlock) {
      gdriveBlock.style.display = 'block';
      gdriveBlock.classList.add('visible');
    }
    await initGDriveSection();
    return;
  }

  // Для страниц резюме (rabota.by, hh.ru) и Huntflow показываем тот же блок, что и для LinkedIn; для неизвестных сайтов (OTHER) — только блок «другая страница», без формы LinkedIn–Huntflow
  const getBlockId = (HRH.tabs && HRH.tabs.getBlockId) ? HRH.tabs.getBlockId : (c) => ((c === CONTEXT.RESUME || c === CONTEXT.HUNTFLOW) ? 'context-linkedin' : `context-${c}`);
  const isLinkedInBlock = (HRH.tabs && HRH.tabs.isLinkedInBlock) ? HRH.tabs.isLinkedInBlock : (c) => (c === CONTEXT.LINKEDIN || c === CONTEXT.RESUME || c === CONTEXT.HUNTFLOW);
  const container = document.getElementById(getBlockId(ctx));
  const showLinkedIn = isLinkedInBlock(ctx);
  if (showLinkedIn) {
    const linkedinBlock = document.getElementById('context-linkedin');
    if (linkedinBlock) linkedinBlock.classList.add('visible');
  }
  if (container) {
    container.classList.add('visible');
    container.style.display = '';
    const dataEl = container.querySelector('.ctx-data');
    if (dataEl && ctx !== CONTEXT.OTHER) dataEl.textContent = url ? `Страница: ${url.replace(/^https?:\/\//, '').split('/')[0]}` : '';
  }

  if (ctx === CONTEXT.HUNTFLOW && tab?.url) {
    linkedinState = { profileUrl: null, huntflowUrl: tab.url, saved: true, candidateInfo: null, vacancies: [], defaultVacancyId: null, selectedVacancyId: null };
    const multiResult = await fetchStatusMulti(null, tab.url);
    if (!multiResult.error) {
      linkedinState.vacancies = multiResult.vacancies || [];
      linkedinState.defaultVacancyId = multiResult.defaultVacancyId ?? null;
      linkedinState.huntflowUrl = multiResult.huntflowUrl || tab.url;
      linkedinState.vacancy_name = multiResult.vacancy_name ?? null;
      linkedinState.status_name = multiResult.status_name ?? null;
      linkedinState.status_id = multiResult.status_id ?? null;
      const info = await fetchCandidateInfo(linkedinState.huntflowUrl);
      if (info) linkedinState.candidateInfo = info;
    }
    renderLinkedInUI();
    return;
  }

  if (ctx === CONTEXT.LINKEDIN || ctx === CONTEXT.RESUME) {
    linkedinState = { profileUrl: null, huntflowUrl: null, saved: false, candidateInfo: null, vacancies: [], defaultVacancyId: null, selectedVacancyId: null };
    if (ctx === CONTEXT.RESUME && tab?.url) {
      let saved = await loadResumeState(tab.url);
      if (!saved) {
        const resumeUrl = getBaseUrl(tab.url);
        if (resumeUrl) {
          try {
            const res = await apiFetch('/api/v1/huntflow/resume-links/?resume_url=' + encodeURIComponent(resumeUrl), { method: 'GET' });
            const data = await res.json().catch(() => ({}));
            if (data?.success && data?.found && data?.huntflow_url) {
              saved = {
                huntflowUrl: data.huntflow_url,
                saved: true,
                vacancy_name: data.vacancy_name || null,
              };
              const info = await fetchCandidateInfo(data.huntflow_url);
              if (info) saved.candidateInfo = info;
              await saveResumeState(tab.url, saved);
            }
          } catch (_) {}
        }
      }
      if (saved) {
        Object.assign(linkedinState, saved);
        if (saved.huntflowUrl) {
          saveResumeLinkToBackend(tab.url, saved).catch(() => {});
          const multiResult = await fetchStatusMulti(null, saved.huntflowUrl);
          if (!multiResult.error) {
            linkedinState.vacancies = multiResult.vacancies || [];
            linkedinState.defaultVacancyId = multiResult.defaultVacancyId ?? null;
            linkedinState.huntflowUrl = multiResult.huntflowUrl || saved.huntflowUrl;
            linkedinState.vacancy_name = multiResult.vacancy_name ?? saved.vacancy_name;
            linkedinState.status_name = multiResult.status_name ?? null;
            linkedinState.status_id = multiResult.status_id ?? null;
          }
        }
      }
    }
    renderLinkedInUI();
  }

  if (!tab?.id) return;
  if (ctx === CONTEXT.OTHER) return;

  function setMeetNoDataUI() {
    if (HRH.tabs && HRH.tabs.meet && HRH.tabs.meet.setMeetNoDataUI) {
      HRH.tabs.meet.setMeetNoDataUI(document);
    } else {
      const hint = document.getElementById('ctx-meet-hint');
      const copyBtn = document.getElementById('ctx-meet-copy');
      const settingsLink = document.getElementById('ctx-meet-settings-link');
      if (hint) hint.style.display = 'block';
      if (copyBtn) { copyBtn.style.display = 'none'; copyBtn.disabled = true; }
      if (settingsLink) { settingsLink.href = 'https://hr.sftntx.com/extension/'; settingsLink.style.display = 'inline-flex'; }
    }
  }

  try {
    const response = await chrome.tabs.sendMessage(tab.id, { action: 'getPageContext' });
    if (!response || !response.url) {
      if (ctx === CONTEXT.MEET) {
        setMeetNoDataUI();
        updateHeaderActions(false);
      }
      return;
    }

    const dataEl = document.getElementById(`context-${ctx}-data`);
    if (dataEl) {
      const parts = [];
      if (response.context === 'resume') {
        parts.push('Расширение активно: под ссылками на Huntflow показываются данные кандидата.');
      } else if (response.profileUrl) {
        parts.push(`Профиль: ${response.profileUrl}`);
      }
      if (response.eventTitle) parts.push(`Событие: ${response.eventTitle}`);
      if (response.pageUrl && !response.profileUrl && response.context !== 'resume') parts.push(response.pageUrl.replace(/^https?:\/\//, '').slice(0, 50));
      dataEl.textContent = parts.length ? parts.join('\n') : '';
    }

    if (ctx === CONTEXT.RESUME) return;

    if (ctx === CONTEXT.LINKEDIN) {
      const profileUrl = response.profileUrl || '';
      if (!profileUrl) {
        linkedinState = { profileUrl: null, huntflowUrl: response.huntflowUrl || null, saved: false };
        renderLinkedInUI();
        return;
      }
      linkedinState.profileUrl = profileUrl;
      const statusResult = await fetchStatusMulti(profileUrl, null);
      if (statusResult.error) {
        linkedinState.saved = false;
        linkedinState.huntflowUrl = null;
        linkedinState.vacancies = [];
        linkedinState.defaultVacancyId = null;
        linkedinState.vacancy_name = null;
        linkedinState.status_name = null;
        linkedinState.status_id = null;
        linkedinState.rejection_reason_id = null;
        linkedinState.rejection_reason_name = null;
        linkedinState.last_comment_datetime = null;
        const statusEl = document.getElementById('status');
        if (statusEl) { statusEl.textContent = statusResult.error; statusEl.className = 'status err'; }
      } else {
        linkedinState.saved = statusResult.saved;
        linkedinState.huntflowUrl = statusResult.huntflowUrl;
        linkedinState.vacancies = statusResult.vacancies || [];
        linkedinState.defaultVacancyId = statusResult.defaultVacancyId ?? null;
        linkedinState.vacancy_name = statusResult.vacancy_name ?? null;
        linkedinState.status_name = statusResult.status_name ?? null;
        linkedinState.status_id = statusResult.status_id != null ? statusResult.status_id : null;
        linkedinState.rejection_reason_id = statusResult.rejection_reason_id != null ? statusResult.rejection_reason_id : null;
        linkedinState.rejection_reason_name = statusResult.rejection_reason_name ?? null;
        linkedinState.last_comment_datetime = statusResult.last_comment_datetime ?? null;
        if (statusResult.huntflowUrl) {
          fetchCandidateInfo(statusResult.huntflowUrl).then((info) => {
            if (info) { linkedinState.candidateInfo = info; renderLinkedInUI(); }
          });
        }
      }
      renderLinkedInUI();
    }

    if (ctx === CONTEXT.MEET) {
      const headerMeetReminderBtn = document.getElementById('headerMeetReminderBtn');
      if (headerMeetReminderBtn) headerMeetReminderBtn.style.display = 'inline-flex';
      updateMeetReminderToggle(floatingData);
      if (HRH.tabs && HRH.tabs.meet && HRH.tabs.meet.updateMeetUI) {
        HRH.tabs.meet.updateMeetUI(document, response, { escapeHtml, getMeetContactIcon, updateHeaderActions });
      } else {
        const hasCopyData = !!(response.level && (response.vacancyName || response.level));
        if (meetHint) meetHint.style.display = hasCopyData ? 'none' : 'block';
        if (meetOpenAll) { if (hasCopyData) { meetOpenAll.style.display = 'inline-flex'; meetOpenAll.disabled = false; } else { meetOpenAll.style.display = 'none'; meetOpenAll.disabled = true; } }
        if (meetCopy) {
          if (hasCopyData) {
            meetCopy.style.display = 'inline-flex'; meetCopy.disabled = false;
            const v = (response.vacancyName || '').trim(); const l = (response.level || '').trim();
            meetCopy.textContent = (l && v) ? `${l}, ${v}` : (l || v || 'Вакансия и грейд');
            meetCopy.title = (l && v) ? `${l}, ${v}` : (l || v || 'Вакансия и грейд');
          } else { meetCopy.style.display = 'none'; meetCopy.disabled = true; }
        }
        if (meetSettingsLink) { meetSettingsLink.href = 'https://hr.sftntx.com/extension/'; meetSettingsLink.style.display = hasCopyData ? 'none' : 'inline-flex'; }
        if (meetHuntflow) {
          if (response.huntflowUrl) { updateHeaderActions(true, response.huntflowUrl, false, false); meetHuntflow.style.display = 'none'; meetHuntflow.href = response.huntflowUrl; meetHuntflow.removeAttribute('aria-disabled'); }
          else { updateHeaderActions(false); meetHuntflow.style.display = 'none'; meetHuntflow.href = '#'; meetHuntflow.setAttribute('aria-disabled', 'true'); }
        }
        if (meetScorecard && response.scorecardLink) { meetScorecard.href = response.scorecardLink; meetScorecard.setAttribute('aria-disabled', 'false'); }
        if (meetContact) {
          if (response.communicationLink) { meetContact.href = response.communicationLink; meetContact.setAttribute('aria-disabled', 'false'); }
          const contactLabel = response.communicationLabel || 'Контакт';
          meetContact.innerHTML = getMeetContactIcon(contactLabel, response.communicationLink || '') + '<span class="ctx-meet-contact-label">' + escapeHtml(contactLabel) + '</span>';
          meetContact.title = contactLabel; meetContact.setAttribute('aria-label', contactLabel);
        }
      }
      const headerActions = document.getElementById('header-actions');
      if (headerActions) headerActions.style.display = 'flex';
    }
  } catch (_) {
    if (currentContext === CONTEXT.MEET) {
      setMeetNoDataUI();
      updateHeaderActions(false);
      const headerActions = document.getElementById('header-actions');
      if (headerActions) headerActions.style.display = 'flex';
      const headerMeetReminderBtn = document.getElementById('headerMeetReminderBtn');
      if (headerMeetReminderBtn) headerMeetReminderBtn.style.display = 'inline-flex';
      updateMeetReminderToggle(floatingData);
    }
  }
}

const MEET_REMINDER_HIDDEN_KEY = 'hrhelper_meet_reminder_hidden';
const LINKEDIN_FLOATING_HIDDEN_KEY = 'hrhelper_linkedin_floating_hidden';
const RESUME_FLOATING_HIDDEN_KEY = 'hrhelper_resume_floating_hidden';
const HUNTFLOW_FLOATING_HIDDEN_KEY = 'hrhelper_huntflow_floating_hidden';

/** Один batch-запрос для всех ключей видимости плавающих окон (снижение обращений к storage). */
function getFloatingHiddenStates() {
  return chrome.storage.local.get({
    [MEET_REMINDER_HIDDEN_KEY]: false,
    [LINKEDIN_FLOATING_HIDDEN_KEY]: false,
    [RESUME_FLOATING_HIDDEN_KEY]: false,
    [HUNTFLOW_FLOATING_HIDDEN_KEY]: false
  });
}

const MEET_REMINDER_EYE_OPEN_SVG = '<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor"><path d="M12 4.5C7 4.5 2.73 7.61 1 12c1.73 4.39 6 7.5 11 7.5s9.27-3.11 11-7.5c-1.73-4.39-6-7.5-11-7.5zM12 17c-2.76 0-5-2.24-5-5s2.24-5 5-5 5 2.24 5 5-2.24 5-5 5zm0-8c-1.66 0-3 1.34-3 3s1.34 3 3 3 3-1.34 3-3-1.34-3-3-3z"/></svg>';
const MEET_REMINDER_EYE_CLOSED_SVG = '<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor"><path d="M12 7c2.76 0 5 2.24 5 5 0 .65-.13 1.26-.36 1.83l2.92 2.92c1.51-1.26 2.7-2.89 3.43-4.75-1.73-4.39-6-7.5-11-7.5-1.4 0-2.74.25-3.98.7l1.74 1.74c.57-.23 1.18-.36 1.83-.36zM2 4.27l2.28 2.28.46.46C3.08 8.3 1.78 10.02 1 12c1.73 4.39 6 7.5 11 7.5 1.55 0 3.03-.3 4.38-.84l.42.42L19.73 22 21 20.73 3.27 3 2 4.27zM7.53 9.8l1.55 1.55c-.05.21-.08.43-.08.65 0 1.66 1.34 3 3 3 .22 0 .44-.03.65-.08l1.55 1.55c-.67.33-1.41.53-2.2.53-2.76 0-5-2.24-5-5 0-.79.2-1.53.53-2.2zm4.31-.78l3.15 3.15.02-.16c0-1.66-1.34-3-3-3l-.17.01z"/></svg>';

async function updateMeetReminderToggle(preloaded) {
  const btn = document.getElementById('headerMeetReminderBtn');
  if (!btn) return;
  const data = preloaded || await getFloatingHiddenStates();
  const hidden = !!data[MEET_REMINDER_HIDDEN_KEY];
  btn.title = hidden ? 'Показать напоминание на странице' : 'Скрыть напоминание на странице';
  btn.setAttribute('aria-label', btn.title);
  btn.innerHTML = hidden ? MEET_REMINDER_EYE_CLOSED_SVG : MEET_REMINDER_EYE_OPEN_SVG;
}

async function toggleMeetReminderVisibility() {
  const data = await getFloatingHiddenStates();
  const currentlyHidden = !!data[MEET_REMINDER_HIDDEN_KEY];
  const visible = currentlyHidden;
  await chrome.storage.local.set({ [MEET_REMINDER_HIDDEN_KEY]: !visible });
  updateMeetReminderToggle();
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (tab?.id) {
      await chrome.tabs.sendMessage(tab.id, { action: 'setMeetReminderVisible', visible });
    }
  } catch (_) {}
}

const RESUME_FLOATING_EYE_OPEN_SVG = '<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor"><path d="M12 4.5C7 4.5 2.73 7.61 1 12c1.73 4.39 6 7.5 11 7.5s9.27-3.11 11-7.5c-1.73-4.39-6-7.5-11-7.5zM12 17c-2.76 0-5-2.24-5-5s2.24-5 5-5 5 2.24 5 5-2.24 5-5 5zm0-8c-1.66 0-3 1.34-3 3s1.34 3 3 3 3-1.34 3-3-1.34-3-3-3z"/></svg>';
const RESUME_FLOATING_EYE_CLOSED_SVG = '<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor"><path d="M12 7c2.76 0 5 2.24 5 5 0 .65-.13 1.26-.36 1.83l2.92 2.92c1.51-1.26 2.7-2.89 3.43-4.75-1.73-4.39-6-7.5-11-7.5-1.4 0-2.74.25-3.98.7l1.74 1.74c.57-.23 1.18-.36 1.83-.36zM2 4.27l2.28 2.28.46.46C3.08 8.3 1.78 10.02 1 12c1.73 4.39 6 7.5 11 7.5 1.55 0 3.03-.3 4.38-.84l.42.42L19.73 22 21 20.73 3.27 3 2 4.27zM7.53 9.8l1.55 1.55c-.05.21-.08.43-.08.65 0 1.66 1.34 3 3 3 .22 0 .44-.03.65-.08l1.55 1.55c-.67.33-1.41.53-2.2.53-2.76 0-5-2.24-5-5 0-.79.2-1.53.53-2.2zm4.31-.78l3.15 3.15.02-.16c0-1.66-1.34-3-3-3l-.17.01z"/></svg>';

const LINKEDIN_FLOATING_EYE_OPEN_SVG = '<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor"><path d="M12 4.5C7 4.5 2.73 7.61 1 12c1.73 4.39 6 7.5 11 7.5s9.27-3.11 11-7.5c-1.73-4.39-6-7.5-11-7.5zM12 17c-2.76 0-5-2.24-5-5s2.24-5 5-5 5 2.24 5 5-2.24 5-5 5zm0-8c-1.66 0-3 1.34-3 3s1.34 3 3 3 3-1.34 3-3-1.34-3-3-3z"/></svg>';
const LINKEDIN_FLOATING_EYE_CLOSED_SVG = '<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor"><path d="M12 7c2.76 0 5 2.24 5 5 0 .65-.13 1.26-.36 1.83l2.92 2.92c1.51-1.26 2.7-2.89 3.43-4.75-1.73-4.39-6-7.5-11-7.5-1.4 0-2.74.25-3.98.7l1.74 1.74c.57-.23 1.18-.36 1.83-.36zM2 4.27l2.28 2.28.46.46C3.08 8.3 1.78 10.02 1 12c1.73 4.39 6 7.5 11 7.5 1.55 0 3.03-.3 4.38-.84l.42.42L19.73 22 21 20.73 3.27 3 2 4.27zM7.53 9.8l1.55 1.55c-.05.21-.08.43-.08.65 0 1.66 1.34 3 3 3 .22 0 .44-.03.65-.08l1.55 1.55c-.67.33-1.41.53-2.2.53-2.76 0-5-2.24-5-5 0-.79.2-1.53.53-2.2zm4.31-.78l3.15 3.15.02-.16c0-1.66-1.34-3-3-3l-.17.01z"/></svg>';

async function updateLinkedInFloatingToggle(preloaded) {
  const btn = document.getElementById('headerLinkedInFloatingBtn');
  if (!btn) return;
  const data = preloaded || await getFloatingHiddenStates();
  const hidden = !!data[LINKEDIN_FLOATING_HIDDEN_KEY];
  btn.title = hidden ? 'Показать плавающее окно на странице' : 'Скрыть плавающее окно на странице';
  btn.setAttribute('aria-label', btn.title);
  btn.innerHTML = hidden ? LINKEDIN_FLOATING_EYE_CLOSED_SVG : LINKEDIN_FLOATING_EYE_OPEN_SVG;
}

async function toggleLinkedInFloatingVisibility() {
  const data = await getFloatingHiddenStates();
  const currentlyHidden = !!data[LINKEDIN_FLOATING_HIDDEN_KEY];
  const visible = currentlyHidden;
  await chrome.storage.local.set({ [LINKEDIN_FLOATING_HIDDEN_KEY]: !visible });
  updateLinkedInFloatingToggle();
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (tab?.id) {
      await chrome.tabs.sendMessage(tab.id, { action: 'setLinkedInFloatingVisible', visible });
    }
  } catch (_) {}
}

async function updateResumeFloatingToggle(preloaded) {
  const btn = document.getElementById('headerResumeFloatingBtn');
  if (!btn) return;
  const data = preloaded || await getFloatingHiddenStates();
  const hidden = !!data[RESUME_FLOATING_HIDDEN_KEY];
  btn.title = hidden ? 'Показать плавающее окно на странице' : 'Скрыть плавающее окно на странице';
  btn.setAttribute('aria-label', btn.title);
  btn.innerHTML = hidden ? RESUME_FLOATING_EYE_CLOSED_SVG : RESUME_FLOATING_EYE_OPEN_SVG;
}

async function toggleResumeFloatingVisibility() {
  const data = await getFloatingHiddenStates();
  const currentlyHidden = !!data[RESUME_FLOATING_HIDDEN_KEY];
  const visible = currentlyHidden;
  await chrome.storage.local.set({ [RESUME_FLOATING_HIDDEN_KEY]: !visible });
  updateResumeFloatingToggle();
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (tab?.id) {
      await chrome.tabs.sendMessage(tab.id, { action: 'setResumeFloatingVisible', visible });
    }
  } catch (_) {}
}

const HUNTFLOW_FLOATING_EYE_OPEN_SVG = '<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor"><path d="M12 4.5C7 4.5 2.73 7.61 1 12c1.73 4.39 6 7.5 11 7.5s9.27-3.11 11-7.5c-1.73-4.39-6-7.5-11-7.5zM12 17c-2.76 0-5-2.24-5-5s2.24-5 5-5 5 2.24 5 5-2.24 5-5 5zm0-8c-1.66 0-3 1.34-3 3s1.34 3 3 3 3-1.34 3-3-1.34-3-3-3z"/></svg>';
const HUNTFLOW_FLOATING_EYE_CLOSED_SVG = '<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor"><path d="M12 7c2.76 0 5 2.24 5 5 0 .65-.13 1.26-.36 1.83l2.92 2.92c1.51-1.26 2.7-2.89 3.43-4.75-1.73-4.39-6-7.5-11-7.5-1.4 0-2.74.25-3.98.7l1.74 1.74c.57-.23 1.18-.36 1.83-.36zM2 4.27l2.28 2.28.46.46C3.08 8.3 1.78 10.02 1 12c1.73 4.39 6 7.5 11 7.5 1.55 0 3.03-.3 4.38-.84l.42.42L19.73 22 21 20.73 3.27 3 2 4.27zM7.53 9.8l1.55 1.55c-.05.21-.08.43-.08.65 0 1.66 1.34 3 3 3 .22 0 .44-.03.65-.08l1.55 1.55c-.67.33-1.41.53-2.2.53-2.76 0-5-2.24-5-5 0-.79.2-1.53.53-2.2zm4.31-.78l3.15 3.15.02-.16c0-1.66-1.34-3-3-3l-.17.01z"/></svg>';

async function updateHuntflowFloatingToggle(preloaded) {
  const btn = document.getElementById('headerHuntflowFloatingBtn');
  if (!btn) return;
  const data = preloaded || await getFloatingHiddenStates();
  const hidden = !!data[HUNTFLOW_FLOATING_HIDDEN_KEY];
  btn.title = hidden ? 'Показать плавающее окно на странице' : 'Скрыть плавающее окно на странице';
  btn.setAttribute('aria-label', btn.title);
  btn.innerHTML = hidden ? HUNTFLOW_FLOATING_EYE_CLOSED_SVG : HUNTFLOW_FLOATING_EYE_OPEN_SVG;
}

async function toggleHuntflowFloatingVisibility() {
  const data = await getFloatingHiddenStates();
  const currentlyHidden = !!data[HUNTFLOW_FLOATING_HIDDEN_KEY];
  const visible = currentlyHidden;
  await chrome.storage.local.set({ [HUNTFLOW_FLOATING_HIDDEN_KEY]: !visible });
  updateHuntflowFloatingToggle();
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (tab?.id) {
      await chrome.tabs.sendMessage(tab.id, { action: 'setHuntflowFloatingVisible', visible });
    }
  } catch (_) {}
}

/** Сохранить связь LinkedIn ↔ Huntflow (кнопка «Сохранить»). Для rabota.by/hh.ru — обновляет resume→huntflow. */
async function saveLinkedInToHuntflow() {
  const input = document.getElementById('ctx-linkedin-input');
  const saveBtn = document.getElementById('ctx-linkedin-save');
  const raw = (input?.value || '').trim();
  const huntUrl = normalizeHuntflowUrl(raw);
  if (!huntUrl) {
    const statusEl = document.getElementById('status');
    if (statusEl) {
      statusEl.textContent = 'Введите ссылку на Huntflow (например https://huntflow.ru/my/...)';
      statusEl.className = 'status err';
    }
    return;
  }
  if (saveBtn) { saveBtn.disabled = true; saveBtn.title = 'Сохранение...'; }

  if (currentContext === CONTEXT.RESUME && currentTabId) {
    try {
      const t = await chrome.tabs.get(currentTabId);
      const resumeUrl = getBaseUrl(t?.url || '');
      if (!resumeUrl) {
        if (saveBtn) { saveBtn.disabled = false; saveBtn.title = 'Сохранить'; }
        const statusEl = document.getElementById('status');
        if (statusEl) { statusEl.textContent = 'Не удалось определить URL страницы.'; statusEl.className = 'status err'; }
        return;
      }
      const res = await apiFetch('/api/v1/huntflow/resume-links/', {
        method: 'POST',
        body: {
          resume_url: resumeUrl,
          huntflow_url: huntUrl,
          vacancy_name: linkedinState.vacancy_name || '',
        },
      });
      const data = await res.json().catch(() => ({}));
      if (saveBtn) { saveBtn.disabled = false; saveBtn.title = 'Сохранить'; }
      if (!res.ok || !data.success) {
        const statusEl = document.getElementById('status');
        if (statusEl) { statusEl.textContent = data?.message || 'Ошибка обновления ссылки'; statusEl.className = 'status err'; }
        return;
      }
      linkedinState.huntflowUrl = huntUrl;
      linkedinState.saved = true;
      await saveResumeState(t.url, linkedinState);
      renderLinkedInUI();
      const statusEl = document.getElementById('status');
      if (statusEl) { statusEl.textContent = 'Ссылка обновлена.'; statusEl.className = 'status ok'; setTimeout(() => { statusEl.textContent = ''; statusEl.className = 'status'; }, 2000); }
    } catch (e) {
      if (saveBtn) { saveBtn.disabled = false; saveBtn.title = 'Сохранить'; }
      const statusEl = document.getElementById('status');
      if (statusEl) { statusEl.textContent = e.message || 'Ошибка сети'; statusEl.className = 'status err'; }
    }
    return;
  }

  if (!linkedinState.profileUrl) {
    if (saveBtn) { saveBtn.disabled = false; saveBtn.title = 'Сохранить'; }
    return;
  }
  const result = await fetchSetLink(linkedinState.profileUrl, huntUrl);
  if (saveBtn) { saveBtn.disabled = false; saveBtn.title = 'Сохранить'; }
  if (result.error) {
    const statusEl = document.getElementById('status');
    if (statusEl) { statusEl.textContent = result.error; statusEl.className = 'status err'; }
    return;
  }
  const statusResult = await fetchStatusMulti(linkedinState.profileUrl, null);
  if (!statusResult.error) {
    Object.assign(linkedinState, statusResult);
  }
  renderLinkedInUI();
  const statusEl = document.getElementById('status');
  if (statusEl) { statusEl.textContent = ''; statusEl.className = 'status'; }
}

/** Применить введённую ссылку Huntflow (локально или загрузка по huntflow_url на страницах резюме) */
async function applyLinkedInInput() {
  const input = document.getElementById('ctx-linkedin-input');
  const applyBtn = document.getElementById('ctx-linkedin-apply');
  const statusEl = document.getElementById('status');
  const raw = (input?.value || '').trim();
  if (!raw) {
    linkedinState.huntflowUrl = null;
    linkedinState.candidateInfo = null;
    linkedinState.saved = false;
    if (currentContext === CONTEXT.RESUME && currentTabId) {
      try {
        const t = await chrome.tabs.get(currentTabId);
        if (t?.url) await saveResumeState(t.url, linkedinState);
      } catch (_) {}
    }
    renderLinkedInUI();
    return;
  }
  const url = normalizeHuntflowUrl(raw);
  if (!url) {
    linkedinState.huntflowUrl = null;
    linkedinState.candidateInfo = null;
    renderLinkedInUI();
    if (statusEl) {
      statusEl.textContent = 'Введите ссылку на Huntflow (например https://huntflow.ru/my/softnetix#/vacancy/...)';
      statusEl.className = 'status err';
    }
    return;
  }
  linkedinState.huntflowUrl = url;
  if (input) input.value = url;

  if (currentContext === CONTEXT.RESUME) {
    if (applyBtn) { applyBtn.disabled = true; applyBtn.title = 'Загрузка…'; }
    if (statusEl) { statusEl.textContent = 'Загрузка данных…'; statusEl.className = 'status'; }
    const [statusResult, candidateInfo] = await Promise.all([
      fetchStatusByHuntflowUrl(url),
      fetchCandidateInfo(url),
    ]);
    if (statusResult.error) {
      linkedinState.saved = false;
      linkedinState.candidateInfo = candidateInfo;
      renderLinkedInUI();
      if (statusEl) { statusEl.textContent = statusResult.error; statusEl.className = 'status err'; }
      if (applyBtn) { applyBtn.disabled = false; applyBtn.title = 'Применить'; }
      return;
    }
    Object.assign(linkedinState, {
      saved: true,
      vacancy_name: statusResult.vacancy_name ?? null,
      status_name: statusResult.status_name ?? null,
      status_id: statusResult.status_id != null ? statusResult.status_id : null,
      rejection_reason_id: statusResult.rejection_reason_id != null ? statusResult.rejection_reason_id : null,
      rejection_reason_name: statusResult.rejection_reason_name ?? null,
      last_comment_datetime: statusResult.last_comment_datetime ?? null,
    });
    linkedinState.candidateInfo = candidateInfo;
    await loadLinkedInStatusOptions();
    renderLinkedInUI();
    if (statusEl) { statusEl.textContent = ''; statusEl.className = 'status'; }
    if (applyBtn) { applyBtn.disabled = false; applyBtn.title = 'Применено'; setTimeout(() => { applyBtn.title = 'Применить'; }, 1500); }
    try {
      const t = await chrome.tabs.get(currentTabId);
      if (t?.url) {
        await saveResumeState(t.url, linkedinState);
        await saveResumeLinkToBackend(t.url, linkedinState);
      }
    } catch (_) {}
    return;
  }

  linkedinState.candidateInfo = null;
  renderLinkedInUI();
  if (statusEl) { statusEl.textContent = ''; statusEl.className = 'status'; }
  if (applyBtn) {
    applyBtn.title = 'Применено';
    setTimeout(() => { applyBtn.title = 'Применить'; }, 1500);
  }
}

/** Открыть в Huntflow */
function openLinkedInHuntflow(e) {
  e.preventDefault();
  const input = document.getElementById('ctx-linkedin-input');
  const raw = (input?.value || '').trim();
  const url = normalizeHuntflowUrl(raw) || linkedinState.huntflowUrl;
  if (url) window.open(url, '_blank', 'noopener,noreferrer');
}

/** Копирование ссылки Huntflow в буфер */
function copyLinkedInUrl() {
  const input = document.getElementById('ctx-linkedin-input');
  const copyBtn = document.getElementById('ctx-linkedin-copy');
  const raw = (input?.value || '').trim();
  const url = normalizeHuntflowUrl(raw) || linkedinState.huntflowUrl || copyBtn?.dataset?.copyUrl || '';
  if (!url) return;
  navigator.clipboard.writeText(url).then(() => {
    if (copyBtn) {
      const old = copyBtn.textContent;
      copyBtn.textContent = 'Скопировано';
      setTimeout(() => { copyBtn.textContent = old; }, 1500);
    }
  });
}

/** Копировать ссылку Huntflow из header (выбранная вакансия) */
function copyHeaderHuntflowUrl() {
  const headerHuntflowBtn = document.getElementById('headerHuntflowBtn');
  const headerCopyBtn = document.getElementById('headerCopyHuntflowBtn');
  const url = headerCopyBtn?.dataset?.copyUrl || headerHuntflowBtn?.href || '';
  if (!url || url === '#') return;
  navigator.clipboard.writeText(url).then(() => {
    if (headerCopyBtn) {
      const oldTitle = headerCopyBtn.title;
      headerCopyBtn.title = 'Скопировано';
      setTimeout(() => { headerCopyBtn.title = oldTitle; }, 1500);
    }
  });
}

/** Редактировать ссылку: показываем форму с текущей ссылкой и кнопку Сохранить */
function editLinkedInLink() {
  const input = document.getElementById('ctx-linkedin-input');
  const formRowEl = formRow();
  const saveBtn = document.getElementById('ctx-linkedin-save');
  const applyBtn = document.getElementById('ctx-linkedin-apply');
  const statusBlockEl = statusBlock();
  if (formRowEl) formRowEl.style.display = 'block';
  if (input) {
    input.value = linkedinState.huntflowUrl || '';
    input.focus();
  }
  if (saveBtn) saveBtn.style.display = 'inline-flex';
  if (applyBtn) applyBtn.style.display = 'none';
  if (statusBlockEl && currentContext === CONTEXT.RESUME) statusBlockEl.style.display = 'none';
}

/** Данные статусов/причин для блока «Изменение статуса» */
let linkedinStatusOptions = { statuses: [], rejection_reasons: [] };

function findRejectionStatusId() {
  const statuses = linkedinStatusOptions?.statuses || [];
  if (!Array.isArray(statuses) || statuses.length === 0) return null;
  // Сначала ищем по type (наиболее надёжно)
  const byType = statuses.find((s) => {
    const t = String(s?.type || '').toLowerCase();
    return t === 'rejected' || t === 'rejection' || t === 'trash';
  });
  if (byType?.id != null) return String(byType.id);
  // Фолбэк: по имени
  const byName = statuses.find((s) => {
    const n = String(s?.name || '').toLowerCase();
    return n.includes('отказ') || n.includes('reject') || n.includes('rejected') || n.includes('trash') || n.includes('отклон');
  });
  if (byName?.id != null) return String(byName.id);
  return null;
}

function syncLinkedInStatusActionButtons() {
  const statusSelect = document.getElementById('ctx-linkedin-status');
  const nextBtn = document.getElementById('ctx-linkedin-status-next');
  const rejectBtn = document.getElementById('ctx-linkedin-status-reject');
  if (!statusSelect) return;
  const sel = statusSelect.options[statusSelect.selectedIndex];
  const isRej = !!(sel && sel.value && isRejectionStatus(sel));
  if (isRej) {
    if (nextBtn) nextBtn.style.display = 'none';
    if (rejectBtn) rejectBtn.style.display = 'none';
    return;
  }

  // Если следующий по циклу статус — отказ, прячем кнопку "следующий статус"
  let hideNext = false;
  try {
    const options = Array.from(statusSelect.options).filter((o) => o.value !== '');
    if (options.length > 0) {
      const currentIdx = options.findIndex((o) => o.value === statusSelect.value);
      const nextIdx = currentIdx < 0 ? 0 : (currentIdx + 1) % options.length;
      const nextOpt = options[nextIdx];
      hideNext = !!(nextOpt && nextOpt.value && isRejectionStatus(nextOpt));
    }
  } catch (_) {}

  if (nextBtn) nextBtn.style.display = hideNext ? 'none' : '';
  if (rejectBtn) rejectBtn.style.display = '';
}

/** Загрузить опции статусов и причин отказа (по linkedin_url или по huntflow_url для страниц резюме) */
async function loadLinkedInStatusOptions() {
  const statusSelect = document.getElementById('ctx-linkedin-status');
  const reasonSelect = document.getElementById('ctx-linkedin-reason');
  const loadMsg = document.getElementById('ctx-linkedin-status-load-message');
  const canLoadByProfile = linkedinState.profileUrl && linkedinState.saved;
  const canLoadByHuntflow = linkedinState.huntflowUrl && (linkedinState.saved || currentContext === CONTEXT.RESUME);
  if (!statusSelect || (!canLoadByProfile && !canLoadByHuntflow)) return;
  const { baseUrl, apiToken } = await getApiConfig();
  if (!apiToken) return;
  statusSelect.innerHTML = '<option value="">— Статус —</option>';
  if (reasonSelect) reasonSelect.innerHTML = '<option value="">— Причина отказа —</option>';
  linkedinStatusOptions = { statuses: [], rejection_reasons: [] };
  if (loadMsg) {
    loadMsg.textContent = 'Загрузка списка статусов...';
    loadMsg.className = 'ctx-status-load-message';
    loadMsg.style.display = 'block';
  }
  try {
    const q = canLoadByProfile
      ? new URLSearchParams({ linkedin_url: linkedinState.profileUrl })
      : new URLSearchParams({ huntflow_url: linkedinState.huntflowUrl });
    const res = await apiFetch('/api/v1/huntflow/linkedin-applicants/status-options/?' + q.toString(), { method: 'GET' });
    const data = await res.json().catch(() => ({}));
    if (!res.ok || !data.success) {
      if (loadMsg) {
        const base = data?.message || 'Не удалось загрузить список статусов.';
        loadMsg.textContent = currentContext === CONTEXT.RESUME ? base : base + ' Используйте кнопку «Изменить статус» на странице LinkedIn.';
        loadMsg.className = 'ctx-status-load-message error';
        loadMsg.style.display = 'block';
      }
      return;
    }
    const statuses = data.statuses || [];
    const rejectionReasons = data.rejection_reasons || [];
    linkedinStatusOptions = { statuses, rejection_reasons: rejectionReasons };
    statuses.forEach((s) => {
      const opt = document.createElement('option');
      opt.value = s.id;
      opt.textContent = s.name || `Статус #${s.id}`;
      opt.dataset.type = (s.type || '').toLowerCase();
      opt.dataset.name = (s.name || '').toLowerCase();
      statusSelect.appendChild(opt);
    });
    if (linkedinState.status_id != null) {
      const hasOption = Array.from(statusSelect.options).some(o => o.value === String(linkedinState.status_id));
      if (hasOption) statusSelect.value = String(linkedinState.status_id);
    }
    const reasonRowEl = document.getElementById('ctx-linkedin-reason-row');
    function toggleReasonRow() {
      const sel = statusSelect.options[statusSelect.selectedIndex];
      const show = reasonRowEl && sel && isRejectionStatus(sel);
      if (reasonRowEl) reasonRowEl.style.display = show ? 'block' : 'none';
    }
    toggleReasonRow();
    syncLinkedInStatusActionButtons();
    updateHuntflowButtonRejectionClass();
    statusSelect.removeEventListener('change', statusSelect._hrhelperReasonToggle);
    statusSelect._hrhelperReasonToggle = () => { toggleReasonRow(); syncLinkedInStatusActionButtons(); updateHuntflowButtonRejectionClass(); };
    statusSelect.addEventListener('change', statusSelect._hrhelperReasonToggle);
    if (reasonSelect) {
      rejectionReasons.forEach((r) => {
        const opt = document.createElement('option');
        opt.value = r.id;
        opt.textContent = r.name || `Причина #${r.id}`;
        reasonSelect.appendChild(opt);
      });
      if (linkedinState.rejection_reason_id != null) {
        const hasReason = Array.from(reasonSelect.options).some(o => o.value === String(linkedinState.rejection_reason_id));
        if (hasReason) reasonSelect.value = String(linkedinState.rejection_reason_id);
      }
    }
    if (loadMsg) {
      loadMsg.style.display = 'none';
      loadMsg.textContent = '';
    }
  } catch (e) {
    if (loadMsg) {
      loadMsg.textContent = currentContext === CONTEXT.RESUME ? 'Ошибка загрузки списка статусов.' : 'Ошибка загрузки. Используйте кнопку «Изменить статус» на странице LinkedIn.';
      loadMsg.className = 'ctx-status-load-message error';
      loadMsg.style.display = 'block';
    }
  }
  updateHuntflowButtonRejectionClass();
  syncLinkedInStatusActionButtons();
}

/** Переключить статус на следующий по порядку */
function advanceToNextStatus() {
  const statusSelect = document.getElementById('ctx-linkedin-status');
  if (!statusSelect || statusSelect.options.length < 2) return;
  const options = Array.from(statusSelect.options).filter((o) => o.value !== '');
  if (options.length === 0) return;
  const currentIdx = options.findIndex((o) => o.value === statusSelect.value);
  const nextIdx = currentIdx < 0 ? 0 : (currentIdx + 1) % options.length;
  statusSelect.value = options[nextIdx].value;
  if (statusSelect._hrhelperReasonToggle) statusSelect._hrhelperReasonToggle();
  updateHuntflowButtonRejectionClass();
}

/** Быстрый переход к отказу */
function jumpToRejectionStatus() {
  const statusSelect = document.getElementById('ctx-linkedin-status');
  if (!statusSelect) return;
  const rejId = findRejectionStatusId();
  if (!rejId) return;
  const hasOpt = Array.from(statusSelect.options).some((o) => o.value === String(rejId));
  if (!hasOpt) return;
  statusSelect.value = String(rejId);
  if (statusSelect._hrhelperReasonToggle) statusSelect._hrhelperReasonToggle();
  updateHuntflowButtonRejectionClass();
}

/** Обновить класс кнопки «Открыть в Huntflow»: красная при статусе отказ (ctx и header) */
function updateHuntflowButtonRejectionClass() {
  const ctxHuntflowBtn = document.getElementById('ctx-linkedin-huntflow');
  const headerHuntflowBtn = document.getElementById('headerHuntflowBtn');
  const statusSelect = document.getElementById('ctx-linkedin-status');
  if (!statusSelect) return;
  const sel = statusSelect.options[statusSelect.selectedIndex];
  const isRej = !!(sel && sel.value && isRejectionStatus(sel));
  if (ctxHuntflowBtn) ctxHuntflowBtn.classList.toggle('rejection', isRej);
  if (headerHuntflowBtn) headerHuntflowBtn.classList.toggle('rejection', isRej);
}

/** Проверка: выбранный статус — отказ (нужна причина) */
function isRejectionStatus(option) {
  return HRH.isRejectionStatus ? HRH.isRejectionStatus(option) : false;
}

/** Получить HTML-содержимое комментария из редактора */
function getCommentHtml() {
  const editor = document.getElementById('ctx-linkedin-comment');
  if (!editor) return '';
  const html = (editor.innerHTML || '').trim();
  return html === '<br>' || html === '<br/>' ? '' : html;
}

/** Применить выбранный статус (и причину при отказе) */
async function applyLinkedInStatus() {
  const statusSelect = document.getElementById('ctx-linkedin-status');
  const reasonSelect = document.getElementById('ctx-linkedin-reason');
  const applyBtn = document.getElementById('ctx-linkedin-apply-status');
  const statusEl = document.getElementById('status');
  const hasIdentity = linkedinState.profileUrl || (linkedinState.huntflowUrl && currentContext === CONTEXT.RESUME);
  if (!hasIdentity || !statusSelect?.value) {
    if (statusEl) { statusEl.textContent = 'Выберите статус.'; statusEl.className = 'status warn'; }
    return;
  }
  const statusId = statusSelect.value.trim();
  const selectedStatusOpt = statusSelect.options[statusSelect.selectedIndex];
  const needReason = isRejectionStatus(selectedStatusOpt);
  const rejectionReasonId = reasonSelect?.value?.trim() || null;
  if (needReason && !rejectionReasonId) {
    if (statusEl) { statusEl.textContent = 'Для статуса отказа выберите причину.'; statusEl.className = 'status warn'; }
    return;
  }
  if (applyBtn) { applyBtn.disabled = true; applyBtn.textContent = 'Сохранение…'; }
  const commentHtml = getCommentHtml();
  const body = {
    status_id: parseInt(statusId, 10),
    rejection_reason_id: rejectionReasonId ? parseInt(rejectionReasonId, 10) : null,
  };
  if (commentHtml) body.comment = commentHtml;
  if (linkedinState.profileUrl) body.linkedin_url = linkedinState.profileUrl;
  else if (linkedinState.huntflowUrl) body.huntflow_url = linkedinState.huntflowUrl;
  if (linkedinState.selectedVacancyId) body.vacancy_id = linkedinState.selectedVacancyId;
  try {
    const res = await apiFetch('/api/v1/huntflow/linkedin-applicants/update-status/', {
      method: 'POST',
      body: body,
    });
    const data = await res.json().catch(() => ({}));
    if (res.ok && data.success) {
      if (statusEl) { statusEl.textContent = 'Статус обновлён.'; statusEl.className = 'status ok'; }
      const commentEditor = document.getElementById('ctx-linkedin-comment');
      if (commentEditor) { commentEditor.innerHTML = ''; }
      setTimeout(() => { if (statusEl) { statusEl.textContent = ''; statusEl.className = 'status'; } }, 2000);
      if (linkedinState.profileUrl) refreshLinkedInState().then(() => renderLinkedInUI());
    } else {
      if (statusEl) { statusEl.textContent = data?.message || 'Ошибка обновления статуса'; statusEl.className = 'status err'; }
    }
  } catch (e) {
    if (statusEl) { statusEl.textContent = e.message || 'Ошибка сети'; statusEl.className = 'status err'; }
  }
  if (applyBtn) { applyBtn.disabled = false; applyBtn.textContent = 'Применить статус'; }
}

/** Запрос копирования текста уровня (Meet): получаем текст из content script и копируем в попапе (нужен контекст клика) */
async function copyMeetLevelText() {
  const btn = document.getElementById('ctx-meet-copy');
  if (!currentTabId || !btn) return;
  const old = btn.textContent;
  try {
    const res = await chrome.tabs.sendMessage(currentTabId, { action: 'copyLevelText' });
    if (res && res.success && res.text) {
      await navigator.clipboard.writeText(res.text);
      btn.textContent = 'Скопировано';
      setTimeout(() => { btn.textContent = old; }, 1500);
    } else {
      btn.textContent = 'Нет данных';
      setTimeout(() => { btn.textContent = old; }, 1500);
    }
  } catch (_) {
    btn.textContent = 'Нет данных';
    setTimeout(() => { btn.textContent = old; }, 1500);
  }
}

/** Копирование и открытие Huntflow + Scorecard (Meet, попап) */
async function openMeetAll() {
  if (!currentTabId) return;
  const openBtn = document.getElementById('ctx-meet-open-all');
  const copyBtn = document.getElementById('ctx-meet-copy');
  if (openBtn) openBtn.disabled = true;
  const oldCopyText = copyBtn ? copyBtn.textContent : '';
  try {
    let res = null;
    try {
      res = await chrome.tabs.sendMessage(currentTabId, { action: 'copyLevelText' });
    } catch (e) {
      // Receiving end does not exist: вкладка закрыта, не Meet, или content script не загружен
      if (e?.message && (e.message.includes('Receiving end does not exist') || e.message.includes('Could not establish connection'))) return;
      throw e;
    }
    if (res && res.success && res.text && navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(res.text);
      if (copyBtn) {
        copyBtn.textContent = 'Скопировано';
        setTimeout(() => { copyBtn.textContent = oldCopyText; }, 1500);
      }
    }
    // открываем Huntflow и Scorecard из текущего контекста
    let urls = [];
    try {
      const tab = await chrome.tabs.get(currentTabId);
      const response = await chrome.tabs.sendMessage(tab.id, { action: 'getPageContext' });
      if (response && response.huntflowUrl) urls.push(response.huntflowUrl);
      if (response && response.scorecardLink) urls.push(response.scorecardLink);
    } catch (_) {
      // вкладка закрыта или content script недоступен — просто не открываем ссылки
    }
    if (urls.length) {
      chrome.runtime.sendMessage({ type: 'HRHELPER_OPEN_TABS', urls });
    }
  } finally {
    if (openBtn) openBtn.disabled = false;
  }
}

var normalizeToken = HRH.normalizeToken;
if (!normalizeToken) {
  throw new Error("[HRHelper] shared/utils/token.js not loaded (normalizeToken missing)");
}

/** Заполняет форму настройки в попапе значениями из storage */
async function loadSetupForm() {
  const cfg = await chrome.storage.sync.get(DEFAULTS);
  const baseUrl = (cfg.baseUrl || DEFAULTS.baseUrl || '').replace(/\/+$/, '');
  const apiToken = cfg.apiToken || '';
  const baseUrlEl = document.getElementById('popup-baseUrl');
  const tokenEl = document.getElementById('popup-apiToken');
  const tokenLink = document.getElementById('popup-token-link');
  if (baseUrlEl) baseUrlEl.value = baseUrl;
  if (tokenEl) tokenEl.value = apiToken;
  if (tokenLink && baseUrl) tokenLink.href = (baseUrl.replace(/\/+$/, '') + '/accounts/integrations/');
}

/** Сохраняет настройки из формы попапа в storage */
async function saveSetupForm() {
  const baseUrl = (document.getElementById('popup-baseUrl')?.value || '').trim().replace(/\/+$/, '');
  const rawToken = (document.getElementById('popup-apiToken')?.value || '').trim();
  const apiToken = normalizeToken(rawToken);
  const statusEl = document.getElementById('status');
  if (!baseUrl) {
    if (statusEl) { statusEl.textContent = 'Укажите Base URL.'; statusEl.className = 'status err'; }
    return false;
  }
  if (!apiToken) {
    if (statusEl) { statusEl.textContent = 'Укажите API токен.'; statusEl.className = 'status err'; }
    return false;
  }
  await chrome.storage.sync.set({ baseUrl, apiToken });
  if (statusEl) { statusEl.textContent = 'Сохранено.'; statusEl.className = 'status ok'; setTimeout(() => { statusEl.textContent = ''; statusEl.className = 'status'; }, 1500); }
  return true;
}

async function showStatus() {
  const cfg = await chrome.storage.sync.get(DEFAULTS);
  const baseUrl = (cfg.baseUrl || DEFAULTS.baseUrl).replace(/\/+$/, '');
  const rawToken = (cfg.apiToken || DEFAULTS.apiToken || '').trim();
  const apiToken = normalizeToken(rawToken);
  const el = document.getElementById('status');
  const beforeSetupBlock = document.getElementById('before-setup-block');
  const addVacancyPanel = document.getElementById('add-vacancy-panel');

  if (!apiToken) {
    el.textContent = 'Укажите API токен для работы с HR Helper.';
    el.className = 'status warn';
    if (beforeSetupBlock) {
      beforeSetupBlock.style.display = 'block';
      loadSetupForm();
    }
    document.querySelectorAll('.context-block').forEach((b) => b.classList.remove('visible'));
    if (addVacancyPanel) addVacancyPanel.classList.remove('visible');
    return;
  }

  try {
    const res = await fetch(`${baseUrl}/api/v1/accounts/users/profile_dashboard/`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Token ${apiToken}`,
      },
    });
    if (res.ok) {
      const json = await res.json().catch(() => ({}));
      const data = json.data || json;
      const user = data.user || data;
      const name = user.email || user.username || (user.first_name && user.last_name ? `${user.first_name} ${user.last_name}` : user.username) || 'Вы';
      el.textContent = `Подключено как ${name}`;
      el.className = 'status ok';
      const wasShowingSetup = beforeSetupBlock && beforeSetupBlock.style.display !== 'none';
      if (beforeSetupBlock) beforeSetupBlock.style.display = 'none';
      if (wasShowingSetup) showContextForTab();
    } else {
      if (res.status === 0) {
        el.textContent = 'Запрос заблокирован (сеть или CORS). На сервере HR Helper должен быть разрешён origin расширения (chrome-extension://ID).';
        el.className = 'status err';
      } else if (res.status === 401) {
        el.textContent = 'Токен недействителен. Вставьте только ключ из data.token (без «Token » и без кавычек).';
        el.className = 'status err';
      } else {
        el.textContent = `Ошибка ${res.status}. Обновите токен или проверьте сервер.`;
        el.className = 'status err';
      }
      if (beforeSetupBlock) {
        beforeSetupBlock.style.display = 'block';
        loadSetupForm();
      }
      document.querySelectorAll('.context-block').forEach((b) => b.classList.remove('visible'));
      if (addVacancyPanel) addVacancyPanel.classList.remove('visible');
    }
  } catch (e) {
    el.textContent = 'Не удалось подключиться к HR Helper. Проверьте URL и сеть.';
    el.className = 'status err';
    if (beforeSetupBlock) {
      beforeSetupBlock.style.display = 'block';
      loadSetupForm();
    }
    document.querySelectorAll('.context-block').forEach((b) => b.classList.remove('visible'));
    if (addVacancyPanel) addVacancyPanel.classList.remove('visible');
  }
}

function openOptionsPage(e) {
  if (e) e.preventDefault();
  chrome.runtime.openOptionsPage();
}
document.getElementById('headerSettingsBtn').addEventListener('click', openOptionsPage);

document.getElementById('popup-save').addEventListener('click', async () => {
  const ok = await saveSetupForm();
  if (ok) await showStatus();
});

document.getElementById('ctx-linkedin-huntflow').addEventListener('click', openLinkedInHuntflow);
document.getElementById('ctx-linkedin-copy').addEventListener('click', copyLinkedInUrl);
document.getElementById('headerCopyHuntflowBtn')?.addEventListener('click', copyHeaderHuntflowUrl);
document.getElementById('ctx-linkedin-apply').addEventListener('click', applyLinkedInInput);
document.getElementById('ctx-linkedin-save').addEventListener('click', () => saveLinkedInToHuntflow());
document.getElementById('ctx-linkedin-edit').addEventListener('click', editLinkedInLink);
document.getElementById('ctx-linkedin-apply-status').addEventListener('click', applyLinkedInStatus);
document.getElementById('ctx-linkedin-status-reject')?.addEventListener('click', jumpToRejectionStatus);
document.getElementById('ctx-linkedin-status-next')?.addEventListener('click', advanceToNextStatus);
document.getElementById('ctx-linkedin-candidate-toggle').addEventListener('click', () => {
  const body = document.getElementById('ctx-linkedin-candidate-body');
  const toggle = document.getElementById('ctx-linkedin-candidate-toggle');
  if (!body || !toggle) return;
  const open = body.hidden;
  body.hidden = !open;
  toggle.setAttribute('aria-expanded', String(open));
});
document.getElementById('ctx-meet-copy').addEventListener('click', copyMeetLevelText);
document.getElementById('ctx-meet-open-all').addEventListener('click', openMeetAll);
document.getElementById('headerMeetReminderBtn')?.addEventListener('click', toggleMeetReminderVisibility);
document.getElementById('headerLinkedInFloatingBtn')?.addEventListener('click', toggleLinkedInFloatingVisibility);
document.getElementById('headerResumeFloatingBtn')?.addEventListener('click', toggleResumeFloatingVisibility);
document.getElementById('headerHuntflowFloatingBtn')?.addEventListener('click', toggleHuntflowFloatingVisibility);

// Круглые кнопки копирования (вакансия/вопросы/слоты)
document.getElementById('btn-copy-vacancy-link-belarus')?.addEventListener('click', async (e) => {
  e.preventDefault();
  const v = copyButtonsState.vacancy;
  const ok = await copyToClipboard(v?.vacancy_link_belarus || '');
  if (ok) flashCopySuccess(e.currentTarget);
});
document.getElementById('btn-copy-vacancy-link-poland')?.addEventListener('click', async (e) => {
  e.preventDefault();
  const v = copyButtonsState.vacancy;
  const ok = await copyToClipboard(v?.vacancy_link_poland || '');
  if (ok) flashCopySuccess(e.currentTarget);
});
document.getElementById('btn-copy-questions-belarus')?.addEventListener('click', async (e) => {
  e.preventDefault();
  const v = copyButtonsState.vacancy;
  const ok = await copyToClipboard(v?.questions_belarus || '');
  if (ok) flashCopySuccess(e.currentTarget);
});
document.getElementById('btn-copy-questions-poland')?.addEventListener('click', async (e) => {
  e.preventDefault();
  const v = copyButtonsState.vacancy;
  const ok = await copyToClipboard(v?.questions_poland || '');
  if (ok) flashCopySuccess(e.currentTarget);
});
document.getElementById('btn-copy-current-week')?.addEventListener('click', async (e) => {
  e.preventDefault();
  await handleCopySlots('current', e.currentTarget);
});
document.getElementById('btn-copy-next-week')?.addEventListener('click', async (e) => {
  e.preventDefault();
  await handleCopySlots('next', e.currentTarget);
});
document.getElementById('btn-copy-all-slots')?.addEventListener('click', async (e) => {
  e.preventDefault();
  await handleCopySlots('all', e.currentTarget);
});
document.getElementById('btn-add-third-week')?.addEventListener('click', async (e) => {
  e.preventDefault();
  await handleAddThirdWeek(e.currentTarget);
});

// Панель форматирования комментария
document.querySelectorAll('.ctx-toolbar-btn').forEach((btn) => {
  btn.addEventListener('click', (e) => {
    e.preventDefault();
    const editor = document.getElementById('ctx-linkedin-comment');
    if (!editor) return;
    editor.focus();
    const cmd = btn.dataset.cmd;
    if (cmd === 'createLink') {
      const url = prompt('Введите URL ссылки:', 'https://');
      if (url && url.trim()) {
        document.execCommand(cmd, false, url.trim());
      }
    } else {
      document.execCommand(cmd, false, null);
    }
  });
});

// ============ GOOGLE DRIVE FUNCTIONS ============

async function initGDriveSection() {
  console.log('[HR Helper] Initializing Google Drive section');
  const section = document.getElementById('context-gdrive');
  if (!section) {
    console.error('[HR Helper] Google Drive section not found in popup.html');
    return;
  }
  
  section.style.display = 'block';
  
  try {
    let fileId = null;
    
    // Сначала пробуем получить из URL текущей вкладки
    let tab = null;
    try {
      const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
      tab = tabs && tabs[0];
      console.log('[HR Helper] Current tab:', tab ? { id: tab.id, url: tab.url } : 'no tab');
    } catch (tabError) {
      console.error('[HR Helper] Error getting tab:', tabError);
    }
    
    if (tab && tab.url) {
      console.log('[HR Helper] Tab URL:', tab.url);
      // Поддержка разных форматов URL Google Drive:
      // - /file/d/FILE_ID/view
      // - /file/d/FILE_ID/edit
      // - /file/d/FILE_ID/preview
      // - /open?id=FILE_ID
      let match = tab.url.match(/\/file\/d\/([a-zA-Z0-9_-]+)/);
      if (!match) {
        match = tab.url.match(/[?&]id=([a-zA-Z0-9_-]+)/);
      }
      if (match) {
        fileId = match[1];
        console.log('[HR Helper] File ID extracted from URL:', fileId);
      } else {
        console.log('[HR Helper] URL does not match Google Drive file pattern');
      }
    } else {
      console.log('[HR Helper] No tab URL available');
    }
    
    // Если не получилось из URL, пробуем из storage
    if (!fileId) {
      try {
        const data = await chrome.storage.local.get('currentGDriveFile');
        console.log('[HR Helper] Storage data:', data);
        if (data.currentGDriveFile && data.currentGDriveFile.fileId) {
          fileId = data.currentGDriveFile.fileId;
          console.log('[HR Helper] File ID loaded from storage:', fileId);
        }
      } catch (storageError) {
        console.error('[HR Helper] Error reading storage:', storageError);
      }
    }
    
    if (fileId) {
      currentGDriveFileId = fileId;
      const fileIdEl = document.getElementById('gdrive-file-id');
      if (fileIdEl) fileIdEl.textContent = currentGDriveFileId;
      
      await loadActiveVacancies();
    } else {
      showGDriveError('Не удалось получить ID файла. Убедитесь, что вы на странице файла Google Drive (drive.google.com/file/d/...).');
    }
  } catch (error) {
    console.error('[HR Helper] Error in initGDriveSection:', error);
    showGDriveError('Ошибка: ' + error.message);
  }
  
  setupGDriveEventHandlers();
}

async function loadActiveVacancies() {
  console.log('[HR Helper] Loading active vacancies');
  const select = document.getElementById('gdrive-vacancy-select');
  const addBtn = document.getElementById('gdrive-add-btn');
  
  if (!select) return;
  
  select.innerHTML = '<option value="">— Загрузка... —</option>';
  
  try {
    const response = await chrome.runtime.sendMessage({
      type: 'HRHELPER_API',
      payload: {
        path: '/api/vacancies/active/',
        method: 'GET'
      }
    });
    
    console.log('[HR Helper] Vacancies response:', response);
    
    if (response && response.ok && response.json && response.json.vacancies) {
      const vacancies = response.json.vacancies;
      
      if (vacancies.length === 0) {
        select.innerHTML = '<option value="">— Нет активных вакансий —</option>';
        return;
      }
      
      select.innerHTML = '<option value="">— Выберите вакансию —</option>';
      
      vacancies.forEach(vacancy => {
        const option = document.createElement('option');
        option.value = vacancy.id;
        option.textContent = `${vacancy.position}${vacancy.company ? ' (' + vacancy.company + ')' : ''}`;
        option.dataset.vacancyUrl = vacancy.huntflow_url || '';
        option.dataset.vacancyName = vacancy.position;
        select.appendChild(option);
      });
      
      select.disabled = false;
      if (addBtn) addBtn.disabled = true;
      console.log('[HR Helper] Loaded', vacancies.length, 'vacancies');
    } else {
      const errorMsg = response?.json?.message || response?.json?.error || 'Ошибка API';
      console.error('[HR Helper] API error:', errorMsg);
      select.innerHTML = '<option value="">— Ошибка загрузки —</option>';
    }
  } catch (error) {
    console.error('[HR Helper] Error loading vacancies:', error);
    select.innerHTML = '<option value="">— Ошибка загрузки —</option>';
  }
}

let gdriveHandlersInitialized = false;

function setupGDriveEventHandlers() {
  if (gdriveHandlersInitialized) return;
  gdriveHandlersInitialized = true;
  
  const vacancySelect = document.getElementById('gdrive-vacancy-select');
  const addBtn = document.getElementById('gdrive-add-btn');
  
  if (vacancySelect) {
    vacancySelect.addEventListener('change', (e) => {
      selectedVacancyId = e.target.value ? parseInt(e.target.value) : null;
      if (addBtn) addBtn.disabled = !selectedVacancyId || !currentGDriveFileId;
      console.log('[HR Helper] Vacancy selected:', selectedVacancyId);
    });
  }
  
  if (addBtn) {
    addBtn.addEventListener('click', async () => {
      console.log('[HR Helper] Add button clicked');
      await parseAndCreateCandidate();
    });
  }
}

async function parseAndCreateCandidate() {
  const addBtn = document.getElementById('gdrive-add-btn');
  const resultBox = document.getElementById('gdrive-result');
  const errorBox = document.getElementById('gdrive-error');
  const vacancySelect = document.getElementById('gdrive-vacancy-select');
  
  if (addBtn) {
    addBtn.disabled = true;
    addBtn.textContent = 'Обработка...';
  }
  if (errorBox) errorBox.style.display = 'none';
  
  try {
    console.log('[HR Helper] Sending parse-and-create request:', {
      fileId: currentGDriveFileId,
      vacancyId: selectedVacancyId
    });
    
    const response = await chrome.runtime.sendMessage({
      type: 'HRHELPER_API',
      payload: {
        path: '/api/gdrive/parse-and-create/',
        method: 'POST',
        body: {
          file_id: currentGDriveFileId,
          vacancy_id: selectedVacancyId
        }
      }
    });
    
    console.log('[HR Helper] Response:', response);
    
    if (response.ok && response.json && response.json.success) {
      const result = response.json;
      
      const selectedOption = vacancySelect?.options[vacancySelect.selectedIndex];
      const vacancyName = selectedOption ? selectedOption.dataset.vacancyName : 'Вакансия';
      
      document.getElementById('result-name').textContent = result.full_name || 'Кандидат';
      document.getElementById('result-vacancy').textContent = vacancyName;
      
      const link = document.getElementById('result-link');
      if (link) link.href = result.huntflow_url || '#';
      
      if (resultBox) resultBox.style.display = 'block';
      
      if (addBtn) addBtn.style.display = 'none';
      if (vacancySelect) vacancySelect.disabled = true;
      
      // Notify content script to show floating widget via storage
      try {
        await chrome.storage.local.set({
          hrhelper_gdrive_candidate_created: {
            fileId: currentGDriveFileId,
            timestamp: Date.now(),
            result: result
          }
        });
        
        // Also try to send message directly
        const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
        if (tabs && tabs[0]) {
          chrome.tabs.sendMessage(tabs[0].id, {
            type: 'HRHELPER_GDRIVE_CANDIDATE_CREATED',
            payload: result
          }).catch(() => {});
        }
      } catch (_) {}
      
      console.log('[HR Helper] Candidate created successfully');
      
    } else {
      throw new Error(response.json?.message || response.json?.error || 'Ошибка создания кандидата');
    }
    
  } catch (error) {
    console.error('[HR Helper] Error:', error);
    showGDriveError('Ошибка: ' + error.message);
  } finally {
    if (addBtn) {
      addBtn.disabled = !selectedVacancyId || !currentGDriveFileId;
      addBtn.textContent = 'Добавить в Huntflow';
    }
  }
}

function showGDriveError(message) {
  const errorBox = document.getElementById('gdrive-error');
  if (errorBox) {
    errorBox.textContent = message;
    errorBox.style.display = 'block';
  }
  console.error('[HR Helper]', message);
}

// ============ END GOOGLE DRIVE FUNCTIONS ============

// Тема попапа из настроек
loadAndApplyPopupTheme();
chrome.storage.onChanged.addListener(function (changes, areaName) {
  if (areaName === 'sync' && changes[OPTIONS_THEME_KEY]) {
    applyPopupTheme(changes[OPTIONS_THEME_KEY].newValue);
  }
});

// Сначала показываем контекст по текущей вкладке, затем статус
showContextForTab().then(() => showStatus());
