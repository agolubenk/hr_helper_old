# Generated manually for company_settings work_start_time / work_end_time

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('company_settings', '0008_companysettings_ignore_non_accepted_meetings'),
    ]

    operations = [
        migrations.AddField(
            model_name='companysettings',
            name='work_start_time',
            field=models.TimeField(
                blank=True,
                help_text='Время начала рабочего дня для планирования интервью. Пусто — использовать настройки из профиля пользователя.',
                null=True,
                verbose_name='Начало рабочего времени компании',
            ),
        ),
        migrations.AddField(
            model_name='companysettings',
            name='work_end_time',
            field=models.TimeField(
                blank=True,
                help_text='Время окончания рабочего дня для планирования интервью. Пусто — использовать настройки из профиля пользователя.',
                null=True,
                verbose_name='Конец рабочего времени компании',
            ),
        ),
    ]
