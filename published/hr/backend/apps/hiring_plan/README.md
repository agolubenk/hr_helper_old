# 📋 Hiring Plan - Планы найма

## 🎯 Описание

Приложение **Hiring Plan** предназначено для стратегического планирования найма специалистов. Позволяет создавать планы найма, управлять позициями, отслеживать прогресс и анализировать метрики рекрутинга.

## ✨ Ключевые возможности

- ✅ **Создание планов найма** с временными рамками и ответственными
- ✅ **Управление позициями** с приоритетами и дедлайнами
- ✅ **Отслеживание прогресса** с автоматическим расчетом метрик
- ✅ **Визуализация данных** с прогресс-барами и индикаторами
- ✅ **Интеграция с существующими модулями** (Vacancy, Grade, User)
- ✅ **Фильтрация и поиск** планов и позиций
- ✅ **Аналитика и дашборды** с ключевыми метриками

## 🏗️ Архитектура

### Модели данных

#### HiringPlan
- **title** - Название плана найма
- **description** - Описание плана
- **start_date/end_date** - Временные рамки
- **status** - Статус (draft, active, paused, completed, cancelled)
- **owner** - Владелец плана
- **responsible_recruiter** - Ответственный рекрутер

#### HiringPlanPosition
- **hiring_plan** - Связь с планом найма
- **vacancy** - Связь с вакансией
- **headcount_needed/hired/in_progress** - Количество специалистов
- **priority** - Приоритет (1-4: критический, высокий, средний, низкий)
- **urgency_deadline** - Критический дедлайн
- **grades** - Требуемые грейды (M2M)
- **specifics/notes** - Дополнительная информация

#### PlanMetrics
- **hiring_plan** - Связь с планом (OneToOne)
- **total_positions** - Общее количество позиций
- **total_headcount_needed/hired** - Общие счетчики
- **completion_rate** - Процент выполнения

### Связи с другими модулями

```
HiringPlan (1) ──→ (N) HiringPlanPosition
HiringPlan (1) ──→ (1) PlanMetrics
HiringPlanPosition (N) ──→ (1) Vacancy
HiringPlanPosition (N) ──→ (N) Grade
HiringPlan (N) ──→ (1) User (owner, responsible_recruiter)
```

## 🚀 Функциональность

### CRUD операции

#### Планы найма
- **Создание** - `/hiring-plans/create/`
- **Просмотр списка** - `/hiring-plans/`
- **Детальный просмотр** - `/hiring-plans/<id>/`
- **Редактирование** - `/hiring-plans/<id>/edit/`
- **Удаление** - `/hiring-plans/<id>/delete/`

#### Позиции в планах
- **Добавление** - `/hiring-plans/<plan_id>/positions/add/`
- **Редактирование** - `/hiring-plans/positions/<id>/edit/`
- **Удаление** - `/hiring-plans/positions/<id>/delete/`

### Аналитика

#### Дашборд плана
- **Общий прогресс** - `/hiring-plans/<id>/dashboard/`
- **Метрики по приоритетам**
- **Статус позиций**
- **Алерты и предупреждения**

#### Автоматические расчеты
- **completion_rate** - Процент выполнения плана
- **fulfillment_rate** - Процент закрытия позиции
- **remaining_headcount** - Оставшееся количество
- **is_overdue** - Проверка просрочки дедлайнов

## 🎨 Интерфейс

### Страницы

1. **Список планов** (`plan_list.html`)
   - Карточки планов с прогресс-барами
   - Фильтры по статусу, рекрутеру, датам
   - Сводная статистика

2. **Детальный просмотр** (`plan_detail.html`)
   - Информация о плане
   - Таблица позиций с метриками
   - Кнопки управления

3. **Формы создания/редактирования** (`plan_form.html`, `position_form.html`)
   - Валидация данных
   - Удобные виджеты
   - JavaScript валидация

4. **Дашборд метрик** (`plan_dashboard.html`)
   - Визуализация прогресса
   - Статистика по приоритетам
   - Алерты и предупреждения

### Стилизация

- **Bootstrap 5** - Адаптивный дизайн
- **Font Awesome** - Иконки
- **Цветовая индикация** - Статусы и приоритеты
- **Progress bars** - Визуализация прогресса

## 🔧 Техническая реализация

### Сервисный слой

#### HiringPlanService
- `get_dashboard_data()` - Данные для дашборда
- `get_plans_summary()` - Сводка по всем планам
- `get_priority_statistics()` - Статистика по приоритетам
- `get_overdue_positions()` - Просроченные позиции
- `get_upcoming_deadlines()` - Приближающиеся дедлайны

### Формы

#### HiringPlanForm
- Валидация дат
- Фильтрация рекрутеров
- Автоматическое назначение владельца

