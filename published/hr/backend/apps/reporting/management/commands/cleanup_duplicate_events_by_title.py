"""
Management команда для удаления дубликатов событий календаря по названию (title)
Оставляет только одно событие - самое последнее по дате начала (start_time)
"""
from django.core.management.base import BaseCommand
from django.db.models import Count, Min
from apps.reporting.models import CalendarEvent


class Command(BaseCommand):
    help = 'Удаляет дубликаты событий календаря по названию, оставляя только одно событие (самое последнее по дате начала)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Показать, что будет удалено, без фактического удаления',
        )
        parser.add_argument(
            '--min-duplicates',
            type=int,
            default=2,
            help='Минимальное количество дубликатов для обработки (по умолчанию: 2)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        min_duplicates = options['min_duplicates']

        self.stdout.write('🔍 Поиск дубликатов событий по названию (title)...')

        # Находим все названия, которые встречаются более одного раза
        duplicates = (
            CalendarEvent.objects
            .values('title')
            .annotate(count=Count('title'))
            .filter(count__gte=min_duplicates)
            .order_by('-count')
        )

        total_duplicates = duplicates.count()

        if total_duplicates == 0:
            self.stdout.write(
                self.style.SUCCESS(
                    f'✅ Дубликатов не найдено (минимум {min_duplicates} события с одинаковым названием).'
                )
            )
            return

        self.stdout.write(
            self.style.WARNING(
                f'⚠️  Найдено {total_duplicates} уникальных названий с дубликатами'
            )
        )

        total_to_delete = 0
        total_to_keep = 0
        processed_titles = 0

        for dup_info in duplicates:
            title = dup_info['title']
            count = dup_info['count']
            
            # Получаем все события с этим названием, отсортированные по start_time (самое последнее первым)
            events = CalendarEvent.objects.filter(title=title).order_by(
                '-start_time',  # Самое последнее по дате начала первым
                '-created_at'   # Если даты одинаковые, берем самое новое по created_at
            )

            # Оставляем первое событие (самое последнее по start_time)
            event_to_keep = events.first()
            events_to_delete = events.exclude(pk=event_to_keep.pk)

            delete_count = events_to_delete.count()

            if delete_count > 0:
                processed_titles += 1
                
                # Показываем информацию о дубликатах
                self.stdout.write(
                    f'\n📋 Название: "{title[:80]}{"..." if len(title) > 80 else ""}"'
                )
                self.stdout.write(
                    f'   Всего дубликатов: {count}, будет удалено: {delete_count}, останется: 1'
                )
                
                # Показываем информацию о событии, которое останется
                self.stdout.write(
                    f'   ✅ Оставляем событие: '
                    f'ID={event_to_keep.id}, '
                    f'event_id={event_to_keep.event_id[:30]}..., '
                    f'рекрутер={event_to_keep.recruiter.username}, '
                    f'дата начала={event_to_keep.start_time.strftime("%Y-%m-%d %H:%M")}'
                )
                
                # Показываем информацию о событиях, которые будут удалены
                if delete_count <= 5:
                    self.stdout.write('   🗑️  Будет удалено:')
                    for event in events_to_delete[:5]:
                        self.stdout.write(
                            f'      - ID={event.id}, '
                            f'event_id={event.event_id[:30]}..., '
                            f'рекрутер={event.recruiter.username}, '
                            f'дата начала={event.start_time.strftime("%Y-%m-%d %H:%M")}'
                        )
                else:
                    self.stdout.write(
                        f'   🗑️  Будет удалено {delete_count} событий (показаны первые 5):'
                    )
                    for event in events_to_delete[:5]:
                        self.stdout.write(
                            f'      - ID={event.id}, '
                            f'event_id={event.event_id[:30]}..., '
                            f'рекрутер={event.recruiter.username}, '
                            f'дата начала={event.start_time.strftime("%Y-%m-%d %H:%M")}'
                        )
                    self.stdout.write(f'      ... и еще {delete_count - 5} событий')

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
                    f'   Найдено уникальных названий с дубликатами: {total_duplicates}\n'
                    f'   Обработано названий: {processed_titles}\n'
                    f'   Будет удалено событий: {total_to_delete}\n'
                    f'   Останется событий: {total_to_keep}\n'
                    f'\nДля фактического удаления запустите команду без флага --dry-run'
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'\n✅ Очистка завершена:\n'
                    f'   Найдено уникальных названий с дубликатами: {total_duplicates}\n'
                    f'   Обработано названий: {processed_titles}\n'
                    f'   Удалено событий: {total_to_delete}\n'
                    f'   Оставлено событий: {total_to_keep}'
                )
            )

