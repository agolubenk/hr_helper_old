# Generated manually

from django.db import migrations, models
import django.db.models.deletion


def determine_vacancy_for_events(apps, schema_editor):
    """Определяет вакансии для существующих событий"""
    CalendarEvent = apps.get_model('reporting', 'CalendarEvent')
    Vacancy = apps.get_model('vacancies', 'Vacancy')
    
    def determine_event_type(title):
        """Определяет тип события"""
        if not title:
            return 'unknown'
        title_lower = title.lower()
        if 'interview' in title_lower or 'интервью' in title_lower:
            return 'interview'
        if 'screening' in title_lower or 'screen' in title_lower or 'скрининг' in title_lower or 'скрин' in title_lower:
            return 'screening'
        return 'unknown'
    
    def titles_match(title1, title2):
        """Проверяет совпадение названий"""
        if not title1 or not title2:
            return False
        normalized1 = ' '.join(title1.lower().strip().split())
        normalized2 = ' '.join(title2.lower().strip().split())
        words1 = set(normalized1.split())
        words2 = set(normalized2.split())
        common_words = words1.intersection(words2)
        if len(common_words) >= 2:
            return True
        if normalized1 in normalized2 or normalized2 in normalized1:
            return True
        return False
    
    vacancies = Vacancy.objects.filter(is_active=True)
    updated_count = 0
    
    for event in CalendarEvent.objects.all():
        if not event.title:
            continue
        
        title_lower = event.title.lower().strip()
        event_type = determine_event_type(event.title)
        matched_vacancy = None
        
        # Для скринингов ищем по invite_title
        if event_type == 'screening':
            for vacancy in vacancies:
                if vacancy.invite_title:
                    invite_title_lower = vacancy.invite_title.lower().strip()
                    if invite_title_lower and (
                        invite_title_lower in title_lower or 
                        title_lower in invite_title_lower or
                        titles_match(event.title, vacancy.invite_title)
                    ):
                        matched_vacancy = vacancy
                        break
        
        # Для интервью ищем по tech_invite_title
        elif event_type == 'interview':
            for vacancy in vacancies:
                if vacancy.tech_invite_title:
                    tech_invite_title_lower = vacancy.tech_invite_title.lower().strip()
                    if tech_invite_title_lower and (
                        tech_invite_title_lower in title_lower or 
                        title_lower in tech_invite_title_lower or
                        titles_match(event.title, vacancy.tech_invite_title)
                    ):
                        matched_vacancy = vacancy
                        break
        
        # Если тип не определен, пробуем оба варианта
        else:
            for vacancy in vacancies:
                if vacancy.tech_invite_title and titles_match(event.title, vacancy.tech_invite_title):
                    matched_vacancy = vacancy
                    break
                if vacancy.invite_title and titles_match(event.title, vacancy.invite_title):
                    matched_vacancy = vacancy
                    break
        
        if matched_vacancy:
            event.vacancy = matched_vacancy
            event.save(update_fields=['vacancy'])
            updated_count += 1


class Migration(migrations.Migration):

    dependencies = [
        ('reporting', '0004_add_event_type_indexes'),
        ('vacancies', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='calendarevent',
            name='vacancy',
            field=models.ForeignKey(
                blank=True,
                help_text='Определяется автоматически на основе соответствия названия события с заголовками инвайтов',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='calendar_events',
                to='vacancies.vacancy',
                verbose_name='Вакансия'
            ),
        ),
        migrations.RunPython(determine_vacancy_for_events, migrations.RunPython.noop),
    ]







