# HR Helper — Chrome Extension

## Архитектура, логика и вёрстка

Подробный документ: логика работы, UI на целевых страницах, вёрстка попапа и настроек.

---

## 1. Общая схема

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         HR Helper Extension                              │
├─────────────────────────────────────────────────────────────────────────┤
│  background.js          │  Единая точка API-запросов к hr.sftntx.com     │
│  (service worker)       │  Хранит baseUrl + apiToken из chrome.storage   │
└─────────────────────────────────────────────────────────────────────────┘
                                    ▲
                                    │ chrome.runtime.sendMessage
                                    │ { type: 'HRHELPER_API', payload }
                                    │
┌───────────────────────────────────┴─────────────────────────────────────┐
│  content.js (LinkedIn, Calendar, Meet)                                   │
│  content-resume.js (rabota.by, hh.ru)                                    │
└─────────────────────────────────────────────────────────────────────────┘
                                    ▲
                                    │ chrome.tabs.sendMessage
                                    │ { action: 'getPageContext' }
                                    │
┌───────────────────────────────────┴─────────────────────────────────────┐
│  popup.html + popup.js                                                  │
│  Контекстный UI в зависимости от активной вкладки                        │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Background (background.js)

**Роль:** прокси для всех HTTP-запросов к бэкенду HR Helper.

- **Конфиг:** `baseUrl` (по умолчанию `https://hr.sftntx.com`) и `apiToken` в `chrome.storage.sync`.
- **Обработка:** слушает `chrome.runtime.onMessage` с `type: 'HRHELPER_API'`.
- **Запрос:** `fetch` к `{baseUrl}{path}` с `Authorization: Token {apiToken}`.
- **Кэш:** для `GET /linkedin-applicants/status/` — 30 секунд.
- **Ответ:** `{ ok, status, json }`.

---

## 3. Popup — вёрстка и стили

### 3.1. Размеры и общий layout

| Параметр | Значение |
|----------|----------|
| Ширина body | 320px |
| Padding body | 16px |
| Min-height | 200px |
| Фон | #f8f9fa |
| Шрифт | -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif, 14px |
| Layout | flex, flex-direction: column |

### 3.2. Структура HTML

```
body
├── .header
│   ├── img (icons/icon-48.png, 32×32)
│   ├── h1 "HR Helper"
│   └── #headerSettingsBtn (кнопка настроек, 32×32)
│
├── .context-block (один из: linkedin | calendar | resume | meet)
│   └── [контент по контексту]
│
├── #status.status (сообщения ok/warn/err)
│
├── #before-setup-block (для OTHER)
│   ├── a.btn.secondary "Открыть HR Helper"
│   ├── p.hint
│   └── .popup-footer
│       └── a#openOptions.btn "Настройки"
│
└── script popup.js
```

### 3.3. Header

| Элемент | Стили |
|---------|-------|
| Контейнер | display: flex, align-items: center, gap: 10px, margin-bottom: 12px, padding-bottom: 12px, border-bottom: 1px solid #dee2e6 |
| Иконка | 32×32 px |
| h1 | font-size: 18px, font-weight: 600, color: #212529, flex: 1 |
| Кнопка настроек | 32×32, border-radius: 6px, прозрачный фон, при hover — rgba(10,102,194,0.1), color: #0a66c2 |

### 3.4. Контекстные блоки (.context-block)

| Свойство | Значение |
|----------|----------|
| display | none (по умолчанию), block при .visible |
| padding | 10px 12px |
| margin-bottom | 12px |
| border-radius | 8px |
| background | #e7f1ff |
| border | 1px solid #b6d4fe |

**Типографика:**
- h2: 16px, font-weight: 600, color: #212529
- h3: 13px, font-weight: 600, color: #084298
- p, .ctx-desc: 12px, color: #0a58ca
- .ctx-fio: 14px, font-weight: 600, color: #212529
- .ctx-label: 12px, font-weight: 600, color: #084298

### 3.5. Формы и инпуты

| Класс | Стили |
|-------|-------|
| .ctx-input | width: 100%, padding: 8px 10px, font-size: 12px, border: 1px solid #b6d4fe, border-radius: 6px, background: #fff. Focus: border-color: #0a66c2, box-shadow: 0 0 0 2px rgba(10,102,194,0.2) |
| .ctx-input-row | display: flex, align-items: center, gap: 8px. Input: flex: 1, min-width: 0 |
| .ctx-select | как .ctx-input |

