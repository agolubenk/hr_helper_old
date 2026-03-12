# Google OAuth App - OAuth авторизация и управление Google сервисами

## Описание
Приложение для OAuth авторизации с Google и управления Google сервисами: Calendar, Drive, Sheets. Предоставляет полный цикл авторизации, синхронизацию данных и управление токенами.

## Зависимости
- Django 5.2.6+
- google-auth>=2.0.0
- google-auth-oauthlib>=1.0.0
- google-api-python-client>=2.0.0
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
- **apps.accounts**: Связь через OneToOneField на User
- **apps.google_oauth**: Использует OAuth аккаунты для автоматизации
- **apps.common**: Используется в сайдбаре для навигации

## Модели

### GoogleOAuthAccount
**Назначение**: OAuth аккаунты Google

**Поля:**
- `user` - пользователь (OneToOneField на User)
- `google_id` - Google ID (CharField, max_length=100, unique=True)
- `email` - email адрес (EmailField)
- `name` - имя (CharField, max_length=200)
- `picture_url` - URL фото (URLField, blank=True, null=True)
- `access_token` - токен доступа (TextField)
- `refresh_token` - токен обновления (TextField, blank=True, null=True)
- `token_expires_at` - время истечения токена (DateTimeField)
- `scopes` - разрешения (JSONField, default=list)
- `created_at`, `updated_at` - временные метки
- `last_sync_at` - время последней синхронизации

**Методы:**
- `is_token_valid()` - проверка валидности токена
- `needs_refresh()` - нуждается ли токен в обновлении
- `has_scope(scope)` - проверка наличия разрешения
- `get_available_services()` - получение доступных сервисов

### GoogleCalendarEvent
**Назначение**: События Google Calendar

**Поля:**
- `google_account` - OAuth аккаунт (ForeignKey)
- `event_id` - ID события (CharField, max_length=200)
- `title` - название (CharField, max_length=500)
- `description` - описание (TextField)
- `start_time`, `end_time` - время начала/окончания (DateTimeField)
- `all_day` - весь день (BooleanField, default=False)
- `location` - местоположение (CharField, max_length=500)
- `status` - статус (CharField, max_length=50, default='confirmed')
- `attendees` - участники (JSONField, default=list)
- `meet_link` - ссылка на Google Meet (URLField)
- `creator_email`, `creator_name` - создатель события
- `created_at`, `updated_at` - временные метки
- `google_created_at`, `google_updated_at` - временные метки Google

**Уникальность**: `['google_account', 'event_id']`

### GoogleDriveFile
**Назначение**: Файлы Google Drive

**Поля:**
- `google_account` - OAuth аккаунт (ForeignKey)
- `file_id` - ID файла (CharField, max_length=200)
- `name` - название (CharField, max_length=500)
- `mime_type` - MIME тип (CharField, max_length=200)
- `size` - размер в байтах (BigIntegerField, blank=True, null=True)
- `created_time`, `modified_time` - временные метки Google
- `web_view_link`, `web_content_link` - ссылки для доступа
- `parents` - родительские папки (JSONField, default=list)
- `synced_at` - время синхронизации

**Уникальность**: `['google_account', 'file_id']`

### GoogleSheet
**Назначение**: Google Sheets

**Поля:**
- `google_account` - OAuth аккаунт (ForeignKey)
- `spreadsheet_id` - ID таблицы (CharField, max_length=200)
- `title` - название (CharField, max_length=500)
- `created_time`, `modified_time` - временные метки Google
- `web_view_link` - ссылка для просмотра
- `synced_at` - время синхронизации

**Уникальность**: `['google_account', 'spreadsheet_id']`

## Логика работы

### OAuth авторизация
1. **Инициация**: Создание OAuth flow с необходимыми scopes
2. **Перенаправление**: Переход на Google OAuth страницу
3. **Callback**: Обработка ответа от Google
4. **Сохранение**: Создание/обновление GoogleOAuthAccount
5. **Валидация**: Проверка токенов и разрешений

### Управление токенами
1. **Проверка валидности**: Проверка времени истечения
2. **Обновление**: Автоматическое обновление access_token
3. **Хранение**: Безопасное хранение в БД
4. **Отзыв**: Возможность отзыва доступа

### Синхронизация данных
1. **Calendar**: Синхронизация событий календаря
2. **Drive**: Синхронизация файлов и папок
3. **Sheets**: Синхронизация таблиц
4. **Обновление**: Инкрементальное обновление данных

## Сервисы

### GoogleOAuthService
**Файл**: `services.py`

**Scopes:**
```python
SCOPES = [
    'https://www.googleapis.com/auth/userinfo.email',
    'https://www.googleapis.com/auth/userinfo.profile',
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/spreadsheets',
]
```

**Методы:**

#### __init__(user)
- **Назначение**: Инициализация сервиса для пользователя
- **Параметры**: user - объект пользователя

