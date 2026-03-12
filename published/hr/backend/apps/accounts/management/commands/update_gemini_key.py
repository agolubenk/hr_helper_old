"""
Команда для обновления API ключа Gemini для пользователя
Использование: python manage.py update_gemini_key <username> <api_key>
"""
from django.core.management.base import BaseCommand
from apps.accounts.models import User
from apps.gemini.logic.services import GeminiService


class Command(BaseCommand):
    help = 'Обновляет API ключ Gemini для указанного пользователя'

    def add_arguments(self, parser):
        parser.add_argument('username', type=str, help='Имя пользователя')
        parser.add_argument('api_key', type=str, help='API ключ Gemini')
        parser.add_argument(
            '--test',
            action='store_true',
            help='Протестировать ключ перед сохранением',
        )
        parser.add_argument(
            '--show-current',
            action='store_true',
            help='Показать текущий ключ (первые и последние символы)',
        )

    def handle(self, *args, **options):
        username = options['username']
        api_key = options['api_key'].strip()
        
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'Пользователь "{username}" не найден'))
            return
        
        # Показываем текущий ключ, если запрошено
        if options['show_current']:
            if user.gemini_api_key:
                key_preview = f"{user.gemini_api_key[:10]}...{user.gemini_api_key[-5:]}"
                self.stdout.write(f'Текущий ключ: {key_preview} (длина: {len(user.gemini_api_key)})')
            else:
                self.stdout.write('Текущий ключ: не установлен')
        
        # Тестируем ключ, если запрошено
        if options['test']:
            self.stdout.write('Тестирование API ключа...')
            try:
                gemini_service = GeminiService(api_key)
                success, message = gemini_service.test_connection()
                if success:
                    self.stdout.write(self.style.SUCCESS(f'✅ Ключ протестирован успешно: {message}'))
                else:
                    self.stdout.write(self.style.ERROR(f'❌ Ошибка тестирования: {message}'))
                    return
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'❌ Ошибка при тестировании: {str(e)}'))
                return
        
        # Обновляем ключ
        old_key = user.gemini_api_key
        user.gemini_api_key = api_key
        user.save()
        
        # Проверяем, что ключ сохранился
        user.refresh_from_db()
        
        if user.gemini_api_key == api_key:
            new_key_preview = f"{user.gemini_api_key[:10]}...{user.gemini_api_key[-5:]}"
            self.stdout.write(self.style.SUCCESS(f'✅ API ключ успешно обновлен: {new_key_preview}'))
            
            if old_key and old_key != api_key:
                old_key_preview = f"{old_key[:10]}...{old_key[-5:]}"
                self.stdout.write(f'Старый ключ: {old_key_preview}')
        else:
            self.stdout.write(self.style.ERROR('❌ Ошибка: ключ не сохранился в базе данных'))
