# Finance App - Финансы и грейды

## Описание
Приложение для управления финансовыми данными: курсы валют НБРБ и грейды сотрудников. Включает автоматическое обновление курсов валют и систему грейдов для HR процессов.

## Зависимости
- Django 5.2.6+
- requests (для API НБРБ)
- datetime, timezone

## Requirements
```python
# В requirements.txt
Django>=5.2.6
requests>=2.31.0
```

## Связи с другими приложениями
- **apps.interviewers**: Связь через `InterviewRule` (ForeignKey на Grade)
- **apps.vacancies**: Потенциальная связь для грейдов вакансий

## Модели

### Grade
**Назначение**: Грейды сотрудников (Junior, Middle, Senior и т.д.)

**Поля:**
- `name` - название грейда (CharField, max_length=64, unique=True)

**Предустановленные грейды:**
- Junior, Junior+, Middle, Middle+, Senior, Lead, Head

### PLNTax
**Назначение**: Налоговые ставки для расчета gross сумм в PLN

**Поля:**
- `name` - название налога (CharField, max_length=100)
- `rate` - налоговая ставка в процентах (DecimalField, max_digits=5, decimal_places=2)
- `is_active` - активен ли налог (BooleanField, default=True)
- `created_at` - время создания (DateTimeField, auto_now_add=True)
- `updated_at` - время обновления (DateTimeField, auto_now=True)

**Предустановленные налоги:**
- Подоходный налог (PIT): 17.0%
- Социальные взносы (ZUS): 19.48%
- Медицинское страхование: 9.0%
- Дополнительные взносы: 2.45% (неактивен по умолчанию)

**Методы:**
- `calculate_gross_from_net(net_amount)` - расчет gross из net суммы
- `calculate_net_from_gross(gross_amount)` - расчет net из gross суммы
- `get_tax_breakdown(gross_amount)` - детализация налогов

### SalaryRange
**Назначение**: Зарплатные вилки по вакансиям и грейдам

**Поля:**
- `vacancy` - вакансия (ForeignKey на Vacancy)
- `grade` - грейд (ForeignKey на Grade)
- `salary_min_usd` - минимальная зарплата в USD (DecimalField)
- `salary_max_usd` - максимальная зарплата в USD (DecimalField)
- `salary_min_byn` - минимальная зарплата в BYN (автоматически рассчитывается)
- `salary_max_byn` - максимальная зарплата в BYN (автоматически рассчитывается)
- `salary_min_pln` - минимальная зарплата в PLN (автоматически рассчитывается)
- `salary_max_pln` - максимальная зарплата в PLN (автоматически рассчитывается)
- `is_active` - активна ли вилка (BooleanField, default=True)
- `created_at` - время создания (DateTimeField, auto_now_add=True)
- `updated_at` - время обновления (DateTimeField, auto_now=True)

**Методы:**
- `update_currency_amounts()` - обновление сумм в других валютах
- `salary_range_usd` - строка с диапазоном в USD
- `salary_range_byn` - строка с диапазоном в BYN
- `salary_range_pln` - строка с диапазоном в PLN
- `update_all_currency_amounts()` - обновление всех вилок

### Benchmark
**Назначение**: Бенчмарки зарплат для анализа рынка

**Поля:**
- `type` - тип бенчмарка (CharField, choices: candidate, vacancy)
- `date_added` - дата добавления (DateTimeField, auto_now_add=True)
- `vacancy` - связанная вакансия (ForeignKey на Vacancy)
- `grade` - связанный грейд (ForeignKey на Grade)
- `amount` - сумма зарплаты в USD (DecimalField)
- `location` - географическое расположение (CharField, max_length=200)
- `notes` - дополнительные заметки (TextField, blank=True, null=True)
- `is_active` - активен ли бенчмарк (BooleanField, default=True)
- `created_at` - время создания (DateTimeField, auto_now_add=True)
- `updated_at` - время обновления (DateTimeField, auto_now=True)

**Свойства:**
- `amount_formatted` - отформатированная сумма с символом валюты
- `type_icon` - иконка для типа бенчмарка
- `type_color` - цвет для типа бенчмарка

**Типы бенчмарков:**
- `candidate` - зарплата кандидата
- `vacancy` - зарплата вакансии

