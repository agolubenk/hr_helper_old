# Add M2M additional_recruiters (multiple additional recruiters per vacancy)

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('vacancies', '0022_vacancy_additional_recruiter'),
    ]

    operations = [
        migrations.AddField(
            model_name='vacancy',
            name='additional_recruiters',
            field=models.ManyToManyField(
                blank=True,
                help_text='Дополнительные рекрутеры по вакансии (опционально)',
                limit_choices_to={'groups__name': 'Рекрутер'},
                related_name='vacancies_extra_recruiters',
                to=settings.AUTH_USER_MODEL,
                verbose_name='Дополнительные рекрутеры'
            ),
        ),
    ]
