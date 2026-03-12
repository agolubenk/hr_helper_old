from django.core.management.base import BaseCommand
from apps.google_oauth.cache_service import CacheService


class Command(BaseCommand):
    help = 'Очистить весь кэш API данных'

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Подтвердить очистку кэша',
        )

    def handle(self, *args, **options):
        if not options['confirm']:
            self.stdout.write(
                self.style.WARNING('⚠️ Для очистки кэша используйте --confirm')
            )
            return
        
        CacheService.clear_all_cache()
        self.stdout.write(
            self.style.SUCCESS('✅ Кэш очищен')
        )
