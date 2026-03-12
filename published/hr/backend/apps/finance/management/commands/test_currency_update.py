"""
Django команда для тестирования автоматического обновления курсов валют
"""
from django.core.management.base import BaseCommand
from config.celery import app
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Тестирует автоматическое обновление курсов валют через Celery'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('🧪 Тестирование автоматического обновления курсов валют'))
        
        try:
            # Запускаем задачу синхронно для тестирования
            self.stdout.write('🔄 Запускаем задачу обновления курсов...')
            result = app.send_task('config.celery.update_currency_rates').get()
            
            if result['success']:
                self.stdout.write(
                    self.style.SUCCESS(f'✅ {result["message"]}')
                )
                self.stdout.write(f'📊 Обновлено курсов: {result["updated_count"]}')
                
                # Выводим детали по каждой валюте
                if 'results' in result:
                    for currency, data in result['results'].items():
                        if data['success']:
                            self.stdout.write(
                                f'  💰 {currency}: {data["rate"]} BYN '
                                f'({"создан" if data["created"] else "обновлен"})'
                            )
                        else:
                            self.stdout.write(
                                self.style.WARNING(f'  ⚠️ {currency}: ошибка - {data["error"]}')
                            )
            else:
                self.stdout.write(
                    self.style.ERROR(f'❌ {result["message"]}')
                )
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Ошибка при тестировании: {e}')
            )
            logger.error(f'Ошибка при тестировании обновления курсов: {e}')
            raise
