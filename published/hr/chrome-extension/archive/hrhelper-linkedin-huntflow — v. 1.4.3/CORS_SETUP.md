# 🔒 Настройка CORS для Chrome расширения

## 📋 Обзор

Chrome расширения используют специальный origin формат: `chrome-extension://EXTENSION_ID`

Для работы расширения нужно добавить этот origin в список разрешенных CORS источников.

## ⚙️ Настройка в Django

### Шаг 1: Получите Extension ID

После установки расширения:

1. Откройте `chrome://extensions/`
2. Найдите "HRHelper LinkedIn → Huntflow"
3. Скопируйте ID (например: `abcdefghijklmnopqrstuvwxyz123456`)

### Шаг 2: Обновите settings_production.py

Добавьте Extension ID в настройки CORS:

```python
# config/settings_production.py

# Extension ID для Chrome расширения LinkedIn → Huntflow
# Получите ID после установки расширения из chrome://extensions/
CHROME_EXTENSION_ID = os.environ.get('CHROME_EXTENSION_ID', 'your-extension-id-here')

# CORS настройки
CORS_ALLOWED_ORIGINS = [
    # Chrome расширение
    f"chrome-extension://{CHROME_EXTENSION_ID}",
    
    # Ваш фронтенд (если есть)
    "https://your-frontend-domain.com",
    
    # Другие разрешенные источники
    # ...
]

# Или разрешить все расширения (менее безопасно, но проще):
# CORS_ALLOWED_ORIGINS = [
#     "chrome-extension://*",  # Все Chrome расширения
#     "https://your-frontend-domain.com",
# ]

CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
]
```

### Шаг 3: Использование переменной окружения (рекомендуется)

В `.env` файле:

```bash
# Chrome Extension ID для LinkedIn → Huntflow интеграции
CHROME_EXTENSION_ID=abcdefghijklmnopqrstuvwxyz123456
```

В `settings_production.py`:

```python
CHROME_EXTENSION_ID = os.environ.get('CHROME_EXTENSION_ID', '')

if CHROME_EXTENSION_ID:
    CORS_ALLOWED_ORIGINS.append(f"chrome-extension://{CHROME_EXTENSION_ID}")
```

## 🔍 Проверка CORS

### Тест 1: Проверка в браузере

1. Откройте LinkedIn профиль
2. Откройте консоль браузера (F12)
3. Перейдите в Network tab
4. Проверьте запросы к вашему API
5. Убедитесь, что нет CORS ошибок

### Тест 2: Проверка заголовков

Запрос от расширения должен содержать:

```
Origin: chrome-extension://your-extension-id
```

Ответ должен содержать:

```
Access-Control-Allow-Origin: chrome-extension://your-extension-id
Access-Control-Allow-Credentials: true
```

## ⚠️ Важные замечания

### Безопасность

1. **Не используйте `chrome-extension://*`** в продакшене без необходимости
   - Это разрешит доступ всем расширениям
   - Используйте конкретный Extension ID

2. **Храните Extension ID в переменных окружения**
   - Не коммитьте в репозиторий
   - Используйте `.env` файл

3. **Проверяйте API токены**
   - Расширение использует Token аутентификацию
   - Убедитесь, что токены валидируются на сервере

### Разные окружения

Для разных окружений (dev, staging, production) используйте разные Extension ID:

```python
# config/settings_production.py
if os.environ.get('ENVIRONMENT') == 'production':
    CHROME_EXTENSION_ID = os.environ.get('CHROME_EXTENSION_ID_PROD')
elif os.environ.get('ENVIRONMENT') == 'staging':
    CHROME_EXTENSION_ID = os.environ.get('CHROME_EXTENSION_ID_STAGING')
else:
    CHROME_EXTENSION_ID = os.environ.get('CHROME_EXTENSION_ID_DEV', 'dev-extension-id')
```

## 🐛 Устранение проблем

### Ошибка: "Access to fetch has been blocked by CORS policy"

**Причина:** Extension ID не добавлен в CORS_ALLOWED_ORIGINS

**Решение:**
1. Проверьте Extension ID в `chrome://extensions/`
2. Убедитесь, что он добавлен в `CORS_ALLOWED_ORIGINS`
3. Перезапустите Django сервер

### Ошибка: "Credentials flag is true, but Access-Control-Allow-Credentials is not"

**Причина:** `CORS_ALLOW_CREDENTIALS` не установлен в `True`

**Решение:**
```python
CORS_ALLOW_CREDENTIALS = True
```

### Ошибка: "Preflight request doesn't pass"

**Причина:** Недостаточно заголовков в `CORS_ALLOW_HEADERS`

**Решение:**
Добавьте все необходимые заголовки (см. пример выше)

## 📝 Чеклист

- [ ] Extension ID получен из `chrome://extensions/`
- [ ] Extension ID добавлен в `CORS_ALLOWED_ORIGINS`
- [ ] `CORS_ALLOW_CREDENTIALS = True` установлен
- [ ] Все необходимые заголовки в `CORS_ALLOW_HEADERS`
- [ ] Django сервер перезапущен
- [ ] CORS ошибки исчезли в консоли браузера

---

**Готово!** CORS настроен для работы с Chrome расширением.
