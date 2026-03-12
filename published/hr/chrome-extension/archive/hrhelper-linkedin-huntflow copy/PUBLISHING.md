# Публикация расширения HR Helper в Chrome Web Store

Пошаговая инструкция для **закрытого (Unlisted)** расширения с минимальным раскрытием.

---

## Шаг 1. Подготовка файлов (5–10 мин)

### 1.1 Структура папки расширения

Убедитесь, что в папке есть:

```
hrhelper-linkedin-huntflow/
├── manifest.json
├── background.js
├── content.js
├── options.html
├── options.js
├── popup.html
├── popup.js
├── icons/
│   ├── icon-48.png
│   ├── icon-128.png
│   └── icon.svg
├── privacy.md
└── PUBLISHING.md (этот файл)
```

### 1.2 Иконки

- **icon-48.png** (48×48) и **icon-128.png** (128×128) уже сгенерированы из `icons/icon.svg`.
- Чтобы пересобрать: в папке `icons/` выполните  
  `magick -background none -resize 48x48 icon.svg icon-48.png`  
  и то же для 128×128.
- Для Store Listing дополнительно подготовьте скриншоты 1280×800 PNG (1–4 шт.), при необходимости размыв чувствительные данные.

### 1.3 Privacy Policy

- Файл **privacy.md** лежит в корне расширения.
- Для Web Store нужна **публичная ссылка** на политику конфиденциальности (HTTPS).
- Рекомендация: выложите `privacy.md` как страницу на GitHub Pages, например:  
  `https://<your-org>.github.io/hr-helper-extension/privacy.html`  
  и укажите эту ссылку в карточке расширения в разделе Privacy.

---

## Шаг 2. Код и manifest (Manifest V3)

- **manifest.json** уже в формате V3: имя «HR Helper», иконки, `permissions` и `host_permissions` только для LinkedIn, Huntflow, Google Calendar/Meet и вашего сервера HR Helper.
- **content.js** — инъекция на LinkedIn (профили/чаты), логика кнопки Huntflow и т.д.
- **background.js** — сервис-воркер для API-запросов к HR Helper.
- **popup** — быстрый доступ к настройкам и проверке подключения.

При необходимости добавьте в `host_permissions` другие домены (например, дополнительные ATS).

---

## Шаг 3. Локальное тестирование

1. Откройте `chrome://extensions/`.
2. Включите **«Режим разработчика»**.
3. Нажмите **«Загрузить распакованное расширение»** и выберите папку **hrhelper-linkedin-huntflow**.
4. Проверьте:
   - открытие popup по клику на иконку;
   - переход в «Настройки» (options);
   - работу на LinkedIn (профиль, при необходимости — чаты);
   - отсутствие ошибок в фоне и на странице (DevTools).

---

## Шаг 4. Упаковка в .crx (опционально)

Если нужно раздавать расширение напрямую (без Store):

1. В `chrome://extensions/` нажмите **«Упаковать расширение»**.
2. Укажите папку **hrhelper-linkedin-huntflow**.
3. При первом упаковывании создайте ключ (сохраните `.pem` для будущих обновлений).
4. Получите **hrhelper-linkedin-huntflow.crx** и раздавайте его вручную (учтите ограничения Chrome для неподписанных .crx).

---

## Шаг 5. Публикация в Chrome Web Store

1. Перейдите на [Chrome Web Store — Developer Dashboard](https://chrome.google.com/webstore/devconsole).
2. **«New Item»** → загрузите **ZIP** с содержимым папки **hrhelper-linkedin-huntflow** (без лишних папок в корне ZIP; в корне ZIP должны быть `manifest.json`, `background.js`, `content.js`, `popup.html`, `popup.js`, `options.html`, `options.js`, папка `icons/` и т.д.).
3. **Store listing:**
   - Краткое описание (например: «Интеграция с HR Helper: кнопка Huntflow на LinkedIn, синхронизация с вакансиями и кандидатами»).
   - При необходимости — скриншоты 1280×800, иконка 128×128 уже задана в manifest.
4. **Privacy:** укажите ссылку на политику конфиденциальности (например, GitHub Pages с `privacy.html`).
5. **Visibility:** выберите **Unlisted**, чтобы расширение не попадало в поиск, но было доступно по прямой ссылке.
6. **Test instructions** для ревью (пример):
   - Установите расширение.
   - Откройте настройки, введите URL HR Helper и API-токен, сохраните.
   - Откройте popup и убедитесь, что отображается статус подключения.
   - Перейдите на профиль в LinkedIn и проверьте появление кнопки Huntflow.
7. Нажмите **«Submit for review»**. Обычно проверка для Unlisted занимает 1–3 рабочих дня.

После одобрения вы получите ссылку на страницу расширения — её можно использовать в вашем приложении (кнопка «Установить расширение»).

---

## Шаг 6. Обновления и поддержка

- **Версия:** при каждом обновлении увеличивайте `version` в **manifest.json** (например, `1.0.1`).
- **Store:** загрузите новый ZIP и отправьте на ревью; после одобрения пользователи получат обновление автоматически.
- **.crx:** переупакуйте расширение с новой версией и разошлите .crx тем, кто использует установку вручную.
- Регулярно проверяйте `chrome://extensions/` на ошибки в фоне и в консоли на страницах LinkedIn/HR Helper.

---

## Ссылки

- [Chrome Web Store — публикация (поддержка Google)](https://support.google.com/chrome/a/answer/2714278?hl=RU)
- [Manifest V3](https://developer.chrome.com/docs/extensions/mv3/intro/)
