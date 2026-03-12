"""
Management команда для обновления рекрутера событий по участникам
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.reporting.models import CalendarEvent

User = get_user_model()


class Command(BaseCommand):
    help = 'Обновляет рекрутера событий по email участника'

    def add_arguments(self, parser):
        parser.add_argument(
            '--attendee-email',
            type=str,
            required=True,
            help='Email участника для поиска событий',
        )
        parser.add_argument(
            '--recruiter-username',
            type=str,
            required=True,
            help='Username рекрутера для установки',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Показать, что будет обновлено, без фактического обновления',
        )

    def handle(self, *args, **options):
        attendee_email = options['attendee_email'].lower().strip()
        recruiter_username = options['recruiter_username']
        dry_run = options['dry_run']

        self.stdout.write(f'🔍 Поиск событий с участником: {attendee_email}')
        self.stdout.write(f'👤 Новый рекрутер: {recruiter_username}')

        # Находим рекрутера
        try:
            recruiter = User.objects.get(username=recruiter_username)
            if not recruiter.groups.filter(name='Рекрутер').exists():
                self.stdout.write(
                    self.style.WARNING(
                        f'⚠️  Пользователь {recruiter_username} не является рекрутером'
                    )
                )
        except User.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'❌ Пользователь {recruiter_username} не найден')
            )
            return

        # Находим все события
        all_events = CalendarEvent.objects.all()
        events_to_update = []

        for event in all_events:
            attendees = event.attendees or []
            # Проверяем, есть ли среди участников нужный email
            for attendee in attendees:
                attendee_email_lower = (attendee.get('email', '') or '').lower().strip()
                if attendee_email_lower == attendee_email:
                    # Если текущий рекрутер отличается от нужного, добавляем в список
                    if event.recruiter != recruiter:
                        events_to_update.append(event)
                    break

        update_count = len(events_to_update)

        if update_count == 0:
            self.stdout.write(
                self.style.SUCCESS(
                    f'\n✅ События с участником {attendee_email} не найдены '
                    f'или уже имеют правильного рекрутера.'
                )
            )
            return

        self.stdout.write(f'\n📊 Найдено событий для обновления: {update_count}')

        # Показываем примеры событий
        self.stdout.write(f'\n📋 Примеры событий, которые будут обновлены (первые 20):')
        for i, event in enumerate(events_to_update[:20], 1):
            self.stdout.write(
                f'   {i}. "{event.title[:60]}{"..." if len(event.title) > 60 else ""}" '
                f'(ID={event.id}, текущий рекрутер={event.recruiter.username}, '
                f'дата={event.start_time.date()})'
            )

        if update_count > 20:
            self.stdout.write(f'   ... и еще {update_count - 20} событий')

        # Обновляем события
        if not dry_run:
            self.stdout.write(f'\n🔄 Обновление событий...')
            
            updated_count = 0
            for event in events_to_update:
                event.recruiter = recruiter
                event.save()
                updated_count += 1
                
                if updated_count % 100 == 0:
                    self.stdout.write(f'   Обновлено {updated_count} из {update_count} событий...')

            self.stdout.write(
                self.style.SUCCESS(
                    f'\n✅ Обновление завершено:\n'
                    f'   Обновлено событий: {updated_count}\n'
                    f'   Новый рекрутер: {recruiter.get_full_name() or recruiter.username} ({recruiter.email})'
                )
            )
        else:
            self.stdout.write('\n' + '='*60)
            self.stdout.write(
                self.style.WARNING(
                    f'\n🔍 [DRY RUN] Режим проверки:\n'
                    f'   Будет обновлено событий: {update_count}\n'
                    f'   Новый рекрутер: {recruiter.get_full_name() or recruiter.username} ({recruiter.email})\n'
                    f'\nДля фактического обновления запустите команду без флага --dry-run'
                )
            )

