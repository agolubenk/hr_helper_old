# HR Helper Django Application

Django-приложение для управления HR процессами с интеграцией Gemini API, Huntflow и курсами валют НБРБ.

## Структура проекта

```
backend/
├── pyproject.toml
├── manage.py
├── config/                 # Основная конфигурация Django
│   ├── settings.py        # Настройки проекта
│   ├── urls.py           # Основные URL
│   ├── wsgi.py           # WSGI конфигурация
│   └── asgi.py           # ASGI конфигурация
├── apps/
│   ├── accounts/          # Управление пользователями и ролями
│   │   ├── models.py     # Кастомная модель User
│   │   ├── admin.py      # Админка пользователей
│   │   ├── signals.py    # Сигналы Django
│   │   └── management/commands/
│   │       └── seed_roles.py  # Создание групп и прав
│   └── finance/           # Финансы и грейды
│       ├── models.py     # Grade и CurrencyRate
│       ├── admin.py      # Админка финансов
│       ├── services.py   # Интеграция с НБРБ
│       ├── management/commands/
│       │   └── update_nbrb_rates.py  # Обновление курсов
│       └── migrations/
│           └── 0002_seed_grades.py   # Начальные грейды
└── README.md
```

## Установка и запуск

### 1. Создание виртуального окружения
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate     # Windows
```

### 2. Установка зависимостей
```bash
pip install -e .
```

### 3. Создание и применение миграций
```bash
python manage.py makemigrations
python manage.py migrate
```

### 4. Создание суперпользователя
```bash
python manage.py createsuperuser
```

### 5. Засеивание ролей и грейдов
```bash
python manage.py seed_roles
```

### 6. Обновление курсов валют НБРБ
```bash
python manage.py update_nbrb_rates
```

### 7. Запуск сервера разработки
```bash
python manage.py runserver
```

## Функциональность

### Пользователи и роли
- **Администраторы**: полный доступ ко всем функциям
- **Рекрутеры**: полный доступ ко всем функциям  
- **Наблюдатели**: только просмотр (view_* права)
- **Интервьюеры**: просмотр + специальные поля (ФИО, календарь, email)

### Интеграции
- **Gemini API**: ключ API для AI-анализа
- **Huntflow**: поддержка prod и sandbox окружений
- **Telegram**: никнейм для уведомлений
- **Выбор системы**: переключение между prod/sandbox

### Финансы
- **Грейды**: Junior, Junior+, Middle, Middle+, Senior, Lead, Head
- **Курсы валют**: BYN, USD, PLN из официального API НБРБ
- **Автообновление**: команда для ежедневного обновления курсов

## Автоматизация

### Обновление курсов валют
Для автоматического обновления курсов НБРБ добавьте в cron:
```bash
# Каждый день в 18:05 по минскому времени
5 18 * * * cd /path/to/backend && python manage.py update_nbrb_rates
```

### Альтернатива через Celery Beat
Если используете Celery, добавьте периодическую задачу:
```python
# В settings.py
CELERY_BEAT_SCHEDULE = {
    'update-nbrb-rates': {
        'task': 'apps.finance.tasks.update_rates',
        'schedule': crontab(hour=18, minute=5),
    },
}
```

## API НБРБ

Источник курсов валют: https://api.nbrb.by/exrates/rates?periodicity=0
- `periodicity=0` - ежедневные официальные курсы
- Автоматическая нормализация масштаба (например, курс за 100 единиц приводится к 1 единице)
- Поддержка BYN (базовая валюта), USD, PLN

## Разработка

### Добавление новых полей
1. Измените модель в `models.py`
2. Создайте миграцию: `python manage.py makemigrations`
3. Примените миграцию: `python manage.py migrate`

### Добавление новых ролей
1. Добавьте название группы в `ROLE_NAMES` в `seed_roles.py`
2. Настройте права доступа в методе `handle`
3. Запустите команду: `python manage.py seed_roles`

### Тестирование
```bash
python manage.py test
```
