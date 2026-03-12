"""
Management команда для фильтрации событий календаря
Удаляет события, в названии которых нет ключевых слов, связанных с интервью и скринингами
"""
from django.core.management.base import BaseCommand
from django.db.models import Q
from apps.reporting.models import CalendarEvent
import re


class Command(BaseCommand):
    help = 'Удаляет события календаря, в названии которых нет ключевых слов интервью/скрининга'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Показать, что будет удалено, без фактического удаления',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        # Ключевые слова для поиска (если хотя бы одно есть - оставляем событие)
        keywords = [
            'meet',
            'final',
            'Screening',
            'скрининг',
            'interview',
            'интервью',
            'tech',
            'office',
            'with',
        ]

        self.stdout.write('🔍 Поиск событий для удаления...')
        self.stdout.write(f'📋 Ключевые слова для сохранения: {", ".join(keywords[:10])}...')

        # Создаем регулярное выражение для поиска ключевых слов (без учета регистра)
        pattern_parts = []
        for keyword in keywords:
            # Экранируем специальные символы регулярных выражений
            escaped_keyword = re.escape(keyword)
            pattern_parts.append(escaped_keyword)

        # Объединяем все ключевые слова через | (ИЛИ)
        pattern = '|'.join(pattern_parts)
        regex_pattern = re.compile(pattern, re.IGNORECASE)

        # Получаем все события
        all_events = CalendarEvent.objects.all()
        total_count = all_events.count()

        self.stdout.write(f'\n📊 Всего событий в базе: {total_count}')

        # Находим события, которые НЕ содержат ни одного ключевого слова
        events_to_delete = []
        events_to_keep = []

        for event in all_events:
            title = event.title or ''
            if regex_pattern.search(title):
                # Содержит хотя бы одно ключевое слово - оставляем
                events_to_keep.append(event)
            else:
                # Не содержит ни одного ключевого слова - удаляем
                events_to_delete.append(event)

        delete_count = len(events_to_delete)
        keep_count = len(events_to_keep)

        self.stdout.write(f'\n📈 Статистика:')
        self.stdout.write(f'   ✅ Будет сохранено: {keep_count} событий')
        self.stdout.write(f'   🗑️  Будет удалено: {delete_count} событий')

        if delete_count == 0:
            self.stdout.write(
                self.style.SUCCESS('\n✅ Все события содержат ключевые слова. Удалять нечего.')
            )
            return

        # Показываем примеры событий, которые будут удалены
        self.stdout.write(f'\n📋 Примеры событий, которые будут удалены (первые 20):')
        for i, event in enumerate(events_to_delete[:20], 1):
            self.stdout.write(
                f'   {i}. "{event.title[:60]}{"..." if len(event.title) > 60 else ""}" '
                f'(ID={event.id}, дата={event.start_time.date()}, рекрутер={event.recruiter.username})'
            )

        if delete_count > 20:
            self.stdout.write(f'   ... и еще {delete_count - 20} событий')

        # Показываем примеры событий, которые будут сохранены
        self.stdout.write(f'\n📋 Примеры событий, которые будут сохранены (первые 10):')
        for i, event in enumerate(events_to_keep[:10], 1):
            # Находим какое ключевое слово найдено
            found_keyword = None
            for keyword in keywords:
                if keyword.lower() in event.title.lower():
                    found_keyword = keyword
                    break
            
            self.stdout.write(
                f'   {i}. "{event.title[:60]}{"..." if len(event.title) > 60 else ""}" '
                f'(найдено: "{found_keyword}", ID={event.id}, дата={event.start_time.date()})'
            )

        if keep_count > 10:
            self.stdout.write(f'   ... и еще {keep_count - 10} событий')

        # Удаляем события
        if not dry_run:
            self.stdout.write(f'\n🗑️  Удаление событий...')
            
            # Удаляем пакетами для оптимизации
            batch_size = 1000
            deleted_total = 0
            
            for i in range(0, len(events_to_delete), batch_size):
                batch = events_to_delete[i:i + batch_size]
                event_ids = [event.id for event in batch]
                deleted_count, _ = CalendarEvent.objects.filter(id__in=event_ids).delete()
                deleted_total += deleted_count
                self.stdout.write(f'   Удалено {deleted_total} из {delete_count} событий...')

            self.stdout.write(
                self.style.SUCCESS(
                    f'\n✅ Очистка завершена:\n'
                    f'   Удалено событий: {deleted_total}\n'
                    f'   Сохранено событий: {keep_count}'
                )
            )
        else:
            self.stdout.write('\n' + '='*60)
            self.stdout.write(
                self.style.WARNING(
                    f'\n🔍 [DRY RUN] Режим проверки:\n'
                    f'   Будет удалено событий: {delete_count}\n'
                    f'   Будет сохранено событий: {keep_count}\n'
                    f'\nДля фактического удаления запустите команду без флага --dry-run'
                )
            )

