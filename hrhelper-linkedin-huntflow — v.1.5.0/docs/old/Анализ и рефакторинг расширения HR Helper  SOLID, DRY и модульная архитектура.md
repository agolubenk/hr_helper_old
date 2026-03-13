# Анализ и план рефакторинга Chrome-расширения HR Helper

## Обзор текущего состояния

Расширение **HR Helper** (v1.4.7, Manifest V3) интегрирует LinkedIn, rabota.by/hh.ru, Huntflow, Google Calendar и Google Meet с бэкендом HR-системы. Кодовая база состоит из 6 JavaScript-файлов без системы модулей и без сборщика, при этом общий объём исходного кода превышает 10 000 строк.

| Файл | Строк | Размер | Ответственность |
|------|--------|--------|-----------------|
| `content.js` | 5 556 | 254 KB | LinkedIn + Calendar + Meet |
| `popup.js` | 2 524 | 124 KB | Popup UI |
| `content-resume.js` | 1 154 | 55 KB | rabota.by / hh.ru |
| `content-huntflow.js` | 1 067 | 49 KB | Huntflow |
| `background.js` | ~160 | 6 KB | Service Worker / API proxy |
| `options.js` | ~110 | 5 KB | Страница настроек |
| `vacancy-utils.js` | ~60 | 2 KB | Утилиты для вакансий |
| `types.js` | ~35 | 1 KB | JSDoc типы |

Также в репозитории находятся `content.js.bak` (бэкап-файл) и папка `node_modules`, закоммиченная напрямую — оба являются явными anti-patterns для контроля версий.

***

## Критические проблемы архитектуры

### God Object: `content.js` — 5 556 строк

Файл `content.js` является «God Object» — он совмещает минимум 4 несвязанных домена в одном файле. Самые длинные функции:

| Функция | Строк | Назначение |
|---------|--------|------------|
| `initGoogleMeet()` | 1 368 | Весь Google Meet целиком |
| `initGoogleCalendar()` | 618 | Весь Google Calendar целиком |
| `startObserver()` | 277 | MutationObserver для LinkedIn |
| `refreshButtonForCurrentProfile()` | 219 | Обновление UI кнопок |
| `populateFloatingWidgetBody()` | 192 | Рендеринг виджета |
| `onSaveLinkClick()` | 174 | Обработка сохранения |

Одна только `initGoogleMeet()` — 1 368 строк — это больше, чем весь `content-huntflow.js` (1 067 строк). Это грубейшее нарушение **Single Responsibility Principle (SRP)**: один файл отвечает за API-коммуникацию, DOM-манипуляции, управление состоянием, рендеринг UI, определение темы, drag & drop, кэширование, интеграцию с Google Calendar, Google Meet, парсинг профилей LinkedIn и LinkedIn messaging.[^1]

### Массивные нарушения DRY

Анализ показал систематическое дублирование функций и констант между файлами:[^2][^3]

**Константы, продублированные во всех 6 файлах:**
- `ACTIVE_PAGES_KEY` и `DEFAULT_ACTIVE_PAGES` — идентичное определение в `content.js`, `popup.js`, `content-resume.js`, `content-huntflow.js`, `background.js` и `options.js`[^2]

**Функции, продублированные в 2-4 файлах:**

| Функция | Файлы | Копий |
|---------|-------|-------|
| `fetchStatusMulti()` | content.js, popup.js, content-resume.js, content-huntflow.js | 4 |
| `apiFetch()` | content.js, content-resume.js, content-huntflow.js | 3 |
| `normalizeLinkedInProfileUrl()` | content.js, popup.js | 2 |
| `normalizeToken()` | background.js, popup.js, options.js | 3 |
| `categorizeVacancies()` | content.js, popup.js, vacancy-utils.js | 3 |
| `fetchCandidateInfo()` | content.js, popup.js | 2 |
| `formatVacancyDate()` | content.js, popup.js | 2 |
| `formatRejectionDateTime()` | content.js, popup.js | 2 |
| `isRejectionStatus()` | content.js, popup.js | 2 |
| `hexToRgba()` | content.js, content-resume.js | 2 |
| `isNewStatusName()` | content.js, content-resume.js | 2 |
| `hasBlacklistLabel()` | content.js, content-resume.js | 2 |
| `applyFloatingBorder()` | content.js, content-resume.js | 2 |

