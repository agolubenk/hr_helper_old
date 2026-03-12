# Generated manually: снимок встреч на дату интервью (команда /in)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('google_oauth', '0031_scorecardpathsettings_protected_sheet_names'),
    ]

    operations = [
        migrations.AddField(
            model_name='invite',
            name='meetings_snapshot',
            field=models.JSONField(
                blank=True,
                default=None,
                help_text='События календаря на дату интервью с responseStatus участников (accepted/declined/tentative)',
                null=True,
                verbose_name='Снимок встреч на дату',
            ),
        ),
    ]
