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
  try {
    var data = await chrome.storage.sync.get({ [ACTIVE_PAGES_KEY]: DEFAULT_ACTIVE_PAGES });
    var active = data[ACTIVE_PAGES_KEY] || DEFAULT_ACTIVE_PAGES;
    if (!active.hh_ecosystem) return;
  } catch (_) {
    return;
  }

  const DATA_ATTR = 'data-hrhelper-candidate-info';
  const BY_LINK_ATTR = 'data-hrhelper-by-link';
  const BLOCK_CLASS = 'hrhelper-candidate-block';
  const RESUME_STORAGE_KEY = 'hrhelper_resume_state';
  const FLOATING_ATTR = 'data-hrhelper-resume-floating';
  const FLOATING_POS_KEY = 'hrhelper_resume_floating_pos';
  const RESUME_FLOATING_HIDDEN_KEY = 'hrhelper_resume_floating_hidden';
  const RESUME_FLOATING_UI_STATE_KEY = 'hrhelper_resume_floating_ui_state';
  const DEFAULT_RESUME_FLOATING_UI_STATE = { widgetCollapsed: false, additionalFieldsOpen: true };
  let resumeFloatingUIState = { ...DEFAULT_RESUME_FLOATING_UI_STATE };

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

  async function checkHhActionsAvailability(resumeUrl) {
    try {
      const qp = new URLSearchParams({ resume_url: resumeUrl });
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

  function formatRow(label, value, valueBold) {
    if (value == null || value === '') return '';
    const valHtml = valueBold ? `<strong>${escapeHtml(String(value))}</strong>` : escapeHtml(String(value));
    return `<div class="${BLOCK_CLASS}-row"><span class="${BLOCK_CLASS}-label">${escapeHtml(label)}:</span> <span class="${BLOCK_CLASS}-value">${valHtml}</span></div>`;
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

  /** Получить список вакансий: status-multi или один элемент из candidate-info */
  function fetchStatusMulti(huntflowUrl) {
    const shared = HRH.fetchStatusMulti;
    if (!shared) {
      throw new Error("[HRHelper] shared/api/status.js not loaded (fetchStatusMulti missing)");
    }
    return shared({ huntflowUrl: huntflowUrl }).then((data) => (data && !data.error ? data : null));
  }

  /**
   * Строит блок: заголовок (ФИО), контакты, список вакансий (вакансия — статус — дата; для отказа + причина).
   * @param {Object} candidateInfo - full_name, phone, email, telegram, communication
   * @param {Array} vacancies - [{ vacancy_name, status_name, last_change_at, status_type, rejection_reason_name }]
   * @param {Object} opts - showIfEmpty
   */
  function buildBlock(candidateInfo, vacancies, opts) {
    opts = opts || {};
    const info = candidateInfo || {};
    const comm = info.communication;
    const isCommTelegram = comm && /t\.me|telegram/i.test(String(comm));

    const contactRows = [
      formatRow('Телефон', info.phone),
      formatRow('Email', info.email),
      formatRow('Telegram', info.telegram),
      formatRow('Где ведётся коммуникация', !isCommTelegram ? comm : null),
    ].filter(Boolean);

    const vacancyItems = (vacancies || []).map((v) => {
      const name = v.vacancy_name || '—';
      const status = v.status_name || '—';
      const date = formatDate(v.last_change_at);
      const isRejected = v.status_type === 'rejected' && v.rejection_reason_name;
      const statusPart = isRejected ? `${status} (${v.rejection_reason_name})` : status;
      return `${escapeHtml(name)} — ${escapeHtml(statusPart)} — ${escapeHtml(date)}`;
    });

    const hasContent = info.full_name || contactRows.length > 0 || vacancyItems.length > 0;
    if (!hasContent && !opts.showIfEmpty) return null;

    const headerHtml = info.full_name
      ? `<div class="${BLOCK_CLASS}-header">${escapeHtml(info.full_name)}</div>`
      : '';

    const contactsHtml = contactRows.length > 0
      ? `<div class="${BLOCK_CLASS}-contacts">${contactRows.join('')}</div>`
      : '';

    const vacancyListHtml = vacancyItems.length > 0
      ? `<div class="${BLOCK_CLASS}-vacancies"><div class="${BLOCK_CLASS}-vacancies-title">Вакансии</div><ul class="${BLOCK_CLASS}-vacancies-list">${vacancyItems.map((t) => `<li>${t}</li>`).join('')}</ul></div>`
      : '';

    const bodyHtml = headerHtml + contactsHtml + vacancyListHtml || `<div class="${BLOCK_CLASS}-row"><span class="${BLOCK_CLASS}-value">Связано с Huntflow</span></div>`;

    const html = `<div class="${BLOCK_CLASS}" ${DATA_ATTR}=""><div class="${BLOCK_CLASS}-body">${bodyHtml}</div></div>`;

    const wrap = document.createElement('div');
    wrap.innerHTML = html.trim();
    return wrap.firstChild;
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
      .hrhelper-resume-floating-widget .hrhelper-resume-floating-switch-service,
      .hrhelper-resume-floating-widget button[style*="border-radius:4px"] { background: var(--hrhelper-btn-bg) !important; color: var(--hrhelper-muted) !important; border-color: var(--hrhelper-border) !important; }
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
      .hrhelper-resume-vacancy-card { padding: 8px 10px; border-radius: 8px; border: 1px solid var(--hrhelper-card-active-border); background: var(--hrhelper-card-active-bg); margin-bottom: 6px; font-size: 12px; display: flex; align-items: flex-start; gap: 10px; }
      .hrhelper-resume-vacancy-card-rejected { border-color: var(--hrhelper-card-rejected-border); background: var(--hrhelper-card-rejected-bg); }
      .hrhelper-resume-vacancy-card-archived { border-color: var(--hrhelper-card-archived-border); background: var(--hrhelper-card-archived-bg); }
      .hrhelper-resume-vacancy-card .hrhelper-resume-vacancy-line1 { margin-bottom: 2px; color: var(--hrhelper-text); font-weight: 600; }
      .hrhelper-resume-vacancy-card .hrhelper-resume-vacancy-line2 { margin-bottom: 2px; color: var(--hrhelper-muted); }
      .hrhelper-resume-vacancy-card .hrhelper-resume-vacancy-reason { margin-top: 4px; font-size: 11px; color: var(--hrhelper-danger); }
      .hrhelper-resume-vacancy-btn { width: 32px; height: 32px; padding: 0; border: 1px solid var(--hrhelper-card-active-border); border-radius: 6px; cursor: pointer; background: var(--hrhelper-card-active-bg); color: var(--hrhelper-accent); display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
      .hrhelper-resume-floating-widget.hrhelper-theme-dark .hrhelper-resume-vacancy-btn { border-color: rgba(88,166,255,.4); background: rgba(88,166,255,.18); color: #58a6ff; }
      .hrhelper-resume-floating-widget.hrhelper-theme-dark .hrhelper-resume-vacancy-card { background: rgba(88,166,255,.08) !important; border-color: rgba(88,166,255,.35) !important; }
      .hrhelper-resume-floating-widget.hrhelper-theme-dark .hrhelper-resume-vacancy-card .hrhelper-resume-vacancy-line1 { color: #e6edf3 !important; }
      .hrhelper-resume-floating-widget.hrhelper-theme-dark .hrhelper-resume-vacancy-card .hrhelper-resume-vacancy-line2 { color: #8b949e !important; }
      .hrhelper-resume-floating-widget.hrhelper-theme-dark .hrhelper-resume-vacancy-btn { background: rgba(88,166,255,.18) !important; border-color: rgba(88,166,255,.4) !important; color: #58a6ff !important; }
      .hrhelper-resume-additional-wrap { margin-bottom: 10px; }
      .hrhelper-resume-additional-header { width: 100%; text-align: left; font-weight: 700; margin-bottom: 4px; font-size: 13px; background: none; border: none; padding: 4px 0; cursor: pointer; display: flex; align-items: center; gap: 6px; color: var(--hrhelper-muted); }
      .hrhelper-resume-additional-header .hrhelper-toggle-icon { font-size: 12px; }
      .hrhelper-resume-additional-body { margin-left: 0; font-size: 11px; margin-bottom: 8px; padding: 8px; background: var(--hrhelper-btn-bg); border-radius: 6px; }
      .hrhelper-resume-additional-body .hrhelper-additional-row { margin-bottom: 4px; }
      .hrhelper-resume-additional-body .hrhelper-additional-label { color: var(--hrhelper-muted); }
      .hrhelper-resume-additional-body .hrhelper-additional-value { color: var(--hrhelper-text); }
      .hrhelper-resume-contacts-title { font-weight: 700; margin-bottom: 6px; font-size: 13px; color: var(--hrhelper-muted); }
      .hrhelper-resume-contact-row { margin-bottom: 4px; }
      .hrhelper-resume-contact-row .hrhelper-contact-label { color: var(--hrhelper-muted); }
      .hrhelper-resume-contact-row .hrhelper-contact-value { color: var(--hrhelper-text); }
      .hrhelper-resume-labels-title { font-weight: 700; margin-bottom: 4px; font-size: 13px; color: var(--hrhelper-muted); }
      .hrhelper-resume-labels-wrap { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 8px; }
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
    wrapper.style.cssText = `
      position: fixed;
      top: 60px;
      right: 12px;
      z-index: 99999;
      width: 320px;
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
    const editBtn = document.createElement('button');
    editBtn.type = 'button';
    editBtn.className = 'hrhelper-resume-floating-edit';
    editBtn.title = 'Редактировать ссылку';
    editBtn.setAttribute('aria-label', 'Редактировать ссылку');
    editBtn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zM20.71 7.04c.39-.39.39-1.02 0-1.41l-2.34-2.34c-.39-.39-1.02-.39-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z"/></svg>';
    editBtn.style.cssText = 'width:24px;height:24px;border:none;background:var(--hrhelper-btn-bg,rgba(0,0,0,.05));border-radius:4px;cursor:pointer;color:var(--hrhelper-muted,#666);flex-shrink:0;display:none;padding:0;align-items:center;justify-content:center;';
    editBtn.addEventListener('click', function () { if (this._onEditClick) this._onEditClick(); });
    editBtn.addEventListener('mouseenter', () => { editBtn.style.background = 'var(--hrhelper-border,rgba(0,0,0,.1))'; });
    editBtn.addEventListener('mouseleave', () => { editBtn.style.background = 'var(--hrhelper-btn-bg,rgba(0,0,0,.05))'; });
    header.appendChild(editBtn);
    const toggleBtn = document.createElement('button');
    toggleBtn.type = 'button';
    toggleBtn.textContent = '−';
    toggleBtn.style.cssText = 'width:24px;height:24px;border:none;background:var(--hrhelper-btn-bg,rgba(0,0,0,.05));border-radius:4px;cursor:pointer;font-size:16px;line-height:1;color:var(--hrhelper-muted,#666);flex-shrink:0;';
    toggleBtn.addEventListener('mouseenter', () => { toggleBtn.style.background = 'var(--hrhelper-border,rgba(0,0,0,.1))'; });
    toggleBtn.addEventListener('mouseleave', () => { toggleBtn.style.background = 'var(--hrhelper-btn-bg,rgba(0,0,0,.05))'; });
    header.appendChild(toggleBtn);
    wrapper.appendChild(header);
    const body = document.createElement('div');
    body.className = 'hrhelper-resume-floating-body';
    body.style.cssText = 'display:flex;flex-direction:column;gap:8px;flex:1;min-height:0;min-width:0;overflow-y:auto;overflow-x:hidden;word-break:break-word;overflow-wrap:break-word;font-size:13px;line-height:1.4;color:var(--hrhelper-text,#333);';
    wrapper.appendChild(body);
    const isCollapsed = !!resumeFloatingUIState.widgetCollapsed;
    body.style.display = isCollapsed ? 'none' : 'flex';
    toggleBtn.textContent = isCollapsed ? '+' : '−';
    toggleBtn.addEventListener('click', () => {
      const next = body.style.display === 'none';
      body.style.display = next ? 'flex' : 'none';
      toggleBtn.textContent = next ? '−' : '+';
      saveResumeFloatingUIState({ widgetCollapsed: !next });
    });
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

  function buildFloatingBodyContent(candidateInfo, vacancies, options) {
    const info = candidateInfo || {};
    const fragment = document.createDocumentFragment();

    const opts = options || {};
    if (opts.showActions) {
      try {
        fragment.appendChild(buildActionButtons(opts));
        const spacer0 = document.createElement('div');
        spacer0.style.marginBottom = '10px';
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
      spacer1.style.marginBottom = '10px';
      fragment.appendChild(spacer1);
    }

    const excludeCommLabel = /где ведется коммуникация|где ведётся коммуникация|communication|телефон|phone|email|telegram|linkedin/i;
    const additionalFields = [
      ['Готовность к офису', info.office_readiness],
      ['Уровень', info.level],
    ].filter(([label, v]) => v != null && v !== '' && !excludeCommLabel.test(String(label)));
    if (info.extra_fields && typeof info.extra_fields === 'object') {
      Object.entries(info.extra_fields).forEach(([key, val]) => {
        if (val != null && val !== '' && !excludeCommLabel.test(String(key))) {
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
      const labelsTitle = document.createElement('div');
      labelsTitle.className = 'hrhelper-resume-labels-title';
      labelsTitle.textContent = 'Метки';
      fragment.appendChild(labelsTitle);
      const labelsWrap = document.createElement('div');
      labelsWrap.className = 'hrhelper-resume-labels-wrap';
      info.labels.forEach((lbl) => {
        const name = (typeof lbl === 'string' ? lbl : (lbl && lbl.name) || '').trim();
        if (!name) return;
        const tag = document.createElement('span');
        tag.className = 'hrhelper-resume-tag';
        tag.textContent = name;
        labelsWrap.appendChild(tag);
      });
      fragment.appendChild(labelsWrap);
    }
    const items = vacancies || [];
    if (items.length > 0) {
      const vacTitle = document.createElement('div');
      vacTitle.className = 'hrhelper-resume-vacancy-title';
      vacTitle.style.cssText = 'font-weight:700;margin-bottom:6px;font-size:13px;';
      vacTitle.textContent = 'Вакансии';
      fragment.appendChild(vacTitle);
      items.forEach((v) => {
        const name = v.vacancy_name || '—';
        const status = v.status_name || '—';
        const date = formatDate(v.last_change_at);
        const card = document.createElement('div');
        card.className = 'hrhelper-resume-vacancy-card' + (v.status_type === 'rejected' ? ' hrhelper-resume-vacancy-card-rejected' : '') + (v.is_archived ? ' hrhelper-resume-vacancy-card-archived' : '');
        const cardLeft = document.createElement('div');
        cardLeft.style.cssText = 'flex:1;min-width:0;';
        const line1 = document.createElement('div');
        line1.className = 'hrhelper-resume-vacancy-line1';
        line1.textContent = name;
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
          const btn = document.createElement('button');
          btn.type = 'button';
          btn.className = 'hrhelper-resume-vacancy-btn';
          btn.title = 'Открыть в Huntflow';
          btn.setAttribute('aria-label', 'Открыть в Huntflow');
          btn.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M19 19H5V5h7V3H5c-1.11 0-2 .9-2 2v14c0 1.1.89 2 2 2h14c1.1 0 2-.9 2-2v-7h-2v7zM14 3v2h3.59l-9.83 9.83 1.41 1.41L19 6.41V10h2V3h-7z"/></svg>';
          btn.addEventListener('click', () => { window.open(v.appurl, '_blank', 'noopener,noreferrer'); });
          card.appendChild(btn);
        }
        fragment.appendChild(card);
      });
    }
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

  async function showRejectForm(bar, options, inviteBtn, rejectBtn) {
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
        bar.appendChild(inviteBtn);
        bar.appendChild(rejectBtn);
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
            badge.textContent = '✓ Отказ отправлен';
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
            message_template: 'default_invite',
          }),
        });
        const data = await res.json().catch(() => null);
        if (res.ok && data?.success) {
          bar.innerHTML = '';
          const badge = document.createElement('div');
          badge.className = 'hrhelper-resume-action-badge hrhelper-resume-action-badge--success';
          badge.textContent = '✓ Приглашение отправлено';
          bar.appendChild(badge);
        } else {
          showActionError(bar, data?.message || 'Не удалось отправить приглашение');
          inviteBtn.disabled = false;
          rejectBtn.disabled = false;
          inviteBtn.innerHTML = originalHTML;
        }
      } catch (e) {
        showActionError(bar, e.message || 'Ошибка сети');
        inviteBtn.disabled = false;
        rejectBtn.disabled = false;
        inviteBtn.innerHTML = originalHTML;
      }
    });

    rejectBtn.addEventListener('click', () => {
      showRejectForm(bar, options, inviteBtn, rejectBtn);
    });

    bar.appendChild(inviteBtn);
    bar.appendChild(rejectBtn);
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
    let widget = document.querySelector(`[${FLOATING_ATTR}="1"]`);
    if (!widget) {
      const { wrapper, body } = createResumeFloatingWidget();
      widget = wrapper;
      document.body.appendChild(widget);
      applyResumeFloatingTheme(widget);
      applyResumeFloatingTheme(widget);
      makeResumeWidgetDraggable(widget);
    }
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
      .${BLOCK_CLASS} {
        margin-top: 8px;
        padding: 12px;
        max-width: 480px;
        background: #f5f7fa;
        border: 1px solid #e0e4e9;
        border-radius: 8px;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        font-size: 13px;
        line-height: 1.4;
        box-shadow: 0 1px 3px rgba(0,0,0,0.06);
      }
      .${BLOCK_CLASS}-header {
        font-weight: 600;
        font-size: 15px;
        color: #111;
        margin-bottom: 8px;
      }
      .${BLOCK_CLASS}-contacts { margin-bottom: 10px; }
      .${BLOCK_CLASS}-vacancies-title {
        font-weight: 600;
        color: #0a66c2;
        margin-bottom: 6px;
        font-size: 12px;
        text-transform: uppercase;
        letter-spacing: 0.02em;
      }
      .${BLOCK_CLASS}-vacancies-list {
        margin: 0;
        padding-left: 18px;
        list-style: disc;
      }
      .${BLOCK_CLASS}-vacancies-list li {
        margin-bottom: 4px;
      }
      .${BLOCK_CLASS}-vacancies-list li:last-child { margin-bottom: 0; }
      .${BLOCK_CLASS}-body { color: #333; }
      .${BLOCK_CLASS}-row { margin-bottom: 4px; }
      .${BLOCK_CLASS}-row:last-child { margin-bottom: 0; }
      .${BLOCK_CLASS}-label { color: #666; }
      .${BLOCK_CLASS}-value { color: #111; }

      .hrhelper-resume-action-bar {
        display: flex;
        flex-direction: column;
        align-items: stretch;
        gap: 8px;
        margin-top: 8px;
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
      apiFetch(candidatePath),
      fetchStatusMulti(url),
    ]).then(([candidateData, multiData]) => {
      const info = candidateData && candidateData.success ? candidateData : null;
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

  /** Найти элемент после которого вставить блок: «Кандидат» или ФИО (или заголовок резюме) */
  function findInsertionPoint(fioFromState) {
    const host = (window.location.hostname || '').toLowerCase();
    const isRabota = host === 'rabota.by' || host === 'www.rabota.by' || host.endsWith('.rabota.by');
    const isHh = host === 'hh.ru' || host.endsWith('.hh.ru');

    const trim = (s) => (s && String(s).trim()) || '';

    function walk(root, fn) {
      const it = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT, null, false);
      let el;
      while ((el = it.nextNode())) {
        if (fn(el)) return el;
      }
      return null;
    }

    // 1) По ФИО из сохранённого состояния
    if (fioFromState && trim(fioFromState)) {
      const need = trim(fioFromState);
      const byFio = walk(document.body, (el) => {
        const t = trim(el.textContent);
        if (t === need) return true;
        if (!el.children.length && t.indexOf(need) !== -1) return true;
        return false;
      });
      if (byFio) return byFio;
    }

    // 2) Текст "Кандидат" (метка или заголовок)
    const byKandidat = walk(document.body, (el) => {
      const t = trim(el.textContent);
      if (t !== 'Кандидат' && !t.startsWith('Кандидат ')) return false;
      return el.children.length === 0 || trim(el.textContent) === 'Кандидат';
    });
    if (byKandidat) return byKandidat;

    // 3) hh.ru: заголовок блока резюме
    if (isHh) {
      const q = document.querySelector('[data-qa="resume-block-title"]') || document.querySelector('[data-qa="resume-block-personal-info"]');
      if (q) return q;
    }

    // 4) rabota.by и субдомены: типичный заголовок с именем (в карточке резюме)
    if (isRabota) {
      const main = document.querySelector('[class*="resume"] [class*="title"]') || document.querySelector('[class*="Resume"] [class*="title"]');
      if (main) return main;
      const byClass = document.querySelector('[class*="resume"]') || document.querySelector('[class*="Resume"]') || document.querySelector('[class*="card"]');
      if (byClass) return byClass;
    }

    // 5) Первый h1 (часто ФИО или заголовок страницы)
    const h1 = document.querySelector('h1');
    if (h1) return h1;

    // 6) Общие запасные варианты
    if (isHh) {
      const q = document.querySelector('.bloko-header-section-1') || document.querySelector('[class*="resume-header"]');
      if (q) return q;
    }
    if (isRabota) {
      const q = document.querySelector('h2') || document.querySelector('.card-title') || document.querySelector('[class*="title"]') || document.querySelector('main') || document.querySelector('article');
      if (q) return q;
    }

    // 7) Универсальный fallback: main, article или первый контейнер с контентом
    const fallback = document.querySelector('main') || document.querySelector('article') || document.querySelector('[role="main"]');
    if (fallback) return fallback;

    // 8) Крайний fallback: body (страница резюме — вставляем в начало body)
    if (document.body && /\/resume\/[^/?#]+/.test(window.location.pathname || '')) {
      return document.body;
    }
    return null;
  }

  /** Показать плавающее окно с данными Huntflow (по сохранённой связи или по API resume-links) */
  function injectSavedLinkBlock() {
    document.querySelectorAll(`[${BY_LINK_ATTR}]`).forEach((el) => el.remove());

    function showFormInWidget(initialUrl) {
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
        useCached ? Promise.resolve(state.candidateInfo) : apiFetch(candidatePath),
        fetchStatusMulti(state.huntflowUrl),
      ]).then(async ([candidateData, multiData]) => {
        const info = (candidateData && (candidateData.success || candidateData.full_name) ? candidateData : state.candidateInfo) || {};
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
        const hasRejected = (vacancies || []).some((v) => (v && String(v.status_type || '').toLowerCase() === 'rejected'));
        const hhStatus = await checkHhIntegrationStatus();
        const actionsInfo = await checkHhActionsAvailability(getResumeUrlForActions());
        const hhCanAct = !!(actionsInfo && actionsInfo.success && actionsInfo.actions_allowed);
        const showActions = !!(state.huntflowUrl && hhStatus && hhStatus.connected && hhCanAct && !hasRejected);

        const options = {
          huntflowUrl: state.huntflowUrl,
          onEditClick: () => showFormInWidget(state.huntflowUrl),
          showActions,
          resumeUrl: getBaseUrl(),
          isRabota,
          portal,
          vacancies,
        };
        chrome.storage.local.get({ [RESUME_FLOATING_HIDDEN_KEY]: false }, (data) => {
          if (!data[RESUME_FLOATING_HIDDEN_KEY]) showFloatingWidget(candidateInfo, vacancies, options);
        });
        if (candidateData && candidateData.success && !useCached) {
          saveStateToStorage({
            huntflowUrl: state.huntflowUrl,
            saved: true,
            candidateInfo: candidateData,
            vacancy_name: state.vacancy_name || candidateData.vacancy_name,
          });
        }
      }).catch(() => {
        hideFloatingWidget();
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
    const observer = new MutationObserver(() => {
      findHuntflowLinks().forEach((link) => processLink(link));
    });
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
