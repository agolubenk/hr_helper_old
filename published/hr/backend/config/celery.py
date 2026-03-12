import os
from celery import Celery
from celery.schedules import crontab

# Устанавливаем переменную окружения для настроек Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('hrhelper')

# Используем строку конфигурации Django для загрузки настроек Celery
app.config_from_object('django.conf:settings', namespace='CELERY')

# Дополнительные настройки
app.conf.update(
    # Максимальное время выполнения задачи (30 минут)
    task_time_limit=1800,
    # Мягкий лимит времени (25 минут)
    task_soft_time_limit=1500,
    # Ограничиваем параллелизм для задач Gemini (1 запрос в минуту)
    worker_concurrency=1,
    # Настройки для ClickUp API
    clickup_task_delay_min=10,  # Минимальная задержка между запросами (секунды)
    clickup_task_delay_max=45,  # Максимальная задержка между запросами (секунды)
    # Настройки сериализации
    accept_content=['json'],
    task_serializer='json',
    result_serializer='json',
    # Настройки времени
    timezone='Europe/Moscow',
    enable_utc=True,
)

# Автоматическое обнаружение задач в установленных приложениях
app.autodiscover_tasks(['apps.finance', 'apps.clickup_int', 'apps.notion_int', 'apps.huntflow', 'apps.google_oauth', 'apps.hhru'])

# Принудительно регистрируем задачи finance после настройки Django
@app.task
def save_hh_analysis_result(ai_response: dict, vacancy_data: dict):
    """Сохраняет результат AI анализа в Benchmark"""
    from apps.finance.tasks import save_hh_analysis_result as original_task
    return original_task(ai_response, vacancy_data)

@app.task
def update_currency_rates():
    """Обновляет курсы валют НБРБ"""
    from apps.finance.tasks import update_currency_rates as original_task
    return original_task()

# Настройки для периодических задач
app.conf.beat_schedule = {
        # Finance задачи
        'fetch-hh-vacancies': {
            'task': 'apps.finance.tasks.fetch_hh_vacancies_task',
            'schedule': 1200.0,  # Каждые 20 минут
        },
    'process-hh-queue': {
        'task': 'apps.finance.tasks.process_hh_queue_with_limit',
        'schedule': 300.0,   # Каждые 5 минут
    },
    'cleanup-old-benchmarks': {
        'task': 'apps.finance.tasks.cleanup_old_benchmarks',
        'schedule': 86400.0,  # Каждый день
    },
    'generate-benchmark-statistics': {
        'task': 'apps.finance.tasks.generate_benchmark_statistics',
        'schedule': 3600.0,  # Каждый час
    },
    
    # Обновление курсов валют НБРБ (11:00 и 16:00 в будние дни)
    'update-currency-rates-morning': {
        'task': 'config.celery.update_currency_rates',
        'schedule': crontab(minute=0, hour=11, day_of_week='1-5'),  # 11:00 ПН-ПТ
    },
    'update-currency-rates-afternoon': {
        'task': 'config.celery.update_currency_rates',
        'schedule': crontab(minute=0, hour=16, day_of_week='1-5'),  # 16:00 ПН-ПТ
    },
    
    # Notion задачи
    'auto-sync-notion-pages': {
        'task': 'apps.notion_int.tasks.auto_sync_notion_pages',
        'schedule': 1800.0,  # Каждые 30 минут
        'kwargs': {'user_id': 1},  # TODO: Настроить для всех пользователей
    },
    
    # Huntflow задачи
    'refresh-huntflow-tokens': {
        'task': 'apps.huntflow.tasks.refresh_huntflow_tokens',
        'schedule': 3600.0,  # Каждый час
    },
    'check-huntflow-token-health': {
        'task': 'apps.huntflow.tasks.check_huntflow_token_health',
        'schedule': 21600.0,  # Каждые 6 часов
    },
    
    # Google OAuth задачи
    'refresh-google-oauth-tokens': {
        'task': 'apps.google_oauth.tasks.refresh_google_oauth_tokens',
        'schedule': 1800.0,  # Каждые 30 минут
    },
    # ОТКЛЮЧЕНО: Автоматическое удаление OAuth аккаунтов
    # 'cleanup-expired-oauth-accounts': {
    #     'task': 'apps.google_oauth.tasks.cleanup_expired_oauth_accounts',
    #     'schedule': 86400.0,  # Каждый день
    # },
    'validate-oauth-tokens': {
        'task': 'apps.google_oauth.tasks.validate_oauth_tokens',
        'schedule': 3600.0,  # Каждый час
    },
    # HH.ru: кэш активных вакансий и откликов (страницы грузятся из кэша)
    'refresh-hhru-vacancies-and-responses-cache': {
        'task': 'apps.hhru.tasks.refresh_hhru_vacancies_and_responses_cache',
        'schedule': 600.0,  # Каждые 10 минут
    },
    'sync-calendar-events-by-vacancies': {
        'task': 'apps.google_oauth.tasks.sync_calendar_events_by_vacancies',
        'schedule': 3600.0,  # Каждый час
    },
    
    # ClickUp задачи (работают по требованию через веб-интерфейс)
    # Массовый импорт и синхронизация запускаются вручную через UI
    # Это правильно, так как эти операции требуют пользовательского вмешательства
}

# Настройки маршрутизации задач для ClickUp
# ОТКЛЮЧЕНО: Используем стандартную очередь celery для упрощения
# app.conf.task_routes = {
#     'apps.clickup_int.tasks.bulk_import_clickup_tasks': {'queue': 'clickup_import'},
#     'apps.clickup_int.tasks.import_single_task': {'queue': 'clickup_import'},
#     'apps.clickup_int.tasks.retry_failed_tasks': {'queue': 'clickup_import'},
# }

app.conf.timezone = 'UTC'

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
