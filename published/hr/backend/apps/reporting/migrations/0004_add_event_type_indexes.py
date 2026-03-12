# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('reporting', '0003_calendarevent_event_type'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='calendarevent',
            index=models.Index(fields=['event_type'], name='reporting_c_event_t_idx'),
        ),
        migrations.AddIndex(
            model_name='calendarevent',
            index=models.Index(fields=['recruiter', 'event_type', 'start_time'], name='reporting_c_recruit_event_idx'),
        ),
    ]