### 3.6. Кнопки

| Класс | Размеры | Цвета |
|-------|---------|-------|
| .btn | width: 100%, padding: 10px 16px, font-size: 14px, font-weight: 600, border-radius: 6px | #0a66c2, hover: #084d99 |
| .btn.secondary | — | #6c757d, hover: #5a6268 |
| .btn-small | height: 36px, padding: 0 12px, font-size: 12px, border-radius: 6px | #0a66c2 |
| .btn-small.secondary | — | #6c757d |
| .btn-small.rejection | — | #c0392b |
| .btn-scorecard | — | #1e8e3e, hover: #137333 |
| .btn-icon | 36×36 px, border-radius: 6px | #0a66c2 |
| .btn-icon.secondary | — | #6c757d |
| .ctx-toolbar-btn | 28×24 px, border-radius: 4px | background: #fff, border: 1px solid #b6d4fe, color: #084298 |

### 3.7. Комментарий (contenteditable)

| Элемент | Стили |
|---------|-------|
| .ctx-comment-wrap | border: 1px solid #b6d4fe, border-radius: 6px, overflow: hidden |
| .ctx-comment-toolbar | display: flex, gap: 4px, padding: 4px 6px, background: #f0f7ff, border-bottom: 1px solid #b6d4fe |
| .ctx-comment-editor | min-height: 60px, max-height: 120px, overflow-y: auto, padding: 8px 10px, font-size: 12px |

### 3.8. Блок Meet (.ctx-buttons-meet)

| Элемент | Layout |
|---------|--------|
| Контейнер | flex-direction: column, gap: 8px |
| .ctx-meet-row1 | flex, flex-wrap: nowrap, align-items: center, gap: 6px |
| .ctx-meet-copy-wrap | flex, flex: 1, min-width: 0 |
| .ctx-meet-divider | height: 0, border-top: 1px solid rgba(0,0,0,0.12) |
| .ctx-meet-contact-full | flex, align-items: center, justify-content: center, gap: 6px, width: 100% |

### 3.9. Сообщения (.status)

| Класс | Фон | Текст |
|-------|-----|-------|
| .status.ok | #d1e7dd | #0f5132 |
| .status.warn | #fff3cd | #664d03 |
| .status.err | #f8d7da | #842029 |

### 3.10. Сообщения в контексте (.ctx-message)

- padding: 8px 10px, font-size: 12px, border-radius: 6px
- background: #fff3cd, color: #664d03, border: 1px solid #ffc107

### 3.11. Множественные вакансии

При `vacancies.length > 1` popup показывает UI для управления несколькими вакансиями:

| Элемент | Стили |
|---------|-------|
| .ctx-employee-badge | padding: 12px 16px, background: #d1e7dd, border: 1px solid #a3cfbb, border-radius: 8px, color: #0f5132 (при hired) |
| .ctx-vacancy-card | padding: 12px, margin-bottom: 8px, border-radius: 8px. Активная: border #b6d4fe, background #e7f1ff. Rejected: border #f1aeb5, background #f8d7da |
| #ctx-linkedin-vacancies-list | margin-top: 12px, контейнер карточек |

Категории: активные, отказы, hired. Кнопки: «В новый цикл», «Изменить статус», «+ Взять на другую вакансию».

---

## 4. Options — вёрстка и стили

### 4.1. Layout

| Параметр | Значение |
|----------|----------|
| max-width | 600px |
| margin | 40px auto |
| padding | 20px |
| background | #f5f5f5 |
| Шрифт | -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif |

### 4.2. Структура

```
body
├── h1 "Настройки"
├── .form-group (Base URL)
│   ├── label "Base URL HRHelper"
│   ├── input#baseUrl (type="url")
│   └── .hint
├── .form-group (API Token)
│   ├── label "API Token (DRF)"
│   ├── input#apiToken (type="password")
│   └── .hint (с ссылкой на /api/v1/accounts/users/token/)
├── button#save "Сохранить"
├── #status
└── .hint (подсказка про cookies)
```

### 4.3. Стили полей

| Элемент | Стили |
|---------|-------|
| label | display: block, margin-bottom: 8px, font-weight: 600, color: #333 |
| input | width: 100%, padding: 10px, border: 1px solid #ddd, border-radius: 4px, font-size: 14px. Focus: border-color: #0a66c2, box-shadow: 0 0 0 3px rgba(10,102,194,0.1) |
| .hint | margin-top: 8px, font-size: 12px, color: #666 |
| .hint.err | color: #c41e47, font-weight: 600 |
| .hint.ok | color: #0a66c2, font-weight: 600 |
| button | padding: 12px 24px, border-radius: 4px, font-size: 14px, font-weight: 600, background: #0a66c2, color: white. Hover: #084d99 |

