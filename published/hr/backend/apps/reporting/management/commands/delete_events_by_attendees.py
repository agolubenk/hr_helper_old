"""
Management команда для удаления событий календаря по участникам
Удаляет события, в которых есть определенные email адреса среди участников
"""
from django.core.management.base import BaseCommand
from apps.reporting.models import CalendarEvent


class Command(BaseCommand):
    help = 'Удаляет события календаря, в которых есть указанные email адреса среди участников'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Показать, что будет удалено, без фактического удаления',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        # Email адреса для поиска и удаления событий
        emails_to_find = [
            'andrei.golubenko@alfa-bank.by',
            'agolubenkoby@gmail.com',
        ]

        self.stdout.write('🔍 Поиск событий для удаления...')
        self.stdout.write(f'📋 Email адреса для поиска: {", ".join(emails_to_find)}')

        # Получаем все события
        all_events = CalendarEvent.objects.all()
        total_count = all_events.count()

        self.stdout.write(f'\n📊 Всего событий в базе: {total_count}')

        # Находим события, которые содержат хотя бы один из указанных email
        events_to_delete = []

        for event in all_events:
            attendees = event.attendees or []
            found_email = None
            
            # Проверяем всех участников
            for attendee in attendees:
                if isinstance(attendee, dict):
                    attendee_email = attendee.get('email', '').lower()
                elif isinstance(attendee, str):
                    attendee_email = attendee.lower()
                else:
                    continue
                
                # Проверяем, совпадает ли email с одним из искомых
                for email_to_find in emails_to_find:
                    if attendee_email == email_to_find.lower():
                        found_email = email_to_find
                        break
                
                if found_email:
                    break
            
            if found_email:
                events_to_delete.append((event, found_email))

        delete_count = len(events_to_delete)

        self.stdout.write(f'\n📈 Статистика:')
        self.stdout.write(f'   🗑️  Будет удалено: {delete_count} событий')

        if delete_count == 0:
            self.stdout.write(
                self.style.SUCCESS('\n✅ События с указанными email адресами не найдены.')
            )
            return

        # Показываем примеры событий, которые будут удалены
        self.stdout.write(f'\n📋 Примеры событий, которые будут удалены (первые 30):')
        for i, (event, found_email) in enumerate(events_to_delete[:30], 1):
            self.stdout.write(
                f'   {i}. "{event.title[:60]}{"..." if len(event.title) > 60 else ""}" '
                f'(найден: {found_email}, ID={event.id}, дата={event.start_time.date()}, рекрутер={event.recruiter.username if event.recruiter else "N/A"})'
            )

        if delete_count > 30:
            self.stdout.write(f'   ... и еще {delete_count - 30} событий')

        # Удаляем события
        if not dry_run:
            self.stdout.write(f'\n🗑️  Удаление событий...')
            
            # Удаляем пакетами для оптимизации
            batch_size = 1000
            deleted_total = 0
            
            event_ids = [event.id for event, _ in events_to_delete]
            
            for i in range(0, len(event_ids), batch_size):
                batch_ids = event_ids[i:i + batch_size]
                deleted_count, _ = CalendarEvent.objects.filter(id__in=batch_ids).delete()
                deleted_total += deleted_count
                self.stdout.write(f'   Удалено {deleted_total} из {delete_count} событий...')

            self.stdout.write(
                self.style.SUCCESS(
                    f'\n✅ Очистка завершена:\n'
                    f'   Удалено событий: {deleted_total}'
                )
            )
        else:
            self.stdout.write('\n' + '='*60)
            self.stdout.write(
                self.style.WARNING(
                    f'\n🔍 [DRY RUN] Режим проверки:\n'
                    f'   Будет удалено событий: {delete_count}\n'
                    f'\nДля фактического удаления запустите команду без флага --dry-run'
                )
            )