Это означает, что любое изменение в логике (например, в определении статуса или формате даты) требует правки в 2-4 местах, что неизбежно приводит к рассинхронизации.

### Нарушения OCP (Open-Closed Principle)

Добавление новой страницы (например, поддержка нового job-портала) требует модификации:
- `ACTIVE_PAGES_KEY` / `DEFAULT_ACTIVE_PAGES` в каждом файле
- `getPageTypeFromUrl()` в `background.js`
- Условной логики в `popup.js` (`showContextForTab()` — 323 строки)
- `manifest.json` (content_scripts и host_permissions)

Система не расширяема: невозможно добавить новый тип страницы без изменения существующего кода в 4-6 файлах.

### Отсутствие модульной системы

Расширение не использует ни ES-модули, ни сборщик (Webpack/Rollup/Vite). Content scripts в MV3 не поддерживают ES-модули напрямую, но решение давно существует — использование bundler'а (Rollup/Vite), который собирает модули в IIFE-формат для content scripts.[^4][^5][^6]

Это приводит к невозможности:
- Переиспользовать код между файлами
- Использовать tree-shaking
- Подключать npm-зависимости нормально (вместо этого `node_modules` закоммичена)
- Писать unit-тесты для изолированных модулей

### Inline-всё: CSS, HTML, SVG

Статистика показывает масштабы проблемы:
- **152** вызова `innerHTML` / `createElement` в `content.js`[^1]
- **248** присваиваний `style.*` в `content.js`
- **125** присваиваний `style.*` в `popup.js`
- **35** inline SVG-определений раскиданы по 4 файлам
- Вся стилизация popup (~41 KB) и options (~32 KB) встроена в HTML-файлы

***

## Предлагаемая целевая архитектура

### Технологический стек

Рекомендуемое решение — внедрение **Vite** как сборщика с его плагинами для Chrome Extensions (например, CRXJS Vite Plugin). Это позволит:[^7][^8]

- Использовать ES-модули и `import`/`export` в исходном коде
- Собирать content scripts в IIFE-формат автоматически[^6]
- Подключить TypeScript (постепенно, через JSDoc → TS migration)
- Получить hot reload при разработке[^8]
- Убрать `node_modules` из репозитория

### Структура каталогов

```
src/
├── shared/                      # Переиспользуемые модули
│   ├── constants.js             # ACTIVE_PAGES_KEY, DEFAULTS, etc.
│   ├── api/
│   │   ├── client.js            # apiFetch() — единая реализация
│   │   ├── status.js            # fetchStatusMulti(), checkStatus()
│   │   ├── candidate.js         # fetchCandidateInfo()
│   │   └── vacancy.js           # categorizeVacancies(), addToVacancy()
│   ├── utils/
│   │   ├── url.js               # normalizeLinkedInProfileUrl(), getBaseUrl()
│   │   ├── token.js             # normalizeToken()
│   │   ├── date.js              # formatVacancyDate(), formatRejectionDateTime()
│   │   ├── color.js             # hexToRgba(), computeBorderColor()
│   │   └── dom.js               # makeWidgetDraggable(), injectStyles()
│   ├── ui/
│   │   ├── floating-widget.js   # Базовый класс floating widget
│   │   ├── theme.js             # Определение темы, observer'ы
│   │   ├── icons.js             # Все SVG-иконки
│   │   └── status-badge.js      # Логика отображения статусов
│   └── domain/
│       ├── blacklist.js         # hasBlacklistLabel(), isRejectionReasonClosedByOther()
│       └── status-logic.js      # isNewStatusName(), isRejectionStatus()
│
├── content-scripts/
│   ├── linkedin/
│   │   ├── index.js             # Entry point — LinkedIn profile + messaging
│   │   ├── profile-scanner.js   # Парсинг DOM профиля
│   │   ├── messaging.js         # Логика messaging-страницы
│   │   ├── floating-widget.js   # LinkedIn-специфичный floating widget
│   │   └── observer.js          # MutationObserver для SPA-навигации
│   ├── calendar/
│   │   ├── index.js             # Entry point — Google Calendar
│   │   └── event-panel.js       # Инъекция кнопок в события
│   ├── meet/
│   │   ├── index.js             # Entry point — Google Meet
│   │   ├── reminder.js          # Фраза-напоминание
│   │   └── controls.js          # Кнопки в панели управления
│   ├── resume/
│   │   ├── index.js             # Entry point — rabota.by / hh.ru
│   │   └── floating-widget.js   # Resume-специфичный floating widget
│   └── huntflow/
│       ├── index.js             # Entry point — Huntflow
│       └── social-buttons.js    # Кнопки соцсетей под фото
│
├── popup/
│   ├── popup.js                 # Основная логика popup
│   ├── contexts/                # Контекстные рендереры
│   │   ├── linkedin.js
│   │   ├── calendar.js
│   │   ├── meet.js
│   │   ├── resume.js
│   │   └── huntflow.js
│   └── components/              # Переиспользуемые UI-компоненты
│       ├── vacancy-card.js
│       ├── status-dropdown.js
│       └── copy-buttons.js
│
├── background/
│   └── background.js            # Service worker
│
├── options/
│   └── options.js               # Настройки
│
├── styles/                      # Отдельные CSS-файлы
│   ├── popup.css
│   ├── options.css
│   ├── floating-widget.css
│   └── content-common.css
│
└── manifest.json
```

