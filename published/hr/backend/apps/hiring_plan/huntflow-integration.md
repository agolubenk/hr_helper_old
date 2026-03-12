# 🔄 СИНХРОНИЗАЦИЯ HUNTFLOW → HIRING PLAN

## 🎯 КОНЦЕПЦИЯ ИНТЕГРАЦИИ

**Задача:** Автоматически создавать и обновлять заявки на найм (HiringRequest) при закрытии вакансий в HuntFlow.

**Логика:**
1. При найме кандидата в HuntFlow (статус "Hired") → создаётся/обновляется HiringRequest со статусом "closed"
2. Автоматическое сопоставление данных HuntFlow ↔ HR Helper
3. Webhook-и или периодическая синхронизация через API

---

## 📊 МАППИНГ ДАННЫХ HUNTFLOW → HIRING REQUEST

### HuntFlow API → HiringRequest

| HuntFlow Field | API Path | HiringRequest Field | Описание |
|---|---|---|---|
| `vacancy.position` | `/vacancies/{id}` | `vacancy` | Название вакансии → сопоставление с Vacancy |
| `applicant.id` | `/applicants/{id}` | `candidate_id` | ID кандидата в HuntFlow |
| `applicant.first_name` + `last_name` | `/applicants/{id}` | `candidate_name` | ФИО кандидата |
| `status.id` (hired) | `/vacancies/{id}/applicants/{id}` | `status='closed'` | Статус найма |
| `log.employment_date` | `/applicants/{id}/logs` | `closed_date` | Дата найма |
| `vacancy.created` | `/vacancies/{id}` | `opening_date` | Дата создания вакансии |
| `vacancy.money` | `/vacancies/{id}` | Доп. поля | Зарплата |
| `vacancy.account_division` | `/vacancies/{id}` | `project` | Подразделение → проект |
| `log.created` | `/applicants/{id}/logs` | `created_at` | Дата создания лога |

---

## 🔧 НОВАЯ МОДЕЛЬ: HuntflowSync

```python
class HuntflowSync(models.Model):
    """Синхронизация данных с HuntFlow"""
    
    ENTITY_TYPE_CHOICES = [
        ('vacancy', 'Вакансия'),
        ('applicant', 'Кандидат'),
        ('status_change', 'Изменение статуса'),
    ]
    
    SYNC_STATUS_CHOICES = [
        ('pending', 'Ожидает'),
        ('success', 'Успешно'),
        ('failed', 'Ошибка'),
        ('skipped', 'Пропущено'),
    ]
    
    # Идентификаторы HuntFlow
    huntflow_vacancy_id = IntegerField(
        verbose_name='ID вакансии в HuntFlow',
        db_index=True
    )
    huntflow_applicant_id = IntegerField(
        null=True, blank=True,
        verbose_name='ID кандидата в HuntFlow',
        db_index=True
    )
    huntflow_log_id = IntegerField(
        null=True, blank=True,
        verbose_name='ID лога в HuntFlow'
    )
    
    # Тип синхронизируемой сущности
    entity_type = CharField(
        max_length=20,
        choices=ENTITY_TYPE_CHOICES,
        verbose_name='Тип сущности'
    )
    
    # Связь с HiringRequest
    hiring_request = ForeignKey(
        HiringRequest,
        on_delete=SET_NULL,
        null=True, blank=True,
        related_name='huntflow_syncs',
        verbose_name='Заявка на найм'
    )
    
    # Данные из HuntFlow (JSON)
    huntflow_data = JSONField(
        verbose_name='Данные из HuntFlow',
        help_text='Полные данные объекта из HuntFlow API'
    )
    
    # Статус синхронизации
    sync_status = CharField(
        max_length=20,
        choices=SYNC_STATUS_CHOICES,
        default='pending',
        verbose_name='Статус синхронизации'
    )
    error_message = TextField(
        blank=True,
        verbose_name='Сообщение об ошибке'
    )
    
    # Метаданные
    synced_at = DateTimeField(
        null=True, blank=True,
        verbose_name='Дата синхронизации'
    )
    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Синхронизация HuntFlow'
        verbose_name_plural = 'Синхронизации HuntFlow'
        ordering = ['-created_at']
        indexes = [
            Index(fields=['huntflow_vacancy_id', 'huntflow_applicant_id']),
            Index(fields=['sync_status']),
        ]
    
    def __str__(self):
        return f"HuntFlow Sync: Vacancy #{self.huntflow_vacancy_id} - {self.get_sync_status_display()}"
```

