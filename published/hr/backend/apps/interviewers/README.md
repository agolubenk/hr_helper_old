# Interviewers App - Управление интервьюерами

## Описание
Приложение для управления интервьюерами и правилами их привлечения. Включает систему грейдов, лимиты интервью, автозаполнение календарей и интеграцию с Google Calendar.

## Зависимости
- Django 5.2.6+
- apps.finance (для грейдов)
- apps.google_oauth (для интеграции с календарями)
- apps.accounts (для пользователей)

## Requirements
```python
# В requirements.txt
Django>=5.2.6
google-auth>=2.0.0
google-auth-oauthlib>=1.0.0
google-api-python-client>=2.0.0
```

## Связи с другими приложениями
- **apps.finance**: Связь через `InterviewRule` (ForeignKey на Grade)
- **apps.google_oauth**: Интеграция для автозаполнения календарей
- **apps.vacancies**: Связь через ManyToManyField
- **apps.accounts**: Связь через пользователей

## Модели

### Interviewer
**Назначение**: Интервьюеры

**Поля:**
- `first_name` - имя (CharField, max_length=100)
- `last_name` - фамилия (CharField, max_length=100)
- `middle_name` - отчество (CharField, max_length=100, blank=True)
- `email` - email адрес (EmailField, unique=True)
- `calendar_link` - ссылка на календарь (URLField, blank=True)
- `is_active` - активен ли интервьюер (BooleanField, default=True)
- `created_at`, `updated_at` - временные метки

**Методы:**
- `get_full_name()` - получение полного имени
- `get_short_name()` - получение короткого имени
- `clean()` - валидация данных
- `save()` - сохранение с автозаполнением

### InterviewRule
**Назначение**: Правила привлечения интервьюеров

**Поля:**
- `name` - название правила (CharField, max_length=200)
- `description` - описание (TextField, blank=True)
- `daily_limit` - лимит в день (PositiveIntegerField, default=5, validators: 1-50)
- `weekly_limit` - лимит в неделю (PositiveIntegerField, default=20, validators: 1-200)
- `min_grade` - минимальный грейд (ForeignKey на Grade)
- `max_grade` - максимальный грейд (ForeignKey на Grade)
- `is_active` - активно ли правило (BooleanField, default=True)
- `created_at`, `updated_at` - временные метки

**Методы:**
- `get_grade_range()` - получение диапазона грейдов
- `is_grade_in_range(grade)` - проверка грейда в диапазоне
- `save()` - сохранение с валидацией
- `get_active_rule()` - получение активного правила
- `activate_rule(rule_id)` - активация правила

## Логика работы

### Управление интервьюерами
1. **Создание**: Добавление нового интервьюера
2. **Редактирование**: Обновление данных интервьюера
3. **Активация/деактивация**: Управление статусом
4. **Удаление**: Удаление интервьюера

### Правила привлечения
1. **Создание правил**: Настройка лимитов и грейдов
2. **Активация**: Выбор активного правила
3. **Валидация**: Проверка корректности данных
4. **Применение**: Использование правил для привлечения

### Автозаполнение календарей
1. **Интеграция**: Подключение к Google Calendar API
2. **Поиск календарей**: Поиск календарей по email
3. **Автозаполнение**: Автоматическое заполнение ссылок
4. **Валидация**: Проверка доступности календарей

## Сервисы

### InterviewerCalendarService
**Файл**: `services.py`

**Методы:**

#### __init__(user)
- **Назначение**: Инициализация сервиса для пользователя
- **Параметры**: user - объект пользователя

#### _get_calendar_service()
- **Назначение**: Получение сервиса Google Calendar
- **Возвращает**: googleapiclient.discovery.Resource

#### get_calendar_link_for_interviewer(interviewer_email)
- **Назначение**: Получение ссылки на календарь интервьюера
- **Параметры**: interviewer_email - email интервьюера
- **Возвращает**: Ссылка на календарь или None

#### auto_fill_calendar_links()
- **Назначение**: Автозаполнение ссылок на календари
- **Возвращает**: Количество обновленных интервьюеров

#### get_available_calendars()
- **Назначение**: Получение доступных календарей
- **Возвращает**: Список календарей

#### suggest_calendar_for_interviewer(interviewer_email)
- **Назначение**: Предложение календаря для интервьюера
- **Параметры**: interviewer_email - email интервьюера
- **Возвращает**: Предложенный календарь или None

