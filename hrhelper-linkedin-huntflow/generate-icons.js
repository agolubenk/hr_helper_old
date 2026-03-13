/**
 * Генерация PNG-иконок для Chrome Extension из SVG (робот с наушниками).
 * Также генерирует favicon для веб-приложения: светлая тема — малина/луна, тёмная — вода/лайм.
 * Запуск: npm install && node generate-icons.js
 */
const sharp = require('sharp');
const fs = require('fs');
const path = require('path');

/* Светлая тема вкладки (малина/луна) — тот же дизайн, что и иконка расширения */
const svgCode = `<svg width="256" height="256" viewBox="0 0 256 256" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="headGradient" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#ff6b81;stop-opacity:1" />
      <stop offset="100%" style="stop-color:#ff4757;stop-opacity:1" />
    </linearGradient>
  </defs>
  <g transform="translate(128,128) scale(1.5) translate(-128,-128)">
    <circle cx="128" cy="128" r="120" fill="#1a1a2e" opacity="0.1"/>
    <line x1="40" y1="100" x2="70" y2="100" stroke="#00f5ff" stroke-width="3" stroke-linecap="round"/>
    <line x1="35" y1="120" x2="65" y2="120" stroke="#00f5ff" stroke-width="2" stroke-linecap="round"/>
    <line x1="45" y1="140" x2="72" y2="140" stroke="#b4ff39" stroke-width="2" stroke-linecap="round"/>
    <line x1="186" y1="100" x2="216" y2="100" stroke="#00f5ff" stroke-width="3" stroke-linecap="round"/>
    <line x1="191" y1="120" x2="221" y2="120" stroke="#00f5ff" stroke-width="2" stroke-linecap="round"/>
    <line x1="184" y1="140" x2="211" y2="140" stroke="#b4ff39" stroke-width="2" stroke-linecap="round"/>
    <circle cx="75" cy="120" r="18" fill="#e8eaf6" stroke="#1a1a2e" stroke-width="4"/>
    <circle cx="75" cy="120" r="10" fill="#ff4757"/>
    <circle cx="181" cy="120" r="18" fill="#e8eaf6" stroke="#1a1a2e" stroke-width="4"/>
    <circle cx="181" cy="120" r="10" fill="#ff4757"/>
    <rect x="85" y="80" width="86" height="90" rx="20" fill="#ff4757" stroke="#1a1a2e" stroke-width="5"/>
    <rect x="85" y="80" width="86" height="90" rx="20" fill="url(#headGradient)" stroke="#1a1a2e" stroke-width="5"/>
    <rect x="95" y="95" width="66" height="50" rx="12" fill="#0f1419" opacity="0.3"/>
    <circle cx="113" cy="115" r="8" fill="#00f5ff"/>
    <circle cx="143" cy="115" r="8" fill="#00f5ff"/>
    <line x1="115" y1="135" x2="141" y2="135" stroke="#e8eaf6" stroke-width="3" stroke-linecap="round"/>
    <rect x="126" y="50" width="4" height="32" rx="2" fill="#5a6c7d" stroke="#1a1a2e" stroke-width="2"/>
    <circle cx="128" cy="48" r="10" fill="#b4ff39" stroke="#1a1a2e" stroke-width="3"/>
    <path d="M 105 170 Q 105 185 105 195 Q 105 205 95 205 Q 85 205 85 195 L 85 170" fill="#ff4757" stroke="#1a1a2e" stroke-width="4" stroke-linejoin="round"/>
    <path d="M 128 170 Q 128 190 128 205 Q 128 215 118 215 Q 108 215 108 205 L 108 170" fill="#ff4757" stroke="#1a1a2e" stroke-width="4" stroke-linejoin="round"/>
    <path d="M 151 170 Q 151 185 151 195 Q 151 205 161 205 Q 171 205 171 195 L 171 170" fill="#ff4757" stroke="#1a1a2e" stroke-width="4" stroke-linejoin="round"/>
  </g>
</svg>`;

