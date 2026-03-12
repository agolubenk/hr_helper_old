# Generated manually for hiring plan requests

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('clickup_int', '0011_add_hiring_plan_folder'),
    ]

    operations = [
        migrations.CreateModel(
            name='ClickUpHiringRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('clickup_task_id', models.CharField(db_index=True, max_length=100, verbose_name='ID задачи ClickUp')),
                ('name', models.CharField(blank=True, max_length=500, verbose_name='Название')),
                ('clickup_status', models.CharField(blank=True, max_length=100, verbose_name='Статус в ClickUp')),
                ('date_created', models.DateTimeField(blank=True, null=True, verbose_name='Дата создания в ClickUp')),
                ('date_updated', models.DateTimeField(blank=True, null=True, verbose_name='Дата обновления в ClickUp')),
                ('start_date', models.DateTimeField(blank=True, null=True, verbose_name='Дата начала')),
                ('due_date', models.DateTimeField(blank=True, null=True, verbose_name='Срок')),
                ('list_id', models.CharField(blank=True, db_index=True, max_length=100, verbose_name='ID списка (спринт)')),
                ('list_name', models.CharField(blank=True, max_length=255, verbose_name='Название списка (спринт)')),
                ('folder_id', models.CharField(blank=True, db_index=True, max_length=100, verbose_name='ID папки')),
                ('request_type', models.CharField(choices=[('hiring', 'Найм'), ('transfer', 'Перевод'), ('unknown', 'Не определено')], default='unknown', max_length=20, verbose_name='Тип заявки')),
                ('normalized_status', models.CharField(blank=True, help_text='Маппинг статуса ClickUp в единый статус системы', max_length=100, verbose_name='Нормализованный статус')),
                ('department', models.CharField(blank=True, max_length=255, verbose_name='Отдел/группа')),
                ('assignees', models.JSONField(blank=True, default=list, verbose_name='Ответственные (JSON)')),
                ('creator', models.JSONField(blank=True, default=dict, verbose_name='Создатель (JSON)')),
                ('custom_fields', models.JSONField(blank=True, default=dict, verbose_name='Кастомные поля ClickUp')),
                ('raw_task', models.JSONField(blank=True, default=dict, verbose_name='Слепок задачи (для отладки)')),
                ('synced_at', models.DateTimeField(auto_now=True, verbose_name='Время последней синхронизации')),
                ('recruiter', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='assigned_clickup_hiring_requests', to=settings.AUTH_USER_MODEL, verbose_name='Рекрутер')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='clickup_hiring_requests', to=settings.AUTH_USER_MODEL, verbose_name='Пользователь')),
            ],
            options={
                'verbose_name': 'Заявка плана найма (ClickUp)',
                'verbose_name_plural': 'Заявки плана найма (ClickUp)',
                'db_table': 'clickup_hiring_requests',
                'ordering': ['-date_updated', '-synced_at'],
            },
        ),
        migrations.AddConstraint(
            model_name='clickuphiringrequest',
            constraint=models.UniqueConstraint(fields=('user', 'clickup_task_id'), name='unique_user_clickup_task_hiring'),
        ),
    ]
