# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('reporting', '0005_calendarevent_vacancy'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='calendarevent',
            index=models.Index(fields=['vacancy'], name='reporting_c_vacancy_idx'),
        ),
        migrations.AddIndex(
            model_name='calendarevent',
            index=models.Index(fields=['vacancy', 'event_type', 'start_time'], name='reporting_c_vacancy_event_idx'),
        ),
    ]







