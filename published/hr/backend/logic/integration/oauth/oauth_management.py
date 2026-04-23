"""Управление OAuth интеграциями"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext as _
from datetime import datetime, timedelta
from django.contrib.auth import get_user_model, login
from django import forms
import json

from apps.google_oauth.models import GoogleOAuthAccount, ScorecardPathSettings, SlotsSettings
from logic.integration.oauth.oauth_services import (
    GoogleOAuthService, 
    GoogleCalendarService, 
    GoogleDriveService, 
    GoogleSheetsService
)
from logic.base.response_handler import UnifiedResponseHandler

User = get_user_model()


def determine_action_type_from_text(text):
    """Определение типа действия из текста"""
    if not text:
        return "hrscreening"
    
    import re
    
    # Паттерны для дат
    date_patterns = [
        r'(\d{4}-\d{1,2}-\d{1,2})',  # 2025-09-15
        r'(\d{2}\.\d{2}\.\d{4})',    # 15.09.2025
        r'(\d{2}\d{2}\d{4})'         # 15092025
    ]
    
    # Паттерны для времени
    time_patterns = [
        r'(\d{1,2}:\d{2})',          # 14:00, 9:30
        r'(\d{1,2}\d{2}\d{4})',      # 140000
    ]
    
    # Дни недели
    weekdays = [
        'понедельник', 'вторник', 'среда', 'четверг', 'пятница', 'суббота', 'воскресенье',
        'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday',
        'пн', 'вт', 'ср', 'чт', 'пт', 'сб', 'вс'
    ]
    
    text_lower = text.lower()
    
    # Проверяем наличие дат и времени
    has_date = any(re.search(pattern, text) for pattern in date_patterns)
    has_time = any(re.search(pattern, text) for pattern in time_patterns)
    has_weekday = any(day in text_lower for day in weekdays)
    
    if has_date or has_time or has_weekday:
        return "interview_scheduling"
    
    # Проверяем ключевые слова для HR скрининга
    hr_keywords = [
        'скрининг', 'собеседование', 'интервью', 'hr', 'рекрутер',
        'screening', 'interview', 'hr screening'
    ]
    
    if any(keyword in text_lower for keyword in hr_keywords):
        return "hrscreening"
    
    return "hrscreening"


@login_required
def google_oauth_start(request):
    """Начало OAuth процесса с Google"""
    try:
        oauth_service = GoogleOAuthService(request.user)
        auth_url, _ = oauth_service.get_authorization_url()
        
        if auth_url:
            return redirect(auth_url)
        else:
            messages.error(request, 'Ошибка получения URL авторизации Google')
            return redirect('accounts:profile')
            
    except Exception as e:
        messages.error(request, f'Ошибка начала OAuth: {str(e)}')
        return redirect('accounts:profile')


@login_required
def google_oauth_callback(request):
    """Обработка callback от Google OAuth"""
    try:
        oauth_service = GoogleOAuthService(request.user)
        result = oauth_service.handle_oauth_callback(request)
        
        if result['success']:
            messages.success(request, result['message'])
            return redirect('google_oauth:dashboard')
        else:
            messages.error(request, result['error'])
            return redirect('accounts:profile')
            
    except Exception as e:
        messages.error(request, f'Ошибка обработки OAuth callback: {str(e)}')
        return redirect('accounts:profile')


@login_required
def google_oauth_dashboard(request):
    """Дашборд Google OAuth"""
    try:
        oauth_account = None
        is_connected = False
        
        try:
            oauth_account = GoogleOAuthAccount.objects.get(user=request.user)
            is_connected = True
        except GoogleOAuthAccount.DoesNotExist:
            pass
        
        if not is_connected:
            messages.warning(request, 'Google аккаунт не подключен')
            return render(request, 'google_oauth/not_connected.html')
        
        # Получаем статистику
        stats = {}
        if oauth_account:
            calendar_service = GoogleCalendarService(oauth_account)
            drive_service = GoogleDriveService(oauth_account)
            sheets_service = GoogleSheetsService(oauth_account)
            
            try:
                stats['calendar_events'] = calendar_service.get_events_count()
                stats['drive_files'] = drive_service.get_files_count()
                stats['sheets'] = sheets_service.get_sheets_count()
            except Exception as e:
                stats['error'] = str(e)
        
        context = {
            'oauth_account': oauth_account,
            'is_connected': is_connected,
            'stats': stats,
        }
        
        return render(request, 'google_oauth/dashboard.html', context)
        
    except Exception as e:
        messages.error(request, f'Ошибка загрузки дашборда: {str(e)}')
        return render(request, 'google_oauth/dashboard.html', {'error': str(e)})


@login_required
@require_http_methods(["POST"])
def google_oauth_disconnect(request):
    """Отключение Google OAuth аккаунта"""
    try:
        oauth_account = get_object_or_404(GoogleOAuthAccount, user=request.user)
        oauth_service = GoogleOAuthService(request.user)
        
        success = oauth_service.revoke_access()
        
        if success:
            messages.success(request, 'Google аккаунт успешно отключен')
        else:
            messages.warning(request, 'Google аккаунт отключен локально')
        
        return redirect('accounts:profile')
        
    except Exception as e:
        messages.error(request, f'Ошибка отключения Google аккаунта: {str(e)}')
        return redirect('accounts:profile')


@login_required
@require_http_methods(["POST"])
def google_sync_data(request):
    """Синхронизация данных с Google"""
    try:
        oauth_account = get_object_or_404(GoogleOAuthAccount, user=request.user)
        
        # Определяем тип синхронизации
        sync_type = request.POST.get('sync_type', 'all')
        
        results = {}
        
        if sync_type in ['all', 'calendar']:
            calendar_service = GoogleCalendarService(oauth_account)
            results['calendar'] = calendar_service.sync_events()
        
        if sync_type in ['all', 'drive']:
            drive_service = GoogleDriveService(oauth_account)
            results['drive'] = drive_service.sync_files()
        
        if sync_type in ['all', 'sheets']:
            sheets_service = GoogleSheetsService(oauth_account)
            results['sheets'] = sheets_service.sync_sheets()
        
        # Обновляем время последней синхронизации
        oauth_account.last_sync_at = timezone.now()
        oauth_account.save()
        
        messages.success(request, 'Синхронизация данных завершена успешно')
        return redirect('google_oauth:dashboard')
        
    except Exception as e:
        messages.error(request, f'Ошибка синхронизации данных: {str(e)}')
        return redirect('google_oauth:dashboard')


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def google_ai_analysis(request):
    """AI анализ данных Google через Gemini"""
    try:
        data = json.loads(request.body)
        text = data.get('text', '').strip()
        
        if not text:
            return JsonResponse({
                'success': False,
                'error': 'Текст для анализа не может быть пустым'
            })
        
        # Определяем тип действия
        action_type = determine_action_type_from_text(text)
        
        # Используем Gemini для анализа
        if request.user.gemini_api_key:
            from logic.ai_analysis.gemini_services import GeminiService
            gemini_service = GeminiService(
                request.user.gemini_api_key,
                model=getattr(request.user, 'preferred_ai_model', None)
            )
            
            # Формируем промпт в зависимости от типа действия
            if action_type == "interview_scheduling":
                prompt = f"""
                Проанализируй следующий текст и извлеки информацию о планировании интервью:
                - Даты и время
                - Тип интервью
                - Участники
                - Дополнительные детали
                
                Текст: {text}
                
                Ответь в формате JSON.
                """
            else:
                prompt = f"""
                Проанализируй следующий текст для HR скрининга и извлеки:
                - Информацию о кандидате
                - Оценки и комментарии
                - Рекомендации
                - Следующие шаги
                
                Текст: {text}
                
                Ответь в формате JSON.
                """
            
            result = gemini_service.generate_response(prompt)
            
            if result['success']:
                return JsonResponse({
                    'success': True,
                    'action_type': action_type,
                    'analysis': result['response'],
                    'raw_response': result.get('raw_response', {})
                })
            else:
                return JsonResponse({
                    'success': False,
                    'error': result['error']
                })
        else:
            return JsonResponse({
                'success': False,
                'error': 'API ключ Gemini не настроен'
            })
            
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Неверный JSON в запросе'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Внутренняя ошибка: {str(e)}'
        })


@login_required
def google_settings(request):
    """Настройки Google OAuth"""
    try:
        oauth_account = None
        try:
            oauth_account = GoogleOAuthAccount.objects.get(user=request.user)
        except GoogleOAuthAccount.DoesNotExist:
            pass
        
        # Получаем настройки пользователя
        sync_settings, created = SyncSettings.objects.get_or_create(user=request.user)
        scorecard_settings, created = ScorecardPathSettings.objects.get_or_create(user=request.user)
        slots_settings, created = SlotsSettings.objects.get_or_create(user=request.user)
        
        if request.method == 'POST':
            # Обновляем настройки синхронизации
            sync_settings.auto_sync = request.POST.get('auto_sync') == 'on'
            sync_settings.sync_interval = int(request.POST.get('sync_interval', 60))
            sync_settings.save()
            
            # Обновляем настройки scorecard
            scorecard_settings.scorecard_path = request.POST.get('scorecard_path', '')
            scorecard_settings.save()
            
            # Обновляем настройки слотов
            slots_settings.default_duration = int(request.POST.get('default_duration', 60))
            slots_settings.working_hours_start = request.POST.get('working_hours_start', '09:00')
            slots_settings.working_hours_end = request.POST.get('working_hours_end', '18:00')
            slots_settings.save()
            
            messages.success(request, 'Настройки успешно сохранены')
            return redirect('google_oauth:settings')
        
        context = {
            'oauth_account': oauth_account,
            'sync_settings': sync_settings,
            'scorecard_settings': scorecard_settings,
            'slots_settings': slots_settings,
        }
        
        return render(request, 'google_oauth/settings.html', context)
        
    except Exception as e:
        messages.error(request, f'Ошибка загрузки настроек: {str(e)}')
        return render(request, 'google_oauth/settings.html', {'error': str(e)})