---

## 5. Content Scripts — вёрстка на страницах

### 5.1. LinkedIn (content.js)

#### Wrapper блока Huntflow

| Контекст | Стили wrapper |
|----------|---------------|
| Messaging | padding: 12px 16px, border-bottom: 1px solid rgba(0,0,0,.08), background: #f3f6f8, display: flex, align-items: center, gap: 8px |
| Профиль (над Activity) | padding: 12px 0, margin-bottom: 8px, display: flex, align-items: center, gap: 8px, flex-wrap: wrap |
| Fallback (рядом с More) | margin-left: 8px, display: inline-flex, align-items: center, gap: 6px |

#### Кнопки

| Элемент | Класс | Стили |
|---------|-------|-------|
| Основная кнопка | .hrhelper-action-btn | padding: 8px 12px, border-radius: 999px, border: 1px solid rgba(0,0,0,.15), color: #fff, font-weight: 600 |
| Копировать | .hrhelper-copy-btn | 32×32, border-radius: 50%, background: #17a2b8 |
| Редактировать | .hrhelper-edit-btn | 32×32, border-radius: 50%, background: #6c757d |
| Статус | .hrhelper-status-btn | padding: 8px 12px, border-radius: 999px, font-size: 12px. При rejection: #dc3545, иначе #28a745 |
| Сохранить | .hrhelper-save-btn | padding: 8px 16px, border-radius: 999px, background: #0a66c2 |
| Отмена | .hrhelper-cancel-btn | padding: 8px 16px, border-radius: 999px, background: #6c757d |

#### Input группа

| Элемент | Стили |
|---------|-------|
| .hrhelper-input-group | display: flex, align-items: center, gap: 8px, flex: 1 |
| .hrhelper-input (messaging) | flex: 1, padding: 8px 12px, border-radius: 8px, border: 1px solid rgba(0,0,0,.2), font-size: 13px |
| .hrhelper-input (профиль) | flex: 1, min-width: 120px, padding: 6px 10px, border-radius: 6px, border: 1px solid rgba(0,0,0,.2), font-size: 12px |

#### Dropdown статусов

| Элемент | Стили |
|---------|-------|
| .hrhelper-status-dropdown | position: absolute/fixed, background: #fff, border: 1px solid rgba(0,0,0,.2), border-radius: 8px, box-shadow: 0 4px 12px rgba(0,0,0,.15), z-index: 10000, min-width: 200px, max-width: 300px |
| .hrhelper-status-item | padding: 8px 12px, cursor: pointer, border-bottom: 1px solid rgba(0,0,0,.05). Hover: background: #f0f0f0 |
| .hrhelper-back-button | padding: 8px 12px, border-bottom: 2px solid rgba(0,0,0,.1), background: #f8f9fa, font-weight: 600 |

### 5.2. Google Calendar — кнопка «Контакт»

| Свойство | Значение |
|----------|----------|
| Класс | .hrhelper-communication-btn |
| Стили | display: inline-block, margin-left: 8px, padding: 4px 8px, background: #0a66c2, color: #fff, border-radius: 4px, font-size: 12px |
| Telegram | background: #0088cc |
| LinkedIn | background: #0a66c2 |
| Другое | background: #6c757d |

### 5.3. Google Meet

#### Панель (fixed, top-right)

| Свойство | Значение |
|----------|----------|
| Контейнер | position: fixed, top: 12px, right: 12px, z-index: 99999, display: flex, gap: 6px, padding: 8px, background: rgba(0,0,0,0.85), border-radius: 8px, box-shadow: 0 2px 8px rgba(0,0,0,0.3) |
| Label | color: #fff, font-size: 12px |

#### Кнопки Meet (в панели управления)

| Константа | Стили |
|-----------|-------|
| HRHELPER_MEET_BTN_STYLE | display: inline-flex, padding: 6px 12px, min-height: 32px, background: #0a66c2, color: #fff, border-radius: 6px, font-size: 13px, font-weight: 500 |
| HRHELPER_MEET_BTN_DISABLED | opacity: 0.6, cursor: not-allowed, pointer-events: none, background: #6c757d |

