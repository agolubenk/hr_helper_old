from django.core.management.base import BaseCommand
from apps.accounts.logic.role_service import RoleService


class Command(BaseCommand):
    help = "Создаёт группы ролей и назначает права доступа"

    def add_arguments(self, parser):
        parser.add_argument(
            '--validate',
            action='store_true',
            help='Проверить корректность назначенных прав',
        )
        parser.add_argument(
            '--stats',
            action='store_true',
            help='Показать статистику по ролям',
        )

    def handle(self, *args, **options):
        if options['validate']:
            # Проверка корректности прав
            validation_result = RoleService.validate_role_permissions()
            if validation_result['valid']:
                self.stdout.write(self.style.SUCCESS("✅ Все роли настроены корректно"))
            else:
                self.stdout.write(self.style.ERROR("❌ Найдены проблемы с ролями:"))
                for issue in validation_result['issues']:
                    self.stdout.write(self.style.WARNING(f"  - {issue}"))
            return

        if options['stats']:
            # Показать статистику
            stats = RoleService.get_role_statistics()
            self.stdout.write(self.style.SUCCESS("📊 Статистика по ролям:"))
            for role_name, data in stats.items():
                if data.get('exists', True):
                    self.stdout.write(f"  {role_name}: {data['users_count']} пользователей, {data['permissions_count']} прав")
                else:
                    self.stdout.write(self.style.WARNING(f"  {role_name}: НЕ СУЩЕСТВУЕТ"))
            return

        # Создание ролей и прав
        result = RoleService.create_roles_and_permissions()
        
        self.stdout.write(self.style.SUCCESS("✅ Группы и права настроены."))
        self.stdout.write(f"  - Создано групп: {result['created_groups']}")
        self.stdout.write(f"  - Всего прав: {result['total_permissions']}")
        self.stdout.write(f"  - View прав: {result['view_permissions']}")
        
        # Проверяем корректность
        validation_result = RoleService.validate_role_permissions()
        if not validation_result['valid']:
            self.stdout.write(self.style.WARNING("⚠️ Обнаружены проблемы с правами:"))
            for issue in validation_result['issues']:
                self.stdout.write(self.style.WARNING(f"  - {issue}"))
