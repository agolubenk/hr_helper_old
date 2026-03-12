from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.accounts'
    verbose_name = 'Управление пользователями'
    
    def ready(self):
        """Подключение сигналов при запуске приложения"""
        import apps.accounts.logic.signals