#### Кнопка «Уровень»

| Состояние | Стили |
|-----------|-------|
| Неактивна | background: #6c757d, opacity: 0.6, cursor: not-allowed |
| Активна | background: #0a66c2 |
| Успех (после копирования) | background: #28a745 на 2 сек |
| Ошибка | background: #dc3545 на 2 сек |

### 5.4. rabota.by / hh.ru (content-resume.js)

#### Блок `.hrhelper-candidate-block`

| Элемент | Стили |
|---------|-------|
| Контейнер | margin-top: 8px, padding: 12px, max-width: 480px, background: #f5f7fa, border: 1px solid #e0e4e9, border-radius: 8px, font-size: 13px, line-height: 1.4, box-shadow: 0 1px 3px rgba(0,0,0,0.06) |
| .hrhelper-candidate-block-title | font-weight: 600, color: #0a66c2, margin-bottom: 8px, font-size: 12px, text-transform: uppercase, letter-spacing: 0.02em |
| .hrhelper-candidate-block-body | color: #333 |
| .hrhelper-candidate-block-row | margin-bottom: 4px |
| .hrhelper-candidate-block-label | color: #666 |
| .hrhelper-candidate-block-value | color: #111 |

#### Loading placeholder

- margin-top: 8px, padding: 8px, color: #666, font-size: 12px, текст «Загрузка данных Huntflow…» или «Загрузка данных кандидата…»

---

## 6. Контексты Popup и структура блоков

| Контекст | Блок | Видимые элементы |
|----------|------|------------------|
| LINKEDIN | #context-linkedin | Заголовок, ФИО, вакансия, форма ввода, кнопки, блок статуса, данные кандидата |
| RESUME | #context-resume | Тот же блок, что и LinkedIn (context-linkedin) |
| CALENDAR | #context-calendar | h3, описание, .ctx-data |
| MEET | #context-meet | h3, кнопки Huntflow, «Вакансия и грейд», Scorecard, «Контакт» |
| OTHER | #before-setup-block | Кнопка «Открыть HR Helper», hint, «Настройки» |

---

## 7. Цветовая палитра

| Назначение | Цвет |
|------------|------|
| Основной (кнопки, ссылки) | #0a66c2 |
| Основной hover | #084d99 |
| Вторичный (серый) | #6c757d |
| Вторичный hover | #5a6268 |
| Успех (Scorecard) | #1e8e3e, hover: #137333 |
| Отказ (rejection) | #c0392b, hover: #a93226 |
| Ошибка | #dc3545, #842029 |
| Предупреждение | #ffc107, #664d03 |
| Фон контекста | #e7f1ff |
| Граница контекста | #b6d4fe |
| Текст основной | #212529, #333 |
| Текст вторичный | #6c757d, #666 |

---

## 8. API-эндпоинты

| Метод | Путь | Назначение |
|-------|------|------------|
| GET | /api/v1/huntflow/linkedin-applicants/status/ | Статус кандидата по LinkedIn (одна вакансия) |
| GET | /api/v1/huntflow/linkedin-applicants/status-multi/ | Все вакансии кандидата (множественные) |
| GET | /api/v1/huntflow/linkedin-applicants/available-vacancies/ | Открытые вакансии, на которые кандидат не добавлен |
| POST | /api/v1/huntflow/linkedin-applicants/add-to-vacancy/ | Добавить кандидата на вакансию |
| GET | /api/v1/huntflow/linkedin-applicants/candidate-info/ | Данные кандидата по Huntflow URL |
| GET | /api/v1/huntflow/resume-links/ | Связь резюме → Huntflow по resume_id |
| POST | /api/v1/huntflow/resume-links/ | Сохранение связи резюме → Huntflow |
| GET | /api/v1/huntflow/meet-links/ | Связь Meet → Huntflow |
| GET | /api/v1/huntflow/linkedin-applicants/level-text/ | Текст грейда |
| GET/POST | /api/v1/linkedin/thread-mapping/ | Маппинг thread_id → profile_url |

---

## 9. Хранение данных

| Ключ | Storage | Содержимое |
|------|---------|------------|
| baseUrl, apiToken | sync | Конфиг API |
| hrhelper_resume_state | local | `{ [resume_id]: { huntflowUrl, candidateInfo, ... } }` |
| hrhelper_thread_profile_map | localStorage | `{ [thread_id]: profile_url }` |