#### get_oauth_account()
- **Назначение**: Получение OAuth аккаунта
- **Возвращает**: GoogleOAuthAccount или None

#### create_oauth_flow()
- **Назначение**: Создание OAuth flow
- **Возвращает**: google_auth_oauthlib.flow.Flow

#### get_authorization_url()
- **Назначение**: Получение URL для авторизации
- **Возвращает**: URL для перенаправления

#### handle_callback(authorization_response, state)
- **Назначение**: Обработка callback от Google
- **Параметры**: 
  - authorization_response - ответ от Google
  - state - состояние для безопасности
- **Возвращает**: GoogleOAuthAccount

#### get_credentials()
- **Назначение**: Получение валидных credentials
- **Возвращает**: google.oauth2.credentials.Credentials

#### _refresh_token(oauth_account)
- **Назначение**: Обновление токена доступа
- **Параметры**: oauth_account - OAuth аккаунт
- **Возвращает**: Обновленные credentials

#### revoke_access()
- **Назначение**: Отзыв доступа к Google сервисам
- **Возвращает**: Результат отзыва

### GoogleCalendarService
**Методы:**

#### __init__(oauth_service)
- **Назначение**: Инициализация сервиса календаря
- **Параметры**: oauth_service - OAuth сервис

#### get_calendars()
- **Назначение**: Получение списка календарей
- **Возвращает**: Список календарей

#### get_events(calendar_id='primary', max_results=100, days_ahead=100)
- **Назначение**: Получение событий календаря
- **Параметры**: 
  - calendar_id - ID календаря
  - max_results - максимум событий
  - days_ahead - количество дней вперед
- **Возвращает**: Список событий

#### sync_events(oauth_account, days_ahead=100)
- **Назначение**: Синхронизация событий
- **Параметры**: 
  - oauth_account - OAuth аккаунт
  - days_ahead - количество дней вперед
- **Возвращает**: Количество синхронизированных событий

### GoogleDriveService
**Методы:**

#### get_files(max_results=100)
- **Назначение**: Получение файлов Drive
- **Параметры**: max_results - максимум файлов
- **Возвращает**: Список файлов

#### sync_files(oauth_account)
- **Назначение**: Синхронизация файлов
- **Параметры**: oauth_account - OAuth аккаунт
- **Возвращает**: Количество синхронизированных файлов

### GoogleSheetsService
**Методы:**

#### get_spreadsheets(max_results=100)
- **Назначение**: Получение таблиц
- **Параметры**: max_results - максимум таблиц
- **Возвращает**: Список таблиц

#### sync_spreadsheets(oauth_account)
- **Назначение**: Синхронизация таблиц
- **Параметры**: oauth_account - OAuth аккаунт
- **Возвращает**: Количество синхронизированных таблиц

## Эндпоинты

### Основные URL
```python
# apps/google_oauth/urls.py
urlpatterns = [
    path('', views.dashboard_redirect, name='dashboard_redirect'),
    path('start/', views.google_oauth_start, name='oauth_start'),
    path('callback/', views.google_oauth_callback, name='oauth_callback'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('disconnect/', views.disconnect, name='disconnect'),
    path('calendar/', views.calendar_view, name='calendar'),
    path('drive/', views.drive_view, name='drive'),
    path('sheets/', views.sheets_view, name='sheets'),
    path('sync/calendar/', views.sync_calendar, name='sync_calendar'),
    path('sync/drive/', views.sync_drive, name='sync_drive'),
    path('sync/sheets/', views.sync_sheets, name='sync_sheets'),
    path('sync/all/', views.sync_all, name='sync_all'),
]
```

### API эндпоинты

#### POST /google-oauth/sync/calendar/
**Назначение**: Синхронизация календаря
**Ответ:**
```json
{
    "success": true,
    "message": "Синхронизировано 15 событий",
    "events_count": 15
}
```

#### POST /google-oauth/sync/drive/
**Назначение**: Синхронизация Drive
**Ответ:**
```json
{
    "success": true,
    "message": "Синхронизировано 25 файлов",
    "files_count": 25
}
```

#### POST /google-oauth/sync/all/
**Назначение**: Синхронизация всех сервисов
**Ответ:**
```json
{
    "success": true,
    "message": "Синхронизация завершена",
    "calendar_events": 15,
    "drive_files": 25,
    "sheets": 5
}
```

## Template Tags

### calendar_filters.py
**Файл**: `templatetags/calendar_filters.py`

**Фильтры:**
- `lookup(dictionary, key)` - поиск в словаре
- `format_date(year, month, day)` - форматирование даты
- `create_date(year, month, day)` - создание даты

## Особенности подключения

### Настройка в settings.py
```python
INSTALLED_APPS = [
    'apps.google_oauth',
]

# Google OAuth настройки
GOOGLE_OAUTH2_CLIENT_ID = 'your-client-id'
GOOGLE_OAUTH2_CLIENT_SECRET = 'your-client-secret'
GOOGLE_OAUTH2_REDIRECT_URI = 'http://localhost:8000/google-oauth/callback/'
```

