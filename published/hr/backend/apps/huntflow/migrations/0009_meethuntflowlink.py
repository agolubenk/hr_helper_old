# Generated manually: связка Google Meet ↔ Huntflow для расширения

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('huntflow', '0008_leveltext_vacancy_name'),
    ]

    operations = [
        migrations.CreateModel(
            name='MeetHuntflowLink',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('meet_code', models.CharField(db_index=True, help_text='Часть URL после meet.google.com/, например xim-pyga-awt', max_length=100, verbose_name='Код встречи Google Meet')),
                ('meet_url', models.URLField(blank=True, help_text='Полная ссылка на встречу (https://meet.google.com/...)', max_length=500, verbose_name='Полный URL встречи')),
                ('account_id', models.IntegerField(blank=True, null=True, verbose_name='Huntflow account_id')),
                ('applicant_id', models.IntegerField(blank=True, null=True, verbose_name='Huntflow applicant_id')),
                ('vacancy_id', models.IntegerField(blank=True, null=True, verbose_name='Huntflow vacancy_id')),
                ('candidate_name', models.CharField(blank=True, max_length=255, verbose_name='Имя кандидата')),
                ('vacancy_title', models.CharField(blank=True, max_length=255, verbose_name='Название вакансии')),
                ('candidate_grade', models.CharField(blank=True, max_length=100, verbose_name='Грейд/уровень')),
                ('scorecard_url', models.URLField(blank=True, max_length=800, verbose_name='Ссылка на Scorecard')),
                ('huntflow_candidate_url', models.URLField(blank=True, max_length=800, verbose_name='Ссылка на кандидата в Huntflow')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Создано')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Обновлено')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='meet_huntflow_links', to=settings.AUTH_USER_MODEL, verbose_name='Пользователь')),
            ],
            options={
                'verbose_name': 'Связка Meet↔Huntflow',
                'verbose_name_plural': 'Связки Meet↔Huntflow',
                'unique_together': {('user', 'meet_code')},
            },
        ),
        migrations.AddIndex(
            model_name='meethuntflowlink',
            index=models.Index(fields=['user', 'meet_code'], name='huntflow_me_user_id_meet_code_idx'),
        ),
    ]
