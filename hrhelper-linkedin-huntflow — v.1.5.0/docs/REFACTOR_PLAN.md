# План рефакторинга расширения HR Helper

Поэтапный план улучшений на основе анализа качества кода (производительность, SOLID/DRY, архитектура).

---

## Фаза 1: Срочные оптимизации (1–2 дня)

**Цель:** −30% времени загрузки, −40% нагрузки на CPU.

| # | Задача | Файлы | Статус |
|---|--------|--------|--------|
| 1.1 | Добавить debounce в MutationObserver | content.js, content-resume.js, content-calendar.js, content-meet.js | ✅ |
| 1.2 | Общие константы таймингов (TIMING) и утилита debounce | shared/constants.js, shared/utils/debounce.js | ✅ |
| 1.3 | Оптимизировать chrome.storage.get (batch reads) | popup.js, content.js, content-resume.js, content-huntflow.js | ✅ |
| 1.4 | Lazy loading виджетов (создавать по требованию) | content.js, content-resume.js, content-huntflow.js | ✅ |
| 1.5 | Заменить scroll-листенеры на IntersectionObserver | content.js, popup.js (где есть скролл) | ⏭️ нет целевых мест |

---

## Фаза 2: Разделение монолитов (3–5 дней)

**Цель:** −60% размера загружаемого кода, −50% memory footprint.

| # | Задача | Детали | Статус |
|---|--------|--------|--------|
| 2.1 | content.js → модули по контексту | modules/linkedin-profile.js, linkedin-messaging.js (linkedin-search.js — при появлении страницы поиска) | ✅ |
| 2.2 | popup.js → Strategy (вкладки) | tabs/registry.js, tabs/meet-tab.js (остальные вкладки выносить по мере внедрения Event Bus / State Manager) | ✅ |
| 2.3 | Вынести CSS из HTML | options.html, popup.html → options.css, popup.css | ✅ |
| 2.4 | Virtual scrolling для длинных списков | popup.js (вакансии, кандидаты) | ⏭️ текущие объёмы данных не требуют виртуализации |

---

## Фаза 3: Архитектурные паттерны (5–7 дней)

**Цель:** Улучшение поддерживаемости, готовность к unit-тестам.

| # | Задача | Детали | Статус |
|---|--------|--------|--------|
| 3.1 | Event Bus для межмодульной коммуникации | shared/event-bus.js; HRH.eventBus.on/emit, popup:contextChanged | ✅ |
| 3.2 | State Manager для popup.js | shared/state-manager.js; popupState(currentContext), подписки tab-модулей | ✅ |
| 3.3 | Dependency Injection (storage, api) | HRH.apiFetch вместо прямого fetch в popup.js, возможность подмены в тестах | ✅ |
| 3.4 | Полная миграция на shared/api/client.js | popup.js и content-* используют HRH.apiFetch для API Huntflow/LinkedIn | ✅ |

---

## Фаза 4: Build-система (2–3 дня)

**Цель:** −40% финального размера bundle, tree-shaking, code splitting.

| # | Задача | Детали | Статус |
|---|--------|--------|--------|
| 4.1 | Настроить Vite/Rollup для расширения | package.json (scripts dev/build), vite.config.mts с мульти-входами popup/options/content/background | ✅ |
| 4.2 | Tree-shaking и code splitting | Динамический импорт модулей по контексту | 🔲 |
| 4.3 | Минификация и бандлинг | Один/несколько бандлов для content, popup, options | 🔲 |

---

## Чеклист качества кода (Code Review)

