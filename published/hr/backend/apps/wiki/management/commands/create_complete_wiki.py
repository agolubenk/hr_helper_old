"""
Команда для создания полной документации Wiki по всем разделам системы
"""
from django.core.management.base import BaseCommand
from apps.wiki.models import WikiPage, WikiTag
from django.db import transaction


class Command(BaseCommand):
    help = 'Создает полную документацию Wiki по всем разделам системы с тегами и хештегами'

    def add_arguments(self, parser):
        parser.add_argument(
            '--prune',
            action='store_true',
            help='Снять публикацию со страниц, которых нет в seed-данных (оставить в БД, но скрыть из /wiki/).'
        )

    def handle(self, *args, **options):
        self.stdout.write('Создание полной документации Wiki...')
        
        # Создаем теги
        tags_data = {
            'настройка': {'color': '#007bff', 'description': 'Настройка системы и модулей'},
            'использование': {'color': '#28a745', 'description': 'Руководство по использованию функций'},
            'интеграции': {'color': '#ffc107', 'description': 'Интеграции с внешними системами'},
            'финансы': {'color': '#17a2b8', 'description': 'Финансовый модуль и зарплатные вилки'},
            'вакансии': {'color': '#dc3545', 'description': 'Управление вакансиями и наймом'},
            'календарь': {'color': '#6f42c1', 'description': 'Google Calendar и инвайты'},
            'ai': {'color': '#e83e8c', 'description': 'AI-помощник и автоматизация'},
            'интервьюеры': {'color': '#20c997', 'description': 'Управление интервьюерами'},
            'метрики': {'color': '#fd7e14', 'description': 'Метрики и аналитика'},
            'пользователи': {'color': '#6c757d', 'description': 'Управление пользователями'},
        }
        
        created_tags = {}
        for tag_name, tag_info in tags_data.items():
            tag, created = WikiTag.objects.get_or_create(
                name=tag_name,
                defaults={'color': tag_info['color']}
            )
            created_tags[tag_name] = tag
            if created:
                self.stdout.write(self.style.SUCCESS(f'✓ Создан тег: #{tag_name}'))
        
        # Импортируем данные страниц
        try:
            from .wiki_pages_data import WIKI_PAGES_DATA
            pages_data = WIKI_PAGES_DATA
        except ImportError:
            # Если файл не найден, используем базовые страницы
            pages_data = []
        
        # Важно: набор страниц берём из seed-данных.
        # Если нужно расширить документацию — добавляйте страницы в wiki_pages_data.py
        all_pages = list(pages_data)
        
        created_count = 0
        updated_count = 0
        seed_slugs = []

        with transaction.atomic():
            for page_data in all_pages:
                page_payload = dict(page_data)  # не мутируем исходные данные
                tags = page_payload.pop('tags', [])
                slug = page_payload.get('slug')
                if not slug:
                    continue

                seed_slugs.append(slug)

                # Принудительно публикуем сидовые страницы
                page_payload['is_published'] = True

                page, created = WikiPage.objects.update_or_create(
                    slug=slug,
                    defaults=page_payload
                )

                # Проставляем теги строго по seed-данным
                tag_objs = [created_tags[name] for name in tags if name in created_tags]
                page.tags.set(tag_objs)

                if created:
                    created_count += 1
                    self.stdout.write(self.style.SUCCESS(f'✓ Создана страница: {page.title}'))
                else:
                    updated_count += 1
                    self.stdout.write(self.style.SUCCESS(f'✓ Обновлена страница: {page.title}'))

            # Подчистка: снимаем публикацию с несидовых страниц (по желанию)
            if options.get('prune'):
                pruned_qs = WikiPage.objects.exclude(slug__in=seed_slugs).filter(is_published=True)
                pruned_count = pruned_qs.update(is_published=False)
                if pruned_count:
                    self.stdout.write(self.style.WARNING(f'→ Снята публикация с {pruned_count} страниц (prune)'))
        
        self.stdout.write(self.style.SUCCESS(f'\nСоздано страниц: {created_count}'))
        self.stdout.write(self.style.SUCCESS(f'Обновлено страниц: {updated_count}'))
        self.stdout.write(self.style.SUCCESS('Документация Wiki успешно создана!'))