### CurrencyRate
**Назначение**: Курсы валют от НБРБ

**Поля:**
- `code` - код валюты (CharField, choices: BYN, USD, PLN)
- `rate` - курс в BYN за 1 единицу валюты (DecimalField)
- `scale` - масштаб (PositiveIntegerField, default=1)
- `fetched_at` - время получения данных (DateTimeField)

**Поддерживаемые валюты:**
- BYN (базовая валюта)
- USD (доллар США)
- PLN (польский злотый)

**Свойства:**
- `status_info` - статус курса (сегодня, вчера, устарел)
- `display_rate` - отформатированный курс для отображения

## Логика работы

### Обновление курсов валют
1. **Источник данных**: API НБРБ (Национальный банк Республики Беларусь)
2. **Fallback данные**: Рыночные курсы при недоступности НБРБ
3. **Автоматическое обновление**: Через cron или команду Django
4. **Валидация**: Проверка корректности полученных данных

### Система грейдов
1. **Иерархия**: От Junior до Head
2. **Использование**: В правилах привлечения интервьюеров
3. **Валидация**: Уникальность названий

## Сервисы

### CurrencyRateService
**Файл**: `services.py`

**Методы:**

#### get_latest_rates()
- **Назначение**: Получение последних курсов валют
- **Возвращает**: Словарь с данными по валютам
- **Логика**: Сначала НБРБ, затем fallback данные

### PLNTaxCalculationService
**Файл**: `pln_tax_services.py`

**Методы:**

#### calculate_salary_with_taxes(net_amount_pln, currency_from, currency_to)
- **Назначение**: Расчет зарплаты с налогами и конвертацией валют
- **Параметры**: 
  - `net_amount_pln` - net сумма в PLN
  - `currency_from` - исходная валюта (по умолчанию PLN)
  - `currency_to` - целевая валюта (по умолчанию BYN)
- **Возвращает**: Словарь с детальным расчетом

#### get_tax_summary()
- **Назначение**: Получение сводки по налогам PLN
- **Возвращает**: Информацию об активных налогах и общей ставке

#### calculate_multiple_salaries(salaries)
- **Назначение**: Расчет налогов для нескольких зарплат
- **Параметры**: Список словарей с данными зарплат
- **Возвращает**: Результаты расчетов с итоговой сводкой

#### _get_nbrb_rates()
- **Назначение**: Получение курсов из API НБРБ
- **URL**: `https://api.nbrb.by/exrates/rates?periodicity=0`
- **Обработка**: Парсинг JSON, извлечение нужных валют

#### _get_fallback_rates_with_info()
- **Назначение**: Fallback курсы при недоступности НБРБ
- **Источники**: Рыночные данные
- **Статус**: Помечается как "nbrb_not_available"

### NBRBClient
**Назначение**: Клиент для работы с API НБРБ

**Методы:**
- `fetch_all()` - получение всех курсов
- `get_latest_available_rates()` - последние доступные курсы
- `extract_rate()` - извлечение курса для конкретной валюты

## Management Commands

### update_nbrb_rates
**Файл**: `management/commands/update_nbrb_rates.py`

**Использование:**
```bash
python manage.py update_nbrb_rates
python manage.py update_nbrb_rates --force  # Принудительное обновление
```

**Функциональность:**
1. Получение курсов из НБРБ
2. Обработка ошибок и fallback данных
3. Обновление записей в базе данных
4. Информативный вывод результатов

**Вывод:**
- ✅ Успешное обновление
- ⚠️ Предупреждения (fallback данные)
- ❌ Ошибки

## Админка

### CurrencyRateAdmin
**Особенности:**
- Кнопка "Обновить курсы" в списке
- Цветовая индикация статуса курсов
- Отображение времени последнего обновления
- Фильтрация по валютам и датам

**Действия:**
- `update_rates()` - обновление курсов из админки

### GradeAdmin
**Особенности:**
- Простое управление грейдами
- Поиск по названию
- Сортировка по алфавиту

## Эндпоинты

### Основные эндпоинты
- `GET /finance/` - дашборд с грейдами и курсами валют
- `POST /finance/update-rates/` - обновление курсов валют
- `POST /finance/grades/add/` - добавление грейда
- `DELETE /finance/grades/<id>/delete/` - удаление грейда

