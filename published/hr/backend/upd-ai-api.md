Теперь у меня полная картина всех файлов. Все бэкенд-части **уже написаны и готовы** — модель, сервис, сериализатор. Остались только frontend-шаги. Расскажу точно, что и где нужно сделать.

***

## Полная картина: что уже готово, что нужно сделать

### ✅ Уже реализовано в коде (делать ничего не нужно)

| Файл | Что уже есть |
|---|---|
| `apps/accounts/models.py` | `AIModelChoice` + поле `preferred_ai_model` — **уже в модели**  |
| `apps/accounts/serializers.py` | `UserSettingsSerializer` — `preferred_ai_model` + `available_ai_models` уже добавлены; `ApiKeyTestSerializer` — поле `model` уже есть  |
| `logic/utilities/account_services.py` | `update_user_api_keys` сохраняет `preferred_ai_model`; `test_api_key_integration` принимает `model=` kwarg  |
| `logic/ai_analysis/gemini_services.py` | `DEFAULT_MODEL`, `AVAILABLE_MODELS` как список dict'ов, `__init__(api_key, model=None)` — всё уже есть  |
| `apps/accounts/views_api.py` | `update_api_keys` и `test_integration` — правильно передают данные в сервис  |

***

### ❗ Что нужно сделать: только 3 шага

***

## Шаг 1 — Миграция БД

Поле `preferred_ai_model` уже в `models.py`, но нужно создать и применить миграцию:

```bash
cd /путь/к/проекту/hr/backend

python manage.py makemigrations accounts
python manage.py migrate
```

Проверь, что создался файл вида `apps/accounts/migrations/00XX_user_preferred_ai_model.py`. Если поле уже было добавлено ранее и миграция уже есть — `migrate` просто скажет "No migrations to apply."
Ошибка при обработке HR-скрининга: ["Ошибка анализа с Gemini: Ошибка Gemini API: Квота API ключа не активирована или исчерпана.\n\nYou exceeded your current quota, please check your plan and billing details. For more information on this error, head to: https://ai.google.dev/gemini-api/docs/rate-limits. To monitor your current usage, head to: https://ai.dev/rate-limit. \n* Quota exceeded for metric: generativelanguage.googleapis.com/generate_content_free_tier_input_token_count, limit: 0, model: gemini-2.0-flash\n* Quota exceeded for metric: generativelanguage.googleapis.com/generate_content_free_tier_requests, limit: 0, model: gemini-2.0-flash\n* Quota exceeded for metric: generativelanguage.googleapis.com/generate_content_free_tier_requests, limit: 0, model: gemini-2.0-flash\nPlease retry in 13.066891795s.\n\n⚠️ ПРОБЛЕМА: Обнаружен 'limit: 0' - это означает отсутствие доступа к квоте.\n\nВОЗМОЖНЫЕ ПРИЧИНЫ:\n1. API ключ не активирован в Google Cloud Console\n2. Gemini API не включен для проекта\n3. Квота Free tier не доступна для этого ключа\n\nРЕШЕНИЯ:\n1. Проверьте статус API ключа: https://makersuite.google.com/app/apikey\n2. Убедитесь, что Gemini API включен в Google Cloud Console\n3. Создайте новый API ключ в Google AI Studio\n4. Проверьте использование: https://ai.dev/usage?tab=rate-limit"]
***

## Шаг 2 — Добавить блок выбора модели в шаблон `api_keys.html`

**Файл:** `templates/profile/api_keys.html`

Внутри карточки `<!-- Gemini AI -->` после блока с `result_gemini` и `form-text` (ссылка на Google AI Studio), прямо перед закрывающим `</div>` карточки — вставить:

