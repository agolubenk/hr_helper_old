# Huntflow App - Интеграция с Huntflow API

## Описание
Приложение для интеграции с Huntflow API - системой управления рекрутингом. Предоставляет полный доступ к данным организаций, вакансий, кандидатов и управление ими через веб-интерфейс.

## Зависимости
- Django 5.2.6+
- requests (для API запросов)
- apps.accounts (для API ключей пользователей)
- apps.common (для сайдбара)

## Requirements
```python
# В requirements.txt
Django>=5.2.6
requests>=2.31.0
```

## Связи с другими приложениями
- **apps.accounts**: Получает API ключи Huntflow из профиля пользователя
- **apps.common**: Предоставляет данные организаций для сайдбара
- **apps.interviewers**: Потенциальная связь для управления интервьюерами
- **apps.vacancies**: Потенциальная связь для локальных вакансий

## Модели

### HuntflowCache
**Назначение**: Кэширование данных Huntflow API

**Поля:**
- `cache_key` - ключ кэша (CharField, max_length=255, unique=True)
- `data` - данные (JSONField, default=dict)
- `created_at` - время создания (DateTimeField, default=timezone.now)
- `updated_at` - время обновления (DateTimeField, default=timezone.now)
- `expires_at` - время истечения (DateTimeField, null=True, blank=True)

**Свойства:**
- `is_expired` - истек ли кэш
- `age_minutes` - возраст кэша в минутах

### HuntflowLog
**Назначение**: Логирование операций с Huntflow API

**Поля:**
- `log_type` - тип операции (CharField, choices: GET, POST, PATCH, DELETE, ERROR)
- `endpoint` - эндпоинт API (CharField, max_length=500)
- `method` - HTTP метод (CharField, max_length=10)
- `status_code` - код ответа (IntegerField, null=True, blank=True)
- `request_data` - данные запроса (JSONField, default=dict, blank=True)
- `response_data` - данные ответа (JSONField, default=dict, blank=True)
- `error_message` - сообщение об ошибке (TextField, blank=True)
- `user` - пользователь (ForeignKey на User)
- `created_at` - время создания (DateTimeField, default=timezone.now)

**Свойства:**
- `is_success` - успешен ли запрос
- `is_error` - есть ли ошибка

## Логика работы

### API интеграция
1. **Аутентификация**: Использование API ключей из профиля пользователя
2. **Кэширование**: Сохранение ответов API для оптимизации
3. **Логирование**: Запись всех операций для отладки
4. **Обработка ошибок**: Graceful handling ошибок API

### Управление данными
1. **Организации**: Получение списка организаций пользователя
2. **Вакансии**: Управление вакансиями в организациях
3. **Кандидаты**: Просмотр и редактирование кандидатов
4. **Статусы**: Управление статусами кандидатов

## Сервисы

### HuntflowService
**Файл**: `services.py`

**Методы:**

#### __init__(user)
- **Назначение**: Инициализация сервиса для пользователя
- **Параметры**: user - объект пользователя

#### _get_base_url()
- **Назначение**: Получение базового URL API
- **Возвращает**: URL API (prod или sandbox)

#### _get_api_key()
- **Назначение**: Получение API ключа
- **Возвращает**: API ключ пользователя

#### _make_request(method, endpoint, **kwargs)
- **Назначение**: Выполнение HTTP запроса к API
- **Параметры**: 
  - method - HTTP метод
  - endpoint - эндпоинт API
  - **kwargs - дополнительные параметры
- **Возвращает**: Ответ API или None

#### get_accounts()
- **Назначение**: Получение списка организаций
- **Возвращает**: Список организаций

#### get_vacancies(account_id, **params)
- **Назначение**: Получение вакансий организации
- **Параметры**: 
  - account_id - ID организации
  - **params - дополнительные параметры
- **Возвращает**: Список вакансий

#### get_vacancy(account_id, vacancy_id)
- **Назначение**: Получение конкретной вакансии
- **Параметры**: 
  - account_id - ID организации
  - vacancy_id - ID вакансии
- **Возвращает**: Данные вакансии

#### get_applicants(account_id, **params)
- **Назначение**: Получение кандидатов организации
- **Параметры**: 
  - account_id - ID организации
  - **params - дополнительные параметры
- **Возвращает**: Список кандидатов

#### get_applicant(account_id, applicant_id)
- **Назначение**: Получение конкретного кандидата
- **Параметры**: 
  - account_id - ID организации
  - applicant_id - ID кандидата