### Миграции
```bash
python manage.py makemigrations google_oauth
python manage.py migrate
```

### Настройка OAuth
1. **Создание проекта**: В Google Cloud Console
2. **Включение API**: Calendar API, Drive API, Sheets API
3. **Создание credentials**: OAuth 2.0 Client ID
4. **Настройка redirect URIs**: Добавить callback URL
5. **Настройка scopes**: Добавить необходимые разрешения

## Админка

### GoogleOAuthAccountAdmin
**Особенности:**
- Отображение статуса токена
- Фильтрация по дате создания
- Поиск по имени, email
- Только чтение для системных полей

### GoogleCalendarEventAdmin
**Особенности:**
- Отображение времени событий
- Фильтрация по статусу, дате
- Поиск по названию, описанию
- Группировка полей

### GoogleDriveFileAdmin
**Особенности:**
- Отображение размера файла
- Фильтрация по типу MIME
- Поиск по названию файла
- Отображение ссылок

### GoogleSheetAdmin
**Особенности:**
- Отображение времени изменения
- Фильтрация по дате
- Поиск по названию
- Отображение ссылок

## Шаблоны

### dashboard.html
**Назначение**: Главная страница OAuth
**Функциональность:**
- Статус подключения к Google
- Статистика синхронизированных данных
- Быстрые действия (синхронизация)
- Ссылки на сервисы

### calendar.html
**Назначение**: Просмотр событий календаря
**Функциональность:**
- Календарный вид событий
- Модальные окна с деталями
- Отображение участников
- Ссылки на Google Meet

### drive.html
**Назначение**: Просмотр файлов Drive
**Функциональность:**
- Список файлов с фильтрацией
- Предварительный просмотр
- Скачивание файлов
- Поиск по файлам

### sheets.html
**Назначение**: Просмотр Google Sheets
**Функциональность:**
- Список таблиц
- Ссылки на таблицы
- Время последнего изменения
- Поиск по таблицам

## JavaScript функциональность

### Синхронизация
```javascript
// Синхронизация всех сервисов
function syncAll() {
    fetch('/google-oauth/sync/all/', {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCSRFToken()
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showSuccess(data.message);
            updateStatistics(data);
        } else {
            showError(data.error);
        }
    });
}
```

### Календарь
```javascript
// Открытие модального окна события
function openEventModal(eventData) {
    const modal = document.getElementById('eventModal');
    const title = document.getElementById('eventTitle');
    const details = document.getElementById('eventDetails');
    
    title.textContent = eventData.title;
    details.innerHTML = formatEventDetails(eventData);
    
    modal.style.display = 'block';
}
```

## Безопасность

### OAuth токены
- Хранятся в зашифрованном виде
- Автоматическое обновление при истечении
- Отзыв доступа при отключении
- Проверка валидности на каждом запросе

### State параметр
- Генерация случайного state для безопасности
- Проверка state в callback
- Защита от CSRF атак

### Валидация данных
- Проверка входных параметров
- Санитизация данных от Google API
- Защита от XSS и CSRF

## Отладка

### Логирование
```python
# В services.py
print(f"OAuth callback: {authorization_response}")
print(f"Синхронизация: {events_count} событий")
print(f"Ошибка API: {error}")
```

### Тестирование
```bash
# Тест OAuth
python manage.py shell
>>> from apps.google_oauth.services import GoogleOAuthService
>>> from apps.accounts.models import User
>>> user = User.objects.get(username='testuser')
>>> service = GoogleOAuthService(user)
>>> url = service.get_authorization_url()
>>> print(f"OAuth URL: {url}")
```

## Troubleshooting

### Проблемы с OAuth
1. **Неверные credentials**: Проверьте настройки в Google Cloud Console
2. **Истекшие токены**: Проверьте автоматическое обновление
3. **Недостаточно прав**: Проверьте scopes в OAuth
4. **Ошибка redirect URI**: Проверьте настройки callback URL

### Проблемы с синхронизацией
1. **API лимиты**: Проверьте квоты в Google Cloud Console
2. **Медленная синхронизация**: Оптимизируйте количество запросов
3. **Дублирование данных**: Проверьте уникальность в моделях
4. **Ошибки парсинга**: Проверьте формат данных от API

### Проблемы с токенами
1. **Токены не обновляются**: Проверьте refresh_token
2. **Ошибки авторизации**: Проверьте scopes и права
3. **Истекшие токены**: Проверьте время истечения
4. **Неверные токены**: Проверьте сохранение в БД

## Производительность
- Кэширование API ответов
- Пакетная обработка данных
- Асинхронная синхронизация
- Оптимизация запросов к БД
- Лимиты на количество синхронизируемых элементов
- Инкрементальное обновление данных
