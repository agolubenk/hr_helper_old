# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('google_oauth', '0029_change_hr_screening_to_hrscreening'),
    ]

    operations = [
        migrations.AddField(
            model_name='invite',
            name='interview_format',
            field=models.CharField(blank=True, choices=[('online', 'Онлайн'), ('office', 'Офис')], default='online', help_text='Формат проведения интервью: онлайн (видеозвонок) или офис (личная встреча)', max_length=10, verbose_name='Формат интервью'),
        ),
    ]

