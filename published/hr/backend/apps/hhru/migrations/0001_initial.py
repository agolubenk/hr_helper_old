# Generated manually for HeadHunter.ru integration

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='HHruOAuthConfig',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255, verbose_name='Название')),
                ('client_id', models.CharField(max_length=512, verbose_name='Client ID')),
                ('client_secret', models.CharField(max_length=512, verbose_name='Client Secret')),
                ('redirect_uri', models.URLField(max_length=1024, verbose_name='Redirect URI')),
                ('is_active', models.BooleanField(default=True, verbose_name='Активна')),
                ('is_default', models.BooleanField(default=False, verbose_name='По умолчанию')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Создано')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Обновлено')),
            ],
            options={
                'verbose_name': 'Конфигурация OAuth HH.ru',
                'verbose_name_plural': 'Конфигурации OAuth HH.ru',
                'ordering': ['-is_default', '-created_at'],
            },
        ),
        migrations.CreateModel(
            name='HHruOAuthAccount',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('access_token', models.TextField(verbose_name='Access Token')),
                ('refresh_token', models.TextField(blank=True, null=True, verbose_name='Refresh Token')),
                ('token_expires_at', models.DateTimeField(blank=True, null=True, verbose_name='Токен истекает')),
                ('hh_user_id', models.CharField(blank=True, max_length=64, verbose_name='HH User ID')),
                ('first_name', models.CharField(blank=True, max_length=255, verbose_name='Имя')),
                ('last_name', models.CharField(blank=True, max_length=255, verbose_name='Фамилия')),
                ('middle_name', models.CharField(blank=True, max_length=255, null=True, verbose_name='Отчество')),
                ('email', models.EmailField(blank=True, max_length=254, verbose_name='Email')),
                ('is_employer', models.BooleanField(default=False, verbose_name='Работодатель')),
                ('is_admin', models.BooleanField(default=False, verbose_name='Администратор')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Создано')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Обновлено')),
                ('config', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='accounts', to='hhru.hhruoauthconfig', verbose_name='Конфигурация OAuth')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='hhru_oauth_accounts', to=settings.AUTH_USER_MODEL, verbose_name='Пользователь')),
            ],
            options={
                'verbose_name': 'Аккаунт HH.ru',
                'verbose_name_plural': 'Аккаунты HH.ru',
                'ordering': ['-created_at'],
                'unique_together': {('user', 'hh_user_id')},
            },
        ),
        migrations.CreateModel(
            name='HHruApiLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('method', models.CharField(default='GET', max_length=10)),
                ('endpoint', models.CharField(max_length=1024)),
                ('status_code', models.PositiveIntegerField(blank=True, null=True)),
                ('log_type', models.CharField(choices=[('GET', 'GET'), ('POST', 'POST'), ('PUT', 'PUT'), ('PATCH', 'PATCH'), ('DELETE', 'DELETE'), ('ERROR', 'Ошибка')], default='GET', max_length=10)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('account', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='api_logs', to='hhru.hhruoauthaccount')),
            ],
            options={
                'verbose_name': 'Лог API HH.ru',
                'verbose_name_plural': 'Логи API HH.ru',
                'ordering': ['-created_at'],
            },
        ),
    ]