---

## 🔧 СЕРВИС СИНХРОНИЗАЦИИ

```python
# services/huntflow_sync_service.py

import requests
from django.conf import settings
from django.utils import timezone
from datetime import datetime
from ..models import HiringRequest, HuntflowSync, VacancySLA, Vacancy
from finance.models import Grade

class HuntflowSyncService:
    """Сервис для синхронизации данных с HuntFlow"""
    
    BASE_URL = "https://api.huntflow.ai/v2"
    
    def __init__(self):
        self.api_token = settings.HUNTFLOW_API_TOKEN
        self.account_id = settings.HUNTFLOW_ACCOUNT_ID
        self.headers = {
            'Authorization': f'Bearer {self.api_token}',
            'Content-Type': 'application/json'
        }
    
    def _make_request(self, endpoint, method='GET', params=None, data=None):
        """Выполнить запрос к HuntFlow API"""
        url = f"{self.BASE_URL}/accounts/{self.account_id}/{endpoint}"
        
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=self.headers,
                params=params,
                json=data,
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"HuntFlow API Error: {e}")
            return None
    
    def get_vacancy(self, vacancy_id):
        """Получить вакансию из HuntFlow"""
        return self._make_request(f"vacancies/{vacancy_id}")
    
    def get_applicant(self, applicant_id):
        """Получить кандидата из HuntFlow"""
        return self._make_request(f"applicants/{applicant_id}")
    
    def get_vacancy_applicants(self, vacancy_id, status=None):
        """Получить кандидатов по вакансии"""
        params = {}
        if status:
            params['status'] = status
        
        return self._make_request(
            f"vacancies/{vacancy_id}/applicants",
            params=params
        )
    
    def get_applicant_logs(self, applicant_id):
        """Получить логи кандидата"""
        return self._make_request(f"applicants/{applicant_id}/logs")
    
    def map_huntflow_to_vacancy(self, hf_vacancy_data):
        """Сопоставить вакансию HuntFlow с Vacancy в системе"""
        # Поиск по названию позиции
        position = hf_vacancy_data.get('position', '')
        
        vacancy = Vacancy.objects.filter(
            name__icontains=position
        ).first()
        
        if not vacancy:
            # Создаем новую вакансию (опционально)
            # или возвращаем None для ручного сопоставления
            pass
        
        return vacancy
    
    def map_huntflow_to_grade(self, hf_vacancy_data):
        """Определить грейд из данных HuntFlow"""
        # Можно использовать money, опыт, или другие поля
        # Упрощенная логика - по названию или salary
        
        money = hf_vacancy_data.get('money', '')
        
        # Примерная логика (нужно адаптировать под ваши данные)
        if 'Senior' in hf_vacancy_data.get('position', ''):
            grade = Grade.objects.filter(name__icontains='Senior').first()
        elif 'Middle' in hf_vacancy_data.get('position', ''):
            grade = Grade.objects.filter(name__icontains='Middle').first()
        elif 'Junior' in hf_vacancy_data.get('position', ''):
            grade = Grade.objects.filter(name__icontains='Junior').first()
        else:
            grade = None
        
        return grade
    
    def sync_hired_applicant(self, vacancy_id, applicant_id, log_data):
        """Синхронизировать нанятого кандидата"""
        
        # Проверяем, не синхронизирован ли уже
        existing_sync = HuntflowSync.objects.filter(
            huntflow_vacancy_id=vacancy_id,
            huntflow_applicant_id=applicant_id,
            entity_type='status_change',
            sync_status='success'
        ).first()
        
        if existing_sync:
            print(f"Applicant {applicant_id} already synced")
            return existing_sync.hiring_request
        
        # Получаем данные из HuntFlow
        hf_vacancy = self.get_vacancy(vacancy_id)
        hf_applicant = self.get_applicant(applicant_id)
        
        if not hf_vacancy or not hf_applicant:
            # Создаем запись об ошибке
            HuntflowSync.objects.create(
                huntflow_vacancy_id=vacancy_id,
                huntflow_applicant_id=applicant_id,
                entity_type='status_change',
                sync_status='failed',
                error_message='Failed to fetch data from HuntFlow API',
                huntflow_data={}
            )
            return None
        
        # Сопоставляем с нашими данными
        vacancy = self.map_huntflow_to_vacancy(hf_vacancy)
        grade = self.map_huntflow_to_grade(hf_vacancy)
        
        if not vacancy or not grade:
            # Создаем запись для ручного сопоставления
            sync_record = HuntflowSync.objects.create(
                huntflow_vacancy_id=vacancy_id,
                huntflow_applicant_id=applicant_id,
                entity_type='status_change',
                sync_status='pending',
                error_message='Manual mapping required: vacancy or grade not found',
                huntflow_data={
                    'vacancy': hf_vacancy,
                    'applicant': hf_applicant,
                    'log': log_data
                }
            )
            return None
        
        # Получаем дату найма из лога
        employment_date = log_data.get('employment_date')
        if employment_date:
            closed_date = datetime.strptime(employment_date, '%Y-%m-%d').date()
        else:
            closed_date = timezone.now().date()
        
        # Определяем дату открытия
        opening_date_str = hf_vacancy.get('created', '')
        if opening_date_str:
            opening_date = datetime.strptime(
                opening_date_str.split('T')[0], '%Y-%m-%d'
            ).date()
        else:
            opening_date = closed_date
        
        # Проект из division
        project = hf_vacancy.get('company', '')
        
        # Создаем HiringRequest
        hiring_request = HiringRequest.objects.create(
            vacancy=vacancy,
            grade=grade,
            project=project,
            priority=2,  # По умолчанию высокий
            status='closed',
            opening_reason='new_position',  # или определить из данных
            opening_date=opening_date,
            closed_date=closed_date,
            candidate_id=str(applicant_id),
            candidate_name=f"{hf_applicant.get('first_name', '')} {hf_applicant.get('last_name', '')}".strip(),
            notes=f"Синхронизировано из HuntFlow. Vacancy ID: {vacancy_id}"
        )
        
        # Создаем запись о синхронизации
        sync_record = HuntflowSync.objects.create(
            huntflow_vacancy_id=vacancy_id,
            huntflow_applicant_id=applicant_id,
            entity_type='status_change',
            hiring_request=hiring_request,
            sync_status='success',
            huntflow_data={
                'vacancy': hf_vacancy,
                'applicant': hf_applicant,
                'log': log_data
            },
            synced_at=timezone.now()
        )
        
        return hiring_request
    
    def sync_all_hired_for_vacancy(self, vacancy_id):
        """Синхронизировать всех нанятых кандидатов по вакансии"""
        
        # Получаем всех кандидатов вакансии
        applicants_data = self.get_vacancy_applicants(vacancy_id)
        
        if not applicants_data:
            return []
        
        hired_requests = []
        
        for applicant_item in applicants_data.get('items', []):
            applicant_id = applicant_item.get('id')
            
            # Получаем логи кандидата
            logs = self.get_applicant_logs(applicant_id)
            
            if not logs:
                continue
            
            # Ищем лог с hired статусом
            hired_log = None
            for log in logs.get('items', []):
                if log.get('type') == 'HIRED' or log.get('status', {}).get('name') == 'Hired':
                    hired_log = log
                    break
            
            if hired_log:
                request = self.sync_hired_applicant(
                    vacancy_id, applicant_id, hired_log
                )
                if request:
                    hired_requests.append(request)
        
        return hired_requests
    
    def bulk_sync_all_vacancies(self):
        """Массовая синхронизация всех вакансий"""
        
        # Получаем список всех вакансий
        vacancies_data = self._make_request('vacancies')
        
        if not vacancies_data:
            return
        
        for vacancy_item in vacancies_data.get('items', []):
            vacancy_id = vacancy_item.get('id')
            
            # Синхронизируем нанятых по каждой вакансии
            self.sync_all_hired_for_vacancy(vacancy_id)
```

