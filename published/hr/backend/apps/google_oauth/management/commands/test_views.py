from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse
from apps.google_oauth.models import GoogleOAuthAccount

User = get_user_model()


class Command(BaseCommand):
    help = 'Тестировать views с авторизованным пользователем'

    def handle(self, *args, **options):
        # Находим пользователя с OAuth аккаунтом
        oauth_accounts = GoogleOAuthAccount.objects.all()
        if not oauth_accounts:
            self.stdout.write(
                self.style.ERROR('❌ Нет пользователей с подключенным Google OAuth')
            )
            return
        
        oauth_account = oauth_accounts[0]
        user = oauth_account.user
        
        self.stdout.write(
            self.style.SUCCESS(f'🧪 Тестируем views для пользователя: {user.username} (ID: {user.id})')
        )
        self.stdout.write(f'📧 OAuth email: {oauth_account.email}')
        
        # Создаем клиент и авторизуемся
        client = Client()
        client.force_login(user)
        
        # Тестируем dashboard
        self.stdout.write('\n📊 Тестируем dashboard:')
        try:
            response = client.get('/google-oauth/')
            self.stdout.write(f'  Status: {response.status_code}')
            if response.status_code == 200:
                self.stdout.write('  ✅ Dashboard загружен успешно')
            else:
                self.stdout.write(f'  ⚠️ Dashboard вернул статус {response.status_code}')
        except Exception as e:
            self.stdout.write(f'  ❌ Ошибка dashboard: {e}')
        
        # Тестируем calendar
        self.stdout.write('\n📅 Тестируем calendar:')
        try:
            response = client.get('/google-oauth/calendar/')
            self.stdout.write(f'  Status: {response.status_code}')
            if response.status_code == 200:
                self.stdout.write('  ✅ Calendar загружен успешно')
                # Проверяем, есть ли события в контексте
                if hasattr(response, 'context') and 'page_obj' in response.context:
                    events = response.context['page_obj']
                    if events is not None:
                        self.stdout.write(f'  📋 Событий на странице: {len(events)}')
                    else:
                        self.stdout.write('  📋 Событий на странице: 0 (None)')
            else:
                self.stdout.write(f'  ⚠️ Calendar вернул статус {response.status_code}')
        except Exception as e:
            self.stdout.write(f'  ❌ Ошибка calendar: {e}')
        
        # Тестируем drive
        self.stdout.write('\n📁 Тестируем drive:')
        try:
            response = client.get('/google-oauth/drive/')
            self.stdout.write(f'  Status: {response.status_code}')
            if response.status_code == 200:
                self.stdout.write('  ✅ Drive загружен успешно')
                # Проверяем, есть ли файлы в контексте
                if hasattr(response, 'context') and 'page_obj' in response.context:
                    files = response.context['page_obj']
                    if files is not None:
                        self.stdout.write(f'  📋 Файлов на странице: {len(files)}')
                    else:
                        self.stdout.write('  📋 Файлов на странице: 0 (None)')
            else:
                self.stdout.write(f'  ⚠️ Drive вернул статус {response.status_code}')
        except Exception as e:
            self.stdout.write(f'  ❌ Ошибка drive: {e}')
        
        # Тестируем sheets
        self.stdout.write('\n📊 Тестируем sheets:')
        try:
            response = client.get('/google-oauth/sheets/')
            self.stdout.write(f'  Status: {response.status_code}')
            if response.status_code == 200:
                self.stdout.write('  ✅ Sheets загружен успешно')
                # Проверяем, есть ли таблицы в контексте
                if hasattr(response, 'context') and 'sheets' in response.context:
                    sheets = response.context['sheets']
                    if sheets is not None:
                        self.stdout.write(f'  📋 Таблиц на странице: {len(sheets)}')
                    else:
                        self.stdout.write('  📋 Таблиц на странице: 0 (None)')
            else:
                self.stdout.write(f'  ⚠️ Sheets вернул статус {response.status_code}')
        except Exception as e:
            self.stdout.write(f'  ❌ Ошибка sheets: {e}')
        
        self.stdout.write(
            self.style.SUCCESS('\n✅ Тест views завершен')
        )
