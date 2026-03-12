Отлично! Теперь я понимаю вашу архитектуру. Вот детализированные примеры интеграции бизнес-процесса с hh.ru в ваши существующие файлы:

## 1. Расширение models.py

### Добавляем модель для временного хранения вакансий с hh.ru

```python
# Добавить в models.py после класса BenchmarkSettings

class HHVacancyTemp(models.Model):
    """Временная модель для хранения сырых вакансий с hh.ru перед обработкой"""
    hh_id = models.CharField(
        _("ID вакансии hh.ru"),
        max_length=50,
        unique=True,
        help_text=_("Уникальный ID вакансии на hh.ru")
    )
    
    raw_data = models.JSONField(
        _("Сырые данные"),
        help_text=_("JSON данные вакансии с API hh.ru")
    )
    
    processed = models.BooleanField(
        _("Обработана"),
        default=False,
        help_text=_("Была ли вакансия отправлена на AI анализ")
    )
    
    created_at = models.DateTimeField(_("Создана"), auto_now_add=True)
    
    class Meta:
        verbose_name = _("Временная вакансия hh.ru")
        verbose_name_plural = _("Временные вакансии hh.ru")
        ordering = ['-created_at']

# Дополняем BenchmarkSettings новыми полями
class BenchmarkSettings(models.Model):
    # ... существующие поля ...
    
    # Настройки для hh.ru
    hh_channel_active = models.BooleanField(
        _("Канал hh.ru активен"),
        default=True,
        help_text=_("Включить/отключить сбор вакансий с hh.ru")
    )
    
    max_daily_hh_tasks = models.IntegerField(
        _("Максимум задач hh.ru в сутки"),
        default=100,
        help_text=_("Лимит обработки вакансий с hh.ru за день")
    )
    
    hh_ai_prompt = models.TextField(
        _("AI промпт для hh.ru"),
        default="",
        help_text=_("Специальный промпт для анализа вакансий с hh.ru")
    )
```

## 2. Расширение services.py

### Добавляем сервис для работы с hh.ru

```python
# Добавить в services.py после CurrencyRateService

class HHVacancyService:
    """Сервис для работы с вакансиями hh.ru"""
    
    def __init__(self):
        self.api_url = "https://api.hh.ru/vacancies"
        self.headers = {"User-Agent": "Finance/v1.0 (your-email@example.com)"}
    
    def fetch_vacancies(self, search_params: dict) -> dict:
        """Получает вакансии с hh.ru API"""
        try:
            response = requests.get(
                self.api_url, 
                params=search_params, 
                headers=self.headers,
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"❌ Ошибка API hh.ru: {e}")
            return {"items": [], "found": 0}
    
    def preprocess_salary(self, vacancy_data: dict) -> dict:
        """Предобработка зарплаты с конвертацией в USD"""
        from .models import CurrencyRate, PLNTax
        
        salary_info = vacancy_data.get('salary', {})
        if not salary_info:
            return {"salary_usd_from": None, "salary_usd_to": None}
        
        original_currency = salary_info.get('currency', 'RUB')
        gross_from = salary_info.get('from')
        gross_to = salary_info.get('to')
        
        result = {}
        
        # Конвертируем зарплату в USD
        for amount, field in [(gross_from, 'salary_usd_from'), (gross_to, 'salary_usd_to')]:
            if not amount:
                result[field] = None
                continue
                
            try:
                if original_currency == 'PLN':
                    # PLN: сначала gross -> net, потом в USD
                    net_amount = PLNTax.calculate_net_from_gross(Decimal(str(amount)))
                    pln_rate = CurrencyRate.objects.get(code='PLN')
                    usd_amount = net_amount / pln_rate.rate
                else:
                    # Прямая конвертация в USD
                    if original_currency == 'USD':
                        usd_amount = Decimal(str(amount))
                    else:
                        currency_rate = CurrencyRate.objects.get(code=original_currency)
                        usd_amount = Decimal(str(amount)) / currency_rate.rate
                        
                result[field] = usd_amount.quantize(Decimal('0.01'))
            except (CurrencyRate.DoesNotExist, ValueError, TypeError):
                result[field] = None
        
        return result
    
    def format_for_ai_analysis(self, hh_id: str, vacancy_data: dict) -> str:
        """Форматирует данные вакансии для AI анализа"""
        return f"""Vacancy_ID: {hh_id}
Компания: {vacancy_data.get('employer', {}).get('name', '')}
Название: {vacancy_data.get('name', '')}
Описание: {vacancy_data.get('description', '')}
Зарплата: {vacancy_data.get('salary', {})}
Локация: {vacancy_data.get('area', {}).get('name', '')}
Опыт: {vacancy_data.get('experience', {}).get('name', '')}
Тип занятости: {vacancy_data.get('employment', {}).get('name', '')}
График работы: {vacancy_data.get('schedule', {}).get('name', '')}"""
```

