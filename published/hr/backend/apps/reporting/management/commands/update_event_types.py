"""
Management команда для обновления типов событий на основе названий
"""
from django.core.management.base import BaseCommand
from apps.reporting.models import CalendarEvent


class Command(BaseCommand):
    help = 'Обновляет типы событий на основе их названий'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Показать статистику без фактического обновления',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        self.stdout.write('🔍 Обновление типов событий на основе названий...')

        all_events = CalendarEvent.objects.all()
        total_count = all_events.count()

        self.stdout.write(f'\n📊 Всего событий в базе: {total_count}')

        stats = {
            'screening': 0,
            'interview': 0,
            'unknown': 0,
            'updated': 0,
        }

        for event in all_events:
            old_type = event.event_type
            new_type = event.determine_event_type()
            
            stats[new_type] = stats.get(new_type, 0) + 1
            
            if old_type != new_type:
                stats['updated'] += 1
                if not dry_run:
                    event.event_type = new_type
                    event.save(update_fields=['event_type'])

        self.stdout.write(f'\n📈 Статистика типов событий:')
        self.stdout.write(f'   ✅ Скрининги: {stats["screening"]}')
        self.stdout.write(f'   ✅ Интервью: {stats["interview"]}')
        self.stdout.write(f'   ⚠️  Не определено: {stats["unknown"]}')
        self.stdout.write(f'   🔄 Обновлено: {stats["updated"]}')

        if dry_run:
            self.stdout.write('\n' + '='*60)
            self.stdout.write(
                self.style.WARNING(
                    f'\n🔍 [DRY RUN] Режим проверки:\n'
                    f'   Будет обновлено событий: {stats["updated"]}\n'
                    f'\nДля фактического обновления запустите команду без флага --dry-run'
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'\n✅ Обновление завершено!\n'
                    f'   Обновлено событий: {stats["updated"]}'
                )
            )







