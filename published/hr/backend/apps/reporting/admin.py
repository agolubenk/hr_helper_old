"""
Админ-панель для приложения отчетности
"""
from django.contrib import admin
from django.contrib.admin import helpers
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.http import HttpResponseRedirect
from django.urls import path, reverse
from django.shortcuts import render
from django.utils.html import format_html
from .models import ReportCache, CalendarEvent
from apps.interviewers.models import Interviewer
from apps.vacancies.models import Vacancy

User = get_user_model()


class InterviewerFilter(admin.SimpleListFilter):
    """Кастомный фильтр по интервьюерам для CalendarEvent"""
    title = 'Интервьюер'
    parameter_name = 'interviewer'

    def lookups(self, request, model_admin):
        """Возвращает список всех активных интервьюеров для фильтра"""
        interviewers = Interviewer.objects.filter(is_active=True).order_by('last_name', 'first_name')
        return [(interviewer.id, interviewer.get_full_name()) for interviewer in interviewers]

    def queryset(self, request, queryset):
        """Фильтрует queryset по выбранному интервьюеру"""
        if self.value():
            interviewer_id = self.value()
            try:
                interviewer = Interviewer.objects.get(id=interviewer_id)
                interviewer_email = interviewer.email.lower()
                
                # Фильтруем события, где email интервьюера присутствует в attendees
                # Используем Q объекты для поиска в JSONField
                return queryset.filter(
                    Q(attendees__icontains=interviewer_email) |
                    Q(attendees__icontains=interviewer.email)
                )
            except Interviewer.DoesNotExist:
                return queryset.none()
        return queryset


@admin.register(ReportCache)
class ReportCacheAdmin(admin.ModelAdmin):
    list_display = ('report_type', 'period', 'start_date', 'end_date', 'recruiter', 'vacancy_id', 'interviewer_id', 'created_at')
    list_filter = ('report_type', 'period', 'created_at')
    search_fields = ('recruiter__username', 'vacancy_id', 'interviewer_id')
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'created_at'


