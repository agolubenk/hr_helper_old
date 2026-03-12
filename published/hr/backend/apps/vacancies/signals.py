from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Vacancy
from apps.hiring_plan.models import HiringRequest


@receiver([post_save, post_delete], sender=HiringRequest)
def update_vacancy_activity_on_request_change(sender, instance, **kwargs):
    """Обновляет статус активности вакансии при изменении заявки на найм"""
    if instance.vacancy:
        instance.vacancy.update_activity_status()


@receiver(post_save, sender=Vacancy)
def update_vacancy_activity_on_vacancy_save(sender, instance, created, **kwargs):
    """Обновляет статус активности вакансии при её сохранении"""
    if not created:  # Только при обновлении, не при создании
        instance.update_activity_status()
