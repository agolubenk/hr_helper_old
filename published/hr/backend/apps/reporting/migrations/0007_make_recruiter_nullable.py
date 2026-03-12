# Generated manually

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('reporting', '0006_add_vacancy_indexes'),
        ('accounts', '0001_initial'),  # Замените на правильную зависимость для User
    ]

    operations = [
        migrations.AlterField(
            model_name='calendarevent',
            name='recruiter',
            field=models.ForeignKey(
                blank=True,
                limit_choices_to={'groups__name': 'Рекрутер'},
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='calendar_events',
                to='accounts.user',
                verbose_name='Рекрутер'
            ),
        ),
    ]
