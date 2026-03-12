"""
Команда для создания пользователей
"""
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from apps.accounts.logic.user_service import UserService
from apps.accounts.logic.role_service import RoleService

User = get_user_model()


class Command(BaseCommand):
    help = "Создать пользователя с указанной ролью"

    def add_arguments(self, parser):
        parser.add_argument('username', help='Имя пользователя')
        parser.add_argument('email', help='Email пользователя')
        parser.add_argument('--password', help='Пароль (если не указан, будет сгенерирован)')
        parser.add_argument('--role', choices=RoleService.ROLE_NAMES, default='Наблюдатели', help='Роль пользователя')

    def handle(self, *args, **options):
        username = options['username']
        email = options['email']
        password = options.get('password')
        role = options['role']
        
        # Проверяем, существует ли пользователь
        if User.objects.filter(username=username).exists():
            raise CommandError(f"Пользователь '{username}' уже существует")
        
        if User.objects.filter(email=email).exists():
            raise CommandError(f"Пользователь с email '{email}' уже существует")
        
        # Создаем пользователя
        user_data = {
            'username': username,
            'email': email,
            'password': password or 'temp_password_123'
        }
        
        try:
            user = UserService.create_user_with_observer_role(user_data)
            
            # Назначаем указанную роль
            if role != 'Наблюдатели':
                success, message = RoleService.assign_role_to_user(user, role)
                if not success:
                    self.stdout.write(self.style.WARNING(f"⚠️ Не удалось назначить роль: {message}"))
            
            self.stdout.write(self.style.SUCCESS(f"✅ Пользователь '{username}' создан успешно"))
            self.stdout.write(f"  - Email: {email}")
            self.stdout.write(f"  - Роль: {role}")
            if not password:
                self.stdout.write(self.style.WARNING(f"  - Временный пароль: temp_password_123"))
                self.stdout.write(self.style.WARNING(f"  - Рекомендуется сменить пароль при первом входе"))
                
        except Exception as e:
            raise CommandError(f"Ошибка при создании пользователя: {str(e)}")

