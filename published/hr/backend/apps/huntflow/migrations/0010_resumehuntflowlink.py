# ResumeHuntflowLink: связка страница резюме (hh.ru/rabota.by) → Huntflow для отображения на /extension/

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('huntflow', '0009_meethuntflowlink'),
    ]

    operations = [
        migrations.CreateModel(
            name='ResumeHuntflowLink',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('resume_url', models.URLField(max_length=500, verbose_name='URL страницы резюме')),
                ('huntflow_url', models.URLField(max_length=800, verbose_name='Ссылка Huntflow')),
                ('vacancy_name', models.CharField(blank=True, max_length=255, verbose_name='Название вакансии')),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now, verbose_name='Создано')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Обновлено')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='resume_huntflow_links', to=settings.AUTH_USER_MODEL, verbose_name='Пользователь')),
            ],
            options={
                'verbose_name': 'Связка резюме↔Huntflow',
                'verbose_name_plural': 'Связки резюме↔Huntflow',
                'ordering': ('-updated_at',),
                'unique_together': {('user', 'resume_url')},
            },
        ),
        migrations.AddIndex(
            model_name='resumehuntflowlink',
            index=models.Index(fields=['user'], name='huntflow_re_user_id_idx'),
        ),
    ]