- **Возвращает**: Данные кандидата

#### update_applicant(account_id, applicant_id, data)
- **Назначение**: Обновление данных кандидата
- **Параметры**: 
  - account_id - ID организации
  - applicant_id - ID кандидата
  - data - данные для обновления
- **Возвращает**: Результат обновления

#### update_applicant_status(account_id, applicant_id, status_id, comment=None, vacancy_id=None)
- **Назначение**: Обновление статуса кандидата
- **Параметры**: 
  - account_id - ID организации
  - applicant_id - ID кандидата
  - status_id - ID статуса
  - comment - комментарий (опционально)
  - vacancy_id - ID вакансии (опционально)
- **Возвращает**: Результат обновления

#### test_connection()
- **Назначение**: Тестирование подключения к API
- **Возвращает**: True/False

## Эндпоинты

### Основные URL
```python
# apps/huntflow/urls.py
urlpatterns = [
    path('', views.huntflow_dashboard, name='dashboard'),
    path('<int:account_id>/vacancies/', views.vacancies_list, name='vacancies_list'),
    path('<int:account_id>/vacancies/<int:vacancy_id>/', views.vacancy_detail, name='vacancy_detail'),
    path('<int:account_id>/applicants/', views.applicants_list, name='applicants_list'),
    path('<int:account_id>/applicants/<int:applicant_id>/', views.applicant_detail, name='applicant_detail'),
    path('<int:account_id>/applicants/<int:applicant_id>/edit/', views.applicant_edit, name='applicant_edit'),
    path('test-connection/', views.test_connection_ajax, name='test_connection_ajax'),
    path('<int:account_id>/applicants/<int:applicant_id>/comment/', views.create_comment_ajax, name='create_comment_ajax'),
    path('<int:account_id>/vacancies-ajax/', views.get_vacancies_ajax, name='get_vacancies_ajax'),
    path('<int:account_id>/applicants-ajax/', views.get_applicants_ajax, name='get_applicants_ajax'),
]
```

### API эндпоинты

#### POST /huntflow/test-connection/
**Назначение**: Тестирование подключения к Huntflow API
**Ответ:**
```json
{
    "success": true,
    "message": "Подключение успешно"
}
```

#### POST /huntflow/{account_id}/applicants/{applicant_id}/comment/
**Назначение**: Создание комментария к кандидату
**Параметры:**
```json
{
    "comment": "Текст комментария",
    "vacancy_id": 123,
    "status_id": 456
}
```

#### GET /huntflow/{account_id}/vacancies-ajax/
**Назначение**: Получение вакансий через AJAX
**Ответ:**
```json
{
    "success": true,
    "vacancies": [...]
}
```

## Template Tags

### huntflow_filters.py
**Файл**: `templatetags/huntflow_filters.py`

**Фильтры:**
- `format_iso_date(iso_string)` - форматирование ISO даты
- `get_contrast_color(hex_color)` - получение контрастного цвета

**Template Tags:**
- `huntflow_breadcrumbs(context)` - хлебные крошки
- `huntflow_sidebar_menu(context)` - сайдбар меню

## Management Commands

### show_admin_data
**Файл**: `management/commands/show_admin_data.py`
**Назначение**: Показ всех данных, доступных в админке Django

### test_huntflow_logging
**Файл**: `management/commands/test_huntflow_logging.py`
**Назначение**: Тестирование Huntflow API и логирование запросов

### test_status_update
**Файл**: `management/commands/test_status_update.py`
**Назначение**: Тестирование обновления статуса кандидата

## Особенности подключения

### Настройка в settings.py
```python
INSTALLED_APPS = [
    'apps.huntflow',
]
```

### Миграции
```bash
python manage.py makemigrations huntflow
python manage.py migrate
```

### Настройка API
1. **Получение API ключа**: В Huntflow (prod или sandbox)
2. **Сохранение**: В профиле пользователя (apps.accounts)
3. **Выбор системы**: prod или sandbox
4. **Тестирование**: Через эндпоинт /huntflow/test-connection/

## Админка

### HuntflowCacheAdmin
**Особенности:**
- Отображение возраста кэша
- Статус кэша (активен/истек)
- Фильтрация по дате
- Поиск по ключу кэша

### HuntflowLogAdmin
**Особенности:**
- Отображение статуса запросов
- Фильтрация по типу операции, методу, статусу
- Поиск по эндпоинту, ошибкам
- Иерархия по дате
- Только чтение (логи не редактируются)

## Шаблоны

