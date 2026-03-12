# 📋 Чеклист для запуска в продакшене

## 🔐 1. Безопасность

### Обязательно:
- [ ] **SECRET_KEY** - изменить на случайный секретный ключ (использовать переменную окружения)
- [ ] **DEBUG = False** - уже установлено ✅
- [ ] **ALLOWED_HOSTS** - указать реальные домены вместо `*`
- [ ] **CSRF_COOKIE_SECURE = True** - для HTTPS
- [ ] **SESSION_COOKIE_SECURE = True** - для HTTPS
- [ ] **SECURE_SSL_REDIRECT = True** - редирект на HTTPS
- [ ] **SECURE_HSTS_SECONDS** - включить HSTS
- [ ] Убрать хардкодные секреты из кода (GOOGLE_OAUTH2_CLIENT_SECRET)

### Текущие проблемы:
```python
# settings.py строка 16 - НЕБЕЗОПАСНО!
SECRET_KEY = 'django-insecure-hrhelper-secret-key-change-in-production'

# settings.py строка 200 - НЕБЕЗОПАСНО!
GOOGLE_OAUTH2_CLIENT_SECRET = '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'
```

## 🗄️ 2. База данных

### Текущее состояние:
- Используется SQLite3 (не подходит для продакшена)

### Необходимо:
- [ ] Перейти на PostgreSQL (уже настроено в `settings_production.py`)
- [ ] Создать базу данных PostgreSQL
- [ ] Выполнить миграции: `python manage.py migrate --settings=config.settings_production`
- [ ] **Мигрировать данные из SQLite в PostgreSQL** (см. `MIGRATION_GUIDE.md`):
  ```bash
  python manage.py migrate_sqlite_to_postgres \
      --sqlite-db=db.sqlite3 \
      --postgres-db=hrhelper_production \
      --postgres-user=hrhelper_user \
      --postgres-password=your-password
  ```
- [ ] Создать суперпользователя: `python manage.py createsuperuser --settings=config.settings_production`
- [ ] Проверить мигрированные данные
- [ ] Настроить резервное копирование БД

## 📦 3. Статические и медиа файлы

### Текущее состояние:
- Статика обслуживается через Django (не оптимально для продакшена)

### Необходимо:
- [ ] Выполнить `python manage.py collectstatic --settings=config.settings_production`
- [ ] Настроить Nginx для обслуживания статики (уже есть в `nginx.conf`)
- [ ] Настроить обслуживание медиа файлов через Nginx
- [ ] Проверить права доступа к папкам `staticfiles/` и `media/`

## 🔄 4. Celery и Redis

### Необходимо:
- [ ] Убедиться, что Redis запущен и доступен
- [ ] Запустить Celery worker: `celery -A config worker -l info`
- [ ] Запустить Celery beat: `celery -A config beat -l info`
- [ ] Настроить мониторинг Celery задач
- [ ] Настроить автозапуск Celery при перезагрузке сервера (systemd/supervisor)

## 🌐 5. Веб-сервер

### Текущее состояние:
- Используется `runserver` (только для разработки)