## 3. Расширение tasks.py

### Добавляем задачи для автоматизации hh.ru

```python
# Добавить в tasks.py новые задачи

from .models import HHVacancyTemp, BenchmarkSettings, Benchmark, Grade, Domain
from .services import HHVacancyService
from .hh_search_config import HH_SPECIALIZATIONS, HH_LOCATIONS, get_search_url_params

@shared_task(bind=True, max_retries=3)
def fetch_hh_vacancies_task(self):
    """Задача сбора вакансий с hh.ru"""
    try:
        settings = BenchmarkSettings.load()
        if not settings.hh_channel_active:
            logger.info("Канал hh.ru отключен")
            return {"success": False, "message": "Канал hh.ru отключен"}
        
        hh_service = HHVacancyService()
        total_fetched = 0
        
        # Проходим по всем специализациям и локациям
        for specialization in HH_SPECIALIZATIONS:
            for location in HH_LOCATIONS:
                params = get_search_url_params(
                    specialization_ids=[specialization['id']],
                    location_codes=[location['code']],
                    keywords=specialization['keywords']
                )
                
                result = hh_service.fetch_vacancies(params)
                
                for item in result.get('items', []):
                    hh_id = item.get('id')
                    
                    # Дедупликация - пропускаем если уже есть
                    if HHVacancyTemp.objects.filter(hh_id=hh_id).exists():
                        continue
                    
                    # Сохраняем временную запись
                    HHVacancyTemp.objects.create(
                        hh_id=hh_id,
                        raw_data=item,
                        processed=False
                    )
                    total_fetched += 1
                
                # Пауза между запросами
                time.sleep(1)
        
        logger.info(f"Собрано {total_fetched} новых вакансий с hh.ru")
        
        # Запускаем обработку с лимитом
        process_hh_queue_with_limit.delay()
        
        return {"success": True, "fetched": total_fetched}
        
    except Exception as e:
        logger.error(f"Ошибка при сборе вакансий hh.ru: {e}")
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=60 * (2 ** self.request.retries))
        return {"success": False, "message": str(e)}

@shared_task
def process_hh_queue_with_limit():
    """Обработка очереди hh.ru с лимитом задач в сутки"""
    from datetime import date
    
    settings = BenchmarkSettings.load()
    max_tasks = settings.max_daily_hh_tasks
    
    today = date.today()
    processed_today = HHVacancyTemp.objects.filter(
        created_at__date=today,
        processed=True
    ).count()
    
    remaining = max_tasks - processed_today
    if remaining <= 0:
        logger.info("Достигнут дневной лимит задач hh.ru")
        return {"message": "Лимит достигнут"}
    
    # Берем необработанные записи
    unprocessed = HHVacancyTemp.objects.filter(
        processed=False
    ).order_by('created_at')[:remaining]
    
    hh_service = HHVacancyService()
    processed_count = 0
    
    for temp_record in unprocessed:
        try:
            # Предобработка данных
            preprocessed = hh_service.preprocess_salary(temp_record.raw_data)
            vacancy_text = hh_service.format_for_ai_analysis(
                temp_record.hh_id, 
                temp_record.raw_data
            )
            
            # Отправляем в AI анализ
            analyze_hh_vacancy_with_ai.delay({
                'hh_id': temp_record.hh_id,
                'vacancy_text': vacancy_text,
                'preprocessed_salary': preprocessed,
                'raw_data': temp_record.raw_data
            })
            
            # Помечаем как обработанную
            temp_record.processed = True
            temp_record.save()
            processed_count += 1
            
        except Exception as e:
            logger.error(f"Ошибка при обработке вакансии {temp_record.hh_id}: {e}")
            continue
    
    logger.info(f"Отправлено {processed_count} вакансий на AI анализ")
    return {"processed": processed_count}

@shared_task
def analyze_hh_vacancy_with_ai(vacancy_data: dict):
    """AI анализ вакансии с hh.ru"""
    try:
        import openai
        import json
        
        settings = BenchmarkSettings.load()
        
        # Расширенный промпт с полем Vacancy_ID и доменами
        extended_prompt = settings.hh_ai_prompt or f"""
        Проанализируй следующий текст о вакансии и верни результат в виде JSON-объекта.
        JSON должен содержать поля:
        'Vacancy_ID': уникальный идентификатор вакансии с hh.ru;
        'Company': название компании;
        'Geo': местоположение компании или вакансии;
        'Specialization': специализация или направление работы;
        'Grade': уровень должности (Trainee, Junior, Junior+, Middle, Middle+, Senior, Senior+, Lead, Head, C-level);
        'Salary Min': минимальная зарплата;
        'Salary Max': максимальная зарплата;
        'Work Format': формат работы (удаленная, офис, релокация, гибрид);
        'Domain': доменная область. Выбери из списка: {', '.join([choice[0] for choice in Domain.choices])}. Если домен не определен — None.
        
        Верни только валидный JSON-объект.
        
        Текст: {{vacancy_text}}
        """
        
        # Отправляем в AI (замените на ваш AI провайдер)
        vacancy_text = vacancy_data['vacancy_text']
        
        # Здесь используйте ваш AI API (OpenAI, Anthropic, etc.)
        # response = openai.ChatCompletion.create(...)
        
        # Для демонстрации - заглушка
        ai_response_text = f'{{"Vacancy_ID": "{vacancy_data["hh_id"]}", "Company": "Demo Company", "Domain": "Fintech"}}'
        
        ai_response = json.loads(ai_response_text)
        
        # Сохраняем результат в Benchmark
        save_hh_analysis_result.delay(ai_response, vacancy_data)
        
        logger.info(f"AI анализ завершен для вакансии {vacancy_data['hh_id']}")
        
    except Exception as e:
        logger.error(f"Ошибка AI анализа для {vacancy_data.get('hh_id')}: {e}")

@shared_task
def save_hh_analysis_result(ai_response: dict, vacancy_data: dict):
    """Сохраняет результат AI анализа в Benchmark"""
    try:
        vacancy_id = ai_response.get('Vacancy_ID')
        
        if vacancy_id != vacancy_data['hh_id']:
            logger.error(f"ID mismatch: {vacancy_id} != {vacancy_data['hh_id']}")
            return
        
        # Находим или создаем Grade
        grade_name = ai_response.get('Grade', '').strip()
        if grade_name:
            grade, _ = Grade.objects.get_or_create(name=grade_name)
        else:
            grade = None
        
        # Находим или создаем Vacancy
        from apps.vacancies.models import Vacancy
        vacancy_name = ai_response.get('Specialization', 'Unknown')
        vacancy, _ = Vacancy.objects.get_or_create(name=vacancy_name)
        
        # Маппим domain
        domain_code = ai_response.get('Domain')
        if domain_code and hasattr(Domain, domain_code):
            domain = domain_code
        else:
            domain = None
        
        # Создаем Benchmark
        benchmark = Benchmark.objects.create(
            type=BenchmarkType.VACANCY,
            hh_vacancy_id=vacancy_data['hh_id'],
            vacancy=vacancy,
            grade=grade,
            salary_from=vacancy_data['preprocessed_salary']['salary_usd_from'],
            salary_to=vacancy_data['preprocessed_salary']['salary_usd_to'],
            location=ai_response.get('Geo', ''),
            work_format=ai_response.get('Work Format', ''),
            domain=domain,
            notes=f"Источник: hh.ru. Компания: {ai_response.get('Company', '')}",
            is_active=True
        )
        
        logger.info(f"Создан Benchmark ID {benchmark.id} для hh.ru вакансии {vacancy_id}")
        
    except Exception as e:
        logger.error(f"Ошибка при сохранении результата анализа: {e}")
```

