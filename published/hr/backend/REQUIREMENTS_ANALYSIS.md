# 📦 Анализ зависимостей проекта

## ✅ Используемые библиотеки

### Django Core
- **Django==4.2.16** - основной фреймворк
- **asgiref, sqlparse, pytz, tzdata** - зависимости Django

### Django Extensions
- **djangorestframework** - REST API
- **django-cors-headers** - CORS поддержка
- **django-allauth** - OAuth аутентификация (Google)
- **django-redis** - Redis кэширование
- **django-timezone-field** - поля с таймзонами
- **django-celery-beat** - планировщик задач

### База данных
- **psycopg2-binary** - PostgreSQL драйвер (для продакшена)

### Celery & Redis
- **celery** - фоновые задачи
- **redis** - брокер сообщений
- **kombu, vine, billiard, amqp** - зависимости Celery

### Google API
- **google-api-python-client** - Google API клиент
- **google-auth, google-auth-oauthlib, google-auth-httplib2** - OAuth
- **google-api-core, googleapis-common-protos** - зависимости Google API
- **httplib2, uritemplate** - HTTP клиенты

### HTTP & Networking
- **requests** - HTTP запросы
- **urllib3, certifi, charset-normalizer, idna** - зависимости requests

### Безопасность
- **PyJWT** - JWT токены
- **cryptography** - шифрование
- **oauthlib, requests-oauthlib** - OAuth

### Excel Export
- **openpyxl** - экспорт в Excel (используется в `reporting` и `hiring_plan`)

### Утилиты
- **python-dotenv** - загрузка .env файлов
- **python-dateutil** - парсинг дат
- **gunicorn** - WSGI сервер для продакшена

## ❌ Удаленные библиотеки (не используются)

### Telethon==1.41.2
- **Статус**: ❌ НЕ используется
- **Причина**: Telegram интеграция не используется в проекте
- **Проверка**: `grep -r "telethon\|Telethon"` - нет совпадений

### qrcode==8.2
- **Статус**: ❌ НЕ используется
- **Причина**: Генерация QR кодов не используется
- **Проверка**: `grep -r "qrcode\|QRCode"` - нет совпадений в Python коде

### pillow==11.3.0
- **Статус**: ❌ НЕ используется напрямую
- **Причина**: Обработка изображений не требуется
- **Примечание**: Может быть транзитивной зависимостью, но не используется напрямую

### prompt_toolkit==3.0.52
- **Статус**: ❌ НЕ используется
- **Причина**: CLI интерфейс не используется
- **Проверка**: `grep -r "prompt_toolkit"` - нет совпадений

### wcwidth==0.2.14
- **Статус**: ⚠️ Транзитивная зависимость
- **Причина**: Зависимость других библиотек (например, click)
- **Решение**: Оставляем, так как требуется другими пакетами

## 📊 Статистика

- **Всего зависимостей**: ~50
- **Основные пакеты**: 15
- **Транзитивные зависимости**: ~35
- **Удалено неиспользуемых**: 4

## 🔍 Как проверить использование

### Проверка импортов
```bash
# Проверить использование библиотеки
grep -r "import library_name\|from library_name" apps/ logic/

# Проверить в settings.py
grep -r "library_name" config/settings.py
```

### Проверка транзитивных зависимостей
```bash
# Установить зависимости
pip install -r requirements.txt

# Проверить установленные пакеты
pip list

# Проверить зависимости конкретного пакета
pip show package_name
```

## 📝 Рекомендации

1. **Регулярно обновляйте зависимости** для безопасности
2. **Используйте `pip-audit`** для проверки уязвимостей
3. **Закрепляйте версии** для стабильности
4. **Проверяйте транзитивные зависимости** при обновлениях

## 🔄 Обновление зависимостей

```bash
# Обновить все зависимости
pip install --upgrade -r requirements.txt

# Обновить конкретную зависимость
pip install --upgrade package_name==new_version

# Зафиксировать новые версии
pip freeze > requirements.freeze.txt
```

## ⚠️ Важно

- **Не удаляйте транзитивные зависимости** - они требуются другими пакетами
- **Тестируйте после обновлений** - могут быть breaking changes
- **Используйте виртуальное окружение** для изоляции