---

## 🌐 WEBHOOK ОБРАБОТЧИК (опционально)

```python
# views.py

from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
import json

@csrf_exempt
@require_http_methods(["POST"])
def huntflow_webhook(request):
    """Webhook для получения событий из HuntFlow"""
    
    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    
    event = payload.get('event')
    
    # Событие "APPLICANT" с типом HIRED
    if event == 'APPLICANT':
        vacancy_id = payload.get('vacancy', {}).get('id')
        applicant_id = payload.get('applicant', {}).get('id')
        status = payload.get('status', {}).get('name')
        
        if status == 'Hired':
            # Запускаем синхронизацию
            sync_service = HuntflowSyncService()
            
            # Получаем данные лога
            log_data = payload.get('log', {})
            
            hiring_request = sync_service.sync_hired_applicant(
                vacancy_id, applicant_id, log_data
            )
            
            if hiring_request:
                return JsonResponse({
                    'status': 'success',
                    'hiring_request_id': hiring_request.id
                })
            else:
                return JsonResponse({
                    'status': 'pending',
                    'message': 'Manual mapping required'
                })
    
    return JsonResponse({'status': 'ignored'})
```

---

## 🔄 MANAGEMENT COMMAND ДЛЯ СИНХРОНИЗАЦИИ

```python
# management/commands/sync_huntflow.py

from django.core.management.base import BaseCommand
from hiring_plan.services.huntflow_sync_service import HuntflowSyncService

class Command(BaseCommand):
    help = 'Синхронизация закрытых вакансий из HuntFlow'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--vacancy-id',
            type=int,
            help='ID конкретной вакансии для синхронизации'
        )
        
        parser.add_argument(
            '--all',
            action='store_true',
            help='Синхронизировать все вакансии'
        )
    
    def handle(self, *args, **options):
        sync_service = HuntflowSyncService()
        
        if options['all']:
            self.stdout.write('Starting bulk sync...')
            sync_service.bulk_sync_all_vacancies()
            self.stdout.write(self.style.SUCCESS('Bulk sync completed'))
        
        elif options['vacancy_id']:
            vacancy_id = options['vacancy_id']
            self.stdout.write(f'Syncing vacancy {vacancy_id}...')
            requests = sync_service.sync_all_hired_for_vacancy(vacancy_id)
            self.stdout.write(
                self.style.SUCCESS(f'Synced {len(requests)} hired applicants')
            )
        
        else:
            self.stdout.write(self.style.ERROR('Specify --vacancy-id or --all'))
```

