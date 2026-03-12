# Copy additional_recruiter to additional_recruiters, then remove the FK

from django.db import migrations


def copy_additional_to_m2m(apps, schema_editor):
    Vacancy = apps.get_model('vacancies', 'Vacancy')
    for v in Vacancy.objects.filter(additional_recruiter_id__isnull=False):
        v.additional_recruiters.add(v.additional_recruiter_id)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('vacancies', '0023_vacancy_additional_recruiters'),
    ]

    operations = [
        migrations.RunPython(copy_additional_to_m2m, noop),
        migrations.RemoveField(
            model_name='vacancy',
            name='additional_recruiter',
        ),
    ]