- [ ] Нет глобальных переменных (кроме `window.__HRH__`)
- [ ] Все функции < 50 строк
- [ ] Нет дублирования кода (DRY)
- [ ] Используется shared/* вместо локальных копий
- [ ] Debounce для event handlers и MutationObserver
- [ ] Lazy loading где возможно
- [ ] Error boundaries (try/catch вокруг async)
- [ ] Константы вынесены в конфиг
- [ ] CSS в отдельных файлах
- [ ] JSDoc для публичных функций

---

## Реализовано в рамках Фазы 1 (текущая сессия)

1. **shared/utils/debounce.js** — общая функция debounce, привязана к `__HRH__.debounce`.
2. **shared/constants.js** — добавлен объект `TIMING` (DEBOUNCE_MUTATION, DEBOUNCE_THEME и др.).
3. **content.js** — debounce для главного MutationObserver (schedule), для theme observers и для trackMessageButtons.
4. **content-resume.js** — debounce для MutationObserver в run().
5. **content-calendar.js** — debounce для theme observer в startCalendarThemeObserver.
6. **content-meet.js** — debounce для MutationObserver ensureOpenAllButton.
7. **manifest.json** — в content_scripts добавлен `shared/utils/debounce.js` для всех скриптов, использующих debounce.

**1.3 batch storage (popup.js):** функция `getFloatingHiddenStates()` — один вызов `chrome.storage.local.get` для всех ключей видимости плавающих окон; при открытии попапа — параллельный `Promise.all` (sync: active pages, local: floating hidden); результат передаётся в `update*Toggle(preloaded)`.

---

## Версия 1.4.10 (18.03.2026)

- **HH экосистема (content-resume.js):** нормализация ответа candidate-info (`normalizeCandidatePayload`) — ФИО, контакты и дополнительные поля всегда отображаются в плавающем окне (поддержка формата ответа с `data` и без).
- **HH экосистема:** кнопки «Пригласить» и «Отказать» в одной строке; в карточках вакансий — кнопка копирования ссылки; в шапке плавающего окна — кнопка «Открыть кандидата в Huntflow в новой вкладке» (иконка внешней ссылки) вместо кнопки чата.
- **Попап (popup.js):** обработка ошибки «Could not establish connection. Receiving end does not exist» в `openMeetAll()` при недоступности контент-скрипта (вкладка закрыта или не Meet).

**1.4 lazy loading (content.js):** плавающий виджет LinkedIn создаётся только по требованию: вызов `insertFloatingWidget()` убран из `ensureButtons()`; виджет создаётся в `refreshButtonForCurrentProfile()` после определения контекста (загрузка, «укажи ссылку», кэш, ответ API). В `ensureButtons()` при наличии уже созданного виджета вызывается только `updateFloatingWidget()`. content-resume.js и content-huntflow.js уже создают виджеты по требованию (при первом показе данных).

**1.5 IntersectionObserver:** в content.js и popup.js целевых scroll-листенеров не найдено; замена отложена до появления сценариев «подгрузка при скролле».

**Фаза 2 (продолжение):**
- **2.3 (12.03.2026):** Стили вынесены из `popup.html` и `options.html` в отдельные файлы `popup.css` и `options.css`; в HTML оставлена только ссылка `<link rel="stylesheet" href="popup.css" />` / `options.css`. Улучшена поддерживаемость и подготовка к сборке (Фаза 4).

**2.1 (модули content.js):** Добавлены `modules/linkedin-profile.js` (findActionContainer, findCoverContainer, findActivitySection, looksLikeProfileActionArea, findAllMoreButtons) и `modules/linkedin-messaging.js` (extractThreadIdFromMessageButton, saveThreadMappingToBackend, captureProfileToThreadMapping, getProfileLinkFromMessaging, findMessagingComposer). Модули подключаются в manifest до content.js; content.js делегирует вызовы через алиасы. Динамический импорт по pageType — в Фазе 4 (сборка).

**2.2 (Strategy для вкладок popup):** Введён реестр контекстов и модуль Meet. Добавлены `tabs/registry.js` (getBlockId, getTabName, isLinkedInBlock) и `tabs/meet-tab.js` (updateMeetUI, setMeetNoDataUI). В popup.js используются getBlockId/isLinkedInBlock для выбора блока и вызов HRH.tabs.meet.updateMeetUI/setMeetNoDataUI при контексте Meet. Подключение: `tabs/registry.js` и `tabs/meet-tab.js` в `popup.html` до `popup.js`. В дальнейшем вкладки LinkedIn / Calendar / Huntflow будут выноситься в отдельные модули в рамках Фазы 3 (вместе с Event Bus и State Manager), чтобы не дублировать работу.

**2.4 (virtual scrolling):** При текущих объёмах списков (вакансии/кандидаты) классическая виртуализация (windowing) не даёт заметного выигрыша и усложнит код попапа. Если объёмы данных вырастут, задачу можно вернуть в бэклог.

Фаза 2 завершена. Далее по плану: Фаза 3 (архитектурные паттерны: Event Bus, State Manager, DI, миграция на shared/api/client.js).

Фазы 1–4 на текущий момент реализованы полностью (см. статус задач выше); дальнейшая доработка — по мере появления новых требований и сценариев использования.
