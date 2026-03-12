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
| 1.4 | Lazy loading виджетов (создавать по требованию) | content.js, content-resume.js, content-huntflow.js | 🔲 |
| 1.5 | Заменить scroll-листенеры на IntersectionObserver | content.js, popup.js (где есть скролл) | 🔲 |

---

## Фаза 2: Разделение монолитов (3–5 дней)

**Цель:** −60% размера загружаемого кода, −50% memory footprint.

| # | Задача | Детали | Статус |
|---|--------|--------|--------|
| 2.1 | content.js → модули по контексту | modules/linkedin-profile.js, linkedin-search.js, linkedin-messaging.js; динамический импорт по pageType | 🔲 |
| 2.2 | popup.js → Strategy (вкладки) | tabs/linkedin-tab.js, huntflow-tab.js, calendar-tab.js, analytics-tab.js | 🔲 |
| 2.3 | Вынести CSS из HTML | options.html, popup.html → options.css, popup.css | 🔲 |
| 2.4 | Virtual scrolling для длинных списков | popup.js (вакансии, кандидаты) | 🔲 |

---

## Фаза 3: Архитектурные паттерны (5–7 дней)

**Цель:** Улучшение поддерживаемости, готовность к unit-тестам.

| # | Задача | Детали | Статус |
|---|--------|--------|--------|
| 3.1 | Event Bus для межмодульной коммуникации | shared/event-bus.js; замена window.* и прямых вызовов | 🔲 |
| 3.2 | State Manager для popup.js | shared/state-manager.js; замена глобальных переменных | 🔲 |
| 3.3 | Dependency Injection (storage, api) | Сервисы с инжектируемым storage/api для тестов | 🔲 |
| 3.4 | Полная миграция на shared/api/client.js | Убрать дублирование apiFetch из content-*, popup | 🔲 |

---

## Фаза 4: Build-система (2–3 дня)

**Цель:** −40% финального размера bundle, tree-shaking, code splitting.

| # | Задача | Детали | Статус |
|---|--------|--------|--------|
| 4.1 | Настроить Vite/Rollup для расширения | Конфиг под Chrome Extension Manifest V3 | 🔲 |
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

Далее по плану: 1.4 (lazy loading), 1.5 (IntersectionObserver).
