# Generated manually

from django.db import migrations


def migrate_time_to_fill_to_offer(apps, schema_editor):
    """Переносит данные из time_to_fill в time_to_offer"""
    VacancySLA = apps.get_model('hiring_plan', 'VacancySLA')
    
    for sla in VacancySLA.objects.all():
        if sla.time_to_fill and not sla.time_to_offer:
            sla.time_to_offer = sla.time_to_fill
            sla.save()


def reverse_migrate_time_to_offer_to_fill(apps, schema_editor):
    """Обратный перенос данных из time_to_offer в time_to_fill"""
    VacancySLA = apps.get_model('hiring_plan', 'VacancySLA')
    
    for sla in VacancySLA.objects.all():
        if sla.time_to_offer and not sla.time_to_fill:
            sla.time_to_fill = sla.time_to_offer
            sla.save()


class Migration(migrations.Migration):

    dependencies = [
        ('hiring_plan', '0011_add_time_to_offer_field'),
    ]

    operations = [
        migrations.RunPython(
            migrate_time_to_fill_to_offer,
            reverse_migrate_time_to_offer_to_fill
        ),
    ]
