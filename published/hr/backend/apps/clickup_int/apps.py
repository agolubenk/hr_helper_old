from django.apps import AppConfig


class ClickupIntConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.clickup_int'
    verbose_name = 'ClickUp интеграция'
    
    def ready(self):
        """Импортируем сигналы при запуске приложения"""
        import apps.clickup_int.signals
