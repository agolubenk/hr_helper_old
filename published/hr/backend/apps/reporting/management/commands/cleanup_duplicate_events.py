"""
Management команда для удаления дубликатов событий календаря по event_id
"""
from django.core.management.base import BaseCommand
from django.db.models import Count
from apps.reporting.models import CalendarEvent


class Command(BaseCommand):
    help = 'Удаляет дубликаты событий календаря, оставляя только одно событие для каждого уникального event_id'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Показать, что будет удалено, без фактического удаления',
        )
        parser.add_argument(
            '--keep-newest',
            action='store_true',
            default=True,
            help='Оставлять самое новое событие (по google_updated_at или created_at)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        keep_newest = options['keep_newest']

        self.stdout.write('🔍 Поиск дубликатов событий по event_id...')

        # Находим все event_id, которые встречаются более одного раза
        duplicates = (
            CalendarEvent.objects
            .values('event_id')
            .annotate(count=Count('event_id'))
            .filter(count__gt=1)
            .order_by('-count')
        )

        total_duplicates = duplicates.count()

        if total_duplicates == 0:
            self.stdout.write(
                self.style.SUCCESS('✅ Дубликатов не найдено. Все события уникальны.')
            )
            return

        self.stdout.write(
            self.style.WARNING(
                f'⚠️  Найдено {total_duplicates} дубликатов event_id'
            )
        )

        total_to_delete = 0
        total_to_keep = 0

        for dup_info in duplicates:
            event_id = dup_info['event_id']
            count = dup_info['count']
            
            # Получаем все события с этим event_id
            if keep_newest:
                # Оставляем самое новое событие (по google_updated_at или created_at)
                events = CalendarEvent.objects.filter(event_id=event_id).order_by(
                    '-google_updated_at',
                    '-created_at'
                )
            else:
                # Оставляем самое старое событие
                events = CalendarEvent.objects.filter(event_id=event_id).order_by(
                    'google_updated_at',
                    'created_at'
                )

            # Оставляем первое событие (самое новое или самое старое)
            event_to_keep = events.first()
            events_to_delete = events.exclude(pk=event_to_keep.pk)

            delete_count = events_to_delete.count()

            if delete_count > 0:
                self.stdout.write(
                    f'\n📋 event_id: {event_id[:50]}...'
                )
                self.stdout.write(
                    f'   Всего дубликатов: {count}, будет удалено: {delete_count}, останется: 1'
                )
                self.stdout.write(
                    f'   Оставляем событие: "{event_to_keep.title[:50]}..." '
                    f'(рекрутер: {event_to_keep.recruiter.username}, '
                    f'дата: {event_to_keep.start_time.date()})'
                )

                if not dry_run:
                    # Удаляем дубликаты
                    deleted_count, _ = events_to_delete.delete()
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'   ✅ Удалено {deleted_count} дубликатов'
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            f'   🔍 [DRY RUN] Будет удалено {delete_count} дубликатов'
                        )
                    )

                total_to_delete += delete_count
                total_to_keep += 1

        self.stdout.write('\n' + '='*60)
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f'\n🔍 [DRY RUN] Режим проверки:\n'
                    f'   Найдено дубликатов: {total_duplicates}\n'
                    f'   Будет удалено событий: {total_to_delete}\n'
                    f'   Останется событий: {total_to_keep}\n'
                    f'\nДля фактического удаления запустите команду без флага --dry-run'
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'\n✅ Очистка завершена:\n'
                    f'   Обработано дубликатов: {total_duplicates}\n'
                    f'   Удалено событий: {total_to_delete}\n'
                    f'   Оставлено событий: {total_to_keep}'
                )
            )

