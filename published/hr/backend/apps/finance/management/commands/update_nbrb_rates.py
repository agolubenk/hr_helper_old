"""
Django команда для обновления курсов валют НБРБ
"""
from django.core.management.base import BaseCommand
from logic.base.currency_service import currency_service
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Обновляет курсы валют НБРБ в базе данных'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Принудительное обновление (игнорирует проверки)',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('🔄 Начинаем обновление курсов валют НБРБ...'))
        
        try:
            # Тестируем подключение к API
            self.stdout.write('🔍 Проверяем подключение к НБРБ API...')
            test_response = currency_service.test_connection()
            
            if not test_response.success:
                self.stdout.write(
                    self.style.ERROR(f'❌ Ошибка подключения к НБРБ API: {test_response.error}')
                )
                return
            
            self.stdout.write(self.style.SUCCESS('✅ Подключение к НБРБ API успешно'))
            
            # Обновляем курсы в базе данных
            self.stdout.write('💱 Обновляем курсы валют в базе данных...')
            result = currency_service.update_currency_rates_in_db()
            
            if result['updated_count'] > 0:
                self.stdout.write(
                    self.style.SUCCESS(f'✅ Успешно обновлено {result["updated_count"]} курсов валют')
                )
                
                # Выводим детали по каждой валюте
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
                    self.style.WARNING('⚠️ Курсы валют не были обновлены')
                )
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Ошибка при обновлении курсов: {e}')
            )
            logger.error(f'Ошибка при обновлении курсов валют: {e}')
            raise
