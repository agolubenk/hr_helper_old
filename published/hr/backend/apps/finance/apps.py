from django.apps import AppConfig


class FinanceConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.finance'
    verbose_name = 'Финансы и грейды'
    
    def ready(self):
        # import apps.finance.logic.signals  # УДАЛЕНО - логика перенесена
        # Импортируем сигналы для автоматического пересчета зарплатных вилок
        import apps.finance.models  # Это загрузит сигналы из models.py