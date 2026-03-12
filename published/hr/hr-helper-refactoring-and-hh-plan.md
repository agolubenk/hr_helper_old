# План рефакторинга HR Helper и расширения функциональности для hh.ru/rabota.by

## 0. Цели и ограничения

- Упростить поддержку и развитие расширения за счёт модульной архитектуры, соблюдения принципов **SOLID** и **DRY**.
- Сохранить текущее поведение для LinkedIn, Huntflow, Google Calendar, Google Meet.
- Добавить новую функциональность для страниц **hh.ru / rabota.by**:
  - Проверка подключения аккаунта к HR Helper.
  - В плавающем окне на резюме выводить кнопки **«Пригласить» / «Отказать»**.
  - При нажатии:
    - синхронизировать статус и комментарии с Huntflow;
    - обновить статус кандидата на самом портале (hh.ru / rabota.by).

---

## 1. Наведение порядка в репозитории

### 1.1. Очистка лишних файлов

- Удалить из репозитория:
  - `content.js.bak`.
  - `node_modules/`.
- Добавить `.gitignore` с правилами:
  - `node_modules/`
  - `*.bak`
  - `dist/`, `*.log` (на будущее при добавлении сборщика).

**Результат:** репозиторий не захламлён зависимостями и временными файлами, проще работать с историей изменений.

---

## 2. Доведение shared-инфраструктуры до консистентного состояния

### 2.1. Жёсткие зависимости от `shared/`

Сейчас в коде используются конструкции вида:

```js
const apiFetch = (window.__HRH__ && window.__HRH__.apiFetch) || (function () { ...fallback... })();
```

Необходимо заменить их на жёсткую зависимость:

```js
const apiFetch = window.__HRH__.apiFetch;
if (!apiFetch) {
  throw new Error('[HRHelper] shared/api/client.js not loaded');
}
```

Аналогично для:
- `normalizeLinkedInProfileUrl`
- `getBaseUrl`
- `ACTIVE_PAGES_KEY`
- `DEFAULT_ACTIVE_PAGES`
- `DEFAULTS`
- `OPTIONS_THEME_KEY`

**Файлы:** `content.js`, `popup.js`, `content-resume.js`, `content-huntflow.js`.

### 2.2. Удаление локального `apiFetch` из `content-resume.js`

В `content-resume.js` удалить собственную реализацию `apiFetch` и использовать общий клиент:

```js
const HRH = (typeof window !== 'undefined' && window.__HRH__) || {};
const apiFetch = HRH.apiFetch;
```

**Результат:** единый API-клиент, отсутствие скрытых заглушек, fail-fast при проблемах с загрузкой shared-скриптов.

---

## 3. Централизация утилит (DRY)

### 3.1. Дата/время

Создать `shared/utils/date.js`:

- Вынести туда функции:
  - `formatVacancyDate`.
  - `formatRejectionDateTime`.
  - `formatCommentDate` (если используется).
- Подключить файл во все `content_scripts` и popup.
- В `content.js` и `popup.js` удалить дубли и заменить на обращения к `window.__HRH__.formatVacancyDate` и т.д.

### 3.2. Цвета

Создать `shared/utils/color.js`:

- Вынести туда `hexToRgba` и любую вспомогательную логику вычисления цветов рамок / бейджей.
- Удалить дубли из `content.js` и `content-resume.js`.

### 3.3. Доменная логика статусов

Создать `shared/domain/status-logic.js`:

- Вынести туда функции:
  - `isRejectionStatus`.
  - `isNewStatusName`.
  - `hasBlacklistLabel`.
  - другие проверки статусов, если есть.
- Использовать их в `content.js`, `content-resume.js`, `popup.js` вместо локальных реализаций.

**Результат:** ключевые доменные правила определены в одном месте, проще менять бизнес-логику статусов.

---

## 4. Централизация `fetchStatusMulti` и связанной API-логики

### 4.1. Общий модуль статусов

Создать `shared/api/status.js`:

```js
(function () {
  var g = typeof window !== 'undefined' ? window : self;
  g.__HRH__ = g.__HRH__ || {};

  async function fetchStatusMulti(params) {
    var apiFetch = g.__HRH__.apiFetch;
    var normalize = g.__HRH__.normalizeLinkedInProfileUrl;
    var qp = new URLSearchParams();

    if (params.linkedinUrl) {
      var li = normalize(params.linkedinUrl);
      if (li) qp.set('linkedin_url', li);
    }
    if (params.huntflowUrl) {
      qp.set('huntflow_url', params.huntflowUrl);
    }

    if (!qp.toString()) {
      return { error: 'Нужен linkedin_url или huntflow_url' };
    }

    var res = await apiFetch('/api/v1/huntflow/linkedin-applicants/status-multi/?' + qp.toString());
    var data = await res.json();
    if (!res.ok || !data) return { error: 'Ошибка API' };
    return data;
  }

  g.__HRH__.fetchStatusMulti = fetchStatusMulti;
})();
```

Добавить `shared/api/status.js` в `manifest.json` для всех `content_scripts` и, при необходимости, для popup через `web_accessible_resources` или отдельный скрипт.