@admin.register(CalendarEvent)
class CalendarEventAdmin(admin.ModelAdmin):
    list_display = ('title', 'recruiter', 'event_type', 'vacancy', 'interviewers_display', 'start_time', 'end_time', 'duration_minutes', 'created_at')
    list_filter = ('event_type', 'recruiter', 'vacancy', InterviewerFilter, 'start_time', 'created_at')
    search_fields = ('title', 'recruiter__username', 'event_id', 'vacancy__name', 'vacancy__external_id')
    readonly_fields = ('duration_minutes', 'created_at', 'updated_at', 'event_id', 'interviewers_display')
    date_hierarchy = 'start_time'
    ordering = ['-start_time']
    actions = ['bulk_change_vacancy', 'bulk_change_event_type', 'bulk_change_recruiter']
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('event_id', 'title', 'recruiter', 'vacancy', 'event_type', 'interviewers_display')
        }),
        ('Время', {
            'fields': ('start_time', 'end_time', 'duration_minutes')
        }),
        ('Дополнительная информация', {
            'fields': ('attendees', 'description', 'location', 'google_updated_at')
        }),
        ('Метаданные', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_readonly_fields(self, request, obj=None):
        if obj:  # Редактирование существующего объекта
            return self.readonly_fields + ('event_id',)
        return self.readonly_fields
    
    def interviewers_display(self, obj):
        """Отображает список интервьюеров из участников события"""
        if not obj.attendees:
            return '—'
        
        interviewer_emails = set()
        for attendee in obj.attendees:
            if isinstance(attendee, dict):
                email = attendee.get('email', '').lower()
            elif isinstance(attendee, str):
                email = attendee.lower()
            else:
                continue
            
            if email:
                interviewer_emails.add(email)
        
        if not interviewer_emails:
            return '—'
        
        # Находим интервьюеров по email
        interviewers = Interviewer.objects.filter(
            email__in=interviewer_emails
        ).order_by('last_name', 'first_name')
        
        if interviewers.exists():
            names = [interviewer.get_full_name() for interviewer in interviewers]
            return ', '.join(names)
        
        return '—'
    
    interviewers_display.short_description = 'Интервьюеры'
    
    def save_model(self, request, obj, form, change):
        """
        Переопределяем сохранение, чтобы автоматически определялись тип и вакансия
        """
        # При сохранении автоматически определяются тип и вакансия через метод save() модели
        super().save_model(request, obj, form, change)
    
    def bulk_change_vacancy(self, request, queryset):
        """Массовое изменение вакансии для выбранных событий"""
        if 'apply' in request.POST:
            # Получаем выбранные ID из POST запроса
            selected_ids = request.POST.getlist(helpers.ACTION_CHECKBOX_NAME)
            vacancy_id = request.POST.get('vacancy')
            
            if not selected_ids:
                self.message_user(
                    request,
                    'Не выбрано ни одного события.',
                    level='ERROR'
                )
                return HttpResponseRedirect(request.get_full_path())
            
            if vacancy_id:
                try:
                    vacancy = Vacancy.objects.get(id=vacancy_id)
                    # Обновляем только выбранные события
                    selected_queryset = CalendarEvent.objects.filter(id__in=selected_ids)
                    updated = selected_queryset.update(vacancy=vacancy)
                    self.message_user(
                        request,
                        f'Вакансия успешно изменена для {updated} событий на "{vacancy.name}".',
                        level='SUCCESS'
                    )
                    return HttpResponseRedirect(request.get_full_path())
                except Vacancy.DoesNotExist:
                    self.message_user(
                        request,
                        'Выбранная вакансия не найдена.',
                        level='ERROR'
                    )
            else:
                self.message_user(
                    request,
                    'Вакансия не выбрана.',
                    level='ERROR'
                )
            return HttpResponseRedirect(request.get_full_path())
        
        # Показываем форму выбора вакансии
        vacancies = Vacancy.objects.all().order_by('name')
        context = {
            'title': 'Массовое изменение вакансии',
            'queryset': queryset,
            'opts': self.model._meta,
            'action_checkbox_name': helpers.ACTION_CHECKBOX_NAME,
            'vacancies': vacancies,
            'count': queryset.count(),
        }
        return render(request, 'admin/reporting/calendarevent/bulk_change_vacancy.html', context)
    
    bulk_change_vacancy.short_description = 'Изменить вакансию для выбранных событий'
    
    def bulk_change_event_type(self, request, queryset):
        """Массовое изменение типа события для выбранных событий"""
        if 'apply' in request.POST:
            # Получаем выбранные ID из POST запроса
            selected_ids = request.POST.getlist(helpers.ACTION_CHECKBOX_NAME)
            event_type = request.POST.get('event_type')
            
            if not selected_ids:
                self.message_user(
                    request,
                    'Не выбрано ни одного события.',
                    level='ERROR'
                )
                return HttpResponseRedirect(request.get_full_path())
            
            if event_type in dict(CalendarEvent.EVENT_TYPE_CHOICES):
                # Обновляем только выбранные события
                selected_queryset = CalendarEvent.objects.filter(id__in=selected_ids)
                updated = selected_queryset.update(event_type=event_type)
                event_type_display = dict(CalendarEvent.EVENT_TYPE_CHOICES)[event_type]
                self.message_user(
                    request,
                    f'Тип события успешно изменен для {updated} событий на "{event_type_display}".',
                    level='SUCCESS'
                )
                return HttpResponseRedirect(request.get_full_path())
            else:
                self.message_user(
                    request,
                    'Неверный тип события.',
                    level='ERROR'
                )
            return HttpResponseRedirect(request.get_full_path())
        
        # Показываем форму выбора типа события
        event_types = CalendarEvent.EVENT_TYPE_CHOICES
        context = {
            'title': 'Массовое изменение типа события',
            'queryset': queryset,
            'opts': self.model._meta,
            'action_checkbox_name': helpers.ACTION_CHECKBOX_NAME,
            'event_types': event_types,
            'count': queryset.count(),
        }
        return render(request, 'admin/reporting/calendarevent/bulk_change_event_type.html', context)
    
    bulk_change_event_type.short_description = 'Изменить тип события для выбранных событий'
    
    def bulk_change_recruiter(self, request, queryset):
        """Массовое изменение рекрутера для выбранных событий"""
        if 'apply' in request.POST:
            # Получаем выбранные ID из POST запроса
            selected_ids = request.POST.getlist(helpers.ACTION_CHECKBOX_NAME)
            recruiter_id = request.POST.get('recruiter')
            
            if not selected_ids:
                self.message_user(
                    request,
                    'Не выбрано ни одного события.',
                    level='ERROR'
                )
                return HttpResponseRedirect(request.get_full_path())
            
            if recruiter_id:
                try:
                    recruiter = User.objects.get(id=recruiter_id)
                    # Обновляем только выбранные события
                    selected_queryset = CalendarEvent.objects.filter(id__in=selected_ids)
                    updated = selected_queryset.update(recruiter=recruiter)
                    recruiter_name = recruiter.get_full_name() or recruiter.username
                    self.message_user(
                        request,
                        f'Рекрутер успешно изменен для {updated} событий на "{recruiter_name}".',
                        level='SUCCESS'
                    )
                    return HttpResponseRedirect(request.get_full_path())
                except User.DoesNotExist:
                    self.message_user(
                        request,
                        'Выбранный рекрутер не найден.',
                        level='ERROR'
                    )
            else:
                self.message_user(
                    request,
                    'Рекрутер не выбран.',
                    level='ERROR'
                )
            return HttpResponseRedirect(request.get_full_path())
        
        # Показываем форму выбора рекрутера
        recruiters = User.objects.filter(groups__name='Рекрутер').distinct().order_by('last_name', 'first_name', 'username')
        context = {
            'title': 'Массовое изменение рекрутера',
            'queryset': queryset,
            'opts': self.model._meta,
            'action_checkbox_name': helpers.ACTION_CHECKBOX_NAME,
            'recruiters': recruiters,
            'count': queryset.count(),
        }
        return render(request, 'admin/reporting/calendarevent/bulk_change_recruiter.html', context)
    
    bulk_change_recruiter.short_description = 'Изменить рекрутера для выбранных событий'

