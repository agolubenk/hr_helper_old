# Добавление M2M поля interviewers (все выбранные интервьюеры встречи)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('google_oauth', '0032_invite_meetings_snapshot'),
    ]

    operations = [
        migrations.AddField(
            model_name='invite',
            name='interviewers',
            field=models.ManyToManyField(
                blank=True,
                help_text='Все выбранные интервьюеры встречи',
                related_name='invites',
                to='interviewers.interviewer',
                verbose_name='Интервьюеры',
            ),
        ),
    ]