### 4.2. Удаление дублей `fetchStatusMulti`

- В `content.js`, `popup.js`, `content-resume.js`, `content-huntflow.js` удалить локальные определения `fetchStatusMulti`.
- Везде использовать:

```js
const fetchStatusMulti = window.__HRH__.fetchStatusMulti;
...
const data = await fetchStatusMulti({ linkedinUrl, huntflowUrl });
```

**Результат:** единая реализация API-логики статусов, меньше расхождений поведения.

---

## 5. Декомпозиция `content.js` по доменам

Цель: убрать God File, не меняя внешнего поведения.

### 5.1. Выделение Google Meet

1. Создать `content-meet.js`.
2. Вырезать из `content.js` функцию `initGoogleMeet()` и все используемые ею вспомогательные функции, перенести в `content-meet.js`.
3. Общие утилиты, которые нужны и LinkedIn, и Meet, вынести в `shared/utils`.
4. В `manifest.json` заменить для `*://meet.google.com/*`:
   - `"js": ["shared/...", "content.js"]` → `"js": ["shared/...", "content-meet.js"]`.

### 5.2. Выделение Google Calendar

Аналогично Meet:

1. Создать `content-calendar.js`.
2. Вырезать `initGoogleCalendar()` и связанные функции из `content.js`.
3. В `manifest.json` для `calendar.google.com` подключать `content-calendar.js`.

### 5.3. Итог

- `content.js` отвечает только за LinkedIn (профиль + messaging + плавающее окно).
- `content-meet.js` — только Meet.
- `content-calendar.js` — только Calendar.

**Результат:** уменьшение размера `content.js` и чёткое разделение областей ответственности.

---

## 6. Рефакторинг popup (контекстные стратегии)

### 6.1. Использование shared-констант в popup

Вместо локального `DEFAULTS` в `popup.js`:

```js
const DEFAULTS = window.__HRH__.DEFAULTS;
```

### 6.2. Разделение контекста по типам страниц

Сейчас `showContextForTab()` содержит большую ветвистую логику. Необходимо:

1. Внутри `popup.js` или в отдельном файле `popup-contexts.js` завести реестр рендереров:

```js
const CONTEXT_RENDERERS = {
  linkedin: renderLinkedInContext,
  calendar: renderCalendarContext,
  meet: renderMeetContext,
  resume: renderResumeContext,
  huntflow: renderHuntflowContext,
};

function renderContext(context, state) {
  const renderer = CONTEXT_RENDERERS[context.type] || renderOtherContext;
  return renderer(context, state);
}
```

2. В `showContextForTab()` оставить лишь:

```js
async function showContextForTab() {
  const context = await detectContext();
  const state = await loadPopupState();
  renderContext(context, state);
}
```

**Результат:** добавление нового типа страницы потребует только добавления нового рендерера и строки в `CONTEXT_RENDERERS` (OCP).

---

## 7. SVG-иконки и стили

### 7.1. Общий модуль иконок

Создать `shared/ui/icons.js` и вынести туда все SVG-иконки (LinkedIn, Telegram, WhatsApp, Viber и т.д.), которые сейчас объявлены в `content.js` и `content-huntflow.js`.

```js
(function () {
  var g = typeof window !== 'undefined' ? window : self;
  g.__HRH__ = g.__HRH__ || {};

  g.__HRH__.ICONS = {
    linkedin: '<svg ...></svg>',
    telegram: '<svg ...></svg>',
    whatsapp: '<svg ...></svg>',
    // ...
  };
})();
```

Заменить локальные `ICONS` на `HRH.ICONS` там, где они используются.

### 7.2. Стили

По мере возможности:
- переезжать с `element.style.* = ...` на CSS-классы и отдельные `.css` файлы;
- особенно актуально для popup и options, где стилей уже много.

---

## 8. Новая функциональность для hh.ru / rabota.by

Ниже — план только для блока резюме (content-resume.js) и частично popup, без реализации сетевых деталей порталов (они зависят от их DOM и API).

### 8.1. Проверка подключения ресурса в HR Helper

**Цель:** понимать, подключен ли у пользователя hh.ru / rabota.by в настройках HR Helper.

1. На стороне backend HR Helper убедиться, что в API есть метод/поле, позволяющее узнать наличие интеграции с hh.ru / rabota.by для текущего пользователя (например, `/api/v1/integrations/` или флаг в ответе статуса кандидата).
2. В `content-resume.js` добавить функцию:

```js
async function checkEcosystemIntegration() {
  const apiFetch = HRH.apiFetch;
  const res = await apiFetch('/api/v1/integrations/hh-ecosystem/');
  const data = await res.json();
  return !!(res.ok && data && data.connected);
}
```

3. При инициализации плавающего окна на резюме:
   - сначала проверить `checkEcosystemIntegration()`;
   - если нет подключения — не показывать новые кнопки и, возможно, вывести подсказку в виджете.

### 8.2. Добавление кнопок «Пригласить» / «Отказать» в плавающее окно

