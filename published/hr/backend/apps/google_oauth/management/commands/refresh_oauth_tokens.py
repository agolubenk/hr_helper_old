"""
Команда для ручного обновления Google OAuth токенов
"""
from django.core.management.base import BaseCommand
from apps.google_oauth.tasks import refresh_google_oauth_tokens, validate_oauth_tokens


class Command(BaseCommand):
    help = 'Обновить истекшие Google OAuth токены'

    def add_arguments(self, parser):
        parser.add_argument(
            '--validate-only',
            action='store_true',
            help='Только проверить статус токенов без обновления',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Принудительно обновить все токены',
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('🔄 Запуск обновления Google OAuth токенов...')
        )

        if options['validate_only']:
            # Только валидация
            result = validate_oauth_tokens()
            if result['success']:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"📊 Статистика OAuth токенов:\n"
                        f"   Всего аккаунтов: {result['total_accounts']}\n"
                        f"   Валидных токенов: {result['valid_tokens']}\n"
                        f"   Истекших токенов: {result['expired_tokens']}\n"
                        f"   Требуют обновления: {result['needs_refresh']}"
                    )
                )
            else:
                self.stdout.write(
                    self.style.ERROR(f"❌ Ошибка валидации: {result['error']}")
                )
        else:
            # Обновление токенов
            result = refresh_google_oauth_tokens()
            if result['success']:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"✅ Обновление завершено:\n"
                        f"   Обновлено токенов: {result['refreshed_count']}\n"
                        f"   Ошибок: {result['failed_count']}\n"
                        f"   Всего проверено: {result['total_checked']}"
                    )
                )
            else:
                self.stdout.write(
                    self.style.ERROR(f"❌ Ошибка обновления: {result['error']}")
                )

        self.stdout.write(
            self.style.SUCCESS('🎉 Команда выполнена успешно!')
        )

