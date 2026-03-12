from django.core.management.base import BaseCommand
from apps.hiring_plan.models import PositionType, PlanPeriodType


class Command(BaseCommand):
    help = 'Инициализация базовых данных для модуля Hiring Plan'

    def handle(self, *args, **options):
        self.stdout.write('Инициализация данных для Hiring Plan...')
        
        # Создаем типы позиций
        position_types_data = [
            {
                'type': 'current',
                'name': 'Текущая работа',
                'description': 'Обычная текущая работа',
                'priority_boost': 0,
                'is_active': True
            },
            {
                'type': 'replacement',
                'name': 'Замена сотрудника',
                'description': 'Замена уволившегося или уходящего сотрудника',
                'priority_boost': 2,
                'is_active': True
            },
            {
                'type': 'planned',
                'name': 'Плановая позиция',
                'description': 'Плановая позиция для развития команды',
                'priority_boost': 1,
                'is_active': True
            },
            {
                'type': 'urgent',
                'name': 'Срочная позиция',
                'description': 'Срочная позиция с высоким приоритетом',
                'priority_boost': 3,
                'is_active': True
            },
            {
                'type': 'potential',
                'name': 'Потенциальная позиция',
                'description': 'Потенциальная позиция для будущего развития',
                'priority_boost': 0,
                'is_active': True
            }
        ]
        
        for data in position_types_data:
            position_type, created = PositionType.objects.get_or_create(
                type=data['type'],
                defaults=data
            )
            if created:
                self.stdout.write(f'Создан тип позиции: {position_type.name}')
            else:
                self.stdout.write(f'Тип позиции уже существует: {position_type.name}')
        
        # Создаем типы периодов
        period_types_data = [
            {
                'period_type': 'monthly',
                'name': 'Месячный план',
                'days': 30,
                'is_active': True
            },
            {
                'period_type': 'quarterly',
                'name': 'Квартальный план',
                'days': 90,
                'is_active': True
            },
            {
                'period_type': 'yearly',
                'name': 'Годовой план',
                'days': 365,
                'is_active': True
            },
            {
                'period_type': 'custom',
                'name': 'Кастомный период',
                'days': 60,
                'is_active': True
            }
        ]
        
        for data in period_types_data:
            period_type, created = PlanPeriodType.objects.get_or_create(
                period_type=data['period_type'],
                defaults=data
            )
            if created:
                self.stdout.write(f'Создан тип периода: {period_type.name}')
            else:
                self.stdout.write(f'Тип периода уже существует: {period_type.name}')
        
        self.stdout.write(
            self.style.SUCCESS('Инициализация данных завершена успешно!')
        )