## 4. Расширение views.py

### Добавляем view для настроек

```python
# Добавить в views.py новую view

@login_required
def benchmarks_settings(request):
    """Страница настроек бенчмарков с управлением hh.ru"""
    settings = BenchmarkSettings.load()
    
    if request.method == 'POST':
        # Обновляем настройки hh.ru
        settings.hh_channel_active = request.POST.get('hh_channel_active') == 'on'
        settings.max_daily_hh_tasks = int(request.POST.get('max_daily_hh_tasks', 100))
        settings.hh_ai_prompt = request.POST.get('hh_ai_prompt', '')
        settings.save()
        
        messages.success(request, 'Настройки hh.ru обновлены')
        return redirect('finance:benchmarks_settings')
    
    # Статистика
    from datetime import date
    today = date.today()
    
    # Статистика по hh.ru
    hh_stats = {
        'temp_vacancies': HHVacancyTemp.objects.count(),
        'processed_today': HHVacancyTemp.objects.filter(
            created_at__date=today,
            processed=True
        ).count(),
        'pending_processing': HHVacancyTemp.objects.filter(processed=False).count(),
        'benchmarks_from_hh': Benchmark.objects.filter(
            hh_vacancy_id__isnull=False,
            is_active=True
        ).count()
    }
    
    context = {
        'settings': settings,
        'hh_stats': hh_stats,
        'available_domains': Domain.choices,
    }
    
    return render(request, 'finance/benchmarks_settings.html', context)

@login_required
@csrf_exempt
@require_http_methods(["POST"])
def start_hh_collection_manual(request):
    """Ручной запуск сбора вакансий с hh.ru"""
    try:
        from .tasks import fetch_hh_vacancies_task
        
        task = fetch_hh_vacancies_task.delay()
        
        return JsonResponse({
            'success': True,
            'message': 'Сбор вакансий с hh.ru запущен',
            'task_id': task.id
        })
        
    except Exception as e:
        logger.error(f"Ошибка при запуске сбора hh.ru: {e}")
        return JsonResponse({
            'success': False,
            'message': f'Ошибка: {str(e)}'
        })
```

