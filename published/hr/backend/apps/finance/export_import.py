"""
Экспорт и импорт зарплатных вилок (SalaryRange) в JSON.

Экспорт: все вилки с привязкой по vacancy.external_id и grade.name для импорта в другой инстанс.
Импорт: создание/обновление вилок по паре (vacancy_external_id, grade_name).
"""
import logging
from decimal import Decimal
from django.utils import timezone

from .models import SalaryRange, Grade
from apps.vacancies.models import Vacancy

logger = logging.getLogger(__name__)


def _serialize_decimal(value):
    if value is None:
        return None
    if isinstance(value, Decimal):
        return str(value)
    return value


def export_salary_ranges_json():
    """
    Экспорт всех зарплатных вилок в структуру для JSON.
    Возвращает dict с ключом 'salary_ranges'; каждая запись содержит
    vacancy_external_id, grade_name и данные вилки (без id вакансии/грейда).
    """
    qs = SalaryRange.objects.select_related('vacancy', 'grade').order_by('vacancy__external_id', 'grade__name')
    items = []
    for sr in qs:
        items.append({
            'vacancy_external_id': sr.vacancy.external_id,
            'grade_name': sr.grade.name,
            'salary_min_usd': _serialize_decimal(sr.salary_min_usd),
            'salary_max_usd': _serialize_decimal(sr.salary_max_usd),
            'is_active': sr.is_active,
        })
    return {
        'version': 1,
        'exported_at': timezone.now().isoformat(),
        'model': 'finance.SalaryRange',
        'salary_ranges': items,
    }


def import_salary_ranges_json(data):
    """
    Импорт зарплатных вилок из структуры JSON.
    data: dict с ключом 'salary_ranges' — список объектов с
    vacancy_external_id, grade_name, salary_min_usd, salary_max_usd, is_active.
    Создаёт или обновляет вилку по паре (vacancy_external_id, grade_name).
    Возвращает (created_count, updated_count, errors).
    """
    if not isinstance(data, dict) or 'salary_ranges' not in data:
        return 0, 0, ['Неверный формат: ожидается объект с ключом "salary_ranges"']

    created_count = 0
    updated_count = 0
    errors = []

    for i, item in enumerate(data['salary_ranges']):
        if not isinstance(item, dict):
            errors.append(f'Запись {i + 1}: ожидается объект')
            continue

        vacancy_external_id = item.get('vacancy_external_id')
        grade_name = item.get('grade_name')
        salary_min_usd = item.get('salary_min_usd')
        salary_max_usd = item.get('salary_max_usd')
        is_active = item.get('is_active', True)

        if not vacancy_external_id or not grade_name:
            errors.append(f'Запись {i + 1}: требуются vacancy_external_id и grade_name')
            continue

        try:
            vacancy = Vacancy.objects.filter(external_id=vacancy_external_id).first()
            if not vacancy:
                errors.append(f'Запись {i + 1}: вакансия с external_id="{vacancy_external_id}" не найдена')
                continue

            grade = Grade.objects.filter(name=grade_name).first()
            if not grade:
                errors.append(f'Запись {i + 1}: грейд с name="{grade_name}" не найден')
                continue
        except Exception as e:
            errors.append(f'Запись {i + 1}: {e}')
            continue

        if salary_min_usd is None and salary_max_usd is None:
            errors.append(f'Запись {i + 1}: укажите salary_min_usd и/или salary_max_usd')
            continue

        try:
            salary_min = Decimal(str(salary_min_usd)) if salary_min_usd is not None else None
            salary_max = Decimal(str(salary_max_usd)) if salary_max_usd is not None else None
            if salary_min is not None and salary_max is not None and salary_min > salary_max:
                errors.append(f'Запись {i + 1}: salary_min_usd не может быть больше salary_max_usd')
                continue
            if salary_min is None:
                salary_min = salary_max
            if salary_max is None:
                salary_max = salary_min
        except (TypeError, ValueError) as e:
            errors.append(f'Запись {i + 1}: неверный формат суммы — {e}')
            continue

        try:
            obj, created = SalaryRange.objects.update_or_create(
                vacancy=vacancy,
                grade=grade,
                defaults={
                    'salary_min_usd': salary_min,
                    'salary_max_usd': salary_max,
                    'is_active': bool(is_active),
                },
            )
            if created:
                created_count += 1
            else:
                updated_count += 1
        except Exception as e:
            logger.exception('Ошибка сохранения зарплатной вилки при импорте')
            errors.append(f'Запись {i + 1}: {e}')

    return created_count, updated_count, errors