### Эндпоинты для налогов PLN
- `GET /finance/pln-taxes/` - дашборд управления налогами PLN
- `POST /finance/pln-taxes/add/` - добавление налога PLN
- `PUT /finance/pln-taxes/<id>/update/` - обновление налога PLN
- `DELETE /finance/pln-taxes/<id>/delete/` - удаление налога PLN
- `GET /finance/pln-taxes/calculate/` - расчет налогов для суммы

### Эндпоинты для зарплатных вилок
- `GET /finance/salary-ranges/` - список зарплатных вилок
- `POST /finance/salary-ranges/create/` - создание зарплатной вилки
- `GET /finance/salary-ranges/<id>/` - детальная информация о вилке
- `PUT /finance/salary-ranges/<id>/update/` - обновление зарплатной вилки
- `DELETE /finance/salary-ranges/<id>/delete/` - удаление зарплатной вилки
- `POST /finance/salary-ranges/update-currency/` - обновление курсов валют для всех вилок

### Эндпоинты для бенчмарков
- `GET /finance/benchmarks/` - список бенчмарков
- `POST /finance/benchmarks/create/` - создание бенчмарка
- `GET /finance/benchmarks/<id>/` - детальная информация о бенчмарке
- `PUT /finance/benchmarks/<id>/update/` - обновление бенчмарка
- `DELETE /finance/benchmarks/<id>/delete/` - удаление бенчмарка

## Особенности подключения

### Настройка в settings.py
```python
INSTALLED_APPS = [
    'apps.finance',
]
```

### Миграции
```bash
python manage.py makemigrations finance
python manage.py migrate
```

### Инициализация данных
```bash
# Создание грейдов
python manage.py migrate finance 0002_seed_grades

# Обновление курсов валют
python manage.py update_nbrb_rates
```

### Автоматическое обновление
**Cron задача:**
```bash
# В crontab
0 9 * * * cd /path/to/project && python manage.py update_nbrb_rates
```

**Скрипт**: `cron_update_rates.sh`

## API интеграция

### НБРБ API
**Базовый URL**: `https://api.nbrb.by/exrates/rates`
**Параметры**: `?periodicity=0` (ежедневные курсы)

**Формат ответа:**
```json
[
  {
    "Cur_ID": 145,
    "Date": "2024-01-15T00:00:00",
    "Cur_Abbreviation": "USD",
    "Cur_Scale": 1,
    "Cur_Name": "Доллар США",
    "Cur_OfficialRate": 3.25
  }
]
```

### Fallback источники
- Рыночные курсы валют
- Кэшированные данные
- Стандартные значения

## Использование в коде

### Получение курса валюты
```python
from apps.finance.models import CurrencyRate

# Получение курса USD
usd_rate = CurrencyRate.objects.get(code='USD')
print(f"1 USD = {usd_rate.rate} BYN")

# Проверка статуса
print(usd_rate.status_info)  # "Сегодня", "Вчера", "Устарел"
```

### Работа с грейдами
```python
from apps.finance.models import Grade

# Получение всех грейдов
grades = Grade.objects.all().order_by('name')

# Проверка существования грейда
if Grade.objects.filter(name='Senior').exists():
    senior_grade = Grade.objects.get(name='Senior')
```

### Работа с налогами PLN
```python
from apps.finance.models import PLNTax
from apps.finance.logic.pln_tax_services import PLNTaxCalculationService
from decimal import Decimal

# Расчет gross из net суммы
net_amount = Decimal('5000.00')
gross_amount = PLNTax.calculate_gross_from_net(net_amount)
print(f"Net: {net_amount} PLN -> Gross: {gross_amount} PLN")

# Детализация налогов
breakdown = PLNTax.get_tax_breakdown(gross_amount)
for tax in breakdown['taxes']:
    print(f"{tax['name']}: {tax['amount']} PLN")

# Расчет с конвертацией валют
calculation = PLNTaxCalculationService.calculate_salary_with_taxes(
    net_amount_pln=Decimal('5000.00'),
    currency_from='PLN',
    currency_to='BYN'
)
print(f"Gross в BYN: {calculation['final_amounts']['gross']} BYN")

# Получение сводки по налогам
summary = PLNTaxCalculationService.get_tax_summary()
print(f"Общая налоговая ставка: {summary['total_tax_rate_percent']}%")
```

