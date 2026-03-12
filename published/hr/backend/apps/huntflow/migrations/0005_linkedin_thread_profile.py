# Generated manually

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('huntflow', '0004_linkedin_link_target_url_nullable_ids'),
    ]

    operations = [
        migrations.CreateModel(
            name='LinkedInThreadProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('thread_id', models.CharField(help_text='ID треда из URL /messaging/thread/<thread_id>/', max_length=255, verbose_name='LinkedIn Thread ID')),
                ('profile_url', models.URLField(help_text='Нормализованный URL профиля (https://www.linkedin.com/in/<username>/)', max_length=500, verbose_name='LinkedIn Profile URL')),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now, verbose_name='Создано')),
                ('last_accessed_at', models.DateTimeField(default=django.utils.timezone.now, verbose_name='Последний доступ')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='linkedin_thread_profiles', to=settings.AUTH_USER_MODEL, verbose_name='Пользователь')),
            ],
            options={
                'verbose_name': 'Маппинг LinkedIn Thread→Profile',
                'verbose_name_plural': 'Маппинги LinkedIn Thread→Profile',
                'unique_together': {('user', 'thread_id')},
            },
        ),
        migrations.AddIndex(
            model_name='linkedinthreadprofile',
            index=models.Index(fields=['user', 'thread_id'], name='huntflow_li_user_id_c5e8a1_idx'),
        ),
        migrations.AddIndex(
            model_name='linkedinthreadprofile',
            index=models.Index(fields=['user', 'profile_url'], name='huntflow_li_user_id_8f9b2c_idx'),
        ),
    ]
