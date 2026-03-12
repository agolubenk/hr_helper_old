# Общие связи для всех пользователей; аудит created_by/updated_by.
# LinkedIn/Resume/Meet/LevelText — без user; уникальность по natural key.
# Слияние дубликатов перед удалением user.

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def copy_user_to_audit(apps, schema_editor):
    """Копируем user в created_by и updated_by перед удалением user."""
    LinkedInHuntflowLink = apps.get_model('huntflow', 'LinkedInHuntflowLink')
    ResumeHuntflowLink = apps.get_model('huntflow', 'ResumeHuntflowLink')
    MeetHuntflowLink = apps.get_model('huntflow', 'MeetHuntflowLink')
    LevelText = apps.get_model('huntflow', 'LevelText')

    for model, has_user_attr in [
        (LinkedInHuntflowLink, True),
        (ResumeHuntflowLink, True),
        (MeetHuntflowLink, True),
        (LevelText, True),
    ]:
        if not has_user_attr:
            continue
        for obj in model.objects.all():
            if getattr(obj, 'user_id', None):
                obj.created_by_id = obj.user_id
                obj.updated_by_id = obj.user_id
                obj.save(update_fields=['created_by_id', 'updated_by_id'])


def merge_duplicates(apps, schema_editor):
    """Оставляем по одной записи на natural key (по последнему updated_at)."""
    LinkedInHuntflowLink = apps.get_model('huntflow', 'LinkedInHuntflowLink')
    ResumeHuntflowLink = apps.get_model('huntflow', 'ResumeHuntflowLink')
    MeetHuntflowLink = apps.get_model('huntflow', 'MeetHuntflowLink')
    LevelText = apps.get_model('huntflow', 'LevelText')

    # LinkedIn: по linkedin_url
    seen = {}
    for obj in LinkedInHuntflowLink.objects.order_by('linkedin_url', '-updated_at'):
        if obj.linkedin_url not in seen:
            seen[obj.linkedin_url] = obj.id
        else:
            obj.delete()

    # Resume: по resume_url (нормализуем до ?)
    seen = {}
    for obj in ResumeHuntflowLink.objects.order_by('resume_url', '-updated_at'):
        url = obj.resume_url.split('?')[0] if obj.resume_url else ''
        if url not in seen:
            seen[url] = obj.id
            if '?' in (obj.resume_url or ''):
                obj.resume_url = url
                obj.save(update_fields=['resume_url'])
        else:
            obj.delete()

    # Meet: по meet_code
    seen = {}
    for obj in MeetHuntflowLink.objects.order_by('meet_code', '-updated_at'):
        if obj.meet_code not in seen:
            seen[obj.meet_code] = obj.id
        else:
            obj.delete()

    # LevelText: по (vacancy_name, level)
    seen = {}
    for obj in LevelText.objects.order_by('vacancy_name', 'level', '-updated_at'):
        key = (obj.vacancy_name or '', obj.level or '')
        if key not in seen:
            seen[key] = obj.id
        else:
            obj.delete()


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('huntflow', '0010_resumehuntflowlink'),
    ]

    operations = [
        # 1. Добавляем поля аудита (nullable)
        migrations.AddField(
            model_name='linkedinhuntflowlink',
            name='created_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='created_linkedin_huntflow_links',
                to=settings.AUTH_USER_MODEL,
                verbose_name='Кто создал',
            ),
        ),
        migrations.AddField(
            model_name='linkedinhuntflowlink',
            name='updated_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='updated_linkedin_huntflow_links',
                to=settings.AUTH_USER_MODEL,
                verbose_name='Кто обновил',
            ),
        ),
        migrations.AddField(
            model_name='resumehuntflowlink',
            name='created_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='created_resume_huntflow_links',
                to=settings.AUTH_USER_MODEL,
                verbose_name='Кто создал',
            ),
        ),
        migrations.AddField(
            model_name='resumehuntflowlink',
            name='updated_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='updated_resume_huntflow_links',
                to=settings.AUTH_USER_MODEL,
                verbose_name='Кто обновил',
            ),
        ),
        migrations.AddField(
            model_name='meethuntflowlink',
            name='created_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='created_meet_huntflow_links',
                to=settings.AUTH_USER_MODEL,
                verbose_name='Кто создал',
            ),
        ),
        migrations.AddField(
            model_name='meethuntflowlink',
            name='updated_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='updated_meet_huntflow_links',
                to=settings.AUTH_USER_MODEL,
                verbose_name='Кто обновил',
            ),
        ),
        migrations.AddField(
            model_name='leveltext',
            name='created_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='created_level_texts',
                to=settings.AUTH_USER_MODEL,
                verbose_name='Кто создал',
            ),
        ),
        migrations.AddField(
            model_name='leveltext',
            name='updated_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='updated_level_texts',
                to=settings.AUTH_USER_MODEL,
                verbose_name='Кто обновил',
            ),
        ),
        migrations.RunPython(copy_user_to_audit, migrations.RunPython.noop),
        migrations.RunPython(merge_duplicates, migrations.RunPython.noop),
        # 2. Удаляем unique_together и индексы с user, затем поле user
        migrations.AlterUniqueTogether(
            name='linkedinhuntflowlink',
            unique_together=set(),
        ),
        migrations.RemoveIndex(
            model_name='linkedinhuntflowlink',
            name='huntflow_li_user_li_8fa0a1_idx',
        ),
        migrations.RemoveIndex(
            model_name='linkedinhuntflowlink',
            name='huntflow_li_user_ac_b6ed03_idx',
        ),
        migrations.RemoveField(
            model_name='linkedinhuntflowlink',
            name='user',
        ),
        migrations.AlterUniqueTogether(
            name='resumehuntflowlink',
            unique_together=set(),
        ),
        migrations.RemoveIndex(
            model_name='resumehuntflowlink',
            name='huntflow_re_user_id_idx',
        ),
        migrations.RemoveField(
            model_name='resumehuntflowlink',
            name='user',
        ),
        migrations.AlterUniqueTogether(
            name='meethuntflowlink',
            unique_together=set(),
        ),
        migrations.RemoveIndex(
            model_name='meethuntflowlink',
            name='huntflow_me_user_id_meet_code_idx',
        ),
        migrations.RemoveField(
            model_name='meethuntflowlink',
            name='user',
        ),
        migrations.AlterUniqueTogether(
            name='leveltext',
            unique_together=set(),
        ),
        migrations.RemoveIndex(
            model_name='leveltext',
            name='huntflow_le_user_id_vacancy_level_idx',
        ),
        migrations.RemoveField(
            model_name='leveltext',
            name='user',
        ),
        # 3. Уникальность по natural key и новые индексы
        migrations.AlterField(
            model_name='linkedinhuntflowlink',
            name='linkedin_url',
            field=models.URLField(max_length=500, unique=True, verbose_name='LinkedIn URL'),
        ),
        migrations.AddIndex(
            model_name='linkedinhuntflowlink',
            index=models.Index(fields=['linkedin_url'], name='huntflow_li_linkedin_uidx'),
        ),
        migrations.AddIndex(
            model_name='linkedinhuntflowlink',
            index=models.Index(fields=['account_id', 'applicant_id'], name='huntflow_li_account_app_idx'),
        ),
        migrations.AlterField(
            model_name='resumehuntflowlink',
            name='resume_url',
            field=models.URLField(max_length=500, unique=True, verbose_name='URL страницы резюме'),
        ),
        migrations.AddIndex(
            model_name='resumehuntflowlink',
            index=models.Index(fields=['resume_url'], name='huntflow_re_resume_url_idx'),
        ),
        migrations.AlterField(
            model_name='meethuntflowlink',
            name='meet_code',
            field=models.CharField(
                db_index=True,
                help_text='Часть URL после meet.google.com/, например xim-pyga-awt',
                max_length=100,
                unique=True,
                verbose_name='Код встречи Google Meet',
            ),
        ),
        migrations.AddIndex(
            model_name='leveltext',
            index=models.Index(fields=['vacancy_name', 'level'], name='huntflow_le_vacancy_level_idx'),
        ),
        migrations.AlterUniqueTogether(
            name='leveltext',
            unique_together={('vacancy_name', 'level')},
        ),
    ]
