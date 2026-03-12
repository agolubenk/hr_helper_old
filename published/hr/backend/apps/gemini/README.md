# Gemini App - Интеграция с Google Gemini AI

## Описание
Приложение для интеграции с Google Gemini AI API. Предоставляет чат-интерфейс для взаимодействия с AI моделью, управление сессиями чата и настройки API.

## Зависимости
- Django 5.2.6+
- requests (для API запросов)
- apps.accounts (для API ключей пользователей)

## Requirements
```python
# В requirements.txt
Django>=5.2.6
requests>=2.31.0
```

## Связи с другими приложениями
- **apps.accounts**: Получает API ключ Gemini из профиля пользователя
- **apps.common**: Используется в сайдбаре для навигации

## Модели

### ChatSession
**Назначение**: Сессии чата с Gemini AI

**Поля:**
- `user` - пользователь (ForeignKey на User)
- `title` - название сессии (CharField, max_length=200)
- `created_at` - время создания (DateTimeField, auto_now_add=True)
- `updated_at` - время обновления (DateTimeField, auto_now=True)
- `is_active` - активна ли сессия (BooleanField, default=True)

**Свойства:**
- `message_count` - количество сообщений в сессии

### ChatMessage
**Назначение**: Сообщения в чате

**Поля:**
- `session` - сессия чата (ForeignKey на ChatSession)
- `role` - роль отправителя (CharField, choices: user, assistant, system)
- `content` - содержание сообщения (TextField)
- `timestamp` - время отправки (DateTimeField, auto_now_add=True)
- `tokens_used` - использовано токенов (IntegerField, null=True)
- `response_time` - время ответа в секундах (FloatField, null=True)

## Логика работы

### Инициализация сессии
1. **Создание сессии**: При первом обращении к чату
2. **Загрузка истории**: Восстановление предыдущих сообщений
3. **Активация**: Установка флага is_active=True

### Обработка сообщений
1. **Получение сообщения**: От пользователя через AJAX
2. **Валидация**: Проверка API ключа и содержимого
3. **Отправка в Gemini**: HTTP запрос к API
4. **Сохранение**: Сохранение сообщения и ответа в БД
5. **Возврат ответа**: JSON ответ клиенту

### Управление токенами
1. **Подсчет токенов**: Отслеживание использования
2. **Лимиты**: Контроль расходования токенов
3. **Статистика**: Отображение в админке

## Сервисы

### GeminiService
**Файл**: `services.py`

**Конфигурация:**
- `BASE_URL`: "https://generativelanguage.googleapis.com/v1beta"
- `MODEL`: "gemini-2.0-flash"

**Методы:**

#### __init__(api_key)
- **Назначение**: Инициализация сервиса с API ключом
- **Параметры**: api_key - ключ Gemini API

#### generate_content(prompt, history=None)
- **Назначение**: Генерация контента через Gemini API
- **Параметры**: 
  - prompt - текст запроса
  - history - история сообщений (опционально)
- **Возвращает**: (success, content, metadata)

#### test_connection()
- **Назначение**: Тестирование подключения к API
- **Возвращает**: (success, message)

#### get_available_models()
- **Назначение**: Получение доступных моделей
- **Возвращает**: (success, models, error)

## Эндпоинты

### Основные URL
```python
# apps/gemini/urls.py
urlpatterns = [
    path('', views.gemini_dashboard, name='dashboard'),
    path('chat/<int:session_id>/', views.chat_session, name='chat_session'),
    path('chat/', views.chat_session, name='chat_session_new'),
    path('settings/', views.settings, name='settings'),
    path('send-message/', views.send_message, name='send_message'),
    path('delete-session/<int:session_id>/', views.delete_session, name='delete_session'),
    path('test-api/', views.test_api_key, name='test_api_key'),
]
```

### API эндпоинты

#### POST /gemini/send-message/
**Назначение**: Отправка сообщения в чат
**Параметры:**
```json
{
    "session_id": 1,
    "message": "Привет, как дела?",
    "api_key": "your-gemini-api-key"
}
```