***

## Пошаговый план рефакторинга

Рефакторинг рекомендуется проводить поэтапно по паттерну **Strangler Fig** — постепенная замена компонентов при сохранении работоспособности системы.[^9]

### Фаза 1: Инфраструктура (1-2 дня)

**Цель:** Настроить сборщик, не меняя бизнес-логику.

1. Инициализировать Vite с плагином CRXJS или собственной конфигурацией Rollup[^6][^8]
2. Добавить `.gitignore` для `node_modules/` и удалить папку из репозитория
3. Удалить `content.js.bak`
4. Настроить `manifest.json` генерацию через сборщик
5. Убедиться, что расширение работает из `dist/` идентично текущему

### Фаза 2: Извлечение shared-модулей (2-3 дня)

**Цель:** Устранить дублирование (DRY).

Порядок извлечения по приоритету:

1. **`shared/constants.js`** — `ACTIVE_PAGES_KEY`, `DEFAULT_ACTIVE_PAGES`, `DEFAULTS` (затрагивает все 6 файлов)[^2]
2. **`shared/utils/token.js`** — `normalizeToken()` (3 копии)
3. **`shared/api/client.js`** — единый `apiFetch()` (3 копии)[^3]
4. **`shared/utils/url.js`** — `normalizeLinkedInProfileUrl()`, `getBaseUrl()`
5. **`shared/utils/date.js`** — `formatVacancyDate()`, `formatRejectionDateTime()`, `formatCommentDate()`
6. **`shared/utils/color.js`** — `hexToRgba()`, `computeFloatingBorderColor*()`
7. **`shared/domain/status-logic.js`** — `isNewStatusName()`, `isRejectionStatus()`, `isRejectionReasonClosedByOther()`
8. **`shared/domain/blacklist.js`** — `hasBlacklistLabel()`, `getPrimaryVacancyForBorder()`
9. **`shared/api/status.js`** — `fetchStatusMulti()`, `fetchCandidateInfo()`
10. **`shared/api/vacancy.js`** — `categorizeVacancies()` (объединить 3 версии в vacancy-utils.js)

Каждый шаг: извлечь → заменить `import` → протестировать.

### Фаза 3: Разделение content.js по доменам (3-5 дней)

**Цель:** Применить SRP — один файл = одна зона ответственности.

Извлечение из `content.js` (5 556 строк → ~5 отдельных модулей):

