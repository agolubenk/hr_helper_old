from django.db.models.signals import pre_save
from django.db.utils import OperationalError
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from .models import ClickUpSettings

User = get_user_model()


@receiver(pre_save, sender=User)
def clear_clickup_settings_on_api_key_change(sender, instance, **kwargs):
    """
    Очищает настройки ClickUp при изменении API ключа ClickUp
    """
    if instance.pk:  # Только для существующих пользователей
        try:
            # Получаем старую версию пользователя из базы данных
            old_user = User.objects.get(pk=instance.pk)
            
            # Проверяем, изменился ли API ключ ClickUp
            if old_user.clickup_api_key != instance.clickup_api_key:
                # API ключ изменился, очищаем настройки ClickUp
                try:
                    clickup_settings = ClickUpSettings.objects.get(user=instance)
                    # Очищаем только ID полей, оставляем другие настройки
                    clickup_settings.team_id = ''
                    clickup_settings.space_id = ''
                    clickup_settings.folder_id = ''
                    clickup_settings.list_id = ''
                    clickup_settings.save()
                    
                    print(f"🔄 API ключ ClickUp изменился для пользователя {instance.username}. Настройки пути очищены.")
                    
                except ClickUpSettings.DoesNotExist:
                    # Настройки не существуют, ничего не делаем
                    pass
                except OperationalError:
                    # Миграции clickup_int не применены (нет колонок hiring_plan_* и т.д.)
                    pass
                    
        except User.DoesNotExist:
            # Пользователь не существует в базе (новый пользователь), ничего не делаем
            pass