### dashboard.html
**Назначение**: Главная страница Huntflow
**Функциональность:**
- Список организаций
- Статистика по вакансиям и кандидатам
- Быстрые действия
- Тестирование подключения

### vacancies_list.html
**Назначение**: Список вакансий организации
**Функциональность:**
- Список вакансий с фильтрацией
- Поиск по вакансиям
- Сортировка
- Пагинация

### vacancy_detail.html
**Назначение**: Детали вакансии
**Функциональность:**
- Полная информация о вакансии
- Список кандидатов
- Статистика
- Действия с вакансией

### applicants_list.html
**Назначение**: Список кандидатов организации
**Функциональность:**
- Список кандидатов с фильтрацией
- Поиск по кандидатам
- Сортировка
- Пагинация

### applicant_detail.html
**Назначение**: Детали кандидата
**Функциональность:**
- Полная информация о кандидате
- История статусов
- Комментарии
- Действия с кандидатом

### applicant_edit.html
**Назначение**: Редактирование кандидата
**Функциональность:**
- Форма редактирования
- Валидация данных
- Сохранение изменений
- Отмена изменений

## JavaScript функциональность

### Тестирование подключения
```javascript
// Тест подключения к Huntflow API
function testConnection() {
    fetch('/huntflow/test-connection/', {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCSRFToken()
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showSuccess(data.message);
        } else {
            showError(data.error);
        }
    });
}
```

### Создание комментария
```javascript
// Создание комментария к кандидату
function createComment(applicantId, accountId) {
    const comment = document.getElementById('commentText').value;
    const vacancyId = document.getElementById('vacancyId').value;
    const statusId = document.getElementById('statusId').value;
    
    fetch(`/huntflow/${accountId}/applicants/${applicantId}/comment/`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCSRFToken()
        },
        body: JSON.stringify({
            comment: comment,
            vacancy_id: vacancyId,
            status_id: statusId
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showSuccess('Комментарий добавлен');
            location.reload();
        } else {
            showError(data.error);
        }
    });
}
```

### Обновление статуса
```javascript
// Обновление статуса кандидата
function updateStatus(applicantId, accountId, statusId) {
    const comment = document.getElementById('statusComment').value;
    
    fetch(`/huntflow/${accountId}/applicants/${applicantId}/status/`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCSRFToken()
        },
        body: JSON.stringify({
            status_id: statusId,
            comment: comment
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showSuccess('Статус обновлен');
            location.reload();
        } else {
            showError(data.error);
        }
    });
}
```

## Безопасность

### API ключи
- Хранятся в профиле пользователя
- Передаются через HTTPS
- Валидируются на сервере

### CSRF защита
- Все POST запросы защищены CSRF токенами
- Валидация на сервере

### Логирование
- Все операции логируются
- Запись ошибок и успешных операций
- Отслеживание пользователей

## Отладка

### Логирование
```python
# В services.py
print(f"API запрос: {method} {endpoint}")
print(f"Ответ API: {response.status_code}")
print(f"Ошибка: {error}")
```

### Тестирование
```bash
# Тест API
python manage.py shell
>>> from apps.huntflow.services import HuntflowService
>>> from apps.accounts.models import User
>>> user = User.objects.get(username='testuser')
>>> service = HuntflowService(user)
>>> accounts = service.get_accounts()
>>> print(f"Организации: {accounts}")
```

### Management команды
```bash
# Тест логирования
python manage.py test_huntflow_logging

# Тест обновления статуса
python manage.py test_status_update

# Показ данных админки
python manage.py show_admin_data
```

## Troubleshooting

### Проблемы с API
1. **Неверный ключ**: Проверьте API ключ в Huntflow
2. **Превышен лимит**: Проверьте квоты API
3. **Сетевые ошибки**: Проверьте интернет-соединение
4. **Неправильный URL**: Проверьте настройки prod/sandbox

### Проблемы с данными
1. **Пустые списки**: Проверьте права доступа к организациям
2. **Ошибки парсинга**: Проверьте формат данных от API
3. **Дублирование**: Проверьте логику кэширования
4. **Медленная загрузка**: Оптимизируйте запросы

### Проблемы с кэшем
1. **Устаревшие данные**: Очистите кэш
2. **Ошибки кэширования**: Проверьте настройки БД
3. **Превышение лимитов**: Настройте TTL кэша

## Производительность
- Кэширование API ответов
- Логирование для мониторинга
- Оптимизация запросов к БД
- Пагинация больших списков
- AJAX для динамических обновлений