1. **Google Meet** (строки ~4188–5556) → `content-scripts/meet/` — это 1 368 строк в одной функции, они полностью изолированы
2. **Google Calendar** (строки ~3507–4125) → `content-scripts/calendar/` — 618 строк, также изолированы
3. **MutationObserver** (строки ~3230–3507) → `content-scripts/linkedin/observer.js`
4. **Floating Widget** (строки ~938–1700) → `content-scripts/linkedin/floating-widget.js` + `shared/ui/floating-widget.js`
5. **LinkedIn messaging** (строки ~286–560) → `content-scripts/linkedin/messaging.js`

После этого `content.js` (LinkedIn profile) сократится до ~1 500–2 000 строк.

### Фаза 4: Разделение popup.js (2-3 дня)

**Цель:** Применить Strategy Pattern для контекстных блоков.

Текущая функция `showContextForTab()` — 323 строки с ветвлениями по `context.type`. Рефакторинг:[^1]

```javascript
// popup/contexts/registry.js
const contextRenderers = {
  linkedin: () => import('./linkedin.js'),
  calendar: () => import('./calendar.js'),
  meet:     () => import('./meet.js'),
  resume:   () => import('./resume.js'),
  huntflow: () => import('./huntflow.js'),
};

// popup/popup.js
async function showContextForTab() {
  const context = await getContext();
  const renderer = contextRenderers[context.type];
  if (renderer) {
    const module = await renderer();
    module.render(context);
  }
}
```

Это реализует **OCP** — добавление нового контекста = создание нового файла и одна строка в registry, без модификации существующего кода.[^3]

### Фаза 5: Выделение CSS и SVG (1-2 дня)

**Цель:** Убрать inline-стили из JS.

1. Извлечь все inline-стили из `popup.html` и `options.html` в отдельные `.css` файлы
2. Создать `shared/ui/icons.js` — объект со всеми SVG-иконками (35 определений сейчас раскиданы по файлам)
3. Использовать CSS-классы вместо `style.*` манипуляций в JS — заменить 248 + 125 inline-присваиваний на toggle классов

### Фаза 6: Введение паттернов (2-3 дня)

**Цель:** Улучшить расширяемость (OCP) и инверсию зависимостей (DIP).

**Event Bus для messaging:**
```javascript
// shared/messaging.js
class MessageBus {
  constructor() { this.handlers = new Map(); }
  
  on(type, handler) { 
    this.handlers.set(type, handler); 
  }
  
  async dispatch(type, payload) {
    const handler = this.handlers.get(type);
    if (!handler) throw new Error(`No handler for ${type}`);
    return handler(payload);
  }
}
```

**Strategy для определения типа страницы:**
```javascript
// shared/page-detector.js
const pageStrategies = [
  { type: 'linkedin',     test: (url) => url.hostname.includes('linkedin.com') },
  { type: 'calendar',     test: (url) => url.hostname.includes('calendar.google.com') },
  { type: 'meet',         test: (url) => url.hostname.includes('meet.google.com') },
  { type: 'hh_ecosystem', test: (url) => /* ... */ },
  { type: 'huntflow',     test: (url) => /* ... */ },
];

function getPageType(url) {
  const parsed = new URL(url);
  return pageStrategies.find(s => s.test(parsed))?.type ?? null;
}
```

**State Manager для content scripts:**
Вместо глобального мутабельного объекта `STATE` — легковесный менеджер состояния:
```javascript
// shared/state.js
function createStore(initialState) {
  let state = { ...initialState };
  const listeners = new Set();
  
  return {
    get: (key) => state[key],
    set: (updates) => {
      state = { ...state, ...updates };
      listeners.forEach(fn => fn(state));
    },
    subscribe: (fn) => { listeners.add(fn); return () => listeners.delete(fn); },
  };
}
```

***

## Принципы SOLID в контексте расширения

| Принцип | Текущая проблема | Целевое решение |
|---------|-----------------|-----------------|
| **S** (SRP) | content.js = 4 домена в 1 файле; функции по 1 368 строк | Один файл = одна зона ответственности; функции ≤50 строк |
| **O** (OCP) | Добавление страницы → правки в 6 файлах | Registry + Strategy: новая страница = новый файл + 1 строка регистрации |
| **L** (LSP) | Не применимо напрямую (нет наследования) | Единый интерфейс floating widget для всех платформ |
| **I** (ISP) | `apiFetch()` разный для content/popup/background | Тонкие интерфейсы: `StatusAPI`, `CandidateAPI`, `VacancyAPI` |
| **D** (DIP) | Жёсткие зависимости на `chrome.storage`, `chrome.runtime` | Инъекция зависимостей через параметры; абстракция storage |

