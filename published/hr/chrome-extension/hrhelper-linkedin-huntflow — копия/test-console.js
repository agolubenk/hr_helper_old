// Вставь этот код в консоль браузера (F12 → Console) на странице LinkedIn профиля
// Он покажет, почему кнопка не отображается

console.log('=== HRHelper Diagnostic Tool ===');
console.log('');

// 1. Проверка URL
console.log('1. URL Check:');
console.log('  Current URL:', location.href);
console.log('  Is /in/ page:', location.href.includes('/in/'));
console.log('  Is /messaging/ page:', location.href.includes('/messaging/'));
console.log('');

// 2. Проверка STATE
console.log('2. STATE Check:');
if (typeof STATE !== 'undefined') {
  console.log('  ✅ STATE exists');
  console.log('  current.show:', STATE.current?.show);
  console.log('  current.mode:', STATE.current?.mode);
  console.log('  current.disabled:', STATE.current?.disabled);
  console.log('  current.appUrl:', STATE.current?.appUrl);
  console.log('  buttons.size:', STATE.buttons?.size);
  console.log('  statusFetchedFor:', STATE.statusFetchedFor);
} else {
  console.log('  ❌ STATE not found (script not loaded?)');
}
console.log('');

// 3. Проверка DOM
console.log('3. DOM Check:');
const widgets = document.querySelectorAll('[data-hrhelper-huntflow="1"]');
console.log('  Widgets found:', widgets.length);
if (widgets.length > 0) {
  console.log('  ✅ Widget exists in DOM');
  widgets.forEach((w, i) => {
    console.log(`  Widget ${i}:`, w.style.display);
  });
} else {
  console.log('  ❌ No widgets in DOM');
}

const buttons = document.querySelectorAll('.hrhelper-action-btn');
console.log('  Buttons found:', buttons.length);

const inputs = document.querySelectorAll('.hrhelper-input');
console.log('  Inputs found:', inputs.length);
console.log('');

// 4. Проверка API Token
console.log('4. API Token Check:');
chrome.storage.sync.get(['apiToken'], (result) => {
  if (result.apiToken) {
    console.log('  ✅ API Token exists:', result.apiToken.substring(0, 10) + '...');
  } else {
    console.log('  ❌ API Token not found');
    console.log('  → Go to chrome://extensions → Details → Extension options');
    console.log('  → Get token from: https://hr.sftntx.com/api/v1/accounts/users/token/');
  }
});
console.log('');

// 5. Проверка localStorage
console.log('5. LocalStorage Check:');
const threadMap = localStorage.getItem('hrhelper_thread_profile_map');
if (threadMap) {
  console.log('  ✅ Thread mapping exists');
  try {
    const parsed = JSON.parse(threadMap);
    console.log('  Threads:', Object.keys(parsed).length);
  } catch (e) {
    console.log('  ⚠️ Invalid JSON in localStorage');
  }
} else {
  console.log('  ℹ️ No thread mapping (normal for first use)');
}
console.log('');

// 6. Проверка MutationObserver
console.log('6. Observer Check:');
const moreButtons = document.querySelectorAll('button[aria-label*="More"], button[aria-label*="Ещё"]');
console.log('  "More" buttons found:', moreButtons.length);
if (moreButtons.length > 0) {
  console.log('  ✅ More buttons exist');
} else {
  console.log('  ⚠️ No "More" buttons (may be normal on some pages)');
}

const composer = document.querySelector('.msg-form__contenteditable, .msg-form__composer');
console.log('  Message composer found:', !!composer);
console.log('');

// 7. Ручной тест API
console.log('7. Manual API Test:');
console.log('  Run this in console:');
console.log('');
console.log('  chrome.storage.sync.get(["apiToken", "baseUrl"], async (cfg) => {');
console.log('    const url = `${cfg.baseUrl || "http://localhost:8000"}/api/v1/huntflow/linkedin-applicants/status/?linkedin_url=${encodeURIComponent(location.href)}`;');
console.log('    const res = await fetch(url, {');
console.log('      headers: { Authorization: `Token ${cfg.apiToken}` }');
console.log('    });');
console.log('    const data = await res.json();');
console.log('    console.log("API Response:", data);');
console.log('  });');
console.log('');

// 8. Рекомендации
console.log('=== Recommendations ===');
console.log('');

if (typeof STATE === 'undefined') {
  console.log('❌ CRITICAL: Script not loaded');
  console.log('  → Reload extension: chrome://extensions → Reload');
  console.log('  → Hard reload page: Ctrl+Shift+R');
}

if (typeof STATE !== 'undefined' && !STATE.current?.show) {
  console.log('❌ ISSUE: STATE.current.show is false');
  console.log('  → Check console for [HRHelper] logs');
  console.log('  → Check Network tab for API errors');
}

if (widgets.length === 0 && typeof STATE !== 'undefined' && STATE.current?.show) {
  console.log('❌ ISSUE: STATE.show=true but no widgets in DOM');
  console.log('  → Run: ensureButtons() in console');
  console.log('  → Check if "More" buttons exist');
}

console.log('');
console.log('=== Next Steps ===');
console.log('1. Check console for [HRHelper] logs');
console.log('2. Check Network tab (F12 → Network) for API requests');
console.log('3. Send me ALL [HRHelper] logs from console');
console.log('');
