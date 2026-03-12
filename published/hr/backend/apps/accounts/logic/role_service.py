"""
Сервис для управления ролями и группами пользователей
Объединяет логику из management/commands/seed_roles.py с сервисным слоем
"""
from django.contrib.auth.models import Group, Permission
from django.db import transaction


class RoleService:
    """Сервис для управления ролями и группами пользователей"""
    
    # Константы ролей
    ROLE_NAMES = ["Администраторы", "Наблюдатели", "Рекрутеры", "Интервьюеры"]
    
    @staticmethod
    def create_roles_and_permissions():
        """
        Создание групп ролей и назначение прав доступа
        Эквивалент команды seed_roles
        """
        with transaction.atomic():
            # Создаём группы
            groups = {}
            for name in RoleService.ROLE_NAMES:
                group, created = Group.objects.get_or_create(name=name)
                groups[name] = group
            
            # Все доступные права
            all_perms = Permission.objects.all()
            
            # Администраторы и Рекрутеры — все права
            groups["Администраторы"].permissions.set(all_perms)
            groups["Рекрутеры"].permissions.set(all_perms)
            
            # Наблюдатели — только view_* для всех моделей
            view_perms = Permission.objects.filter(codename__startswith="view_")
            groups["Наблюдатели"].permissions.set(view_perms)
            
            # Интервьюеры — видеть всё + редактировать только себя
            groups["Интервьюеры"].permissions.set(view_perms)
            
            return {
                'created_groups': len([g for g in groups.values() if g]),
                'total_permissions': all_perms.count(),
                'view_permissions': view_perms.count()
            }
    
    @staticmethod
    def get_role_statistics():
        """
        Получение статистики по ролям
        """
        stats = {}
        for role_name in RoleService.ROLE_NAMES:
            try:
                group = Group.objects.get(name=role_name)
                stats[role_name] = {
                    'users_count': group.user_set.count(),
                    'permissions_count': group.permissions.count(),
                    'created': group.date_joined if hasattr(group, 'date_joined') else None
                }
            except Group.DoesNotExist:
                stats[role_name] = {
                    'users_count': 0,
                    'permissions_count': 0,
                    'created': None,
                    'exists': False
                }
        
        return stats
    
    @staticmethod
    def assign_role_to_user(user, role_name):
        """
        Назначение роли пользователю
        """
        try:
            group = Group.objects.get(name=role_name)
            user.groups.add(group)
            
            # Обновляем флаги ролей
            if role_name == 'Наблюдатели':
                user.is_observer_active = True
                user.save(update_fields=['is_observer_active'])
            
            return True, f"Роль '{role_name}' успешно назначена"
        except Group.DoesNotExist:
            return False, f"Роль '{role_name}' не найдена"
        except Exception as e:
            return False, f"Ошибка при назначении роли: {str(e)}"
    
    @staticmethod
    def remove_role_from_user(user, role_name):
        """
        Удаление роли у пользователя
        """
        try:
            group = Group.objects.get(name=role_name)
            user.groups.remove(group)
            
            # Обновляем флаги ролей
            if role_name == 'Наблюдатели':
                user.is_observer_active = False
                user.save(update_fields=['is_observer_active'])
            
            return True, f"Роль '{role_name}' успешно удалена"
        except Group.DoesNotExist:
            return False, f"Роль '{role_name}' не найдена"
        except Exception as e:
            return False, f"Ошибка при удалении роли: {str(e)}"
    
    @staticmethod
    def get_user_roles(user):
        """
        Получение ролей пользователя
        """
        return {
            'groups': list(user.groups.values_list('name', flat=True)),
            'is_admin': user.is_admin,
            'is_recruiter': user.is_recruiter,
            'is_interviewer': user.is_interviewer,
            'is_observer': user.is_observer,
            'is_observer_active': user.is_observer_active
        }
    
    @staticmethod
    def validate_role_permissions():
        """
        Проверка корректности назначенных прав
        """
        issues = []
        
        for role_name in RoleService.ROLE_NAMES:
            try:
                group = Group.objects.get(name=role_name)
                permissions = group.permissions.all()
                
                if role_name in ['Администраторы', 'Рекрутеры']:
                    # Должны иметь все права
                    all_perms = Permission.objects.all()
                    if permissions.count() != all_perms.count():
                        issues.append(f"Роль '{role_name}' имеет неполные права")
                
                elif role_name in ['Наблюдатели', 'Интервьюеры']:
                    # Должны иметь только view права
                    non_view_perms = permissions.exclude(codename__startswith="view_")
                    if non_view_perms.exists():
                        issues.append(f"Роль '{role_name}' имеет лишние права: {list(non_view_perms.values_list('codename', flat=True))}")
                        
            except Group.DoesNotExist:
                issues.append(f"Роль '{role_name}' не существует")
        
        return {
            'valid': len(issues) == 0,
            'issues': issues
        }

