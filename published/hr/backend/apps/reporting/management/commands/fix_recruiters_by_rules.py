"""
Management команда для исправления рекрутеров по правилам
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import datetime
from apps.reporting.models import CalendarEvent
from apps.interviewers.models import Interviewer

User = get_user_model()


class Command(BaseCommand):
    help = 'Исправляет рекрутеров для событий по заданным правилам'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Показать, что будет изменено, без фактического изменения',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        # Email адреса для проверки
        alena_email = 'alena.koipash@softnetix.io'
        chernomordin_email = 'andrey.chernomordin@softnetix.io'
        
        # Дата отсечения: 9 июля включительно (до конца дня)
        cutoff_date = datetime(2025, 7, 9, 23, 59, 59)
        if timezone.is_naive(cutoff_date):
            cutoff_date = timezone.make_aware(cutoff_date)

        self.stdout.write('🔍 Поиск событий для обновления рекрутеров...')
        self.stdout.write(f'📅 Дата отсечения: до {cutoff_date.date()} включительно')

        # Находим интервьюера Koipash Alena
        try:
            alena_interviewer = Interviewer.objects.filter(
                email__iexact=alena_email
            ).first()
            
            if not alena_interviewer:
                # Пробуем найти по имени
                alena_interviewer = Interviewer.objects.filter(
                    first_name__icontains='Alena',
                    last_name__icontains='Koipash'
                ).first()
            
            if alena_interviewer:
                self.stdout.write(f'✅ Найден интервьюер: {alena_interviewer.get_full_name()} ({alena_interviewer.email})')
            else:
                self.stdout.write(
                    self.style.WARNING(f'⚠️  Интервьюер Koipash Alena не найден')
                )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Ошибка при поиске интервьюера: {e}')
            )
            return

        # Находим пользователей
        try:
            admin_user = User.objects.filter(username='admin').first()
            if not admin_user:
                # Пробуем найти по email или полному имени
                admin_user = User.objects.filter(
                    email__icontains='admin'
                ).first() or User.objects.filter(
                    first_name__icontains='Alena',
                    last_name__icontains='Koipash'
                ).first()
            
            # Ищем пользователя andrey.chernomordin разными способами
            chernomordin_user = None
            if chernomordin_email:
                chernomordin_user = User.objects.filter(
                    email__iexact=chernomordin_email
                ).first()
            
            if not chernomordin_user:
                chernomordin_user = User.objects.filter(
                    username__icontains='chernomordin'
                ).first()
            
            if not chernomordin_user:
                chernomordin_user = User.objects.filter(
                    first_name__icontains='Andrey',
                    last_name__icontains='Chernomordin'
                ).first()
            
            if not admin_user:
                self.stdout.write(
                    self.style.ERROR('❌ Пользователь admin не найден')
                )
                return
            
            if not chernomordin_user:
                self.stdout.write(
                    self.style.WARNING('⚠️  Пользователь andrey.chernomordin не найден. Правило 2 (Backend) не будет применено.')
                )
            
            self.stdout.write(f'✅ Найден пользователь admin: {admin_user.get_full_name() or admin_user.username} ({admin_user.email or admin_user.username})')
            if chernomordin_user:
                self.stdout.write(f'✅ Найден пользователь chernomordin: {chernomordin_user.get_full_name() or chernomordin_user.username} ({chernomordin_user.email or chernomordin_user.username})')
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Ошибка при поиске пользователей: {e}')
            )
            return

        # Находим пользователя andrei.golubenko
        golubenko_user = None
        golubenko_emails = [
            'andrei.golubenko@softnetix.io',
            'agolubenkoby@gmail.com',
            'andrei.golubenko@alfa-bank.by',
        ]
        
        for email in golubenko_emails:
            golubenko_user = User.objects.filter(email__iexact=email).first()
            if golubenko_user:
                break
        
        if not golubenko_user:
            golubenko_user = User.objects.filter(username__icontains='golubenko').first()
        
        if not golubenko_user:
            self.stdout.write(
                self.style.ERROR('❌ Пользователь andrei.golubenko не найден')
            )
            return
        
        self.stdout.write(f'✅ Найден пользователь golubenko: {golubenko_user.get_full_name() or golubenko_user.username} ({golubenko_user.email or golubenko_user.username})')

        # Получаем все события до 9 июля включительно, где рекрутер = andrei.golubenko
        events = CalendarEvent.objects.filter(
            start_time__lte=cutoff_date,
            recruiter=golubenko_user
        ).select_related('recruiter', 'vacancy')

        total_count = events.count()
        self.stdout.write(f'\n📊 Всего событий до {cutoff_date.date()} с рекрутером {golubenko_user.username}: {total_count}')

        # Статистика изменений
        stats = {
            'rule1_alena': 0,  # События с Alena Koipash -> admin
            'rule2_frontend': 0,  # Frontend без указанных email -> admin
            'rule2_backend': 0,  # Backend без указанных email -> chernomordin
            'remove_recruiter': 0,  # Убрать рекрутера (NULL)
        }

        events_to_update = []

        for event in events:
            attendees = event.attendees or []
            attendee_emails = []
            
            # Собираем email участников
            for attendee in attendees:
                if isinstance(attendee, dict):
                    email = attendee.get('email', '').lower()
                elif isinstance(attendee, str):
                    email = attendee.lower()
                else:
                    continue
                if email:
                    attendee_emails.append(email)
            
            new_recruiter = None
            rule_applied = None
            remove_recruiter = False
            
            # Правило 1: Если среди участников есть Koipash Alena -> admin
            if alena_interviewer and alena_interviewer.email.lower() in attendee_emails:
                new_recruiter = admin_user
                rule_applied = 'rule1_alena'
            
            # Правило 2: Если нет andrey.chernomordin@softnetix.io или alena.koipash@softnetix.io
            elif chernomordin_email.lower() not in attendee_emails and alena_email.lower() not in attendee_emails:
                if event.vacancy:
                    vacancy_name = event.vacancy.name or ''
                    vacancy_name_lower = vacancy_name.lower()
                    
                    # Проверяем Frontend
                    if 'frontend' in vacancy_name_lower:
                        new_recruiter = admin_user
                        rule_applied = 'rule2_frontend'
                    # Проверяем Backend
                    elif 'backend' in vacancy_name_lower or 'back-end' in vacancy_name_lower:
                        if chernomordin_user:
                            new_recruiter = chernomordin_user
                            rule_applied = 'rule2_backend'
                        else:
                            # Если chernomordin не найден, убираем рекрутера
                            remove_recruiter = True
                            rule_applied = 'remove_recruiter'
                else:
                    # Если нет вакансии, убираем рекрутера
                    remove_recruiter = True
                    rule_applied = 'remove_recruiter'
            else:
                # Если есть один из указанных email, но не Alena Koipash, убираем рекрутера
                remove_recruiter = True
                rule_applied = 'remove_recruiter'
            
            # Если нужно изменить рекрутера
            if new_recruiter and event.recruiter != new_recruiter:
                events_to_update.append((event, new_recruiter, rule_applied, False))
                stats[rule_applied] = stats.get(rule_applied, 0) + 1
            elif remove_recruiter:
                events_to_update.append((event, None, rule_applied, True))
                stats[rule_applied] = stats.get(rule_applied, 0) + 1

        # Выводим статистику
        self.stdout.write(f'\n📈 Статистика изменений:')
        self.stdout.write(f'   📌 Правило 1 (с Alena Koipash -> admin): {stats["rule1_alena"]}')
        self.stdout.write(f'   📌 Правило 2 (Frontend без указанных email -> admin): {stats["rule2_frontend"]}')
        self.stdout.write(f'   📌 Правило 2 (Backend без указанных email -> chernomordin): {stats["rule2_backend"]}')
        self.stdout.write(f'   🗑️  Убрать рекрутера (NULL): {stats["remove_recruiter"]}')

        if not events_to_update:
            self.stdout.write(
                self.style.SUCCESS('\n✅ Нет событий для обновления.')
            )
            return

        # Показываем примеры
        self.stdout.write(f'\n📋 Примеры событий, которые будут обновлены (первые 20):')
        for i, (event, new_recruiter, rule, is_remove) in enumerate(events_to_update[:20], 1):
            rule_name = {
                'rule1_alena': 'Правило 1 (Alena Koipash)',
                'rule2_frontend': 'Правило 2 (Frontend)',
                'rule2_backend': 'Правило 2 (Backend)',
                'remove_recruiter': 'Убрать рекрутера',
            }.get(rule, rule)
            
            if is_remove:
                recruiter_text = 'NULL (убрать)'
            else:
                recruiter_text = new_recruiter.get_full_name() or new_recruiter.username
            
            self.stdout.write(
                f'   {i}. "{event.title[:50]}{"..." if len(event.title) > 50 else ""}" '
                f'({rule_name}) -> {recruiter_text}'
            )

        if len(events_to_update) > 20:
            self.stdout.write(f'   ... и еще {len(events_to_update) - 20} событий')

        # Применяем изменения
        if not dry_run:
            self.stdout.write(f'\n🔄 Обновление рекрутеров...')
            
            # Проверяем, можно ли установить NULL для recruiter
            from django.db import connection
            recruiter_field = CalendarEvent._meta.get_field('recruiter')
            can_be_null = recruiter_field.null
            
            if not can_be_null:
                self.stdout.write(
                    self.style.WARNING(
                        '\n⚠️  ВНИМАНИЕ: Поле recruiter не может быть NULL в модели.\n'
                        '   События, которые должны остаться без рекрутера, будут пропущены.\n'
                        '   Для установки NULL необходимо сначала сделать миграцию.\n'
                    )
                )
            
            updated_count = 0
            skipped_count = 0
            
            for event, new_recruiter, rule, is_remove in events_to_update:
                if is_remove:
                    if can_be_null:
                        event.recruiter = None
                        event.save(update_fields=['recruiter'])
                        updated_count += 1
                    else:
                        skipped_count += 1
                        self.stdout.write(
                            self.style.WARNING(
                                f'   ⚠️  Пропущено событие "{event.title[:50]}": '
                                f'нельзя установить NULL (требуется миграция)'
                            )
                        )
                else:
                    event.recruiter = new_recruiter
                    event.save(update_fields=['recruiter'])
                    updated_count += 1
                
                if updated_count % 100 == 0:
                    self.stdout.write(f'   Обновлено {updated_count} из {len(events_to_update)} событий...')

            result_msg = f'\n✅ Обновление завершено:\n   Обновлено событий: {updated_count}'
            if skipped_count > 0:
                result_msg += f'\n   Пропущено событий (требуется миграция): {skipped_count}'
            
            self.stdout.write(self.style.SUCCESS(result_msg))
        else:
            self.stdout.write('\n' + '='*60)
            self.stdout.write(
                self.style.WARNING(
                    f'\n🔍 [DRY RUN] Режим проверки:\n'
                    f'   Будет обновлено событий: {len(events_to_update)}\n'
                    f'\nДля фактического обновления запустите команду без флага --dry-run'
                )
            )
