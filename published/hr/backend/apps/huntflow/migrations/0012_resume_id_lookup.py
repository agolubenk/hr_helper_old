# Миграция: поиск по resume_id вместо полного URL
# resume_id = часть пути после /resume/ — один ID для всех доменов (hh.ru, rabota.by, gomel.rabota.by и т.д.)

import re
from django.db import migrations, models


def extract_resume_id(url):
    if not url:
        return None
    m = re.search(r"/resume/([^/?#]+)", url, re.IGNORECASE)
    return m.group(1) if m else None


def populate_resume_id(apps, schema_editor):
    ResumeHuntflowLink = apps.get_model('huntflow', 'ResumeHuntflowLink')
    for obj in ResumeHuntflowLink.objects.all():
        rid = extract_resume_id(obj.resume_url)
        if rid:
            obj.resume_id = rid
            obj.save(update_fields=['resume_id'])
        else:
            # Fallback: использовать хэш URL если путь не /resume/...
            obj.resume_id = f"legacy_{obj.id}"
            obj.save(update_fields=['resume_id'])


def reverse_populate(apps, schema_editor):
    pass  # Нельзя восстановить resume_url из resume_id


class Migration(migrations.Migration):

    dependencies = [
        ('huntflow', '0011_shared_links_and_audit'),
    ]

    operations = [
        migrations.AddField(
            model_name='resumehuntflowlink',
            name='resume_id',
            field=models.CharField(
                db_index=True,
                help_text='Уникальный ID из URL, напр. 1a6de8370007670893003b77395447734e764e',
                max_length=100,
                null=True,
                unique=True,
                verbose_name='ID резюме (из пути /resume/{id})',
            ),
        ),
        migrations.RunPython(populate_resume_id, reverse_populate),
        migrations.AlterField(
            model_name='resumehuntflowlink',
            name='resume_id',
            field=models.CharField(
                db_index=True,
                help_text='Уникальный ID из URL, напр. 1a6de8370007670893003b77395447734e764e',
                max_length=100,
                unique=True,
                verbose_name='ID резюме (из пути /resume/{id})',
            ),
        ),
        migrations.AlterField(
            model_name='resumehuntflowlink',
            name='resume_url',
            field=models.URLField(
                blank=True,
                help_text='Канонический URL для отображения (hh.ru или rabota.by)',
                max_length=500,
                verbose_name='URL страницы резюме (канонический)',
            ),
        ),
        migrations.RemoveIndex(
            model_name='resumehuntflowlink',
            name='huntflow_re_resume_url_idx',
        ),
    ]
