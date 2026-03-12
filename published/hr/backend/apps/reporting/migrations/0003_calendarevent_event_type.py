# Generated manually

from django.db import migrations, models


def determine_event_type_from_title(title):
    """Определяет тип события на основе названия"""
    if not title:
        return 'unknown'
    
    title_lower = title.lower()
    
    # Ключевые слова для интервью (приоритет выше)
    interview_keywords = ['interview', 'интервью']
    for keyword in interview_keywords:
        if keyword in title_lower:
            return 'interview'
    
    # Ключевые слова для скрининга
    screening_keywords = ['screening', 'screen', 'скрининг', 'скрин', 'скриннинг']
    for keyword in screening_keywords:
        if keyword in title_lower:
            return 'screening'
    
    return 'unknown'


def set_event_types(apps, schema_editor):
    """Устанавливает типы событий для существующих записей"""
    CalendarEvent = apps.get_model('reporting', 'CalendarEvent')
    for event in CalendarEvent.objects.all():
        event.event_type = determine_event_type_from_title(event.title)
        event.save(update_fields=['event_type'])


class Migration(migrations.Migration):

    dependencies = [
        ('reporting', '0002_calendarevent'),
    ]

    operations = [
        migrations.AddField(
            model_name='calendarevent',
            name='event_type',
            field=models.CharField(
                choices=[('screening', 'Скрининг'), ('interview', 'Интервью'), ('unknown', 'Не определено')],
                default='unknown',
                help_text='Определяется автоматически на основе названия события',
                max_length=20,
                verbose_name='Тип события'
            ),
        ),
        migrations.RunPython(set_event_types, migrations.RunPython.noop),
    ]







