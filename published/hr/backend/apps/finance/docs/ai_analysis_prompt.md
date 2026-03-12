# Промпт для ИИ анализа данных о зарплатах

## Описание

Промпт для ИИ анализа данных о зарплатах был обновлен для работы **только с вакансиями** и включает автоматическую конвертацию валют в USD. Промпт настроен на извлечение структурированных данных для сохранения в базу данных с учетом текущих курсов валют.

## Структура промпта

### Основные задачи ИИ:
1. Проанализировать каждую **ВАКАНСИЮ** из данных (только вакансии, не кандидаты)
2. Извлечь структурированную информацию для сохранения в базу
3. **Конвертировать все зарплаты в USD** используя текущие курсы валют
4. Определить рекомендуемые зарплатные диапазоны
5. Выявить дополнительные данные (формат работы, компенсации, бенефиты, технологии, домен)

### Формат ответа (JSON):

```json
{
    "analysis_metadata": {
        "analysis_date": "YYYY-MM-DD HH:MM:SS",
        "total_processed": число,
        "data_source": "источник данных",
        "analysis_version": "3.0",
        "currency_conversion_used": true
    },
    "structured_benchmarks": [
        {
            "type": "vacancy",
            "vacancy_name": "название вакансии",
            "grade": "грейд (Junior/Middle/Senior/Lead)",
            "salary_from": число_в_USD,
            "salary_to": число_в_USD,
            "location": "локация (город, страна)",
            "work_format": "remote/office/hybrid/all world",
            "compensation": "дополнительные компенсации и бонусы",
            "benefits": "социальные льготы и бенефиты",
            "development": "возможности для развития и обучения",
            "technologies": "используемые технологии и стеки",
            "domain": "домен деятельности (retail/fintech/gaming/etc)",
            "notes": "дополнительные заметки"
        }
    ],
    "recommended_ranges": {
        "grade_name": {
            "min_salary": число_в_USD,
            "max_salary": число_в_USD,
            "median_salary": число_в_USD,
            "sample_size": число,
            "confidence_level": "high/medium/low"
        }
    },
    "market_insights": {
        "trends": ["тренд1", "тренд2"],
        "in_demand_skills": ["навык1", "навык2"],
        "salary_growth_rate": "процент",
        "market_competitiveness": "высокая/средняя/низкая",
        "geographic_variations": {
            "location": "разница в зарплатах в USD"
        },
        "currency_analysis": {
            "conversion_accuracy": "высокая/средняя/низкая",
            "exchange_rate_impact": "влияние курсов на зарплаты"
        }
    },
    "recommendations": {
        "for_candidates": ["рекомендация1", "рекомендация2"],
        "for_companies": ["рекомендация1", "рекомендация2"],
        "salary_negotiation_tips": ["совет1", "совет2"]
    }
}
```

## Соответствие полям модели Benchmark

### Обязательные поля:
- **type**: Тип бенчмарка (всегда "vacancy")
- **vacancy_name**: Название вакансии
- **grade**: Грейд (Junior/Middle/Senior/Lead)
- **salary_from**: Минимальная зарплата в USD
- **salary_to**: Максимальная зарплата в USD (обязательно для вакансий)
- **location**: Локация в формате "Город, Страна"

### Дополнительные поля:
- **work_format**: Формат работы (remote/office/hybrid/all world)
- **compensation**: Дополнительные компенсации и бонусы
- **benefits**: Социальные льготы и бенефиты
- **development**: Возможности для развития и обучения
- **technologies**: Используемые технологии и стеки (через запятую)
- **domain**: Домен деятельности (из предустановленного списка)
- **notes**: Дополнительные заметки

## Доступные значения

### Форматы работы (WorkFormat):
- `remote` - Удаленка
- `office` - Офис
- `hybrid` - Гибрид
- `all world` - All World

