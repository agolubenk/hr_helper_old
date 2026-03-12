async function loadOptions() {
  const { baseUrl, apiToken } = await chrome.storage.sync.get({
    baseUrl: "https://hr.sftntx.com/",
    apiToken: "",
  });
  document.getElementById("baseUrl").value = baseUrl;
  document.getElementById("apiToken").value = apiToken;
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

  await chrome.storage.sync.set({ baseUrl, apiToken });
  status.textContent = "Сохранено.";
  status.className = "hint ok";
  setTimeout(() => (status.textContent = ""), 1500);
}

document.getElementById("save").addEventListener("click", saveOptions);
loadOptions();

const manifest = chrome.runtime?.getManifest?.();
if (manifest && typeof manifest.version === "string") {
  const el = document.getElementById("extension-version");
  if (el) el.textContent = manifest.version;
}