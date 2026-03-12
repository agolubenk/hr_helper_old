# Migration: HHruResumeHuntflowCheck model

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hhru', '0002_vacancy_links_and_employer_id'),
    ]

    operations = [
        migrations.CreateModel(
            name='HHruResumeHuntflowCheck',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('resume_id', models.CharField(db_index=True, max_length=100, unique=True, verbose_name='ID резюме HH.ru')),
                ('status', models.CharField(choices=[('pending', 'Проверка'), ('found', 'Найден в Huntflow'), ('not_found', 'Нужно добавить')], default='pending', max_length=20, verbose_name='Статус')),
                ('huntflow_url', models.URLField(blank=True, max_length=800, verbose_name='Ссылка Huntflow')),
                ('checked_at', models.DateTimeField(blank=True, null=True, verbose_name='Проверено')),
            ],
            options={
                'verbose_name': 'Проверка HH резюме → Huntflow',
                'verbose_name_plural': 'Проверки HH резюме → Huntflow',
                'ordering': ['-checked_at'],
            },
        ),
    ]
