# 📦 Руководство по миграции данных из SQLite в PostgreSQL

## 🎯 Цель

Миграция данных из локальной SQLite базы данных в PostgreSQL для продакшена, включая только необходимые таблицы:
- Вакансии
- Настройки компании
- Финансы (грейды, курсы валют, зарплатные вилки, бенчмарки)
- План найма
- Отчеты
- Интервьюеры
- Настройки Scorecard

## ⚠️ Важно

**НЕ мигрируются:**
- Пользователи (accounts_user) - создаются заново
- Сессии (django_session)
- Логи и кэш (huntflow_*, clickup_*, notion_*)
- Другие временные данные

## 📋 Подготовка

### 1. Создание PostgreSQL базы данных

```bash
# Подключитесь к PostgreSQL
psql -U postgres

# Создайте базу данных и пользователя
CREATE DATABASE hrhelper_production;
CREATE USER hrhelper_user WITH PASSWORD 'your-secure-password';
GRANT ALL PRIVILEGES ON DATABASE hrhelper_production TO hrhelper_user;
\q
```

### 2. Настройка переменных окружения

Создайте файл `.env` или установите переменные окружения:

```bash
export DB_NAME=hrhelper_production
export DB_USER=hrhelper_user
export DB_PASSWORD=your-secure-password
export DB_HOST=localhost
export DB_PORT=5432
```

### 3. Применение миграций в PostgreSQL

```bash
# Переключитесь на настройки продакшена
export DJANGO_SETTINGS_MODULE=config.settings_production

# Примените миграции
python manage.py migrate --settings=config.settings_production
```

## 🚀 Выполнение миграции

### Пробный запуск (рекомендуется сначала)

```bash
python manage.py migrate_sqlite_to_postgres \
    --sqlite-db=db.sqlite3 \
    --postgres-db=hrhelper_production \
    --postgres-user=hrhelper_user \
    --postgres-password=your-password \
    --postgres-host=localhost \
    --dry-run
```

### Реальная миграция

```bash
python manage.py migrate_sqlite_to_postgres \
    --sqlite-db=db.sqlite3 \
    --postgres-db=hrhelper_production \
    --postgres-user=hrhelper_user \
    --postgres-password=your-password \
    --postgres-host=localhost
```

### Использование переменных окружения

Если переменные окружения установлены, можно использовать упрощенную команду:

```bash
python manage.py migrate_sqlite_to_postgres --sqlite-db=db.sqlite3
```

## 📊 Мигрируемые таблицы

### Порядок миграции (с учетом зависимостей):

1. **Базовые таблицы:**
   - `finance_grade` - Грейды
   - `interviewers_interviewer` - Интервьюеры

2. **Таблицы с зависимостями:**
   - `interviewers_interviewrule` - Правила привлечения интервьюеров
   - `company_settings_rejectiontemplate` - Шаблоны отказов
   - `company_settings_companysettings` - Настройки компании
   - `company_settings_vacancyprompt` - Промпты для вакансий
   - `company_settings_vacancyprompthistory` - История промптов
   - `finance_currencyrate` - Курсы валют
   - `finance_plntax` - Налоги PLN
   - `finance_benchmarksettings` - Настройки бенчмарков

3. **Вакансии:**
   - `vacancies_vacancy` - Вакансии

4. **Финансы (зависит от вакансий):**
   - `finance_salaryrange` - Зарплатные вилки
   - `finance_benchmark` - Бенчмарки

5. **План найма:**
   - Все таблицы `hiring_plan_*`

6. **Отчеты:**
   - `reporting_reportcache` - Кэш отчетов
   - `reporting_calendarevent` - События календаря

7. **Google OAuth:**
   - `google_oauth_scorecardpathsettings` - Настройки Scorecard

8. **ManyToMany связи:**
   - Все промежуточные таблицы для ManyToMany полей

## ⚠️ Важные замечания

### Пользователи (User)

**Пользователи НЕ мигрируются автоматически!** Вам нужно:

1. Создать суперпользователя в новой БД:
```bash
python manage.py createsuperuser --settings=config.settings_production
```

2. Или экспортировать/импортировать пользователей отдельно (если нужно):
```bash
# Экспорт из SQLite
python manage.py dumpdata accounts.User --indent 2 > users.json

# Импорт в PostgreSQL (после миграции)
python manage.py loaddata users.json --settings=config.settings_production
```

### Внешние ключи

Скрипт автоматически обрабатывает:
- ✅ Пропуск записей с конфликтами (ON CONFLICT DO NOTHING)
- ✅ Обработку NULL значений
- ✅ ManyToMany связи

### Проверка после миграции

```bash
# Подключитесь к PostgreSQL
psql -U hrhelper_user -d hrhelper_production

# Проверьте количество записей
SELECT 'vacancies_vacancy' as table_name, COUNT(*) FROM vacancies_vacancy
UNION ALL
SELECT 'finance_grade', COUNT(*) FROM finance_grade
UNION ALL
SELECT 'company_settings_companysettings', COUNT(*) FROM company_settings_companysettings
UNION ALL
SELECT 'hiring_plan_hiringrequest', COUNT(*) FROM hiring_plan_hiringrequest;
```

## 🔧 Устранение проблем

### Ошибка подключения к PostgreSQL

```bash
# Проверьте, что PostgreSQL запущен
sudo systemctl status postgresql  # Linux
brew services list | grep postgresql  # macOS

# Проверьте доступность
psql -U hrhelper_user -d hrhelper_production -h localhost
```

### Ошибки целостности данных

Если возникают ошибки ForeignKey:
1. Убедитесь, что базовые таблицы мигрированы первыми
2. Проверьте, что пользователи существуют (или обновите ForeignKey на NULL)
3. Используйте `--dry-run` для проверки

### Пропущенные записи

Скрипт автоматически пропускает записи с конфликтами. Если нужно перезаписать:
1. Очистите таблицу в PostgreSQL: `TRUNCATE TABLE table_name CASCADE;`
2. Запустите миграцию снова

## 📝 После миграции

1. **Создайте суперпользователя:**
```bash
python manage.py createsuperuser --settings=config.settings_production
```

2. **Проверьте данные:**
```bash
python manage.py shell --settings=config.settings_production
>>> from apps.vacancies.models import Vacancy
>>> Vacancy.objects.count()
>>> from apps.finance.models import Grade
>>> Grade.objects.count()
```

3. **Обновите настройки:**
   - Проверьте настройки компании
   - Проверьте настройки Scorecard
   - Проверьте грейды и зарплатные вилки

4. **Запустите приложение:**
```bash
python manage.py runserver --settings=config.settings_production
```

## 🐳 Миграция в Docker

Если используете Docker:

```bash
# 1. Скопируйте SQLite БД в контейнер (или используйте volume)
docker cp db.sqlite3 hrhelper_web:/app/db.sqlite3

# 2. Выполните миграцию внутри контейнера
docker exec -it hrhelper_web python manage.py migrate_sqlite_to_postgres \
    --sqlite-db=/app/db.sqlite3 \
    --postgres-db=hrhelper_production \
    --postgres-user=hrhelper_user \
    --postgres-password=${DB_PASSWORD} \
    --postgres-host=db
```

## ✅ Чеклист миграции

- [ ] PostgreSQL база данных создана
- [ ] Пользователь PostgreSQL создан и имеет права
- [ ] Миграции применены в PostgreSQL
- [ ] Переменные окружения настроены
- [ ] Пробный запуск выполнен (`--dry-run`)
- [ ] Реальная миграция выполнена
- [ ] Данные проверены
- [ ] Суперпользователь создан
- [ ] Приложение протестировано с новой БД
