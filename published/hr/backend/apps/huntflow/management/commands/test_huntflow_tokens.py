from django.core.management.base import BaseCommand
from apps.huntflow.tasks import refresh_huntflow_tokens, check_huntflow_token_health
from apps.accounts.models import User

class Command(BaseCommand):
    help = 'Тестирует автоматическое обновление токенов Huntflow'

    def add_arguments(self, parser):
        parser.add_argument(
            '--action',
            type=str,
            choices=['refresh', 'health', 'both'],
            default='both',
            help='Действие для выполнения'
        )

    def handle(self, *args, **options):
        action = options['action']
        
        self.stdout.write(self.style.SUCCESS('🧪 Тестирование автоматического обновления токенов Huntflow'))
        
        if action in ['refresh', 'both']:
            self.stdout.write('🔄 Тестирование обновления токенов...')
            try:
                result = refresh_huntflow_tokens()
                self.stdout.write(
                    self.style.SUCCESS(
                        f'✅ Обновление токенов завершено: {result["updated"]} успешно, '
                        f'{result["failed"]} ошибок из {result["total"]} пользователей'
                    )
                )
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'❌ Ошибка при обновлении токенов: {e}'))
        
        if action in ['health', 'both']:
            self.stdout.write('🏥 Тестирование проверки здоровья токенов...')
            try:
                result = check_huntflow_token_health()
                self.stdout.write(
                    self.style.SUCCESS(
                        f'✅ Проверка здоровья завершена: {result["healthy"]} здоровых, '
                        f'{result["warning"]} предупреждений, {result["critical"]} критических '
                        f'из {result["total_users"]} пользователей'
                    )
                )
                
                # Показываем детали
                if result['details']:
                    self.stdout.write('\n📊 Детали:')
                    for detail in result['details']:
                        status_emoji = {
                            'healthy': '✅',
                            'warning': '⚠️',
                            'critical': '🚨'
                        }.get(detail['status'], '❓')
                        
                        self.stdout.write(
                            f'  {status_emoji} {detail["user"]}: {detail["status"]} '
                            f'(access: {detail["access_expires"]}, refresh: {detail["refresh_expires"]})'
                        )
                        
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'❌ Ошибка при проверке здоровья: {e}'))
        
        self.stdout.write(self.style.SUCCESS('🎉 Тестирование завершено!'))
