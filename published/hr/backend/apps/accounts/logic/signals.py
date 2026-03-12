"""
Сигналы для автоматической обработки событий пользователей
Объединяет логику из signals.py с использованием сервисного слоя
"""
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.contrib.auth.models import Group
from ..models import User
from .user_service import UserService


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """
    Автоматическое создание профиля пользователя при создании
    """
    if created:
        # Автоматически назначаем роль наблюдателя новым пользователям
        from .role_service import RoleService
        if not instance.groups.filter(name='Наблюдатели').exists():
            success, message = RoleService.assign_role_to_user(instance, 'Наблюдатели')
            if success:
                print(f"✅ SIGNAL: Новому пользователю {instance.username} назначены права наблюдателя")
            else:
                print(f"⚠️ SIGNAL: Не удалось назначить права наблюдателя: {message}")




@receiver(post_save, sender=User)
def log_user_activity(sender, instance, created, **kwargs):
    """
    Логирование активности пользователей
    """
    if created:
        print(f"📝 SIGNAL: Создан новый пользователь: {instance.username} ({instance.email})")
    else:
        print(f"📝 SIGNAL: Обновлен пользователь: {instance.username}")


