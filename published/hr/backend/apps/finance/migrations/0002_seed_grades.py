from django.db import migrations


def seed_grades(apps, schema_editor):
    Grade = apps.get_model('finance', 'Grade')
    for name in [
        'Junior', 'Junior+', 'Middle', 'Middle+', 'Senior', 'Lead', 'Head',
    ]:
        Grade.objects.get_or_create(name=name)


def unseed_grades(apps, schema_editor):
    Grade = apps.get_model('finance', 'Grade')
    Grade.objects.filter(name__in=['Junior', 'Junior+', 'Middle', 'Middle+', 'Senior', 'Lead', 'Head']).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('finance', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_grades, reverse_code=unseed_grades),
    ]