**Использование:**

```bash
# Синхронизировать конкретную вакансию
python manage.py sync_huntflow --vacancy-id 123

# Синхронизировать все вакансии
python manage.py sync_huntflow --all
```

---

## ⚙️ НАСТРОЙКИ (settings.py)

```python
# HuntFlow Integration
HUNTFLOW_API_TOKEN = env('HUNTFLOW_API_TOKEN', default='your_token_here')
HUNTFLOW_ACCOUNT_ID = env('HUNTFLOW_ACCOUNT_ID', default=11)
HUNTFLOW_WEBHOOK_SECRET = env('HUNTFLOW_WEBHOOK_SECRET', default='')
```

---

## 📋 АДМИНКА ДЛЯ HUNTFLOWSYNC

```python
@admin.register(HuntflowSync)
class HuntflowSyncAdmin(admin.ModelAdmin):
    list_display = [
        'huntflow_vacancy_id', 'huntflow_applicant_id',
        'entity_type', 'sync_status', 'hiring_request',
        'synced_at', 'created_at'
    ]
    list_filter = ['sync_status', 'entity_type', 'synced_at']
    search_fields = [
        'huntflow_vacancy_id', 'huntflow_applicant_id',
        'hiring_request__vacancy__name'
    ]
    readonly_fields = ['created_at', 'updated_at', 'synced_at']
    
    fieldsets = (
        ('HuntFlow IDs', {
            'fields': (
                'huntflow_vacancy_id', 'huntflow_applicant_id',
                'huntflow_log_id', 'entity_type'
            )
        }),
        ('Синхронизация', {
            'fields': (
                'hiring_request', 'sync_status', 'error_message'
            )
        }),
        ('Данные', {
            'fields': ('huntflow_data',),
            'classes': ('collapse',)
        }),
        ('Метаданные', {
            'fields': ('synced_at', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['retry_sync']
    
    def retry_sync(self, request, queryset):
        """Повторить синхронизацию для выбранных записей"""
        sync_service = HuntflowSyncService()
        
        for sync_record in queryset:
            if sync_record.sync_status == 'failed':
                # Повторяем синхронизацию
                log_data = sync_record.huntflow_data.get('log', {})
                
                hiring_request = sync_service.sync_hired_applicant(
                    sync_record.huntflow_vacancy_id,
                    sync_record.huntflow_applicant_id,
                    log_data
                )
                
                if hiring_request:
                    sync_record.sync_status = 'success'
                    sync_record.hiring_request = hiring_request
                    sync_record.synced_at = timezone.now()
                    sync_record.error_message = ''
                    sync_record.save()
        
        self.message_user(request, f"Повторно синхронизировано: {queryset.count()}")
    
    retry_sync.short_description = "Повторить синхронизацию"
```

