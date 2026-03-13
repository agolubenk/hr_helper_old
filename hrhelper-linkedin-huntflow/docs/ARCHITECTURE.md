# Архитектура расширения HR Helper

Документ описывает структуру расширения, модули и потоки данных.

## Общая схема

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         HR Helper Extension (Manifest V3)               │
├─────────────────────────────────────────────────────────────────────────┤
│  background.js (service worker)                                          │
│  Единая точка API-запросов к hr.sftntx.com; baseUrl + apiToken из       │
│  chrome.storage.sync; кэш для GET /linkedin-applicants/status/           │
└─────────────────────────────────────────────────────────────────────────┘
                                    ▲
                                    │ chrome.runtime.sendMessage
                                    │ { type: 'HRHELPER_API', payload: { path, method, body } }
                                    │
┌───────────────────────────────────┴─────────────────────────────────────┐
│  Content scripts (загружают shared/* до основного скрипта)                 │
│  content.js       — LinkedIn, Google Calendar, Google Meet               │
│  content-resume.js — rabota.by, hh.ru (страницы резюме)                   │
│  content-huntflow.js — huntflow.ru (карточки кандидатов)                  │
└─────────────────────────────────────────────────────────────────────────┘
                                    ▲
                                    │ chrome.tabs.sendMessage / getPageContext
                                    │
┌───────────────────────────────────┴─────────────────────────────────────┐
│  popup.html + popup.js                                                   │
│  Контекстный UI по активной вкладке (linkedin, resume, calendar, meet,   │
│  other); тема из настроек (светлая/тёмная/авто).                         │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│  options.html + options.js                                               │
│  Base URL, API Token, тема оформления, ссылка на интеграции,             │
│  отображение статуса подключения к API.                                  │
└─────────────────────────────────────────────────────────────────────────┘
```

## Shared-модули

Общий код вынесен в `shared/` и подключается в `manifest.json` первым в списке `content_scripts[].js`. Контексты: content scripts (window), background (self). Доступ через глобальный объект `__HRH__` (window.__HRH__ или self.__HRH__).

| Файл | Назначение |
|------|------------|
| `shared/constants.js` | `DEFAULTS` (baseUrl, apiToken), `ACTIVE_PAGES_KEY`, `DEFAULT_ACTIVE_PAGES`, `OPTIONS_THEME_KEY`, `DEFAULT_THEME`, иконки. |
| `shared/utils/token.js` | `normalizeToken(token)` — нормализация API-токена. |
| `shared/utils/url.js` | `normalizeLinkedInProfileUrl(url)`, `getBaseUrl()` — работа с URL профилей и Base URL. |
| `shared/api/client.js` | `apiFetch(path, init)` — отправка запросов в background через `chrome.runtime.sendMessage({ type: 'HRHELPER_API', payload })`, возвращает `{ ok, status, json }`. |

Все константы и утилиты используются в background, popup, options и content scripts через `__HRH__`, чтобы не дублировать значения и логику (DRY).

## Background (service worker)

- **Роль:** прокси для HTTP-запросов к бэкенду HR Helper.
- **Конфиг:** считывает `baseUrl` и `apiToken` из `chrome.storage.sync` (значения по умолчанию из `__HRH__.DEFAULTS`).
- **Обработка:** слушает `chrome.runtime.onMessage` с `type: 'HRHELPER_API'`; выполняет `fetch` к `{baseUrl}{path}` с заголовком `Authorization: Token {apiToken}`.
- **Кэш:** для `GET /linkedin-applicants/status/` — 30 секунд (по ключу canonical URL профиля).
- **Ответ:** объект вида `{ ok, status, json }` для передачи в content/popup.

## Content scripts

### content.js (LinkedIn, Calendar, Meet)

- **Страницы:** `linkedin.com/in/*`, `linkedin.com/messaging/*`, `calendar.google.com/*`, `meet.google.com/*`.
- **LinkedIn:** кнопка «Huntflow», плавающее окно с данными кандидата, статусы, добавление на вакансии; в переписке — панель с действиями и привязка thread → profile. Использует `__HRH__.apiFetch` (через background).
- **Тема:** при настройке «Автоматически» сначала определяется тема сайта (data-theme, классы, яркость фона), при неопределённости — `prefers-color-scheme`. При выборе «Светлая»/«Тёмная» используется выбранная тема. Класс `hrhelper-theme-dark` применяется к плавающим виджетам и панели переписки.
- **Google Calendar:** кнопки контактов (мессенджеры, LinkedIn) рядом с «Уведомить гостей». Тема кнопок: из настроек (светлая/тёмная/авто); при авто — тема страницы календаря (body/html, затем контейнер кнопки), иначе тема браузера.
- **Google Meet:** панель с кнопками (уровень, Scorecard, контакт в Huntflow и т.д.) и копирование текста.

### content-resume.js (rabota.by, hh.ru)

- **Страницы:** `rabota.by/resume/*`, `hh.ru/resume/*`.
- **Функции:** привязка ссылки на кандидата в Huntflow к резюме, отображение данных кандидата из Huntflow, плавающее окно с вакансиями и формой сохранения. Тема плавающего окна берётся из настроек (светлая/тёмная/авто через разрешённую тему, с палитрой в стиле LinkedIn для тёмной темы).

### content-huntflow.js (Huntflow)

- **Страницы:** `huntflow.ru/my/*`, `huntflow.dev/my/*`.
- **Функции:** на странице карточки кандидата — плавающее окно с контактами (соцсети, мессенджеры), кнопки копирования ФИО, телефона, email, ссылки на вакансию. Тема плавающего окна — из настроек (светлая/тёмная/авто), стили кнопок и карточек через CSS-переменные и класс `hrhelper-theme-dark`.

## Popup

- **Размер/структура:** фиксированная ширина (например 320px), заголовок с иконкой и кнопкой настроек, контекстный блок в зависимости от активной вкладки (linkedin, resume, calendar, meet, other).
- **Контекст:** определяется через `chrome.tabs.sendMessage` (action `getPageContext`) или по URL вкладки. Отображаются вакансии, статус кандидата, формы и кнопки действий.
- **Тема:** из `chrome.storage.sync` по ключу `hrhelper_options_theme` (system/light/dark). При «system» применяется тема по `prefers-color-scheme`. Классы `popup-theme-dark` / `popup-theme-light` на `body`; карточки вакансий и текст стилизуются под тёмную тему.
- **Ссылки:** ссылка на страницу «Интеграции» формируется из Base URL (например `https://hr.sftntx.com/` → `https://hr.sftntx.com/...`). Инструкции по настройке согласованы со страницей настроек.

## Options

- **Поля:** Base URL HRHelper, API Token (с подсказкой, где получить токен).
- **Тема:** переключатель «Светлая» / «Тёмная» / «Автоматически»; значение сохраняется в `chrome.storage.sync` по ключу `hrhelper_options_theme`.
- **Статус подключения:** отображается при сохранении или при открытии страницы: проверка API (например запрос к бэкенду с токеном), вывод успешного подключения или ошибки, при наличии — информация о пользователе.
- **Ссылка на интеграции:** формируется динамически из Base URL.

## Темы оформления

- **Настройка:** в options сохраняется `hrhelper_options_theme`: `"light"` | `"dark"` | `"system"`.
- **Popup:** при загрузке и при изменении настроек читается тема и применяется класс на `body`; при `system` используется `prefers-color-scheme`.
- **LinkedIn (виджеты, панель переписки):** при `system` сначала определяется тема страницы (атрибуты, классы, яркость фона), при неопределённости — тема браузера. Кэш `resolvedWidgetTheme` обновляется при смене настройки; MutationObserver следит за атрибутами темы на странице.
- **Календарь:** при `system` тема кнопок определяется по теме страницы календаря (body/html, затем родители кнопки); при отсутствии явной темы — по `prefers-color-scheme`. При смене настройки темы вызывается переприменение темы кнопок.
- **Резюме и Huntflow:** плавающие окна получают разрешённую тему из настроек (light/dark/system с разрешением через тему страницы или браузера) и класс `hrhelper-theme-dark`; стили заданы через CSS-переменные в духе тёмной темы LinkedIn.

## Хранение данных

| Ключ / источник | Storage | Содержимое |
|------------------|---------|------------|
| baseUrl, apiToken | sync | Конфиг API (из options). |
| hrhelper_options_theme | sync | Тема: "light" \| "dark" \| "system". |
| hrhelper_active_pages | sync | Включение/выключение страниц (linkedin, hh_ecosystem, huntflow, meet, calendar). |
| hrhelper_resume_state | local | Состояние по резюме (например ссылка Huntflow, данные кандидата и т.д.). |
| (на странице) | localStorage | Например маппинг thread_id → profile_url для переписки LinkedIn. |

## API (бэкенд HR Helper)

Запросы идут через background на `{baseUrl}{path}` с `Authorization: Token {apiToken}`. Примеры путей:

- `GET /api/v1/huntflow/linkedin-applicants/status/` — статус кандидата по LinkedIn.
- `GET /api/v1/huntflow/linkedin-applicants/status-multi/` — все вакансии кандидата.
- `GET/POST` — добавление на вакансию, данные кандидата, связи резюме/Huntflow, Meet, маппинг переписки и т.д.

Полный перечень эндпоинтов и форматы запросов/ответов определяются бэкендом HR Helper.

## Иконки и ресурсы

- В `manifest.json` указаны иконки 16, 32, 48, 128 px (в папке `icons/`).
- В `web_accessible_resources` объявлены `icons/*.png` для использования в content scripts на указанных доменах.
