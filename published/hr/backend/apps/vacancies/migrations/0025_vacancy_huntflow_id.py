# Migration: huntflow_id on Vacancy (non-unique, for linking with HH/Huntflow)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('vacancies', '0024_migrate_additional_recruiter_to_m2m'),
    ]

    operations = [
        migrations.AddField(
            model_name='vacancy',
            name='huntflow_id',
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text='Идентификатор для связи с вакансией в Huntflow или HH.ru (может совпадать у нескольких вакансий)',
                max_length=100,
                null=True,
                verbose_name='Huntflow ID',
            ),
        ),
    ]