### Работа с зарплатными вилками
```python
from apps.finance.models import SalaryRange
from apps.vacancies.models import Vacancy
from apps.finance.models import Grade

# Создание зарплатной вилки
vacancy = Vacancy.objects.get(name='Python Developer')
grade = Grade.objects.get(name='Middle')

salary_range = SalaryRange.objects.create(
    vacancy=vacancy,
    grade=grade,
    salary_min_usd=Decimal('2500.00'),
    salary_max_usd=Decimal('3500.00')
)

# Автоматический расчет в других валютах
print(f"USD: {salary_range.salary_range_usd}")
print(f"BYN: {salary_range.salary_range_byn}")
print(f"PLN: {salary_range.salary_range_pln}")

# Обновление курсов валют для всех вилок
SalaryRange.update_all_currency_amounts()

# Получение всех активных вилок
active_ranges = SalaryRange.objects.filter(is_active=True)
for range in active_ranges:
    print(f"{range.vacancy.name} - {range.grade.name}: {range.salary_range_usd}")
```

### Работа с бенчмарками
```python
from apps.finance.models import Benchmark

# Создание бенчмарка кандидата
candidate_benchmark = Benchmark.objects.create(
    type='candidate',
    vacancy=vacancy,
    grade=grade,
    amount=Decimal('3500.00'),
    location='Минск, Беларусь',
    notes='Кандидат с 3 годами опыта'
)

# Создание бенчмарка вакансии
vacancy_benchmark = Benchmark.objects.create(
    type='vacancy',
    vacancy=vacancy,
    grade=grade,
    amount=Decimal('4000.00'),
    location='Варшава, Польша',
    notes='Вакансия в международной компании'
)

# Получение бенчмарков по типу
candidate_benchmarks = Benchmark.objects.filter(type='candidate', is_active=True)
vacancy_benchmarks = Benchmark.objects.filter(type='vacancy', is_active=True)

# Получение бенчмарков по вакансии и грейду
python_benchmarks = Benchmark.objects.filter(
    vacancy__name__icontains='Python',
    grade__name='Middle',
    is_active=True
)

# Статистика по бенчмаркам
total_benchmarks = Benchmark.objects.filter(is_active=True).count()
candidate_count = Benchmark.objects.filter(type='candidate', is_active=True).count()
vacancy_count = Benchmark.objects.filter(type='vacancy', is_active=True).count()

print(f"Всего бенчмарков: {total_benchmarks}")
print(f"Кандидаты: {candidate_count}")
print(f"Вакансии: {vacancy_count}")

# Форматированный вывод
for benchmark in Benchmark.objects.filter(is_active=True)[:5]:
    print(f"{benchmark.get_type_display()} - {benchmark.vacancy.name} ({benchmark.grade.name}): {benchmark.amount_formatted} в {benchmark.location}")
```

## Отладка

### Логирование
```python
# В services.py
print(f"Получены курсы: {rates_info}")
print(f"Ошибка API НБРБ: {e}")
```

### Тестирование
```bash
# Тест обновления курсов
python manage.py update_nbrb_rates --force

# Проверка данных в админке
python manage.py shell
>>> from apps.finance.models import CurrencyRate, Grade
>>> CurrencyRate.objects.all()
>>> Grade.objects.all()
```

## Troubleshooting

### Проблемы с API НБРБ
1. **Нет ответа**: Проверьте интернет-соединение
2. **Неправильный формат**: Проверьте структуру API ответа
3. **Ошибки парсинга**: Проверьте логи команды

### Проблемы с курсами
1. **Устаревшие данные**: Запустите `update_nbrb_rates`
2. **Неправильные курсы**: Проверьте fallback данные
3. **Отсутствие валют**: Проверьте настройки валют

### Проблемы с грейдами
1. **Дублирование**: Проверьте уникальность в модели
2. **Отсутствие грейдов**: Выполните миграцию 0002_seed_grades

## Производительность
- Курсы обновляются раз в день
- Кэширование на уровне базы данных
- Минимальное количество API запросов
- Fallback данные для стабильности
