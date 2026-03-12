"""
Management команда для обновления вакансий событий на основе названий
"""
from django.core.management.base import BaseCommand
from apps.reporting.models import CalendarEvent


class Command(BaseCommand):
    help = 'Обновляет вакансии событий на основе соответствия названий с заголовками инвайтов'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Показать статистику без фактического обновления',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Обновить вакансии даже для событий, у которых уже есть вакансия',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        force = options['force']

        self.stdout.write('🔍 Обновление вакансий событий на основе названий...')

        if force:
            events = CalendarEvent.objects.all()
            self.stdout.write('⚠️  Режим принудительного обновления: будут обновлены все события')
        else:
            events = CalendarEvent.objects.filter(vacancy__isnull=True)
            self.stdout.write('ℹ️  Обновляются только события без вакансии')

        total_count = events.count()
        self.stdout.write(f'\n📊 Всего событий для обработки: {total_count}')

        stats = {
            'updated': 0,
            'not_found': 0,
            'already_set': 0,
        }

        for event in events:
            old_vacancy = event.vacancy
            new_vacancy = event.determine_vacancy()
            
            if new_vacancy:
                if old_vacancy != new_vacancy:
                    stats['updated'] += 1
                    if not dry_run:
                        event.vacancy = new_vacancy
                        event.save(update_fields=['vacancy'])
                        self.stdout.write(
                            f'   ✅ "{event.title[:50]}..." -> {new_vacancy.name}'
                        )
                else:
                    stats['already_set'] += 1
            else:
                stats['not_found'] += 1

        self.stdout.write(f'\n📈 Статистика:')
        self.stdout.write(f'   ✅ Обновлено: {stats["updated"]}')
        self.stdout.write(f'   ⚠️  Не найдено вакансии: {stats["not_found"]}')
        if force:
            self.stdout.write(f'   ℹ️  Уже установлено: {stats["already_set"]}')

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







