const HRH = window.__HRH__;
if (!HRH) throw new Error("[HRHelper] shared/constants.js not loaded");

const KEY = HRH.BLACKLIST_LABELS_KEY || "hrhelper_black_frame_labels";
const DEFAULTS = Array.isArray(HRH.DEFAULT_BLACKLIST_LABELS) ? HRH.DEFAULT_BLACKLIST_LABELS : [];
const normalizeToken = window.__HRH__.normalizeToken;

function setLabelsLoadStatus(text, cls) {
  const el = document.getElementById("labelsLoadStatus");
  if (!el) return;
  el.textContent = text || "";
  el.className = "small " + (cls || "");
}

function normLabel(s) {
  return String(s || "")
    .trim()
    .toLowerCase()
    .replace(/ё/g, "е")
    .replace(/\s+/g, " ");
}

function uniqNormalized(list) {
  const seen = new Set();
  const out = [];
  (Array.isArray(list) ? list : []).forEach((x) => {
    const raw = String(x || "").trim();
    const n = normLabel(raw);
    if (!n) return;
    if (seen.has(n)) return;
    seen.add(n);
    out.push(raw);
  });
  return out;
}

function setSaveStatus(text, cls) {
  const el = document.getElementById("saveStatus");
  if (!el) return;
  el.textContent = text || "";
  el.className = "small " + (cls || "");
}

function renderChips(labels) {
  const wrap = document.getElementById("labelsChips");
  if (!wrap) return;
  wrap.innerHTML = "";
  (labels || []).forEach((name) => {
    const chip = document.createElement("div");
    chip.className = "chip";
    chip.appendChild(document.createTextNode(name));
    const x = document.createElement("button");
    x.type = "button";
    x.title = "Удалить";
    x.setAttribute("aria-label", "Удалить");
    x.textContent = "×";
    x.addEventListener("click", async () => {
      const next = (labels || []).filter((l) => normLabel(l) !== normLabel(name));
      await saveLabels(next);
    });
    chip.appendChild(x);
    wrap.appendChild(chip);
  });
}

async function saveLabels(labels) {
  const list = uniqNormalized(labels);
  await chrome.storage.sync.set({ [KEY]: list });
  setSaveStatus("Сохранено.", "ok");
  setTimeout(() => setSaveStatus("", ""), 1200);
  return list;
}

async function loadLabels() {
  const data = await chrome.storage.sync.get({ [KEY]: null });
  const v = data[KEY];
  if (Array.isArray(v)) return uniqNormalized(v);
  return uniqNormalized(DEFAULTS);
}

async function fetchAvailableLabels() {
  const cfg = await chrome.storage.sync.get({ baseUrl: "https://hr.sftntx.com/", apiToken: "" });
  const baseUrl = String(cfg.baseUrl || "https://hr.sftntx.com").trim().replace(/\/+$/, "");
  const apiToken = normalizeToken ? normalizeToken(cfg.apiToken || "") : String(cfg.apiToken || "").trim();
  if (!apiToken) return { error: "Не задан API Token (в Настройках)." };

  // Варианты меток должны приходить через API (backend → Huntflow).
  // Предполагаемый эндпоинт: /api/v1/huntflow/labels/
  // (если на backend другой путь — просто поменяем здесь).
  const url = `${baseUrl}/api/v1/huntflow/labels/`;
  try {
    const res = await fetch(url, {
      method: "GET",
      headers: { "Content-Type": "application/json", Authorization: `Token ${apiToken}` },
    });
    const json = await res.json().catch(() => null);
    if (!res.ok) {
      const msg = (json && (json.message || json.error)) || `HTTP ${res.status}`;
      return { error: `Не удалось загрузить метки: ${msg}` };
    }
    // Поддержка форматов:
    // - { success, items:[{name}] }
    // - { results:[{name}] }
    // - [{name}]
    const items = Array.isArray(json)
      ? json
      : (json && (json.items || json.results || json.data || json.labels)) || [];
    const names = (Array.isArray(items) ? items : [])
      .map((x) => (typeof x === "string" ? x : (x && (x.name || x.title)) || ""))
      .map((s) => String(s || "").trim())
      .filter(Boolean);
    return { names: uniqNormalized(names) };
  } catch (e) {
    return { error: e?.message || "Ошибка сети при загрузке меток" };
  }
}

function bindCollapsible() {
  document.querySelectorAll(".options-collapsible").forEach((section) => {
    const header = section.querySelector(".options-collapsible-header");
    const body = section.querySelector(".options-collapsible-body");
    if (!header || !body) return;
    header.addEventListener("click", () => {
      const collapsed = section.classList.toggle("collapsed");
      header.setAttribute("aria-expanded", collapsed ? "false" : "true");
    });
  });
}

async function init() {
  // theme from sync (reuse key)
  const themeKey = HRH.OPTIONS_THEME_KEY || "hrhelper_options_theme";
  const themeData = await chrome.storage.sync.get({ [themeKey]: "system" });
  const theme = themeData[themeKey] === "light" || themeData[themeKey] === "dark" ? themeData[themeKey] : "system";
  document.body.classList.remove("options-theme-light", "options-theme-dark", "options-theme-system");
  document.body.classList.add("options-theme-" + theme);

  bindCollapsible();

  let labels = await loadLabels();
  renderChips(labels);

  const input = document.getElementById("labelInput");
  const addBtn = document.getElementById("addLabel");
  addBtn?.addEventListener("click", async () => {
    const v = String(input?.value || "").trim();
    if (!v) return;
    labels = await saveLabels([...(labels || []), v]);
    renderChips(labels);
    if (input) input.value = "";
  });
  input?.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      addBtn?.click();
    }
  });

  document.getElementById("useDefaults")?.addEventListener("click", async () => {
    labels = await saveLabels(DEFAULTS);
    renderChips(labels);
  });
  document.getElementById("clearAll")?.addEventListener("click", async () => {
    labels = await saveLabels([]);
    renderChips(labels);
  });

  document.getElementById("backToOptions")?.addEventListener("click", () => {
    location.href = "options.html";
  });

  // labels from API (Huntflow via backend)
  const select = document.getElementById("labelsSelect");
  const addSelected = document.getElementById("addSelected");
  if (select) {
    setLabelsLoadStatus("Загрузка меток…", "");
    const result = await fetchAvailableLabels();
    if (result.error) {
      select.innerHTML = `<option value="">— Метки недоступны —</option>`;
      select.disabled = true;
      setLabelsLoadStatus(result.error, "err");
    } else {
      const names = result.names || [];
      select.innerHTML = `<option value="">— Выберите метку —</option>` + names.map((n) => `<option value="${String(n).replace(/"/g, "&quot;")}">${String(n).replace(/</g, "&lt;")}</option>`).join("");
      select.disabled = false;
      setLabelsLoadStatus(names.length ? `Загружено меток: ${names.length}` : "Список меток пуст.", "");
    }
  }
  addSelected?.addEventListener("click", async () => {
    const v = String(select?.value || "").trim();
    if (!v) return;
    labels = await saveLabels([...(labels || []), v]);
    renderChips(labels);
    if (select) select.value = "";
  });

  // live updates from sync
  chrome.storage.onChanged.addListener((changes, area) => {
    if (area !== "sync" || !changes[KEY]) return;
    const nv = changes[KEY].newValue;
    if (Array.isArray(nv)) {
      labels = uniqNormalized(nv);
      renderChips(labels);
    }
  });
}

init();

