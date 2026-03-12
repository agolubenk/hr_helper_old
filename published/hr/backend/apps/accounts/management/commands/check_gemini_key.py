"""
Команда для проверки API ключа Gemini в базе данных
Использование: python manage.py check_gemini_key <username>
"""
from django.core.management.base import BaseCommand
from apps.accounts.models import User
from django.db import connection


class Command(BaseCommand):
    help = 'Проверяет API ключ Gemini в базе данных для указанного пользователя'

    def add_arguments(self, parser):
        parser.add_argument('username', type=str, help='Имя пользователя')

    def handle(self, *args, **options):
        username = options['username']
        
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'Пользователь "{username}" не найден'))
            return
        
        self.stdout.write(f'\n📊 Информация о пользователе:')
        self.stdout.write(f'Username: {user.username}')
        self.stdout.write(f'ID: {user.id}')
        self.stdout.write(f'Email: {user.email}')
        
        # Проверяем ключ через ORM
        self.stdout.write(f'\n🔍 Проверка через ORM:')
        if user.gemini_api_key:
            key_preview = f"{user.gemini_api_key[:10]}...{user.gemini_api_key[-5:]}"
            self.stdout.write(f'Ключ найден: {key_preview}')
            self.stdout.write(f'Длина: {len(user.gemini_api_key)} символов')
            self.stdout.write(f'Начинается с: {user.gemini_api_key[:10]}')
            self.stdout.write(f'Заканчивается на: ...{user.gemini_api_key[-5:]}')
        else:
            self.stdout.write(self.style.WARNING('Ключ не найден (None или пустая строка)'))
        
        # Проверяем ключ через прямой SQL запрос
        self.stdout.write(f'\n🔍 Проверка через прямой SQL запрос:')
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT gemini_api_key FROM accounts_user WHERE id = %s",
                [user.id]
            )
            row = cursor.fetchone()
            if row and row[0]:
                db_key = row[0]
                key_preview = f"{db_key[:10]}...{db_key[-5:]}"
                self.stdout.write(f'Ключ в БД: {key_preview}')
                self.stdout.write(f'Длина: {len(db_key)} символов')
                self.stdout.write(f'Начинается с: {db_key[:10]}')
                self.stdout.write(f'Заканчивается на: ...{db_key[-5:]}')
                
                # Сравниваем
                if user.gemini_api_key == db_key:
                    self.stdout.write(self.style.SUCCESS('✅ Ключи совпадают (ORM и БД)'))
                else:
                    self.stdout.write(self.style.ERROR('❌ Ключи НЕ совпадают! Проблема с кешированием!'))
            else:
                self.stdout.write(self.style.WARNING('Ключ не найден в БД'))
        
        # Проверяем все пользователей с ключами
        self.stdout.write(f'\n📋 Все пользователи с Gemini API ключами:')
        users_with_keys = User.objects.exclude(gemini_api_key__isnull=True).exclude(gemini_api_key='')
        for u in users_with_keys:
            key_preview = f"{u.gemini_api_key[:10]}...{u.gemini_api_key[-5:]}" if len(u.gemini_api_key) > 15 else "короткий"
            self.stdout.write(f'  - {u.username} (ID: {u.id}): {key_preview}')