```html
<!-- ─── Выбор базовой AI-модели ─────────────────────────────── -->
<div class="mt-3 p-3" style="background:var(--bs-body-bg,#f8f9fa);
     border:1px solid var(--bs-border-color,#dee2e6);border-radius:.5rem;">

    <div class="d-flex align-items-center justify-content-between mb-2">
        <label for="preferred_ai_model" class="form-label mb-0 fw-semibold">
            <i class="fas fa-microchip me-1"></i>
            Базовая модель
            <span id="current-model-badge"
                  style="font-size:.7rem;font-weight:600;padding:2px 8px;
                         border-radius:4px;background:rgba(52,168,83,.15);
                         color:#34a853;margin-left:6px;vertical-align:middle;">
                {{ user.preferred_ai_model|default:"gemini-2.0-flash" }}
            </span>
        </label>
        <a href="https://ai.google.dev/gemini-api/docs/models"
           target="_blank" class="text-muted small">
            <i class="fas fa-external-link-alt me-1"></i>Сравнить модели
        </a>
    </div>

    <select class="form-select" id="preferred_ai_model" name="preferred_ai_model"
            onchange="document.getElementById('current-model-badge').textContent = this.value">
        <option value="gemini-2.0-flash"
            {% if user.preferred_ai_model == 'gemini-2.0-flash' or not user.preferred_ai_model %}selected{% endif %}>
            Gemini 2.0 Flash — быстрый, баланс скорости/качества
        </option>
        <option value="gemini-2.0-flash-lite"
            {% if user.preferred_ai_model == 'gemini-2.0-flash-lite' %}selected{% endif %}>
            Gemini 2.0 Flash Lite — максимально лёгкий и дешёвый
        </option>
        <option value="gemini-1.5-pro"
            {% if user.preferred_ai_model == 'gemini-1.5-pro' %}selected{% endif %}>
            Gemini 1.5 Pro — мощный, контекст 2M токенов
        </option>
        <option value="gemini-1.5-flash"
            {% if user.preferred_ai_model == 'gemini-1.5-flash' %}selected{% endif %}>
            Gemini 1.5 Flash — компактный 1.5 поколения
        </option>
        <option value="gemini-1.0-pro"
            {% if user.preferred_ai_model == 'gemini-1.0-pro' %}selected{% endif %}>
            Gemini 1.0 Pro — классическая версия
        </option>
    </select>

    <div class="form-text mt-2">
        <i class="fas fa-info-circle me-1"></i>
        Модель используется для всех AI-операций (анализ резюме, генерация писем, чат).
        «Тестировать» выше проверяет ключ именно на этой модели.
    </div>
</div>
<!-- ──────────────────────────────────────────────────────────── -->
```

***

## Шаг 3 — Добавить передачу модели в `testApiKey` в том же шаблоне

В `<script>` блоке уже есть функция `testApiKey(provider, system)`. Найди строку, где формируется `data`:

```javascript
const data = {
    'api_key': apiKeyField.value
};
```

Сразу после неё (и после блоков `if (apiUrlField)` / `if (system)`) добавь:

```javascript
// передаём выбранную модель при тестировании Gemini
if (provider === 'gemini') {
    const modelSel = document.getElementById('preferred_ai_model');
    if (modelSel) data['model'] = modelSel.value;
}
```

***

## Итог: как работает полный флоу после правок

```
Страница /accounts/api-keys/
    ↓ user вводит ключ + выбирает модель
    
POST /accounts/test-gemini/
    → data: { api_key, model }
    → UserService.test_api_key_integration('gemini', api_key, model=model)
    → GeminiService(api_key, model=model).test_connection()
    → реальный запрос к выбранной модели ✅

POST form (кнопка «Сохранить API ключи»)
    → data: { gemini_api_key, preferred_ai_model, ... }
    → UserService.update_user_api_keys(user, data)
    → user.preferred_ai_model = data['preferred_ai_model']
    → user.save() ✅

Любой вызов GeminiService во view/task:
    → GeminiService(user.gemini_api_key, model=user.preferred_ai_model)
    → использует выбранную пользователем модель ✅
```

Все остальные файлы (`account_services.py`, `serializers.py`, `models.py`, `gemini_services.py`, `views_api.py`) — **уже содержат всё необходимое**, трогать их не нужно. Достаточно трёх шагов выше.