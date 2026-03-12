"""
Команда для тестирования API ключа Gemini
Использование: python manage.py test_gemini_key <username> [--api-key KEY]
"""
from django.core.management.base import BaseCommand
from apps.accounts.models import User
from apps.gemini.logic.services import GeminiService
import json


class Command(BaseCommand):
    help = 'Тестирует API ключ Gemini для указанного пользователя'

    def add_arguments(self, parser):
        parser.add_argument('username', type=str, help='Имя пользователя')
        parser.add_argument(
            '--api-key',
            type=str,
            help='API ключ для тестирования (если не указан, используется ключ из профиля)',
        )
        parser.add_argument(
            '--test-models',
            action='store_true',
            help='Протестировать все доступные модели',
        )

    def handle(self, *args, **options):
        username = options['username']
        test_api_key = options.get('api_key')
        test_models = options.get('test_models', False)
        
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'Пользователь "{username}" не найден'))
            return
        
        # Определяем, какой ключ использовать
        if test_api_key:
            api_key = test_api_key.strip()
            self.stdout.write(f'Используется указанный ключ: {api_key[:10]}...{api_key[-5:]}')
        else:
            api_key = user.gemini_api_key
            if not api_key:
                self.stdout.write(self.style.ERROR('❌ API ключ не найден в профиле пользователя'))
                self.stdout.write('Используйте --api-key для указания ключа или обновите ключ в профиле')
                return
            self.stdout.write(f'Используется ключ из профиля: {api_key[:10]}...{api_key[-5:]}')
        
        # Тестируем подключение
        self.stdout.write('\n🔍 Тестирование подключения к Gemini API...')
        try:
            gemini_service = GeminiService(api_key)
            success, message = gemini_service.test_connection()
            
            if success:
                self.stdout.write(self.style.SUCCESS(f'✅ Подключение успешно: {message}'))
            else:
                self.stdout.write(self.style.ERROR(f'❌ Ошибка подключения: {message}'))
                return
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Ошибка при тестировании: {str(e)}'))
            return
        
        # Тестируем генерацию контента
        self.stdout.write('\n🔍 Тестирование генерации контента...')
        test_prompt = "Привет! Это тестовое сообщение. Ответь коротко: 'Тест успешен'."
        
        models_to_test = ["gemini-1.5-pro", "gemini-1.5-flash", "gemini-pro"]
        if not test_models:
            models_to_test = [gemini_service.MODEL]
        
        for model_name in models_to_test:
            self.stdout.write(f'\n📝 Тестирование модели: {model_name}')
            try:
                success, response, metadata = gemini_service.generate_content(test_prompt, model=model_name)
                
                if success:
                    self.stdout.write(self.style.SUCCESS(f'✅ Модель {model_name} работает'))
                    self.stdout.write(f'Ответ: {response[:100]}...')
                    if metadata:
                        self.stdout.write(f'Метаданные: {json.dumps(metadata, indent=2, ensure_ascii=False)}')
                else:
                    self.stdout.write(self.style.ERROR(f'❌ Модель {model_name} не работает: {response}'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'❌ Ошибка при тестировании модели {model_name}: {str(e)}'))
        
        # Проверяем информацию о ключе
        self.stdout.write('\n📊 Информация о ключе:')
        self.stdout.write(f'Длина ключа: {len(api_key)} символов')
        self.stdout.write(f'Начинается с: {api_key[:10]}...')
        self.stdout.write(f'Заканчивается на: ...{api_key[-5:]}')
        
        # Рекомендации
        self.stdout.write('\n💡 Рекомендации:')
        self.stdout.write('1. Проверьте квоты в Google AI Studio: https://makersuite.google.com/app/apikey')
        self.stdout.write('2. Free tier имеет лимиты: 15 запросов/мин, 1500 запросов/день для gemini-2.0-flash')
        self.stdout.write('3. Модель gemini-1.5-pro обычно имеет более мягкие лимиты')
        self.stdout.write('4. Если лимиты превышены, подождите несколько минут или часов')
