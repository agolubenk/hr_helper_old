"""
Команда для показа статистики пользователей
"""
from django.core.management.base import BaseCommand
from apps.accounts.logic.user_service import UserService
from apps.accounts.logic.role_service import RoleService


class Command(BaseCommand):
    help = "Показать статистику пользователей и ролей"

    def handle(self, *args, **options):
        # Статистика пользователей
        user_stats = UserService.get_user_stats()
        self.stdout.write(self.style.SUCCESS("📊 Статистика пользователей:"))
        self.stdout.write(f"  - Всего пользователей: {user_stats['total_users']}")
        self.stdout.write(f"  - Активных пользователей: {user_stats['active_users']}")
        self.stdout.write(f"  - Сотрудников: {user_stats['staff_users']}")
        
        # Статистика по группам
        self.stdout.write("\n📊 Статистика по группам:")
        for group_name, count in user_stats['groups_stats'].items():
            self.stdout.write(f"  - {group_name}: {count} пользователей")
        
        # Статистика по ролям
        role_stats = RoleService.get_role_statistics()
        self.stdout.write("\n📊 Статистика по ролям:")
        for role_name, data in role_stats.items():
            if data.get('exists', True):
                self.stdout.write(f"  - {role_name}: {data['users_count']} пользователей, {data['permissions_count']} прав")
            else:
                self.stdout.write(self.style.WARNING(f"  - {role_name}: НЕ СУЩЕСТВУЕТ"))

