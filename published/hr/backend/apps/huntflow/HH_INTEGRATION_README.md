# Интеграция с HH.ru - Краткое руководство

## Быстрый старт

### 1. API Endpoint

**URL:** `POST /api/v1/huntflow/hh-responses/import-hh-responses/`

**Требуется аутентификация:** Да (IsAuthenticated)

### 2. Пример запроса

```bash
curl -X POST http://localhost:8000/api/v1/huntflow/hh-responses/import-hh-responses/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "account_id": 123,
    "vacancy_id": 456,
    "hh_vacancy_id": "87654321",
    "filters": {
      "allowed_locations": ["1", "2"],
      "allowed_genders": ["any"],
      "min_age": 18,
      "max_age": 65,
      "check_existing": true,
      "min_experience_years": 1,
      "max_experience_years": 50
    }
  }'
```

### 3. Параметры запроса

#### Обязательные параметры:
- `account_id` (int) - ID организации в Huntflow
- `vacancy_id` (int) - ID вакансии в Huntflow
- `hh_vacancy_id` (string) - ID вакансии на HH.ru

#### Опциональные параметры:
- `filters` (dict) - Критерии фильтрации:
  - `allowed_locations` (list) - Разрешенные локации (ID городов HH.ru)
    - `["1"]` - только Москва
    - `["1", "2"]` - Москва и Санкт-Петербург
    - `["1", "2", "3"]` - Москва, СПб, Екатеринбург
  - `allowed_genders` (list) - Разрешенные полы
    - `["male"]` - только мужчины
    - `["female"]` - только женщины
    - `["any"]` - любой пол
  - `min_age` (int) - Минимальный возраст (по умолчанию: 18)
  - `max_age` (int) - Максимальный возраст (по умолчанию: 65)
  - `check_existing` (bool) - Проверять наличие в базе (по умолчанию: true)
  - `min_experience_years` (int) - Минимальный опыт в годах (по умолчанию: 1)
  - `max_experience_years` (int) - Максимальный опыт в годах (по умолчанию: 50)

### 4. Пример ответа

```json
{
  "success": true,
  "imported": 5,
  "filtered_out": 3,
  "errors": 0,
  "imported_candidates": [
    {
      "id": 123,
      "first_name": "Иван",
      "last_name": "Иванов",
      "email": "ivan@example.com"
    }
  ],
  "filter_results": {
    "total_responses": 8,
    "passed_filter": 5,
    "rejected": {
      "location_mismatch": 1,
      "age_mismatch": 1,
      "experience_mismatch": 1,
      "gender_mismatch": 0,
      "already_in_db": 0,
      "other": 0
    }
  },
  "message": "Импортировано 5 кандидатов, отклонено 3"
}
```

## Использование в Python коде

### Пример 1: Простой импорт

```python
from apps.huntflow.hh_integration import HHResponsesHandler

# Инициализация
user = request.user  # Django пользователь
handler = HHResponsesHandler(user)

# Получение откликов
responses = handler.get_responses_from_hh(
    vacancy_id="87654321",
    page=0,
    per_page=100
)

# Фильтрация и импорт
filters = {
    'allowed_locations': ['1'],  # Только Москва
    'allowed_genders': ['any'],
    'min_age': 25,
    'max_age': 50,
    'check_existing': True,
    'min_experience_years': 2,
    'max_experience_years': 30
}

result = handler.filter_and_import_responses(
    responses['items'],
    account_id=123,
    vacancy_id=456,
    filters=filters
)

print(f"Импортировано: {result['imported']}")
print(f"Отфильтровано: {result['filtered_out']}")
```

### Пример 2: Использование через HuntflowOperations

```python
from logic.integration.shared.huntflow_operations import HuntflowOperations

operations = HuntflowOperations(request.user)

result = operations.get_and_import_hh_responses(
    account_id=123,
    vacancy_id=456,
    hh_vacancy_id="87654321",
    filters={
        'allowed_locations': ['1', '2'],
        'min_age': 25,
        'max_age': 50
    }
)
```

## ID городов HH.ru (основные)

- `"1"` - Москва
- `"2"` - Санкт-Петербург
- `"3"` - Екатеринбург
- `"4"` - Новосибирск
- `"76"` - Казань
- `"88"` - Нижний Новгород
- `"104"` - Челябинск
- `"120"` - Самара
- `"137"` - Омск
- `"153"` - Ростов-на-Дону

Полный список: https://api.hh.ru/areas

## Модели базы данных

### HHResponse
Хранит информацию об откликах из HH.ru

### HHSyncConfiguration
Конфигурация автоматической синхронизации

### HHSyncLog
Логи синхронизаций

### HHFilterStatistics
Статистика фильтрации

Все модели доступны в Django Admin для просмотра и управления.

## Логирование

Все операции логируются в модель `HuntflowLog`:
- Получение откликов из HH.ru
- Импорт кандидатов
- Ошибки

## Обработка ошибок

API возвращает понятные сообщения об ошибках:
- `400 Bad Request` - неверные параметры запроса
- `500 Internal Server Error` - ошибка сервера

Все ошибки логируются для последующего анализа.

## Дополнительная информация

Подробная документация находится в файлах:
- `backend/PM/HH_responses_integration.md`
- `backend/PM/HH_integration_examples.md`
- `backend/PM/HH_models_and_queries.md`
- `backend/PM/Implementation_checklist.md`