***

## Приоритеты и ожидаемый эффект

| Приоритет | Действие | Снижение дублирования | Сложность |
|-----------|----------|----------------------|-----------|
| 🔴 Критично | Настройка Vite + модули | Основа для всего остального | Средняя |
| 🔴 Критично | Извлечение shared-модулей | ~30 дублированных функций → 1 копия | Низкая |
| 🟠 Высокий | Разделение content.js | 5 556 → 5 файлов по ~300–1 500 строк | Средняя |
| 🟠 Высокий | Разделение popup.js (Strategy) | 323-строчный switch → модули | Средняя |
| 🟡 Средний | Выделение CSS/SVG | 373 inline-стиля → CSS-классы | Низкая |
| 🟢 Полезно | Паттерны (EventBus, Store) | Упрощение состояния и messaging | Высокая |
| 🟢 Полезно | TypeScript миграция | Типобезопасность, автодополнение | Высокая |

Общая ожидаемая оценка: 10–15 рабочих дней при последовательном выполнении фаз. Каждая фаза может быть развёрнута независимо, сохраняя работоспособность расширения на каждом этапе.

---

## References

1. [Extension Architecture Patterns (MV3): Messaging, State ...](https://codemyextension.com/resources/extension-architecture/) - Practical MV3 architecture: service workers, content scripts, messaging, state, build pipelines, i18...

2. [Chrome拡張のContentScriptsをES Modulesとして実行する](https://scrapbox.io/dojineko/Chrome%E6%8B%A1%E5%BC%B5%E3%81%AEContentScripts%E3%82%92ES_Modules%E3%81%A8%E3%81%97%E3%81%A6%E5%AE%9F%E8%A1%8C%E3%81%99%E3%82%8B) - まとめ content_scripts は今の所 ES Modules として動作させられない。 そこで起点になるスクリプトから、Dynamic Import することでその制限を回避する。 解説 以...

3. [Modularization Best Practices (MV3 Extensions)](https://codemyextension.com/resources/extension-architecture/modularization-best-practices.html) - Structure extensions by feature verticals, shared libs, and message contracts; enable gradual refact...

4. [Use ES Modules from content_scripts of Web Extension (add-on)](https://stackoverflow.com/questions/50322611/use-es-modules-from-content-scripts-of-web-extension-add-on) - Since the latest Firefox supports ES Modules without flags as well as Chrome, I would like to use im...

5. [How to import ES6 modules in content script for Chrome Extension](https://stackoverflow.com/questions/48104433/how-to-import-es6-modules-in-content-script-for-chrome-extension) - Content scripts are unusual scripts, which are injected through an absolutely different mechanism, n...

6. [vite-plugin-chrome-extension/docs/workflow.md at main · StarkShang/vite-plugin-chrome-extension](https://github.com/StarkShang/vite-plugin-chrome-extension/blob/main/docs/workflow.md) - A vite plugin to bundle chrome extensions for Manifest V3. - StarkShang/vite-plugin-chrome-extension

7. [Build Chrome Extension (MV3) development environment based on Vite + React](https://dev.to/yuns/build-chrome-extension-mv3-development-environment-based-on-vite-react-497h) - Foreword I have always wanted to make a bilibili barrage extension. I recently took the...

8. [Real Vite-React HMR in Chrome Extension Content Scripts](https://dev.to/jacksteamdev/real-vite-react-hmr-in-chrome-extension-content-scripts-40di) - A content script is JavaScript from a Chrome Extension that the browser executes on a designated...

9. [How to Refactor Complex Codebases – A Practical Guide for Devs](https://www.freecodecamp.org/news/how-to-refactor-complex-codebases/) - In this article, I'll walk you through the steps I use to refactor a complex codebase. We'll talk ab...