---

## 📊 URL ROUTES

```python
# urls.py

urlpatterns = [
    # ... существующие URLs ...
    
    # HuntFlow webhook
    path('huntflow/webhook/', huntflow_webhook, name='huntflow_webhook'),
]
```

---

## 🔄 АВТОМАТИЗАЦИЯ (Celery задачи)

```python
# tasks.py

from celery import shared_task
from .services.huntflow_sync_service import HuntflowSyncService

@shared_task
def sync_huntflow_vacancies():
    """Периодическая синхронизация HuntFlow"""
    sync_service = HuntflowSyncService()
    sync_service.bulk_sync_all_vacancies()
    return "Sync completed"

@shared_task
def sync_huntflow_vacancy(vacancy_id):
    """Синхронизация конкретной вакансии"""
    sync_service = HuntflowSyncService()
    requests = sync_service.sync_all_hired_for_vacancy(vacancy_id)
    return f"Synced {len(requests)} requests"
```

**Celery Beat Schedule:**

```python
from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    'sync-huntflow-daily': {
        'task': 'hiring_plan.tasks.sync_huntflow_vacancies',
        'schedule': crontab(hour=2, minute=0),  # Каждый день в 2:00
    },
}
```

---

## ✅ ИТОГО: ПОЛНАЯ ИНТЕГРАЦИЯ

✅ **Модель HuntflowSync** — хранение истории синхронизации  
✅ **HuntflowSyncService** — полная логика синхронизации через API  
✅ **Маппинг данных** — автоматическое сопоставление Vacancy + Grade  
✅ **Webhook обработчик** — реал-тайм синхронизация при найме  
✅ **Management команда** — ручная синхронизация  
✅ **Celery задачи** — автоматическая периодическая синхронизация  
✅ **Админка** — управление и повторная синхронизация  

**Система готова к внедрению!** 🚀

### Следующие шаги:

1. Добавить `HUNTFLOW_API_TOKEN` в `.env`
2. Создать миграции: `python manage.py makemigrations`
3. Выполнить миграции: `python manage.py migrate`
4. Настроить webhook в HuntFlow (если используете)
5. Запустить первую синхронизацию: `python manage.py sync_huntflow --all`