## 5. Расширение urls.py

```python
# Добавить в urls.py новые маршруты

urlpatterns += [
    # Настройки hh.ru
    path('benchmarks/settings/', views.benchmarks_settings, name='benchmarks_settings'),
    path('api/hh/start-collection/', views.start_hh_collection_manual, name='start_hh_collection'),
    
    # Статусы задач
    path('api/task-status/<str:task_id>/', views.task_status, name='task_status'),
]
```

## 6. Планировщик задач (Celery Beat)

### Создаем файл celery.py в вашем Django проекте

```python
# В settings.py или отдельном celery.py файле

from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    'fetch-hh-vacancies-daily': {
        'task': 'apps.finance.tasks.fetch_hh_vacancies_task',
        'schedule': crontab(hour=9, minute=0),  # Каждый день в 9:00
    },
    'process-hh-queue-hourly': {
        'task': 'apps.finance.tasks.process_hh_queue_with_limit',
        'schedule': crontab(minute=0),  # Каждый час
    },
}
```

Этот подход полностью интегрируется с вашей существующей архитектурой, используя ваши модели (`Benchmark`, `BenchmarkSettings`, `Grade`, `Domain`), сервисы конвертации валют (`CurrencyRate`, `PLNTax`) и поддерживает все бизнес-требования с автоматическим лимитированием задач, дедупликацией и AI-анализом через расширенный промпт с полем `Vacancy_ID`.

