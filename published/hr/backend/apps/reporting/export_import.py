"""
Экспорт и импорт событий календаря отчётности (CalendarEvent) в JSON.

При импорте существующие записи перезаписываются по event_id (update_or_create).
"""
import logging
from django.utils import timezone

from .models import CalendarEvent
from apps.vacancies.models import Vacancy

logger = logging.getLogger(__name__)


def _event_to_dict(e):
    """Событие в словарь для JSON."""
    return {
        'event_id': e.event_id,
        'title': e.title,
        'event_type': e.event_type,
        'recruiter_username': e.recruiter.username if e.recruiter_id else None,
        'vacancy_external_id': e.vacancy.external_id if e.vacancy_id else None,
        'start_time': e.start_time.isoformat() if e.start_time else None,
        'end_time': e.end_time.isoformat() if e.end_time else None,
        'duration_minutes': e.duration_minutes,
        'attendees': e.attendees or [],
        'description': (e.description or '')[:5000],
        'location': e.location or '',
        'google_updated_at': e.google_updated_at.isoformat() if e.google_updated_at else None,
    }


def export_calendar_events_json():
    """Экспорт всех событий календаря в JSON-структуру."""
    qs = CalendarEvent.objects.select_related('recruiter', 'vacancy').order_by('-start_time')
    items = [_event_to_dict(e) for e in qs]
    return {
        'version': 1,
        'exported_at': timezone.now().isoformat(),
        'model': 'reporting.CalendarEvent',
        'calendar_events': items,
    }


def import_calendar_events_json(data):
    """
    Импорт событий календаря из JSON.
    Существующие записи перезаписываются по event_id (update_or_create).
    Возвращает (created_count, updated_count, errors).
    """
    from django.contrib.auth import get_user_model
    User = get_user_model()

    if not isinstance(data, dict) or 'calendar_events' not in data:
        return 0, 0, ['Неверный формат: ожидается объект с ключом "calendar_events"']

    created_count = 0
    updated_count = 0
    errors = []

    for i, item in enumerate(data['calendar_events']):
        if not isinstance(item, dict):
            errors.append(f'Запись {i + 1}: ожидается объект')
            continue

        event_id = item.get('event_id')
        if not event_id:
            errors.append(f'Запись {i + 1}: требуется event_id')
            continue

        recruiter_username = item.get('recruiter_username')
        recruiter = None
        if recruiter_username:
            recruiter = User.objects.filter(username=recruiter_username).first()
            if not recruiter:
                errors.append(f'Запись {i + 1}: пользователь "{recruiter_username}" не найден')
                continue

        vacancy = None
        vacancy_external_id = item.get('vacancy_external_id')
        if vacancy_external_id:
            vacancy = Vacancy.objects.filter(external_id=vacancy_external_id).first()

        start_time = item.get('start_time')
        end_time = item.get('end_time')
        if not start_time or not end_time:
            errors.append(f'Запись {i + 1}: требуются start_time и end_time')
            continue

        try:
            from dateutil.parser import parse as date_parse
            start_dt = date_parse(start_time)
            end_dt = date_parse(end_time)
            if timezone.is_naive(start_dt):
                start_dt = timezone.make_aware(start_dt)
            if timezone.is_naive(end_dt):
                end_dt = timezone.make_aware(end_dt)
        except Exception as e:
            errors.append(f'Запись {i + 1}: неверный формат даты — {e}')
            continue

        duration = int(item.get('duration_minutes', 0)) if item.get('duration_minutes') is not None else 0
        if duration <= 0 and start_dt and end_dt:
            duration = max(0, int((end_dt - start_dt).total_seconds() // 60))

        defaults = {
            'title': item.get('title') or '',
            'event_type': (item.get('event_type') or 'unknown') if item.get('event_type') in ('screening', 'interview', 'unknown') else 'unknown',
            'recruiter': recruiter,
            'vacancy': vacancy,
            'start_time': start_dt,
            'end_time': end_dt,
            'duration_minutes': duration,
            'attendees': item.get('attendees') if isinstance(item.get('attendees'), list) else [],
            'description': (item.get('description') or '')[:5000],
            'location': (item.get('location') or '')[:500],
        }
        if item.get('google_updated_at'):
            try:
                from dateutil.parser import parse as date_parse
                defaults['google_updated_at'] = date_parse(item['google_updated_at'])
                if timezone.is_naive(defaults['google_updated_at']):
                    defaults['google_updated_at'] = timezone.make_aware(defaults['google_updated_at'])
            except Exception:
                pass

        try:
            obj, created = CalendarEvent.objects.update_or_create(
                event_id=event_id,
                defaults=defaults,
            )
            if created:
                created_count += 1
            else:
                updated_count += 1
        except Exception as e:
            logger.exception('Ошибка импорта события календаря')
            errors.append(f'Запись {i + 1} ({event_id}): {e}')

    return created_count, updated_count, errors
