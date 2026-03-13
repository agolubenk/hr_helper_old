/**
 * HR Helper — контент-скрипт для Google Drive/Docs
 * Плавающее окно полностью идентичное LinkedIn
 */
(async function () {
  'use strict';

  var HRH = window.__HRH__;
  if (!HRH) return;

  var ACTIVE_PAGES_KEY = HRH.ACTIVE_PAGES_KEY;
  var DEFAULT_ACTIVE_PAGES = HRH.DEFAULT_ACTIVE_PAGES;
  var OPTIONS_THEME_KEY = HRH.OPTIONS_THEME_KEY;
  var debounce = HRH.debounce;
  var TIMING = HRH.TIMING || {};

  try {
    var data = await chrome.storage.sync.get({ [ACTIVE_PAGES_KEY]: DEFAULT_ACTIVE_PAGES });
    var active = data[ACTIVE_PAGES_KEY] || DEFAULT_ACTIVE_PAGES;
    if (!active.gdrive) return;
  } catch (e) { return; }

  const FLOATING_UI_STATE_KEY = 'hrhelper_gdrive_floating_ui_state';
  const FLOATING_POS_KEY = 'hrhelper_gdrive_floating_pos';
  const DEFAULT_UI_STATE = { widgetCollapsed: false, candidateDataOpen: true, extraFieldsOpen: true, commentsOpen: true };

  let floatingWidgetUIState = { ...DEFAULT_UI_STATE };
  let floatingWidgetData = null;
  let resolvedWidgetTheme = 'light';

  let currentFileId = null;
  let currentLinkInfo = null;
  let candidateInfo = null;
  let vacancies = [];
  let selectedVacancyId = null;
  let defaultVacancyId = null;
  let isEditMode = false;

  function loadFloatingUIState() {
    try {
      chrome.storage.local.get({ [FLOATING_UI_STATE_KEY]: DEFAULT_UI_STATE }, (data) => {
        floatingWidgetUIState = { ...DEFAULT_UI_STATE, ...data[FLOATING_UI_STATE_KEY] };
      });
    } catch (_) {}
  }

  function saveFloatingUIState(partial) {
    floatingWidgetUIState = { ...floatingWidgetUIState, ...partial };
    try { chrome.storage.local.set({ [FLOATING_UI_STATE_KEY]: floatingWidgetUIState }); } catch (_) {}
  }

  loadFloatingUIState();

  function extractFileId() {
    const url = window.location.href;
    let match = url.match(/\/file\/d\/([a-zA-Z0-9_-]+)/);
    if (!match) match = url.match(/\/document\/d\/([a-zA-Z0-9_-]+)/);
    if (!match) match = url.match(/\/spreadsheets\/d\/([a-zA-Z0-9_-]+)/);
    if (!match) match = url.match(/\/presentation\/d\/([a-zA-Z0-9_-]+)/);
    if (!match) match = url.match(/[?&]id=([a-zA-Z0-9_-]+)/);
    return match ? match[1] : null;
  }

  function escapeHtml(s) {
    return String(s || '').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  const formatVacancyDate = HRH.formatVacancyDate || function(d) {
    if (!d) return '';
    try { return new Date(d).toLocaleDateString('ru-RU'); } catch (_) { return ''; }
  };

  const formatCommentDate = HRH.formatCommentDate || function(d) {
    if (!d) return '';
    try {
      const dt = new Date(d);
      return dt.toLocaleDateString('ru-RU') + ' ' + dt.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
    } catch (_) { return ''; }
  };

  async function apiJson(path, options = {}) {
    try {
      const response = await chrome.runtime.sendMessage({
        type: 'HRHELPER_API',
        payload: { path, method: options.method || 'GET', body: options.body }
      });
      return response?.ok ? response.json : (response?.json || null);
    } catch (e) { return null; }
  }

  async function fetchGDriveLink(fileId) {
    return apiJson(`/api/gdrive/link/?file_id=${encodeURIComponent(fileId)}`);
  }

  async function fetchVacanciesActive() {
    return apiJson('/api/vacancies/active/');
  }

  async function parseAndCreateCandidate(fileId, vacancyId) {
    return apiJson('/api/gdrive/parse-and-create/', {
      method: 'POST',
      body: { file_id: fileId, vacancy_id: vacancyId, source_url: window.location.href }
    });
  }

  async function updateGDriveLink(fileId, huntflowUrl) {
    return apiJson('/api/gdrive/link/update/', {
      method: 'POST',
      body: { file_id: fileId, huntflow_url: huntflowUrl }
    });
  }

  async function fetchCandidateInfo(huntflowUrl) {
    if (!huntflowUrl) return null;
    return apiJson(`/api/v1/huntflow/linkedin-applicants/candidate-info/?huntflow_url=${encodeURIComponent(huntflowUrl)}`);
  }

  async function fetchStatusMulti(huntflowUrl) {
    if (!huntflowUrl) return null;
    return apiJson(`/api/v1/huntflow/linkedin-applicants/status-multi/?huntflow_url=${encodeURIComponent(huntflowUrl)}`);
  }

  async function fetchStatusOptions(huntflowUrl) {
    if (!huntflowUrl) return null;
    return apiJson(`/api/v1/huntflow/linkedin-applicants/status-options/?huntflow_url=${encodeURIComponent(huntflowUrl)}`);
  }

  async function fetchAvailableVacancies(huntflowUrl) {
    if (!huntflowUrl) return null;
    return apiJson(`/api/v1/huntflow/linkedin-applicants/available-vacancies/?huntflow_url=${encodeURIComponent(huntflowUrl)}`);
  }

  async function updateStatus(huntflowUrl, statusId, rejectionReasonId, vacancyId, comment) {
    return apiJson('/api/v1/huntflow/linkedin-applicants/update-status/', {
      method: 'POST',
      body: { huntflow_url: huntflowUrl, status_id: statusId, rejection_reason_id: rejectionReasonId || null, vacancy_id: vacancyId, comment: comment || null }
    });
  }

  async function addToVacancy(huntflowUrl, vacancyId) {
    return apiJson('/api/v1/huntflow/linkedin-applicants/add-to-vacancy/', {
      method: 'POST',
      body: { huntflow_url: huntflowUrl, vacancy_id: vacancyId }
    });
  }

  const hasBlacklistLabel = HRH.hasBlacklistLabel;
  const isNewStatusName = HRH.isNewStatusName;
  const hexToRgba = HRH.hexToRgba;
  const normalizeLabelColor = HRH.normalizeLabelColor || ((v) => (v && typeof v === 'string' ? (v.indexOf('#') === 0 ? v : '#' + v.replace(/^#/, '')) : ''));

  function isRejectionReasonClosedByOther(reasonName) {
    const n = (reasonName || '').trim().toLowerCase().replace(/ё/g, 'е');
    return n.includes('закрыли') && n.includes('вакансию') && n.includes('другим');
  }

  function computeBorderColorForVacancy(v) {
    if (!v) return null;
    const statusType = v.status_type;
    const statusName = v.status_name || '';
    if (statusType === 'rejected') {
      if (isRejectionReasonClosedByOther(v.rejection_reason_name)) return '#0a66c2';
      const ts = v.last_change_at || v.last_comment_at || null;
      const dt = ts ? new Date(ts) : null;
      const ms = dt && !isNaN(dt.getTime()) ? (Date.now() - dt.getTime()) : null;
      const halfYearMs = 183 * 24 * 60 * 60 * 1000;
      if (ms != null && ms < halfYearMs) return '#dc3545';
      return '#fd7e14';
    }
    if (!isNewStatusName(statusName)) return '#198754';
    return '#0a66c2';
  }

  function getPrimaryVacancyForBorder() {
    const items = vacancies || [];
    const selId = selectedVacancyId ?? defaultVacancyId;
    const bySel = selId != null ? items.find(v => v && v.vacancy_id === selId) : null;
    if (bySel) return bySel;
    const active = items.find(v => v && !v.is_hired && !v.is_archived && v.status_type !== 'rejected');
    return active || items[0] || null;
  }

  function computeFloatingBorderColor() {
    if (hasBlacklistLabel && hasBlacklistLabel(candidateInfo)) return '#111';
    const inBase = currentLinkInfo?.found && currentLinkInfo?.huntflow_url;
    if (!inBase) return null;
    const primary = getPrimaryVacancyForBorder();
    return computeBorderColorForVacancy(primary);
  }

  function categorizeVacancies(items) {
    return {
      active: items.filter(v => v && !v.is_hired && !v.is_archived && v.status_type !== 'rejected'),
      rejected: items.filter(v => v && v.status_type === 'rejected'),
      archived: items.filter(v => v && v.is_archived && v.status_type !== 'rejected'),
      hired: items.filter(v => v && v.is_hired)
    };
  }

  function getSelectedVacancyUrl() {
    const selId = selectedVacancyId ?? defaultVacancyId;
    const v = (vacancies || []).find(i => i.vacancy_id === selId);
    return v ? v.appurl : currentLinkInfo?.huntflow_url;
  }

  function updateResolvedWidgetTheme() {
    chrome.storage.sync.get({ [OPTIONS_THEME_KEY]: 'system' }, (data) => {
      const theme = data[OPTIONS_THEME_KEY] || 'system';
      if (theme === 'light') { resolvedWidgetTheme = 'light'; }
      else if (theme === 'dark') { resolvedWidgetTheme = 'dark'; }
      else { resolvedWidgetTheme = window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'; }
      applyFloatingWidgetTheme();
    });
  }

  function applyFloatingWidgetTheme() {
    const wrapper = document.querySelector('[data-hrhelper-gdrive-floating]');
    if (!wrapper) return;
    if (resolvedWidgetTheme === 'dark') wrapper.classList.add('hrhelper-theme-dark');
    else wrapper.classList.remove('hrhelper-theme-dark');
  }

  function applyFloatingBorder(wrapper, color) {
    if (!wrapper) return;
    const base = '0 4px 16px rgba(0, 0, 0, 0.15), 0 0 0 1px rgba(0, 0, 0, 0.05)';
    if (!color) { wrapper.style.boxShadow = base; return; }
    const shadowColor = hexToRgba ? hexToRgba(color, 0.28) : color;
    wrapper.style.boxShadow = `0 0 0 2px ${color} inset, 0 4px 14px -2px ${shadowColor}, ${base}`;
  }

  function injectFloatingWidgetThemeStyles() {
    if (document.getElementById('hrhelper-gdrive-theme')) return;
    const style = document.createElement('style');
    style.id = 'hrhelper-gdrive-theme';
    style.textContent = `
      .hrhelper-floating-widget { background: var(--hrhelper-bg) !important; color: var(--hrhelper-text) !important; }
      .hrhelper-floating-widget .hrhelper-widget-header { border-bottom-color: var(--hrhelper-border) !important; }
      .hrhelper-floating-widget .hrhelper-widget-title { color: var(--hrhelper-accent) !important; }
      .hrhelper-floating-widget .hrhelper-toggle-btn { background: var(--hrhelper-btn-bg) !important; color: var(--hrhelper-muted) !important; transition: background .15s ease !important; }
      .hrhelper-floating-widget .hrhelper-toggle-btn:hover { background: var(--hrhelper-border) !important; }
      .hrhelper-floating-widget .hrhelper-floating-action-group button { transition: background .15s ease !important; }
      .hrhelper-floating-widget .hrhelper-floating-action-group button:hover { background: var(--hrhelper-border) !important; }
      .hrhelper-floating-widget .hrhelper-floating-copy-btn.hrhelper-copy-btn-copied { background: var(--hrhelper-success-bg) !important; border-color: var(--hrhelper-success-border) !important; color: var(--hrhelper-success) !important; }
      .hrhelper-floating-widget input, .hrhelper-floating-widget select { background: var(--hrhelper-input-bg) !important; color: var(--hrhelper-text) !important; border-color: var(--hrhelper-border) !important; }
      .hrhelper-floating-widget .hrhelper-widget-body { color: var(--hrhelper-text) !important; }
      .hrhelper-floating-widget .hrhelper-body-muted { color: var(--hrhelper-muted) !important; }
      .hrhelper-floating-widget .hrhelper-body-accent { color: var(--hrhelper-accent) !important; }
      .hrhelper-floating-widget .hrhelper-body-danger { color: var(--hrhelper-danger) !important; }
      .hrhelper-floating-widget .hrhelper-body-success { color: var(--hrhelper-success) !important; }
      .hrhelper-floating-widget .hrhelper-ctx-status-block { border-top-color: var(--hrhelper-border) !important; }
      :root { --hrhelper-bg: rgba(255,255,255,.98); --hrhelper-text: #212529; --hrhelper-muted: #6c757d; --hrhelper-border: rgba(0,0,0,.08); --hrhelper-accent: #0a66c2; --hrhelper-btn-bg: rgba(0,0,0,.05); --hrhelper-input-bg: #fff; --hrhelper-danger: #842029; --hrhelper-danger-bg: #f8d7da; --hrhelper-danger-border: #f1aeb5; --hrhelper-success: #0f5132; --hrhelper-success-bg: #d1e7dd; --hrhelper-success-border: #a3cfbb; --hrhelper-card-border: #b6d4fe; --hrhelper-card-bg: #f0f7ff; --hrhelper-card-sel-border: #0a66c2; --hrhelper-card-sel-bg: #e7f1ff; }
      .hrhelper-floating-widget.hrhelper-theme-dark { --hrhelper-bg: #161b22; --hrhelper-text: #e6edf3; --hrhelper-muted: #8b949e; --hrhelper-border: rgba(255,255,255,.12); --hrhelper-accent: #58a6ff; --hrhelper-btn-bg: rgba(255,255,255,.08); --hrhelper-input-bg: #0d1117; --hrhelper-danger: #f85149; --hrhelper-danger-bg: rgba(248,81,73,.15); --hrhelper-danger-border: rgba(248,81,73,.4); --hrhelper-success: #3fb950; --hrhelper-success-bg: rgba(63,185,80,.15); --hrhelper-success-border: rgba(63,185,80,.4); --hrhelper-card-border: rgba(88,166,255,.35); --hrhelper-card-bg: rgba(88,166,255,.08); --hrhelper-card-sel-border: #58a6ff; --hrhelper-card-sel-bg: rgba(88,166,255,.18); }
    `;
    (document.head || document.documentElement).appendChild(style);
  }

  function createFloatingWidget() {
    injectFloatingWidgetThemeStyles();
    const wrapper = document.createElement('div');
    wrapper.className = 'hrhelper-floating-widget';
    wrapper.dataset.hrhelperGdriveFloating = 'true';
    const widgetWidth = HRH.FLOATING_WIDGET_WIDTH != null ? HRH.FLOATING_WIDGET_WIDTH : 320;
    wrapper.style.cssText = `position:fixed;top:60px;right:12px;z-index:99999;width:${widgetWidth}px;min-width:0;max-height:calc(100vh - 168px);border-radius:12px;padding:16px;backdrop-filter:blur(8px);transition:all 0.3s cubic-bezier(0.16, 1, 0.3, 1);display:flex;flex-direction:column;overflow:hidden;overflow-x:hidden;`;
    const baseShadow = '0 4px 16px rgba(0, 0, 0, 0.15), 0 0 0 1px rgba(0, 0, 0, 0.05)';
    wrapper.style.boxShadow = baseShadow;

    const header = document.createElement('div');
    header.className = 'hrhelper-widget-header';
    header.style.cssText = 'display:flex;align-items:center;justify-content:space-between;gap:8px;padding-bottom:8px;border-bottom:1px solid var(--hrhelper-border,rgba(0,0,0,.08));flex-shrink:0;';

    const headerLeft = document.createElement('div');
    headerLeft.style.cssText = 'flex:1;min-width:0;display:flex;align-items:center;gap:6px;';

    const title = document.createElement('div');
    title.className = 'hrhelper-widget-title';
    title.style.cssText = 'font-size:14px;font-weight:600;color:var(--hrhelper-accent,#0a66c2);display:flex;align-items:center;gap:6px;flex:1;min-width:0;overflow:hidden;';
    const titleIcon = document.createElement('img');
    titleIcon.className = 'hrhelper-title-icon';
    titleIcon.src = chrome.runtime.getURL('icons/icon-32.png');
    titleIcon.width = 20; titleIcon.height = 20;
    titleIcon.style.cssText = 'flex-shrink:0;display:block;object-fit:contain;';
    title.appendChild(titleIcon);
    const titleText = document.createElement('span');
    titleText.className = 'hrhelper-widget-title-text';
    titleText.style.cssText = 'overflow:hidden;text-overflow:ellipsis;white-space:nowrap;';
    titleText.textContent = 'HR Helper';
    title.appendChild(titleText);
    headerLeft.appendChild(title);

    const actionGroup = document.createElement('div');
    actionGroup.className = 'hrhelper-floating-action-group';
    actionGroup.style.cssText = 'display:flex;align-items:stretch;gap:0;flex-shrink:0;';

    const btnStyle = 'width:24px;height:24px;border:1px solid var(--hrhelper-border,rgba(0,0,0,.15));cursor:pointer;color:var(--hrhelper-muted,#666);flex-shrink:0;padding:0;display:none;align-items:center;justify-content:center;background:var(--hrhelper-btn-bg,rgba(0,0,0,.05));';

    const addVacancyBtn = document.createElement('button');
    addVacancyBtn.type = 'button';
    addVacancyBtn.className = 'hrhelper-add-vacancy-btn';
    addVacancyBtn.textContent = '+';
    addVacancyBtn.title = 'Взять на другую вакансию';
    addVacancyBtn.style.cssText = btnStyle + 'border-right:none;border-radius:4px 0 0 4px;font-size:16px;line-height:1;';
    actionGroup.appendChild(addVacancyBtn);

    const huntflowBtn = document.createElement('button');
    huntflowBtn.type = 'button';
    huntflowBtn.className = 'hrhelper-floating-huntflow-btn';
    huntflowBtn.title = 'Открыть в Huntflow';
    huntflowBtn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M19 19H5V5h7V3H5c-1.11 0-2 .9-2 2v14c0 1.1.89 2 2 2h14c1.1 0 2-.9 2-2v-7h-2v7zM14 3v2h3.59l-9.83 9.83 1.41 1.41L19 6.41V10h2V3h-7z"/></svg>';
    huntflowBtn.style.cssText = btnStyle + 'border-radius:0;';
    actionGroup.appendChild(huntflowBtn);

    const floatingEditBtn = document.createElement('button');
    floatingEditBtn.type = 'button';
    floatingEditBtn.className = 'hrhelper-floating-edit-btn';
    floatingEditBtn.title = 'Редактировать ссылку';
    floatingEditBtn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zM20.71 7.04c.39-.39.39-1.02 0-1.41l-2.34-2.34c-.39-.39-1.02-.39-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z"/></svg>';
    floatingEditBtn.style.cssText = btnStyle + 'border-radius:0 4px 4px 0;';
    actionGroup.appendChild(floatingEditBtn);

    const copyVacancyBtn = document.createElement('button');
    copyVacancyBtn.type = 'button';
    copyVacancyBtn.className = 'hrhelper-floating-copy-btn';
    copyVacancyBtn.title = 'Скопировать ссылку';
    copyVacancyBtn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M16 1H4c-1.1 0-2 .9-2 2v14h2V3h12V1zm3 4H8c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h11c1.1 0 2-.9 2-2V7c0-1.1-.9-2-2-2zm0 16H8V7h11v14z"/></svg>';
    copyVacancyBtn.style.cssText = 'width:24px;height:24px;border:1px solid var(--hrhelper-border,rgba(0,0,0,.15));border-radius:4px;cursor:pointer;color:var(--hrhelper-muted,#666);flex-shrink:0;padding:0;display:flex;align-items:center;justify-content:center;background:var(--hrhelper-btn-bg,rgba(0,0,0,.05));margin-right:4px;';
    copyVacancyBtn.addEventListener('click', async (e) => {
      e.stopPropagation();
      try {
        const url = getSelectedVacancyUrl();
        if (!url) return;
        await navigator.clipboard.writeText(url);
        copyVacancyBtn.classList.add('hrhelper-copy-btn-copied');
        copyVacancyBtn.style.borderColor = 'var(--hrhelper-success-border)';
        copyVacancyBtn.style.color = 'var(--hrhelper-success)';
        copyVacancyBtn.style.background = 'var(--hrhelper-success-bg)';
        copyVacancyBtn.title = 'Скопировано';
        setTimeout(() => {
          copyVacancyBtn.classList.remove('hrhelper-copy-btn-copied');
          copyVacancyBtn.style.borderColor = '';
          copyVacancyBtn.style.color = '';
          copyVacancyBtn.style.background = '';
          copyVacancyBtn.title = 'Скопировать ссылку';
        }, 1500);
      } catch (_) {}
    });

    const toggleBtn = document.createElement('button');
    toggleBtn.type = 'button';
    toggleBtn.className = 'hrhelper-toggle-btn';
    toggleBtn.title = 'Свернуть / развернуть';
    toggleBtn.style.cssText = 'width:24px;height:24px;border:none;background:var(--hrhelper-btn-bg,rgba(0,0,0,.05));border-radius:4px;cursor:pointer;color:var(--hrhelper-muted,#666);flex-shrink:0;padding:0;display:flex;align-items:center;justify-content:center;';
    toggleBtn.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path class="hrhelper-toggle-icon-path" d="M7.41 15.41L12 10.83l4.59 4.58L18 14l-6-6-6 6z"/></svg>';

    header.appendChild(headerLeft);
    header.appendChild(copyVacancyBtn);
    header.appendChild(actionGroup);
    header.appendChild(toggleBtn);
    wrapper.appendChild(header);

    const body = document.createElement('div');
    body.className = 'hrhelper-widget-body';
    body.style.cssText = 'display:flex;flex-direction:column;gap:8px;flex:1;min-height:0;min-width:0;overflow-y:auto;overflow-x:hidden;word-break:break-word;overflow-wrap:break-word;color:inherit;padding-top:8px;';
    wrapper.appendChild(body);

    const isCollapsed = !!floatingWidgetUIState.widgetCollapsed;
    body.style.display = isCollapsed ? 'none' : 'flex';
    const togglePath = toggleBtn.querySelector('.hrhelper-toggle-icon-path');
    if (togglePath) togglePath.setAttribute('d', isCollapsed ? 'M7.41 8.59L12 13.17l4.59-4.58L18 10l-6 6-6-6z' : 'M7.41 15.41L12 10.83l4.59 4.58L18 14l-6-6-6 6z');
    toggleBtn.addEventListener('click', () => {
      const willExpand = body.style.display === 'none';
      body.style.display = willExpand ? 'flex' : 'none';
      const pathEl = toggleBtn.querySelector('.hrhelper-toggle-icon-path');
      if (pathEl) pathEl.setAttribute('d', willExpand ? 'M7.41 15.41L12 10.83l4.59 4.58L18 14l-6-6-6 6z' : 'M7.41 8.59L12 13.17l4.59-4.58L18 10l-6 6-6-6z');
      saveFloatingUIState({ widgetCollapsed: !willExpand });
    });

    floatingWidgetData = { wrapper, body, titleText, titleIcon, actionGroup, addVacancyBtn, huntflowBtn, floatingEditBtn, copyVacancyBtn, toggleBtn };
    return floatingWidgetData;
  }

  function makeWidgetDraggable(wrapper) {
    if (!wrapper) return;
    try {
      const saved = localStorage.getItem(FLOATING_POS_KEY);
      if (saved) {
        const obj = JSON.parse(saved);
        if (typeof obj.top === 'number' && typeof obj.left === 'number') {
          wrapper.style.top = Math.max(8, obj.top) + 'px';
          wrapper.style.left = Math.max(8, obj.left) + 'px';
          wrapper.style.right = 'auto';
        }
      }
    } catch (_) {}

    const header = wrapper.querySelector('.hrhelper-widget-header');
    if (!header) return;
    let drag = null;
    header.addEventListener('mousedown', (e) => {
      if (e.target.closest('button')) return;
      drag = { startX: e.clientX, startY: e.clientY, origTop: wrapper.getBoundingClientRect().top, origLeft: wrapper.getBoundingClientRect().left };
      document.addEventListener('mousemove', move);
      document.addEventListener('mouseup', stop);
    });
    function move(e) {
      if (!drag) return;
      wrapper.style.top = Math.max(8, drag.origTop + e.clientY - drag.startY) + 'px';
      wrapper.style.left = Math.max(8, drag.origLeft + e.clientX - drag.startX) + 'px';
      wrapper.style.right = 'auto';
    }
    function stop() {
      if (!drag) return;
      document.removeEventListener('mousemove', move);
      document.removeEventListener('mouseup', stop);
      try { localStorage.setItem(FLOATING_POS_KEY, JSON.stringify({ top: wrapper.getBoundingClientRect().top, left: wrapper.getBoundingClientRect().left })); } catch (_) {}
      drag = null;
    }
  }

  function updateFloatingWidgetTitleIcon() {
    const icon = floatingWidgetData?.titleIcon;
    if (!icon) return;
    const isBlacklist = hasBlacklistLabel && hasBlacklistLabel(candidateInfo);
    try {
      icon.src = isBlacklist ? chrome.runtime.getURL('icons/dark-label.png') : chrome.runtime.getURL('icons/icon-32.png');
      const size = isBlacklist ? 30 : 20;
      icon.width = size; icon.height = size;
    } catch (_) {}
  }

  function updateFloatingWidgetHeader() {
    const { titleText, addVacancyBtn, huntflowBtn, floatingEditBtn, copyVacancyBtn } = floatingWidgetData || {};
    if (!titleText) return;
    const hasFio = candidateInfo?.full_name && currentLinkInfo?.found;
    titleText.textContent = hasFio ? candidateInfo.full_name : 'HR Helper';
    const showActions = currentLinkInfo?.found && currentLinkInfo?.huntflow_url;
    const showEditBtn = showActions || !currentLinkInfo?.found;
    if (addVacancyBtn) {
      addVacancyBtn.style.display = showActions ? 'flex' : 'none';
      if (!addVacancyBtn._bound) {
        addVacancyBtn._bound = true;
        addVacancyBtn.addEventListener('click', onAddVacancyClick);
      }
    }
    if (huntflowBtn) {
      huntflowBtn.style.display = showActions ? 'flex' : 'none';
      huntflowBtn.onclick = () => { const url = getSelectedVacancyUrl(); if (url) window.open(url, '_blank'); };
    }
    if (floatingEditBtn) {
      floatingEditBtn.style.display = showEditBtn ? 'flex' : 'none';
      floatingEditBtn.onclick = onEditClick;
    }
    if (copyVacancyBtn) {
      copyVacancyBtn.style.display = showActions ? 'flex' : 'none';
    }
  }

  async function onAddVacancyClick(e) {
    e?.stopPropagation?.();
    const dropdown = document.querySelector('.hrhelper-add-vacancy-dropdown');
    if (dropdown) { dropdown.remove(); return; }
    const dd = document.createElement('div');
    dd.className = 'hrhelper-add-vacancy-dropdown';
    dd.style.cssText = 'position:absolute;right:0;top:100%;background:var(--hrhelper-bg,#fff);border:1px solid var(--hrhelper-border,rgba(0,0,0,.2));border-radius:8px;box-shadow:0 4px 12px rgba(0,0,0,.15);z-index:100002;min-width:200px;max-width:280px;max-height:220px;overflow-y:auto;padding:8px 0;';
    dd.innerHTML = '<div style="padding:12px;color:var(--hrhelper-muted);">Загрузка...</div>';
    floatingWidgetData?.wrapper?.appendChild(dd);
    const data = await fetchAvailableVacancies(currentLinkInfo?.huntflow_url);
    if (!data?.success || !data.items?.length) {
      dd.innerHTML = '<div style="padding:12px;color:var(--hrhelper-muted);">Нет доступных вакансий</div>';
      return;
    }
    dd.innerHTML = '';
    data.items.forEach(v => {
      const item = document.createElement('div');
      item.style.cssText = 'padding:8px 12px;cursor:pointer;font-size:13px;';
      item.textContent = v.vacancy_name || `#${v.vacancy_id}`;
      item.addEventListener('mouseenter', () => { item.style.background = 'var(--hrhelper-btn-bg)'; });
      item.addEventListener('mouseleave', () => { item.style.background = ''; });
      item.addEventListener('click', async () => {
        dd.remove();
        const result = await addToVacancy(currentLinkInfo.huntflow_url, v.vacancy_id);
        if (result?.success) { await refreshData(); populateFloatingWidgetBody(); }
      });
      dd.appendChild(item);
    });
    document.addEventListener('click', function handler(ev) {
      if (!dd.contains(ev.target) && !floatingWidgetData?.addVacancyBtn?.contains(ev.target)) {
        dd.remove();
        document.removeEventListener('click', handler);
      }
    });
  }

  function onEditClick(e) {
    e?.stopPropagation?.();
    isEditMode = true;
    populateFloatingWidgetBody();
  }

  function populateFloatingWidgetBody() {
    const body = floatingWidgetData?.body;
    if (!body) return;
    body.innerHTML = '';
    updateFloatingWidgetHeader();
    updateFloatingWidgetTitleIcon();
    applyFloatingBorder(floatingWidgetData?.wrapper, computeFloatingBorderColor());

    if (isEditMode) {
      renderEditMode(body);
      return;
    }

    if (!currentLinkInfo?.found) {
      renderUnlinkedState(body);
      return;
    }

    renderLinkedState(body);
  }

  function renderLinkedState(body) {
    const btnStyle = 'padding:8px 12px;border:none;border-radius:6px;cursor:pointer;font-size:12px;';
    const info = candidateInfo;
    const vacs = vacancies || [];
    const { active, rejected, archived, hired } = categorizeVacancies(vacs);

    const hasContacts = info && (info.phone || info.email || info.telegram || info.communication);
    if (hasContacts) {
      const open = !!floatingWidgetUIState.candidateDataOpen;
      const toggle = document.createElement('button');
      toggle.type = 'button';
      toggle.className = 'hrhelper-body-accent';
      toggle.style.cssText = 'font-size:12px;background:none;border:none;cursor:pointer;padding:4px 0;margin-bottom:4px;text-align:left;';
      toggle.textContent = open ? 'Контакты и коммуникация ▲' : 'Контакты и коммуникация ▼';
      const details = document.createElement('div');
      details.className = 'hrhelper-body-muted';
      details.style.cssText = 'font-size:11px;margin-bottom:8px;padding:8px;background:var(--hrhelper-btn-bg,rgba(0,0,0,.03));border-radius:6px;display:' + (open ? 'block' : 'none') + ';';
      const contactRows = [];
      if (info.phone) contactRows.push({ label: 'Телефон', html: '<a href="tel:' + escapeHtml(info.phone) + '">' + escapeHtml(info.phone) + '</a>' });
      if (info.email) contactRows.push({ label: 'Email', html: '<a href="mailto:' + escapeHtml(info.email) + '">' + escapeHtml(info.email) + '</a>' });
      contactRows.push({ label: 'Google Drive', html: '<a href="' + escapeHtml(location.href) + '" target="_blank">' + escapeHtml(location.href.length > 50 ? location.href.slice(0, 50) + '...' : location.href) + '</a>' });
      if (info.telegram) {
        const t = String(info.telegram).trim();
        const telegramHref = /^https?:\/\//i.test(t) ? t : 'https://t.me/' + t.replace(/^@/, '');
        contactRows.push({ label: 'Telegram', html: '<a href="' + escapeHtml(telegramHref) + '" target="_blank">' + escapeHtml(t) + '</a>' });
      }
      if (info.communication) contactRows.push({ label: 'Коммуникация', html: escapeHtml(info.communication) });
      details.innerHTML = contactRows.map(r => '<div><b>' + escapeHtml(r.label) + ':</b> ' + r.html + '</div>').join('');
      toggle.addEventListener('click', () => {
        const nowOpen = details.style.display !== 'none';
        details.style.display = nowOpen ? 'none' : 'block';
        toggle.textContent = nowOpen ? 'Контакты и коммуникация ▼' : 'Контакты и коммуникация ▲';
        saveFloatingUIState({ candidateDataOpen: !nowOpen });
      });
      body.appendChild(toggle);
      body.appendChild(details);
    }

    const excludeLevelKey = /^уровень$|^level$/i;
    const extraFieldsEntries = info?.extra_fields && typeof info.extra_fields === 'object'
      ? Object.entries(info.extra_fields).filter(([k, v]) => v != null && v !== '' && !excludeLevelKey.test(String(k).trim()))
      : [];
    if (extraFieldsEntries.length > 0) {
      const openExtra = !!floatingWidgetUIState.extraFieldsOpen;
      const toggleExtra = document.createElement('button');
      toggleExtra.type = 'button';
      toggleExtra.className = 'hrhelper-body-accent';
      toggleExtra.style.cssText = 'font-size:12px;background:none;border:none;cursor:pointer;padding:4px 0;margin-bottom:4px;text-align:left;';
      toggleExtra.textContent = openExtra ? 'Дополнительные поля ▲' : 'Дополнительные поля ▼';
      const extraBlock = document.createElement('div');
      extraBlock.className = 'hrhelper-body-muted';
      extraBlock.style.cssText = 'font-size:11px;margin-bottom:8px;padding:8px;background:var(--hrhelper-btn-bg,rgba(0,0,0,.03));border-radius:6px;display:' + (openExtra ? 'block' : 'none') + ';';
      extraBlock.innerHTML = extraFieldsEntries.map(([l, v]) => '<div><b>' + escapeHtml(l) + ':</b> ' + escapeHtml(String(v)) + '</div>').join('');
      toggleExtra.addEventListener('click', () => {
        const nowOpen = extraBlock.style.display !== 'none';
        extraBlock.style.display = nowOpen ? 'none' : 'block';
        toggleExtra.textContent = nowOpen ? 'Дополнительные поля ▼' : 'Дополнительные поля ▲';
        saveFloatingUIState({ extraFieldsOpen: !nowOpen });
      });
      body.appendChild(toggleExtra);
      body.appendChild(extraBlock);
    }

    if (info?.labels?.length > 0) {
      const labelsWrap = document.createElement('div');
      labelsWrap.style.cssText = 'display:flex;flex-wrap:wrap;gap:4px;margin-bottom:8px;';
      info.labels.forEach(lbl => {
        const name = (typeof lbl === 'string' ? lbl : (lbl?.name || lbl?.title)) || '';
        if (!name) return;
        const tag = document.createElement('span');
        tag.style.cssText = 'font-size:11px;padding:2px 8px;border-radius:4px;background:var(--hrhelper-btn-bg,rgba(0,0,0,.06));border:1px solid var(--hrhelper-border,rgba(0,0,0,.1));';
        const rawColor = (lbl && typeof lbl === 'object' && (lbl.color || lbl.background_color || lbl.bg_color)) || '';
        const color = rawColor ? normalizeLabelColor(String(rawColor)) : '';
        if (color) { tag.style.borderColor = color; tag.style.color = color; }
        tag.textContent = name;
        labelsWrap.appendChild(tag);
      });
      body.appendChild(labelsWrap);
    }

    if (hired.length > 0) {
      const badge = document.createElement('div');
      badge.className = 'hrhelper-body-success';
      badge.style.cssText = 'padding:8px;background:var(--hrhelper-success-bg);border:1px solid var(--hrhelper-success-border);border-radius:6px;font-size:12px;font-weight:600;';
      badge.textContent = '✅ Сотрудник';
      body.appendChild(badge);
    } else if (active.length > 0 || rejected.length > 0 || archived.length > 0) {
      const selId = selectedVacancyId ?? defaultVacancyId;
      if (active.length > 0) {
        const activeTitle = document.createElement('div');
        activeTitle.className = 'hrhelper-body-muted';
        activeTitle.style.cssText = 'font-size:11px;font-weight:600;margin:8px 0 4px 0;';
        activeTitle.textContent = 'Активные вакансии';
        body.appendChild(activeTitle);
        active.forEach(v => {
          const card = document.createElement('div');
          const isSel = v.vacancy_id === selId;
          const cardBorderColor = computeBorderColorForVacancy(v) || (isSel ? 'var(--hrhelper-card-sel-border)' : 'var(--hrhelper-card-border)');
          const cardBg = isSel ? 'var(--hrhelper-card-sel-bg)' : 'var(--hrhelper-card-bg)';
          card.style.cssText = 'padding:8px 10px;margin-bottom:4px;border-radius:6px;font-size:12px;cursor:pointer;border:1px solid ' + cardBorderColor + ';background:' + cardBg + ';display:flex;align-items:center;justify-content:space-between;gap:8px;';
          const left = document.createElement('span');
          left.style.cssText = 'min-width:0;flex:1;';
          left.textContent = (isSel ? '✓ ' : '') + (v.vacancy_name || '—') + (v.status_name ? ' (' + v.status_name + ')' : '');
          const dateSpan = document.createElement('span');
          dateSpan.className = 'hrhelper-body-muted';
          dateSpan.style.cssText = 'font-size:10px;flex-shrink:0;';
          dateSpan.textContent = formatVacancyDate(v.last_change_at);
          card.appendChild(left);
          card.appendChild(dateSpan);
          card.addEventListener('click', () => { selectedVacancyId = v.vacancy_id; populateFloatingWidgetBody(); });
          body.appendChild(card);
        });
      }
      if (rejected.length > 0) {
        const rejTitle = document.createElement('div');
        rejTitle.className = 'hrhelper-body-danger';
        rejTitle.style.cssText = 'font-size:11px;font-weight:600;margin:8px 0 4px 0;';
        rejTitle.textContent = '❌ Отказы';
        body.appendChild(rejTitle);
        rejected.forEach(v => {
          const card = document.createElement('div');
          card.style.cssText = 'padding:8px 10px;margin-bottom:4px;border-radius:6px;font-size:12px;cursor:pointer;border:1px solid var(--hrhelper-danger-border);background:var(--hrhelper-danger-bg);color:var(--hrhelper-danger);display:flex;align-items:center;justify-content:space-between;gap:8px;';
          const left = document.createElement('div');
          left.textContent = (v.vacancy_name || '—') + (v.rejection_reason_name ? ' — ' + v.rejection_reason_name : '');
          const dateSpan = document.createElement('span');
          dateSpan.style.cssText = 'font-size:10px;opacity:.9;flex-shrink:0;';
          dateSpan.textContent = formatVacancyDate(v.last_change_at);
          card.appendChild(left);
          card.appendChild(dateSpan);
          card.addEventListener('click', () => { selectedVacancyId = v.vacancy_id; populateFloatingWidgetBody(); });
          body.appendChild(card);
        });
      }
      if (archived.length > 0) {
        const archTitle = document.createElement('div');
        archTitle.className = 'hrhelper-body-muted';
        archTitle.style.cssText = 'font-size:11px;font-weight:600;margin:8px 0 4px 0;';
        archTitle.textContent = 'Архивные вакансии';
        body.appendChild(archTitle);
        archived.forEach(v => {
          const card = document.createElement('div');
          const isSel = v.vacancy_id === selId;
          const borderColor = isSel ? 'var(--hrhelper-card-sel-border)' : 'var(--hrhelper-border)';
          const bgColor = isSel ? 'var(--hrhelper-card-sel-bg)' : 'var(--hrhelper-btn-bg)';
          card.style.cssText = 'padding:8px 10px;margin-bottom:4px;border-radius:6px;font-size:12px;cursor:pointer;border:1px solid ' + borderColor + ';background:' + bgColor + ';display:flex;align-items:center;justify-content:space-between;gap:8px;';
          const left = document.createElement('span');
          left.style.cssText = 'min-width:0;flex:1;';
          left.textContent = (isSel ? '✓ ' : '') + (v.vacancy_name || '—') + (v.status_name ? ' (' + v.status_name + ')' : '');
          const dateSpan = document.createElement('span');
          dateSpan.className = 'hrhelper-body-muted';
          dateSpan.style.cssText = 'font-size:10px;flex-shrink:0;';
          dateSpan.textContent = formatVacancyDate(v.last_change_at);
          card.appendChild(left);
          card.appendChild(dateSpan);
          card.addEventListener('click', () => { selectedVacancyId = v.vacancy_id; populateFloatingWidgetBody(); });
          body.appendChild(card);
        });
      }
    }

    appendFloatingStatusBlock(body, btnStyle);
    appendFloatingCommentsBlock(body);
  }

  function appendFloatingCommentsBlock(body) {
    const selId = selectedVacancyId ?? defaultVacancyId;
    const vacancy = (vacancies || []).find(v => v.vacancy_id === selId);
    const comments = vacancy?.comments || [];
    if (comments.length === 0) return;

    const isArchived = !!(vacancy?.is_archived);
    const vacancyNameForTitle = (vacancy.vacancy_name && String(vacancy.vacancy_name).trim()) || 'вакансии';
    const commentsTitle = isArchived ? 'Комментарии к ' + vacancyNameForTitle + ' (архив)' : 'Последние комментарии';
    const expanded = isArchived ? false : !!floatingWidgetUIState.commentsOpen;

    const block = document.createElement('div');
    block.className = 'hrhelper-comments-block';
    block.style.cssText = 'margin-top:12px;padding-top:10px;border-top:1px solid var(--hrhelper-border,rgba(0,0,0,.1));';

    const header = document.createElement('div');
    header.className = 'hrhelper-body-accent';
    header.style.cssText = 'display:flex;align-items:center;gap:6px;cursor:pointer;user-select:none;font-size:12px;font-weight:600;margin-bottom:8px;';
    const chevronSpan = document.createElement('span');
    chevronSpan.className = 'hrhelper-comments-chevron';
    chevronSpan.style.cssText = 'transition:transform .2s;';
    chevronSpan.textContent = '▼';
    header.appendChild(chevronSpan);
    header.appendChild(document.createTextNode(' ' + commentsTitle));

    const list = document.createElement('div');
    list.style.cssText = 'display:flex;flex-direction:column;gap:8px;';
    list.style.display = expanded ? 'flex' : 'none';
    chevronSpan.style.transform = expanded ? 'rotate(0deg)' : 'rotate(-90deg)';
    header.addEventListener('click', () => {
      const next = list.style.display === 'none';
      list.style.display = next ? 'flex' : 'none';
      chevronSpan.style.transform = next ? 'rotate(0deg)' : 'rotate(-90deg)';
      saveFloatingUIState({ commentsOpen: next });
    });
    block.appendChild(header);

    comments.forEach(c => {
      const item = document.createElement('div');
      item.style.cssText = 'font-size:11px;padding:8px;background:var(--hrhelper-btn-bg,rgba(0,0,0,.03));border-radius:6px;border-left:3px solid var(--hrhelper-accent,#0a66c2);color:var(--hrhelper-text);';
      const meta = document.createElement('div');
      meta.className = 'hrhelper-body-muted';
      meta.style.cssText = 'font-size:10px;margin-bottom:4px;';
      const metaParts = [];
      if (c.author) metaParts.push(c.author);
      if (c.created) metaParts.push(formatCommentDate(c.created));
      meta.textContent = metaParts.join(' · ');
      item.appendChild(meta);
      const text = document.createElement('div');
      text.style.cssText = 'line-height:1.4;word-break:break-word;white-space:pre-wrap;';
      let raw = (c.text || '').replace(/<[^>]*>/g, '').replace(/&nbsp;/g, ' ').trim();
      try { const tmp = document.createElement('textarea'); tmp.innerHTML = raw; raw = tmp.value; } catch (_) {}
      text.textContent = raw || '—';
      item.appendChild(text);
      list.appendChild(item);
    });

    block.appendChild(list);
    body.appendChild(block);
  }

  function isRejectionStatusOption(opt) {
    if (!opt || !opt.value) return false;
    const type = (opt.dataset?.type || '').toLowerCase();
    const name = (opt.dataset?.name || opt.textContent || '').toLowerCase();
    return type === 'rejected' || type === 'trash' || name.includes('отказ') || name.includes('reject');
  }

  function appendFloatingStatusBlock(body, btnStyle) {
    const block = document.createElement('div');
    block.className = 'hrhelper-ctx-status-block';
    block.style.cssText = 'margin-top:12px;padding-top:10px;border-top:1px solid var(--hrhelper-border,rgba(0,0,0,.1));';

    const formLabel = document.createElement('span');
    formLabel.className = 'hrhelper-ctx-label';
    formLabel.style.cssText = 'display:block;margin-bottom:6px;font-size:12px;font-weight:600;';
    formLabel.textContent = 'Изменение статуса / Причина';
    block.appendChild(formLabel);

    const loadMsg = document.createElement('p');
    loadMsg.className = 'hrhelper-status-load-msg hrhelper-body-muted';
    loadMsg.style.cssText = 'margin:0 0 6px 0;font-size:11px;display:none;';
    block.appendChild(loadMsg);

    const statusRow = document.createElement('div');
    statusRow.style.cssText = 'display:flex;align-items:center;gap:8px;margin-bottom:8px;';
    const statusSelect = document.createElement('select');
    statusSelect.className = 'hrhelper-ctx-status-select';
    statusSelect.innerHTML = '<option value="">— Статус —</option>';
    statusSelect.style.cssText = 'flex:1;min-width:0;padding:8px 10px;font-size:12px;border:1px solid var(--hrhelper-border);border-radius:6px;background:var(--hrhelper-input-bg);color:var(--hrhelper-text);';
    const nextBtn = document.createElement('button');
    nextBtn.type = 'button';
    nextBtn.className = 'hrhelper-ctx-status-next';
    nextBtn.title = 'Следующий статус';
    nextBtn.style.cssText = 'width:36px;height:36px;padding:0;border:1px solid var(--hrhelper-border);border-radius:6px;background:var(--hrhelper-input-bg);color:var(--hrhelper-accent);cursor:pointer;flex-shrink:0;';
    nextBtn.innerHTML = '<svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor"><path d="M10 6L8.59 7.41 13.17 12l-4.58 4.59L10 18l6-6z"/></svg>';
    statusRow.appendChild(statusSelect);
    statusRow.appendChild(nextBtn);
    block.appendChild(statusRow);

    const reasonRow = document.createElement('div');
    reasonRow.className = 'hrhelper-ctx-reason-row';
    reasonRow.style.cssText = 'margin-bottom:8px;display:none;';
    const reasonSelect = document.createElement('select');
    reasonSelect.className = 'hrhelper-ctx-reason-select';
    reasonSelect.innerHTML = '<option value="">— Причина отказа —</option>';
    reasonSelect.style.cssText = 'width:100%;padding:8px 10px;font-size:12px;border:1px solid var(--hrhelper-border);border-radius:6px;background:var(--hrhelper-input-bg);color:var(--hrhelper-text);box-sizing:border-box;';
    reasonRow.appendChild(reasonSelect);
    block.appendChild(reasonRow);

    const commentRow = document.createElement('div');
    commentRow.style.cssText = 'margin-bottom:8px;';
    const commentLabel = document.createElement('label');
    commentLabel.className = 'hrhelper-ctx-label';
    commentLabel.style.cssText = 'display:block;margin-bottom:6px;font-size:12px;font-weight:600;';
    commentLabel.textContent = 'Комментарий';
    commentRow.appendChild(commentLabel);
    const commentWrap = document.createElement('div');
    commentWrap.className = 'hrhelper-ctx-comment-wrap';
    commentWrap.style.cssText = 'border:1px solid var(--hrhelper-border);border-radius:6px;overflow:hidden;background:var(--hrhelper-input-bg);';
    const toolbar = document.createElement('div');
    toolbar.className = 'hrhelper-ctx-comment-toolbar';
    toolbar.style.cssText = 'display:flex;gap:4px;padding:4px 6px;border-bottom:1px solid var(--hrhelper-border);flex-wrap:wrap;';
    const toolbarBtns = [
      { cmd: 'bold', title: 'Жирный', html: '<b>B</b>' },
      { cmd: 'italic', title: 'Курсив', html: '<i>I</i>' },
      { cmd: 'insertUnorderedList', title: 'Маркированный список', html: '•' },
      { cmd: 'insertOrderedList', title: 'Нумерованный список', html: '1.' },
      { cmd: 'createLink', title: 'Вставить ссылку', html: '🔗' }
    ];
    const commentEditor = document.createElement('div');
    commentEditor.className = 'hrhelper-ctx-comment-editor';
    commentEditor.contentEditable = 'true';
    commentEditor.dataset.placeholder = 'Добавить комментарий к статусу...';
    commentEditor.style.cssText = 'min-height:60px;max-height:120px;overflow-y:auto;padding:8px 10px;font-size:12px;border:none;background:var(--hrhelper-input-bg);color:var(--hrhelper-text);line-height:1.5;box-sizing:border-box;';
    toolbarBtns.forEach(({ cmd, title, html }) => {
      const b = document.createElement('button');
      b.type = 'button';
      b.className = 'hrhelper-ctx-comment-toolbar-btn';
      b.style.cssText = 'width:28px;height:24px;padding:0;border:1px solid var(--hrhelper-border);border-radius:4px;background:var(--hrhelper-input-bg);color:var(--hrhelper-text);cursor:pointer;font-size:11px;display:inline-flex;align-items:center;justify-content:center;';
      b.title = title;
      b.innerHTML = html;
      b.addEventListener('click', (e) => {
        e.preventDefault();
        if (cmd === 'createLink') {
          const url = prompt('Введите URL:');
          if (url) document.execCommand(cmd, false, url);
        } else {
          document.execCommand(cmd, false, null);
        }
        commentEditor.focus();
      });
      toolbar.appendChild(b);
    });
    commentWrap.appendChild(toolbar);
    commentWrap.appendChild(commentEditor);
    commentRow.appendChild(commentWrap);
    block.appendChild(commentRow);

    const applyBtn = document.createElement('button');
    applyBtn.type = 'button';
    applyBtn.className = 'hrhelper-ctx-apply-status';
    applyBtn.textContent = 'Применить статус';
    applyBtn.style.cssText = btnStyle + 'background:var(--hrhelper-input-bg);color:var(--hrhelper-text);width:100%;border:1px solid var(--hrhelper-border);';
    block.appendChild(applyBtn);

    const toggleReasonRow = () => {
      const sel = statusSelect.options[statusSelect.selectedIndex];
      reasonRow.style.display = (sel && sel.value && isRejectionStatusOption(sel)) ? 'block' : 'none';
    };
    statusSelect.addEventListener('change', toggleReasonRow);

    nextBtn.addEventListener('click', () => {
      const opts = Array.from(statusSelect.options).filter(o => o.value !== '');
      if (opts.length < 2) return;
      const idx = opts.findIndex(o => o.value === statusSelect.value);
      const nextIdx = idx < 0 ? 0 : (idx + 1) % opts.length;
      statusSelect.value = opts[nextIdx].value;
      toggleReasonRow();
    });

    applyBtn.addEventListener('click', async () => {
      if (!statusSelect.value) {
        loadMsg.textContent = 'Выберите статус.';
        loadMsg.style.display = 'block';
        loadMsg.style.color = '#842029';
        return;
      }
      const sel = statusSelect.options[statusSelect.selectedIndex];
      const needReason = sel && isRejectionStatusOption(sel);
      const rejectionReasonId = reasonSelect.value?.trim() || null;
      if (needReason && !rejectionReasonId) {
        loadMsg.textContent = 'Для статуса отказа выберите причину.';
        loadMsg.style.display = 'block';
        loadMsg.style.color = '#842029';
        return;
      }
      const commentHtml = (commentEditor.innerHTML || '').trim();
      const comment = commentHtml === '<br>' || commentHtml === '<br/>' ? '' : commentHtml;
      applyBtn.disabled = true;
      applyBtn.textContent = 'Сохранение…';
      loadMsg.style.display = 'none';
      try {
        const vid = selectedVacancyId ?? defaultVacancyId;
        const result = await updateStatus(currentLinkInfo?.huntflow_url, parseInt(statusSelect.value, 10), rejectionReasonId ? parseInt(rejectionReasonId, 10) : null, vid, comment);
        if (result?.success) {
          commentEditor.innerHTML = '';
          loadMsg.textContent = 'Статус обновлён.';
          loadMsg.style.color = '#0f5132';
          loadMsg.style.display = 'block';
          setTimeout(() => { loadMsg.style.display = 'none'; }, 2000);
          await refreshData();
          populateFloatingWidgetBody();
        } else {
          throw new Error(result?.message || 'Ошибка');
        }
      } catch (e) {
        loadMsg.textContent = e.message || 'Ошибка';
        loadMsg.style.color = '#842029';
        loadMsg.style.display = 'block';
      }
      applyBtn.disabled = false;
      applyBtn.textContent = 'Применить статус';
    });

    body.appendChild(block);
    loadFloatingStatusOptions(statusSelect, reasonSelect, loadMsg);
  }

  async function loadFloatingStatusOptions(statusSelect, reasonSelect, loadMsg) {
    if (!currentLinkInfo?.huntflow_url) return;
    loadMsg.textContent = 'Загрузка списка статусов...';
    loadMsg.style.display = 'block';
    loadMsg.style.color = '#6c757d';
    try {
      const data = await fetchStatusOptions(currentLinkInfo.huntflow_url);
      if (!data?.success) {
        loadMsg.textContent = data?.message || 'Не удалось загрузить список статусов.';
        loadMsg.style.color = '#842029';
        return;
      }
      const statuses = data.statuses || [];
      const rejectionReasons = data.rejection_reasons || [];
      const currentVacancy = (vacancies || []).find(v => v.vacancy_id === (selectedVacancyId ?? defaultVacancyId));
      statusSelect.innerHTML = '<option value="">— Статус —</option>';
      reasonSelect.innerHTML = '<option value="">— Причина отказа —</option>';
      statuses.forEach(s => {
        const opt = document.createElement('option');
        opt.value = s.id;
        opt.textContent = s.name || `Статус #${s.id}`;
        opt.dataset.type = (s.type || '').toLowerCase();
        opt.dataset.name = (s.name || '').toLowerCase();
        statusSelect.appendChild(opt);
      });
      if (currentVacancy?.status_id != null) {
        const hasOpt = Array.from(statusSelect.options).some(o => o.value === String(currentVacancy.status_id));
        if (hasOpt) statusSelect.value = String(currentVacancy.status_id);
      }
      rejectionReasons.forEach(r => {
        const opt = document.createElement('option');
        opt.value = r.id;
        opt.textContent = r.name || `Причина #${r.id}`;
        reasonSelect.appendChild(opt);
      });
      if (currentVacancy?.rejection_reason_id != null) {
        const hasOpt = Array.from(reasonSelect.options).some(o => o.value === String(currentVacancy.rejection_reason_id));
        if (hasOpt) reasonSelect.value = String(currentVacancy.rejection_reason_id);
      }
      loadMsg.style.display = 'none';
    } catch (e) {
      loadMsg.textContent = 'Ошибка загрузки статусов.';
      loadMsg.style.color = '#842029';
    }
  }

  function renderEditMode(body) {
    const btnStyle = 'padding:8px 12px;border:none;border-radius:6px;cursor:pointer;font-size:12px;';
    const inputRow = document.createElement('div');
    inputRow.style.cssText = 'display:flex;gap:8px;align-items:stretch;margin-bottom:8px;';
    const input = document.createElement('input');
    input.type = 'url';
    input.placeholder = 'https://huntflow.ru/my/...';
    input.value = currentLinkInfo?.huntflow_url || '';
    input.style.cssText = 'flex:1;min-width:0;padding:8px 10px;font-size:12px;border:1px solid var(--hrhelper-border);border-radius:6px;background:var(--hrhelper-input-bg);color:var(--hrhelper-text);';
    const saveBtn = document.createElement('button');
    saveBtn.type = 'button';
    saveBtn.textContent = 'Сохранить';
    saveBtn.style.cssText = btnStyle + 'background:var(--hrhelper-accent);color:#fff;';
    inputRow.appendChild(input);
    inputRow.appendChild(saveBtn);
    body.appendChild(inputRow);

    const desc = document.createElement('div');
    desc.className = 'hrhelper-body-muted';
    desc.style.cssText = 'font-size:11px;margin-bottom:8px;';
    desc.textContent = 'Вставьте ссылку на кандидата в Huntflow и нажмите «Сохранить».';
    body.appendChild(desc);

    const cancelBtn = document.createElement('button');
    cancelBtn.type = 'button';
    cancelBtn.textContent = 'Отмена';
    cancelBtn.style.cssText = btnStyle + 'background:var(--hrhelper-btn-bg);color:var(--hrhelper-text);border:1px solid var(--hrhelper-border);';
    cancelBtn.onclick = () => { isEditMode = false; populateFloatingWidgetBody(); };
    body.appendChild(cancelBtn);

    const errorDiv = document.createElement('div');
    errorDiv.className = 'hrhelper-body-danger';
    errorDiv.style.cssText = 'display:none;margin-top:8px;font-size:11px;padding:8px;background:var(--hrhelper-danger-bg);border-radius:6px;';
    body.appendChild(errorDiv);

    saveBtn.onclick = async () => {
      const url = input.value.trim();
      if (!url) { errorDiv.textContent = 'Введите ссылку'; errorDiv.style.display = 'block'; return; }
      saveBtn.disabled = true;
      saveBtn.textContent = 'Сохранение...';
      const result = await updateGDriveLink(currentFileId, url);
      if (result?.success) {
        currentLinkInfo = { ...currentLinkInfo, huntflow_url: url, found: true };
        isEditMode = false;
        await refreshData();
        populateFloatingWidgetBody();
      } else {
        errorDiv.textContent = result?.error || result?.message || 'Ошибка сохранения';
        errorDiv.style.display = 'block';
        saveBtn.disabled = false;
        saveBtn.textContent = 'Сохранить';
      }
    };

    input.focus();
  }

  async function renderUnlinkedState(body) {
    const btnStyle = 'padding:8px 12px;border:none;border-radius:6px;cursor:pointer;font-size:12px;';
    const desc = document.createElement('div');
    desc.className = 'hrhelper-body-muted';
    desc.style.cssText = 'font-size:12px;margin-bottom:12px;';
    desc.textContent = 'Этот файл ещё не добавлен в Huntflow. Выберите вакансию или укажите ссылку вручную (✏️).';
    body.appendChild(desc);

    const selectLabel = document.createElement('div');
    selectLabel.className = 'hrhelper-body-muted';
    selectLabel.style.cssText = 'font-size:11px;font-weight:600;margin-bottom:6px;';
    selectLabel.textContent = 'Вакансия';
    body.appendChild(selectLabel);

    const select = document.createElement('select');
    select.style.cssText = 'width:100%;padding:8px 10px;font-size:12px;border:1px solid var(--hrhelper-border);border-radius:6px;background:var(--hrhelper-input-bg);color:var(--hrhelper-text);';
    select.innerHTML = '<option value="">— Загрузка... —</option>';
    select.disabled = true;
    body.appendChild(select);

    const addBtn = document.createElement('button');
    addBtn.type = 'button';
    addBtn.style.cssText = btnStyle + 'width:100%;margin-top:8px;background:var(--hrhelper-accent);color:#fff;';
    addBtn.textContent = 'Добавить в Huntflow';
    addBtn.disabled = true;
    body.appendChild(addBtn);

    const errorDiv = document.createElement('div');
    errorDiv.className = 'hrhelper-body-danger';
    errorDiv.style.cssText = 'display:none;margin-top:8px;font-size:11px;padding:8px;background:var(--hrhelper-danger-bg);border-radius:6px;';
    body.appendChild(errorDiv);

    const data = await fetchVacanciesActive();
    if (data?.vacancies?.length > 0) {
      select.innerHTML = '<option value="">— Выберите вакансию —</option>';
      data.vacancies.forEach(v => {
        const opt = document.createElement('option');
        opt.value = v.id;
        opt.textContent = v.position || v.name || `#${v.id}`;
        select.appendChild(opt);
      });
      select.disabled = false;
    } else {
      select.innerHTML = '<option value="">— Нет активных вакансий —</option>';
    }

    select.onchange = () => { addBtn.disabled = !select.value; };

    addBtn.onclick = async () => {
      if (!select.value) return;
      addBtn.disabled = true;
      addBtn.textContent = 'Обработка...';
      errorDiv.style.display = 'none';
      try {
        const result = await parseAndCreateCandidate(currentFileId, parseInt(select.value));
        if (result?.success) {
          currentLinkInfo = { found: true, huntflow_url: result.huntflow_url, candidate_name: result.full_name };
          await refreshData();
          populateFloatingWidgetBody();
        } else { throw new Error(result?.error || result?.message || 'Ошибка создания'); }
      } catch (e) {
        errorDiv.textContent = e.message;
        errorDiv.style.display = 'block';
        addBtn.disabled = !select.value;
        addBtn.textContent = 'Добавить в Huntflow';
      }
    };
  }

  async function refreshData() {
    if (!currentLinkInfo?.huntflow_url) return;
    const [infoData, multiData] = await Promise.all([
      fetchCandidateInfo(currentLinkInfo.huntflow_url),
      fetchStatusMulti(currentLinkInfo.huntflow_url)
    ]);
    if (infoData?.success) {
      candidateInfo = {
        full_name: infoData.full_name,
        phone: infoData.phone,
        email: infoData.email,
        telegram: infoData.telegram,
        communication: infoData.communication,
        office_readiness: infoData.office_readiness,
        level: infoData.level,
        labels: infoData.labels || [],
        extra_fields: infoData.extra_fields || {}
      };
    }
    if (multiData?.success && multiData.items) {
      vacancies = multiData.items;
      defaultVacancyId = multiData.default_vacancy_id || (vacancies[0]?.vacancy_id ?? null);
      if (!selectedVacancyId && vacancies.length > 0) {
        selectedVacancyId = defaultVacancyId;
      }
    }
  }

  async function initWidget() {
    const fileId = extractFileId();
    if (!fileId) {
      const existing = document.querySelector('[data-hrhelper-gdrive-floating]');
      if (existing) existing.remove();
      return;
    }
    if (fileId === currentFileId && document.querySelector('[data-hrhelper-gdrive-floating]')) return;

    currentFileId = fileId;
    selectedVacancyId = null;
    defaultVacancyId = null;
    candidateInfo = null;
    vacancies = [];
    isEditMode = false;

    const { wrapper } = createFloatingWidget();
    document.body.appendChild(wrapper);
    makeWidgetDraggable(wrapper);
    updateResolvedWidgetTheme();

    floatingWidgetData.body.innerHTML = '<div style="text-align:center;color:var(--hrhelper-muted);padding:20px;">Загрузка...</div>';

    try {
      const linkInfo = await fetchGDriveLink(fileId);
      currentLinkInfo = linkInfo;
      if (linkInfo?.found && linkInfo?.huntflow_url) {
        await refreshData();
      }
      populateFloatingWidgetBody();
    } catch (e) {
      floatingWidgetData.body.innerHTML = '<div style="color:var(--hrhelper-danger);padding:8px;">Ошибка: ' + escapeHtml(e.message) + '</div>';
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => setTimeout(initWidget, 800));
  } else {
    setTimeout(initWidget, 800);
  }

  let lastUrl = location.href;
  new MutationObserver(debounce(() => {
    if (location.href !== lastUrl) {
      lastUrl = location.href;
      currentFileId = null;
      initWidget();
    }
  }, 300)).observe(document, { subtree: true, childList: true });

  chrome.storage.onChanged.addListener((changes, area) => {
    if (area === 'local' && changes.hrhelper_gdrive_candidate_created) {
      const val = changes.hrhelper_gdrive_candidate_created.newValue;
      if (val?.fileId === extractFileId()) {
        currentFileId = null;
        setTimeout(initWidget, 500);
        chrome.storage.local.remove('hrhelper_gdrive_candidate_created');
      }
    }
    if (area === 'sync' && changes[OPTIONS_THEME_KEY]) {
      updateResolvedWidgetTheme();
    }
  });
})();
