/**
 * HR Helper — контент-скрипт для rabota.by/resume/* и hh.ru/resume/*
 * 1) Под «Кандидат» или ФИО подрисовывает сохранённые данные Huntflow при связи по ссылке.
 * 2) Под ссылками на Huntflow на странице выводит блок с данными кандидата из API.
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
  var debounce = HRH.debounce;
  var TIMING = HRH.TIMING || {};
  try {
    var data = await chrome.storage.sync.get({ [ACTIVE_PAGES_KEY]: DEFAULT_ACTIVE_PAGES });
    var active = data[ACTIVE_PAGES_KEY] || DEFAULT_ACTIVE_PAGES;
    if (!active.hh_ecosystem) return;
  } catch (_) {
    return;
  }

  const DATA_ATTR = 'data-hrhelper-candidate-info';
  const BY_LINK_ATTR = 'data-hrhelper-by-link';
  const RESUME_STORAGE_KEY = 'hrhelper_resume_state';
  const FLOATING_ATTR = 'data-hrhelper-resume-floating';
  const FLOATING_POS_KEY = 'hrhelper_resume_floating_pos';
  const RESUME_FLOATING_HIDDEN_KEY = 'hrhelper_resume_floating_hidden';
  const RESUME_FLOATING_UI_STATE_KEY = 'hrhelper_resume_floating_ui_state';
  const DEFAULT_RESUME_FLOATING_UI_STATE = { widgetCollapsed: false, additionalFieldsOpen: true, commentsOpen: true };
  let resumeFloatingUIState = { ...DEFAULT_RESUME_FLOATING_UI_STATE };
  let resumeSelectedVacancyId = null;
  let resumeDefaultVacancyId = null;
  let resumeVacanciesCache = [];
  let resumeCandidateInfoCache = null;

  function loadResumeFloatingUIState() {
    try {
      chrome.storage.local.get({ [RESUME_FLOATING_UI_STATE_KEY]: DEFAULT_RESUME_FLOATING_UI_STATE }, (data) => {
        const s = data[RESUME_FLOATING_UI_STATE_KEY] || {};
        resumeFloatingUIState = { ...DEFAULT_RESUME_FLOATING_UI_STATE, ...s };
      });
    } catch (_) {}
  }
  function saveResumeFloatingUIState(update) {
    Object.assign(resumeFloatingUIState, update);
    try {
      chrome.storage.local.set({ [RESUME_FLOATING_UI_STATE_KEY]: { ...resumeFloatingUIState } });
    } catch (_) {}
  }

  const isNewStatusName = HRH.isNewStatusName;
  const hasBlacklistLabel = HRH.hasBlacklistLabel;
  if (!isNewStatusName || !hasBlacklistLabel) {
    throw new Error("[HRHelper] shared/domain/status-logic.js not loaded (isNewStatusName/hasBlacklistLabel missing)");
  }

  function getPrimaryVacancyForBorder(vacancies) {
    const items = Array.isArray(vacancies) ? vacancies : [];
    // Берём ту, что с последней активностью, иначе первую
    let best = null;
    let bestTs = null;
    for (const v of items) {
      const ts = v?.last_change_at || null;
      const dt = ts ? new Date(ts) : null;
      const t = dt && !isNaN(dt.getTime()) ? dt.getTime() : null;
      if (t != null && (bestTs == null || t > bestTs)) {
        bestTs = t;
        best = v;
      }
    }
    return best || items[0] || null;
  }

  /** Единственное исключение среди отказов: причина «Закрыли вакансию другим» — рамка синяя. */
  function isRejectionReasonClosedByOther(reasonName) {
    const n = (reasonName || '').trim().toLowerCase().replace(/ё/g, 'е');
    return n.includes('закрыли') && n.includes('вакансию') && n.includes('другим');
  }

  function computeFloatingBorderColorResume(candidateInfo, vacancies) {
    if (hasBlacklistLabel(candidateInfo)) return '#111'; // чёрный — всегда, вне зависимости от статуса и состояния

    const inBase = !!(candidateInfo && (candidateInfo.full_name || candidateInfo.phone || candidateInfo.email || candidateInfo.telegram || candidateInfo.communication || candidateInfo.office_readiness || candidateInfo.level)) || (vacancies || []).length > 0;
    if (!inBase) return null;

    const primary = getPrimaryVacancyForBorder(vacancies || []);
    const statusType = primary?.status_type;
    const statusName = primary?.status_name || '';

    if (statusType === 'rejected') {
      if (isRejectionReasonClosedByOther(primary?.rejection_reason_name)) return '#0a66c2'; // синий — исключение
      const ts = primary?.last_change_at || null;
      const dt = ts ? new Date(ts) : null;
      const ms = dt && !isNaN(dt.getTime()) ? (Date.now() - dt.getTime()) : null;
      const halfYearMs = 183 * 24 * 60 * 60 * 1000;
      if (ms != null && ms < halfYearMs) return '#dc3545'; // красный
      return '#fd7e14'; // оранжевый
    }

    if (!isNewStatusName(statusName)) return '#198754'; // зелёный
    return '#0a66c2'; // синий
  }

  /** Цвет рамки для одной вакансии (та же логика, что для всего плавающего окна). */
  function computeBorderColorForVacancy(v) {
    if (!v) return null;
    const statusType = v.status_type;
    const statusName = v.status_name || '';

    if (statusType === 'rejected') {
      if (isRejectionReasonClosedByOther(v.rejection_reason_name)) return '#0a66c2'; // синий — исключение
      const ts = v.last_change_at || v.last_comment_at || null;
      const dt = ts ? new Date(ts) : null;
      const ms = dt && !isNaN(dt.getTime()) ? (Date.now() - dt.getTime()) : null;
      const halfYearMs = 183 * 24 * 60 * 60 * 1000;
      if (ms != null && ms < halfYearMs) return '#dc3545'; // красный
      return '#fd7e14'; // оранжевый
    }
    if (!isNewStatusName(statusName)) return '#198754'; // зелёный
    return '#0a66c2'; // синий
  }

  const hexToRgba = HRH.hexToRgba;
  if (!hexToRgba) {
    throw new Error("[HRHelper] shared/utils/color.js not loaded (hexToRgba missing)");
  }

  function applyFloatingBorder(wrapper, color) {
    if (!wrapper) return;
    if (!wrapper.dataset.hrhelperBaseBoxShadow) wrapper.dataset.hrhelperBaseBoxShadow = wrapper.style.boxShadow || '';
    const base = wrapper.dataset.hrhelperBaseBoxShadow || '';
    if (!color) { wrapper.style.boxShadow = base; return; }
    const shadowColor = hexToRgba(color, 0.28);
    wrapper.style.boxShadow = `0 0 0 2px ${color} inset, 0 4px 14px -2px ${shadowColor}, ${base}`;
  }

  function getHuntflowUrl(link) {
    let href = (link.href || link.getAttribute('href') || '').trim();
    if (href && href.includes('google.com/url')) {
      try {
        const u = new URL(href);
        const q = u.searchParams.get('q');
        if (q) href = decodeURIComponent(q);
      } catch (_) {}
    }
    if (href && (href.includes('huntflow.ru') || href.includes('huntflow.dev'))) return href;
    const text = (link.textContent || '').trim();
    const m = text.match(/https?:\/\/[^\s]+huntflow[^\s]*/);
    return m ? m[0] : null;
  }

  const apiFetch = HRH.apiFetch;
  if (!apiFetch) {
    throw new Error("[HRHelper] shared/api/client.js not loaded (apiFetch missing)");
  }

  async function apiJson(path, init) {
    var res = await apiFetch(path, init || {});
    if (!res || !res.ok) return null;
    return (typeof res.json === "function") ? await res.json() : res.json;
  }

  async function checkHhIntegrationStatus() {
    try {
      const res = await apiFetch('/api/v1/hh/integration-status', { method: 'GET' });
      const data = await res.json().catch(() => null);
      if (!res.ok || !data) return { connected: false };
      return data;
    } catch (_) {
      return { connected: false };
    }
  }

  async function checkHhActionsAvailability(resumeUrl, huntflowUrl) {
    try {
      const qp = new URLSearchParams({ resume_url: resumeUrl });
      if (huntflowUrl && (huntflowUrl = (huntflowUrl || '').trim())) qp.set('huntflow_url', huntflowUrl);
      const res = await apiFetch(`/api/v1/hh/actions-availability?${qp.toString()}`, { method: 'GET' });
      const data = await res.json().catch(() => null);
      if (!res.ok || !data) return { success: false, actions_allowed: false };
      return data;
    } catch (_) {
      return { success: false, actions_allowed: false };
    }
  }

  function normalizeHuntflowUrl(raw) {
    const s = (raw || '').trim();
    if (!s || (!s.includes('huntflow.ru') && !s.includes('huntflow.dev'))) return null;
    try {
      const u = new URL(s);
      if (u.hostname.includes('huntflow')) return s;
    } catch (_) {}
    return s || null;
  }

  /** POST сохранение связи резюме ↔ Huntflow */
  function postResumeLink(resumeUrl, huntflowUrl) {
    return apiJson('/api/v1/huntflow/resume-links/', {
      method: 'POST',
      body: { resume_url: resumeUrl, huntflow_url: huntflowUrl },
    });
  }

  /** Добавить кандидата (по huntflow_url, для HH можно передать resume_url) на вакансию */
  async function addToVacancyResume(huntflowUrl, vacancyId, resumeUrl) {
    try {
      const body = { huntflow_url: huntflowUrl, vacancy_id: vacancyId };
      if (resumeUrl && (resumeUrl = (resumeUrl || '').trim())) body.resume_url = resumeUrl;
      const res = await apiFetch('/api/v1/huntflow/linkedin-applicants/add-to-vacancy/', {
        method: 'POST',
        body: JSON.stringify(body),
      });
      const data = await res.json().catch(() => null);
      return res.ok && data && data.success ? data : null;
    } catch (_) {
      return null;
    }
  }

  function escapeHtml(s) {
    const div = document.createElement('div');
    div.textContent = s;
    return div.innerHTML;
  }

  /** Формат даты: дд.мм.гггг */
  const formatDate = HRH.formatVacancyDate;
  if (!formatDate) {
    throw new Error("[HRHelper] shared/utils/date.js not loaded (formatVacancyDate missing)");
  }

  /** Нормализует ответ API candidate-info: бэкенд может вернуть данные в .data или в корне */
  function normalizeCandidatePayload(payload) {
    if (!payload) return null;
    const data = payload.data && typeof payload.data === 'object' && (payload.data.full_name != null || payload.data.phone != null || payload.data.email != null)
      ? payload.data
      : payload;
    return (data.full_name != null || data.phone != null || data.email != null || data.telegram != null || data.communication != null || (payload && payload.success)) ? data : null;
  }

  /** Получить список вакансий: status-multi или один элемент из candidate-info */
  function fetchStatusMulti(huntflowUrl) {
    const shared = HRH.fetchStatusMulti;
    if (!shared) {
      throw new Error("[HRHelper] shared/api/status.js not loaded (fetchStatusMulti missing)");
    }
    return shared({ huntflowUrl: huntflowUrl }).then((data) => (data && !data.error ? data : null));
  }

  function makeResumeWidgetDraggable(wrapper) {
    if (!wrapper) return;
    try {
      const saved = localStorage.getItem(FLOATING_POS_KEY);
      if (saved) {
        const obj = JSON.parse(saved);
        if (typeof obj.top === 'number' && typeof obj.left === 'number') {
          const margin = 8;
          let top = obj.top;
          let left = obj.left;
          const maxTop = window.innerHeight - wrapper.offsetHeight - margin;
          const maxLeft = window.innerWidth - wrapper.offsetWidth - margin;
          top = Math.min(Math.max(margin, top), Math.max(margin, maxTop));
          left = Math.min(Math.max(margin, left), Math.max(margin, maxLeft));
          wrapper.style.top = top + 'px';
          wrapper.style.left = left + 'px';
          wrapper.style.right = 'auto';
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
      document.addEventListener('mousemove', move);
      document.addEventListener('mouseup', stop);
      document.addEventListener('touchmove', move, { passive: false });
      document.addEventListener('touchend', stop);
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
      wrapper.style.top = top + 'px';
      wrapper.style.left = left + 'px';
      wrapper.style.right = 'auto';
    };
    const stop = () => {
      if (!drag) return;
      document.removeEventListener('mousemove', move);
      document.removeEventListener('mouseup', stop);
      document.removeEventListener('touchmove', move);
      document.removeEventListener('touchend', stop);
      try {
        const rect = wrapper.getBoundingClientRect();
        localStorage.setItem(FLOATING_POS_KEY, JSON.stringify({ top: rect.top, left: rect.left }));
      } catch (_) {}
      drag = null;
    };
    const header = wrapper.querySelector('.hrhelper-resume-floating-header');
    const handle = header || wrapper;
    handle.style.cursor = 'move';
    handle.addEventListener('mousedown', start);
    handle.addEventListener('touchstart', start, { passive: true });
  }

  var OPTIONS_THEME_KEY = HRH.OPTIONS_THEME_KEY;
  if (!OPTIONS_THEME_KEY) {
    throw new Error("[HRHelper] shared/constants.js not loaded (OPTIONS_THEME_KEY missing)");
  }

  function getResolvedResumeTheme() {
    return new Promise(function (resolve) {
      try {
        chrome.storage.sync.get({ [OPTIONS_THEME_KEY]: 'system' }, function (data) {
          var theme = data[OPTIONS_THEME_KEY] || 'system';
          if (theme === 'light') { resolve('light'); return; }
          if (theme === 'dark') { resolve('dark'); return; }
          var dark = typeof window !== 'undefined' && window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
          resolve(dark ? 'dark' : 'light');
        });
      } catch (_) {
        resolve('light');
      }
    });
  }

  function applyResumeFloatingTheme(wrapper) {
    if (!wrapper || !wrapper.classList) return;
    getResolvedResumeTheme().then(function (theme) {
      if (theme === 'dark') wrapper.classList.add('hrhelper-theme-dark');
      else wrapper.classList.remove('hrhelper-theme-dark');
    });
  }

  function injectResumeFloatingThemeStyles() {
    if (document.getElementById('hrhelper-resume-floating-theme')) return;
    const style = document.createElement('style');
    style.id = 'hrhelper-resume-floating-theme';
    style.textContent = `
      .hrhelper-resume-floating-widget { background: var(--hrhelper-bg) !important; color: var(--hrhelper-text) !important; }
      .hrhelper-resume-floating-widget .hrhelper-resume-floating-header { border-bottom-color: var(--hrhelper-border) !important; }
      .hrhelper-resume-floating-widget .hrhelper-resume-floating-header-title { color: var(--hrhelper-accent) !important; }
      .hrhelper-resume-floating-widget .hrhelper-resume-floating-body,
      .hrhelper-resume-floating-widget .hrhelper-resume-floating-body * { color: var(--hrhelper-text) !important; }
      .hrhelper-resume-floating-widget .hrhelper-resume-floating-edit,
      .hrhelper-resume-floating-widget .hrhelper-resume-floating-open-huntflow,
      .hrhelper-resume-floating-widget .hrhelper-resume-floating-add-vacancy,
      .hrhelper-resume-floating-widget .hrhelper-resume-floating-toggle,
      .hrhelper-resume-floating-widget .hrhelper-resume-floating-switch-service,
      .hrhelper-resume-floating-widget button[style*="border-radius:4px"] { background: var(--hrhelper-btn-bg) !important; color: var(--hrhelper-muted) !important; border-color: var(--hrhelper-border) !important; transition: background .15s ease, opacity .15s ease !important; }
      .hrhelper-resume-floating-widget .hrhelper-resume-floating-edit:hover,
      .hrhelper-resume-floating-widget .hrhelper-resume-floating-open-huntflow:hover,
      .hrhelper-resume-floating-widget .hrhelper-resume-floating-add-vacancy:hover,
      .hrhelper-resume-floating-widget .hrhelper-resume-floating-toggle:hover,
      .hrhelper-resume-floating-widget .hrhelper-resume-floating-switch-service:hover { background: var(--hrhelper-border) !important; }
      .hrhelper-resume-floating-widget .hrhelper-resume-floating-edit:active,
      .hrhelper-resume-floating-widget .hrhelper-resume-floating-open-huntflow:active,
      .hrhelper-resume-floating-widget .hrhelper-resume-floating-add-vacancy:active,
      .hrhelper-resume-floating-widget .hrhelper-resume-floating-toggle:active,
      .hrhelper-resume-floating-widget .hrhelper-resume-floating-switch-service:active { background: rgba(0,0,0,.15) !important; }
      .hrhelper-resume-floating-widget.hrhelper-theme-dark .hrhelper-resume-floating-edit:active,
      .hrhelper-resume-floating-widget.hrhelper-theme-dark .hrhelper-resume-floating-open-huntflow:active,
      .hrhelper-resume-floating-widget.hrhelper-theme-dark .hrhelper-resume-floating-add-vacancy:active,
      .hrhelper-resume-floating-widget.hrhelper-theme-dark .hrhelper-resume-floating-toggle:active,
      .hrhelper-resume-floating-widget.hrhelper-theme-dark .hrhelper-resume-floating-switch-service:active { background: rgba(255,255,255,.15) !important; }
      .hrhelper-resume-floating-widget input,
      .hrhelper-resume-floating-widget .hrhelper-link-form-input { background: var(--hrhelper-input-bg) !important; color: var(--hrhelper-text) !important; border-color: var(--hrhelper-border) !important; }
      .hrhelper-resume-floating-widget .hrhelper-link-form-desc { color: var(--hrhelper-muted) !important; }
      .hrhelper-resume-floating-widget .hrhelper-link-form-status { color: var(--hrhelper-text) !important; }
      .hrhelper-resume-floating-widget .hrhelper-resume-vacancy-title { color: var(--hrhelper-accent) !important; }
      :root { --hrhelper-bg: rgba(255,255,255,.98); --hrhelper-text: #212529; --hrhelper-muted: #6c757d; --hrhelper-border: rgba(0,0,0,.08); --hrhelper-accent: #0a66c2; --hrhelper-btn-bg: rgba(0,0,0,.05); --hrhelper-input-bg: #fff; --hrhelper-danger: #842029; --hrhelper-danger-bg: #f8d7da; --hrhelper-success: #0f5132; --hrhelper-success-bg: #d1e7dd; --hrhelper-card-active-bg: #e7f1ff; --hrhelper-card-active-border: #b6d4fe; --hrhelper-card-rejected-bg: #f8d7da; --hrhelper-card-rejected-border: #f1aeb5; --hrhelper-card-archived-bg: #e9ecef; --hrhelper-card-archived-border: #dee2e6; }
      .hrhelper-resume-floating-widget.hrhelper-theme-dark {
        --hrhelper-bg: #161b22; --hrhelper-text: #e6edf3; --hrhelper-muted: #8b949e; --hrhelper-border: rgba(255,255,255,.12); --hrhelper-accent: #58a6ff; --hrhelper-btn-bg: rgba(255,255,255,.08); --hrhelper-input-bg: #0d1117;
        --hrhelper-danger: #f85149; --hrhelper-danger-bg: rgba(248,81,73,.15); --hrhelper-success: #3fb950; --hrhelper-success-bg: rgba(63,185,80,.15);
        --hrhelper-card-active-bg: rgba(88,166,255,.08); --hrhelper-card-active-border: rgba(88,166,255,.35); --hrhelper-card-rejected-bg: rgba(248,81,73,.15); --hrhelper-card-rejected-border: rgba(248,81,73,.4); --hrhelper-card-archived-bg: #21262d; --hrhelper-card-archived-border: rgba(255,255,255,.12);
      }
      .hrhelper-resume-vacancy-card { padding: 6px 8px; border-radius: 8px; border: 1px solid var(--hrhelper-card-active-border); background: var(--hrhelper-card-active-bg); margin-bottom: 4px; font-size: 12px; display: flex; align-items: flex-start; gap: 8px; }
      .hrhelper-resume-vacancy-card-rejected { border-color: var(--hrhelper-card-rejected-border); background: var(--hrhelper-card-rejected-bg); }
      .hrhelper-resume-vacancy-card-archived { border-color: var(--hrhelper-card-archived-border); background: var(--hrhelper-card-archived-bg); }
      .hrhelper-resume-vacancy-card .hrhelper-resume-vacancy-line1 { margin-bottom: 2px; color: var(--hrhelper-text); font-weight: 600; }
      .hrhelper-resume-vacancy-card .hrhelper-resume-vacancy-line2 { margin-bottom: 2px; color: var(--hrhelper-muted); }
      .hrhelper-resume-vacancy-card .hrhelper-resume-vacancy-reason { margin-top: 4px; font-size: 11px; color: var(--hrhelper-danger); }
      .hrhelper-resume-vacancy-btn { width: 32px; height: 32px; padding: 0; border: 1px solid var(--hrhelper-card-active-border); border-radius: 6px; cursor: pointer; background: var(--hrhelper-card-active-bg); color: var(--hrhelper-accent); display: flex; align-items: center; justify-content: center; flex-shrink: 0; transition: background .15s ease, border-color .15s ease, color .15s ease; }
      .hrhelper-resume-vacancy-btn:hover { background: var(--hrhelper-border); }
      .hrhelper-resume-vacancy-btn.hrhelper-copy-btn-copied { background: var(--hrhelper-success-bg) !important; border-color: var(--hrhelper-success-border) !important; color: var(--hrhelper-success) !important; }
      .hrhelper-resume-floating-widget.hrhelper-theme-dark .hrhelper-resume-vacancy-btn { border-color: rgba(88,166,255,.4); background: rgba(88,166,255,.18); color: #58a6ff; }
      .hrhelper-resume-floating-widget.hrhelper-theme-dark .hrhelper-resume-vacancy-btn.hrhelper-copy-btn-copied { background: var(--hrhelper-success-bg) !important; border-color: var(--hrhelper-success-border) !important; color: var(--hrhelper-success) !important; }
      .hrhelper-resume-floating-widget.hrhelper-theme-dark .hrhelper-resume-vacancy-card { background: rgba(88,166,255,.08) !important; border-color: rgba(88,166,255,.35) !important; }
      .hrhelper-resume-floating-widget.hrhelper-theme-dark .hrhelper-resume-vacancy-card .hrhelper-resume-vacancy-line1 { color: #e6edf3 !important; }
      .hrhelper-resume-floating-widget.hrhelper-theme-dark .hrhelper-resume-vacancy-card .hrhelper-resume-vacancy-line2 { color: #8b949e !important; }
      .hrhelper-resume-floating-widget.hrhelper-theme-dark .hrhelper-resume-vacancy-btn { background: rgba(88,166,255,.18) !important; border-color: rgba(88,166,255,.4) !important; color: #58a6ff !important; }
      .hrhelper-resume-additional-wrap { margin-bottom: 4px; }
      .hrhelper-resume-additional-header { width: 100%; text-align: left; font-weight: 700; margin-bottom: 2px; font-size: 13px; background: none; border: none; padding: 2px 0; cursor: pointer; display: flex; align-items: center; gap: 6px; color: var(--hrhelper-muted); }
      .hrhelper-resume-additional-header .hrhelper-toggle-icon { font-size: 12px; }
      .hrhelper-resume-additional-body { margin-left: 0; font-size: 11px; margin-bottom: 4px; padding: 6px; background: var(--hrhelper-btn-bg); border-radius: 6px; }
      .hrhelper-resume-additional-body .hrhelper-additional-row { margin-bottom: 2px; }
      .hrhelper-resume-additional-body .hrhelper-additional-label { color: var(--hrhelper-muted); }
      .hrhelper-resume-additional-body .hrhelper-additional-value { color: var(--hrhelper-text); }
      .hrhelper-resume-contacts-title { font-weight: 700; margin-bottom: 4px; font-size: 13px; color: var(--hrhelper-muted); }
      .hrhelper-resume-contact-row { margin-bottom: 2px; }
      .hrhelper-resume-contact-row .hrhelper-contact-label { color: var(--hrhelper-muted); }
      .hrhelper-resume-contact-row .hrhelper-contact-value { color: var(--hrhelper-text); }
      .hrhelper-resume-labels-title { font-weight: 700; margin-bottom: 2px; font-size: 13px; color: var(--hrhelper-muted); }
      .hrhelper-resume-labels-wrap { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 4px; }
      .hrhelper-resume-tag { padding: 2px 8px; border-radius: 4px; font-size: 11px; background: var(--hrhelper-card-active-bg); color: var(--hrhelper-accent); border: 1px solid var(--hrhelper-card-active-border); }
      .hrhelper-resume-floating-widget.hrhelper-theme-dark .hrhelper-resume-tag { background: rgba(88,166,255,.08); color: #58a6ff; border-color: rgba(88,166,255,.35); }
      .hrhelper-resume-fallback { color: var(--hrhelper-muted); }
    `;
    (document.head || document.documentElement).appendChild(style);
  }

  try {
    chrome.storage.onChanged.addListener(function (changes, areaName) {
      if (areaName === 'sync' && changes[OPTIONS_THEME_KEY]) {
        var w = document.querySelector('[data-hrhelper-resume-floating="1"]');
        if (w) applyResumeFloatingTheme(w);
      }
    });
  } catch (_) {}

  function createResumeFloatingWidget() {
    injectResumeFloatingThemeStyles();
    const wrapper = document.createElement('div');
    wrapper.setAttribute(FLOATING_ATTR, '1');
    wrapper.className = 'hrhelper-resume-floating-widget';
    const baseShadow = '0 4px 16px rgba(0, 0, 0, 0.15), 0 0 0 1px rgba(0, 0, 0, 0.05)';
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
      box-shadow: ${baseShadow};
      padding: 16px;
      backdrop-filter: blur(8px);
      display: flex;
      flex-direction: column;
      overflow: hidden;
      overflow-x: hidden;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    `;
    wrapper.dataset.hrhelperBaseBoxShadow = baseShadow;
    const header = document.createElement('div');
    header.className = 'hrhelper-resume-floating-header';
    header.style.cssText = 'display:flex;align-items:center;justify-content:space-between;gap:8px;padding-bottom:8px;border-bottom:1px solid var(--hrhelper-border,rgba(0,0,0,.08));flex-shrink:0;';
    const titleWrap = document.createElement('div');
    titleWrap.style.cssText = 'display:flex;align-items:center;gap:6px;flex:1;min-width:0;';
    const titleIcon = document.createElement('img');
    titleIcon.className = 'hrhelper-title-icon';
    titleIcon.src = chrome.runtime.getURL('icons/icon-32.png');
    titleIcon.alt = '';
    titleIcon.width = 20;
    titleIcon.height = 20;
    titleIcon.style.cssText = 'flex-shrink:0;display:block;object-fit:contain;';
    titleIcon.onerror = function () {
      const svg = document.createElement('span');
      svg.innerHTML = '<svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor" style="flex-shrink:0;display:block;"><path d="M20 6h-4V4c0-1.11-.89-2-2-2h-4c-1.11 0-2 .89-2 2v2H4c-1.11 0-1.99.89-1.99 2L2 19c0 1.11.89 2 2 2h16c1.11 0 2-.89 2-2V8c0-1.11-.89-2-2-2zm-6 0h-4V4h4v2z"/></svg>';
      titleIcon.replaceWith(svg.firstElementChild || svg);
    };
    titleWrap.appendChild(titleIcon);
    const titleText = document.createElement('span');
    titleText.className = 'hrhelper-resume-floating-header-title';
    titleText.style.cssText = 'font-size:14px;font-weight:600;color:var(--hrhelper-accent,#0a66c2);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;';
    titleText.textContent = 'HR Helper';
    titleWrap.appendChild(titleText);
    header.appendChild(titleWrap);
    const _host = (window.location.hostname || '').toLowerCase();
    const _isRabota = _host === 'rabota.by' || _host === 'www.rabota.by' || _host.endsWith('.rabota.by');
    const _isHh = _host === 'hh.ru' || _host.endsWith('.hh.ru');
    const switchServiceBtn = document.createElement('button');
    switchServiceBtn.type = 'button';
    switchServiceBtn.className = 'hrhelper-resume-floating-switch-service';
    switchServiceBtn.title = _isRabota ? 'Открыть это резюме на hh.ru' : _isHh ? 'Открыть это резюме на rabota.by' : 'Другой сервис';
    switchServiceBtn.setAttribute('aria-label', switchServiceBtn.title);
    switchServiceBtn.style.cssText = 'width:24px;height:24px;border:none;background:var(--hrhelper-btn-bg,rgba(0,0,0,.05));border-radius:4px;cursor:pointer;color:var(--hrhelper-muted,#666);flex-shrink:0;padding:0;align-items:center;justify-content:center;display:flex;position:relative;';
    switchServiceBtn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M6.99 11L3 15l3.99 4v-3H14v-2H6.99v-3zM21 9l-3.99-4v3H10v2h7.01v3L21 9z"/></svg>';
    const targetSiteIcon = document.createElement('img');
    targetSiteIcon.className = 'hrhelper-resume-switch-service-icon';
    targetSiteIcon.src = _isRabota ? 'https://hh.ru/favicon.ico' : _isHh ? 'https://rabota.by/favicon.ico' : '';
    targetSiteIcon.alt = _isRabota ? 'hh.ru' : _isHh ? 'rabota.by' : '';
    targetSiteIcon.style.cssText = 'position:absolute;top:0;right:0;width:10px;height:10px;border-radius:2px;object-fit:contain;background:var(--hrhelper-bg,#fff);border:1px solid var(--hrhelper-border,rgba(0,0,0,.15));pointer-events:none;';
    if (targetSiteIcon.src) switchServiceBtn.appendChild(targetSiteIcon);
    switchServiceBtn.addEventListener('click', function () {
      const rid = (window.location.pathname || '').match(/\/resume\/([^/?#]+)/i);
      const resumeId = rid ? rid[1] : null;
      if (!resumeId) return;
      const host = (window.location.hostname || '').toLowerCase();
      const isRabota = host === 'rabota.by' || host === 'www.rabota.by' || host.endsWith('.rabota.by');
      const isHh = host === 'hh.ru' || host.endsWith('.hh.ru');
      if (isRabota) window.location.href = 'https://hh.ru/resume/' + resumeId;
      else if (isHh) window.location.href = 'https://rabota.by/resume/' + resumeId;
    });
    switchServiceBtn.addEventListener('mouseenter', () => { switchServiceBtn.style.background = 'var(--hrhelper-border,rgba(0,0,0,.1))'; });
    switchServiceBtn.addEventListener('mouseleave', () => { switchServiceBtn.style.background = 'var(--hrhelper-btn-bg,rgba(0,0,0,.05))'; });
    header.appendChild(switchServiceBtn);
    const actionGroup = document.createElement('div');
    actionGroup.className = 'hrhelper-resume-floating-action-group';
    actionGroup.style.cssText = 'display:flex;align-items:stretch;gap:0;flex-shrink:0;';
    const addVacancyBtn = document.createElement('button');
    addVacancyBtn.type = 'button';
    addVacancyBtn.className = 'hrhelper-resume-floating-add-vacancy';
    addVacancyBtn.title = 'Добавить кандидата на вакансию';
    addVacancyBtn.setAttribute('aria-label', 'Добавить на вакансию');
    addVacancyBtn.textContent = '+';
    addVacancyBtn.style.cssText = 'width:24px;height:24px;border:1px solid var(--hrhelper-border,rgba(0,0,0,.15));border-right:none;border-radius:4px 0 0 4px;background:var(--hrhelper-btn-bg,rgba(0,0,0,.05));cursor:pointer;color:var(--hrhelper-muted,#666);font-size:16px;line-height:1;padding:0;display:none;align-items:center;justify-content:center;';
    addVacancyBtn.addEventListener('mouseenter', () => { addVacancyBtn.style.background = 'var(--hrhelper-border,rgba(0,0,0,.1))'; });
    addVacancyBtn.addEventListener('mouseleave', () => { addVacancyBtn.style.background = 'var(--hrhelper-btn-bg,rgba(0,0,0,.05))'; });
    actionGroup.appendChild(addVacancyBtn);
    const openInHuntflowBtn = document.createElement('button');
    openInHuntflowBtn.type = 'button';
    openInHuntflowBtn.className = 'hrhelper-resume-floating-open-huntflow';
    openInHuntflowBtn.title = 'Открыть кандидата в Huntflow в новой вкладке';
    openInHuntflowBtn.setAttribute('aria-label', 'Открыть в Huntflow');
    openInHuntflowBtn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M19 19H5V5h7V3H5c-1.11 0-2 .9-2 2v14c0 1.1.89 2 2 2h14c1.1 0 2-.9 2-2v-7h-2v7zM14 3v2h3.59l-9.83 9.83 1.41 1.41L19 6.41V10h2V3h-7z"/></svg>';
    openInHuntflowBtn.style.cssText = 'width:24px;height:24px;border:1px solid var(--hrhelper-border,rgba(0,0,0,.15));border-radius:0;cursor:pointer;color:var(--hrhelper-muted,#666);flex-shrink:0;display:none;padding:0;align-items:center;justify-content:center;background:var(--hrhelper-btn-bg,rgba(0,0,0,.05));';
    openInHuntflowBtn.addEventListener('mouseenter', () => { openInHuntflowBtn.style.background = 'var(--hrhelper-border,rgba(0,0,0,.1))'; });
    openInHuntflowBtn.addEventListener('mouseleave', () => { openInHuntflowBtn.style.background = 'var(--hrhelper-btn-bg,rgba(0,0,0,.05))'; });
    actionGroup.appendChild(openInHuntflowBtn);
    const editBtn = document.createElement('button');
    editBtn.type = 'button';
    editBtn.className = 'hrhelper-resume-floating-edit';
    editBtn.title = 'Редактировать ссылку';
    editBtn.setAttribute('aria-label', 'Редактировать ссылку');
    editBtn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zM20.71 7.04c.39-.39.39-1.02 0-1.41l-2.34-2.34c-.39-.39-1.02-.39-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z"/></svg>';
    editBtn.style.cssText = 'width:24px;height:24px;border:1px solid var(--hrhelper-border,rgba(0,0,0,.15));border-radius:0 4px 4px 0;cursor:pointer;color:var(--hrhelper-muted,#666);flex-shrink:0;display:none;padding:0;align-items:center;justify-content:center;background:var(--hrhelper-btn-bg,rgba(0,0,0,.05));';
    editBtn.addEventListener('click', function () { if (this._onEditClick) this._onEditClick(); });
    editBtn.addEventListener('mouseenter', () => { editBtn.style.background = 'var(--hrhelper-border,rgba(0,0,0,.1))'; });
    editBtn.addEventListener('mouseleave', () => { editBtn.style.background = 'var(--hrhelper-btn-bg,rgba(0,0,0,.05))'; });
    actionGroup.appendChild(editBtn);
    header.appendChild(actionGroup);
    const toggleBtn = document.createElement('button');
    toggleBtn.type = 'button';
    toggleBtn.className = 'hrhelper-resume-floating-toggle';
    toggleBtn.title = 'Свернуть / развернуть';
    toggleBtn.setAttribute('aria-label', 'Свернуть');
    toggleBtn.style.cssText = 'width:24px;height:24px;border:none;background:var(--hrhelper-btn-bg,rgba(0,0,0,.05));border-radius:4px;cursor:pointer;color:var(--hrhelper-muted,#666);flex-shrink:0;padding:0;align-items:center;justify-content:center;display:flex;';
    toggleBtn.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path class="hrhelper-toggle-icon-path" d="M7.41 15.41L12 10.83l4.59 4.58L18 14l-6-6-6 6z"/></svg>';
    toggleBtn.addEventListener('mouseenter', () => { toggleBtn.style.background = 'var(--hrhelper-border,rgba(0,0,0,.1))'; });
    toggleBtn.addEventListener('mouseleave', () => { toggleBtn.style.background = 'var(--hrhelper-btn-bg,rgba(0,0,0,.05))'; });
    header.appendChild(toggleBtn);
    wrapper.appendChild(header);
    const body = document.createElement('div');
    body.className = 'hrhelper-resume-floating-body';
    body.style.cssText = 'display:flex;flex-direction:column;gap:4px;flex:1;min-height:0;min-width:0;overflow-y:auto;overflow-x:hidden;word-break:break-word;overflow-wrap:break-word;font-size:13px;line-height:1.4;color:var(--hrhelper-text,#333);';
    wrapper.appendChild(body);
    const isCollapsed = !!resumeFloatingUIState.widgetCollapsed;
    body.style.display = isCollapsed ? 'none' : 'flex';
    const togglePath = toggleBtn.querySelector('.hrhelper-toggle-icon-path');
    if (togglePath) togglePath.setAttribute('d', isCollapsed ? 'M7.41 8.59L12 13.17l4.59-4.58L18 10l-6 6-6-6z' : 'M7.41 15.41L12 10.83l4.59 4.58L18 14l-6-6-6 6z');
    toggleBtn.addEventListener('click', () => {
      const next = body.style.display === 'none';
      body.style.display = next ? 'flex' : 'none';
      const pathEl = toggleBtn.querySelector('.hrhelper-toggle-icon-path');
      if (pathEl) pathEl.setAttribute('d', next ? 'M7.41 15.41L12 10.83l4.59 4.58L18 14l-6-6-6 6z' : 'M7.41 8.59L12 13.17l4.59-4.58L18 10l-6 6-6-6z');
      toggleBtn.setAttribute('aria-label', next ? 'Свернуть' : 'Развернуть');
      toggleBtn.title = next ? 'Свернуть' : 'Развернуть';
      saveResumeFloatingUIState({ widgetCollapsed: !next });
    });
    const addVacancyDropdown = document.createElement('div');
    addVacancyDropdown.className = 'hrhelper-resume-add-vacancy-dropdown';
    addVacancyDropdown.style.cssText = 'display:none;position:absolute;top:100%;right:0;margin-top:4px;min-width:200px;max-width:280px;max-height:240px;overflow-y:auto;background:var(--hrhelper-bg,#fff);border:1px solid var(--hrhelper-border,rgba(0,0,0,.15));border-radius:8px;box-shadow:0 4px 12px rgba(0,0,0,.15);z-index:100000;';
    wrapper.appendChild(addVacancyDropdown);
    wrapper.dataset.addVacancyDropdown = '1';
    return { wrapper, body };
  }

  function normForDup(s) {
    return (s || '').toString().trim().toLowerCase().replace(/\s+/g, ' ');
  }
  function isDuplicateOf(value, existingList) {
    const v = normForDup(value);
    if (!v) return true;
    for (const [, existing] of existingList) {
      const e = normForDup(existing);
      if (!e) continue;
      if (v === e || v.indexOf(e) !== -1 || e.indexOf(v) !== -1) return true;
    }
    return false;
  }

  function categorizeVacanciesResume(vacancies) {
    const active = [];
    const rejected = [];
    const archived = [];
    const hired = [];
    for (const v of (vacancies || [])) {
      if (!v) continue;
      if (v.is_hired) hired.push(v);
      else if (v.status_type === 'rejected') rejected.push(v);
      else if (v.is_archived) archived.push(v);
      else active.push(v);
    }
    return { active, rejected, archived, hired };
  }

  function appendResumeCommentsBlock(fragment, vacancies, selectedId) {
    const vacancy = (vacancies || []).find((v) => v.vacancy_id === selectedId);
    const comments = vacancy?.comments || [];
    if (comments.length === 0) return;

    const isArchived = !!(vacancy && vacancy.is_archived);
    const vacancyNameForTitle = (vacancy.vacancy_name && String(vacancy.vacancy_name).trim()) || 'вакансии';
    const commentsTitle = isArchived
      ? 'Комментарии к ' + vacancyNameForTitle + ' (архив)'
      : 'Последние комментарии';
    const expanded = isArchived ? false : !!resumeFloatingUIState.commentsOpen;

    const block = document.createElement('div');
    block.className = 'hrhelper-resume-comments-block';
    block.style.cssText = 'margin-top:12px;padding-top:10px;border-top:1px solid var(--hrhelper-border,rgba(0,0,0,.1));';

    const toggleHeader = document.createElement('button');
    toggleHeader.type = 'button';
    toggleHeader.className = 'hrhelper-resume-comments-header';
    toggleHeader.style.cssText = 'width:100%;text-align:left;font-weight:700;font-size:12px;background:none;border:none;padding:4px 0;cursor:pointer;display:flex;align-items:center;gap:6px;color:var(--hrhelper-muted,#6c757d);';
    toggleHeader.innerHTML = '<span style="flex:1;">' + escapeHtml(commentsTitle) + '</span><span class="hrhelper-toggle-icon">' + (expanded ? '▼' : '▶') + '</span>';

    const commentsBody = document.createElement('div');
    commentsBody.className = 'hrhelper-resume-comments-body';
    commentsBody.style.cssText = 'font-size:11px;margin-top:6px;display:' + (expanded ? 'block' : 'none') + ';';

    comments.slice(0, 5).forEach((c) => {
      const row = document.createElement('div');
      row.style.cssText = 'margin-bottom:8px;padding:6px;background:var(--hrhelper-btn-bg,rgba(0,0,0,.03));border-radius:6px;';
      const meta = document.createElement('div');
      meta.style.cssText = 'display:flex;justify-content:space-between;gap:6px;margin-bottom:4px;';
      const author = document.createElement('span');
      author.style.cssText = 'font-weight:600;color:var(--hrhelper-accent,#0a66c2);';
      author.textContent = c.author || 'Система';
      const dateSpan = document.createElement('span');
      dateSpan.style.cssText = 'color:var(--hrhelper-muted,#6c757d);font-size:10px;';
      dateSpan.textContent = c.datetime ? formatDate(c.datetime) : '';
      meta.appendChild(author);
      meta.appendChild(dateSpan);
      row.appendChild(meta);
      const text = document.createElement('div');
      text.style.cssText = 'color:var(--hrhelper-text,#212529);word-break:break-word;';
      text.textContent = c.text || '';
      row.appendChild(text);
      commentsBody.appendChild(row);
    });

    toggleHeader.addEventListener('click', () => {
      const next = commentsBody.style.display === 'none';
      commentsBody.style.display = next ? 'block' : 'none';
      const icon = toggleHeader.querySelector('.hrhelper-toggle-icon');
      if (icon) icon.textContent = next ? '▼' : '▶';
      saveResumeFloatingUIState({ commentsOpen: next });
    });

    block.appendChild(toggleHeader);
    block.appendChild(commentsBody);
    fragment.appendChild(block);
  }

  function refreshResumeFloatingWidget() {
    const widget = document.querySelector(`[${FLOATING_ATTR}="1"]`);
    if (!widget) return;
    const bodyEl = widget.querySelector('.hrhelper-resume-floating-body');
    if (!bodyEl) return;
    bodyEl.innerHTML = '';
    const options = {
      huntflowUrl: widget._huntflowUrl || null,
      resumeUrl: widget._resumeUrl || getBaseUrl(),
      showActions: widget._showActions || false,
      portal: widget._portal || 'hh.ru',
      candidateName: (resumeCandidateInfoCache?.full_name || '').trim(),
      onAddedToVacancy: refreshResumeFloatingWidget,
    };
    bodyEl.appendChild(buildFloatingBodyContent(resumeCandidateInfoCache, resumeVacanciesCache, options));
    applyFloatingBorder(widget, computeFloatingBorderColorResume(resumeCandidateInfoCache, resumeVacanciesCache));
  }

  function buildFloatingBodyContent(candidateInfo, vacancies, options) {
    const info = candidateInfo || {};
    const fragment = document.createDocumentFragment();

    const opts = options || {};
    if (opts.showActions) {
      try {
        fragment.appendChild(buildActionButtons(opts));
        const spacer0 = document.createElement('div');
        spacer0.style.marginBottom = '4px';
        fragment.appendChild(spacer0);
      } catch (_) {}
    }

    const contactRows = [
      ['Телефон', info.phone],
      ['Email', info.email],
      ['Telegram', info.telegram],
      ['LinkedIn', info.linkedin],
    ].filter(([, v]) => v != null && v !== '');
    if (info.communication != null && String(info.communication).trim() !== '' && !isDuplicateOf(info.communication, contactRows)) {
      contactRows.push(['Где ведётся коммуникация', info.communication]);
    }
    if (contactRows.length > 0) {
      const contactsTitle = document.createElement('div');
      contactsTitle.className = 'hrhelper-resume-contacts-title';
      contactsTitle.textContent = 'Контакты';
      fragment.appendChild(contactsTitle);
      contactRows.forEach(([label, value]) => {
        const row = document.createElement('div');
        row.className = 'hrhelper-resume-contact-row';
        row.innerHTML = `<span class="hrhelper-contact-label">${escapeHtml(String(label))}:</span> <span class="hrhelper-contact-value">${escapeHtml(String(value))}</span>`;
        fragment.appendChild(row);
      });
      const spacer1 = document.createElement('div');
      spacer1.style.marginBottom = '4px';
      fragment.appendChild(spacer1);
    }

    const excludeCommLabel = /где ведется коммуникация|где ведётся коммуникация|communication|телефон|phone|email|telegram|linkedin/i;
    const excludeLevel = /^уровень$|^level$/i;
    const additionalFields = [
      ['Готовность к офису', info.office_readiness],
      ['Уровень', info.level],
    ].filter(([label, v]) => v != null && v !== '' && !excludeCommLabel.test(String(label)));
    if (info.extra_fields && typeof info.extra_fields === 'object') {
      Object.entries(info.extra_fields).forEach(([key, val]) => {
        if (val != null && val !== '' && !excludeCommLabel.test(String(key)) && !excludeLevel.test(String(key).trim())) {
          additionalFields.push([key, val]);
        }
      });
    }
    if (additionalFields.length > 0) {
      const addWrap = document.createElement('div');
      addWrap.className = 'hrhelper-resume-additional-wrap';
      const addHeader = document.createElement('button');
      addHeader.type = 'button';
      addHeader.className = 'hrhelper-resume-additional-header';
      addHeader.innerHTML = '<span style="flex:1;">Дополнительные поля</span><span class="hrhelper-toggle-icon">▼</span>';
      const addBody = document.createElement('div');
      addBody.className = 'hrhelper-resume-additional-body';
      additionalFields.forEach(([label, value]) => {
        const row = document.createElement('div');
        row.className = 'hrhelper-additional-row';
        row.innerHTML = `<span class="hrhelper-additional-label">${escapeHtml(String(label))}:</span> <span class="hrhelper-additional-value">${escapeHtml(String(value))}</span>`;
        addBody.appendChild(row);
      });
      const addCollapsed = !resumeFloatingUIState.additionalFieldsOpen;
      addBody.style.display = addCollapsed ? 'none' : 'block';
      const addIcon = addHeader.querySelector('.hrhelper-toggle-icon');
      if (addIcon) addIcon.textContent = addCollapsed ? '▶' : '▼';
      addHeader.addEventListener('click', () => {
        const next = addBody.style.display === 'none';
        addBody.style.display = next ? 'block' : 'none';
        if (addIcon) addIcon.textContent = next ? '▼' : '▶';
        saveResumeFloatingUIState({ additionalFieldsOpen: next });
      });
      addWrap.appendChild(addHeader);
      addWrap.appendChild(addBody);
      fragment.appendChild(addWrap);
    }
    if (info.labels && Array.isArray(info.labels) && info.labels.length > 0) {
      const normalizeLabelColor = HRH.normalizeLabelColor || ((v) => (v && typeof v === 'string' ? (v.indexOf('#') === 0 ? v : '#' + v.replace(/^#/, '')) : ''));
      const labelsTitle = document.createElement('div');
      labelsTitle.className = 'hrhelper-resume-labels-title';
      labelsTitle.textContent = 'Метки';
      fragment.appendChild(labelsTitle);
      const labelsWrap = document.createElement('div');
      labelsWrap.className = 'hrhelper-resume-labels-wrap';
      info.labels.forEach((lbl) => {
        const name = (typeof lbl === 'string' ? lbl : (lbl && (lbl.name || lbl.title)) || '').trim();
        if (!name) return;
        const tag = document.createElement('span');
        tag.className = 'hrhelper-resume-tag';
        tag.textContent = name;
        const rawColor = (lbl && typeof lbl === 'object' && (lbl.color || lbl.background_color || lbl.bg_color || lbl.border_color || lbl.hex)) || '';
        const color = rawColor ? normalizeLabelColor(String(rawColor)) : '';
        if (color) {
          tag.style.borderColor = color;
          tag.style.color = color;
        }
        labelsWrap.appendChild(tag);
      });
      fragment.appendChild(labelsWrap);
    }
    const items = vacancies || [];
    const selId = resumeSelectedVacancyId ?? resumeDefaultVacancyId;
    const categorized = categorizeVacanciesResume(items);
    const { active, rejected, archived } = categorized;

    function createVacancyCard(v, isSelected, categoryClass) {
      const name = v.vacancy_name || '—';
      const status = v.status_name || '—';
      const date = formatDate(v.last_change_at);
      const card = document.createElement('div');
      card.className = 'hrhelper-resume-vacancy-card' + (categoryClass ? ' ' + categoryClass : '');
      card.style.cursor = 'pointer';
      const cardBorderColor = computeBorderColorForVacancy(v);
      if (cardBorderColor) {
        card.style.borderColor = cardBorderColor;
      }
      if (isSelected) {
        card.style.boxShadow = '0 0 0 2px var(--hrhelper-accent, #0a66c2) inset';
      }
      const cardLeft = document.createElement('div');
      cardLeft.style.cssText = 'flex:1;min-width:0;';
      const line1 = document.createElement('div');
      line1.className = 'hrhelper-resume-vacancy-line1';
      line1.textContent = (isSelected ? '✓ ' : '') + name;
      cardLeft.appendChild(line1);
      const line2 = document.createElement('div');
      line2.className = 'hrhelper-resume-vacancy-line2';
      line2.textContent = date ? `${status} — ${date}` : status;
      cardLeft.appendChild(line2);
      if (v.status_type === 'rejected' && (v.rejection_reason_name || '').trim()) {
        const reasonLine = document.createElement('div');
        reasonLine.className = 'hrhelper-resume-vacancy-reason';
        reasonLine.textContent = (v.rejection_reason_name || '').trim();
        cardLeft.appendChild(reasonLine);
      }
      card.appendChild(cardLeft);
      if (v.appurl) {
        const copyBtn = document.createElement('button');
        copyBtn.type = 'button';
        copyBtn.className = 'hrhelper-resume-vacancy-btn';
        copyBtn.title = 'Копировать ссылку на Huntflow';
        copyBtn.setAttribute('aria-label', 'Копировать ссылку');
        copyBtn.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M16 1H4c-1.1 0-2 .9-2 2v14h2V3h12V1zm3 4H8c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h11c1.1 0 2-.9 2-2V7c0-1.1-.9-2-2-2zm0 16H8V7h11v14z"/></svg>';
        copyBtn.addEventListener('click', (e) => {
          e.stopPropagation();
          if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(v.appurl).then(() => {
              copyBtn.classList.add('hrhelper-copy-btn-copied');
              copyBtn.title = 'Скопировано';
              setTimeout(() => {
                copyBtn.classList.remove('hrhelper-copy-btn-copied');
                copyBtn.title = 'Копировать ссылку на Huntflow';
              }, 1500);
            });
          }
        });
        card.appendChild(copyBtn);
      }
      card.dataset.vacancyId = v.vacancy_id;
      card.addEventListener('click', () => {
        resumeSelectedVacancyId = v.vacancy_id;
        refreshResumeFloatingWidget();
      });
      return card;
    }

    if (active.length > 0) {
      const activeTitle = document.createElement('div');
      activeTitle.className = 'hrhelper-resume-vacancy-title';
      activeTitle.style.cssText = 'font-weight:700;margin-bottom:4px;font-size:13px;margin-top:8px;';
      activeTitle.textContent = 'Активные вакансии';
      fragment.appendChild(activeTitle);
      active.forEach((v) => {
        const isSelected = v.vacancy_id === selId;
        fragment.appendChild(createVacancyCard(v, isSelected, ''));
      });
    }
    if (rejected.length > 0) {
      const rejTitle = document.createElement('div');
      rejTitle.className = 'hrhelper-resume-vacancy-title';
      rejTitle.style.cssText = 'font-weight:700;margin-bottom:4px;font-size:13px;margin-top:8px;color:var(--hrhelper-danger,#842029);';
      rejTitle.textContent = '❌ Отказы';
      fragment.appendChild(rejTitle);
      rejected.forEach((v) => {
        const isSelected = v.vacancy_id === selId;
        fragment.appendChild(createVacancyCard(v, isSelected, 'hrhelper-resume-vacancy-card-rejected'));
      });
    }
    if (archived.length > 0) {
      const archTitle = document.createElement('div');
      archTitle.className = 'hrhelper-resume-vacancy-title';
      archTitle.style.cssText = 'font-weight:700;margin-bottom:4px;font-size:13px;margin-top:8px;';
      archTitle.textContent = 'Архивные вакансии';
      fragment.appendChild(archTitle);
      archived.forEach((v) => {
        const isSelected = v.vacancy_id === selId;
        fragment.appendChild(createVacancyCard(v, isSelected, 'hrhelper-resume-vacancy-card-archived'));
      });
    }

    appendResumeCommentsBlock(fragment, items, selId);
    const hasAny = contactRows.length > 0 || additionalFields.length > 0 || (info.labels && info.labels.length > 0) || items.length > 0;
    if (!hasAny) {
      const fallback = document.createElement('div');
      fallback.className = 'hrhelper-resume-fallback';
      fallback.textContent = 'Связано с Huntflow';
      fragment.appendChild(fallback);
    }
    return fragment;
  }

  function showActionError(container, message) {
    if (!container) return;
    const el = document.createElement('div');
    el.className = 'hrhelper-resume-action-error';
    el.textContent = (message || 'Ошибка').toString();
    container.appendChild(el);
  }

  async function showRejectForm(bar, options, inviteBtn, rejectBtn, buttonsRow) {
    bar.innerHTML = '';
    const loading = document.createElement('div');
    loading.textContent = 'Загрузка причин отказа...';
    loading.className = 'hrhelper-resume-action-loading';
    bar.appendChild(loading);

    try {
      const qp = new URLSearchParams({ huntflow_url: options.huntflowUrl });
      const res = await apiFetch(`/api/v1/huntflow/linkedin-applicants/status-options?${qp.toString()}`, { method: 'GET' });
      const data = await res.json().catch(() => null);
      if (!res.ok || !data?.success) {
        loading.textContent = data?.message || 'Не удалось загрузить причины';
        loading.classList.add('is-error');
        return;
      }

      const rejectionReasons = data.rejection_reasons || [];
      const rejectionStatuses = (data.statuses || []).filter((s) =>
        s?.type?.toLowerCase?.() === 'rejected' || (s?.name || '').toLowerCase().includes('отказ')
      );
      const defaultRejectionStatusId = rejectionStatuses[0]?.id || null;

      bar.innerHTML = '';

      const reasonLabel = document.createElement('div');
      reasonLabel.className = 'hrhelper-resume-action-label';
      reasonLabel.textContent = 'Причина отказа:';
      bar.appendChild(reasonLabel);

      const reasonSelect = document.createElement('select');
      reasonSelect.className = 'hrhelper-resume-action-select';
      reasonSelect.innerHTML = '<option value="">Выберите причину</option>';
      rejectionReasons.forEach((r) => {
        const opt = document.createElement('option');
        opt.value = r.id;
        opt.textContent = r.name;
        reasonSelect.appendChild(opt);
      });
      bar.appendChild(reasonSelect);

      const commentLabel = document.createElement('div');
      commentLabel.className = 'hrhelper-resume-action-label';
      commentLabel.textContent = 'Комментарий (необязательно):';
      bar.appendChild(commentLabel);

      const commentArea = document.createElement('textarea');
      commentArea.className = 'hrhelper-resume-action-textarea';
      commentArea.placeholder = 'Дополнительная информация...';
      commentArea.rows = 2;
      bar.appendChild(commentArea);

      const btnRow = document.createElement('div');
      btnRow.className = 'hrhelper-resume-action-row';

      const confirmBtn = document.createElement('button');
      confirmBtn.type = 'button';
      confirmBtn.className = 'hrhelper-resume-action-btn hrhelper-resume-action-btn--reject';
      confirmBtn.textContent = 'Отправить отказ';

      const cancelBtn = document.createElement('button');
      cancelBtn.type = 'button';
      cancelBtn.className = 'hrhelper-resume-action-btn hrhelper-resume-action-btn--secondary';
      cancelBtn.textContent = 'Отмена';

      btnRow.appendChild(confirmBtn);
      btnRow.appendChild(cancelBtn);
      bar.appendChild(btnRow);

      cancelBtn.addEventListener('click', () => {
        bar.innerHTML = '';
        if (buttonsRow && inviteBtn && rejectBtn) {
          buttonsRow.innerHTML = '';
          buttonsRow.appendChild(inviteBtn);
          buttonsRow.appendChild(rejectBtn);
          bar.appendChild(buttonsRow);
        } else {
          bar.appendChild(inviteBtn);
          bar.appendChild(rejectBtn);
        }
      });

      confirmBtn.addEventListener('click', async () => {
        if (confirmBtn.disabled) return;
        const reasonId = reasonSelect.value ? parseInt(reasonSelect.value, 10) : null;
        if (!reasonId) {
          showActionError(bar, 'Выберите причину отказа.');
          return;
        }
        confirmBtn.disabled = true;
        cancelBtn.disabled = true;
        const old = confirmBtn.textContent;
        confirmBtn.textContent = 'Отправка...';
        try {
          const res2 = await apiFetch('/api/v1/hh/reject', {
            method: 'POST',
            body: JSON.stringify({
              resume_url: options.resumeUrl,
              huntflow_url: options.huntflowUrl,
              portal: options.portal,
              candidate_name: options.candidateName || '',
              status_id: defaultRejectionStatusId,
              rejection_reason_id: reasonId,
              comment: (commentArea.value || '').trim(),
              message_template: 'default_rejection',
            }),
          });
          const data2 = await res2.json().catch(() => null);
          if (res2.ok && data2?.success) {
            bar.innerHTML = '';
            const badge = document.createElement('div');
            badge.className = 'hrhelper-resume-action-badge hrhelper-resume-action-badge--success';
            const hhMsg = (data2.hh_status || '').trim();
            const hfMsg = (data2.huntflow_status || '').trim();
            const hfOk = /обновлён|успешно|отправлен/i.test(hfMsg || '');
            const hhNotFound = /не найден|не обновлён/i.test(hhMsg || '');
            let text = '✓ Отказ отправлен';
            if (hfOk && hhNotFound) {
              text = '✓ Отказ зафиксирован в Huntflow. В HH отклик не найден — обновите отклики по вакансии в приложении HR Helper.';
            } else if (hfOk) {
              text = '✓ Отказ зафиксирован в Huntflow' + (hhMsg ? '. HH: ' + hhMsg : '');
            } else if (hhMsg || hfMsg) {
              text = '✓ Отказ: ' + [hhMsg, hfMsg].filter(Boolean).join('. ');
            }
            badge.textContent = text;
            bar.appendChild(badge);
          } else {
            showActionError(bar, data2?.message || 'Не удалось отправить отказ');
            confirmBtn.disabled = false;
            cancelBtn.disabled = false;
            confirmBtn.textContent = old;
          }
        } catch (e) {
          showActionError(bar, e.message || 'Ошибка сети');
          confirmBtn.disabled = false;
          cancelBtn.disabled = false;
          confirmBtn.textContent = old;
        }
      });
    } catch (e) {
      bar.innerHTML = '';
      showActionError(bar, e.message || 'Ошибка загрузки');
    }
  }

  function buildActionButtons(options) {
    const bar = document.createElement('div');
    bar.className = 'hrhelper-resume-action-bar';

    const inviteBtn = document.createElement('button');
    inviteBtn.type = 'button';
    inviteBtn.className = 'hrhelper-resume-action-btn hrhelper-resume-action-btn--invite';
    inviteBtn.innerHTML = '<span>Пригласить</span>';

    const rejectBtn = document.createElement('button');
    rejectBtn.type = 'button';
    rejectBtn.className = 'hrhelper-resume-action-btn hrhelper-resume-action-btn--reject';
    rejectBtn.innerHTML = '<span>Отказать</span>';

    const buttonsRow = document.createElement('div');
    buttonsRow.className = 'hrhelper-resume-action-buttons-row';
    buttonsRow.style.cssText = 'display:flex;flex-direction:row;gap:8px;align-items:stretch;';
    buttonsRow.appendChild(inviteBtn);
    buttonsRow.appendChild(rejectBtn);

    inviteBtn.addEventListener('click', async () => {
      if (inviteBtn.disabled) return;
      inviteBtn.disabled = true;
      rejectBtn.disabled = true;
      const originalHTML = inviteBtn.innerHTML;
      inviteBtn.textContent = 'Отправка...';
      try {
        const res = await apiFetch('/api/v1/hh/invite', {
          method: 'POST',
          body: JSON.stringify({
            resume_url: options.resumeUrl,
            huntflow_url: options.huntflowUrl,
            portal: options.portal,
            candidate_name: options.candidateName || '',
            message_template: 'default_invite',
          }),
        });
        const data = await res.json().catch(() => null);
        if (res.ok && data?.success) {
          bar.innerHTML = '';
          const badge = document.createElement('div');
          badge.className = 'hrhelper-resume-action-badge hrhelper-resume-action-badge--success';
          const hhMsg = (data.hh_status || '').trim();
          const hfMsg = (data.huntflow_status || '').trim();
          const hfOk = /обновлён|успешно|отправлен/i.test(hfMsg || '');
          const hhNotFound = /не найден|не обновлён/i.test(hhMsg || '');
          let text = '✓ Приглашение отправлено';
          if (hfOk && hhNotFound) {
            text = '✓ Приглашение зафиксировано в Huntflow. В HH отклик не найден — обновите отклики по вакансии в приложении HR Helper.';
          } else if (hfOk) {
            text = '✓ Приглашение зафиксировано в Huntflow' + (hhMsg ? '. HH: ' + hhMsg : '');
          } else if (hhMsg || hfMsg) {
            text = '✓ Приглашение: ' + [hhMsg, hfMsg].filter(Boolean).join('. ');
          }
          badge.textContent = text;
          bar.appendChild(badge);
        } else {
          showActionError(bar, data?.message || 'Не удалось отправить приглашение');
          inviteBtn.disabled = false;
          rejectBtn.disabled = false;
          inviteBtn.innerHTML = originalHTML;
        }
      } catch (e) {
        showActionError(bar, (e && e.message) || 'Ошибка сети');
        inviteBtn.disabled = false;
        rejectBtn.disabled = false;
        inviteBtn.innerHTML = originalHTML;
      }
    });

    rejectBtn.addEventListener('click', () => {
      showRejectForm(bar, options, inviteBtn, rejectBtn, buttonsRow);
    });

    bar.appendChild(buttonsRow);
    return bar;
  }

  /** Форма ввода/редактирования ссылки Huntflow: поле + квадратная кнопка «Сохранить» в один ряд */
  function buildLinkForm(initialUrl, onSave) {
    const wrap = document.createElement('div');
    wrap.className = 'hrhelper-link-form';
    wrap.style.cssText = 'display:flex;flex-direction:column;gap:8px;';
    const desc = document.createElement('div');
    desc.className = 'hrhelper-link-form-desc';
    desc.style.cssText = 'color:var(--hrhelper-muted,#666);font-size:13px;';
    desc.textContent = initialUrl ? 'Изменить ссылку на кандидата в Huntflow:' : 'Ссылка на кандидата в Huntflow не сохранена. Вставьте ссылку и нажмите «Сохранить».';
    wrap.appendChild(desc);
    const statusEl = document.createElement('div');
    statusEl.className = 'hrhelper-link-form-status';
    statusEl.style.cssText = 'font-size:12px;min-height:18px;color:var(--hrhelper-text);';
    const inputRow = document.createElement('div');
    inputRow.style.cssText = 'display:flex;align-items:center;gap:8px;';
    const input = document.createElement('input');
    input.type = 'text';
    input.className = 'hrhelper-link-form-input';
    input.placeholder = 'https://huntflow.ru/my/...';
    input.value = initialUrl || '';
    input.style.cssText = 'flex:1;min-width:0;padding:8px 10px;border:1px solid var(--hrhelper-border,rgba(0,0,0,.2));border-radius:6px;font-size:13px;box-sizing:border-box;';
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        saveBtn.click();
      }
      if (e.key === 'Escape' && wrap._onEscape) {
        e.preventDefault();
        wrap._onEscape();
      }
    });
    const saveBtn = document.createElement('button');
    saveBtn.type = 'button';
    saveBtn.title = 'Сохранить';
    saveBtn.setAttribute('aria-label', 'Сохранить');
    saveBtn.innerHTML = '<svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg>';
    saveBtn.style.cssText = 'width:36px;height:36px;flex-shrink:0;padding:0;border:none;border-radius:6px;cursor:pointer;background:var(--hrhelper-accent,#0a66c2);color:#fff;display:flex;align-items:center;justify-content:center;';
    saveBtn.addEventListener('click', async () => {
      const raw = (input.value || '').trim();
      const url = normalizeHuntflowUrl(raw);
      if (!url) {
        statusEl.textContent = 'Введите ссылку на Huntflow (например https://huntflow.ru/my/...).';
        statusEl.style.color = 'var(--hrhelper-danger,#842029)';
        return;
      }
      statusEl.textContent = 'Сохранение…';
      statusEl.style.color = 'var(--hrhelper-muted,#666)';
      saveBtn.disabled = true;
      try {
        const result = await onSave(url);
        if (result && result.success) {
          statusEl.textContent = 'Ссылка сохранена.';
          statusEl.style.color = 'var(--hrhelper-success,#0f5132)';
        } else {
          statusEl.textContent = (result && result.message) || 'Ошибка сохранения';
          statusEl.style.color = 'var(--hrhelper-danger,#842029)';
        }
      } catch (e) {
        statusEl.textContent = e.message || 'Ошибка сети';
        statusEl.style.color = 'var(--hrhelper-danger,#842029)';
      }
      saveBtn.disabled = false;
    });
    inputRow.appendChild(input);
    inputRow.appendChild(saveBtn);
    wrap.appendChild(inputRow);
    wrap.appendChild(statusEl);
    return wrap;
  }

  function showFloatingWidget(candidateInfo, vacancies, options) {
    resumeCandidateInfoCache = candidateInfo;
    resumeVacanciesCache = vacancies || [];
    if (resumeVacanciesCache.length > 0 && resumeDefaultVacancyId == null) {
      const categorized = categorizeVacanciesResume(resumeVacanciesCache);
      const firstActive = categorized.active[0];
      const firstRejected = categorized.rejected[0];
      const firstArchived = categorized.archived[0];
      resumeDefaultVacancyId = (firstActive && firstActive.vacancy_id) || (firstRejected && firstRejected.vacancy_id) || (firstArchived && firstArchived.vacancy_id) || null;
    }

    let widget = document.querySelector(`[${FLOATING_ATTR}="1"]`);
    if (!widget) {
      const { wrapper, body } = createResumeFloatingWidget();
      widget = wrapper;
      document.body.appendChild(widget);
      applyResumeFloatingTheme(widget);
      applyResumeFloatingTheme(widget);
      makeResumeWidgetDraggable(widget);
    }
    widget._huntflowUrl = options?.huntflowUrl || null;
    widget._resumeUrl = options?.resumeUrl || getBaseUrl();
    widget._showActions = options?.showActions || false;
    widget._portal = options?.portal || 'hh.ru';
    applyFloatingBorder(widget, computeFloatingBorderColorResume(candidateInfo, vacancies));
    const titleIcon = widget.querySelector('.hrhelper-title-icon');
    if (titleIcon) {
      const isBlacklist = hasBlacklistLabel(candidateInfo);
      titleIcon.src = isBlacklist ? chrome.runtime.getURL('icons/dark-label.png') : chrome.runtime.getURL('icons/icon-32.png');
      const size = isBlacklist ? 30 : 20;
      titleIcon.width = size;
      titleIcon.height = size;
    }
    const titleEl = widget.querySelector('.hrhelper-resume-floating-header-title');
    if (titleEl) titleEl.textContent = (candidateInfo && candidateInfo.full_name) ? candidateInfo.full_name : 'HR Helper';
    const actionGroup = widget.querySelector('.hrhelper-resume-floating-action-group');
    const addVacancyBtn = widget.querySelector('.hrhelper-resume-floating-add-vacancy');
    const addVacancyDropdown = widget.querySelector('.hrhelper-resume-add-vacancy-dropdown');
    if (addVacancyBtn && addVacancyDropdown && options && options.huntflowUrl) {
      addVacancyBtn.style.display = 'flex';
      addVacancyBtn._huntflowUrl = options.huntflowUrl;
      addVacancyBtn.onclick = async function () {
        const huntflowUrl = this._huntflowUrl;
        if (!huntflowUrl) return;
        const drop = addVacancyDropdown;
        if (drop.style.display === 'block') {
          drop.style.display = 'none';
          if (drop.parentNode === document.body && widget) widget.appendChild(drop);
          return;
        }
        if (drop.parentNode !== document.body) document.body.appendChild(drop);
        const rect = addVacancyBtn.getBoundingClientRect();
        drop.style.position = 'fixed';
        drop.style.top = (rect.bottom + 4) + 'px';
        drop.style.left = rect.left + 'px';
        drop.style.minWidth = '200px';
        drop.style.maxWidth = '280px';
        drop.style.display = 'block';
        drop.innerHTML = '<div style="padding:10px 12px;color:var(--hrhelper-muted,#666);font-size:12px;">Загрузка…</div>';
        const closeDrop = () => {
          drop.style.display = 'none';
          document.removeEventListener('click', h);
          if (widget && drop.parentNode === document.body) widget.appendChild(drop);
        };
        const h = (ev) => {
          if (!drop.contains(ev.target) && !addVacancyBtn.contains(ev.target)) closeDrop();
        };
        setTimeout(() => document.addEventListener('click', h), 0);
        try {
          const qp = new URLSearchParams({ huntflow_url: huntflowUrl });
          const resumeUrl = (options && options.resumeUrl) ? (options.resumeUrl || '').trim() : '';
          if (resumeUrl) qp.set('resume_url', resumeUrl);
          const res = await apiFetch('/api/v1/huntflow/linkedin-applicants/available-vacancies/?' + qp.toString(), { method: 'GET' });
          const data = await res.json().catch(() => null);
          if (!res.ok || !data || !data.success) {
            drop.innerHTML = '<div style="padding:10px 12px;color:var(--hrhelper-danger,#842029);font-size:12px;">' + (data && data.message ? escapeHtml(data.message) : 'Ошибка загрузки') + '</div>';
            return;
          }
          const items = data.items || [];
          if (items.length === 0) {
            drop.innerHTML = '<div style="padding:10px 12px;color:var(--hrhelper-muted,#666);font-size:12px;">Нет доступных вакансий</div>';
            return;
          }
          drop.innerHTML = '';
          items.forEach((v) => {
            const el = document.createElement('div');
            el.style.cssText = 'padding:8px 12px;cursor:pointer;border-bottom:1px solid var(--hrhelper-border,rgba(0,0,0,.06));font-size:13px;';
            el.textContent = v.vacancy_name || 'Вакансия #' + (v.vacancy_id || '');
            el.addEventListener('click', async (ev) => {
              ev.stopPropagation();
              closeDrop();
              const result = await addToVacancyResume(huntflowUrl, v.vacancy_id, options && options.resumeUrl);
              if (result && options.onAddedToVacancy) options.onAddedToVacancy();
            });
            el.addEventListener('mouseenter', () => { el.style.background = 'var(--hrhelper-btn-bg,rgba(0,0,0,.06))'; });
            el.addEventListener('mouseleave', () => { el.style.background = ''; });
            drop.appendChild(el);
          });
        } catch (_) {
          drop.innerHTML = '<div style="padding:10px 12px;color:var(--hrhelper-danger,#842029);font-size:12px;">Ошибка загрузки</div>';
        }
      };
    } else if (addVacancyBtn) {
      addVacancyBtn.style.display = 'none';
      addVacancyBtn.onclick = null;
    }
    const openInHuntflowBtn = widget.querySelector('.hrhelper-resume-floating-open-huntflow');
    if (openInHuntflowBtn && options && options.huntflowUrl) {
      openInHuntflowBtn.style.display = 'flex';
      openInHuntflowBtn._huntflowUrl = options.huntflowUrl;
      openInHuntflowBtn.onclick = function () {
        const url = this._huntflowUrl;
        if (url) window.open(url, '_blank', 'noopener,noreferrer');
      };
    } else if (openInHuntflowBtn) {
      openInHuntflowBtn.style.display = 'none';
      openInHuntflowBtn.onclick = null;
    }
    const editBtn = widget.querySelector('.hrhelper-resume-floating-edit');
    if (editBtn) {
      const onEdit = options && options.onEditClick;
      if (typeof onEdit === 'function') {
        editBtn._onEditClick = onEdit;
        editBtn.style.display = 'flex';
      } else {
        editBtn._onEditClick = null;
        editBtn.style.display = 'none';
      }
    }
    if (actionGroup) {
      const visible = [addVacancyBtn, openInHuntflowBtn, editBtn].filter(function (b) { return b && b.style.display === 'flex'; });
      [addVacancyBtn, openInHuntflowBtn, editBtn].forEach(function (b) {
        if (!b) return;
        b.style.borderRadius = '';
        b.style.borderRight = '1px solid var(--hrhelper-border,rgba(0,0,0,.15))';
      });
      visible.forEach(function (b, i) {
        if (visible.length === 1) b.style.borderRadius = '4px';
        else if (i === 0) b.style.borderRadius = '4px 0 0 4px';
        else if (i === visible.length - 1) b.style.borderRadius = '0 4px 4px 0';
        else b.style.borderRadius = '0';
        if (i < visible.length - 1) b.style.borderRight = 'none';
      });
    }
    const bodyEl = widget.querySelector('.hrhelper-resume-floating-body');
    if (!bodyEl) return;
    bodyEl.innerHTML = '';
    bodyEl.appendChild(buildFloatingBodyContent(candidateInfo, vacancies, options || {}));
  }

  function hideFloatingWidget() {
    const widget = document.querySelector(`[${FLOATING_ATTR}="1"]`);
    if (widget && widget.parentNode) widget.parentNode.removeChild(widget);
  }

  /** Legacy: построить один элемент вакансии из candidate-info (для обратной совместимости) */
  function buildVacancyFromCandidateInfo(data, opts) {
    const v = {
      vacancy_name: opts?.vacancy_name ?? data?.vacancy_name ?? '—',
      status_name: opts?.status_name ?? data?.status_name ?? null,
      last_change_at: null,
      status_type: (opts?.status_name || data?.status_name) && /отказ|reject|trash/i.test(String(opts?.status_name || data?.status_name)) ? 'rejected' : 'active',
      rejection_reason_name: opts?.rejection_reason_name ?? data?.rejection_reason_name ?? null,
    };
    return v;
  }

  function injectStyles() {
    if (document.getElementById('hrhelper-resume-styles')) return;
    const style = document.createElement('style');
    style.id = 'hrhelper-resume-styles';
    style.textContent = `
      .hrhelper-resume-action-bar {
        display: flex;
        flex-direction: column;
        align-items: stretch;
        gap: 8px;
        margin-top: 8px;
      }
      .hrhelper-resume-action-buttons-row {
        display: flex;
        flex-direction: row;
        gap: 8px;
        align-items: stretch;
      }
      .hrhelper-resume-action-buttons-row .hrhelper-resume-action-btn {
        flex: 1;
        width: auto;
        min-width: 0;
        max-width: 320px;
      }
      .hrhelper-resume-action-btn {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        gap: 6px;
        border: 1px solid var(--hrhelper-border, rgba(0,0,0,.2));
        border-radius: 8px;
        padding: 7px 10px;
        font-size: 12px;
        font-weight: 700;
        cursor: pointer;
        background: var(--hrhelper-bg, #fff);
        color: var(--hrhelper-text, #212529);
        min-height: 32px;
        width: 100%;
        box-sizing: border-box;
        white-space: nowrap;
        writing-mode: horizontal-tb;
      }
      .hrhelper-resume-action-btn:disabled {
        opacity: .65;
        cursor: not-allowed;
      }
      .hrhelper-resume-action-btn--invite {
        background: rgba(25, 135, 84, .12);
        border-color: rgba(25, 135, 84, .35);
        color: #198754;
      }
      .hrhelper-resume-action-btn--reject {
        background: rgba(220, 53, 69, .10);
        border-color: rgba(220, 53, 69, .35);
        color: #dc3545;
      }
      .hrhelper-resume-action-btn--secondary {
        background: rgba(0,0,0,.04);
        border-color: rgba(0,0,0,.18);
        color: #495057;
      }
      .hrhelper-resume-action-badge {
        width: 100%;
        padding: 8px 10px;
        border-radius: 8px;
        font-size: 12px;
        font-weight: 700;
        text-align: center;
        border: 1px solid transparent;
      }
      .hrhelper-resume-action-badge--success {
        background: rgba(25, 135, 84, .12);
        border-color: rgba(25, 135, 84, .35);
        color: #198754;
      }
      .hrhelper-resume-action-error {
        margin-top: 8px;
        padding: 8px 10px;
        border-radius: 8px;
        font-size: 12px;
        background: rgba(220, 53, 69, .10);
        border: 1px solid rgba(220, 53, 69, .35);
        color: #842029;
      }
      .hrhelper-resume-action-loading {
        font-size: 12px;
        color: var(--hrhelper-muted, #666);
        padding: 6px 2px;
      }
      .hrhelper-resume-action-loading.is-error { color: #842029; }
      .hrhelper-resume-action-label {
        font-size: 12px;
        font-weight: 700;
        margin: 6px 0 4px;
      }
      .hrhelper-resume-action-select,
      .hrhelper-resume-action-textarea {
        width: 100%;
        border: 1px solid var(--hrhelper-border, rgba(0,0,0,.2));
        border-radius: 8px;
        padding: 7px 10px;
        font-size: 12px;
        background: var(--hrhelper-bg, #fff);
        color: var(--hrhelper-text, #212529);
        box-sizing: border-box;
      }
      .hrhelper-resume-action-textarea { resize: vertical; }
      .hrhelper-resume-action-row {
        display: flex;
        gap: 8px;
        margin-top: 8px;
        align-items: center;
        justify-content: space-between;
      }
    `;
    (document.head || document.documentElement).appendChild(style);
  }

  function processLink(link) {
    if (link.getAttribute(DATA_ATTR) === 'processed') return;
    const url = getHuntflowUrl(link);
    if (!url) return;
    link.setAttribute(DATA_ATTR, 'processed');

    const candidatePath = `/api/v1/huntflow/linkedin-applicants/candidate-info/?huntflow_url=${encodeURIComponent(url)}`;
    Promise.all([
      apiFetch(candidatePath).then((r) => r.json().catch(() => null)),
      fetchStatusMulti(url),
    ]).then(([candidateData, multiData]) => {
      const info = normalizeCandidatePayload(candidateData);
      const vacancies = multiData && multiData.success && multiData.items && multiData.items.length > 0
        ? multiData.items
        : (info ? [buildVacancyFromCandidateInfo(info)] : []);
      const candidateInfo = info ? {
        full_name: info.full_name,
        phone: info.phone,
        email: info.email,
        telegram: info.telegram,
        linkedin: info.linkedin,
        communication: info.communication,
        office_readiness: info.office_readiness,
        level: info.level,
        extra_fields: info.extra_fields,
        labels: info.labels,
      } : null;
      const hasContent = candidateInfo && (candidateInfo.full_name || candidateInfo.phone || candidateInfo.email || candidateInfo.telegram || candidateInfo.communication) || (vacancies && vacancies.length > 0);
      if (hasContent) {
        chrome.storage.local.get({ [RESUME_FLOATING_HIDDEN_KEY]: false }, (data) => {
          if (!data[RESUME_FLOATING_HIDDEN_KEY]) showFloatingWidget(candidateInfo, vacancies);
        });
      }
    }).catch(() => {});
  }

  /** Собирает все ссылки, у которых getHuntflowUrl находит URL (в href или в тексте) */
  function findHuntflowLinks() {
    const found = [];
    document.querySelectorAll('a').forEach((link) => {
      if (link.getAttribute(DATA_ATTR) === 'processed') return;
      if (getHuntflowUrl(link)) found.push(link);
    });
    return found;
  }

  /** Base URL страницы (до ? и #) */
  function getBaseUrl() {
    const u = window.location.href;
    return u.split('?')[0].split('#')[0];
  }

  /** Полный URL для проверки actions-availability (с query), чтобы бэкенд мог извлечь resumeId на rabota.by */
  function getResumeUrlForActions() {
    return (window.location.href || '').split('#')[0];
  }

  /** ID резюме из пути /resume/{id} — один ключ для всех доменов (hh.ru, rabota.by, gomel.rabota.by) */
  function getResumeId() {
    const m = (window.location.pathname || '').match(/\/resume\/([^/?#]+)/i);
    return m ? m[1] : null;
  }

  /** Проверка: является ли текущая страница откликом (из списка откликов на вакансию)
   *  Используется для определения, показывать ли кнопки "Пригласить" / "Отказать"
   *  Плавающее окно показывается всегда, кнопки — только для откликов */
  function isResponsePage() {
    const urlParams = new URLSearchParams(window.location.search);
    const hhtmFrom = urlParams.get('hhtmFrom');
    return hhtmFrom === 'employer_vacancy_responses';
  }

  /** Сохранить состояние в storage (ключ = resume_id) */
  function saveStateToStorage(state) {
    const key = getResumeId();
    if (!key) return;
    chrome.storage.local.get(RESUME_STORAGE_KEY, (data) => {
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
      chrome.storage.local.set({ [RESUME_STORAGE_KEY]: map });
    });
  }

  /** Получить сохранённое состояние для текущей страницы резюме (по resume_id) */
  function getStoredStateForPage() {
    return new Promise((resolve) => {
      try {
        const rid = getResumeId();
        if (!rid) {
          resolve(null);
          return;
        }
        chrome.storage.local.get(RESUME_STORAGE_KEY, (data) => {
          if (chrome.runtime.lastError) {
            resolve(null);
            return;
          }
          const map = data[RESUME_STORAGE_KEY];
          const state = map && map[rid] && map[rid].huntflowUrl ? map[rid] : null;
          resolve(state);
        });
      } catch (_) {
        resolve(null);
      }
    });
  }

  /** Показать плавающее окно с данными Huntflow (по сохранённой связи или по API resume-links) */
  function injectSavedLinkBlock() {
    document.querySelectorAll(`[${BY_LINK_ATTR}]`).forEach((el) => el.remove());

    function showFormInWidget(initialUrl, onRestore) {
      let widget = document.querySelector(`[${FLOATING_ATTR}="1"]`);
      if (!widget) {
        const { wrapper } = createResumeFloatingWidget();
        widget = wrapper;
        document.body.appendChild(widget);
        applyResumeFloatingTheme(widget);
        makeResumeWidgetDraggable(widget);
      }
      const bodyEl = widget.querySelector('.hrhelper-resume-floating-body');
      if (!bodyEl) return;
      bodyEl.innerHTML = '';
      const baseUrl = getBaseUrl();
      const form = buildLinkForm(initialUrl, async (url) => {
        const data = await postResumeLink(baseUrl, url);
        if (data && data.success) {
          const newState = {
            huntflowUrl: url,
            saved: true,
            candidateInfo: null,
            vacancy_name: (data.vacancy_name != null) ? data.vacancy_name : null,
          };
          saveStateToStorage(newState);
          renderBlock(newState);
        }
        return data || { success: false, message: 'Ошибка сохранения' };
      });
      if (typeof onRestore === 'function') {
        form._onEscape = onRestore;
        const escHandler = (e) => {
          if (e.key === 'Escape') {
            e.preventDefault();
            document.removeEventListener('keydown', escHandler);
            onRestore();
          }
        };
        document.addEventListener('keydown', escHandler);
      }
      bodyEl.appendChild(form);
    }

    function renderBlock(state) {
      const candidatePath = `/api/v1/huntflow/linkedin-applicants/candidate-info/?huntflow_url=${encodeURIComponent(state.huntflowUrl)}`;
      const useCached = state.candidateInfo && (state.candidateInfo.phone || state.candidateInfo.email || state.candidateInfo.full_name);

      showFloatingWidget(null, []);
      const bodyEl = document.querySelector(`[${FLOATING_ATTR}="1"] .hrhelper-resume-floating-body`);
      if (bodyEl) {
        bodyEl.innerHTML = '';
        const loading = document.createElement('div');
        loading.style.cssText = 'color:#666;font-size:13px;';
        loading.textContent = 'Загрузка данных кандидата…';
        bodyEl.appendChild(loading);
      }

      Promise.all([
        useCached ? Promise.resolve(state.candidateInfo) : apiFetch(candidatePath).then((r) => r.json().catch(() => null)),
        fetchStatusMulti(state.huntflowUrl),
      ]).then(async ([candidateData, multiData]) => {
        const info = normalizeCandidatePayload(candidateData) || state.candidateInfo || {};
        const candidateInfo = {
          full_name: info.full_name,
          phone: info.phone,
          email: info.email,
          telegram: info.telegram,
          linkedin: info.linkedin,
          communication: info.communication,
          office_readiness: info.office_readiness,
          level: info.level,
          extra_fields: info.extra_fields,
          labels: info.labels,
        };
        const vacancies = multiData && multiData.success && multiData.items && multiData.items.length > 0
          ? multiData.items
          : [buildVacancyFromCandidateInfo(info, {
            vacancy_name: state.vacancy_name,
            status_name: state.status_name,
            rejection_reason_name: state.rejection_reason_name,
          })];
        const host = (location.hostname || '').toLowerCase();
        const isRabota = host.includes('rabota.by');
        const portal = isRabota ? 'rabota.by' : 'hh.ru';
        // Показываем кнопки только для откликов (hhtmFrom=employer_vacancy_responses)
        // и только если есть хотя бы одна вакансия со статусом "rejected" или "new"
        const hasRejectedOrNew = (vacancies || []).some((v) => {
          if (!v) return false;
          const statusType = String(v.status_type || '').toLowerCase();
          const statusName = v.status_name || '';
          return statusType === 'rejected' || isNewStatusName(statusName);
        });
        const showActions = !!(state.huntflowUrl && hasRejectedOrNew && isResponsePage());

        const options = {
          huntflowUrl: state.huntflowUrl,
          onEditClick: null,
          onAddedToVacancy: () => renderBlock(state),
          showActions,
          resumeUrl: getBaseUrl(),
          isRabota,
          portal,
          vacancies,
          candidateName: (candidateInfo.full_name || '').trim(),
        };
        const restore = () => showFloatingWidget(candidateInfo, vacancies, options);
        options.onEditClick = () => {
          const w = document.querySelector(`[${FLOATING_ATTR}="1"]`);
          const b = w && w.querySelector('.hrhelper-resume-floating-body');
          if (b && b.querySelector('.hrhelper-link-form')) restore();
          else showFormInWidget(state.huntflowUrl, restore);
        };
        chrome.storage.local.get({ [RESUME_FLOATING_HIDDEN_KEY]: false }, (data) => {
          if (!data[RESUME_FLOATING_HIDDEN_KEY]) showFloatingWidget(candidateInfo, vacancies, options);
        });
        if (candidateData && !useCached && (normalizeCandidatePayload(candidateData) || candidateData.success)) {
          saveStateToStorage({
            huntflowUrl: state.huntflowUrl,
            saved: true,
            candidateInfo: normalizeCandidatePayload(candidateData) || candidateData,
            vacancy_name: state.vacancy_name || candidateData.vacancy_name,
          });
        }
      }).catch(() => {
        // При ошибке загрузки показываем виджет без кнопок (не знаем actions_allowed / статус)
        const host = (location.hostname || '').toLowerCase();
        const isRabota = host.includes('rabota.by');
        const fallbackOptions = {
          huntflowUrl: state.huntflowUrl,
          onEditClick: null,
          onAddedToVacancy: () => renderBlock(state),
          showActions: false,
          resumeUrl: getBaseUrl(),
          isRabota,
          portal: isRabota ? 'rabota.by' : 'hh.ru',
          vacancies: [],
        };
        const restoreFallback = () => showFloatingWidget(state.candidateInfo || {}, [], fallbackOptions);
        fallbackOptions.onEditClick = () => {
          const w = document.querySelector(`[${FLOATING_ATTR}="1"]`);
          const b = w && w.querySelector('.hrhelper-resume-floating-body');
          if (b && b.querySelector('.hrhelper-link-form')) restoreFallback();
          else showFormInWidget(state.huntflowUrl, restoreFallback);
        };
        showFloatingWidget(state.candidateInfo || {}, [], fallbackOptions);
      });
    }

    getStoredStateForPage().then((state) => {
      if (state && state.huntflowUrl) {
        renderBlock(state);
        return;
      }

      const baseUrl = getBaseUrl();
      if (!baseUrl) {
        hideFloatingWidget();
        return;
      }
      const resumeLinksPath = `/api/v1/huntflow/resume-links/?resume_url=${encodeURIComponent(baseUrl)}`;
      apiFetch(resumeLinksPath).then((res) => {
        if (!res || !res.success || !res.found || !res.huntflow_url) {
          try {
            chrome.storage.local.get({ [RESUME_FLOATING_HIDDEN_KEY]: false }, (data) => {
              try {
                if (!data[RESUME_FLOATING_HIDDEN_KEY]) showFormInWidget('');
              } catch (_) {}
            });
          } catch (_) {}
          return;
        }
        const backendState = {
          huntflowUrl: res.huntflow_url,
          saved: true,
          candidateInfo: null,
          vacancy_name: res.vacancy_name || null,
        };
        renderBlock(backendState);
      }).catch(() => {
        try {
          chrome.storage.local.get({ [RESUME_FLOATING_HIDDEN_KEY]: false }, (data) => {
            try {
              if (!data[RESUME_FLOATING_HIDDEN_KEY]) showFormInWidget('');
            } catch (_) {}
          });
        } catch (_) {
          // Extension context invalidated — не вызываем chrome API
        }
      });
    });
  }

  function scan() {
    injectStyles();
    injectSavedLinkBlock();
    findHuntflowLinks().forEach((link) => processLink(link));
  }

  function run() {
    loadResumeFloatingUIState();
    scan();
    var debouncedProcessLinks = debounce(function () {
      findHuntflowLinks().forEach(function (link) { processLink(link); });
    }, (TIMING && TIMING.DEBOUNCE_MUTATION) || 100);
    const observer = new MutationObserver(function () { debouncedProcessLinks(); });
    if (document.body) {
      observer.observe(document.body, { childList: true, subtree: true });
    } else {
      document.addEventListener('DOMContentLoaded', () => observer.observe(document.body, { childList: true, subtree: true }));
    }
    setTimeout(scan, 1500);
    setTimeout(scan, 4000);

    chrome.storage.onChanged.addListener((changes, areaName) => {
      if (areaName !== 'local' || !changes[RESUME_STORAGE_KEY]) return;
      const prev = document.querySelector(`[${BY_LINK_ATTR}]`);
      if (prev) prev.remove();
      injectSavedLinkBlock();
    });
  }

  chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
    if (msg && msg.action === 'getPageContext') {
      sendResponse({ url: window.location.href, pageUrl: window.location.href, context: 'resume' });
      return true;
    }
    if (msg && msg.action === 'setResumeFloatingVisible') {
      const visible = msg.visible === true;
      chrome.storage.local.set({ [RESUME_FLOATING_HIDDEN_KEY]: !visible }, () => {
        const widget = document.querySelector(`[${FLOATING_ATTR}="1"]`);
        if (widget) {
          widget.style.display = visible ? '' : 'none';
        } else if (visible) {
          injectSavedLinkBlock();
        }
        sendResponse({ success: true });
      });
      return true;
    }
  });

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', run);
  } else {
    run();
  }
})();
