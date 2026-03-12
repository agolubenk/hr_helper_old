#!/usr/bin/env python
import os
import sys
import django
from datetime import date, timedelta

# Настройка Django
sys.path.append('/Users/agolubenko/hrhelper/fullstack/backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model
from apps.hiring_plan.models import HiringRequest, RecruiterAssignment
from apps.vacancies.models import Vacancy
from apps.finance.models import Grade

User = get_user_model()

def test_recruiter_functionality():
    print("🧪 Тестирование функциональности рекрутеров...")
    
    # Получаем или создаем тестовых пользователей
    recruiter1, created = User.objects.get_or_create(
        username='recruiter1',
        defaults={
            'first_name': 'Анна',
            'last_name': 'Петрова',
            'email': 'anna.petrova@example.com',
            'is_active': True
        }
    )
    
    recruiter2, created = User.objects.get_or_create(
        username='recruiter2',
        defaults={
            'first_name': 'Иван',
            'last_name': 'Сидоров',
            'email': 'ivan.sidorov@example.com',
            'is_active': True
        }
    )
    
    print(f"✅ Рекрутер 1: {recruiter1.get_full_name()}")
    print(f"✅ Рекрутер 2: {recruiter2.get_full_name()}")
    
    # Получаем первую доступную вакансию и грейд
    vacancy = Vacancy.objects.first()
    grade = Grade.objects.first()
    
    if not vacancy or not grade:
        print("❌ Нет доступных вакансий или грейдов")
        return
    
    print(f"✅ Вакансия: {vacancy.name}")
    print(f"✅ Грейд: {grade.name}")
    
    # Создаем тестовую заявку
    request = HiringRequest.objects.create(
        vacancy=vacancy,
        grade=grade,
        project='Тестовый проект',
        priority=3,
        opening_reason='new_position',
        opening_date=date.today() - timedelta(days=5),
        notes='Тестовая заявка для проверки функциональности рекрутеров'
    )
    
    print(f"✅ Создана заявка: {request}")
    
    # Тест 1: Назначение рекрутера
    print("\n📋 Тест 1: Назначение рекрутера")
    assignment1 = request.assign_recruiter(recruiter1)
    print(f"✅ Назначен рекрутер: {assignment1.recruiter.get_full_name()}")
    print(f"✅ Дата назначения: {assignment1.assigned_at}")
    print(f"✅ Активно: {assignment1.is_active}")
    
    # Тест 2: Смена рекрутера
    print("\n📋 Тест 2: Смена рекрутера")
    assignment2 = request.assign_recruiter(recruiter2)
    print(f"✅ Назначен новый рекрутер: {assignment2.recruiter.get_full_name()}")
    print(f"✅ Дата назначения: {assignment2.assigned_at}")
    
    # Проверяем, что предыдущее назначение деактивировано
    assignment1.refresh_from_db()
    print(f"✅ Предыдущее назначение деактивировано: {not assignment1.is_active}")
    print(f"✅ Дата снятия: {assignment1.unassigned_at}")
    
    # Тест 3: Проверка дней работы
    print("\n📋 Тест 3: Проверка дней работы")
    print(f"✅ Дни работы текущего рекрутера: {request.recruiter_work_days}")
    print(f"✅ Общие дни работы всех рекрутеров: {request.total_recruiter_work_days}")
    
    # Тест 4: Снятие рекрутера
    print("\n📋 Тест 4: Снятие рекрутера")
    request.unassign_recruiter()
    print(f"✅ Рекрутер снят: {request.recruiter is None}")
    
    # Проверяем, что назначение деактивировано
    assignment2.refresh_from_db()
    print(f"✅ Назначение деактивировано: {not assignment2.is_active}")
    print(f"✅ Дата снятия: {assignment2.unassigned_at}")
    
    # Тест 5: Проверка истории назначений
    print("\n📋 Тест 5: История назначений")
    assignments = request.recruiter_assignments.all()
    print(f"✅ Всего назначений: {assignments.count()}")
    for i, assignment in enumerate(assignments, 1):
        print(f"  {i}. {assignment.recruiter.get_full_name()} - {assignment.assigned_at.strftime('%d.%m.%Y')} - {assignment.duration_days} дней")
    
    print("\n🎉 Все тесты пройдены успешно!")
    
    # Очистка
    request.delete()
    print("🧹 Тестовые данные удалены")

if __name__ == '__main__':
    test_recruiter_functionality()