**Место:** плавающее окно на hh.ru / rabota.by (content-resume.js) — сразу после заголовка, но до области контактов.

1. В логике построения плавающего окна (там, где уже рендерятся данные кандидата из Huntflow):
   - найти место, где есть header блока (ФИО / заголовок);
   - сразу после него вставить контейнер с двумя кнопками:

```js
const actionsContainer = document.createElement('div');
actionsContainer.className = 'hrhelper-resume-actions';

const inviteBtn = document.createElement('button');
inviteBtn.textContent = 'Пригласить';
inviteBtn.className = 'hrhelper-btn hrhelper-btn-primary';

const rejectBtn = document.createElement('button');
rejectBtn.textContent = 'Отказать';
rejectBtn.className = 'hrhelper-btn hrhelper-btn-secondary';

actionsContainer.append(inviteBtn, rejectBtn);
headerElement.after(actionsContainer);
```

2. Стили для кнопок описать в отдельном CSS (или переиспользовать стили popup, если есть).

### 8.3. Логика «Пригласить» для hh.ru / rabota.by

При клике на кнопку **«Пригласить»** должны произойти шаги:

1. **Huntflow:**
   - установить метку «Отклик» (label или tag, в зависимости от API);
   - установить этап "Message";
   - записать комментарий "Invited hh.ru" или "Invited rabota.by".

   Пример псевдокода:

```js
async function onInviteClick(candidateId, portalType) {
  const apiFetch = HRH.apiFetch;

  // 1) Обновить кандидата в Huntflow
  await apiFetch('/api/v1/huntflow/candidates/' + candidateId + '/status/', {
    method: 'POST',
    body: JSON.stringify({
      label: 'Отклик',
      stage: 'Message',
      comment: portalType === 'hh' ? 'Invited hh.ru' : 'Invited rabota.by',
    }),
  });

  // 2) Обновить статус на портале (DOM/API hh.ru/rabota.by)
  await setPortalStatusInvited(portalType);
}
```

2. **Портал hh.ru / rabota.by:**
   - найти в DOM dropdown / кнопку смены статуса резюме;
   - выбрать статус «Первичный контакт»;
   - если портал позволяет, вставить текст сообщения по шаблону.

   Это потребует отдельной функции `setPortalStatusInvited(portalType)`, которая будет работать с DOM конкретного портала (возможно, два варианта — под hh и под rabota.by).

### 8.4. Логика «Отказать» для hh.ru / rabota.by

При клике на кнопку **«Отказать»**:

1. Открыть небольшое модальное окно / выпадающий блок внутри плавающего окна с формой:
   - select со списком причин отказа (подтягиваются из Huntflow: `/api/v1/huntflow/rejection-reasons/`);
   - textarea для комментария (опционально);
   - кнопки «Подтвердить» / «Отмена».

2. После подтверждения:

   **Huntflow:**
   - установить статус «Отказ» с выбранной причиной;
   - при необходимости добавить комментарий.

   Псевдокод:

```js
async function onRejectConfirm(candidateId, reasonId, comment, portalType) {
  const apiFetch = HRH.apiFetch;

  await apiFetch('/api/v1/huntflow/candidates/' + candidateId + '/reject/', {
    method: 'POST',
    body: JSON.stringify({
      reason_id: reasonId,
      comment: comment || null,
    }),
  });

  await setPortalStatusRejected(portalType);
}
```

   **Портал hh.ru / rabota.by:**
   - сменить статус на «Отказ: не подходит» через DOM/их API.

3. Закрыть модальное окно и обновить отображение статуса в плавающем виджете (например, подсветить статус красным, показать причину).

### 8.5. Где брать `candidateId` и `portalType`

- `candidateId` — уже должен быть доступен в `content-resume.js`, так как виджет подгружает данные из Huntflow по ссылкам/соответствию резюме.
- `portalType` можно определить по URL:

```js
function getPortalType() {
  const host = location.hostname;
  if (host.includes('hh.ru')) return 'hh';
  if (host.includes('rabota.by')) return 'rabota';
  return 'unknown';
}
```

### 8.6. Права доступа и ошибки

- Обработать ошибки API (Huntflow или портала) — показывать уведомление в плавающем окне (мини-тост).
- Убедиться, что `host_permissions` в `manifest.json` уже содержат домены hh.ru и rabota.by (они есть, но стоит ещё раз проверить перед деплоем).

---

## 9. Приоритеты реализации

Рекомендуемый порядок внедрения:

1. **Репозиторий и shared-инфраструктура** (разделы 1–4) — убирают дублирование и делают базу стабильной.
2. **Декомпозиция `content.js`** (раздел 5) — уменьшает риск ломать LinkedIn при изменении Meet/Calendar.
3. **Рефакторинг popup** (раздел 6) — улучшает работу контекстов.
4. **SVG/стили** (раздел 7) — повышают читаемость и переиспользование UI.
5. **Новая функциональность hh.ru/rabota.by** (раздел 8) — можно начинать параллельно после завершения shared-части, когда есть устойчивый `apiFetch` и статусная логика.