## Эндпоинты

### Основные URL
```python
# apps/interviewers/urls.py
urlpatterns = [
    path('', views.interviewer_dashboard, name='dashboard'),
    path('list/', views.interviewer_list, name='list'),
    path('<int:pk>/', views.interviewer_detail, name='detail'),
    path('create/', views.interviewer_create, name='create'),
    path('<int:pk>/edit/', views.interviewer_edit, name='edit'),
    path('<int:pk>/delete/', views.interviewer_delete, name='delete'),
    path('<int:pk>/toggle-active/', views.interviewer_toggle_active, name='toggle_active'),
    path('rules/', views.rule_list, name='rule_list'),
    path('rules/<int:pk>/', views.rule_detail, name='rule_detail'),
    path('rules/create/', views.rule_create, name='rule_create'),
    path('rules/<int:pk>/edit/', views.rule_edit, name='rule_edit'),
    path('rules/<int:pk>/delete/', views.rule_delete, name='rule_delete'),
    path('rules/<int:pk>/toggle-active/', views.rule_toggle_active, name='rule_toggle_active'),
    path('auto-fill-calendar/', views.auto_fill_calendar, name='auto_fill_calendar'),
    path('auto-fill-all-calendars/', views.auto_fill_all_calendars, name='auto_fill_all_calendars'),
]
```

### API эндпоинты

#### POST /interviewers/auto-fill-calendar/
**Назначение**: Автозаполнение календаря для конкретного интервьюера
**Параметры:**
```json
{
    "interviewer_id": 1
}
```

#### POST /interviewers/auto-fill-all-calendars/
**Назначение**: Автозаполнение календарей для всех интервьюеров
**Ответ:**
```json
{
    "success": true,
    "message": "Обновлено 5 интервьюеров",
    "updated_count": 5
}
```

## Формы

### InterviewerForm
**Назначение**: Форма для создания/редактирования интервьюера
**Поля:**
- `first_name` - имя
- `last_name` - фамилия
- `middle_name` - отчество
- `email` - email адрес
- `calendar_link` - ссылка на календарь
- `is_active` - активен ли интервьюер

### InterviewerSearchForm
**Назначение**: Форма поиска интервьюеров
**Поля:**
- `search` - поиск по имени, фамилии или email
- `is_active` - фильтр по активности

### InterviewRuleForm
**Назначение**: Форма для создания/редактирования правил
**Поля:**
- `name` - название правила
- `description` - описание
- `daily_limit` - лимит в день
- `weekly_limit` - лимит в неделю
- `min_grade` - минимальный грейд
- `max_grade` - максимальный грейд
- `is_active` - активно ли правило

### InterviewRuleSearchForm
**Назначение**: Форма поиска правил
**Поля:**
- `search` - поиск по названию или описанию
- `is_active` - фильтр по активности
- `min_grade` - фильтр по минимальному грейду

## Особенности подключения

### Настройка в settings.py
```python
INSTALLED_APPS = [
    'apps.interviewers',
]
```

### Миграции
```bash
python manage.py makemigrations interviewers
python manage.py migrate
```

### Настройка Google Calendar
1. **OAuth настройка**: В apps.google_oauth
2. **API ключи**: В профиле пользователя
3. **Scopes**: calendar.readonly для чтения календарей

## Админка

### InterviewerAdmin
**Особенности:**
- Отображение полного имени
- Фильтрация по активности и дате
- Поиск по имени, фамилии, email
- Редактирование активности в списке
- Группировка полей по категориям

### InterviewRuleAdmin
**Особенности:**
- Отображение диапазона грейдов
- Фильтрация по активности и грейдам
- Поиск по названию и описанию
- Действие "Деактивировать все правила"
- Группировка полей по категориям

## Шаблоны

### interviewer_dashboard.html
**Назначение**: Главная страница интервьюеров
**Функциональность:**
- Статистика по интервьюерам
- Активные правила
- Быстрые действия
- Автозаполнение календарей

### interviewer_list.html
**Назначение**: Список интервьюеров
**Функциональность:**
- Список интервьюеров с фильтрацией
- Поиск по интервьюерам
- Сортировка
- Пагинация
- Действия с интервьюерами

### interviewer_detail.html
**Назначение**: Детали интервьюера
**Функциональность:**
- Полная информация об интервьюере
- Ссылка на календарь
- Статистика
- Действия с интервьюером