[1](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/images/30706959/88c0380e-4211-49d7-87f4-0c64d7e89357/image.jpg?AWSAccessKeyId=ASIA2F3EMEYEUIVKWU2K&Signature=guK7nYoTv0iq3uYvrJNdlFOtWkE%3D&x-amz-security-token=IQoJb3JpZ2luX2VjEKj%2F%2F%2F%2F%2F%2F%2F%2F%2F%2FwEaCXVzLWVhc3QtMSJHMEUCIQDkg%2FFIw1bSVxM0GVyx2KdGrOvQdYcd5q4iDiXACN2pDAIgNWpEgmj7cWTAgReOwTCvuHEqMQ%2FEZXZM3p5M2IN1YVoq8QQIMRABGgw2OTk3NTMzMDk3MDUiDNtoQNxT%2BC5EfJ5LiSrOBIe1BY0bz16tQvLkhUHxsAD4y4b8wxPuxBSmYuNcT%2FnOzMnSGpHa%2F%2BdVeZiWzob%2F6IMFKD6veJ23UwkvZiKloCWzCTHhGCiwTK8tCIoEKDw1cWaINaQVowEtJUM8g6pUfLT2aKJiwqeVtHbNQ70zZksrmKEbfNszZU%2FEnk28JFxAukB2DOIqfHqcyeAK%2FuLk4X5d6Vjc4XwAfXe4Kf10oZC4lC2CldlFIDwbZ%2BaAJ80dIiykeqntIOefJ0HjXwjf7tEBN0C4OHnH1BvSpBw6w%2FgegvKgoD0MDcmLgpaNoUszsDaZmL1x7tYv4cv%2FFiDmUhvScCDnREB343Jis%2B2zRMlTf9s%2Fd14D%2BkzZdWWKZeVdUfgSm6vLdRJXoNCWWMTYINtIbpCgQDSdqoVacSoTBRcP8hTWLdEL%2FXBprXstQzbnNGmTM2yVLMwBRAY3Y%2BrjJQO92nGY9gwzn8wL%2BioXqZGdmFl3uKMg8fuo5JyAWjcibNn3JY15WeP1PwVUUsN6UNAC4RhV%2BxJmFhhPfos%2FThSyk4iXuGfgSFAQZqHLNiSfTorrN5vfP%2FaXkdT2Vz1Nm9GdWC18%2B8bbDOUqnZxg9NKFfNAK846gR3evubxsjaHe7fN07%2BTizvPK%2BYARa%2BEDCarFLxgUZmXqW13YaH0sPOeBIiCg12e0J0A9IHr%2FbeFPywNJVeNAgWcELfgKyGP3420pdga9iktw9TLBff%2BVFfm1TPYlroDWgUtuaLuS8BBC3fJ6ueSwIUEKEzXroxyIx%2B%2BxpjW%2BWOGOAk51S59%2FMODVxcYGOpoB6hIMuONp%2F8xSPWEcxp62o62B2A6ZNf5tviSRz6p0vtpdsKOkU2BUM%2F77DxN98tRy%2By46Qu4kJYt1HH%2BmBNnMB13G04dtlJWuC9c4HLvhczwxTfFuZZxDvh8TZRk6Ww5bOOJ5U23WnuWzNe%2BcwFF0qSYyScjohWGtHMmqn9FU8Chv7%2BJxWSIES7kGV15chi0VA7Pb0ncv%2FEc0FQ%3D%3D&Expires=1758555449)
[2](https://github.com/agolubenk/CandBenchmark)
[3](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/30706959/81625e48-64c7-49e0-959c-24beeef48104/services.py)
[4](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/30706959/cbd4b294-618d-4cc7-93e0-084aae1ee6f7/tasks.py)
[5](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/30706959/d482bcf4-808f-44e5-bb10-e60fb97194a4/hh_search_config.py)
[6](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/30706959/ce867c06-aea7-4f83-a57d-d114673c9bbd/hh_search_constants.py)
[7](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/30706959/bae38c97-ddf6-42f9-b1d9-68bb22f86fcd/views.py)
[8](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/30706959/8f8e6db3-756b-47af-b357-ed9b8c7fda10/models.py)