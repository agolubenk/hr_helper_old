# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('vacancies', '0025_vacancy_huntflow_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='vacancy',
            name='review_period_months',
            field=models.PositiveIntegerField(blank=True, help_text='Срок пересмотра вакансии в месяцах (число)', null=True, verbose_name='Срок пересмотра (месяцы)'),
        ),
    ]
