# Generated manually for GDriveHuntflowLink model

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('huntflow', '0012_resume_id_lookup'),
    ]

    operations = [
        migrations.CreateModel(
            name='GDriveHuntflowLink',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('gdrive_file_id', models.CharField(db_index=True, help_text='Уникальный ID файла из URL Google Drive', max_length=100, unique=True, verbose_name='ID файла Google Drive')),
                ('gdrive_url', models.URLField(blank=True, max_length=500, verbose_name='URL файла Google Drive')),
                ('huntflow_url', models.URLField(max_length=800, verbose_name='Ссылка Huntflow')),
                ('applicant_id', models.IntegerField(blank=True, null=True, verbose_name='ID кандидата в Huntflow')),
                ('account_id', models.IntegerField(blank=True, null=True, verbose_name='ID организации в Huntflow')),
                ('vacancy_id', models.IntegerField(blank=True, null=True, verbose_name='ID вакансии')),
                ('vacancy_name', models.CharField(blank=True, max_length=255, verbose_name='Название вакансии')),
                ('candidate_name', models.CharField(blank=True, max_length=255, verbose_name='ФИО кандидата')),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now, verbose_name='Создано')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Обновлено')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_gdrive_huntflow_links', to=settings.AUTH_USER_MODEL, verbose_name='Кто создал')),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='updated_gdrive_huntflow_links', to=settings.AUTH_USER_MODEL, verbose_name='Кто обновил')),
            ],
            options={
                'verbose_name': 'Связка GDrive↔Huntflow',
                'verbose_name_plural': 'Связки GDrive↔Huntflow',
                'ordering': ('-updated_at',),
            },
        ),
        migrations.AddIndex(
            model_name='gdrivehuntflowlink',
            index=models.Index(fields=['gdrive_file_id'], name='huntflow_gd_gdrive__123456_idx'),
        ),
    ]
