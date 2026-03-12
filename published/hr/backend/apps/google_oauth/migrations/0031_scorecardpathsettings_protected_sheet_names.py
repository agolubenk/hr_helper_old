# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('google_oauth', '0030_invite_interview_format'),
    ]

    operations = [
        migrations.AddField(
            model_name='scorecardpathsettings',
            name='protected_sheet_names',
            field=models.TextField(
                blank=True,
                default='',
                help_text='Список названий листов (через запятую), которые нельзя удалять при обработке scorecard',
                verbose_name='Защищённые листы scorecard',
            ),
        ),
    ]

