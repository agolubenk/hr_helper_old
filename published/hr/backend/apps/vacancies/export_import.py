"""
Экспорт и импорт вакансий (Vacancy) в JSON.

Экспорт: все вакансии с recruiter_username, available_grade_names, interviewer_emails.
Импорт: создание/обновление по external_id; привязка по username, названиям грейдов, email интервьюеров.
"""
import logging
from django.utils import timezone

from .models import Vacancy
from apps.finance.models import Grade

logger = logging.getLogger(__name__)


def _vacancy_to_dict(v):
    """Сериализация одной вакансии в словарь для JSON."""
    return {
        'external_id': v.external_id,
        'name': v.name,
        'recruiter_username': v.recruiter.username if v.recruiter_id else None,
        'additional_recruiter_usernames': list(v.additional_recruiters.values_list('username', flat=True)),
        'invite_title': v.invite_title or '',
        'invite_text': v.invite_text or '',
        'scorecard_title': v.scorecard_title or '',
        'scorecard_link': v.scorecard_link or '',
        'questions_belarus': v.questions_belarus or '',
        'questions_poland': v.questions_poland or '',
        'vacancy_link_belarus': v.vacancy_link_belarus or '',
        'vacancy_link_poland': v.vacancy_link_poland or '',
        'candidate_update_prompt': v.candidate_update_prompt or '',
        'use_common_prompt': bool(v.use_common_prompt),
        'hr_screening_stage': v.hr_screening_stage or '',
        'tech_screening_stage': v.tech_screening_stage or '',
        'tech_interview_stage': v.tech_interview_stage or '',
        'screening_duration': int(v.screening_duration) if v.screening_duration else 45,
        'technologies': v.technologies or '',
        'tech_interview_duration': int(v.tech_interview_duration) if v.tech_interview_duration else None,
        'tech_invite_title': v.tech_invite_title or '',
        'tech_invite_text': v.tech_invite_text or '',
        'is_active': bool(v.is_active),
        'available_grade_names': [g.name for g in v.available_grades.all()],
        'interviewer_emails': list(v.interviewers.values_list('email', flat=True)),
        'mandatory_tech_interviewer_emails': list(v.mandatory_tech_interviewers.values_list('email', flat=True)),
    }


def export_vacancies_json():
    """Экспорт всех вакансий в структуру для JSON."""
    qs = Vacancy.objects.select_related('recruiter').prefetch_related(
        'available_grades', 'interviewers', 'mandatory_tech_interviewers', 'additional_recruiters'
    ).order_by('external_id')
    items = [_vacancy_to_dict(v) for v in qs]
    return {
        'version': 1,
        'exported_at': timezone.now().isoformat(),
        'model': 'vacancies.Vacancy',
        'vacancies': items,
    }


def import_vacancies_json(data):
    """
    Импорт вакансий из JSON.
    data: dict с ключом 'vacancies' — список объектов с полями как в экспорте.
    Создаёт/обновляет по external_id. Возвращает (created_count, updated_count, errors).
    """
    from django.contrib.auth import get_user_model
    from apps.interviewers.models import Interviewer

    User = get_user_model()

    if not isinstance(data, dict) or 'vacancies' not in data:
        return 0, 0, ['Неверный формат: ожидается объект с ключом "vacancies"']

    created_count = 0
    updated_count = 0
    errors = []

    for i, item in enumerate(data['vacancies']):
        if not isinstance(item, dict):
            errors.append(f'Запись {i + 1}: ожидается объект')
            continue

        external_id = item.get('external_id')
        if not external_id:
            errors.append(f'Запись {i + 1}: требуется external_id')
            continue

        recruiter_username = item.get('recruiter_username')
        if not recruiter_username:
            errors.append(f'Запись {i + 1}: требуется recruiter_username')
            continue

        recruiter = User.objects.filter(username=recruiter_username).first()
        if not recruiter:
            errors.append(f'Запись {i + 1}: пользователь "{recruiter_username}" не найден')
            continue

        name = item.get('name') or external_id
        defaults = {
            'name': name,
            'recruiter': recruiter,
            'invite_title': item.get('invite_title') or '',
            'invite_text': item.get('invite_text') or '',
            'scorecard_title': item.get('scorecard_title') or '',
            'scorecard_link': item.get('scorecard_link') or '',
            'questions_belarus': item.get('questions_belarus') or '',
            'questions_poland': item.get('questions_poland') or '',
            'vacancy_link_belarus': item.get('vacancy_link_belarus') or '',
            'vacancy_link_poland': item.get('vacancy_link_poland') or '',
            'candidate_update_prompt': item.get('candidate_update_prompt') or '',
            'use_common_prompt': bool(item.get('use_common_prompt', False)),
            'hr_screening_stage': item.get('hr_screening_stage') or '',
            'tech_screening_stage': item.get('tech_screening_stage') or '',
            'tech_interview_stage': item.get('tech_interview_stage') or '',
            'screening_duration': int(item.get('screening_duration', 45)) if item.get('screening_duration') is not None else 45,
            'technologies': item.get('technologies') or '',
            'tech_interview_duration': int(item['tech_interview_duration']) if item.get('tech_interview_duration') is not None else None,
            'tech_invite_title': item.get('tech_invite_title') or '',
            'tech_invite_text': item.get('tech_invite_text') or '',
            'is_active': bool(item.get('is_active', True)),
        }

        additional_usernames = item.get('additional_recruiter_usernames') or []
        additional_recruiters = list(User.objects.filter(username__in=additional_usernames))

        try:
            vacancy, created = Vacancy.objects.update_or_create(
                external_id=external_id,
                defaults=defaults,
            )
            if created:
                created_count += 1
            else:
                updated_count += 1

            grade_names = item.get('available_grade_names') or []
            grades = list(Grade.objects.filter(name__in=grade_names))
            vacancy.available_grades.set(grades)

            emails = item.get('interviewer_emails') or []
            interviewers = list(Interviewer.objects.filter(email__in=emails))
            vacancy.interviewers.set(interviewers)

            mandatory_emails = item.get('mandatory_tech_interviewer_emails') or []
            mandatory = list(Interviewer.objects.filter(email__in=mandatory_emails))
            vacancy.mandatory_tech_interviewers.set(mandatory)

            vacancy.additional_recruiters.set(additional_recruiters)

        except Exception as e:
            logger.exception('Ошибка импорта вакансии')
            errors.append(f'Запись {i + 1} ({external_id}): {e}')

    return created_count, updated_count, errors
