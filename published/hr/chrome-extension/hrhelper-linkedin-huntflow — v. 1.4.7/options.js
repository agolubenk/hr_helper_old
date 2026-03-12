const OPTIONS_THEME_KEY = "hrhelper_options_theme";
const ACTIVE_PAGES_KEY = "hrhelper_active_pages";
const DEFAULT_ACTIVE_PAGES = {
  linkedin: true,
  hh_ecosystem: true,
  huntflow: true,
  meet: true,
  calendar: true,
};

async function loadOptions() {
  const { baseUrl, apiToken, [OPTIONS_THEME_KEY]: theme, [ACTIVE_PAGES_KEY]: activePages } = await chrome.storage.sync.get({
    baseUrl: "https://hr.sftntx.com/",
    apiToken: "",
    [OPTIONS_THEME_KEY]: "system",
    [ACTIVE_PAGES_KEY]: DEFAULT_ACTIVE_PAGES,
  });
  document.getElementById("baseUrl").value = baseUrl;
  document.getElementById("apiToken").value = apiToken;
  const themeValue = theme === "light" || theme === "dark" ? theme : "system";
  const radio = document.querySelector(`input[name="optionsTheme"][value="${themeValue}"]`);
  if (radio) radio.checked = true;
  applyTheme(themeValue);
  const pages = { ...DEFAULT_ACTIVE_PAGES, ...(activePages || {}) };
  document.querySelectorAll(".options-page-btn[data-page]").forEach((btn) => {
    const key = btn.getAttribute("data-page");
    const on = !!pages[key];
    btn.classList.toggle("options-page-on", on);
    btn.classList.toggle("options-page-off", !on);
    btn.setAttribute("aria-pressed", on ? "true" : "false");
  });
}

/** Из вставленного текста извлекает только ключ токена для сохранения. */
function normalizeToken(input) {
  if (!input || typeof input !== "string") return "";
  let s = input.trim();
  if (!s) return "";
  if (/^Token\s+/i.test(s)) s = s.replace(/^Token\s+/i, "");
  if (/^Bearer\s+/i.test(s)) s = s.replace(/^Bearer\s+/i, "");
  try {
    const parsed = JSON.parse(s);
    if (parsed && typeof parsed.data === "object" && parsed.data && typeof parsed.data.token === "string")
      return parsed.data.token.trim();
    if (parsed && typeof parsed.token === "string") return parsed.token.trim();
  } catch (_) {}
  return s;
}

async function saveOptions() {
  const baseUrl = (document.getElementById("baseUrl").value || "")
    .trim()
    .replace(/\/+$/, "");
  const apiToken = normalizeToken(document.getElementById("apiToken").value || "");
  const status = document.getElementById("status");

  if (!baseUrl) {
    status.textContent = "Укажите base URL.";
    status.className = "hint err";
    return;
  }

  if (!apiToken) {
    status.textContent = "Укажите API Token.";
    status.className = "hint err";
    return;
  }

  const themeRadio = document.querySelector('input[name="optionsTheme"]:checked');
  const theme = themeRadio ? themeRadio.value : "system";
  const activePages = { ...DEFAULT_ACTIVE_PAGES };
  document.querySelectorAll(".options-page-btn[data-page]").forEach((btn) => {
    const key = btn.getAttribute("data-page");
    if (key) activePages[key] = btn.classList.contains("options-page-on");
  });
  await chrome.storage.sync.set({ baseUrl, apiToken, [OPTIONS_THEME_KEY]: theme, [ACTIVE_PAGES_KEY]: activePages });
  applyTheme(theme);
  status.textContent = "Сохранено.";
  status.className = "hint ok";
  setTimeout(() => (status.textContent = ""), 1500);
}

function applyTheme(theme) {
  document.body.classList.remove("options-theme-light", "options-theme-dark", "options-theme-system");
  document.body.classList.add("options-theme-" + (theme || "system"));
}

document.getElementById("save").addEventListener("click", saveOptions);
document.querySelectorAll('input[name="optionsTheme"]').forEach((el) => {
  el.addEventListener("change", () => {
    const theme = document.querySelector('input[name="optionsTheme"]:checked')?.value || "system";
    chrome.storage.sync.set({ [OPTIONS_THEME_KEY]: theme });
    applyTheme(theme);
  });
});
document.getElementById("options-pages-row")?.addEventListener("click", (e) => {
  const btn = e.target.closest(".options-page-btn[data-page]");
  if (!btn) return;
  const on = btn.classList.contains("options-page-on");
  btn.classList.toggle("options-page-on", !on);
  btn.classList.toggle("options-page-off", on);
  btn.setAttribute("aria-pressed", !on ? "true" : "false");
  const activePages = { ...DEFAULT_ACTIVE_PAGES };
  document.querySelectorAll(".options-page-btn[data-page]").forEach((b) => {
    const key = b.getAttribute("data-page");
    if (key) activePages[key] = b.classList.contains("options-page-on");
  });
  chrome.storage.sync.set({ [ACTIVE_PAGES_KEY]: activePages });
});
loadOptions();

const manifest = chrome.runtime?.getManifest?.();
if (manifest && typeof manifest.version === "string") {
  const el = document.getElementById("extension-version");
  if (el) el.textContent = manifest.version;
}

try {
  const wikiIcon = document.getElementById("wiki-pill-icon");
  if (wikiIcon && typeof chrome.runtime.getURL === "function") {
    wikiIcon.src = chrome.runtime.getURL("icons/icon-32.png");
  }
} catch (_) {}