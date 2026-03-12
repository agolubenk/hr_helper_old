# Generated manually

from django.db import migrations, models


def set_default_time_to_offer(apps, schema_editor):
    """Устанавливает значение по умолчанию для time_to_offer"""
    VacancySLA = apps.get_model('hiring_plan', 'VacancySLA')
    
    for sla in VacancySLA.objects.filter(time_to_offer__isnull=True):
        sla.time_to_offer = 30  # 30 дней по умолчанию
        sla.save()


class Migration(migrations.Migration):

    dependencies = [
        ('hiring_plan', '0012_migrate_time_to_fill_to_offer'),
    ]

    operations = [
        migrations.RunPython(set_default_time_to_offer),
        migrations.RemoveField(
            model_name='vacancysla',
            name='time_to_fill',
        ),
        migrations.AlterField(
            model_name='vacancysla',
            name='time_to_offer',
            field=models.PositiveIntegerField(
                help_text='Целевое время от открытия до предложения кандидату',
                verbose_name='Time-to-Offer (дни)'
            ),
        ),
    ]
