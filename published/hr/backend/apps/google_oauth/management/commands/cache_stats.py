from django.core.management.base import BaseCommand
from apps.google_oauth.cache_service import CacheService


class Command(BaseCommand):
    help = 'Показать статистику кэша API данных'

    def handle(self, *args, **options):
        stats = CacheService.get_cache_stats()
        
        self.stdout.write(
            self.style.SUCCESS(f'📊 Статистика кэша API данных:')
        )
        self.stdout.write(f'Всего ключей: {stats["total_keys"]}')
        
        if stats['services']:
            self.stdout.write('\n📋 По сервисам:')
            for service, count in stats['services'].items():
                self.stdout.write(f'  {service}: {count} ключей')
        
        if stats['oldest_cache']:
            self.stdout.write(f'\n⏰ Самый старый кэш: {stats["oldest_cache"]}')
        
        if stats['newest_cache']:
            self.stdout.write(f'🆕 Самый новый кэш: {stats["newest_cache"]}')
        
        if stats['total_keys'] == 0:
            self.stdout.write(
                self.style.WARNING('⚠️ Кэш пуст')
            )