**Ответ:**
```json
{
    "success": true,
    "response": "Привет! У меня все хорошо, спасибо!",
    "tokens_used": 25,
    "response_time": 1.2
}
```

#### POST /gemini/test-api/
**Назначение**: Тестирование API ключа
**Параметры:**
```json
{
    "api_key": "your-gemini-api-key"
}
```

## Особенности подключения

### Настройка в settings.py
```python
INSTALLED_APPS = [
    'apps.gemini',
]
```

### Миграции
```bash
python manage.py makemigrations gemini
python manage.py migrate
```

### Настройка API ключа
1. **Получение ключа**: В Google AI Studio
2. **Сохранение**: В профиле пользователя (apps.accounts)
3. **Тестирование**: Через эндпоинт /gemini/test-api/

## Админка

### ChatSessionAdmin
**Особенности:**
- Отображение количества сообщений
- Фильтрация по активности и дате
- Поиск по названию и пользователю
- Только чтение для системных полей

### ChatMessageAdmin
**Особенности:**
- Предварительный просмотр контента
- Фильтрация по роли и времени
- Поиск по содержимому
- Отображение статистики токенов

## Шаблоны

### dashboard.html
**Назначение**: Главная страница Gemini AI
**Функциональность:**
- Список активных сессий
- Создание новой сессии
- Настройки API
- Статистика использования

### chat.html
**Назначение**: Интерфейс чата
**Функциональность:**
- Отображение истории сообщений
- Поле ввода сообщения
- Отправка через AJAX
- Управление сессией

### settings.html
**Назначение**: Настройки API
**Функциональность:**
- Тестирование API ключа
- Настройка параметров
- Статистика использования

## JavaScript функциональность

### Отправка сообщений
```javascript
// Отправка сообщения через AJAX
function sendMessage() {
    const message = document.getElementById('messageInput').value;
    const sessionId = getCurrentSessionId();
    
    fetch('/gemini/send-message/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCSRFToken()
        },
        body: JSON.stringify({
            session_id: sessionId,
            message: message,
            api_key: getApiKey()
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            displayMessage(data.response, 'assistant');
        } else {
            showError(data.error);
        }
    });
}
```

### Управление сессиями
```javascript
// Создание новой сессии
function createNewSession() {
    fetch('/gemini/chat/', {
        method: 'GET'
    })
    .then(response => response.text())
    .then(html => {
        document.body.innerHTML = html;
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

### Ограничения
- Лимиты на количество запросов
- Контроль размера сообщений
- Валидация входных данных

## Отладка

### Логирование
```python
# В services.py
print(f"API запрос: {endpoint}")
print(f"Ответ API: {response.status_code}")
print(f"Ошибка: {error}")
```

### Тестирование
```bash
# Тест API ключа
python manage.py shell
>>> from apps.gemini.logic.services import GeminiService
>>> service = GeminiService("your-api-key")
>>> success, message = service.test_connection()
>>> print(f"Подключение: {success}, Сообщение: {message}")
```

## Troubleshooting

### Проблемы с API
1. **Неверный ключ**: Проверьте API ключ в Google AI Studio
2. **Превышен лимит**: Проверьте квоты в Google Cloud Console
3. **Сетевые ошибки**: Проверьте интернет-соединение

### Проблемы с чатом
1. **Сообщения не отправляются**: Проверьте JavaScript консоль
2. **Сессии не сохраняются**: Проверьте миграции БД
3. **Медленные ответы**: Проверьте производительность API

### Проблемы с токенами
1. **Неправильный подсчет**: Проверьте логику в GeminiService
2. **Превышение лимитов**: Настройте ограничения
3. **Статистика не обновляется**: Проверьте сохранение в БД

## Производительность
- Кэширование API ответов
- Асинхронная отправка сообщений
- Оптимизация запросов к БД
- Лимиты на размер сообщений
