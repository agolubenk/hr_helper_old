# Generated manually for additional_recruiter field

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('vacancies', '0021_vacancy_use_common_prompt'),
    ]

    operations = [
        migrations.AddField(
            model_name='vacancy',
            name='additional_recruiter',
            field=models.ForeignKey(
                blank=True,
                help_text='Дополнительный рекрутер по вакансии (опционально)',
                limit_choices_to={'groups__name': 'Рекрутер'},
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='vacancies_as_additional_recruiter',
                to=settings.AUTH_USER_MODEL,
                verbose_name='Дополнительный рекрутер'
            ),
        ),
    ]
