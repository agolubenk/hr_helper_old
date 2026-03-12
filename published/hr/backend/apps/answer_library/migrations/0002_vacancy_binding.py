# Generated for answer_library: vacancy binding for topics and sessions

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('answer_library', '0001_initial'),
        ('vacancies', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='triggertopic',
            name='vacancy',
            field=models.ForeignKey(
                blank=True,
                help_text='Если не указана — тема применяется ко всем вакансиям',
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='answer_library_topics',
                to='vacancies.vacancy',
                verbose_name='Вакансия',
            ),
        ),
        migrations.AddField(
            model_name='answerlibrarysession',
            name='vacancy',
            field=models.ForeignKey(
                blank=True,
                help_text='Выбранная вакансия для ответов (подтягиваются только темы для неё и общие)',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='answer_library_sessions',
                to='vacancies.vacancy',
                verbose_name='Вакансия',
            ),
        ),
    ]