### Необходимо:
- [ ] Установить Gunicorn (уже в Dockerfile)
- [ ] Настроить количество workers (рекомендуется: `(2 * CPU cores) + 1`)
- [ ] Настроить Nginx как reverse proxy (уже есть конфигурация)
- [ ] Настроить SSL сертификаты (Let's Encrypt)
- [ ] Обновить `nginx.conf` с реальным доменом

## 🔑 6. OAuth и API ключи

### Необходимо:
- [ ] Переместить все секреты в переменные окружения:
  - `GOOGLE_OAUTH2_CLIENT_ID`
  - `GOOGLE_OAUTH2_CLIENT_SECRET`
  - `GOOGLE_OAUTH_REDIRECT_URI` (для продакшена)
- [ ] Обновить redirect URIs в Google Cloud Console для продакшена:
  - `https://yourdomain.com/google-oauth/callback/`
  - `https://yourdomain.com/auth/google/login/callback/`
- [ ] Проверить все API ключи (Huntflow, Notion, ClickUp и т.д.)

## 📧 7. Email настройки

### Необходимо:
- [ ] Настроить SMTP сервер (уже есть в `settings_production.py`)
- [ ] Указать переменные окружения:
  - `EMAIL_HOST`
  - `EMAIL_PORT`
  - `EMAIL_HOST_USER`
  - `EMAIL_HOST_PASSWORD`
- [ ] Протестировать отправку email

## 📝 8. Логирование

### Необходимо:
- [ ] Настроить ротацию логов
- [ ] Настроить централизованное логирование (опционально)
- [ ] Убедиться, что папка `logs/` существует и доступна для записи

## 🐳 9. Docker (если используется)

### Необходимо:
- [ ] Создать `.env` файл с переменными окружения
- [ ] Обновить `docker-compose.production.yml` с реальными значениями
- [ ] **Убедиться, что `psycopg2-binary` и `gunicorn` добавлены в `requirements.txt`** ✅
- [ ] Собрать образы: `docker-compose -f docker-compose.production.yml build`
- [ ] Запустить: `docker-compose -f docker-compose.production.yml up -d`
- [ ] Проверить healthchecks всех сервисов

## 🔍 10. Мониторинг и мониторинг

### Необходимо:
- [ ] Настроить мониторинг приложения (Sentry, Rollbar и т.д.)
- [ ] Настроить мониторинг сервера (CPU, память, диск)
- [ ] Настроить алерты для критических ошибок
- [ ] Настроить health checks (`/health/` endpoint)

## 🚀 11. Деплой

### Необходимо:
- [ ] Настроить CI/CD пайплайн (опционально)
- [ ] Создать скрипт деплоя
- [ ] Настроить автоматические миграции
- [ ] Настроить откат (rollback) при проблемах

## 📋 12. Переменные окружения (.env)

Создайте файл `.env` со следующими переменными:

```bash
# Django
SECRET_KEY=your-super-secret-key-here-min-50-chars
DEBUG=False
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com

# База данных
DB_NAME=hrhelper_production
DB_USER=hrhelper_user
DB_PASSWORD=your-secure-db-password
DB_HOST=localhost
DB_PORT=5432

# Redis
REDIS_URL=redis://127.0.0.1:6379/1
CELERY_BROKER_URL=redis://127.0.0.1:6379/0
CELERY_RESULT_BACKEND=redis://127.0.0.1:6379/0

# Google OAuth
GOOGLE_OAUTH2_CLIENT_ID=your-client-id
GOOGLE_OAUTH2_CLIENT_SECRET=your-client-secret
GOOGLE_OAUTH_REDIRECT_URI=https://yourdomain.com/google-oauth/callback/

# Email
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-email-password

# Другие API ключи (если используются)
HUNTFLOW_API_KEY=your-huntflow-key
NOTION_API_KEY=your-notion-key
CLICKUP_API_KEY=your-clickup-key
```

## ⚠️ 13. Критические исправления в коде

### settings.py:
1. **Строка 16**: Заменить SECRET_KEY на переменную окружения
2. **Строка 65**: Убрать `'*'` из ALLOWED_HOSTS, указать реальные домены
3. **Строка 200**: Убрать хардкодный GOOGLE_OAUTH2_CLIENT_SECRET
4. **Строка 203**: Обновить GOOGLE_OAUTH_REDIRECT_URI для продакшена

### settings_production.py:
1. **Строка 12**: Обновить ALLOWED_HOSTS с реальным доменом
2. Проверить все переменные окружения

## 🔧 14. Команды для запуска

### Без Docker:
```bash
# Миграции
python manage.py migrate --settings=config.settings_production

# Сборка статики
python manage.py collectstatic --noinput --settings=config.settings_production

# Запуск Gunicorn
gunicorn --bind 0.0.0.0:8000 --workers 3 config.wsgi:application

# Запуск Celery worker
celery -A config worker -l info

# Запуск Celery beat
celery -A config beat -l info
```

### С Docker:
```bash
docker-compose -f docker-compose.production.yml up -d
```

## ✅ Финальная проверка

- [ ] Все тесты проходят
- [ ] Приложение доступно по HTTPS
- [ ] Статические файлы загружаются
- [ ] OAuth авторизация работает
- [ ] Celery задачи выполняются
- [ ] Email отправляется
- [ ] Логи пишутся корректно
- [ ] Резервное копирование настроено
- [ ] Мониторинг работает

## 📚 Дополнительные рекомендации

1. **Производительность:**
   - Настроить кэширование (Redis уже настроен)
   - Оптимизировать запросы к БД
   - Использовать CDN для статики (опционально)

2. **Безопасность:**
   - Регулярно обновлять зависимости
   - Использовать firewall
   - Настроить rate limiting
   - Регулярно проверять логи на подозрительную активность

3. **Масштабирование:**
   - Настроить load balancing (если нужно)
   - Использовать несколько Celery workers
   - Настроить горизонтальное масштабирование БД (если нужно)
