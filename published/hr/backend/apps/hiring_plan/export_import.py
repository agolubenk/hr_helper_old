"""
Экспорт и импорт заявок на найм (HiringRequest) и SLA (VacancySLA) в JSON.
"""
import logging
from django.utils import timezone

from .models import HiringRequest, VacancySLA
from apps.vacancies.models import Vacancy
from apps.finance.models import Grade

logger = logging.getLogger(__name__)


def _date_str(d):
    return d.isoformat() if d else None


def export_hiring_requests_json():
    """Экспорт всех заявок и SLA в структуру для JSON."""
    sla_list = []
    for s in VacancySLA.objects.select_related('vacancy', 'grade').order_by('vacancy__external_id', 'grade__name'):
        sla_list.append({
            'vacancy_external_id': s.vacancy.external_id,
            'grade_name': s.grade.name,
            'time_to_offer': s.time_to_offer,
            'time_to_hire': s.time_to_hire,
            'is_active': s.is_active,
        })

    requests_list = []
    for r in HiringRequest.objects.select_related('vacancy', 'grade', 'recruiter').order_by('-opening_date'):
        requests_list.append({
            'vacancy_external_id': r.vacancy.external_id,
            'grade_name': r.grade.name,
            'recruiter_username': r.recruiter.username if r.recruiter_id else None,
            'project': r.project or '',
            'priority': r.priority,
            'status': r.status,
            'opening_reason': r.opening_reason,
            'opening_date': _date_str(r.opening_date),
            'closed_date': _date_str(r.closed_date),
            'hire_date': _date_str(r.hire_date),
            'candidate_id': r.candidate_id or '',
            'candidate_name': r.candidate_name or '',
            'notes': r.notes or '',
        })

    return {
        'version': 1,
        'exported_at': timezone.now().isoformat(),
        'vacancy_sla': sla_list,
        'hiring_requests': requests_list,
    }


def import_hiring_requests_json(data):
    """
    Импорт SLA и заявок из JSON.
    data: dict с ключами 'vacancy_sla' и 'hiring_requests'.
    Возвращает (sla_created, sla_updated, requests_created, errors).
    """
    from django.contrib.auth import get_user_model
    User = get_user_model()

    sla_created = 0
    sla_updated = 0
    requests_created = 0
    errors = []

    # Импорт SLA
    for i, item in enumerate((data.get('vacancy_sla') or [])):
        if not isinstance(item, dict):
            continue
        vid = item.get('vacancy_external_id')
        gname = item.get('grade_name')
        if not vid or not gname:
            errors.append(f'SLA {i + 1}: нужны vacancy_external_id и grade_name')
            continue
        vacancy = Vacancy.objects.filter(external_id=vid).first()
        grade = Grade.objects.filter(name=gname).first()
        if not vacancy:
            errors.append(f'SLA {i + 1}: вакансия "{vid}" не найдена')
            continue
        if not grade:
            errors.append(f'SLA {i + 1}: грейд "{gname}" не найден')
            continue
        try:
            _, created = VacancySLA.objects.update_or_create(
                vacancy=vacancy,
                grade=grade,
                defaults={
                    'time_to_offer': int(item.get('time_to_offer', 30)),
                    'time_to_hire': int(item.get('time_to_hire', 60)),
                    'is_active': bool(item.get('is_active', True)),
                },
            )
            if created:
                sla_created += 1
            else:
                sla_updated += 1
        except Exception as e:
            errors.append(f'SLA {i + 1}: {e}')

    # Импорт заявок (только создание новых)
    for i, item in enumerate((data.get('hiring_requests') or [])):
        if not isinstance(item, dict):
            continue
        vid = item.get('vacancy_external_id')
        gname = item.get('grade_name')
        opening_date = item.get('opening_date')
        if not vid or not gname:
            errors.append(f'Заявка {i + 1}: нужны vacancy_external_id и grade_name')
            continue
        if not opening_date:
            errors.append(f'Заявка {i + 1}: нужна opening_date')
            continue
        vacancy = Vacancy.objects.filter(external_id=vid).first()
        grade = Grade.objects.filter(name=gname).first()
        if not vacancy:
            errors.append(f'Заявка {i + 1}: вакансия "{vid}" не найдена')
            continue
        if not grade:
            errors.append(f'Заявка {i + 1}: грейд "{gname}" не найден')
            continue
        recruiter = None
        if item.get('recruiter_username'):
            recruiter = User.objects.filter(username=item['recruiter_username']).first()
        try:
            from datetime import datetime
            open_d = datetime.fromisoformat(opening_date.replace('Z', '+00:00')).date() if isinstance(opening_date, str) else opening_date
            closed_d = None
            if item.get('closed_date'):
                closed_d = datetime.fromisoformat(item['closed_date'].replace('Z', '+00:00')).date() if isinstance(item['closed_date'], str) else item['closed_date']
            hire_d = None
            if item.get('hire_date'):
                hire_d = datetime.fromisoformat(item['hire_date'].replace('Z', '+00:00')).date() if isinstance(item['hire_date'], str) else item['hire_date']

            HiringRequest.objects.create(
                vacancy=vacancy,
                grade=grade,
                recruiter=recruiter,
                project=item.get('project') or '',
                priority=int(item.get('priority', 3)),
                opening_reason=item.get('opening_reason') or 'new_position',
                opening_date=open_d,
                closed_date=closed_d,
                hire_date=hire_d,
                candidate_id=item.get('candidate_id') or '',
                candidate_name=item.get('candidate_name') or '',
                notes=item.get('notes') or '',
            )
            requests_created += 1
        except Exception as e:
            logger.exception('Ошибка импорта заявки')
            errors.append(f'Заявка {i + 1}: {e}')

    return sla_created, sla_updated, requests_created, errors
