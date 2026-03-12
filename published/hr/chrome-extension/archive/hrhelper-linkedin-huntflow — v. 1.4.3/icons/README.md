# Иконки расширения HR Helper

- **icon-16.png**, **icon-32.png**, **icon-48.png**, **icon-128.png** — используются в `manifest.json` и в popup.
- **icon.svg** — запасная векторная иконка.

## Генерация PNG из SVG (рекомендуемый способ)

В корне расширения лежит скрипт **generate-icons.js** с SVG-дизайном робота (наушники, антенна, «глаза»). Он создаёт все четыре размера PNG одной командой:

```bash
cd published/hr/chrome-extension/hrhelper-linkedin-huntflow
npm install
npm run generate-icons
```

Или: `node generate-icons.js`. Иконки появятся в папке `icons/`.

## Альтернатива: PNG из logo.png приложения

Иконки можно собрать из **fullstack/backend/static/img/logo.png** (верхняя половина — светлая тема), например через ImageMagick:

```bash
cd fullstack/backend/static/img
magick logo.png -crop 2048x1024+0+0 +repage -resize 128x128 -write ../../../../published/hr/chrome-extension/hrhelper-linkedin-huntflow/icons/icon-128.png -resize 48x48 ../../../../published/hr/chrome-extension/hrhelper-linkedin-huntflow/icons/icon-48.png
```

Иконки должны находиться в папке `icons/` — на них ссылается manifest.
