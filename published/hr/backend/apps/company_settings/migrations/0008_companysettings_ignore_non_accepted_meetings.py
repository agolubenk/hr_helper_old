# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('company_settings', '0007_vacancyprompt_vacancyprompthistory'),
    ]

    operations = [
        migrations.AddField(
            model_name='companysettings',
            name='ignore_non_accepted_meetings',
            field=models.BooleanField(
                default=False,
                help_text='Если включено, встречи без подтверждения (не принятые) будут игнорироваться при расчёте занятости',
                verbose_name='Игнорировать не принятые встречи',
            ),
        ),
    ]