### Домены деятельности (Domain):
- `retail` - Retail (Ритейл)
- `fintech` - Fintech (Финтех)
- `gaming` - Gaming (Гейминг)
- `gambling` - Gambling (Гемблинг)
- `betting` - Betting (Беттинг)
- `medtech` - Medtech/Healthtech (Медтех/Здравоохранение)
- `telecom` - Telecom (Телеком)
- `edtech` - Edtech (Образовательные технологии)
- `agritech` - Agritech (Агротех)
- `proptech` - Proptech (Недвижимость)
- `legaltech` - Legaltech (Юридические технологии)
- `govtech` - Govtech (Государственное управление)
- `logistics` - Logistics/Supply Chain (Логистика)
- `foodtech` - Foodtech (Пищевые технологии)
- `insurtech` - Insurtech (Страхование)
- `martech` - Martech (Маркетинговые технологии)
- `adtech` - Adtech (Рекламные технологии)
- `cybersecurity` - Cybersecurity (Кибербезопасность)
- `cleantech` - Cleantech/Sustaintech (Экологические технологии)
- `hrtech` - HRtech (Управление персоналом)
- `traveltech` - Traveltech (Туризм)
- `sporttech` - Sporttech (Спортивные технологии)
- `entertainment` - Entertainment (Развлечения)
- `ecommerce` - E-commerce (Электронная коммерция)
- `blockchain` - Blockchain/Crypto (Блокчейн и крипто)
- `aiml` - AI/ML (Искусственный интеллект и машинное обучение)
- `iot` - IoT (Интернет вещей)
- `cloud` - Cloud Computing (Облачные вычисления)

### Грейды:
- `Junior` - Junior (1-3 года)
- `Middle` - Middle (3-6 лет)
- `Senior` - Senior (6+ лет)
- `Lead` - Lead (6+ лет)

## Важные требования

1. **Анализ только вакансий**: Тип бенчмарка всегда `vacancy`
2. **Конвертация валют**: Все суммы ОБЯЗАТЕЛЬНО конвертируются в USD используя текущие курсы валют
3. **Формат работы**: Только из предустановленного списка
4. **Домен**: Только из предустановленного списка
5. **Грейд**: Только Junior/Middle/Senior/Lead
6. **Обязательные поля**: Все поля обязательны, включая `salary_to` (диапазон зарплат)
7. **Технологии**: Указываются через запятую
8. **Локация**: В формате "Город, Страна" (например, "Минск, Беларусь")
9. **Курсы валют**: Автоматически передаются в промпт для точной конвертации

## Использование

Промпт автоматически используется в системе при анализе данных через ИИ. Данные из поля `structured_benchmarks` могут быть напрямую сохранены в модель `Benchmark`.

### Пример использования:

```python
from apps.finance.ai_analyzer import AIBenchmarkAnalyzer

analyzer = AIBenchmarkAnalyzer()
prompt = analyzer.get_ai_analysis_prompt()

# Получить курсы валют
currency_rates = analyzer.get_currency_rates_for_prompt()

# Заменить плейсхолдеры на реальные данные
full_prompt = prompt.format(
    benchmark_data=json_data,
    currency_rates=currency_rates
)

# Отправить в ИИ сервис
ai_response = send_to_ai_service(full_prompt)

# Парсить ответ и сохранять в базу
structured_data = json.loads(ai_response)
for benchmark_data in structured_data['structured_benchmarks']:
    # Создать объект Benchmark (только для вакансий)
    if benchmark_data['type'] == 'vacancy':
        # Создать объект Benchmark
        pass
```

## Обновление промпта

Промпт можно обновить через:
1. Админку Django (`/admin/finance/benchmarksettings/`)
2. API endpoint для обновления настроек
3. Миграции данных (для массовых изменений)

## Версионирование

Текущая версия промпта: **3.0**

### Изменения в версии 3.0:
- **Анализ только вакансий**: Убран анализ кандидатов, фокус только на вакансиях
- **Автоматическая конвертация валют**: Добавлен плейсхолдер `{currency_rates}` для передачи текущих курсов
- **Обязательный диапазон зарплат**: Поле `salary_to` стало обязательным для вакансий
- **Улучшенная структура ответа**: Добавлен `currency_analysis` в `market_insights`
- **Правила конвертации валют**: Детальные инструкции по конвертации BYN, EUR, PLN в USD
- **Версионирование**: Добавлено поле `currency_conversion_used` в метаданные

### Изменения в версии 2.0:
- Добавлено поле `technologies`
- Добавлено поле `domain`
- Обновлен формат работы (добавлен `all world`)
- Улучшена структура ответа
- Добавлены более детальные требования к полям

## Конвертация валют

Система автоматически передает актуальные курсы валют в промпт:

```
Текущие курсы валют:
- 1 PLN = 0.2785 USD
- 1 USD = 3.0419 BYN
- 1 BYN = 0.3287 USD
```

ИИ использует эти курсы для точной конвертации всех зарплат в USD перед сохранением в базу данных.