### interviewer_form.html
**Назначение**: Форма создания/редактирования интервьюера
**Функциональность:**
- Форма с валидацией
- Автозаполнение полей
- Сохранение изменений
- Отмена изменений

### rule_list.html
**Назначение**: Список правил привлечения
**Функциональность:**
- Список правил с фильтрацией
- Поиск по правилам
- Сортировка
- Пагинация
- Действия с правилами

### rule_detail.html
**Назначение**: Детали правила
**Функциональность:**
- Полная информация о правиле
- Диапазон грейдов
- Лимиты
- Действия с правилом

### rule_form.html
**Назначение**: Форма создания/редактирования правила
**Функциональность:**
- Форма с валидацией
- Выбор грейдов
- Настройка лимитов
- Сохранение изменений

## Template Tags

### interviewer_filters.py
**Файл**: `templatetags/interviewer_filters.py`

**Фильтры:**
- `get_initials(first_name, last_name)` - получение инициалов
- `get_avatar_color(name)` - получение цвета аватара
- `get_avatar_bg_color(name)` - получение фонового цвета аватара

## JavaScript функциональность

### Автозаполнение календарей
```javascript
// Автозаполнение календаря для конкретного интервьюера
function autoFillCalendar(interviewerId) {
    fetch('/interviewers/auto-fill-calendar/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCSRFToken()
        },
        body: JSON.stringify({
            interviewer_id: interviewerId
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showSuccess(data.message);
            location.reload();
        } else {
            showError(data.error);
        }
    });
}
```

### Автозаполнение всех календарей
```javascript
// Автозаполнение календарей для всех интервьюеров
function autoFillAllCalendars() {
    if (confirm('Автозаполнить календари для всех интервьюеров?')) {
        fetch('/interviewers/auto-fill-all-calendars/', {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCSRFToken()
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showSuccess(data.message);
                location.reload();
            } else {
                showError(data.error);
            }
        });
    }
}
```

### Переключение активности
```javascript
// Переключение активности интервьюера
function toggleActive(interviewerId) {
    fetch(`/interviewers/${interviewerId}/toggle-active/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCSRFToken()
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showSuccess(data.message);
            location.reload();
        } else {
            showError(data.error);
        }
    });
}
```

## Безопасность

### Валидация данных
- Проверка email адресов
- Валидация URL календарей
- Проверка лимитов (1-50 для дневных, 1-200 для недельных)
- Уникальность email адресов

### CSRF защита
- Все POST запросы защищены CSRF токенами
- Валидация на сервере

### Права доступа
- Проверка авторизации пользователя
- Ограничение доступа к функциям

## Отладка

### Логирование
```python
# В services.py
print(f"Автозаполнение календаря: {interviewer_email}")
print(f"Найдено календарей: {len(calendars)}")
print(f"Ошибка API: {error}")
```

### Тестирование
```bash
# Тест автозаполнения
python manage.py shell
>>> from apps.interviewers.services import InterviewerCalendarService
>>> from apps.accounts.models import User
>>> user = User.objects.get(username='testuser')
>>> service = InterviewerCalendarService(user)
>>> updated_count = service.auto_fill_calendar_links()
>>> print(f"Обновлено: {updated_count} интервьюеров")
```

## Troubleshooting

### Проблемы с Google Calendar
1. **Нет доступа к календарям**: Проверьте OAuth настройки
2. **Ошибки API**: Проверьте API ключи и scopes
3. **Медленные запросы**: Оптимизируйте количество запросов
4. **Неправильные ссылки**: Проверьте формат URL календарей

### Проблемы с правилами
1. **Неправильные лимиты**: Проверьте валидацию (1-50, 1-200)
2. **Отсутствие грейдов**: Проверьте миграции apps.finance
3. **Дублирование правил**: Проверьте уникальность
4. **Неактивные правила**: Проверьте флаг is_active

### Проблемы с интервьюерами
1. **Дублирование email**: Проверьте уникальность в модели
2. **Неправильные данные**: Проверьте валидацию форм
3. **Отсутствие календарей**: Проверьте автозаполнение
4. **Медленная загрузка**: Оптимизируйте запросы к БД

## Производительность
- Кэширование данных календарей
- Оптимизация запросов к Google API
- Пагинация больших списков
- AJAX для динамических обновлений
- Индексы в БД для быстрого поиска
