"""
Команда для назначения ролей пользователям
"""
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from apps.accounts.logic.role_service import RoleService

User = get_user_model()


class Command(BaseCommand):
    help = "Назначить роль пользователю"

    def add_arguments(self, parser):
        parser.add_argument('username', help='Имя пользователя')
        parser.add_argument('role', choices=RoleService.ROLE_NAMES, help='Роль для назначения')

    def handle(self, *args, **options):
        username = options['username']
        role = options['role']
        
        try:
            user = User.objects.get(username=username)
            success, message = RoleService.assign_role_to_user(user, role)
            
            if success:
                self.stdout.write(self.style.SUCCESS(f"✅ {message}"))
            else:
                self.stdout.write(self.style.ERROR(f"❌ {message}"))
                
        except User.DoesNotExist:
            raise CommandError(f"Пользователь '{username}' не найден")