/* Тёмная тема вкладки (вода + лайм) — тот же силуэт, яркий на тёмном фоне */
const svgCodeWaterLime = `<svg width="256" height="256" viewBox="0 0 256 256" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="headGradientWL" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#00f5ff;stop-opacity:1" />
      <stop offset="100%" style="stop-color:#00c8e8;stop-opacity:1" />
    </linearGradient>
  </defs>
  <g transform="translate(128,128) scale(1.5) translate(-128,-128)">
    <circle cx="128" cy="128" r="120" fill="#00f5ff" opacity="0.06"/>
    <line x1="40" y1="100" x2="70" y2="100" stroke="#00f5ff" stroke-width="3" stroke-linecap="round"/>
    <line x1="35" y1="120" x2="65" y2="120" stroke="#00f5ff" stroke-width="2" stroke-linecap="round"/>
    <line x1="45" y1="140" x2="72" y2="140" stroke="#b4ff39" stroke-width="2" stroke-linecap="round"/>
    <line x1="186" y1="100" x2="216" y2="100" stroke="#00f5ff" stroke-width="3" stroke-linecap="round"/>
    <line x1="191" y1="120" x2="221" y2="120" stroke="#00f5ff" stroke-width="2" stroke-linecap="round"/>
    <line x1="184" y1="140" x2="211" y2="140" stroke="#b4ff39" stroke-width="2" stroke-linecap="round"/>
    <circle cx="75" cy="120" r="18" fill="#e8fffe" stroke="#0d2137" stroke-width="4"/>
    <circle cx="75" cy="120" r="10" fill="#b4ff39"/>
    <circle cx="181" cy="120" r="18" fill="#e8fffe" stroke="#0d2137" stroke-width="4"/>
    <circle cx="181" cy="120" r="10" fill="#b4ff39"/>
    <rect x="85" y="80" width="86" height="90" rx="20" fill="url(#headGradientWL)" stroke="#0d2137" stroke-width="5"/>
    <rect x="95" y="95" width="66" height="50" rx="12" fill="#0d2137" opacity="0.9"/>
    <circle cx="113" cy="115" r="8" fill="#00f5ff"/>
    <circle cx="143" cy="115" r="8" fill="#b4ff39"/>
    <line x1="115" y1="135" x2="141" y2="135" stroke="#e8fffe" stroke-width="3" stroke-linecap="round"/>
    <rect x="126" y="50" width="4" height="32" rx="2" fill="#00a8cc" stroke="#0d2137" stroke-width="2"/>
    <circle cx="128" cy="48" r="10" fill="#b4ff39" stroke="#0d2137" stroke-width="3"/>
    <path d="M 105 170 Q 105 185 105 195 Q 105 205 95 205 Q 85 205 85 195 L 85 170" fill="#00f5ff" stroke="#0d2137" stroke-width="4" stroke-linejoin="round"/>
    <path d="M 128 170 Q 128 190 128 205 Q 128 215 118 215 Q 108 215 108 205 L 108 170" fill="#00f5ff" stroke="#0d2137" stroke-width="4" stroke-linejoin="round"/>
    <path d="M 151 170 Q 151 185 151 195 Q 151 205 161 205 Q 171 205 171 195 L 171 170" fill="#00f5ff" stroke="#0d2137" stroke-width="4" stroke-linejoin="round"/>
  </g>
</svg>`;

const iconsDir = path.join(__dirname, 'icons');
if (!fs.existsSync(iconsDir)) {
  fs.mkdirSync(iconsDir, { recursive: true });
}

// Размеры для Chrome Extension (имена как у существующих: icon-48.png, icon-128.png)
const sizes = [16, 32, 48, 128];

console.log('Генерация иконок для Chrome Extension (SVG → PNG)...\n');

Promise.all(
  sizes.map((size) => {
    const filename = `icon-${size}.png`;
    return sharp(Buffer.from(svgCode))
      .resize(size, size)
      .png()
      .toFile(path.join(iconsDir, filename))
      .then(() => {
        console.log(`  ${filename}`);
      })
      .catch((err) => {
        console.error(`  Ошибка ${filename}:`, err.message);
      });
  })
).then(() => {
  console.log('\nИконки записаны в папку icons/');
  console.log('Текущий manifest.json уже использует icons/icon-48.png и icons/icon-128.png.');
  console.log('При желании можно добавить в manifest 16 и 32 для action.default_icon.');

  // Favicon для веб-приложения: светлая тема вкладки = малина (favicon-dark), тёмная = вода/лайм (favicon-light)
  const repoRoot = path.join(__dirname, '..', '..', '..', '..');
  const staticImg = path.join(repoRoot, 'fullstack', 'backend', 'static', 'img');
  const publishedImg = path.join(__dirname, '..', '..', 'backend', 'static', 'img');
  const dirs = [];
  if (fs.existsSync(staticImg)) dirs.push(staticImg);
  if (!fs.existsSync(publishedImg)) fs.mkdirSync(publishedImg, { recursive: true });
  dirs.push(publishedImg);
  if (dirs.length === 0) {
    console.log('\nПапка fullstack/backend/static/img не найдена — favicon не копируются.');
    return;
  }
  const writes = [];
  dirs.forEach((dir) => {
    writes.push(
      sharp(Buffer.from(svgCode)).resize(32, 32).png().toFile(path.join(dir, 'favicon-dark.png')),
      sharp(Buffer.from(svgCodeWaterLime)).resize(32, 32).png().toFile(path.join(dir, 'favicon-light.png'))
    );
  });
  return Promise.all(writes).then(() => {
    console.log('\nFavicon записаны в:', dirs.map((d) => path.relative(repoRoot, d)).join(', '));
  }).catch((e) => {
    console.log('\nFavicon не записаны:', e.message);
  });
});
