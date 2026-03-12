"""
Management команда для исправления назначений рекрутеров для событий

Исправляет:
1. Все события до 15 января 2025 года включительно - закрепляет за рекрутером admin
2. Все события до 10 июля, где единственный интервьюер - Koipash Alena - закрепляет за рекрутером admin
3. Все события с рекрутером andrei.golubenko до 10 июля включительно - закрепляет за рекрутером admin
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import datetime
from apps.reporting.models import CalendarEvent
from apps.interviewers.models import Interviewer

User = get_user_model()


class Command(BaseCommand):
    help = 'Исправляет назначения рекрутеров для событий по заданным правилам'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Показать, что будет обновлено, без фактического обновления',
        )
        parser.add_argument(
            '--july-year',
            type=int,
            default=2025,
            help='Год для даты 10 июля (по умолчанию 2025)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        july_year = options['july_year']

        self.stdout.write('='*60)
        self.stdout.write(self.style.SUCCESS('🔧 Исправление назначений рекрутеров для событий'))
        self.stdout.write('='*60)

        # Находим рекрутера admin
        try:
            admin_recruiter = User.objects.get(username='admin')
            if not admin_recruiter.groups.filter(name='Рекрутер').exists():
                self.stdout.write(
                    self.style.WARNING(
                        f'⚠️  Пользователь admin не является рекрутером, но продолжим...'
                    )
                )
        except User.DoesNotExist:
            self.stdout.write(
                self.style.ERROR('❌ Пользователь admin не найден')
            )
            return

        self.stdout.write(f'\n👤 Рекрутер admin найден: {admin_recruiter.get_full_name() or admin_recruiter.username}')

        # Находим рекрутера andrei.golubenko
        try:
            andrei_golubenko_recruiter = User.objects.get(username='andrei.golubenko')
            self.stdout.write(f'👤 Рекрутер andrei.golubenko найден: {andrei_golubenko_recruiter.get_full_name() or andrei_golubenko_recruiter.username}')
        except User.DoesNotExist:
            self.stdout.write(
                self.style.WARNING(
                    '\n⚠️  Пользователь andrei.golubenko не найден. '
                    'Пропускаем правило для событий с этим рекрутером.'
                )
            )
            andrei_golubenko_recruiter = None

        # Находим интервьюера Koipash Alena
        interviewer = None
        try:
            # Пробуем найти по имени и фамилии
            interviewer = Interviewer.objects.filter(
                first_name__icontains='Alena',
                last_name__icontains='Koipash'
            ).first()
            
            if not interviewer:
                # Пробуем найти по email (из логов видно alena.koipash@softnetix.io)
                interviewer = Interviewer.objects.filter(
                    email__icontains='alena.koipash'
                ).first()
            
            if interviewer:
                self.stdout.write(
                    f'\n👤 Интервьюер найден: {interviewer.get_full_name()} ({interviewer.email})'
                )
            else:
                self.stdout.write(
                    self.style.WARNING(
                        '\n⚠️  Интервьюер Koipash Alena не найден. '
                        'Пропускаем правило для событий с единственным интервьюером.'
                    )
                )
        except Exception as e:
            self.stdout.write(
                self.style.WARNING(
                    f'\n⚠️  Ошибка при поиске интервьюера: {e}'
                )
            )

        # Правило 1: События до 15 января 2025 года включительно
        self.stdout.write('\n' + '='*60)
        self.stdout.write('📅 Правило 1: События до 15 января 2025 года включительно')
        self.stdout.write('='*60)
        
        cutoff_date_1 = datetime(2025, 1, 15, 23, 59, 59, tzinfo=timezone.utc)
        events_rule_1 = CalendarEvent.objects.filter(
            start_time__lte=cutoff_date_1
        ).exclude(recruiter=admin_recruiter)
        
        count_rule_1 = events_rule_1.count()
        self.stdout.write(f'\n📊 Найдено событий для обновления (правило 1): {count_rule_1}')
        
        if count_rule_1 > 0:
            self.stdout.write(f'\n📋 Примеры событий (первые 10):')
            for i, event in enumerate(events_rule_1[:10], 1):
                self.stdout.write(
                    f'   {i}. "{event.title[:60]}{"..." if len(event.title) > 60 else ""}" '
                    f'(ID={event.id}, текущий рекрутер={event.recruiter.username}, '
                    f'дата={event.start_time.date()})'
                )
            if count_rule_1 > 10:
                self.stdout.write(f'   ... и еще {count_rule_1 - 10} событий')

        # Правило 2: События до 10 июля, где единственный интервьюер - Koipash Alena
        events_rule_2 = []
        if interviewer:
            self.stdout.write('\n' + '='*60)
            self.stdout.write(f'📅 Правило 2: События до 10 июля {july_year}, где единственный интервьюер - {interviewer.get_full_name()}')
            self.stdout.write('='*60)
            
            cutoff_date_2 = datetime(july_year, 7, 10, 23, 59, 59, tzinfo=timezone.utc)
            all_events_rule_2 = CalendarEvent.objects.filter(
                start_time__lte=cutoff_date_2
            ).exclude(recruiter=admin_recruiter)
            
            interviewer_email_lower = interviewer.email.lower()
            
            for event in all_events_rule_2:
                attendees = event.attendees or []
                if not attendees:
                    continue
                
                # Считаем количество интервьюеров среди участников
                interviewer_count = 0
                found_target_interviewer = False
                
                for attendee in attendees:
                    if isinstance(attendee, dict):
                        attendee_email = attendee.get('email', '').lower()
                    elif isinstance(attendee, str):
                        attendee_email = attendee.lower()
                    else:
                        continue
                    
                    if not attendee_email:
                        continue
                    
                    # Проверяем, является ли участник интервьюером
                    try:
                        attendee_interviewer = Interviewer.objects.filter(
                            email__iexact=attendee_email,
                            is_active=True
                        ).first()
                        
                        if attendee_interviewer:
                            interviewer_count += 1
                            if attendee_email == interviewer_email_lower:
                                found_target_interviewer = True
                    except:
                        pass
                
                # Если единственный интервьюер - это наш целевой интервьюер
                if found_target_interviewer and interviewer_count == 1:
                    events_rule_2.append(event)
            
            count_rule_2 = len(events_rule_2)
            self.stdout.write(f'\n📊 Найдено событий для обновления (правило 2): {count_rule_2}')
            
            if count_rule_2 > 0:
                self.stdout.write(f'\n📋 Примеры событий (первые 10):')
                for i, event in enumerate(events_rule_2[:10], 1):
                    self.stdout.write(
                        f'   {i}. "{event.title[:60]}{"..." if len(event.title) > 60 else ""}" '
                        f'(ID={event.id}, текущий рекрутер={event.recruiter.username}, '
                        f'дата={event.start_time.date()})'
                    )
                if count_rule_2 > 10:
                    self.stdout.write(f'   ... и еще {count_rule_2 - 10} событий')
        else:
            self.stdout.write('\n⚠️  Правило 2 пропущено (интервьюер не найден)')

        # Правило 3: События с рекрутером andrei.golubenko до 10 июля включительно
        events_rule_3 = []
        if andrei_golubenko_recruiter:
            self.stdout.write('\n' + '='*60)
            self.stdout.write(f'📅 Правило 3: События с рекрутером andrei.golubenko до 10 июля {july_year} включительно')
            self.stdout.write('='*60)
            
            cutoff_date_3 = datetime(july_year, 7, 10, 23, 59, 59, tzinfo=timezone.utc)
            events_rule_3_queryset = CalendarEvent.objects.filter(
                recruiter=andrei_golubenko_recruiter,
                start_time__lte=cutoff_date_3
            )
            
            count_rule_3 = events_rule_3_queryset.count()
            events_rule_3 = list(events_rule_3_queryset)
            self.stdout.write(f'\n📊 Найдено событий для обновления (правило 3): {count_rule_3}')
            
            if count_rule_3 > 0:
                self.stdout.write(f'\n📋 Примеры событий (первые 10):')
                for i, event in enumerate(events_rule_3[:10], 1):
                    self.stdout.write(
                        f'   {i}. "{event.title[:60]}{"..." if len(event.title) > 60 else ""}" '
                        f'(ID={event.id}, текущий рекрутер={event.recruiter.username}, '
                        f'дата={event.start_time.date()})'
                    )
                if count_rule_3 > 10:
                    self.stdout.write(f'   ... и еще {count_rule_3 - 10} событий')
        else:
            self.stdout.write('\n⚠️  Правило 3 пропущено (рекрутер andrei.golubenko не найден)')

        # Объединяем события для обновления (убираем дубликаты)
        all_events_to_update = list(set(events_rule_1) | set(events_rule_2) | set(events_rule_3))
        total_count = len(all_events_to_update)

        self.stdout.write('\n' + '='*60)
        self.stdout.write(f'📊 ИТОГО: Событий для обновления: {total_count}')
        self.stdout.write('='*60)

        if total_count == 0:
            self.stdout.write(
                self.style.SUCCESS(
                    '\n✅ Нет событий для обновления. Все события уже имеют правильного рекрутера.'
                )
            )
            return

        # Обновляем события
        if not dry_run:
            self.stdout.write(f'\n🔄 Обновление событий...')
            
            updated_count = 0
            for event in all_events_to_update:
                event.recruiter = admin_recruiter
                event.save()
                updated_count += 1
                
                if updated_count % 100 == 0:
                    self.stdout.write(f'   Обновлено {updated_count} из {total_count} событий...')

            self.stdout.write(
                self.style.SUCCESS(
                    f'\n✅ Обновление завершено:\n'
                    f'   Обновлено событий: {updated_count}\n'
                    f'   Новый рекрутер: {admin_recruiter.get_full_name() or admin_recruiter.username} ({admin_recruiter.email})'
                )
            )
        else:
            self.stdout.write('\n' + '='*60)
            self.stdout.write(
                self.style.WARNING(
                    f'\n🔍 [DRY RUN] Режим проверки:\n'
                    f'   Будет обновлено событий: {total_count}\n'
                    f'   Новый рекрутер: {admin_recruiter.get_full_name() or admin_recruiter.username} ({admin_recruiter.email})\n'
                    f'\nДля фактического обновления запустите команду без флага --dry-run'
                )
            )

