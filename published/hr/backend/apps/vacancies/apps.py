from django.apps import AppConfig


class VacanciesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.vacancies'
    verbose_name = 'Локальные данные по вакансиям'
    
    def ready(self):
        import apps.vacancies.signals