#### HiringPlanPositionForm
- Валидация количества
- Исключение дублирующих вакансий
- Множественный выбор грейдов

### Views

- **Class-based views** для CRUD операций
- **LoginRequiredMixin** для защиты
- **Пагинация** для списков
- **AJAX** для обновления метрик

## 📊 Метрики и аналитика

### Ключевые показатели

- **Общий прогресс плана** - completion_rate
- **Прогресс по позициям** - fulfillment_rate
- **Распределение по приоритетам**
- **Статус позиций** (закрыты/в процессе/не начаты)
- **Просроченные дедлайны**
- **Приближающиеся дедлайны**

### Автоматические обновления

- Метрики обновляются при изменении позиций
- Расчет процентов в реальном времени
- Проверка просрочки дедлайнов

## 🔗 Интеграция

### С существующими модулями

- **vacancies.Vacancy** - Выбор вакансий для позиций
- **finance.Grade** - Требуемые грейды специалистов
- **accounts.User** - Владельцы и ответственные рекрутеры

### Готовность к расширению

- **HuntFlow интеграция** - Автосинхронизация данных
- **Telegram уведомления** - Алерты о дедлайнах
- **Расширенная аналитика** - Time-to-Fill, Cost-per-Hire
- **Бюджетирование** - Финансовое планирование

## 🚀 Быстрый старт

### 1. Создание плана найма

```python
from apps.hiring_plan.models import HiringPlan
from django.contrib.auth import get_user_model

User = get_user_model()
user = User.objects.get(username='recruiter')

plan = HiringPlan.objects.create(
    title='Q4 2025 Backend Team Growth',
    description='План расширения backend команды',
    start_date='2025-10-01',
    end_date='2025-12-31',
    status='active',
    owner=user,
    responsible_recruiter=user
)
```

### 2. Добавление позиции

```python
from apps.hiring_plan.models import HiringPlanPosition
from apps.vacancies.models import Vacancy
from apps.finance.models import Grade

vacancy = Vacancy.objects.get(name='Backend Engineer (Java)')
middle_grade = Grade.objects.get(name='Middle')

position = HiringPlanPosition.objects.create(
    hiring_plan=plan,
    vacancy=vacancy,
    headcount_needed=5,
    headcount_hired=2,
    headcount_in_progress=1,
    priority=1,  # Критический
    urgency_deadline='2025-11-15'
)
position.grades.add(middle_grade)
```

### 3. Получение метрик

```python
from apps.hiring_plan.services import HiringPlanService

dashboard_data = HiringPlanService.get_dashboard_data(plan)
print(f"Прогресс: {dashboard_data['overview']['completion_rate']}%")
print(f"Просрочено: {dashboard_data['overdue']} позиций")
```

## 📝 Примеры использования

### Веб-интерфейс

1. **Создание плана**: `/hiring-plans/create/`
2. **Просмотр списка**: `/hiring-plans/`
3. **Добавление позиции**: `/hiring-plans/<id>/positions/add/`
4. **Просмотр метрик**: `/hiring-plans/<id>/dashboard/`

### API (будущее развитие)

```python
# Получение планов
GET /api/hiring-plans/

# Создание плана
POST /api/hiring-plans/
{
    "title": "Q4 2025 Backend Team Growth",
    "start_date": "2025-10-01",
    "end_date": "2025-12-31",
    "status": "active"
}

# Обновление позиции
PATCH /api/positions/<id>/
{
    "headcount_hired": 3,
    "headcount_in_progress": 1
}
```

## 🔮 Планы развития

### Фаза 2: HuntFlow интеграция
- Автосинхронизация количества нанятых
- Автоактивация вакансий при создании позиции
- Webhooks для реалтайм обновлений

### Фаза 3: Расширенная аналитика
- Time-to-Fill (среднее время закрытия)
- Cost-per-Hire (стоимость найма)
- Source of Hire (эффективность каналов)
- Прогнозирование даты завершения

### Фаза 4: Бюджетирование
- Бюджет плана найма
- Tracking затрат vs план
- Финансовые отчеты

### Фаза 5: Collaboration
- Комментарии к позициям
- История изменений
- Telegram уведомления
- Совместная работа

## 🛠️ Техническая поддержка

### Логирование
- Все операции логируются
- Ошибки отслеживаются
- Метрики производительности

### Мониторинг
- Проверка просроченных дедлайнов
- Алерты о критических позициях
- Статистика использования

### Безопасность
- Аутентификация обязательна
- Проверка прав доступа
- Валидация всех входных данных

---

**Версия**: 1.0 MVP  
**Дата**: 14 октября 2025  
**Статус**: Готов к использованию
