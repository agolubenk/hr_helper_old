"""
Документация по проблемным импортам (линтер):
- django.shortcuts, django.contrib.*, django.http, django.views.decorators.*, django.conf,
  django.utils, django.template.loader, django.db, django.core.paginator, django.urls
- google.oauth2.credentials, googleapiclient.discovery
- pytz (обработка таймзон)

Влияние: все представления Google OAuth (аутентификация, календарь, чат, пагинация) и
интеграции с Google API зависят от этих импортов. При их недоступности авторизация Google,
чтение календаря/Drive, постраничная навигация и корректная работа времени перестанут работать.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext as _
from django.template.loader import render_to_string
from datetime import datetime, timedelta, time as dt_time
from django.contrib.auth import get_user_model, login
from django import forms
from django.db import models
import json
import re
from time import time

from .models import GoogleOAuthAccount, ScorecardPathSettings, SlotsSettings, ChatSession, ChatMessage
from logic.integration.oauth.oauth_services import (
    GoogleOAuthService, 
    GoogleCalendarService, 
    GoogleDriveService, 
    GoogleSheetsService
)


def _build_slot_events_both_variants(calendar_events_data, current_user_email_lower):
    """
    Строит оба варианта списков событий для расчёта слотов (один проход по событиям).
    - ignore_non_accepted: слот занят при любом ответе кроме declined (для настройки «игнорировать не принятые» = ДА).
    - consider_non_accepted: слот занят только при accepted (для настройки «не игнорировать» = НЕТ).
    Возвращает: {'ignore_non_accepted': [...], 'consider_non_accepted': [...]}
    """
    list_ignore = []
    list_consider = []
    for event in calendar_events_data:
        if event.get('status') == 'cancelled' or event.get('status') == 'declined':
            continue
        item = {
            'start': event.get('start'),
            'end': event.get('end'),
            'is_all_day': event.get('is_all_day', event.get('isallday', False)),
        }
        if not item['start'] or not item['end']:
            continue
        user_response_status = None
        if current_user_email_lower and event.get('attendees'):
            for attendee in event.get('attendees', []):
                if (attendee.get('email') or '').lower() == current_user_email_lower:
                    user_response_status = (attendee.get('response_status') or attendee.get('responseStatus') or 'needsAction')
                    break
        if user_response_status == 'declined':
            continue
        list_ignore.append(item)
        if user_response_status is None or user_response_status == 'accepted':
            list_consider.append(item)
    return {'ignore_non_accepted': list_ignore, 'consider_non_accepted': list_consider}


def _check_tech_screening_grade_needs_confirmation(user, candidate_url):
    """
    Проверяет, указан ли грейд кандидата в Huntflow.
    Возвращает (needs_confirmation: bool, grade: str).
    Если needs_confirmation=True — на фронте нужно спросить пользователя: создавать встречу без грейда или нет.
    """
    from .models import Invite
    if not candidate_url or not user:
        return False, None
    try:
        invite = Invite(user=user, candidate_url=candidate_url)
        success, _ = invite.parse_candidate_url()
        if not success:
            return False, None
        success, _ = invite.get_candidate_info()
        if not success:
            return False, None
        grade = (invite.candidate_grade or '').strip()
        # Грейд не указан в Huntflow — нужно подтверждение на фронте
        needs = grade.lower() in ('не указан', '') or not grade
        return needs, grade or 'Не указан'
    except Exception as e:
        print(f"⚠️ _check_tech_screening_grade_needs_confirmation: {e}")
        return False, None


def _extract_calendar_id_from_link(calendar_link):
    """Извлекает calendar_id из ссылки на календарь Google Calendar"""
    if not calendar_link:
        return None
    
    # Убираем @ в начале, если есть (например, @https://...)
    if calendar_link.startswith('@'):
        calendar_link = calendar_link[1:]
    
    # Различные форматы ссылок на календарь Google:
    # 1. https://calendar.google.com/calendar/u/0?cid=calendar_id%40gmail.com
    # 2. https://calendar.google.com/calendar/embed?src=c_6neaou3phcsg46u40pjbf6bki8%40group.calendar.google.com&ctz=Europe%2FMinsk
    # 3. calendar_id@gmail.com (email напрямую)
    # 4. @https://calendar.google.com/... (с @ в начале)
    
    # Проверяем, это просто email (без http и без параметров)
    if '@' in calendar_link and 'http' not in calendar_link and '?' not in calendar_link:
        return calendar_link
    
    # Извлекаем calendar_id из разных форматов ссылок
    import re
    from urllib.parse import unquote
    
    # Формат 1: cid=calendar_id%40gmail.com или cid=calendar_id%40group.calendar.google.com
    # Захватываем все до следующего &, включая % для URL-encoded значений
    match = re.search(r'[?&]cid=([^&\s]+)', calendar_link)
    if match:
        calendar_id_encoded = match.group(1)
        calendar_id = unquote(calendar_id_encoded)  # Декодируем URL-encoded строку
        print(f"🔍 EXTRACT_CALENDAR_ID: Извлечен из cid: '{calendar_id}' (исходный: '{calendar_id_encoded}')")
        return calendar_id
    
    # Формат 2: src=calendar_id%40gmail.com или src=c_xxx%40group.calendar.google.com
    # Важно: не исключаем %, чтобы захватывать URL-encoded значения
    match = re.search(r'[?&]src=([^&\s]+)', calendar_link)
    if match:
        calendar_id_encoded = match.group(1)
        calendar_id = unquote(calendar_id_encoded)  # Декодируем URL-encoded строку (%40 -> @, %2F -> /)
        print(f"🔍 EXTRACT_CALENDAR_ID: Извлечен из src: '{calendar_id}' (исходный: '{calendar_id_encoded}')")
        return calendar_id
    
    # Формат 3: Прямая ссылка с email в параметрах (любой формат email, включая %40)
    match = re.search(r'([a-zA-Z0-9._+-]+(?:%40|@)[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', calendar_link)
    if match:
        calendar_id_raw = match.group(1)
        calendar_id = unquote(calendar_id_raw.replace('@', '%40'))  # Нормализуем и декодируем
        print(f"🔍 EXTRACT_CALENDAR_ID: Извлечен из паттерна email: '{calendar_id}' (исходный: '{calendar_id_raw}')")
        return calendar_id
    
    print(f"⚠️ EXTRACT_CALENDAR_ID: Не удалось извлечь calendar_id из ссылки: '{calendar_link}'")
    return None


def determine_action_type_from_text(text):
    """
    Определение типа действия из текста
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - text: текст для анализа
    
    ИСТОЧНИКИ ДАННЫХ:
    - Переданный текст
    
    ОБРАБОТКА:
    - Анализ текста на наличие паттернов дат, времени, дней недели
    - Определение типа действия (hrscreening, interview, meeting)
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - str: тип действия
    
    СВЯЗИ:
    - Использует: регулярные выражения для анализа текста
    - Передает: тип действия
    - Может вызываться из: Google OAuth views
    """
    if not text:
        return "hrscreening"
    
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
    
    # НОВОЕ: Относительные даты
    relative_dates = [
        'сегодня', 'завтра', 'послезавтра', 'вчера', 'позавчера',
        'сёдня', 'зафтра', 'послезавтра', 'вчира', 'позавчира'
    ]
    
    # НОВОЕ: Времена суток  
    time_periods = [
        'утром', 'днем', 'днём', 'вечером', 'ночью',
        'утра', 'дня', 'вечера', 'ночи', 
        'с утра', 'в обед', 'обед'
    ]
    
    # Индикаторы встреч
    meeting_indicators = [
        'встреча', 'интервью', 'собеседование', 'созвон', 'звонок',
        'техническое', 'technical', 'скрининг', 'screening',
        'инвайт', 'invite', 'приглашение',
        'meeting', 'interview', 'call', 'schedule', 'time', 'date'
    ]
    
    # HR индикаторы
    hr_indicators = [
        'зарплата', 'заработная', 'оклад', 'salary', 'wage', 'pay',
        'byn', 'usd', '$', 'руб', 'рублей', 'долларов',
        'опыт', 'стаж', 'experience', 'работал', 'работала',
        'senior', 'junior', 'middle', 'lead', 'head', 'trainee',
        'навыки', 'skills', 'технологии', 'technologies',
        'образование', 'education', 'университет', 'институт',
        'резюме', 'cv', 'resume'
    ]
    
    # Проверка условий
    has_date = any(re.search(pattern, text, re.IGNORECASE) for pattern in date_patterns)
    has_time = any(re.search(pattern, text, re.IGNORECASE) for pattern in time_patterns)  
    has_weekday = any(day.lower() in text.lower() for day in weekdays)
    # НОВОЕ: Проверка относительных дат и времен суток
    has_relative_date = any(rel_date in text.lower() for rel_date in relative_dates)
    has_time_period = any(period in text.lower() for period in time_periods)
    has_meeting_indicators = any(indicator.lower() in text.lower() for indicator in meeting_indicators)
    has_hr_indicators = any(re.search(r'\b' + re.escape(indicator.lower()) + r'\b', text.lower()) for indicator in hr_indicators)
    
    text_length = len(text.strip())
    
    # ОБНОВЛЕННАЯ ЛОГИКА определения (такая же как в forms.py)
    if has_hr_indicators:
        return "hrscreening"  # 1. HR-индикаторы - HR-скрининг
    elif any(re.search(r'\b' + re.escape(keyword.lower()) + r'\b', text.lower()) 
             for keyword in ['senior', 'junior', 'middle', 'lead', 'head', 'trainee']):
        return "hrscreening"  # 2. Ключевые слова уровней - HR-скрининг
    # ОБНОВЛЕНО: добавлены has_relative_date и has_time_period
    elif (has_date or has_time or has_weekday or has_relative_date or has_time_period):
        return "invite"       # 3. Временные указания - инвайт
    elif has_meeting_indicators and not has_hr_indicators:
        return "invite"       # 4. Индикаторы встреч без HR - инвайт
    elif text_length < 100:
        return "hrscreening"  # 5. Короткий текст - HR-скрининг
    else:
        return "hrscreening"  # 6. По умолчанию - HR-скрининг

User = get_user_model()


def format_file_size(size_bytes):
    """
    Форматирование размера файла
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - size_bytes: размер файла в байтах
    
    ИСТОЧНИКИ ДАННЫХ:
    - Переданный размер файла
    
    ОБРАБОТКА:
    - Конвертация байтов в читаемый формат (KB, MB, GB)
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - str: отформатированный размер файла
    
    СВЯЗИ:
    - Использует: математические операции для конвертации
    - Передает: отформатированный размер
    - Может вызываться из: Google OAuth views
    """
    if size_bytes is None:
        return "-"
    
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    
    return f"{size_bytes:.1f} {size_names[i]}"


def get_file_type_display(mime_type):
    """
    Получение отображаемого типа файла
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - mime_type: MIME тип файла
    
    ИСТОЧНИКИ ДАННЫХ:
    - Переданный MIME тип
    
    ОБРАБОТКА:
    - Маппинг MIME типов на читаемые названия типов файлов
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - str: читаемое название типа файла
    
    СВЯЗИ:
    - Использует: словарь маппинга MIME типов
    - Передает: название типа файла
    - Может вызываться из: Google OAuth views
    """
    type_mapping = {
        'application/vnd.google-apps.folder': 'Папка',
        'application/vnd.google-apps.document': 'Google Документ',
        'application/vnd.google-apps.spreadsheet': 'Google Таблица',
        'application/vnd.google-apps.presentation': 'Google Презентация',
        'application/vnd.google-apps.form': 'Google Форма',
        'application/vnd.google-apps.drawing': 'Google Рисунок',
        'application/pdf': 'PDF',
        'application/msword': 'Word',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'Word',
        'application/vnd.ms-excel': 'Excel',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'Excel',
        'application/vnd.ms-powerpoint': 'PowerPoint',
        'application/vnd.openxmlformats-officedocument.presentationml.presentation': 'PowerPoint',
        'text/plain': 'Текстовый файл',
        'text/csv': 'CSV',
        'image/jpeg': 'JPEG',
        'image/png': 'PNG',
        'image/gif': 'GIF',
        'image/svg+xml': 'SVG',
        'video/mp4': 'MP4',
        'video/avi': 'AVI',
        'video/quicktime': 'MOV',
        'audio/mp3': 'MP3',
        'audio/wav': 'WAV',
        'application/zip': 'ZIP',
        'application/x-rar-compressed': 'RAR',
    }
    
    return type_mapping.get(mime_type, mime_type.split('/')[-1].upper())


@login_required
@permission_required('google_oauth.view_googleoauthaccount', raise_exception=True)
def dashboard_redirect(request):
    """
    Редирект на дашборд Google OAuth
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - request: HTTP запрос
    
    ИСТОЧНИКИ ДАННЫХ:
    - request.user: текущий пользователь
    
    ОБРАБОТКА:
    - Проверка аутентификации пользователя
    - Перенаправление на дашборд Google OAuth
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - redirect: на google_oauth:dashboard
    
    СВЯЗИ:
    - Использует: request.user
    - Передает: HTTP redirect
    - Может вызываться из: Google OAuth URL patterns
    """
    return redirect('accounts:profile')


@login_required(login_url=None)  # None = use settings.LOGIN_URL, next сохраняется автоматически
@permission_required('google_oauth.add_googleoauthaccount', raise_exception=True)
def google_oauth_start(request):
    """
    Начало OAuth процесса
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - request: HTTP запрос
    
    ИСТОЧНИКИ ДАННЫХ:
    - request.user: текущий пользователь
    - GoogleOAuthService: сервис для работы с Google OAuth
    
    ОБРАБОТКА:
    - Создание GoogleOAuthService
    - Генерация URL для авторизации
    - Перенаправление на Google OAuth
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - redirect: на Google OAuth authorization URL
    
    СВЯЗИ:
    - Использует: GoogleOAuthService
    - Передает: HTTP redirect
    - Может вызываться из: Google OAuth URL patterns
    """
    print(f"=== OAUTH START DEBUG ===")
    print(f"User authenticated: {request.user.is_authenticated}")
    
    # Запоминаем текущего пользователя, чтобы в callback привязать OAuth к нему
    request.session['google_oauth_link_user_id'] = request.user.id
    
    oauth_service = GoogleOAuthService(request.user)
    
    try:
        auth_url, state = oauth_service.get_authorization_url()
        request.session['google_oauth_state'] = state
        print(f"✅ Auth URL created: {auth_url[:100]}...")
        print(f"✅ State saved: {state[:20]}...")
        return redirect(auth_url)
    except Exception as e:
        print(f"❌ Error creating OAuth URL: {e}")
        import traceback
        traceback.print_exc()
        messages.error(request, f'Ошибка при создании OAuth URL: {str(e)}')
        # Редирект в профиль, а не на account_login (иначе авторизованного уносит на /huntflow/)
        return redirect('accounts:profile')


@permission_required('google_oauth.change_googleoauthaccount', raise_exception=True)
def google_oauth_callback(request):
    """
    Обработка callback от Google OAuth
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - request: HTTP запрос с кодом авторизации
    - request.GET: code, state, error
    
    ИСТОЧНИКИ ДАННЫХ:
    - Google OAuth API
    - GoogleOAuthService
    
    ОБРАБОТКА:
    - Получение кода авторизации из callback
    - Обмен кода на токен доступа
    - Сохранение токенов пользователя
    - Перенаправление на дашборд
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - redirect: на google_oauth:dashboard или error page
    
    СВЯЗИ:
    - Использует: GoogleOAuthService, Google OAuth API
    - Передает: HTTP redirect
    - Может вызываться из: Google OAuth URL patterns
    """
    print(f"=== OAUTH CALLBACK DEBUG ===")
    print(f"GET params: {request.GET}")
    print(f"Session state: {request.session.get('google_oauth_state')}")
    
    # Проверяем state
    state = request.session.get('google_oauth_state')
    if not state:
        print("❌ State not found in session")
        messages.error(request, 'Ошибка авторизации: неверный state')
        return redirect('accounts:account_login')
    
    # Получаем код авторизации
    code = request.GET.get('code')
    if not code:
        print("❌ Code not found in GET params")
        messages.error(request, 'Ошибка авторизации: код не получен')
        return redirect('accounts:account_login')
    
    print(f"✅ Code received: {code[:20]}...")
    print(f"✅ State: {state[:20]}...")
    
    try:
        # Создаем временного пользователя для получения токенов
        temp_user, created = User.objects.get_or_create(
            username='temp_oauth_user',
            defaults={
                'email': 'temp@oauth.com',
                'is_active': True,
            }
        )
        
        oauth_service = GoogleOAuthService(temp_user)
        
        # Обрабатываем callback
        authorization_response = request.build_absolute_uri()
        print(f"🔄 Processing callback with URL: {authorization_response}")
        
        oauth_account = oauth_service.handle_callback(authorization_response, state)
        print(f"✅ OAuth account created: {oauth_account.id}")
        print(f"   - Access Token: {'Есть' if oauth_account.access_token else 'Нет'}")
        print(f"   - Refresh Token: {'Есть' if oauth_account.refresh_token else 'Нет'}")
        
        # Подключение к уже авторизованному пользователю (из профиля «Подключить Google API»)
        link_user_id = request.session.pop('google_oauth_link_user_id', None)
        if link_user_id:
            try:
                user = User.objects.get(pk=link_user_id)
                oauth_account.user = user
                oauth_account.save()
                if temp_user.username == 'temp_oauth_user':
                    temp_user.delete()
                if 'google_oauth_state' in request.session:
                    del request.session['google_oauth_state']
                messages.success(request, f'Google аккаунт {oauth_account.email} успешно подключен к вашему профилю.')
                return redirect('accounts:profile')
            except User.DoesNotExist:
                pass  # fallback к логике по email ниже
        
        # Получаем данные пользователя из Google (логин через Google или fallback)
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        
        credentials = Credentials(
            token=oauth_account.access_token,
            refresh_token=oauth_account.refresh_token,
            token_uri='https://oauth2.googleapis.com/token',
            client_id=settings.GOOGLE_OAUTH2_CLIENT_ID,
            client_secret=settings.GOOGLE_OAUTH2_CLIENT_SECRET,
            scopes=oauth_account.scopes
        )
        
        # Получаем информацию о пользователе
        service = build('oauth2', 'v2', credentials=credentials)
        user_info = service.userinfo().get().execute()
        
        google_email = user_info.get('email')
        google_name = user_info.get('name', '')
        
        print(f"✅ User info received:")
        print(f"   - Email: {google_email}")
        print(f"   - Name: {google_name}")
        
        # Создаем или находим пользователя по email
        if google_email:
            # Сначала ищем по email
            try:
                user = User.objects.get(email=google_email)
                print(f"✅ Найден существующий пользователь: {user.username}")
            except User.DoesNotExist:
                # Создаем нового пользователя
                username = google_email.split('@')[0]
                # Проверяем, что username уникален
                counter = 1
                original_username = username
                while User.objects.filter(username=username).exists():
                    username = f"{original_username}_{counter}"
                    counter += 1
                
                user = User.objects.create(
                    username=username,
                    email=google_email,
                    first_name=google_name.split(' ')[0] if google_name else '',
                    last_name=' '.join(google_name.split(' ')[1:]) if len(google_name.split(' ')) > 1 else '',
                    is_active=True,
                )
                print(f"✅ Создан новый пользователь: {user.username}")
        else:
            # Если email не получен, создаем пользователя с временным именем
            username = f'google_user_{oauth_account.id}'
            user = User.objects.create(
                username=username,
                email=f'user_{oauth_account.id}@google.com',
                first_name=google_name.split(' ')[0] if google_name else 'Google',
                last_name=' '.join(google_name.split(' ')[1:]) if len(google_name.split(' ')) > 1 else 'User',
                is_active=True,
            )
            print(f"✅ Создан пользователь без email: {user.username}")
        
        # Переносим OAuth аккаунт на правильного пользователя
        oauth_account.user = user
        oauth_account.save()
        
        # Удаляем временного пользователя
        if temp_user.username == 'temp_oauth_user':
            temp_user.delete()
        
        # Удаляем state из сессии
        if 'google_oauth_state' in request.session:
            del request.session['google_oauth_state']
        
        # Авторизуем пользователя
        login(request, user)
        
        print(f"✅ User logged in: {user.username}")
        print(f"✅ Redirecting to dashboard")
        
        messages.success(request, f'Добро пожаловать, {user.first_name}! Google аккаунт {google_email} успешно подключен!')
        return redirect('accounts:profile')
        
    except Exception as e:
        print(f"❌ Error in callback: {e}")
        import traceback
        traceback.print_exc()
        messages.error(request, f'Ошибка при подключении Google аккаунта: {str(e)}')
        return redirect('accounts:account_login')


@login_required
@permission_required('google_oauth.view_googleoauthaccount', raise_exception=True)
def dashboard(request):
    """
    Дашборд Google OAuth
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - request.user: аутентифицированный пользователь
    
    ИСТОЧНИКИ ДАННЫХ:
    - GoogleOAuthAccount.objects: аккаунты пользователя
    - GoogleCalendarService, GoogleDriveService, GoogleSheetsService
    
    ОБРАБОТКА:
    - Получение аккаунтов Google пользователя
    - Проверка статуса авторизации
    - Получение данных из Google сервисов
    - Формирование статистики
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - context: словарь с данными Google сервисов
    - render: HTML страница 'google_oauth/dashboard.html'
    
    СВЯЗИ:
    - Использует: GoogleOAuthAccount, Google сервисы
    - Передает данные в: google_oauth/dashboard.html
    - Может вызываться из: google_oauth/ URL patterns
    """
    oauth_service = GoogleOAuthService(request.user)
    oauth_account = oauth_service.get_oauth_account()
    
    context = {
        'oauth_account': oauth_account,
        'is_connected': bool(oauth_account and oauth_account.is_token_valid()),
        'available_services': oauth_account.get_available_services() if oauth_account else [],
    }
    
    return render(request, 'google_oauth/dashboard.html', context)


@login_required
@permission_required('google_oauth.delete_googleoauthaccount', raise_exception=True)
def disconnect(request):
    """
    Отключение Google OAuth
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - request.user: аутентифицированный пользователь
    
    ИСТОЧНИКИ ДАННЫХ:
    - GoogleOAuthAccount.objects: аккаунты пользователя
    - GoogleOAuthService: сервис для работы с OAuth
    
    ОБРАБОТКА:
    - Получение OAuth аккаунта пользователя
    - Отзыв токенов доступа
    - Удаление аккаунта из базы данных
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - messages: сообщение об успешном отключении
    - redirect: на google_oauth:dashboard
    
    СВЯЗИ:
    - Использует: GoogleOAuthAccount, GoogleOAuthService
    - Передает: HTTP redirect
    - Может вызываться из: google_oauth/ URL patterns
    """
    oauth_service = GoogleOAuthService(request.user)
    
    try:
        success = oauth_service.revoke_access()
        if success:
            messages.success(request, 'Google аккаунт успешно отключен!')
        else:
            messages.warning(request, 'Google аккаунт не был подключен.')
    except Exception as e:
        messages.error(request, f'Ошибка при отключении: {str(e)}')
    
    return redirect('google_oauth:dashboard')


@login_required
@permission_required('google_oauth.view_googlecalendar', raise_exception=True)
def calendar_view(request):
    """
    Просмотр календаря Google
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - request.user: аутентифицированный пользователь
    
    ИСТОЧНИКИ ДАННЫХ:
    - GoogleCalendarService: сервис для работы с Google Calendar
    - GoogleOAuthAccount.objects: аккаунты пользователя
    
    ОБРАБОТКА:
    - Получение OAuth аккаунта пользователя
    - Получение списка календарей
    - Получение событий календаря
    - Формирование контекста для отображения
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - context: словарь с данными календаря
    - render: HTML страница 'google_oauth/calendar.html'
    
    СВЯЗИ:
    - Использует: GoogleCalendarService, GoogleOAuthAccount
    - Передает данные в: google_oauth/calendar.html
    - Может вызываться из: google_oauth/ URL patterns
    """
    oauth_service = GoogleOAuthService(request.user)
    oauth_account = oauth_service.get_oauth_account()
    
    if not oauth_account or not oauth_account.has_scope('https://www.googleapis.com/auth/calendar'):
        messages.warning(
            request,
            'Нет доступа к Google Calendar. Переподключите Google-аккаунт (профиль → Войти через Google), чтобы выдать права приложению.'
        )
        return redirect('google_oauth:dashboard')
    
    # Получаем параметры для календаря
    import calendar
    
    # Получаем месяц и год из параметров или используем текущий
    year = int(request.GET.get('year', timezone.now().year))
    month = int(request.GET.get('month', timezone.now().month))
    
    # Создаем даты начала и конца месяца
    month_start = datetime(year, month, 1)
    if month == 12:
        month_end = datetime(year + 1, 1, 1) - timedelta(days=1)
    else:
        month_end = datetime(year, month + 1, 1) - timedelta(days=1)
    
    # Получаем события за месяц из кэша через API (logic-сервис ожидает oauth_account)
    calendar_service = GoogleCalendarService(oauth_account)
    try:
        events_data = calendar_service.get_events(days_ahead=100)
    except Exception as e:
        print(f"🔍 DEBUG CALENDAR: Ошибка получения событий: {e}")
        events_data = []
    
    # Фильтруем события за нужный месяц
    month_events = []
    for event_data in events_data:
        try:
            # Парсим время начала
            start_time = None
            if 'dateTime' in event_data['start']:
                start_time = datetime.fromisoformat(event_data['start']['dateTime'].replace('Z', '+00:00'))
                # Конвертируем в локальный часовой пояс Minsk
                import pytz
                minsk_tz = pytz.timezone('Europe/Minsk')
                start_time = start_time.astimezone(minsk_tz)
            elif 'date' in event_data['start']:
                start_time = datetime.fromisoformat(event_data['start']['date'] + 'T00:00:00+00:00')
            
            if start_time and month_start <= start_time <= month_end:
                month_events.append({
                    'id': event_data['id'],
                    'title': event_data.get('summary', 'Без названия'),
                    'start_time': start_time,
                    'location': event_data.get('location', ''),
                    'description': event_data.get('description', ''),
                })
        except Exception as e:
            print(f"Ошибка обработки события {event_data.get('id', 'unknown')}: {e}")
            continue
    
    # Сортируем события по времени начала
    month_events.sort(key=lambda x: x['start_time'])
    
    # Группируем события по дням
    events_by_day = {}
    for event in month_events:
        day_key = event['start_time'].date()
        if day_key not in events_by_day:
            events_by_day[day_key] = []
        events_by_day[day_key].append(event)
    
    # Создаем календарь
    cal = calendar.monthcalendar(year, month)
    
    # Навигация по месяцам
    prev_month = month - 1 if month > 1 else 12
    prev_year = year if month > 1 else year - 1
    next_month = month + 1 if month < 12 else 1
    next_year = year if month < 12 else year + 1
    
    # Подготавливаем данные участников для JavaScript
    import json
    attendees_data = {}
    for event in month_events:
        if 'attendees' in event:
            attendees_data[event['title']] = event['attendees']
    
    context = {
        'oauth_account': oauth_account,
        'events': month_events,
        'events_by_day': events_by_day,
        'calendar': cal,
        'year': year,
        'month': month,
        'month_name': calendar.month_name[month],
        'prev_month': prev_month,
        'prev_year': prev_year,
        'next_month': next_month,
        'next_year': next_year,
        'today': timezone.now().date(),
        'attendees_data_json': json.dumps(attendees_data),
    }
    
    return render(request, 'google_oauth/calendar.html', context)


@login_required
@permission_required('google_oauth.view_googledrivefile', raise_exception=True)
def drive_view(request):
    """
    Просмотр Google Drive
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - request.user: аутентифицированный пользователь
    
    ИСТОЧНИКИ ДАННЫХ:
    - GoogleDriveService: сервис для работы с Google Drive
    - GoogleOAuthAccount.objects: аккаунты пользователя
    
    ОБРАБОТКА:
    - Получение OAuth аккаунта пользователя
    - Получение списка файлов из Google Drive
    - Получение информации о файлах
    - Формирование контекста для отображения
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - context: словарь с данными Google Drive
    - render: HTML страница 'google_oauth/drive.html'
    
    СВЯЗИ:
    - Использует: GoogleDriveService, GoogleOAuthAccount
    - Передает данные в: google_oauth/drive.html
    - Может вызываться из: google_oauth/ URL patterns
    """
    oauth_service = GoogleOAuthService(request.user)
    oauth_account = oauth_service.get_oauth_account()
    
    if not oauth_account or not oauth_account.has_scope('https://www.googleapis.com/auth/drive'):
        messages.warning(
            request,
            'Нет доступа к Google Drive. Переподключите Google-аккаунт (дашборд Google OAuth → отключить и войти снова), чтобы выдать права приложению.'
        )
        return redirect('google_oauth:dashboard')
    
    # Получаем файлы из кэша через API (logic-сервис ожидает oauth_account)
    drive_service = GoogleDriveService(oauth_account)
    try:
        files_data = drive_service.get_files(max_results=50)
    except Exception as e:
        print(f"🔍 DEBUG DRIVE: Ошибка получения файлов: {e}")
        files_data = []
    
    # Преобразуем файлы в нужный формат
    files = []
    for file_data in files_data:
        try:
            modified_time = datetime.fromisoformat(file_data['modifiedTime'].replace('Z', '+00:00'))
            files.append({
                'id': file_data['id'],
                'name': file_data['name'],
                'mime_type': file_data['mimeType'],
                'size': int(file_data.get('size', 0)) if file_data.get('size') else None,
                'modified_time': modified_time,
                'web_view_link': file_data.get('webViewLink', ''),
                'web_content_link': file_data.get('webContentLink', ''),
            })
        except Exception as e:
            print(f"Ошибка обработки файла {file_data.get('id', 'unknown')}: {e}")
            continue
    
    # Сортируем файлы по времени изменения
    files.sort(key=lambda x: x['modified_time'], reverse=True)
    
    context = {
        'oauth_account': oauth_account,
        'files': files,
    }
    
    return render(request, 'google_oauth/drive.html', context)


@login_required
@permission_required('google_oauth.view_googlesheet', raise_exception=True)
def sheets_view(request):
    """
    Просмотр Google Sheets
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - request.user: аутентифицированный пользователь
    
    ИСТОЧНИКИ ДАННЫЕ:
    - GoogleSheetsService: сервис для работы с Google Sheets
    - GoogleOAuthAccount.objects: аккаунты пользователя
    
    ОБРАБОТКА:
    - Получение OAuth аккаунта пользователя
    - Получение списка таблиц из Google Sheets
    - Получение данных из таблиц
    - Формирование контекста для отображения
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - context: словарь с данными Google Sheets
    - render: HTML страница 'google_oauth/sheets.html'
    
    СВЯЗИ:
    - Использует: GoogleSheetsService, GoogleOAuthAccount
    - Передает данные в: google_oauth/sheets.html
    - Может вызываться из: google_oauth/ URL patterns
    """
    oauth_service = GoogleOAuthService(request.user)
    oauth_account = oauth_service.get_oauth_account()
    
    if not oauth_account or not oauth_account.has_scope('https://www.googleapis.com/auth/spreadsheets'):
        messages.warning(
            request,
            'Нет доступа к Google Таблицам. Переподключите Google-аккаунт (дашборд Google OAuth), чтобы выдать права приложению.'
        )
        return redirect('google_oauth:dashboard')
    
    # Получаем таблицы из кэша через API (logic-сервис ожидает oauth_account)
    sheets_service = GoogleSheetsService(oauth_account)
    try:
        sheets_data = sheets_service.get_spreadsheets(max_results=50)
    except Exception as e:
        print(f"🔍 DEBUG SHEETS: Ошибка получения таблиц: {e}")
        sheets_data = []
    
    # Преобразуем таблицы в нужный формат
    sheets = []
    for sheet_data in sheets_data:
        try:
            modified_time = datetime.fromisoformat(sheet_data['modifiedTime'].replace('Z', '+00:00'))
            sheets.append({
                'id': sheet_data['id'],
                'title': sheet_data['name'],
                'modified_time': modified_time,
                'web_view_link': sheet_data.get('webViewLink', ''),
            })
        except Exception as e:
            print(f"Ошибка обработки таблицы {sheet_data.get('id', 'unknown')}: {e}")
            continue
    
    # Сортируем таблицы по времени изменения
    sheets.sort(key=lambda x: x['modified_time'], reverse=True)
    
    context = {
        'oauth_account': oauth_account,
        'sheets': sheets,
    }
    
    return render(request, 'google_oauth/sheets.html', context)


@login_required
@permission_required('google_oauth.change_syncsettings', raise_exception=True)
@require_POST
def sync_calendar(request):
    """
    Синхронизация календаря Google
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - request.user: аутентифицированный пользователь
    
    ИСТОЧНИКИ ДАННЫХ:
    - GoogleCalendarService: сервис для работы с Google Calendar
    - GoogleOAuthAccount.objects: аккаунты пользователя
    
    ОБРАБОТКА:
    - Получение OAuth аккаунта пользователя
    - Проверка доступа к календарю
    - Синхронизация данных календаря
    - Обновление времени последней синхронизации
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - messages: сообщение о результате синхронизации
    - redirect: на google_oauth:calendar
    
    СВЯЗИ:
    - Использует: GoogleCalendarService, GoogleOAuthAccount
    - Передает: HTTP redirect
    - Может вызываться из: google_oauth/ URL patterns
    """
    oauth_service = GoogleOAuthService(request.user)
    oauth_account = oauth_service.get_oauth_account()
    
    if not oauth_account or not oauth_account.has_scope('https://www.googleapis.com/auth/calendar'):
        return JsonResponse({'success': False, 'message': 'Нет доступа к Google Calendar'})
    
    try:
        calendar_service = GoogleCalendarService(oauth_account)
        calendar_service.sync_events()
        
        # Обновляем время последней синхронизации
        oauth_account.last_sync_at = timezone.now()
        oauth_account.save()
        
        return JsonResponse({'success': True, 'message': 'Календарь успешно синхронизирован!'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Ошибка синхронизации: {str(e)}'})

@login_required
@permission_required('google_oauth.change_syncsettings', raise_exception=True)
@require_POST
def sync_drive(request):
    """
    Синхронизация Google Drive
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - request.user: аутентифицированный пользователь
    
    ИСТОЧНИКИ ДАННЫЕ:
    - GoogleDriveService: сервис для работы с Google Drive
    - GoogleOAuthAccount.objects: аккаунты пользователя
    
    ОБРАБОТКА:
    - Получение OAuth аккаунта пользователя
    - Проверка доступа к Google Drive
    - Синхронизация данных Google Drive
    - Обновление времени последней синхронизации
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - messages: сообщение о результате синхронизации
    - redirect: на google_oauth:drive
    
    СВЯЗИ:
    - Использует: GoogleDriveService, GoogleOAuthAccount
    - Передает: HTTP redirect
    - Может вызываться из: google_oauth/ URL patterns
    """
    oauth_service = GoogleOAuthService(request.user)
    oauth_account = oauth_service.get_oauth_account()
    
    if not oauth_account or not oauth_account.has_scope('https://www.googleapis.com/auth/drive'):
        return JsonResponse({'success': False, 'message': 'Нет доступа к Google Drive'})
    
    try:
        drive_service = GoogleDriveService(oauth_account)
        drive_service.sync_files()
        
        # Обновляем время последней синхронизации
        oauth_account.last_sync_at = timezone.now()
        oauth_account.save()
        
        return JsonResponse({'success': True, 'message': 'Google Drive успешно синхронизирован!'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Ошибка синхронизации: {str(e)}'})

@login_required
@permission_required('google_oauth.change_syncsettings', raise_exception=True)
@require_POST
def sync_sheets(request):
    """
    Синхронизация Google Sheets
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - request.user: аутентифицированный пользователь
    
    ИСТОЧНИКИ ДАННЫЕ:
    - GoogleSheetsService: сервис для работы с Google Sheets
    - GoogleOAuthAccount.objects: аккаунты пользователя
    
    ОБРАБОТКА:
    - Получение OAuth аккаунта пользователя
    - Проверка доступа к Google Sheets
    - Синхронизация данных Google Sheets
    - Обновление времени последней синхронизации
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - messages: сообщение о результате синхронизации
    - redirect: на google_oauth:sheets
    
    СВЯЗИ:
    - Использует: GoogleSheetsService, GoogleOAuthAccount
    - Передает: HTTP redirect
    - Может вызываться из: google_oauth/ URL patterns
    """
    oauth_service = GoogleOAuthService(request.user)
    oauth_account = oauth_service.get_oauth_account()
    
    if not oauth_account or not oauth_account.has_scope('https://www.googleapis.com/auth/spreadsheets'):
        return JsonResponse({'success': False, 'message': 'Нет доступа к Google Sheets'})
    
    try:
        sheets_service = GoogleSheetsService(oauth_account)
        sheets_service.sync_sheets()
        
        # Обновляем время последней синхронизации
        oauth_account.last_sync_at = timezone.now()
        oauth_account.save()
        
        return JsonResponse({'success': True, 'message': 'Google Sheets успешно синхронизированы!'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Ошибка синхронизации: {str(e)}'})

@login_required
@permission_required('google_oauth.change_syncsettings', raise_exception=True)
@require_POST
def sync_all(request):
    """
    Синхронизация всех Google сервисов
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - request.user: аутентифицированный пользователь
    
    ИСТОЧНИКИ ДАННЫЕ:
    - GoogleCalendarService, GoogleDriveService, GoogleSheetsService: сервисы Google
    - GoogleOAuthAccount.objects: аккаунты пользователя
    
    ОБРАБОТКА:
    - Получение OAuth аккаунта пользователя
    - Проверка доступа ко всем сервисам
    - Последовательная синхронизация всех сервисов
    - Обновление времени последней синхронизации
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - messages: сообщение о результате синхронизации
    - redirect: на google_oauth:dashboard
    
    СВЯЗИ:
    - Использует: Google сервисы, GoogleOAuthAccount
    - Передает: HTTP redirect
    - Может вызываться из: google_oauth/ URL patterns
    """
    oauth_service = GoogleOAuthService(request.user)
    oauth_account = oauth_service.get_oauth_account()
    
    if not oauth_account:
        return JsonResponse({'success': False, 'message': 'Google аккаунт не подключен'})
    
    results = []
    
    # Синхронизируем календарь
    if oauth_account.has_scope('https://www.googleapis.com/auth/calendar'):
        try:
            calendar_service = GoogleCalendarService(oauth_account)
            calendar_service.sync_events()
            results.append('Календарь: ✅')
        except Exception as e:
            results.append(f'Календарь: ❌ {str(e)}')
    
    # Синхронизируем Drive
    if oauth_account.has_scope('https://www.googleapis.com/auth/drive'):
        try:
            drive_service = GoogleDriveService(oauth_account)
            drive_service.sync_files()
            results.append('Drive: ✅')
        except Exception as e:
            results.append(f'Drive: ❌ {str(e)}')
    
    # Синхронизируем Sheets
    if oauth_account.has_scope('https://www.googleapis.com/auth/spreadsheets'):
        try:
            sheets_service = GoogleSheetsService(oauth_account)
            sheets_service.sync_sheets()
            results.append('Sheets: ✅')
        except Exception as e:
            results.append(f'Sheets: ❌ {str(e)}')
    
    # Обновляем время последней синхронизации
    oauth_account.last_sync_at = timezone.now()
    oauth_account.save()
    
    return JsonResponse({
        'success': True, 
        'message': 'Синхронизация завершена!',
        'results': results
    })


# Views для Google OAuth
from django.core.paginator import Paginator
from django.db.models import Q
from .models import SyncSettings, Invite, HRScreening
from .forms import SyncSettingsForm, InviteForm, InviteUpdateForm, InviteCombinedForm, HRScreeningForm


@login_required
@permission_required('google_oauth.view_googleoauthaccount', raise_exception=True)
def dashboard(request):
    """Дашборд Google автоматизации"""
    user = request.user
    
    # Получаем Google OAuth аккаунт
    oauth_service = GoogleOAuthService(user)
    oauth_account = oauth_service.get_oauth_account()
    
    # Проверяем, подключен ли аккаунт (аккаунт считается подключенным, даже если токен истек)
    is_connected = oauth_account is not None
    token_valid = oauth_account.is_token_valid() if oauth_account else False
    
    # Отладочная информация
    if oauth_account:
        print(f"🔍 DEBUG: OAuth account found: {oauth_account.email}")
        print(f"🔍 DEBUG: Token valid: {oauth_account.is_token_valid()}")
        print(f"🔍 DEBUG: Token expires at: {oauth_account.token_expires_at}")
        print(f"🔍 DEBUG: Current time: {timezone.now()}")
    else:
        print("🔍 DEBUG: No OAuth account found")
    
    # Если аккаунт не подключён — показываем дашборд с приглашением подключить Google OAuth (без 500)
    if not oauth_account:
        context = {
            'integration': None,
            'oauth_account': None,
            'is_connected': False,
            'token_valid': False,
            'total_events': 0,
            'total_files': 0,
            'calendar_events_count': 0,
            'drive_files_count': 0,
            'recent_events': [],
            'recent_files': [],
        }
        return render(request, 'google_oauth/dashboard.html', context)
    
    # Получаем данные из кэша через API
    now = timezone.now()
    future_limit = now + timedelta(days=100)  # События на ближайшие 100 дней
    
    # Сервисы logic ожидают oauth_account (модель), не oauth_service
    calendar_service = GoogleCalendarService(oauth_account)
    drive_service = GoogleDriveService(oauth_account)
    
    # Получаем события календаря (при истёкшем токене не падаем с 500)
    try:
        events_data = calendar_service.get_events(days_ahead=100)
    except Exception as e:
        print(f"🔍 DEBUG: Ошибка получения событий календаря: {e}")
        events_data = []
    
    # Фильтруем только будущие события
    future_events = []
    for event_data in events_data:
        try:
            # Парсим время начала и окончания
            start_time = None
            end_time = None
            
            if 'dateTime' in event_data['start']:
                start_time = datetime.fromisoformat(event_data['start']['dateTime'].replace('Z', '+00:00'))
                # Конвертируем в локальный часовой пояс Minsk
                import pytz
                minsk_tz = pytz.timezone('Europe/Minsk')
                start_time = start_time.astimezone(minsk_tz)
                # Конвертируем в локальный часовой пояс Minsk
                import pytz
                minsk_tz = pytz.timezone('Europe/Minsk')
                start_time = start_time.astimezone(minsk_tz)
            elif 'date' in event_data['start']:
                start_time = datetime.fromisoformat(event_data['start']['date'] + 'T00:00:00+00:00')
            
            if 'dateTime' in event_data['end']:
                end_time = datetime.fromisoformat(event_data['end']['dateTime'].replace('Z', '+00:00'))
                # Конвертируем в локальный часовой пояс Minsk
                import pytz
                minsk_tz = pytz.timezone('Europe/Minsk')
                end_time = end_time.astimezone(minsk_tz)
                # Конвертируем в локальный часовой пояс Minsk
                import pytz
                minsk_tz = pytz.timezone('Europe/Minsk')
                end_time = end_time.astimezone(minsk_tz)
            elif 'date' in event_data['end']:
                end_time = datetime.fromisoformat(event_data['end']['date'] + 'T00:00:00+00:00')
            
            if start_time and now <= start_time <= future_limit:
                # Извлекаем участников
                attendees = []
                if 'attendees' in event_data:
                    for attendee in event_data['attendees']:
                        attendees.append({
                            'email': attendee.get('email', ''),
                            'name': attendee.get('displayName', ''),
                            'response_status': attendee.get('responseStatus', 'needsAction'),
                        })
                
                # Извлекаем ссылку на Google Meet
                meet_link = None
                if 'hangoutLink' in event_data and event_data['hangoutLink']:
                    meet_link = event_data['hangoutLink']
                elif 'conferenceData' in event_data:
                    if 'entryPoints' in event_data['conferenceData']:
                        for entry_point in event_data['conferenceData']['entryPoints']:
                            if entry_point.get('entryPointType') == 'video':
                                meet_link = entry_point.get('uri')
                                break
                
                # Извлекаем информацию о создателе
                creator_email = ''
                creator_name = ''
                if 'creator' in event_data:
                    creator_email = event_data['creator'].get('email', '')
                    creator_name = event_data['creator'].get('displayName', '')
                
                future_events.append({
                    'id': event_data['id'],
                    'title': event_data.get('summary', 'Без названия'),
                    'description': event_data.get('description', ''),
                    'start_datetime': start_time,  # Для совместимости с шаблоном
                    'end_datetime': end_time,      # Для совместимости с шаблоном
                    'start_time': start_time,      # Дублируем для обратной совместимости
                    'end_time': end_time,          # Дублируем для обратной совместимости
                    'is_all_day': 'date' in event_data['start'],
                    'all_day': 'date' in event_data['start'],  # Дублируем для обратной совместимости
                    'location': event_data.get('location', ''),
                    'status': event_data.get('status', 'confirmed'),
                    'attendees': attendees,
                    'meet_link': meet_link,
                    'creator_email': creator_email,
                    'creator_name': creator_name,
                    'calendar_id': event_data.get('calendar_id', 'primary'),
                    'html_link': event_data.get('htmlLink', ''),  # Ссылка на событие в Google Calendar
                    'google_created_at': datetime.fromisoformat(event_data['created'].replace('Z', '+00:00')) if 'created' in event_data else None,
                    'google_updated_at': datetime.fromisoformat(event_data['updated'].replace('Z', '+00:00')) if 'updated' in event_data else None,
                })
        except Exception as e:
            print(f"Ошибка обработки события {event_data.get('id', 'unknown')}: {e}")
            continue
    
    # Сортируем события по времени начала
    future_events.sort(key=lambda x: x['start_time'])
    
    # Получаем файлы Drive (при ошибке credentials — не 500)
    try:
        files_data = drive_service.get_files(max_results=100)
    except Exception as e:
        print(f"🔍 DEBUG: Ошибка получения файлов Drive: {e}")
        files_data = []
    
    # Преобразуем файлы в нужный формат
    recent_files = []
    for file_data in files_data[:5]:  # Берем первые 5 файлов
        try:
            created_time = datetime.fromisoformat(file_data['createdTime'].replace('Z', '+00:00'))
            modified_time = datetime.fromisoformat(file_data['modifiedTime'].replace('Z', '+00:00')) if 'modifiedTime' in file_data else created_time
            
            # Добавляем методы для размера и типа файла
            size = file_data.get('size', 0)
            if isinstance(size, str):
                try:
                    size = int(size)
                except (ValueError, TypeError):
                    size = 0
            
            file_obj = {
                'id': file_data['id'],
                'name': file_data['name'],
                'mime_type': file_data['mimeType'],
                'created_time': created_time,
                'modified_time': modified_time,
                'web_view_link': file_data.get('webViewLink', ''),
                'is_folder': file_data['mimeType'] == 'application/vnd.google-apps.folder',
                'is_shared': file_data.get('shared', False),
                'shared_with_me': file_data.get('sharedWithMe', False),
                'size': size,
            }
            
            # Добавляем методы для отображения размера и типа
            file_obj['get_size_display'] = lambda: format_file_size(file_obj['size'])
            file_obj['get_file_type_display'] = lambda: get_file_type_display(file_obj['mime_type'])
            
            recent_files.append(file_obj)
        except Exception as e:
            print(f"Ошибка обработки файла {file_data.get('id', 'unknown')}: {e}")
            continue
    
    # Статистика
    calendar_events_count = len(future_events)
    drive_files_count = len(files_data)
    recent_events = future_events[:5]  # Берем первые 5 событий
    
    # Отладочная информация
    print(f"🔍 DEBUG: Found {calendar_events_count} upcoming events (from cache/API)")
    print(f"🔍 DEBUG: Found {drive_files_count} files (from cache/API)")
    for event in recent_events:
        print(f"🔍 DEBUG: Event: {event['title']} at {event['start_time']}")
    
    context = {
        'integration': oauth_account,  # Для совместимости
        'oauth_account': oauth_account,
        'is_connected': is_connected,
        'token_valid': token_valid,
        'total_events': calendar_events_count,  # Для совместимости с шаблоном
        'total_files': drive_files_count,  # Для совместимости с шаблоном
        'calendar_events_count': calendar_events_count,
        'drive_files_count': drive_files_count,
        'recent_events': recent_events,
        'recent_files': recent_files,
    }
    
    return render(request, 'google_oauth/dashboard.html', context)






@login_required
@permission_required('google_oauth.delete_googleoauthaccount', raise_exception=True)
@require_POST
def disconnect_google(request):
    """Отключение Google интеграции"""
    user = request.user
    oauth_service = GoogleOAuthService(user)
    
    try:
        oauth_service.disconnect()
        messages.success(request, 'Google интеграция успешно отключена!')
    except Exception as e:
        messages.error(request, f'Ошибка отключения: {str(e)}')
    
    return redirect('google_oauth:dashboard')


@login_required
@permission_required('google_oauth.view_googlecalendar', raise_exception=True)
def calendar_events(request):
    """Список событий календаря"""
    user = request.user
    
    # Проверяем OAuth аккаунт
    oauth_service = GoogleOAuthService(user)
    integration = oauth_service.get_oauth_account()
    
    # Отладочная информация для calendar_events
    if integration:
        print(f"🔍 DEBUG CALENDAR: OAuth account found: {integration.email}")
        print(f"🔍 DEBUG CALENDAR: Token valid: {integration.is_token_valid()}")
        print(f"🔍 DEBUG CALENDAR: Token expires at: {integration.token_expires_at}")
        print(f"🔍 DEBUG CALENDAR: Current time: {timezone.now()}")
    else:
        print("🔍 DEBUG CALENDAR: No OAuth account found")
    
    # Временно отключаем проверку токена для диагностики
    if not integration:
        messages.warning(request, 'Необходимо подключить Google аккаунт для просмотра событий календаря.')
        return redirect('google_oauth:dashboard')
    
    # Пытаемся обновить токен, если он истек
    if not integration.is_token_valid():
        print(f"🔍 DEBUG CALENDAR: Token expired, attempting to refresh...")
        try:
            # Попытка обновить токен через get_credentials
            credentials = oauth_service.get_credentials()
            if credentials:
                # Обновляем объект integration из базы данных
                integration.refresh_from_db()
                if integration.is_token_valid():
                    print(f"🔍 DEBUG CALENDAR: Token successfully refreshed!")
                    messages.success(request, 'Токен Google успешно обновлен.')
                else:
                    print(f"🔍 DEBUG CALENDAR: Token refresh failed")
                    messages.warning(request, 'Не удалось обновить токен Google. Рекомендуется переподключить аккаунт.')
            else:
                print(f"🔍 DEBUG CALENDAR: Failed to get credentials")
                messages.warning(request, 'Не удалось получить действительные credentials. Рекомендуется переподключить аккаунт.')
        except Exception as e:
            print(f"🔍 DEBUG CALENDAR: Error refreshing token: {e}")
            messages.warning(request, f'Ошибка обновления токена: {str(e)}')
    
    # Получаем события из кэша через API (logic ожидает oauth_account — модель)
    calendar_service = GoogleCalendarService(integration)
    try:
        events_data = calendar_service.get_events(days_ahead=100)
    except Exception as e:
        print(f"🔍 DEBUG CALENDAR_EVENTS: Ошибка получения событий: {e}")
        events_data = []
    
    # Преобразуем данные API в формат для шаблона
    events = []
    for event_data in events_data:
        try:
            # Парсим время начала
            start_time = None
            if 'dateTime' in event_data['start']:
                start_time = datetime.fromisoformat(event_data['start']['dateTime'].replace('Z', '+00:00'))
                # Конвертируем в локальный часовой пояс Minsk
                import pytz
                minsk_tz = pytz.timezone('Europe/Minsk')
                start_time = start_time.astimezone(minsk_tz)
            elif 'date' in event_data['start']:
                start_time = datetime.fromisoformat(event_data['start']['date'] + 'T00:00:00+00:00')
            
            # Парсим время окончания
            end_time = None
            if 'dateTime' in event_data['end']:
                end_time = datetime.fromisoformat(event_data['end']['dateTime'].replace('Z', '+00:00'))
                # Конвертируем в локальный часовой пояс Minsk
                import pytz
                minsk_tz = pytz.timezone('Europe/Minsk')
                end_time = end_time.astimezone(minsk_tz)
            elif 'date' in event_data['end']:
                end_time = datetime.fromisoformat(event_data['end']['date'] + 'T23:59:59+00:00')
            
            # Извлекаем участников
            attendees = []
            if 'attendees' in event_data:
                for attendee in event_data['attendees']:
                    attendee_info = {
                        'email': attendee.get('email', ''),
                        'name': attendee.get('displayName', ''),
                        'response_status': attendee.get('responseStatus', 'needsAction'),
                        'organizer': attendee.get('organizer', False),
                    }
                    attendees.append(attendee_info)
            
            # Извлекаем ссылку на Google Meet
            meet_link = None
            # Сначала проверяем hangoutLink (более простой способ)
            if 'hangoutLink' in event_data and event_data['hangoutLink']:
                meet_link = event_data['hangoutLink']
            # Если нет hangoutLink, проверяем conferenceData
            elif 'conferenceData' in event_data:
                if 'entryPoints' in event_data['conferenceData']:
                    for entry_point in event_data['conferenceData']['entryPoints']:
                        if entry_point.get('entryPointType') == 'video':
                            meet_link = entry_point.get('uri')
                            break
            
            # Извлекаем информацию о создателе
            creator_email = None
            creator_name = None
            if 'creator' in event_data:
                creator_email = event_data['creator'].get('email')
                creator_name = event_data['creator'].get('displayName')
            
            # Создаем объект события для шаблона
            event_obj = {
                'id': event_data['id'],
                'title': event_data.get('summary', 'Без названия'),
                'description': event_data.get('description', ''),
                'start_datetime': start_time,  # Для совместимости с шаблоном
                'end_datetime': end_time,      # Для совместимости с шаблоном
                'start_time': start_time,      # Дублируем для обратной совместимости
                'end_time': end_time,          # Дублируем для обратной совместимости
                'is_all_day': 'date' in event_data['start'],
                'all_day': 'date' in event_data['start'],  # Дублируем для обратной совместимости
                'location': event_data.get('location', ''),
                'status': event_data.get('status', 'confirmed'),
                'attendees': attendees,
                'meet_link': meet_link,
                'creator_email': creator_email,
                'creator_name': creator_name,
                'calendar_id': event_data.get('calendar_id', 'primary'),
                'html_link': event_data.get('htmlLink', ''),  # Ссылка на событие в Google Calendar
                'google_created_at': datetime.fromisoformat(event_data['created'].replace('Z', '+00:00')) if 'created' in event_data else None,
                'google_updated_at': datetime.fromisoformat(event_data['updated'].replace('Z', '+00:00')) if 'updated' in event_data else None,
            }
            events.append(event_obj)
        except Exception as e:
            print(f"Ошибка обработки события {event_data.get('id', 'unknown')}: {e}")
            continue
    
    # Сортируем события по времени начала
    events.sort(key=lambda x: x['start_time'] if x['start_time'] else datetime.min)
    
    # Моковые данные: если нет реальных событий, подставляем демо-события
    if len(events) == 0:
        import pytz
        minsk_tz = pytz.timezone('Europe/Minsk')
        today = timezone.now().astimezone(minsk_tz)
        for i in range(5):
            day = today + timedelta(days=i)
            if day.weekday() < 5:  # пн-пт
                start = day.replace(hour=10 + i % 4, minute=0, second=0, microsecond=0)
                end = start + timedelta(hours=1)
                events.append({
                    'id': f'mock-{i}',
                    'title': f'Демо-встреча {i + 1}',
                    'description': 'Моковое событие (нет данных из календаря)',
                    'start_datetime': start,
                    'end_datetime': end,
                    'start_time': start,
                    'end_time': end,
                    'is_all_day': False,
                    'all_day': False,
                    'location': '',
                    'status': 'confirmed',
                    'attendees': [],
                    'meet_link': f'https://meet.google.com/abc-defg-hij' if i < 2 else None,
                    'creator_email': None,
                    'creator_name': None,
                    'calendar_id': 'primary',
                    'html_link': '',
                    'google_created_at': None,
                    'google_updated_at': None,
                })
        events.sort(key=lambda x: x['start_time'] if x['start_time'] else datetime.min)
    
    # Отладочная информация
    print(f"🔍 DEBUG: Found {len(events)} total events for calendar page (from cache/API)")
    for event in events[:5]:  # Показываем первые 5 событий
        print(f"🔍 DEBUG: Event: {event['title']} at {event['start_time']}")
    
    # Поиск и фильтрация
    from .forms import CalendarEventSearchForm
    search_form = CalendarEventSearchForm(request.GET)
    if search_form.is_valid():
        search = search_form.cleaned_data.get('search')
        date_from = search_form.cleaned_data.get('date_from')
        date_to = search_form.cleaned_data.get('date_to')
        
        # Фильтруем события в памяти
        filtered_events = []
        for event in events:
            # Поиск по названию и описанию
            if search:
                if not (search.lower() in event['title'].lower() or 
                       search.lower() in event['description'].lower()):
                    continue
            
            # Фильтр по дате начала
            if date_from and event['start_time']:
                if event['start_time'].date() < date_from:
                    continue
            
            # Фильтр по дате окончания
            if date_to and event['start_time']:
                if event['start_time'].date() > date_to:
                    continue
            
            
            filtered_events.append(event)
        
        events = filtered_events
    
    # Пагинация (для списка объектов)
    from django.core.paginator import Paginator
    paginator = Paginator(events, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Получаем настройки слотов для пользователя
    slots_settings = SlotsSettings.get_or_create_for_user(user)
    print(f"🔍 DEBUG SLOTS: Настройки для пользователя {user.username}: {slots_settings.to_dict()}")
    
    # Рабочие часы для календаря: приоритет компания > пользователь (см. SLOTS_LOGIC)
    from logic.working_hours_service import get_effective_working_hours
    from apps.company_settings.models import CompanySettings
    company_settings = None
    try:
        company_settings = CompanySettings.get_settings()
    except Exception:
        pass
    calendar_hours = get_effective_working_hours(
        user, company_settings, user_is_participant=True, company_hours_priority=True
    )
    
    context = {
        'page_obj': page_obj,
        'search_form': search_form,
        'integration': integration,
        'total_count': len(events),
        'slots_settings': slots_settings,
        'calendar_work_hours': calendar_hours,
    }
    
    return render(request, 'google_oauth/calendar_events.html', context)


@login_required
@permission_required('google_oauth.view_googledrivefile', raise_exception=True)
def drive_files(request):
    """Список файлов Google Drive"""
    user = request.user
    
    # Проверяем OAuth аккаунт
    oauth_service = GoogleOAuthService(user)
    integration = oauth_service.get_oauth_account()
    
    # Временно отключаем проверку токена для диагностики
    if not integration:
        messages.warning(request, 'Необходимо подключить Google аккаунт для просмотра файлов Drive.')
        return redirect('google_oauth:dashboard')
    
    # Проверяем токен, но не перенаправляем, если он истек
    if not integration.is_token_valid():
        print(f"🔍 DEBUG DRIVE: Token expired, but continuing anyway for debugging")
        messages.warning(request, 'Токен Google истек. Рекомендуется переподключить аккаунт.')
    
    # Получаем файлы из кэша через API (logic ожидает oauth_account — модель)
    drive_service = GoogleDriveService(integration)
    try:
        files_data = drive_service.get_files(max_results=100)
    except Exception as e:
        print(f"🔍 DEBUG DRIVE_FILES: Ошибка получения файлов: {e}")
        files_data = []
    
    # Преобразуем данные API в формат для шаблона
    files = []
    for file_data in files_data:
        try:
            # Парсим даты
            created_time = datetime.fromisoformat(file_data['createdTime'].replace('Z', '+00:00'))
            modified_time = datetime.fromisoformat(file_data['modifiedTime'].replace('Z', '+00:00'))
            
            # Создаем объект файла для шаблона
            file_size = int(file_data.get('size', 0)) if file_data.get('size') else None
            file_mime_type = file_data['mimeType']
            
            file_obj = {
                'id': file_data['id'],
                'name': file_data['name'],
                'mime_type': file_mime_type,
                'size': file_size,
                'created_time': created_time,
                'modified_time': modified_time,
                'web_view_link': file_data.get('webViewLink', ''),
                'web_content_link': file_data.get('webContentLink', ''),
                'parents': file_data.get('parents', []),
                'is_folder': file_mime_type == 'application/vnd.google-apps.folder',
                'is_shared': False,  # Пока не реализовано в API
                'get_size_display': lambda: format_file_size(file_size),
                'get_file_type_display': lambda: get_file_type_display(file_mime_type),
            }
            files.append(file_obj)
        except Exception as e:
            print(f"Ошибка обработки файла {file_data.get('id', 'unknown')}: {e}")
            continue
    
    # Сортируем файлы по времени изменения
    files.sort(key=lambda x: x['modified_time'], reverse=True)
    
    # Поиск и фильтрация
    from .forms import DriveFileSearchForm
    search_form = DriveFileSearchForm(request.GET)
    if search_form.is_valid():
        search = search_form.cleaned_data.get('search')
        is_shared = search_form.cleaned_data.get('is_shared')
        shared_with_me = search_form.cleaned_data.get('shared_with_me')
        
        # Фильтруем файлы в памяти
        filtered_files = []
        for file_obj in files:
            # Поиск по названию
            if search:
                if search.lower() not in file_obj['name'].lower():
                    continue
            
            # Фильтр по общему доступу (пока не реализовано)
            if is_shared == 'true' and not file_obj['is_shared']:
                continue
            elif is_shared == 'false' and file_obj['is_shared']:
                continue
            
            # Фильтр по "поделились со мной" (пока не реализовано)
            if shared_with_me == 'true' and not file_obj.get('shared_with_me', False):
                continue
            elif shared_with_me == 'false' and file_obj.get('shared_with_me', False):
                continue
            
            filtered_files.append(file_obj)
        
        files = filtered_files
    
    # Пагинация
    paginator = Paginator(files, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'search_form': search_form,
        'integration': integration,
    }
    
    return render(request, 'google_oauth/drive_files.html', context)


@login_required
@permission_required('google_oauth.change_syncsettings', raise_exception=True)
@require_POST
def sync_calendar(request):
    """Синхронизация календаря"""
    user = request.user
    oauth_service = GoogleOAuthService(user)
    oauth_account = oauth_service.get_oauth_account()
    
    if not oauth_account or not oauth_account.has_scope('https://www.googleapis.com/auth/calendar'):
        return JsonResponse({'success': False, 'message': 'Нет доступа к Google Calendar'})
    
    try:
        from .services import GoogleCalendarService
        calendar_service = GoogleCalendarService(oauth_service)
        calendar_service.sync_events(oauth_account)
        
        # Обновляем время последней синхронизации
        oauth_account.last_sync_at = timezone.now()
        oauth_account.save()
        
        return JsonResponse({
            'success': True,
            'message': 'События календаря успешно синхронизированы!'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Ошибка синхронизации календаря: {str(e)}'
        })


@login_required
@permission_required('google_oauth.change_syncsettings', raise_exception=True)
@require_POST
def sync_drive(request):
    """Синхронизация Google Drive"""
    user = request.user
    oauth_service = GoogleOAuthService(user)
    oauth_account = oauth_service.get_oauth_account()
    
    if not oauth_account or not oauth_account.has_scope('https://www.googleapis.com/auth/drive'):
        return JsonResponse({'success': False, 'message': 'Нет доступа к Google Drive'})
    
    try:
        from .services import GoogleDriveService
        drive_service = GoogleDriveService(oauth_service)
        drive_service.sync_files(oauth_account)
        
        # Обновляем время последней синхронизации
        oauth_account.last_sync_at = timezone.now()
        oauth_account.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Файлы Google Drive успешно синхронизированы!'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Ошибка синхронизации Drive: {str(e)}'
        })




@login_required
@permission_required('google_oauth.view_googleoauthaccount', raise_exception=True)
def test_oauth(request):
    """Страница тестирования OAuth"""
    user = request.user
    oauth_service = GoogleOAuthService(user)
    integration = oauth_service.get_oauth_account()
    
    context = {
        'integration': integration,
    }
    
    return render(request, 'google_oauth/test_oauth.html', context)


@login_required
@permission_required('google_oauth.view_googleoauthaccount', raise_exception=True)
def test_oauth_url(request):
    """API для тестирования создания OAuth URL"""
    user = request.user
    oauth_service = GoogleOAuthService(user)
    
    try:
        oauth_url = oauth_service.get_oauth_url()
        return JsonResponse({
            'success': True,
            'oauth_url': oauth_url
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        })


# Views для инвайтов
@login_required
@permission_required('google_oauth.view_invite', raise_exception=True)
def invite_list(request):
    """
    Список приглашений
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - request.user: аутентифицированный пользователь
    
    ИСТОЧНИКИ ДАННЫХ:
    - Invite.objects: приглашения пользователя
    - Vacancy.objects: вакансии для фильтрации
    
    ОБРАБОТКА:
    - Получение приглашений пользователя
    - Фильтрация по статусу и вакансии
    - Пагинация результатов
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - context: словарь с приглашениями и пагинацией
    - render: HTML страница 'google_oauth/invite_list.html'
    
    СВЯЗИ:
    - Использует: Invite, Vacancy модели
    - Передает данные в: google_oauth/invite_list.html
    - Может вызываться из: google_oauth/ URL patterns
    """
    invites = Invite.objects.filter(user=request.user)
    
    # Фильтрация
    status_filter = request.GET.get('status')
    if status_filter:
        invites = invites.filter(status=status_filter)
    
    # Поиск
    search_query = request.GET.get('search')
    if search_query:
        invites = invites.filter(
            Q(candidate_name__icontains=search_query) |
            Q(vacancy_title__icontains=search_query)
        )
    
    # Пагинация
    paginator = Paginator(invites, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'status_filter': status_filter,
        'search_query': search_query,
        'status_choices': Invite.STATUS_CHOICES,
    }
    
    return render(request, 'google_oauth/invite_list.html', context)


@login_required
@permission_required('google_oauth.add_invite', raise_exception=True)
def invite_create(request):
    """
    Создание нового приглашения
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - request.POST: данные формы приглашения
    - request.user: аутентифицированный пользователь
    
    ИСТОЧНИКИ ДАННЫХ:
    - POST данные формы создания приглашения
    - Vacancy.objects: вакансии для выбора
    - User.objects: пользователи для приглашения
    
    ОБРАБОТКА:
    - Валидация данных формы
    - Создание нового приглашения
    - Отправка приглашения через Google Calendar
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - messages: сообщение о результате создания
    - redirect: на google_oauth:invite_list
    
    СВЯЗИ:
    - Использует: Invite.objects.create(), Vacancy, User модели
    - Передает: HTTP redirect
    - Может вызываться из: google_oauth/ URL patterns
    """
    print(f"🔍 INVITE_CREATE: Метод запроса: {request.method}")
    print(f"🔍 INVITE_CREATE: Пользователь: {request.user}")
    
    if request.method == 'POST':
        print(f"🔍 INVITE_CREATE: POST запрос получен!")
        print(f"🔍 INVITE_CREATE: POST данные: {request.POST}")
        print(f"🔍 INVITE_CREATE: Пользователь: {request.user}")
        
        form = InviteForm(request.POST, user=request.user)
        print(f"🔍 INVITE_CREATE: Форма создана")
        
        is_valid = form.is_valid()
        print(f"🔍 INVITE_CREATE: Форма валидна: {is_valid}")
        
        if not is_valid:
            print(f"❌ INVITE_CREATE: Ошибки формы: {form.errors}")
            print(f"❌ INVITE_CREATE: Ошибки полей: {form.errors.as_data()}")
        
        if is_valid:
            try:
                print(f"🔍 INVITE_CREATE: Начинаем сохранение формы...")
                invite = form.save()
                print(f"🔍 INVITE_CREATE: Инвайт сохранен с ID: {invite.id}")
                messages.success(
                    request, 
                    f'Инвайт успешно создан! Scorecard доступен по ссылке: {invite.google_drive_file_url}'
                )
                print(f"🔍 INVITE_CREATE: Перенаправляем на детальную страницу...")
                return redirect('google_oauth:invite_detail', pk=invite.pk)
            except Exception as e:
                print(f"❌ INVITE_CREATE: Ошибка при сохранении: {e}")
                import traceback
                traceback.print_exc()
                messages.error(request, f'Ошибка создания инвайта: {str(e)}')
        else:
            print(f"❌ INVITE_CREATE: Форма не валидна, показываем ошибки")
    else:
        print(f"🔍 INVITE_CREATE: GET запрос, создаем пустую форму")
        form = InviteForm(user=request.user)
    
    # Получаем настройки структуры папок для отображения
    try:
        path_settings = ScorecardPathSettings.objects.get(user=request.user)
        path_preview = path_settings.generate_path_preview()
    except ScorecardPathSettings.DoesNotExist:
        path_preview = "Настройки структуры папок не найдены"
    
    context = {
        'form': form,
        'title': 'Создать инвайт',
        'path_preview': path_preview
    }
    
    return render(request, 'google_oauth/invite_form.html', context)


@login_required
@permission_required('google_oauth.view_invite', raise_exception=True)
def invite_detail(request, pk):
    """
    Детали приглашения
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - pk: ID приглашения
    - request.user: аутентифицированный пользователь
    
    ИСТОЧНИКИ ДАННЫЕ:
    - Invite.objects: приглашения пользователя
    - Vacancy.objects: связанные вакансии
    
    ОБРАБОТКА:
    - Получение приглашения по ID
    - Проверка прав доступа
    - Получение связанных данных
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - context: словарь с данными приглашения
    - render: HTML страница 'google_oauth/invite_detail.html'
    
    СВЯЗИ:
    - Использует: Invite, Vacancy модели
    - Передает данные в: google_oauth/invite_detail.html
    - Может вызываться из: google_oauth/ URL patterns
    """
    invite = get_object_or_404(
        Invite.objects.prefetch_related('interviewers'),
        pk=pk, user=request.user
    )
    
    context = {
        'invite': invite,
    }
    
    return render(request, 'google_oauth/invite_detail.html', context)


@login_required
@permission_required('google_oauth.change_invite', raise_exception=True)
def invite_update(request, pk):
    """
    Обновление приглашения
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - pk: ID приглашения
    - request.POST: данные формы обновления
    - request.user: аутентифицированный пользователь
    
    ИСТОЧНИКИ ДАННЫЕ:
    - POST данные формы обновления приглашения
    - Invite.objects: приглашения пользователя
    - Vacancy.objects: связанные вакансии
    
    ОБРАБОТКА:
    - Получение приглашения по ID
    - Проверка прав доступа
    - Валидация данных формы
    - Обновление приглашения
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - messages: сообщение о результате обновления
    - redirect: на google_oauth:invite_detail
    
    СВЯЗИ:
    - Использует: Invite.objects.get(), Vacancy модели
    - Передает: HTTP redirect
    - Может вызываться из: google_oauth/ URL patterns
    """
    invite = get_object_or_404(Invite, pk=pk, user=request.user)
    
    if request.method == 'POST':
        form = InviteUpdateForm(request.POST, instance=invite)
        if form.is_valid():
            form.save()
            messages.success(request, 'Инвайт успешно обновлен!')
            return redirect('google_oauth:invite_detail', pk=invite.pk)
    else:
        form = InviteUpdateForm(instance=invite)
    
    context = {
        'form': form,
        'invite': invite,
        'title': _('Редактировать инвайт')
    }
    
    return render(request, 'google_oauth/invite_form.html', context)


@login_required
@permission_required('google_oauth.delete_invite', raise_exception=True)
def invite_delete(request, pk):
    """
    Удаление приглашения
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - pk: ID приглашения
    - request.user: аутентифицированный пользователь
    
    ИСТОЧНИКИ ДАННЫЕ:
    - Invite.objects: приглашения пользователя
    
    ОБРАБОТКА:
    - Получение приглашения по ID
    - Проверка прав доступа
    - Удаление приглашения из базы данных
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - messages: сообщение о результате удаления
    - redirect: на google_oauth:invite_list
    
    СВЯЗИ:
    - Использует: Invite.objects.get()
    - Передает: HTTP redirect
    - Может вызываться из: google_oauth/ URL patterns
    """
    invite = get_object_or_404(Invite, pk=pk, user=request.user)
    
    if request.method == 'POST':
        # Удаляем событие из Google Calendar перед удалением инвайта
        try:
            calendar_deleted = invite.delete_calendar_event()
            if calendar_deleted:
                print(f"✅ Событие календаря удалено для инвайта {invite.pk}")
            else:
                print(f"⚠️ Не удалось удалить событие календаря для инвайта {invite.pk}")
        except Exception as e:
            print(f"❌ Ошибка при удалении события календаря: {e}")
        
        # Удаляем инвайт
        invite.delete()
        messages.success(request, 'Инвайт успешно удален!')
        return redirect('google_oauth:invite_list')
    
    context = {
        'invite': invite,
    }
    
    return render(request, 'google_oauth/invite_confirm_delete.html', context)


@login_required
@permission_required('google_oauth.change_invite', raise_exception=True)
@require_POST
def invite_regenerate_scorecard(request, pk):
    """Пересоздание scorecard для инвайта"""
    invite = get_object_or_404(Invite, pk=pk, user=request.user)
    
    try:
        # Удаляем старую структуру (если есть)
        if invite.google_drive_folder_id:
            # TODO: Реализовать удаление папки из Google Drive
            pass
        
        # Создаем новую структуру
        success, message = invite.create_google_drive_structure()
        if not success:
            return JsonResponse({'success': False, 'message': message})
        
        # Обрабатываем scorecard
        success, message = invite.process_scorecard()
        if not success:
            return JsonResponse({'success': False, 'message': message})
        
        invite.save()
        
        return JsonResponse({
            'success': True, 
            'message': 'Scorecard успешно пересоздан',
            'file_url': invite.google_drive_file_url
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Ошибка: {str(e)}'})


@login_required
@permission_required('google_oauth.view_invite', raise_exception=True)
def invite_dashboard(request):
    """Дашборд инвайтов"""
    user = request.user
    
    # Статистика
    total_invites = Invite.objects.filter(user=user).count()
    pending_invites = Invite.objects.filter(user=user, status='pending').count()
    sent_invites = Invite.objects.filter(user=user, status='sent').count()
    completed_invites = Invite.objects.filter(user=user, status='completed').count()
    
    # Последние инвайты
    recent_invites = Invite.objects.filter(user=user).order_by('-created_at')[:5]
    
    # Предстоящие интервью
    upcoming_interviews = Invite.objects.filter(
        user=user,
        interview_datetime__gte=timezone.now(),
        status__in=['pending', 'sent']
    ).order_by('interview_datetime')[:5]
    
    context = {
        'total_invites': total_invites,
        'pending_invites': pending_invites,
        'sent_invites': sent_invites,
        'completed_invites': completed_invites,
        'recent_invites': recent_invites,
        'upcoming_interviews': upcoming_interviews,
    }
    
    return render(request, 'google_oauth/invite_dashboard.html', context)


@login_required
@permission_required('google_oauth.view_googleoauthaccount', raise_exception=True)
def check_integration(request):
    """API для проверки состояния интеграции"""
    user = request.user
    oauth_service = GoogleOAuthService(user)
    
    try:
        integration = oauth_service.get_oauth_account()
        return JsonResponse({
            'success': True,
            'connected': integration.is_token_valid if integration else False,
            'expires_at': integration.expires_at.isoformat() if integration and integration.expires_at else None
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        })


@login_required
@permission_required('google_oauth.view_googlecalendar', raise_exception=True)
def get_event_details(request, event_id):
    """API для получения детальной информации о событии календаря"""
    user = request.user
    
    # Проверяем OAuth аккаунт
    oauth_service = GoogleOAuthService(user)
    integration = oauth_service.get_oauth_account()
    
    if not integration:
        return JsonResponse({
            'success': False,
            'message': 'Google аккаунт не подключен'
        })
    
    try:
        # Получаем события из кэша через API (logic ожидает oauth_account)
        calendar_service = GoogleCalendarService(integration)
        events_data = calendar_service.get_events(days_ahead=100)
        
        # Ищем нужное событие
        event_data = None
        for event in events_data:
            if event['id'] == event_id:
                event_data = event
                break
        
        if not event_data:
            return JsonResponse({
                'success': False,
                'message': 'Событие не найдено'
            })
        
        # Парсим время начала и окончания
        start_time = None
        end_time = None
        
        if 'dateTime' in event_data['start']:
            start_time = datetime.fromisoformat(event_data['start']['dateTime'].replace('Z', '+00:00'))
        elif 'date' in event_data['start']:
            start_time = datetime.fromisoformat(event_data['start']['date'] + 'T00:00:00+00:00')
        
        if 'dateTime' in event_data['end']:
            end_time = datetime.fromisoformat(event_data['end']['dateTime'].replace('Z', '+00:00'))
        elif 'date' in event_data['end']:
            end_time = datetime.fromisoformat(event_data['end']['date'] + 'T23:59:59+00:00')
        
        # Извлекаем участников
        attendees = []
        if 'attendees' in event_data:
            for attendee in event_data['attendees']:
                attendee_info = {
                    'email': attendee.get('email', ''),
                    'name': attendee.get('displayName', ''),
                    'response_status': attendee.get('responseStatus', 'needsAction'),
                    'organizer': attendee.get('organizer', False),
                }
                attendees.append(attendee_info)
        
        # Извлекаем ссылку на Google Meet
        meet_link = None
        if 'hangoutLink' in event_data and event_data['hangoutLink']:
            meet_link = event_data['hangoutLink']
        elif 'conferenceData' in event_data:
            if 'entryPoints' in event_data['conferenceData']:
                for entry_point in event_data['conferenceData']['entryPoints']:
                    if entry_point.get('entryPointType') == 'video':
                        meet_link = entry_point.get('uri')
                        break
        
        # Извлекаем информацию о создателе
        creator_email = None
        creator_name = None
        if 'creator' in event_data:
            creator_email = event_data['creator'].get('email')
            creator_name = event_data['creator'].get('displayName')
        
        # Формируем ответ
        event_details = {
            'id': event_data['id'],
            'title': event_data.get('summary', 'Без названия'),
            'description': event_data.get('description', ''),
            'start_time': start_time.isoformat() if start_time else None,
            'end_time': end_time.isoformat() if end_time else None,
            'is_all_day': 'date' in event_data['start'],
            'location': event_data.get('location', ''),
            'status': event_data.get('status', 'confirmed'),
            'attendees': attendees,
            'meet_link': meet_link,
            'creator_email': creator_email,
            'creator_name': creator_name,
            'calendar_id': event_data.get('calendar_id', 'primary'),
            'html_link': event_data.get('htmlLink', ''),
            'created': event_data.get('created'),
            'updated': event_data.get('updated'),
        }
        
        return JsonResponse({
            'success': True,
            'event': event_details
        })
        
    except Exception as e:
        print(f"Ошибка получения деталей события {event_id}: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'message': f'Ошибка получения деталей события: {str(e)}'
        })


@login_required
@permission_required('google_oauth.view_scorecardpathsettings', raise_exception=True)
def scorecard_path_settings(request):
    """Страница настроек структуры папок для scorecard"""
    try:
        # Получаем или создаем настройки для пользователя
        settings_obj, created = ScorecardPathSettings.objects.get_or_create(
            user=request.user,
            defaults={'folder_structure': []}
        )
        
        # Если настройки только что созданы, устанавливаем структуру по умолчанию
        if created or not settings_obj.folder_structure:
            settings_obj.folder_structure = settings_obj.get_default_structure()
            settings_obj.save()
        
        # Отладка: выводим структуру папок
        print(f"🔍 DEBUG: folder_structure = {settings_obj.folder_structure}")
        
        # Получаем доступные паттерны
        available_patterns = settings_obj.get_available_patterns()
        
        # Генерируем предварительный просмотр
        path_preview = settings_obj.generate_path_preview()
        print(f"🔍 DEBUG: path_preview = {path_preview}")
        
        # Получаем информацию о вакансиях пользователя для примера
        from apps.vacancies.models import Vacancy
        user_vacancies = Vacancy.objects.filter(recruiter=request.user)[:5]
        
        # Конвертируем паттерны в JSON для JavaScript
        import json
        available_patterns_json = json.dumps(available_patterns, ensure_ascii=False)
        
        context = {
            'settings': settings_obj,
            'available_patterns': available_patterns_json,
            'path_preview': path_preview,
            'user_vacancies': user_vacancies,
        }
        
        return render(request, 'google_oauth/scorecard_path_settings.html', context)
        
    except Exception as e:
        messages.error(request, f'Ошибка загрузки настроек: {str(e)}')
        return redirect('google_oauth:invite_dashboard')



@login_required
@permission_required('google_oauth.change_scorecardpathsettings', raise_exception=True)
@require_POST
def api_scorecard_path_settings(request):
    """API для сохранения настроек структуры папок"""
    try:
        import json
        
        # Получаем данные из запроса
        data = json.loads(request.body)
        folder_structure = data.get('folder_structure', None)
        protected_sheet_names = data.get('protected_sheet_names', None)
        
        # Получаем или создаем настройки (нужно и для частичных обновлений)
        settings_obj, created = ScorecardPathSettings.objects.get_or_create(
            user=request.user,
            defaults={'folder_structure': []}
        )
        
        # Если обновляем только защищённые листы — структуру не трогаем
        if folder_structure is None and protected_sheet_names is None:
            return JsonResponse({
                'success': False,
                'message': 'Не переданы данные для обновления'
            })

        # Обновляем список защищённых листов (если пришёл)
        if protected_sheet_names is not None:
            raw = (protected_sheet_names or '').strip()
            # Нормализуем: split по запятым, trim, удаляем пустые, убираем дубли
            parts = [p.strip() for p in raw.split(',')] if raw else []
            seen = set()
            normalized = []
            for p in parts:
                if not p:
                    continue
                key = p.lower()
                if key in seen:
                    continue
                seen.add(key)
                normalized.append(p)
            settings_obj.protected_sheet_names = ', '.join(normalized)

        # Если folder_structure не передали — просто сохраняем защищённые листы и выходим
        if folder_structure is None:
            settings_obj.save()
            return JsonResponse({
                'success': True,
                'message': 'Настройки сохранены успешно',
                'path_preview': settings_obj.generate_path_preview()
            })
        
        print(f"🔍 DEBUG: Received folder_structure: {folder_structure}")
        for i, item in enumerate(folder_structure):
            print(f"🔍 DEBUG: Item {i}: type={item.get('type')}, value='{item.get('value')}', isEmpty={not item.get('value') or item.get('value').strip() == ''}")
        
        # Валидация структуры
        if not isinstance(folder_structure, list):
            return JsonResponse({
                'success': False,
                'message': 'Структура папок должна быть массивом'
            })
        
        # Парсим и валидируем каждый элемент
        parsed_structure = []
        for item in folder_structure:
            if not isinstance(item, dict):
                return JsonResponse({
                    'success': False,
                    'message': 'Каждый элемент структуры должен быть объектом'
                })
            
            if 'type' not in item:
                return JsonResponse({
                    'success': False,
                    'message': 'Каждый элемент должен содержать поле "type"'
                })
            
            # Если это смешанный тип (множественные паттерны), сохраняем как есть
            if item['type'] == 'mixed':
                # Для mixed-типа сохраняем весь элемент как есть, не разбивая на части
                parsed_structure.append({
                    'type': 'mixed',
                    'value': item.get('value', ''),
                    'patterns': item.get('patterns', [])  # Сохраняем массив паттернов
                })
            else:
                # Обычная валидация для одиночных паттернов
                if item['type'] == 'text':
                    print(f"🔍 DEBUG: Validating text field: value='{item.get('value')}', hasValue={'value' in item}, isEmpty={not item.get('value') or not item.get('value').strip()}")
                    if 'value' not in item or not item['value'].strip():
                        print(f"❌ DEBUG: Text field validation failed for item: {item}")
                        return JsonResponse({
                            'success': False,
                            'message': 'Текстовые поля не могут быть пустыми'
                        })
                    
                    # Проверка на недопустимые символы в именах папок
                    value = item['value'].strip()
                    invalid_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
                    for char in invalid_chars:
                        if char in value:
                            return JsonResponse({
                                'success': False,
                                'message': f'Недопустимый символ "{char}" в текстовом поле'
                            })
                else:
                    # Для паттернов (не text) значение может быть пустым
                    # Проверяем только, что поле value существует
                    if 'value' not in item:
                        item['value'] = ''
                
                parsed_structure.append(item)
        
        # Используем распарсенную структуру
        folder_structure = parsed_structure
        
        # Проверяем, что у нас есть хотя бы один элемент
        if not folder_structure:
            return JsonResponse({
                'success': False,
                'message': 'Структура папок не может быть пустой'
            })
        
        # Обновляем структуру
        settings_obj.folder_structure = folder_structure
        settings_obj.save()
        
        # Генерируем новый предварительный просмотр
        path_preview = settings_obj.generate_path_preview()
        
        return JsonResponse({
            'success': True,
            'message': 'Настройки сохранены успешно',
            'path_preview': path_preview
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': 'Неверный формат JSON'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Ошибка сохранения настроек: {str(e)}'
        })


@login_required
@permission_required('google_oauth.view_invite', raise_exception=True)
@require_POST
def get_invitation_text(request, pk):
    """API для получения текста приглашения"""
    try:
        invite = get_object_or_404(Invite, pk=pk, user=request.user)
        
        # Генерируем текст приглашения
        invitation_text = invite.get_invitation_text()
        
        return JsonResponse({
            'success': True,
            'invitation_text': invitation_text
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Ошибка получения текста приглашения: {str(e)}'
        })


@login_required
@permission_required('google_oauth.view_googlecalendar', raise_exception=True)
@require_POST
def get_meetings_count(request):
    """Получает количество встреч для указанных дат из Redis кэша"""
    try:
        import json
        from datetime import datetime, timedelta
        import pytz
        
        data = json.loads(request.body)
        dates = data.get('dates', [])
        
        if not dates:
            return JsonResponse({
                'success': False,
                'message': 'Не указаны даты'
            })
        
        from apps.google_oauth.services import GoogleOAuthService
        from apps.google_oauth.cache_service import GoogleAPICache
        
        oauth_service = GoogleOAuthService(request.user)
        oauth_account = oauth_service.get_oauth_account()
        
        if not oauth_account:
            return JsonResponse({
                'success': False,
                'message': 'Google OAuth не настроен'
            })
        
        # Получаем все события из кэша
        cached_events = GoogleAPICache.get_calendar_events(
            user_id=request.user.id,
            calendar_id='primary',
            days_ahead=100
        )
        
        print(f"🔍 DEBUG: Получено {len(cached_events) if cached_events else 0} событий из кэша")
        
        if not cached_events:
            print("⚠️ Нет кэшированных событий календаря")
            # Возвращаем нули для всех дат
            meetings_count = {date_str: 0 for date_str in dates}
            return JsonResponse({
                'success': True,
                'meetings_count': meetings_count,
                'debug': 'Нет кэшированных событий'
            })
        
        meetings_count = {}
        
        # Обрабатываем каждую дату
        for date_str in dates:
            try:
                # Парсим дату (формат: DD.MM)
                day, month = date_str.split('.')
                current_year = datetime.now().year
                target_date = datetime(current_year, int(month), int(day)).date()
                
                # Подсчитываем события на эту дату
                day_events_count = 0
                for event in cached_events:
                    try:
                        # Получаем дату начала события
                        start_data = event.get('start', {})
                        if 'dateTime' in start_data:
                            # Событие с конкретным временем
                            start_time_str = start_data['dateTime']
                            if start_time_str.endswith('Z'):
                                start_time_str = start_time_str[:-1] + '+00:00'
                            event_start = datetime.fromisoformat(start_time_str)
                            # Конвертируем из UTC в локальное время
                            minsk_tz = pytz.timezone('Europe/Minsk')
                            event_start = event_start.replace(tzinfo=pytz.UTC).astimezone(minsk_tz)
                            event_date = event_start.date()
                        elif 'date' in start_data:
                            # Событие на весь день
                            event_date = datetime.fromisoformat(start_data['date']).date()
                        else:
                            continue
                        
                        # Проверяем, совпадает ли дата
                        if event_date == target_date:
                            day_events_count += 1
                            
                    except Exception as e:
                        print(f"❌ Ошибка обработки события {event.get('id', 'unknown')}: {e}")
                        continue
                
                meetings_count[date_str] = day_events_count
                print(f"📅 Дата {date_str}: {day_events_count} событий")
                
            except Exception as e:
                print(f"❌ Ошибка обработки даты {date_str}: {e}")
                meetings_count[date_str] = 0
        
        print(f"✅ Получено количество встреч из кэша: {meetings_count}")
        
        return JsonResponse({
            'success': True,
            'meetings_count': meetings_count,
            'debug': f'Обработано {len(cached_events)} событий из кэша'
        })
        
    except Exception as e:
        print(f"❌ Ошибка получения количества встреч: {e}")
        return JsonResponse({
            'success': False,
            'message': f'Ошибка получения количества встреч: {str(e)}'
        })


@login_required
@permission_required('google_oauth.view_googleoauthaccount', raise_exception=True)
def debug_cache(request):
    """Отладочный endpoint для проверки кэша"""
    try:
        from apps.google_oauth.cache_service import GoogleAPICache
        
        cached_events = GoogleAPICache.get_calendar_events(
            user_id=request.user.id,
            calendar_id='primary',
            days_ahead=100
        )
        
        return JsonResponse({
            'success': True,
            'cached_events_count': len(cached_events) if cached_events else 0,
            'user_id': request.user.id,
            'has_oauth': bool(GoogleOAuthService(request.user).get_oauth_account())
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required
@permission_required('google_oauth.view_slotssettings', raise_exception=True)
@require_http_methods(["GET", "POST"])
def api_slots_settings(request):
    """API для получения и сохранения настроек слотов"""
    user = request.user
    
    if request.method == 'GET':
        # Получаем настройки
        settings = SlotsSettings.get_or_create_for_user(user)
        print(f"🔍 DEBUG API GET: Настройки для {user.username}: {settings.to_dict()}")
        return JsonResponse({
            'success': True,
            'settings': settings.to_dict()
        })
    
    elif request.method == 'POST':
        # Сохраняем настройки
        try:
            data = json.loads(request.body)
            print(f"🔍 DEBUG API POST: Получены данные: {data}")
            settings = SlotsSettings.get_or_create_for_user(user)
            print(f"🔍 DEBUG API POST: Текущие настройки: {settings.to_dict()}")
            
            # Обновляем поля
            settings.current_week_prefix = data.get('currentWeekPrefix', '')
            settings.next_week_prefix = data.get('nextWeekPrefix', '')
            settings.all_slots_prefix = data.get('allSlotsPrefix', '')
            settings.separator_text = data.get('separatorText', '---')
            
            print(f"🔍 DEBUG API POST: Новые настройки: {settings.to_dict()}")
            settings.save()
            print(f"🔍 DEBUG API POST: Настройки сохранены")
            
            return JsonResponse({
                'success': True,
                'message': 'Настройки слотов сохранены',
                'settings': settings.to_dict()
            })
            
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': 'Неверный JSON формат'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })


@login_required
@permission_required('google_oauth.add_invite', raise_exception=True)
def invite_create_combined(request):
    """Создание нового инвайта с объединенной формой"""
    print(f"🔍 INVITE_CREATE_COMBINED: Метод запроса: {request.method}")
    print(f"🔍 INVITE_CREATE_COMBINED: Пользователь: {request.user}")
    
    if request.method == 'POST':
        print(f"🔍 INVITE_CREATE_COMBINED: POST запрос получен!")
        print(f"🔍 INVITE_CREATE_COMBINED: POST данные: {request.POST}")
        
        form = InviteCombinedForm(request.POST, user=request.user)
        print(f"🔍 INVITE_CREATE_COMBINED: Форма создана")
        
        is_valid = form.is_valid()
        print(f"🔍 INVITE_CREATE_COMBINED: Форма валидна: {is_valid}")
        
        if not is_valid:
            print(f"❌ INVITE_CREATE_COMBINED: Ошибки формы: {form.errors}")
            print(f"❌ INVITE_CREATE_COMBINED: Ошибки полей: {form.errors.as_data()}")
        
        if is_valid:
            print(f"✅ INVITE_CREATE_COMBINED: Форма валидна, сохраняем инвайт...")
            try:
                invite = form.save()
                print(f"✅ INVITE_CREATE_COMBINED: Инвайт сохранен с ID: {invite.id}")
                messages.success(request, f'Инвайт успешно создан! ID: {invite.id}')
                return redirect('google_oauth:invite_detail', pk=invite.id)
            except Exception as e:
                print(f"❌ INVITE_CREATE_COMBINED: Ошибка при сохранении: {e}")
                import traceback
                traceback.print_exc()
                messages.error(request, f'Ошибка при создании инвайта: {str(e)}')
        else:
            print(f"❌ INVITE_CREATE_COMBINED: Форма невалидна")
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        print(f"🔍 INVITE_CREATE_COMBINED: GET запрос, создаем пустую форму")
        form = InviteCombinedForm(user=request.user)
    
    # Получаем настройки структуры папок для отображения
    try:
        path_settings = ScorecardPathSettings.get_or_create_for_user(request.user)
        path_preview = path_settings.get_path_preview()
    except Exception as e:
        print(f"❌ INVITE_CREATE_COMBINED: Ошибка получения настроек пути: {e}")
        path_preview = "Ошибка получения настроек"
    
    context = {
        'form': form,
        'title': 'Создание инвайта (Объединенная форма)',
        'path_preview': path_preview,
    }
    
    return render(request, 'google_oauth/invite_combined_form.html', context)


@login_required
@permission_required('google_oauth.view_invite', raise_exception=True)
@require_POST
def get_parser_time_analysis(request, pk):
    """API для получения анализа времени от парсера"""
    try:
        invite = get_object_or_404(Invite, pk=pk, user=request.user)
        
        # Проверяем, есть ли уже проанализированное время
        if invite.gemini_suggested_datetime:
            return JsonResponse({
                'success': True,
                'suggested_datetime': invite.gemini_suggested_datetime,
                'cached': True
            })
        
        # Если нет, анализируем время
        success, message = invite.analyze_time_with_parser()
        
        if success:
            return JsonResponse({
                'success': True,
                'suggested_datetime': invite.gemini_suggested_datetime,
                'cached': False
            })
        else:
            return JsonResponse({
                'success': False,
                'error': message
            })
            
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Ошибка анализа времени: {str(e)}'
        })


# Views для HR-скрининга
@login_required
@permission_required('google_oauth.view_hrscreening', raise_exception=True)
def hr_screening_list(request):
    """Список HR-скринингов"""
    hr_screenings = HRScreening.objects.filter(user=request.user).order_by('-created_at')
    
    # Пагинация
    paginator = Paginator(hr_screenings, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'hr_screenings': page_obj,
    }
    
    return render(request, 'google_oauth/hr_screening_list.html', context)


@login_required
@permission_required('google_oauth.add_hrscreening', raise_exception=True)
def hr_screening_create(request):
    """Создание нового HR-скрининга"""
    if request.method == 'POST':
        form = HRScreeningForm(request.POST, user=request.user)
        if form.is_valid():
            try:
                hr_screening = form.save()
                messages.success(request, 'HR-скрининг успешно создан и обработан!')
                return redirect('google_oauth:hr_screening_detail', pk=hr_screening.pk)
            except Exception as e:
                messages.error(request, f'Ошибка при создании HR-скрининга: {str(e)}')
    else:
        form = HRScreeningForm(user=request.user)
    
    context = {
        'form': form,
        'title': 'Создать HR-скрининг'
    }
    
    return render(request, 'google_oauth/hr_screening_form.html', context)


@login_required
@permission_required('google_oauth.view_hrscreening', raise_exception=True)
def hr_screening_detail(request, pk):
    """Детали HR-скрининга"""
    hr_screening = get_object_or_404(HRScreening, pk=pk, user=request.user)
    
    # Парсим анализ от Gemini
    parsed_analysis = hr_screening.get_parsed_analysis()
    
    # Получаем информацию о поле "Уровень" из Huntflow
    level_field_info = None
    if hr_screening.determined_grade:
        try:
            fields_schema_success, fields_schema = hr_screening.get_candidate_fields_schema()
            if fields_schema_success and fields_schema:
                # Ищем поле "Уровень" в схеме
                for field_id, field_data in fields_schema.items():
                    if field_data.get('title') == 'Уровень':
                        # Получаем список доступных значений
                        values = field_data.get('values', [])
                        determined_grade = hr_screening.determined_grade
                        
                        # Ищем правильное значение из вариантов
                        selected_value = None
                        selected_index = None
                        if determined_grade and values:
                            grade_name_lower = determined_grade.lower()
                            
                            # Ищем точное совпадение
                            for index, value in enumerate(values):
                                if value.lower() == grade_name_lower:
                                    selected_value = value
                                    selected_index = index
                                    break
                            
                            # Если точного совпадения нет, ищем частичное
                            if not selected_value:
                                for index, value in enumerate(values):
                                    if grade_name_lower in value.lower() or value.lower() in grade_name_lower:
                                        selected_value = value
                                        selected_index = index
                                        break
                        
                        level_field_info = {
                            'field_key': field_id,  # Используем field_id вместо search_field
                            'field_title': field_data.get('title', 'Уровень'),
                            'field_id': field_id,
                            'search_field': field_data.get('search_field', 'string_field_1'),
                            'selected_value': selected_value,  # Выбранное значение из вариантов
                            'selected_index': selected_index,  # Индекс выбранного значения
                            'available_values': values  # Все доступные варианты
                        }
                        break
        except Exception as e:
            print(f"Ошибка при получении информации о поле уровня: {e}")
    
    # Получаем информацию о поле "money" из Huntflow
    money_field_info = None
    if hr_screening.extracted_salary:
        try:
            fields_schema_success, fields_schema = hr_screening.get_candidate_fields_schema()
            if fields_schema_success and fields_schema:
                # Ищем поле "money" в схеме
                for field_id, field_data in fields_schema.items():
                    if field_data.get('title') == 'Зарплата' or field_id == 'money':
                        money_field_info = {
                            'field_key': field_id,  # Используем field_id вместо 'money'
                            'field_title': field_data.get('title', 'Зарплата'),
                            'field_id': field_id,
                            'search_field': 'money'
                        }
                        break
        except Exception as e:
            print(f"Ошибка при получении информации о поле зарплаты: {e}")
    
    # Получаем реальный account_id пользователя
    account_id = hr_screening._get_user_account_id()
    
    context = {
        'hr_screening': hr_screening,
        'parsed_analysis': parsed_analysis,
        'level_field_info': level_field_info,
        'money_field_info': money_field_info,
        'account_id': account_id,
    }
    
    return render(request, 'google_oauth/hr_screening_detail.html', context)


@login_required
@permission_required('google_oauth.delete_hrscreening', raise_exception=True)
def hr_screening_delete(request, pk):
    """Удаление HR-скрининга"""
    hr_screening = get_object_or_404(HRScreening, pk=pk, user=request.user)
    
    if request.method == 'POST':
        hr_screening.delete()
        messages.success(request, 'HR-скрининг успешно удален!')
        return redirect('hr_screening_list')
    
    context = {
        'hr_screening': hr_screening,
    }
    
    return render(request, 'google_oauth/hr_screening_confirm_delete.html', context)


@login_required
@permission_required('google_oauth.change_hrscreening', raise_exception=True)
@require_POST
def reject_candidate(request, hr_screening_id):
    """Обработка отказа кандидата после HR-скрининга"""
    try:
        hr_screening = get_object_or_404(HRScreening, pk=hr_screening_id, user=request.user)
        
        # Получаем данные из запроса
        data = json.loads(request.body) if request.body else {}
        message_id = data.get('message_id')
        rejection_type = (data.get('rejection_type') or '').strip()  # 'salary' | 'office_format' | пусто (приоритет)
        
        # Определяем причину отказа и статус
        rejection_status_id = None
        rejection_reason_id = None
        comment = ""
        
        from apps.huntflow.services import HuntflowService
        huntflow_service = HuntflowService(request.user)
        accounts = huntflow_service.get_accounts()
        
        if not accounts or 'items' not in accounts:
            return JsonResponse({'success': False, 'error': 'Нет доступных аккаунтов Huntflow'})
        
        account_id = accounts['items'][0]['id']
        
        # Проверяем превышение зарплаты
        salary_above_range = False
        if hr_screening.extracted_salary and hr_screening.salary_currency:
            salary_above_range = hr_screening.is_salary_above_range()
        
        # Проверяем офисный формат
        office_format_rejected = hr_screening.is_office_format_rejected()
        
        # Если указана конкретная причина — проверяем её и обрабатываем только её
        if rejection_type == 'salary':
            if not salary_above_range:
                return JsonResponse({'success': False, 'error': 'Причина «Финансы» не применима к этому кандидату'})
            salary_above_range = True
            office_format_rejected = False
        elif rejection_type == 'office_format':
            if not office_format_rejected:
                return JsonResponse({'success': False, 'error': 'Причина «Офис» не применима к этому кандидату'})
            office_format_rejected = True
            salary_above_range = False
        
        # Определяем причину отказа
        if salary_above_range:
            # Приоритет 1: Зарплата превышает вилку
            rejection_status_id, rejection_reason_id = hr_screening._find_salary_rejection_status(huntflow_service, account_id)
            
            # При отказе по ЗП не передаем комментарий - только причину отказа
            comment = ""
            
            # Причина отказа обязательна для отказа по ЗП
            if not rejection_reason_id:
                # Получаем список всех причин отказа для более информативного сообщения
                try:
                    rejection_reasons_data = huntflow_service.get_rejection_reasons(account_id)
                    all_reasons = []
                    if rejection_reasons_data and 'items' in rejection_reasons_data:
                        for reason in rejection_reasons_data['items']:
                            if isinstance(reason, dict) and reason.get('name'):
                                all_reasons.append(f"'{reason.get('name')}'")
                    
                    error_msg = 'Причина отказа "Высокие запросы по зарплате" не найдена в Huntflow.'
                    if all_reasons:
                        error_msg += f' Доступные причины отказа: {", ".join(all_reasons)}. Убедитесь, что в списке причин отказа есть причина с названием, содержащим "Высокие запросы по зарплате" или похожим.'
                    else:
                        error_msg += ' В списке причин отказа не найдено ни одной причины. Убедитесь, что причины отказа настроены в Huntflow.'
                    
                    return JsonResponse({
                        'success': False, 
                        'error': error_msg
                    })
                except Exception as e:
                    print(f"⚠️ REJECT_CANDIDATE: Ошибка при получении списка причин отказа: {e}")
                    return JsonResponse({
                        'success': False, 
                        'error': 'Причина отказа "Высокие запросы по зарплате" не найдена в Huntflow. Убедитесь, что в списке причин отказа есть причина с таким названием.'
                    })
            
            # Если статус не найден, но причина найдена, ищем статус отказа
            if not rejection_status_id and rejection_reason_id:
                statuses = huntflow_service.get_vacancy_statuses(account_id)
                if statuses and 'items' in statuses:
                    for status in statuses['items']:
                        if status.get('type', '').lower() == 'trash':
                            rejection_status_id = status.get('id')
                            print(f"✅ REJECT_CANDIDATE: Найден статус отказа (ID: {rejection_status_id}) для причины отказа (ID: {rejection_reason_id})")
                            break
        elif office_format_rejected:
            # Приоритет 2: Офисный формат
            rejection_status_id, rejection_reason_id = hr_screening._find_rejection_status_with_reason(huntflow_service, account_id, 'office_format')
            comment = "Отказ по офисному формату"
        else:
            # Общий отказ (если нет специфической причины)
            # Ищем статус отказа типа 'trash'
            statuses = huntflow_service.get_vacancy_statuses(account_id)
            if statuses and 'items' in statuses:
                for status in statuses['items']:
                    if status.get('type', '').lower() == 'trash':
                        rejection_status_id = status.get('id')
                        break
        
        if not rejection_status_id:
            return JsonResponse({'success': False, 'error': 'Статус отказа не найден в Huntflow'})
        
        # Убеждаемся, что комментарий не пустой (только для не-ЗП отказов)
        if not comment and not salary_above_range:
            if office_format_rejected:
                comment = "Отказ по офисному формату"
            else:
                comment = "Отказ кандидата"
        
        print(f"🔍 REJECT_CANDIDATE: rejection_status_id={rejection_status_id}, rejection_reason_id={rejection_reason_id}, comment='{comment}'")
        
        # Формируем текст статуса для отображения (нужен и для ответа, и для metadata)
        status_text = "Данные сохранены. Статус - Отказ"
        if salary_above_range:
            status_text = "Данные сохранены. Статус - Отказ: Высокие ЗП ожидания"
        elif office_format_rejected:
            status_text = "Данные сохранены. Статус - Отказ: Офисный формат"

        # Обновляем статус в Huntflow
        status_result = hr_screening._update_applicant_status_with_rejection(
            huntflow_service,
            account_id,
            int(hr_screening.candidate_id),
            rejection_status_id,
            comment,
            int(hr_screening.vacancy_id) if hr_screening.vacancy_id else None,
            rejection_reason_id
        )
        
        if not status_result:
            return JsonResponse({'success': False, 'error': 'Не удалось обновить статус в Huntflow'})
        
        # Обновляем metadata сообщения, если указан message_id
        if message_id:
            try:
                from .models import ChatMessage
                
                # Получаем текущие metadata из базы
                chat_message = ChatMessage.objects.get(id=int(message_id), session__user=request.user)
                current_metadata = chat_message.metadata or {}
                
                # Создаем НОВЫЙ словарь с обновленными данными
                new_metadata = dict(current_metadata)
                new_metadata['rejected'] = True
                new_metadata['rejection_status_id'] = rejection_status_id
                new_metadata['rejection_reason_id'] = rejection_reason_id
                new_metadata['rejection_comment'] = comment
                new_metadata['rejection_status_text'] = status_text
                new_metadata['rejection_form_answered'] = True  # Ключевое поле!

                # Сохраняем через ORM (корректно для SQLite/PostgreSQL и не падает на debug_sql)
                ChatMessage.objects.filter(id=chat_message.id, session__user=request.user).update(metadata=new_metadata)
                chat_message.refresh_from_db(fields=['metadata'])
                
                # Проверяем, что данные действительно сохранились
                saved_answered = chat_message.metadata.get('rejection_form_answered', False)
                saved_rejected = chat_message.metadata.get('rejected', False)
                print(f"✅ REJECT_CANDIDATE: Metadata сообщения {message_id} сохранено. rejection_form_answered={saved_answered} (тип: {type(saved_answered)}), rejected={saved_rejected}, все ключи: {list(chat_message.metadata.keys())}")
            except ChatMessage.DoesNotExist:
                print(f"⚠️ REJECT_CANDIDATE: Сообщение {message_id} не найдено")
            except Exception as e:
                print(f"⚠️ REJECT_CANDIDATE: Ошибка обновления metadata: {e}")
                import traceback
                traceback.print_exc()
        
        return JsonResponse({
            'success': True,
            'message': 'Кандидат успешно отклонен',
            'rejection_status_id': rejection_status_id,
            'rejection_reason_id': rejection_reason_id,
            'status_text': status_text,
            'rejection_type': 'salary' if salary_above_range else ('office_format' if office_format_rejected else 'general')
        })
        
    except Exception as e:
        print(f"❌ REJECT_CANDIDATE: Ошибка при отказе кандидата: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@permission_required('google_oauth.change_hrscreening', raise_exception=True)
@require_POST
def hr_screening_retry_analysis(request, pk):
    """Повторный анализ HR-скрининга с помощью Gemini"""
    hr_screening = get_object_or_404(HRScreening, pk=pk, user=request.user)
    
    try:
        success, message = hr_screening.analyze_with_gemini()
        
        if success:
            return JsonResponse({
                'success': True,
                'message': 'Анализ успешно выполнен',
                'analysis': hr_screening.gemini_analysis
            })
        else:
            return JsonResponse({
                'success': False,
                'error': message
            })
            
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Ошибка анализа: {str(e)}'
        })


@login_required
@permission_required('google_oauth.view_googleoauthaccount', raise_exception=True)
def gdata_automation(request):
    """Страница G-данных и автоматизации с выбором вакансии"""
    from apps.vacancies.models import Vacancy
    from apps.google_oauth.services import GoogleOAuthService, GoogleCalendarService
    from apps.google_oauth.cache_service import GoogleAPICache
    import json
    from datetime import datetime, timedelta
    import pytz
    
    # Получаем все активные вакансии
    active_vacancies = Vacancy.objects.filter(is_active=True).order_by('name')
    
    # Получаем выбранную вакансию из параметров
    selected_vacancy_id = request.GET.get('vacancy_id')
    selected_vacancy = None
    
    if selected_vacancy_id:
        try:
            selected_vacancy = Vacancy.objects.get(id=selected_vacancy_id, is_active=True)
        except Vacancy.DoesNotExist:
            messages.warning(request, 'Выбранная вакансия не найдена')
    
    # Если вакансия не выбрана, берем первую активную
    if not selected_vacancy and active_vacancies.exists():
        selected_vacancy = active_vacancies.first()
    
    # Получаем данные о событиях календаря для JavaScript (как на странице календаря)
    calendar_events_data = []
    try:
        oauth_service = GoogleOAuthService(request.user)
        oauth_account = oauth_service.get_oauth_account()
        
        if oauth_account:
            # Получаем события через GoogleCalendarService (как на странице календаря)
            calendar_service = GoogleCalendarService(oauth_service)
            events_data = calendar_service.get_events(days_ahead=14)
            
            print(f"🔍 DEBUG G-DATA: Получено {len(events_data)} событий из API")
            
            if events_data:
                # Преобразуем данные API в формат для JavaScript (как на странице календаря)
                for event_data in events_data:
                    try:
                        # Парсим время начала
                        start_time = None
                        if 'dateTime' in event_data['start']:
                            start_time = datetime.fromisoformat(event_data['start']['dateTime'].replace('Z', '+00:00'))
                            # Конвертируем в локальный часовой пояс Minsk
                            import pytz
                            minsk_tz = pytz.timezone('Europe/Minsk')
                            start_time = start_time.astimezone(minsk_tz)
                        elif 'date' in event_data['start']:
                            start_time = datetime.fromisoformat(event_data['start']['date'] + 'T00:00:00+00:00')
                        
                        # Парсим время окончания
                        end_time = None
                        if 'dateTime' in event_data['end']:
                            end_time = datetime.fromisoformat(event_data['end']['dateTime'].replace('Z', '+00:00'))
                            end_time = end_time.astimezone(minsk_tz)
                        elif 'date' in event_data['end']:
                            end_time = datetime.fromisoformat(event_data['end']['date'] + 'T23:59:59+00:00')
                        
                        if start_time:
                            # Очищаем description от HTML-тегов для безопасного использования в JavaScript
                            description = event_data.get('description', '')
                            if description:
                                # Удаляем HTML-теги
                                description = re.sub(r'<[^>]+>', '', description)
                                # Заменяем кавычки на безопасные символы
                                description = description.replace('"', "'").replace("'", "'")
                            
                            is_all_day_event = 'date' in event_data['start']
                            calendar_events_data.append({
                                'id': event_data['id'],
                                'title': event_data.get('summary', 'Без названия'),
                                'start': start_time.isoformat(),
                                'end': end_time.isoformat() if end_time else start_time.isoformat(),
                                'is_all_day': is_all_day_event,
                                'isallday': is_all_day_event,  # Для совместимости с существующим кодом
                                'location': event_data.get('location', ''),
                                'description': description,
                            })
                    except Exception as e:
                        print(f"Ошибка обработки события {event_data.get('id', 'unknown')}: {e}")
                        continue
    except Exception as e:
        print(f"Ошибка получения данных о событиях: {e}")
    
    # Получаем настройки слотов для пользователя
    slots_settings = SlotsSettings.get_or_create_for_user(request.user)
    print(f"🔍 DEBUG G-DATA: Настройки слотов для пользователя {request.user.username}: {slots_settings.to_dict()}")
    
    context = {
        'active_vacancies': active_vacancies,
        'selected_vacancy': selected_vacancy,
        'calendar_events_data': calendar_events_data,
        'slots_settings': slots_settings,
        'title': 'G-данные и автоматизация'
    }
    
    # Отладочная информация
    print(f"🔍 DEBUG G-DATA: Передаем {len(calendar_events_data)} событий в шаблон")
    for event in calendar_events_data[:3]:  # Показываем первые 3 события
        print(f"🔍 DEBUG G-DATA: Событие: {event['title']} в {event['start']}")
    
    return render(request, 'google_oauth/gdata_automation.html', context)


@login_required
@permission_required('google_oauth.view_googlecalendar', raise_exception=True)
@require_http_methods(["GET"])
def api_calendar_events(request):
    """API для получения событий календаря в JSON формате"""
    try:
        from apps.google_oauth.services import GoogleOAuthService, GoogleCalendarService
        from apps.google_oauth.cache_service import GoogleAPICache
        from apps.interviewers.models import Interviewer
        import json
        from datetime import datetime, timedelta
        import pytz
        import re
        
        # Получаем OAuth аккаунт
        oauth_service = GoogleOAuthService(request.user)
        oauth_account = oauth_service.get_oauth_account()
        
        if not oauth_account:
            return JsonResponse({
                'success': False, 
                'message': 'Google OAuth аккаунт не подключен'
            })
        
        # Получаем параметры запроса
        vacancy_id = request.GET.get('vacancy_id')
        meeting_type = request.GET.get('meeting_type', 'screening')  # screening или interview
        include_interviewers = (meeting_type == 'interview')
        
        # Получаем календарь компании из настроек
        company_calendar_id = None
        try:
            from apps.company_settings.models import CompanySettings
            company_settings = CompanySettings.get_settings()
            if company_settings.main_calendar_id:
                # main_calendar_id может быть ссылкой или ID, извлекаем ID
                calendar_input = company_settings.main_calendar_id.strip()
                print(f"📅 API КАЛЕНДАРЬ КОМПАНИИ: Исходное значение из настроек: '{calendar_input}'")
                
                # Проверяем, является ли это ссылкой
                is_link = 'http' in calendar_input.lower() or 'calendar.google.com' in calendar_input.lower()
                if is_link:
                    print(f"📅 API КАЛЕНДАРЬ КОМПАНИИ: Обнаружена ссылка, извлекаем calendar_id...")
                
                # Извлекаем calendar_id из ссылки или используем как есть, если это уже ID
                company_calendar_id = _extract_calendar_id_from_link(calendar_input)
                
                if company_calendar_id:
                    print(f"✅ API КАЛЕНДАРЬ КОМПАНИИ: Извлечен calendar_id из {'ссылки' if is_link else 'значения'}: '{company_calendar_id}'")
                else:
                    # Если не удалось извлечь из ссылки, возможно это уже ID
                    company_calendar_id = calendar_input
                    print(f"⚠️ API КАЛЕНДАРЬ КОМПАНИИ: Не удалось извлечь calendar_id, используем значение как есть: '{company_calendar_id}'")
                
                print(f"✅ API КАЛЕНДАРЬ КОМПАНИИ: Финальный calendar_id для использования: '{company_calendar_id}'")
            else:
                print(f"⚠️ API КАЛЕНДАРЬ КОМПАНИИ: Календарь не настроен")
        except Exception as e:
            print(f"⚠️ API КАЛЕНДАРЬ КОМПАНИИ: Ошибка получения настроек: {e}")
        
        # Получаем события основного календаря пользователя (force_refresh для актуальных слотов на странице чата)
        calendar_service = GoogleCalendarService(oauth_service)
        events_data = calendar_service.get_events(calendar_id='primary', days_ahead=14, force_refresh=True)
        
        # Добавляем события календаря компании, если он настроен
        if company_calendar_id:
            try:
                company_events_data = calendar_service.get_events(calendar_id=company_calendar_id, days_ahead=14, force_refresh=True)
                print(f"📅 API КАЛЕНДАРЬ КОМПАНИИ: Получено {len(company_events_data)} событий из календаря компании")
                if company_events_data:
                    events_data.extend(company_events_data)
                    print(f"📅 API КАЛЕНДАРЬ КОМПАНИИ: Всего событий после объединения: {len(events_data)}")
            except Exception as e:
                print(f"⚠️ API КАЛЕНДАРЬ КОМПАНИИ: Ошибка получения событий календаря компании: {e}")
        
        # Если это интервью, получаем события календарей обязательных интервьюеров
        if include_interviewers and vacancy_id:
            try:
                from apps.vacancies.models import Vacancy
                print(f"🔍 API: Параметры запроса - vacancy_id={vacancy_id}, meeting_type={meeting_type}, include_interviewers={include_interviewers}")
                vacancy = Vacancy.objects.get(id=vacancy_id, is_active=True)
                if vacancy.recruiter_id != request.user.id and not vacancy.additional_recruiters.filter(pk=request.user.pk).exists():
                    raise Vacancy.DoesNotExist()
                mandatory_interviewers = vacancy.mandatory_tech_interviewers.filter(is_active=True)
                print(f"🔍 API: Найдено {len(mandatory_interviewers)} обязательных интервьюеров")
                
                for interviewer in mandatory_interviewers:
                    print(f"🔍 API: Обработка интервьюера {interviewer.email}, calendar_link={interviewer.calendar_link}")
                    
                    # Пытаемся получить calendar_id разными способами
                    calendar_id = None
                    
                    # Способ 1: Если есть calendar_link, извлекаем из него
                    if interviewer.calendar_link:
                        calendar_id = _extract_calendar_id_from_link(interviewer.calendar_link)
                        print(f"🔍 API: Извлечен calendar_id из ссылки: {calendar_id}")
                    
                    # Способ 2: Если calendar_id не найден, используем email напрямую
                    if not calendar_id:
                        # Проверяем, есть ли календарь с таким email в списке доступных
                        calendar = calendar_service.get_calendar_by_email(interviewer.email)
                        if calendar:
                            calendar_id = calendar['id']
                            print(f"🔍 API: Найден календарь по email: {calendar_id}")
                    
                    # Способ 3: Если все еще нет calendar_id, используем email напрямую
                    if not calendar_id:
                        calendar_id = interviewer.email
                        print(f"🔍 API: Используем email как calendar_id: {calendar_id}")
                    
                    if calendar_id:
                        try:
                            print(f"🔍 API: Получение событий для интервьюера {interviewer.email}, calendar_id={calendar_id}")
                            interviewer_events = calendar_service.get_events(calendar_id=calendar_id, days_ahead=14, force_refresh=True)
                            print(f"🔍 API: Получено {len(interviewer_events)} событий от {interviewer.email}")
                            events_data.extend(interviewer_events)
                            print(f"🔍 API: Добавлено {len(interviewer_events)} событий от {interviewer.email}, всего событий: {len(events_data)}")
                        except Exception as e:
                            print(f"⚠️ API: Ошибка получения событий для {interviewer.email}: {e}")
                    else:
                        print(f"⚠️ API: Не удалось определить calendar_id для интервьюера {interviewer.email}")
            except Vacancy.DoesNotExist:
                print(f"⚠️ API: Вакансия {vacancy_id} не найдена")
            except Exception as e:
                print(f"❌ API: Ошибка при обработке интервьюеров: {e}")
                import traceback
                traceback.print_exc()
        
        print(f"🔍 API CALENDAR EVENTS: Получено {len(events_data)} событий из API")
        
        # Преобразуем данные API в формат для JavaScript
        calendar_events_data = []
        for idx, event_data in enumerate(events_data):
            # Определяем источник события
            event_source = "primary"
            if company_calendar_id and 'company_events_data' in locals() and company_events_data:
                primary_events_count = len(events_data) - len(company_events_data)
                if idx >= primary_events_count:
                    event_source = f"company ({company_calendar_id})"
            
            # Получаем информацию о владельце/организаторе события
            organizer_email = None
            organizer_name = None
            creator_email = None
            if 'organizer' in event_data:
                organizer_email = event_data['organizer'].get('email', '')
                organizer_name = event_data['organizer'].get('displayName', '')
            if 'creator' in event_data:
                creator_email = event_data['creator'].get('email', '')
            
            # Логируем информацию о событии
            event_title = event_data.get('summary', 'Без названия')
            print(f"📅 API СОБЫТИЕ [{idx+1}]: '{event_title}'")
            print(f"   📍 Источник: {event_source}")
            if organizer_email:
                print(f"   👤 Организатор: {organizer_email}" + (f" ({organizer_name})" if organizer_name else ""))
            if creator_email and creator_email != organizer_email:
                print(f"   ✏️ Создатель: {creator_email}")
            try:
                # Парсим время начала
                start_time = None
                if 'dateTime' in event_data['start']:
                    start_time = datetime.fromisoformat(event_data['start']['dateTime'].replace('Z', '+00:00'))
                    # Конвертируем в локальный часовой пояс Minsk
                    minsk_tz = pytz.timezone('Europe/Minsk')
                    start_time = start_time.astimezone(minsk_tz)
                elif 'date' in event_data['start']:
                    start_time = datetime.fromisoformat(event_data['start']['date'] + 'T00:00:00+00:00')
                
                # Парсим время окончания
                end_time = None
                if 'dateTime' in event_data['end']:
                    end_time = datetime.fromisoformat(event_data['end']['dateTime'].replace('Z', '+00:00'))
                    end_time = end_time.astimezone(minsk_tz)
                elif 'date' in event_data['end']:
                    end_time = datetime.fromisoformat(event_data['end']['date'] + 'T23:59:59+00:00')
                
                if start_time:
                    # Очищаем description от HTML-тегов для безопасного использования в JavaScript
                    description = event_data.get('description', '')
                    if description:
                        # Удаляем HTML-теги
                        description = re.sub(r'<[^>]+>', '', description)
                        # Заменяем кавычки на безопасные символы
                        description = description.replace('"', "'").replace("'", "'")
                    
                    is_all_day = 'date' in event_data['start']
                    calendar_events_data.append({
                        'id': event_data['id'],
                        'title': event_data.get('summary', 'Без названия'),
                        'start': start_time.isoformat(),
                        'end': end_time.isoformat() if end_time else start_time.isoformat(),
                        'is_all_day': is_all_day,
                        'isallday': is_all_day,  # Для совместимости с существующим кодом
                        'location': event_data.get('location', ''),
                        'description': description,
                    })
            except Exception as e:
                print(f"Ошибка обработки события {event_data.get('id', 'unknown')}: {e}")
                continue
        
        print(f"🔍 API CALENDAR EVENTS: Передаем {len(calendar_events_data)} событий в ответе")
        
        return JsonResponse({
            'success': True,
            'events': calendar_events_data,
            'count': len(calendar_events_data)
        })
        
    except Exception as e:
        print(f"❌ API CALENDAR EVENTS: Ошибка получения событий: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'message': f'Ошибка получения событий: {str(e)}'
        })


@login_required
@require_http_methods(["GET", "POST"])
def api_interview_slots(request):
    """API для пересчета слотов интервью с учетом выбранных участников"""
    try:
        from apps.google_oauth.services import GoogleOAuthService, GoogleCalendarService
        from apps.google_oauth.cache_service import GoogleAPICache
        from apps.interviewers.models import Interviewer
        from apps.vacancies.models import Vacancy
        from logic.slots_calculator import SlotsCalculator
        import json
        from datetime import datetime, timedelta, time as dt_time
        import pytz
        
        # Получаем параметры запроса
        vacancy_id = request.GET.get('vacancy_id') or (json.loads(request.body).get('vacancy_id') if request.method == 'POST' else None)
        interviewer_ids_str = request.GET.get('interviewer_ids') or (json.loads(request.body).get('interviewer_ids') if request.method == 'POST' else None)
        include_user = request.GET.get('include_user', '1')  # По умолчанию включаем пользователя
        include_user = include_user == '1' or include_user == 'true' or include_user == True
        
        print(f"🔍 API INTERVIEW SLOTS: vacancy_id={vacancy_id}, interviewer_ids={interviewer_ids_str}, include_user={include_user}")
        
        if not vacancy_id:
            return JsonResponse({
                'success': False,
                'message': 'Не указан ID вакансии'
            })
        
        # Получаем вакансию (доступ: основной или дополнительный рекрутер)
        try:
            vacancy = Vacancy.objects.get(id=vacancy_id, is_active=True)
            if vacancy.recruiter_id != request.user.id and not vacancy.additional_recruiters.filter(pk=request.user.pk).exists():
                raise Vacancy.DoesNotExist()
        except Vacancy.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Вакансия не найдена'
            })
        
        # Получаем выбранных интервьюеров
        selected_interviewers = []
        if interviewer_ids_str:
            try:
                interviewer_ids = [int(id.strip()) for id in interviewer_ids_str.split(',') if id.strip()]
                selected_interviewers = Interviewer.objects.filter(id__in=interviewer_ids, is_active=True)
                print(f"🔍 API INTERVIEW SLOTS: Найдено {len(selected_interviewers)} выбранных интервьюеров")
            except ValueError:
                return JsonResponse({
                    'success': False,
                    'message': 'Неверный формат ID интервьюеров'
                })
        
        # ВАЖНО: если интервьюеры не выбраны — НЕ используем обязательных.
        # Слоты считаются только по календарю пользователя и компании.
        if not selected_interviewers:
            print("🔍 API INTERVIEW SLOTS: Интервьюеры не выбраны — считаем слоты без календарей интервьюеров")
        
        # Получаем OAuth аккаунт
        oauth_service = GoogleOAuthService(request.user)
        oauth_account = oauth_service.get_oauth_account()
        
        if not oauth_account:
            return JsonResponse({
                'success': False,
                'message': 'Google OAuth аккаунт не подключен'
            })
        
        # Получаем календарь компании
        company_calendar_id = None
        try:
            from apps.company_settings.models import CompanySettings
            company_settings = CompanySettings.get_settings()
            if company_settings.main_calendar_id:
                calendar_input = company_settings.main_calendar_id.strip()
                company_calendar_id = _extract_calendar_id_from_link(calendar_input)
        except Exception as e:
            print(f"⚠️ API INTERVIEW SLOTS: Ошибка получения календаря компании: {e}")
            company_settings = None
        
        # apps.google_oauth.services.GoogleCalendarService ожидает oauth_service (не oauth_account)
        calendar_service = GoogleCalendarService(oauth_service)
        events_data = []
        
        # Добавляем события календаря пользователя только если он выбран как участник (force_refresh для актуальных слотов)
        if include_user:
            user_events = calendar_service.get_events(calendar_id='primary', days_ahead=14, force_refresh=True)
            events_data.extend(user_events)
            print(f"🔍 API INTERVIEW SLOTS: Добавлены события календаря пользователя: {len(user_events)} событий")
        else:
            print(f"🔍 API INTERVIEW SLOTS: События календаря пользователя не учитываются (пользователь не выбран)")
        
        # Всегда добавляем события календаря компании
        if company_calendar_id:
            try:
                company_events_data = calendar_service.get_events(calendar_id=company_calendar_id, days_ahead=14, force_refresh=True)
                events_data.extend(company_events_data)
                print(f"🔍 API INTERVIEW SLOTS: Добавлены события календаря компании: {len(company_events_data)} событий")
            except Exception as e:
                print(f"⚠️ API INTERVIEW SLOTS: Ошибка получения событий календаря компании: {e}")
        
        # Преобразуем события в формат для калькулятора
        # ВАЖНО: Фильтруем отклоненные события перед расчетом слотов
        interview_events_for_calc = []
        current_user_email_lower = request.user.email.lower() if request.user.email else None
        
        for event in events_data:
            try:
                # Пропускаем отмененные события
                event_status = event.get('status', 'confirmed')
                if event_status == 'cancelled' or event_status == 'declined':
                    print(f"  ❌ API INTERVIEW SLOTS: Исключаем отклоненное событие: \"{event.get('summary', 'Без названия')}\" (статус: {event_status})")
                    continue
                
                # Проверяем ответ участника: при "игнорировать не принятые = НЕТ" слот свободен, пока не принято (accepted)
                if current_user_email_lower and 'attendees' in event:
                    current_user_attendee = None
                    for attendee in event.get('attendees', []):
                        attendee_email = (attendee.get('email') or '').lower()
                        if attendee_email == current_user_email_lower:
                            current_user_attendee = attendee
                            break
                    
                    if current_user_attendee:
                        user_response_status = current_user_attendee.get('responseStatus', 'needsAction')
                        if user_response_status == 'declined':
                            print(f"  ❌ API INTERVIEW SLOTS: Исключаем событие, которое отклонил пользователь: \"{event.get('summary', 'Без названия')}\"")
                            continue
                        if not getattr(company_settings, 'ignore_non_accepted_meetings', True) and user_response_status != 'accepted':
                            continue
                
                start_time = None
                if 'dateTime' in event.get('start', {}):
                    start_time = datetime.fromisoformat(event['start']['dateTime'].replace('Z', '+00:00'))
                    minsk_tz = pytz.timezone('Europe/Minsk')
                    start_time = start_time.astimezone(minsk_tz)
                elif 'date' in event.get('start', {}):
                    start_time = datetime.fromisoformat(event['start']['date'])
                    minsk_tz = pytz.timezone('Europe/Minsk')
                    start_time = minsk_tz.localize(start_time)
                
                end_time = None
                if 'dateTime' in event.get('end', {}):
                    end_time = datetime.fromisoformat(event['end']['dateTime'].replace('Z', '+00:00'))
                    minsk_tz = pytz.timezone('Europe/Minsk')
                    end_time = end_time.astimezone(minsk_tz)
                elif 'date' in event.get('end', {}):
                    end_time = datetime.fromisoformat(event['end']['date'])
                    minsk_tz = pytz.timezone('Europe/Minsk')
                    end_time = minsk_tz.localize(end_time)
                
                if start_time:
                    is_all_day = 'date' in event.get('start', {})
                    interview_events_for_calc.append({
                        'start': start_time.isoformat(),
                        'end': end_time.isoformat() if end_time else start_time.isoformat(),
                        'is_all_day': is_all_day,
                    })
            except Exception as e:
                print(f"⚠️ API INTERVIEW SLOTS: Ошибка обработки события: {e}")
        
        # Добавляем события выбранных интервьюеров
        for interviewer in selected_interviewers:
            calendar_id = None
            
            # Способ 1: Извлекаем из calendar_link
            if interviewer.calendar_link:
                calendar_id = _extract_calendar_id_from_link(interviewer.calendar_link)
            
            # Способ 2: Проверяем календарь по email
            if not calendar_id:
                calendar = calendar_service.get_calendar_by_email(interviewer.email)
                if calendar:
                    calendar_id = calendar['id']
            
            # Способ 3: Используем email
            if not calendar_id:
                calendar_id = interviewer.email
            
            if calendar_id:
                try:
                    interviewer_events = calendar_service.get_events(calendar_id=calendar_id, days_ahead=14, force_refresh=True)
                    print(f"📅 API INTERVIEW SLOTS: Получено {len(interviewer_events)} событий от {interviewer.email}")
                    
                    for event_data in interviewer_events:
                        try:
                            # Пропускаем отмененные события интервьюера
                            event_status = event_data.get('status', 'confirmed')
                            if event_status == 'cancelled' or event_status == 'declined':
                                print(f"  ❌ API INTERVIEW SLOTS: Исключаем отклоненное событие интервьюера {interviewer.email}: \"{event_data.get('summary', 'Без названия')}\" (статус: {event_status})")
                                continue
                            
                            # Проверяем ответ интервьюера: при "игнорировать не принятые = НЕТ" слот свободен, пока не принято
                            interviewer_email_lower = interviewer.email.lower()
                            if 'attendees' in event_data:
                                interviewer_attendee = None
                                for attendee in event_data.get('attendees', []):
                                    attendee_email = (attendee.get('email') or '').lower()
                                    if attendee_email == interviewer_email_lower:
                                        interviewer_attendee = attendee
                                        break
                                
                                if interviewer_attendee:
                                    interviewer_response_status = interviewer_attendee.get('responseStatus', 'needsAction')
                                    if interviewer_response_status == 'declined':
                                        print(f"  ❌ API INTERVIEW SLOTS: Исключаем событие, которое отклонил интервьюер {interviewer.email}: \"{event_data.get('summary', 'Без названия')}\"")
                                        continue
                                    if not getattr(company_settings, 'ignore_non_accepted_meetings', True) and interviewer_response_status != 'accepted':
                                        continue
                            
                            start_time = None
                            if 'dateTime' in event_data.get('start', {}):
                                start_time = datetime.fromisoformat(event_data['start']['dateTime'].replace('Z', '+00:00'))
                                minsk_tz = pytz.timezone('Europe/Minsk')
                                start_time = start_time.astimezone(minsk_tz)
                            
                            end_time = None
                            if 'dateTime' in event_data.get('end', {}):
                                end_time = datetime.fromisoformat(event_data['end']['dateTime'].replace('Z', '+00:00'))
                                minsk_tz = pytz.timezone('Europe/Minsk')
                                end_time = end_time.astimezone(minsk_tz)
                            
                            if start_time:
                                is_all_day = 'date' in event_data.get('start', {})
                                interview_events_for_calc.append({
                                    'start': start_time.isoformat(),
                                    'end': end_time.isoformat() if end_time else start_time.isoformat(),
                                    'is_all_day': is_all_day,
                                })
                        except Exception as e:
                            print(f"⚠️ API INTERVIEW SLOTS: Ошибка обработки события интервьюера {interviewer.email}: {e}")
                except Exception as e:
                    print(f"⚠️ API INTERVIEW SLOTS: Ошибка получения событий для {interviewer.email}: {e}")
        
        # Получаем эффективные рабочие часы: если пользователь не участник или без часов в профиле — данные компании
        from logic.working_hours_service import get_effective_working_hours
        hours = get_effective_working_hours(
            request.user, company_settings, user_is_participant=include_user
        )
        work_start = hours['work_start_hour']
        work_end = hours['work_end_hour']
        meeting_interval = hours['meeting_interval_minutes']
        
        # Рассчитываем слоты
        interview_duration = vacancy.tech_interview_duration if hasattr(vacancy, 'tech_interview_duration') and vacancy.tech_interview_duration else 90
        
        calculator = SlotsCalculator(
            work_start_hour=work_start,
            work_end_hour=work_end,
            meeting_interval_minutes=meeting_interval
        )
        interview_slots = calculator.calculate_slots_for_two_weeks(
            interview_events_for_calc,
            required_duration_minutes=interview_duration
        )
        
        print(f"📅 API INTERVIEW SLOTS: Рассчитано {len(interview_slots)} дней со слотами")
        
        return JsonResponse({
            'success': True,
            'slots': interview_slots,
            'interviewer_count': len(selected_interviewers)
        })
        
    except Exception as e:
        print(f"❌ API INTERVIEW SLOTS: Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'message': f'Ошибка расчета слотов: {str(e)}'
        })


@login_required
def api_interviewers_autocomplete(request):
    """API для автодополнения интервьюеров по вакансии"""
    try:
        vacancy_id = request.GET.get('vacancy_id')
        query = request.GET.get('q', '').strip()
        
        print(f"🔍 API INTERVIEWERS AUTOCOMPLETE: vacancy_id={vacancy_id}, query='{query}'")
        
        if not vacancy_id:
            return JsonResponse({
                'success': False,
                'message': 'Не указан ID вакансии'
            })
        
        # Получаем вакансию (доступ: основной или дополнительный рекрутер)
        from apps.vacancies.models import Vacancy
        try:
            vacancy = Vacancy.objects.get(id=vacancy_id)
            if vacancy.recruiter_id != request.user.id and not vacancy.additional_recruiters.filter(pk=request.user.pk).exists():
                raise Vacancy.DoesNotExist()
        except Vacancy.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Вакансия не найдена'
            })
        
        # Получаем интервьюеров, привязанных к вакансии
        interviewers = vacancy.interviewers.filter(is_active=True)
        
        # Фильтруем по запросу, если он есть
        if query:
            interviewers = interviewers.filter(
                models.Q(first_name__icontains=query) |
                models.Q(last_name__icontains=query) |
                models.Q(email__icontains=query)
            )
        
        # Формируем результат
        results = []
        for interviewer in interviewers[:10]:  # Ограничиваем до 10 результатов
            results.append({
                'id': interviewer.id,
                'username': interviewer.email.split('@')[0],  # Используем часть email до @ как username
                'full_name': interviewer.get_full_name(),
                'email': interviewer.email
            })
        
        print(f"🔍 API INTERVIEWERS AUTOCOMPLETE: Найдено {len(results)} интервьюеров")
        
        return JsonResponse({
            'success': True,
            'results': results
        })
        
    except Exception as e:
        print(f"❌ API INTERVIEWERS AUTOCOMPLETE: Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'message': f'Ошибка получения интервьюеров: {str(e)}'
        })


@login_required
def api_weekly_reports(request):
    """API для получения отчетов текущей и предыдущей недели"""
    from apps.reporting.models import CalendarEvent
    from apps.vacancies.models import Vacancy
    from apps.interviewers.models import Interviewer
    from datetime import timedelta
    
    try:
        vacancy_id = request.GET.get('vacancy_id')
        week_type = request.GET.get('week_type', 'current')  # 'current' или 'previous'
        
        if not vacancy_id:
            return JsonResponse({
                'success': False,
                'message': 'Не указан ID вакансии'
            })
        
        # Получаем вакансию (доступ: основной или дополнительный рекрутер)
        try:
            vacancy = Vacancy.objects.get(id=vacancy_id, is_active=True)
            if vacancy.recruiter_id != request.user.id and not vacancy.additional_recruiters.filter(pk=request.user.pk).exists():
                raise Vacancy.DoesNotExist()
        except Vacancy.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Вакансия не найдена'
            })
        
        # Определяем границы недели (ПН-СБ)
        now = timezone.now()
        days_since_monday = now.weekday()  # 0 = ПН, 6 = ВС
        
        if week_type == 'current':
            # Текущая неделя: от прошлого понедельника до субботы
            week_start = now - timedelta(days=days_since_monday)
            week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
            week_end = week_start + timedelta(days=5)  # До субботы включительно
            week_end = week_end.replace(hour=23, minute=59, second=59, microsecond=999999)
        else:
            # Предыдущая неделя: от понедельника недели назад до субботы
            week_start = now - timedelta(days=days_since_monday + 7)
            week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
            week_end = week_start + timedelta(days=5)  # До субботы включительно
            week_end = week_end.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        # Получаем invite_title вакансии
        invite_title = vacancy.invite_title or ''
        if not invite_title:
            return JsonResponse({
                'success': True,
                'data': {
                    'hr_screening': 0,
                    'tech_screening': 0,
                    'interview': 0,
                    'offer': 0,
                    'offer_accepted': 0,
                    'onboarding': 0,
                }
            })
        
        # Получаем интервьюеров вакансии
        vacancy_interviewers = vacancy.interviewers.filter(is_active=True)
        vacancy_interviewer_emails = set()
        for interviewer in vacancy_interviewers:
            if interviewer.email:
                vacancy_interviewer_emails.add(interviewer.email.lower())
        
        # Получаем события за неделю
        events = CalendarEvent.objects.filter(
            start_time__gte=week_start,
            start_time__lte=week_end,
            event_type__in=['screening', 'interview', 'unknown']
        ).select_related('vacancy', 'recruiter')
        
        # Фильтруем события по invite_title вакансии
        matching_events = []
        invite_title_lower = invite_title.lower().strip()
        
        print(f"📊 WEEKLY REPORTS: Вакансия ID={vacancy_id}, invite_title='{invite_title}'")
        print(f"📊 WEEKLY REPORTS: Неделя {week_type}, период: {week_start.date()} - {week_end.date()}")
        print(f"📊 WEEKLY REPORTS: Всего событий за период: {events.count()}")
        print(f"📊 WEEKLY REPORTS: Интервьюеров вакансии: {len(vacancy_interviewer_emails)}")
        if vacancy_interviewer_emails:
            print(f"📊 WEEKLY REPORTS: Email интервьюеров: {', '.join(list(vacancy_interviewer_emails)[:5])}")
        
        for event in events:
            event_title_lower = (event.title or '').lower().strip()
            # Проверяем, содержит ли название события заголовок инвайта
            if invite_title_lower and invite_title_lower in event_title_lower:
                matching_events.append(event)
                print(f"  ✅ Найдено совпадение: '{event.title}' (ID={event.id}, дата={event.start_time.date()})")
        
        print(f"📊 WEEKLY REPORTS: Событий с совпадением invite_title: {len(matching_events)}")
        
        # Подсчитываем скрининги
        hr_screening_count = 0
        tech_screening_count = 0
        
        # Получаем заголовок инвайта для Tech Screening (invite_title из вакансии)
        # Формат названия события: "[Заголовок инвайтов] | [Фамилия Имя]"
        tech_screening_invite_title = invite_title.strip() if invite_title else ''
        tech_screening_invite_title_lower = tech_screening_invite_title.lower().strip().rstrip('|').strip()
        
        if not tech_screening_invite_title_lower:
            # Если заголовок инвайта не указан, возвращаем нули
            print(f"📊 WEEKLY REPORTS: Заголовок инвайта не указан для вакансии, скрининги не найдены")
            return JsonResponse({
                'success': True,
                'data': {
                    'hr_screening': 0,
                    'tech_screening': 0,
                    'interview': 0,
                    'offer': 0,
                    'offer_accepted': 0,
                    'onboarding': 0,
                }
            })
        
        for event in matching_events:
            event_title = event.title or ''
            event_title_lower = event_title.lower()
            
            # Событие считается скринингом ТОЛЬКО если название начинается с invite_title (точное совпадение)
            # Формат: "[Заголовок инвайтов] | [Фамилия Имя]" или "[Заголовок инвайтов]|[Фамилия Имя]"
            is_screening = False
            if event_title_lower.startswith(tech_screening_invite_title_lower):
                # Проверяем, что после заголовка идет разделитель | или пробел
                remaining = event_title_lower[len(tech_screening_invite_title_lower):].strip()
                if remaining.startswith('|') or remaining.startswith(' '):
                    is_screening = True
            
            if not is_screening:
                continue  # Пропускаем события, которые не являются скринингами (нет точного совпадения с invite_title)
            
            # Если это скрининг (есть точное совпадение с invite_title), проверяем участников
            attendees = event.attendees or []
            has_interviewer = False
            found_interviewer_email = None
            
            for attendee in attendees:
                if isinstance(attendee, dict):
                    attendee_email = attendee.get('email', '').lower()
                elif isinstance(attendee, str):
                    attendee_email = attendee.lower()
                else:
                    continue
                
                if attendee_email in vacancy_interviewer_emails:
                    has_interviewer = True
                    found_interviewer_email = attendee_email
                    break
            
            # Определяем тип скрининга на основе участников
            if has_interviewer:
                tech_screening_count += 1
                print(f"  🔵 Tech Screening: '{event.title}' (точное совпадение с invite_title='{invite_title}', интервьюер: {found_interviewer_email})")
            else:
                hr_screening_count += 1
                print(f"  🟢 HR-screening: '{event.title}' (точное совпадение с invite_title='{invite_title}', но нет интервьюеров)")
        
        print(f"📊 WEEKLY REPORTS: Итого - HR-screening: {hr_screening_count}, Tech Screening: {tech_screening_count}")
        
        # Подсчитываем интервью
        interview_count = 0
        
        # Получаем заголовок инвайта для интервью (tech_invite_title из вакансии)
        tech_invite_title = vacancy.tech_invite_title or ''
        tech_invite_title_lower = tech_invite_title.lower().strip().rstrip('|').strip() if tech_invite_title else ''
        
        if tech_invite_title_lower:
            print(f"📊 WEEKLY REPORTS: Заголовок инвайта для интервью: '{tech_invite_title}'")
            
            # Проверяем все события за период на совпадение с tech_invite_title
            for event in events:
                event_title = event.title or ''
                event_title_lower = event_title.lower()
                
                # Событие считается интервью ТОЛЬКО если название начинается с tech_invite_title (точное совпадение)
                # Формат: "[Заголовок инвайтов] | [Фамилия Имя]" или "[Заголовок инвайтов]|[Фамилия Имя]"
                is_interview = False
                if event_title_lower.startswith(tech_invite_title_lower):
                    # Проверяем, что после заголовка идет разделитель | или пробел
                    remaining = event_title_lower[len(tech_invite_title_lower):].strip()
                    if remaining.startswith('|') or remaining.startswith(' '):
                        is_interview = True
                
                if is_interview:
                    interview_count += 1
                    print(f"  🟣 Интервью: '{event.title}' (точное совпадение с tech_invite_title='{tech_invite_title}')")
        else:
            print(f"📊 WEEKLY REPORTS: Заголовок инвайта для интервью не указан, интервью не найдены")
        
        print(f"📊 WEEKLY REPORTS: Итого интервью: {interview_count}")
        
        # Пока остальные этапы возвращаем как 0 (будут реализованы позже)
        return JsonResponse({
            'success': True,
            'data': {
                'hr_screening': hr_screening_count,
                'tech_screening': tech_screening_count,
                'interview': interview_count,
                'offer': 0,
                'offer_accepted': 0,
                'onboarding': 0,
            }
        })
        
    except Exception as e:
        import traceback
        return JsonResponse({
            'success': False,
            'message': str(e),
            'traceback': traceback.format_exc()
        })


@login_required
def api_third_week_slots(request):
    """API для расчета слотов третьей недели"""
    try:
        vacancy_id = request.GET.get('vacancy_id')
        meeting_type = request.GET.get('meeting_type', 'screening')
        interviewer_ids_str = request.GET.get('interviewer_ids', '')
        
        print(f"📅 API THIRD WEEK: vacancy_id={vacancy_id}, meeting_type={meeting_type}, interviewer_ids={interviewer_ids_str}")
        
        if not vacancy_id:
            return JsonResponse({
                'success': False,
                'message': 'Не указан ID вакансии'
            })
        
        # Получаем вакансию (доступ: основной или дополнительный рекрутер)
        from apps.vacancies.models import Vacancy
        try:
            vacancy = Vacancy.objects.get(id=vacancy_id, is_active=True)
            if vacancy.recruiter_id != request.user.id and not vacancy.additional_recruiters.filter(pk=request.user.pk).exists():
                raise Vacancy.DoesNotExist()
        except Vacancy.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Вакансия не найдена'
            })
        
        # Получаем эффективные рабочие часы (компания -> пользователь -> по умолчанию)
        from logic.working_hours_service import get_effective_working_hours
        try:
            from apps.company_settings.models import CompanySettings
            _company_settings = CompanySettings.get_settings()
        except Exception:
            _company_settings = None
        hours = get_effective_working_hours(request.user, _company_settings)
        work_start = hours['work_start_hour']
        work_end = hours['work_end_hour']
        meeting_interval = hours['meeting_interval_minutes']
        
        print(f"🕐 THIRD WEEK: Рабочие часы {work_start}:00-{work_end}:00, интервал {meeting_interval} мин")
        
        from logic.slots_calculator import SlotsCalculator
        calculator = SlotsCalculator(
            work_start_hour=work_start,
            work_end_hour=work_end,
            meeting_interval_minutes=meeting_interval
        )
        
        # Получаем события календаря
        from apps.google_oauth.services import GoogleOAuthService, GoogleCalendarService
        oauth_service = GoogleOAuthService(request.user)
        calendar_service = GoogleCalendarService(oauth_service)
        
        events_data = []

        # Добавляем календарь компании (если настроен) — влияет и на screening, и на interview
        company_calendar_id = None
        company_settings = None
        try:
            from apps.company_settings.models import CompanySettings
            company_settings = CompanySettings.get_settings()
            if company_settings.main_calendar_id:
                company_calendar_id = _extract_calendar_id_from_link(company_settings.main_calendar_id.strip())
        except Exception as e:
            print(f"⚠️ THIRD WEEK: Ошибка получения календаря компании: {e}")
        
        ignore_non_accepted_meetings = getattr(company_settings, 'ignore_non_accepted_meetings', True)
        
        if meeting_type == 'screening':
            # Для скринингов только календарь пользователя
            print(f"📅 THIRD WEEK: Получение слотов для скринингов")
            events_data = calendar_service.get_events(days_ahead=21, force_refresh=True)  # Получаем на 3 недели
            if company_calendar_id:
                try:
                    company_events_data = calendar_service.get_events(calendar_id=company_calendar_id, days_ahead=21, force_refresh=True)
                    events_data.extend(company_events_data)
                except Exception as e:
                    print(f"⚠️ THIRD WEEK: Ошибка получения событий календаря компании: {e}")
            duration = vacancy.screening_duration if hasattr(vacancy, 'screening_duration') and vacancy.screening_duration else 45
        else:
            # Для интервью: по умолчанию только календарь пользователя (и компании, если добавлена отдельно).
            # ВАЖНО: если интервьюеры не выбраны — никого не подтягиваем автоматически.
            print(f"📅 THIRD WEEK: Получение слотов для интервью")
            events_data = calendar_service.get_events(days_ahead=21, force_refresh=True)
            if company_calendar_id:
                try:
                    company_events_data = calendar_service.get_events(calendar_id=company_calendar_id, days_ahead=21, force_refresh=True)
                    events_data.extend(company_events_data)
                except Exception as e:
                    print(f"⚠️ THIRD WEEK: Ошибка получения событий календаря компании: {e}")

            # Если интервьюеры выбраны — добавляем их календари; если нет — считаем без них
            selected_interviewers = []
            if interviewer_ids_str:
                try:
                    from apps.interviewers.models import Interviewer
                    interviewer_ids = [int(i.strip()) for i in interviewer_ids_str.split(',') if i.strip()]
                    selected_interviewers = list(Interviewer.objects.filter(id__in=interviewer_ids, is_active=True))
                    print(f"📅 THIRD WEEK: Выбрано интервьюеров: {len(selected_interviewers)}")
                except Exception as e:
                    print(f"⚠️ THIRD WEEK: Ошибка парсинга interviewer_ids: {e}")

            for interviewer in selected_interviewers:
                calendar_id = None
                if interviewer.calendar_link:
                    calendar_id = _extract_calendar_id_from_link(interviewer.calendar_link)
                if not calendar_id:
                    try:
                        calendar = calendar_service.get_calendar_by_email(interviewer.email)
                        if calendar:
                            calendar_id = calendar.get('id')
                    except Exception:
                        calendar_id = None
                if not calendar_id:
                    calendar_id = interviewer.email

                if calendar_id:
                    try:
                        interviewer_events = calendar_service.get_events(calendar_id=calendar_id, days_ahead=21, force_refresh=True)
                        events_data.extend(interviewer_events)
                        print(f"📅 THIRD WEEK: Добавлено {len(interviewer_events)} событий от {interviewer.email}")
                    except Exception as e:
                        print(f"⚠️ THIRD WEEK: Ошибка получения событий для {interviewer.email}: {e}")
            
            duration = vacancy.tech_interview_duration if hasattr(vacancy, 'tech_interview_duration') and vacancy.tech_interview_duration else 90
        
        # Логируем события для отладки
        print(f"📅 THIRD WEEK: Всего получено {len(events_data)} событий")
        if events_data:
            for i, event in enumerate(events_data[:5]):  # Показываем первые 5 событий
                start_str = event.get('start', {}).get('dateTime', event.get('start', 'N/A'))
                title = event.get('summary', 'N/A')
                print(f"📅 THIRD WEEK: Событие {i+1}: {title} - {start_str}")
        
        # Преобразуем события в формат для калькулятора и фильтруем отклоненные
        events_for_calc = []
        current_user_email_lower = request.user.email.lower() if request.user.email else None
        
        # Получаем список выбранных интервьюеров для проверки их отклоненных событий (если еще не получен)
        if meeting_type == 'interview' and 'selected_interviewers' not in locals():
            selected_interviewers = []
            if interviewer_ids_str:
                try:
                    from apps.interviewers.models import Interviewer
                    interviewer_ids = [int(i.strip()) for i in interviewer_ids_str.split(',') if i.strip()]
                    selected_interviewers = list(Interviewer.objects.filter(id__in=interviewer_ids, is_active=True))
                except Exception as e:
                    print(f"⚠️ THIRD WEEK: Ошибка парсинга interviewer_ids: {e}")
                    selected_interviewers = []
        elif meeting_type != 'interview':
            selected_interviewers = []
        
        for event in events_data:
            try:
                # Пропускаем отмененные события
                event_status = event.get('status', 'confirmed')
                if event_status == 'cancelled' or event_status == 'declined':
                    print(f"  ❌ THIRD WEEK: Исключаем отклоненное событие: \"{event.get('summary', 'Без названия')}\" (статус: {event_status})")
                    continue
                
                # Проверяем ответ участника: при "игнорировать не принятые = НЕТ" слот свободен, пока не принято (accepted)
                if current_user_email_lower and 'attendees' in event:
                    current_user_attendee = None
                    for attendee in event.get('attendees', []):
                        attendee_email = (attendee.get('email') or '').lower()
                        if attendee_email == current_user_email_lower:
                            current_user_attendee = attendee
                            break
                    
                    if current_user_attendee:
                        user_response_status = current_user_attendee.get('responseStatus', 'needsAction')
                        if user_response_status == 'declined':
                            print(f"  ❌ THIRD WEEK: Исключаем событие, которое отклонил пользователь: \"{event.get('summary', 'Без названия')}\"")
                            continue
                        if not ignore_non_accepted_meetings and user_response_status != 'accepted':
                            continue
                
                # Для интервью также проверяем ответ интервьюера
                if meeting_type == 'interview' and selected_interviewers:
                    event_skipped = False
                    for interviewer in selected_interviewers:
                        interviewer_email_lower = interviewer.email.lower()
                        if 'attendees' in event:
                            interviewer_attendee = None
                            for attendee in event.get('attendees', []):
                                attendee_email = (attendee.get('email') or '').lower()
                                if attendee_email == interviewer_email_lower:
                                    interviewer_attendee = attendee
                                    break
                            
                            if interviewer_attendee:
                                interviewer_response_status = interviewer_attendee.get('responseStatus', 'needsAction')
                                if interviewer_response_status == 'declined':
                                    print(f"  ❌ THIRD WEEK: Исключаем событие, которое отклонил интервьюер {interviewer.email}: \"{event.get('summary', 'Без названия')}\"")
                                    event_skipped = True
                                    break
                                if not ignore_non_accepted_meetings and interviewer_response_status != 'accepted':
                                    event_skipped = True
                                    break
                    
                    if event_skipped:
                        continue  # Пропускаем событие, если его отклонил интервьюер или не принято (при настройке «не игнорировать»)
                
                # Преобразуем событие в формат для калькулятора
                import pytz
                start_time = None
                if 'dateTime' in event.get('start', {}):
                    start_time = datetime.fromisoformat(event['start']['dateTime'].replace('Z', '+00:00'))
                    minsk_tz = pytz.timezone('Europe/Minsk')
                    start_time = start_time.astimezone(minsk_tz)
                elif 'date' in event.get('start', {}):
                    start_time = datetime.fromisoformat(event['start']['date'])
                    minsk_tz = pytz.timezone('Europe/Minsk')
                    start_time = minsk_tz.localize(start_time)
                
                end_time = None
                if 'dateTime' in event.get('end', {}):
                    end_time = datetime.fromisoformat(event['end']['dateTime'].replace('Z', '+00:00'))
                    minsk_tz = pytz.timezone('Europe/Minsk')
                    end_time = end_time.astimezone(minsk_tz)
                elif 'date' in event.get('end', {}):
                    end_time = datetime.fromisoformat(event['end']['date'])
                    minsk_tz = pytz.timezone('Europe/Minsk')
                    end_time = minsk_tz.localize(end_time)
                
                if start_time:
                    is_all_day = 'date' in event.get('start', {})
                    events_for_calc.append({
                        'start': start_time.isoformat(),
                        'end': end_time.isoformat() if end_time else start_time.isoformat(),
                        'is_all_day': is_all_day,
                    })
            except Exception as e:
                print(f"⚠️ THIRD WEEK: Ошибка обработки события: {e}")
                continue
        
        print(f"📅 THIRD WEEK: После фильтрации осталось {len(events_for_calc)} событий для расчета")
        
        # Рассчитываем слоты для третьей недели
        third_week_slots = calculator.calculate_slots_for_week(
            events_for_calc,
            required_duration_minutes=duration,
            week_offset=2  # Третья неделя
        )
        
        print(f"📅 THIRD WEEK: Рассчитано {len(third_week_slots)} дней")
        
        return JsonResponse({
            'success': True,
            'slots': third_week_slots
        })
        
    except Exception as e:
        print(f"❌ THIRD WEEK: Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'message': f'Ошибка расчета слотов: {str(e)}'
        })


@login_required
@permission_required('google_oauth.view_hrscreening', raise_exception=True)
def combined_workflow(request):
    from django.http import Http404
    raise Http404("Combined workflow отключен администратором")


def _normalize_chat_command_ru_to_en(text):
    """
    Заменяет команды чата, набранные в русской раскладке, на английские эквиваленты.
    Так /ы (та же клавиша что s) и /s обрабатываются одинаково.
    Соответствия по клавишам ЙЦУКЕН: ы=s, е=t, шт=in, рк=hr, вуд=del, фвв=add, шм=inv.
    """
    if not text or not isinstance(text, str):
        return text or ''
    s = text.strip()
    if not s.startswith('/'):
        return text
    # Порядок: длинные команды первыми
    replacements = [
        (r'^/вуд(\s|$)', r'/del\1'),
        (r'^/фвв(\s|$)', r'/add\1'),
        (r'^/шт(\s|$)', r'/in\1'),
        (r'^/шм(\s|$)', r'/inv\1'),
        (r'^/рк(\s|$)', r'/hr\1'),
        (r'^/[ыЫ](\s|$)', r'/s\1'),
        (r'^/[еЕ](\s|$)', r'/t\1'),
    ]
    for pat, repl in replacements:
        s = re.sub(pat, repl, s, count=1)
    return s


@login_required
@permission_required('google_oauth.view_hrscreening', raise_exception=True)
def chat_ajax_handler(request, session_id):
    """Обработка AJAX запросов для чата"""
    print(f"🔍 CHAT AJAX HANDLER: Получен запрос на session_id={session_id}")
    print(f"🔍 CHAT AJAX HANDLER: Метод={request.method}, Content-Type={request.content_type}")
    
    # Поддерживаем как JSON, так и multipart/form-data (для файлов)
    is_json = request.content_type == 'application/json'
    is_multipart = 'multipart/form-data' in (request.content_type or '')
    
    if request.method != 'POST' or (not is_json and not is_multipart):
        print(f"❌ CHAT AJAX HANDLER: Неверный тип запроса - метод={request.method}, content_type={request.content_type}")
        return JsonResponse({'success': False, 'error': 'Неверный тип запроса'})
    
    try:
        import json
        # Обрабатываем JSON или FormData
        if is_json:
            data = json.loads(request.body)
            message_text = data.get('text', '').strip()
            action_type_from_js = data.get('action_type', '')
            action = data.get('action', '')
        else:
            # FormData
            data = request.POST
            message_text = data.get('text', '').strip()
            action_type_from_js = data.get('action_type', '')
            action = data.get('action', '')
        
        # Нормализация команд с русской раскладки: /ы → /s, /е → /t, /шт → /in и т.д.
        message_text = _normalize_chat_command_ru_to_en(message_text)
        
        # Обработка специальных действий (не требующих сообщения)
        if action == 'save_rejection_form_answer':
            message_id = data.get('message_id')
            answer = data.get('answer')  # 'yes' или 'no'
            reason = (data.get('reason') or '').strip()  # 'office_format' | 'salary' — по какой причине нажали «Нет»
            
            if not message_id:
                return JsonResponse({'success': False, 'error': 'Не указан ID сообщения'})
            
            try:
                from .models import ChatMessage
                
                chat_message = ChatMessage.objects.get(id=int(message_id), session__user=request.user)
                current_metadata = chat_message.metadata or {}
                new_metadata = dict(current_metadata)
                
                # Сохраняем ответ по причине (для нескольких форм отказа)
                rejection_form_answers = dict(new_metadata.get('rejection_form_answers') or {})
                if reason:
                    rejection_form_answers[reason] = answer
                    new_metadata['rejection_form_answers'] = rejection_form_answers
                
                # Если причину не передали (одиночная форма) — старый формат
                if not reason:
                    new_metadata['rejection_form_answered'] = True
                    new_metadata['rejection_form_answer'] = answer
                else:
                    # Проверяем, все ли показанные причины получили ответ
                    office_shown = bool(current_metadata.get('office_format_rejected'))
                    salary_shown = bool(current_metadata.get('salary_above_range'))
                    office_done = not office_shown or (rejection_form_answers.get('office_format') is not None)
                    salary_done = not salary_shown or (rejection_form_answers.get('salary') is not None)
                    if office_done and salary_done:
                        new_metadata['rejection_form_answered'] = True
                
                ChatMessage.objects.filter(id=chat_message.id, session__user=request.user).update(metadata=new_metadata)
                chat_message.refresh_from_db(fields=['metadata'])
                saved_answered = chat_message.metadata.get('rejection_form_answered', False)
                print(f"✅ CHAT AJAX: Сохранен ответ на форму отказа для сообщения {message_id}: reason={reason}, answer={answer}. rejection_form_answered={saved_answered}")
                
                return JsonResponse({
                    'success': True,
                    'message': 'Ответ сохранен',
                    'all_answered': new_metadata.get('rejection_form_answered', False)
                })
            except ChatMessage.DoesNotExist:
                return JsonResponse({'success': False, 'error': 'Сообщение не найдено'})
            except Exception as e:
                print(f"❌ CHAT AJAX: Ошибка при сохранении ответа на форму отказа: {e}")
                return JsonResponse({'success': False, 'error': str(e)})
        
        print(f"🔍 CHAT AJAX HANDLER: Получен message_text (длина: {len(message_text)}): {message_text}")
        print(f"🔍 CHAT AJAX HANDLER: Проверяем наличие @ в message_text: {'@' in message_text}")
        
        if not message_text:
            return JsonResponse({'success': False, 'error': 'Пустое сообщение'})
        
        # Получаем сессию чата
        try:
            chat_session = ChatSession.objects.get(id=session_id, user=request.user)
        except ChatSession.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Сессия чата не найдена'})
        
        # Получаем вакансию из сессии чата
        vacancy = chat_session.vacancy
        if not vacancy:
            return JsonResponse({'success': False, 'error': 'Вакансия не найдена для данного чата'})
        
        # Сохраняем пользовательское сообщение
        user_message = ChatMessage.objects.create(
            session=chat_session,
            message_type='user',
            content=message_text
        )

        # Определяем тип действия (с приоритетом команд)
        print(f"🔍 CHAT AJAX: Анализируем сообщение: '{message_text}'")
        print(f"🔍 CHAT AJAX: action_type_from_js: '{action_type_from_js}' (type: {type(action_type_from_js)}, bool: {bool(action_type_from_js)})")
        
        # Проверяем команды строго с границами слов или пробелами
        message_lower = message_text.strip().lower()
        
        if re.match(r'^/del(\s|$)', message_lower):
            action_type = 'delete_last'
            print(f"🔍 CHAT AJAX: Команда /del обнаружена - удаление последнего действия")
            message_text = re.sub(r'^/del\s*', '', message_text, flags=re.IGNORECASE).strip()
        elif re.match(r'^/s(\s|$)', message_lower):
            action_type = 'hrscreening'
            print(f"🔍 CHAT AJAX: Команда /s обнаружена в тексте - принудительный HR-скрининг")
            message_text = re.sub(r'^/s\s*', '', message_text, flags=re.IGNORECASE).strip()
        elif re.match(r'^/t(\s|$)', message_lower):
            action_type = 'tech_screening'
            print(f"🔍 CHAT AJAX: Команда /t обнаружена в тексте - Tech Screening")
            message_text = re.sub(r'^/t\s*', '', message_text, flags=re.IGNORECASE).strip()
        elif re.match(r'^/in(\s|$)', message_lower):
            action_type = 'final_interview'
            print(f"🔍 CHAT AJAX: Команда /in обнаружена в тексте - Final Interview")
            message_text = re.sub(r'^/in\s*', '', message_text, flags=re.IGNORECASE).strip()
        else:
            # Комбинированный/автоматический режим отключен, но допускаем явный тип из JS
            # ВАЖНО: проверяем что action_type_from_js не пустая строка и не None
            if action_type_from_js and action_type_from_js.strip():
                action_type = action_type_from_js.strip()
                print(f"🔍 CHAT AJAX: Используем тип действия из JS (скрытое поле): '{action_type}'")
            else:
                print(f"❌ CHAT AJAX: НЕТ КОМАНДЫ! message_text: '{message_text}', action_type_from_js: '{action_type_from_js}'")
                return JsonResponse({'success': False, 'error': 'Укажи команду: /s для HR-скрининга, /t для Tech Screening или /in для Final Interview'})
        
        print(f"🔍 CHAT AJAX: ФИНАЛЬНЫЙ action_type: '{action_type}'")

        # Обрабатываем действие
        if action_type == 'delete_last':
            # Проверяем, не была ли уже выполнена команда удаления
            last_message = ChatMessage.objects.filter(
                session=chat_session
            ).order_by('-created_at').first()
            
            if last_message and last_message.message_type == 'delete':
                ChatMessage.objects.create(
                    session=chat_session,
                    message_type='system',
                    content="⚠️ **Команда удаления уже была выполнена**\n\nКоманда `/del` может быть использована только один раз подряд. Сначала создайте новое действие (HR-скрининг или инвайт), а затем используйте команду удаления."
                )
            else:
                # Обрабатываем команду удаления последнего действия
                delete_result = delete_last_action(chat_session, request.user)
                
                if delete_result['success']:
                    # Создаем стилизованный ответ в виде карточки
                    action_type_display = {
                        'hrscreening': 'HR-скрининг',
                        'tech_screening': 'Tech Screening',
                        'final_interview': 'Final Interview'
                    }.get(delete_result['action_type'], delete_result['action_type'])
                    
                    # Формируем список изменений
                    changes_html = ""
                    if delete_result.get('changes'):
                        changes_list = []
                        for change in delete_result['changes']:
                            changes_list.append(f"<li>{change}</li>")
                        changes_html = f"""
<div class="delete-changes">
<h6><i class="fas fa-list me-2"></i>Выполненные изменения:</h6>
<ul>{''.join(changes_list)}</ul>
</div>"""
                    
                    # Формируем ссылку на Huntflow
                    huntflow_link = ""
                    if delete_result.get('huntflow_candidate_url'):
                        huntflow_link = f"""
<div class="delete-item">
<span class="delete-label">Huntflow:</span> 
<a href="{delete_result['huntflow_candidate_url']}" target="_blank" class="btn btn-sm btn-outline-primary">
<i class="fas fa-external-link-alt me-1"></i>Открыть кандидата
</a>
</div>"""
                    
                    response_content = f"""<div class="delete-result-card">
<div class="delete-header">
<i class="fas fa-trash-alt text-danger me-2"></i>
<strong>Удалено</strong>
</div>
<div class="delete-info">
<div class="delete-item">
<span class="delete-label">Тип:</span> {action_type_display}
</div>
<div class="delete-item">
<span class="delete-label">Кандидат:</span> {delete_result.get('candidate_name', 'Не указан')}
</div>
<div class="delete-item">
<span class="delete-label">Вакансия:</span> {delete_result.get('vacancy_name', 'Не указана')}
</div>
{huntflow_link}
</div>
<div class="delete-status">
<i class="fas fa-check-circle text-success me-2"></i>
<span class="delete-status-text">Данные удалены и изменения отменены</span>
</div>
{changes_html if changes_html else ''}
</div>"""
                
                    ChatMessage.objects.create(
                        session=chat_session,
                        message_type='delete',
                        content=response_content,
                        metadata={
                            'action_type': 'delete_last',
                            'deleted_action_type': delete_result['action_type'],
                            'deleted_object_id': delete_result.get('deleted_object_id'),
                            'deleted_candidate_name': delete_result.get('candidate_name'),
                            'deleted_vacancy_name': delete_result.get('vacancy_name'),
                            'huntflow_candidate_url': delete_result.get('huntflow_candidate_url'),
                            'changes': delete_result.get('changes', [])
                        }
                    )
                else:
                    ChatMessage.objects.create(
                        session=chat_session,
                        message_type='system',
                        content=f"❌ **Ошибка при удалении**\n\n{delete_result.get('message', 'Неизвестная ошибка')}"
                    )
                
        elif action_type == 'hrscreening':
            # Создаем HR-скрининг
            hr_form = HRScreeningForm({'input_data': message_text}, user=request.user)
            
            if hr_form.is_valid():
                try:
                    hr_screening = hr_form.save()
                    
                    # Генерируем полную ссылку с вакансией
                    full_candidate_url = None
                    if hr_screening.vacancy_id and hr_screening.candidate_id:
                        full_candidate_url = _generate_full_huntflow_link(
                            hr_screening.vacancy_id,
                            hr_screening.candidate_id,
                            request.user
                        )
                    
                    # Используем полную ссылку, если она сгенерирована, иначе исходную
                    # ВАЖНО: Перезагружаем объект из БД, чтобы получить актуальные данные,
                    # включая зарплату, которая могла быть извлечена в analyze_with_gemini
                    from apps.google_oauth.models import HRScreening
                    hr_screening = HRScreening.objects.get(id=hr_screening.id)
                    
                    print(f"🔍 CHAT AJAX: HR-скрининг перезагружен, зарплата: {hr_screening.extracted_salary}, валюта: {hr_screening.salary_currency}")
                    print(f"🔍 CHAT AJAX: gemini_analysis присутствует: {bool(hr_screening.gemini_analysis)}")
                    if hr_screening.gemini_analysis:
                        print(f"🔍 CHAT AJAX: gemini_analysis длина: {len(hr_screening.gemini_analysis)} символов")
                        print(f"🔍 CHAT AJAX: gemini_analysis начало: {hr_screening.gemini_analysis[:200]}")
                    
                    candidate_url_for_metadata = full_candidate_url or hr_screening.candidate_url
                    
                    # Проверяем, был ли отклонен кандидат по офисному формату
                    print(f"🔍 CHAT AJAX: Проверяем офисный формат...")
                    office_format_rejected = hr_screening.is_office_format_rejected()
                    print(f"🔍 CHAT AJAX: Результат проверки офисного формата: {office_format_rejected}")
                    
                    rejection_template = None
                    if office_format_rejected:
                        print(f"🔍 CHAT AJAX: Кандидат отклонен по офисному формату, получаем шаблон отказа...")
                        rejection_template = hr_screening.get_office_format_rejection_template()
                        if rejection_template:
                            print(f"✅ CHAT AJAX: Найден шаблон отказа: {rejection_template.title} (ID: {rejection_template.id})")
                            print(f"✅ CHAT AJAX: Текст шаблона (первые 100 символов): {rejection_template.message[:100]}")
                        else:
                            print(f"⚠️ CHAT AJAX: Шаблон отказа не найден")
                    else:
                        print(f"ℹ️ CHAT AJAX: Кандидат не отклонен по офисному формату")
                    
                    # Проверяем, превышает ли зарплата максимальную вилку
                    print(f"🔍 CHAT AJAX: Проверяем превышение зарплаты над вилкой...")
                    salary_above_range = hr_screening.is_salary_above_range()
                    print(f"🔍 CHAT AJAX: Результат проверки превышения зарплаты: {salary_above_range}")
                    
                    finance_more_template = None
                    if salary_above_range:
                        print(f"🔍 CHAT AJAX: Зарплата превышает вилку, получаем шаблон отказа 'Финансы - больше'...")
                        finance_more_template = hr_screening.get_finance_more_rejection_template()
                        if finance_more_template:
                            print(f"✅ CHAT AJAX: Найден шаблон отказа 'Финансы - больше': {finance_more_template.title} (ID: {finance_more_template.id})")
                            print(f"✅ CHAT AJAX: Текст шаблона (первые 100 символов): {finance_more_template.message[:100]}")
                        else:
                            print(f"⚠️ CHAT AJAX: Шаблон отказа 'Финансы - больше' не найден")
                    else:
                        print(f"ℹ️ CHAT AJAX: Зарплата не превышает вилку")
                    
                    response_content = ""  # Пустой контент, данные будут браться из metadata
                    
                    # Получаем контактную информацию кандидата
                    candidate_contact_info = {}
                    if hr_screening.candidate_id:
                        candidate_contact_info = _get_candidate_contact_info(request.user, hr_screening.candidate_id)
                        print(f"🔍 CHAT AJAX: Получена контактная информация кандидата: {candidate_contact_info}")
                    
                    metadata = {
                        'action_type': 'hrscreening',
                        'hr_screening_id': hr_screening.id,
                        'candidate_name': hr_screening.candidate_name,
                        'vacancy_name': hr_screening.vacancy_title,
                        'determined_grade': hr_screening.determined_grade,
                        'candidate_url': candidate_url_for_metadata,
                        'extracted_salary': str(hr_screening.extracted_salary) if hr_screening.extracted_salary else None,
                        'salary_currency': hr_screening.salary_currency,
                        'candidate_contact_info': candidate_contact_info
                    }
                    
                    # Определяем, нужно ли показывать форму отказа (только при потенциальном отказе)
                    show_rejection_form = False
                    
                    # Добавляем информацию о шаблоне отказа, если кандидат отклонен по офисному формату
                    if office_format_rejected:
                        # Сохраняем флаг отказа в метаданные, даже если шаблон не найден
                        metadata['office_format_rejected'] = True
                        show_rejection_form = True
                        
                        if rejection_template:
                            metadata['rejection_template_id'] = rejection_template.id
                            metadata['rejection_template_title'] = rejection_template.title
                            metadata['rejection_template_message'] = rejection_template.message
                            print(f"✅ CHAT AJAX: Метаданные обновлены с информацией об отказе. office_format_rejected=True, template_id={rejection_template.id}")
                            print(f"✅ CHAT AJAX: Текст шаблона (первые 200 символов): {rejection_template.message[:200]}")
                        else:
                            print(f"⚠️ CHAT AJAX: Кандидат отклонен по офисному формату, но шаблон отказа не найден. office_format_rejected=True установлен в метаданные")
                    else:
                        print(f"ℹ️ CHAT AJAX: Кандидат не отклонен по офисному формату. office_format_rejected={office_format_rejected} (type: {type(office_format_rejected)})")
                    
                    # Добавляем информацию о шаблоне отказа "Финансы - больше", если зарплата превышает вилку
                    if salary_above_range:
                        # Сохраняем флаг отказа в метаданные, даже если шаблон не найден
                        metadata['salary_above_range'] = True
                        show_rejection_form = True
                        
                        if finance_more_template:
                            metadata['finance_more_template_id'] = finance_more_template.id
                            metadata['finance_more_template_title'] = finance_more_template.title
                            metadata['finance_more_template_message'] = finance_more_template.message
                            print(f"✅ CHAT AJAX: Метаданные обновлены с информацией об отказе 'Финансы - больше'. salary_above_range=True, template_id={finance_more_template.id}")
                            print(f"✅ CHAT AJAX: Текст шаблона (первые 200 символов): {finance_more_template.message[:200]}")
                        else:
                            print(f"⚠️ CHAT AJAX: Зарплата превышает вилку, но шаблон отказа 'Финансы - больше' не найден. salary_above_range=True установлен в метаданные")
                    else:
                        print(f"ℹ️ CHAT AJAX: Зарплата не превышает вилку. salary_above_range={salary_above_range}")
                    
                    # Добавляем флаг для отображения формы отказа
                    metadata['show_rejection_form'] = show_rejection_form
                    print(f"🔍 CHAT AJAX: show_rejection_form={show_rejection_form} (salary_above_range={salary_above_range}, office_format_rejected={office_format_rejected})")
                    
                    print(f"🔍 CHAT AJAX: Сохраняем сообщение с метаданными. Ключи: {list(metadata.keys())}")
                    print(f"🔍 CHAT AJAX: office_format_rejected в метаданных: {metadata.get('office_format_rejected', 'NOT SET')}")
                    print(f"🔍 CHAT AJAX: rejection_template_message в метаданных: {'SET' if metadata.get('rejection_template_message') else 'NOT SET'}")
                    
                    ChatMessage.objects.create(
                        session=chat_session,
                        message_type='hrscreening',
                        content=response_content,
                        hr_screening=hr_screening,
                        metadata=metadata
                    )
                    
                    print(f"✅ CHAT AJAX: Сообщение создано успешно с контактной информацией в metadata")
                except Exception as e:
                    print(f"🔍 CHAT AJAX: Ошибка сохранения HR: {str(e)}")
                    ChatMessage.objects.create(
                        session=chat_session,
                        message_type='system',
                        content=f"Ошибка при обработке HR-скрининга: {str(e)}"
                    )
            else:
                # Ошибки валидации
                error_content = "Ошибка при обработке HR-скрининга:\n"
                for field, errors in hr_form.errors.items():
                    error_content += f"- {field}: {', '.join(errors)}\n"
                
                ChatMessage.objects.create(
                    session=chat_session,
                    message_type='system',
                    content=error_content
                )

        elif action_type == 'tech_screening':
            # Создаем Tech Screening (логика как для invite)
            invite_form_data = {'combined_data': message_text}
            
            # Передаем данные об интервьюере, если они есть
            if 'selected_interviewer' in request.POST:
                invite_form_data['selected_interviewer'] = request.POST['selected_interviewer']
                print(f"🔍 CHAT AJAX: Передаем данные об интервьюере: {request.POST['selected_interviewer']}")
            elif is_json and 'selected_interviewer' in data:
                invite_form_data['selected_interviewer'] = data['selected_interviewer']
                print(f"🔍 CHAT AJAX: Передаем данные об интервьюере (JSON): {data['selected_interviewer']}")
            
            invite_form = InviteCombinedForm(invite_form_data, user=request.user)
            
            if invite_form.is_valid():
                # Проверка грейда: если в Huntflow не указан, спрашиваем пользователя
                confirm_create = data.get('confirm_create_without_grade') if is_json else request.POST.get('confirm_create_without_grade')
                if not confirm_create:
                    candidate_url = invite_form.cleaned_data.get('candidate_url')
                    if candidate_url:
                        needs_confirmation, grade = _check_tech_screening_grade_needs_confirmation(request.user, candidate_url)
                        if needs_confirmation:
                            print(f"🔍 CHAT AJAX: Грейд не указан в Huntflow, требуем подтверждения")
                            return JsonResponse({
                                'success': False,
                                'requires_grade_confirmation': True,
                                'message': 'В Huntflow не указан грейд кандидата. Создать встречу без грейда?',
                                'original_text': message_text
                            })
                try:
                    invite = invite_form.save()
                    
                    # Генерируем полную ссылку с вакансией
                    full_candidate_url = None
                    if invite.vacancy_id and invite.candidate_id:
                        full_candidate_url = _generate_full_huntflow_link(
                            invite.vacancy_id,
                            invite.candidate_id,
                            request.user
                        )
                    
                    # Используем полную ссылку, если она сгенерирована, иначе исходную
                    candidate_url_for_metadata = full_candidate_url or invite.candidate_url
                    
                    # Получаем контактную информацию кандидата ДО создания сообщения
                    candidate_contact_info = {}
                    if invite.candidate_id:
                        candidate_contact_info = _get_candidate_contact_info(request.user, invite.candidate_id)
                        print(f"🔍 CHAT AJAX: Получена контактная информация кандидата: {candidate_contact_info}")
                    
                    response_content = ""  # Пустой контент, данные будут браться из metadata
                    
                    ChatMessage.objects.create(
                        session=chat_session,
                        message_type='invite',  # Используем существующий тип для совместимости
                        content=response_content,
                        invite=invite,
                        metadata={
                            'action_type': 'tech_screening',
                            'invite_id': invite.id,
                            'candidate_name': invite.candidate_name,
                            'vacancy_name': invite.vacancy_title,
                            'interviewer_name': invite.interviewer.get_full_name() if invite.interviewer else None,
                            'interviewer_email': invite.interviewer.email if invite.interviewer else None,
                            'interview_datetime': invite.interview_datetime.isoformat() if invite.interview_datetime else None,
                            'candidate_url': candidate_url_for_metadata,
                            'calendar_event_url': invite.calendar_event_url,
                            'google_drive_file_url': invite.google_drive_file_url,
                            'candidate_contact_info': candidate_contact_info
                        }
                    )
                except Exception as e:
                    print(f"🔍 CHAT AJAX: Ошибка сохранения инвайта: {str(e)}")
                    ChatMessage.objects.create(
                        session=chat_session,
                        message_type='system',
                        content=f"Ошибка при обработке инвайта: {str(e)}"
                    )
            else:
                # Ошибки валидации
                error_content = "Ошибка при обработке инвайта:\n"
                for field, errors in invite_form.errors.items():
                    error_content += f"- {field}: {', '.join(errors)}\n"
                
                ChatMessage.objects.create(
                    session=chat_session,
                    message_type='system',
                    content=error_content
                )
        
        elif action_type == 'final_interview':
            # Создаем Final Interview БЕЗ скоркарда (используется tech_invite_title)
            invite_form_data = {'combined_data': message_text}
            
            # Передаем данные об интервьюере, если они есть
            if 'selected_interviewer' in data:
                invite_form_data['selected_interviewer'] = data['selected_interviewer']
                print(f"🔍 CHAT AJAX: Передаем данные об интервьюере: {data['selected_interviewer']}")
            
            invite_form = InviteCombinedForm(invite_form_data, user=request.user)
            
            if invite_form.is_valid():
                try:
                    # Создаем инвайт без сохранения (commit=False)
                    invite = invite_form.save(commit=False)
                    
                    # Устанавливаем формат интервью (онлайн/офис)
                    interview_format = data.get('interview_format', 'online')
                    invite.interview_format = interview_format
                    print(f"🔍 CHAT AJAX: Установлен формат интервью: {interview_format}")
                    
                    # Используем специальный метод для интервью (без скоркарда)
                    invite.save_for_interview()
                    
                    # Генерируем полную ссылку с вакансией
                    full_candidate_url = None
                    if invite.vacancy_id and invite.candidate_id:
                        full_candidate_url = _generate_full_huntflow_link(
                            invite.vacancy_id,
                            invite.candidate_id,
                            request.user
                        )
                    
                    # Используем полную ссылку, если она сгенерирована, иначе исходную
                    candidate_url_for_metadata = full_candidate_url or invite.candidate_url
                    
                    # Получаем контактную информацию кандидата ДО создания сообщения
                    candidate_contact_info = {}
                    if invite.candidate_id:
                        candidate_contact_info = _get_candidate_contact_info(request.user, invite.candidate_id)
                        print(f"🔍 CHAT AJAX: Получена контактная информация кандидата: {candidate_contact_info}")
                    
                    response_content = ""  # Пустой контент, данные будут браться из metadata
                    
                    ChatMessage.objects.create(
                        session=chat_session,
                        message_type='invite',  # Используем существующий тип для совместимости
                        content=response_content,
                        invite=invite,
                        metadata={
                            'action_type': 'final_interview',
                            'invite_id': invite.id,
                            'candidate_name': invite.candidate_name,
                            'vacancy_name': invite.vacancy_title,
                            'interviewer_name': invite.interviewer.get_full_name() if invite.interviewer else None,
                            'interviewer_email': invite.interviewer.email if invite.interviewer else None,
                            'interview_datetime': invite.interview_datetime.isoformat() if invite.interview_datetime else None,
                            'candidate_url': candidate_url_for_metadata,
                            'calendar_event_url': invite.calendar_event_url,
                            'candidate_contact_info': candidate_contact_info
                            # google_drive_file_url не создается для интервью
                        }
                    )
                except Exception as e:
                    print(f"🔍 CHAT AJAX: Ошибка сохранения Final Interview: {str(e)}")
                    import traceback
                    traceback.print_exc()
                    ChatMessage.objects.create(
                        session=chat_session,
                        message_type='system',
                        content=f"Ошибка при обработке Final Interview: {str(e)}"
                    )
            else:
                # Ошибки валидации
                error_content = "Ошибка при обработке Final Interview:\n"
                for field, errors in invite_form.errors.items():
                    error_content += f"- {field}: {', '.join(errors)}\n"
                
                ChatMessage.objects.create(
                    session=chat_session,
                    message_type='system',
                    content=error_content
                )
        
        elif action_type == 'add_candidate':
            # Создаем кандидата в Huntflow с привязкой к вакансии
            print(f"🔍 CHAT AJAX: Обрабатываем команду /add для создания кандидата")
            
            try:
                from apps.huntflow.views import get_correct_account_id
                from apps.huntflow.services import HuntflowService
                
                # Получаем правильный account_id
                correct_account_id = get_correct_account_id(request.user)
                if not correct_account_id:
                    ChatMessage.objects.create(
                        session=chat_session,
                        message_type='system',
                        content="❌ Не удалось определить организацию Huntflow. Проверьте настройки."
                    )
                else:
                    huntflow_service = HuntflowService(request.user)
                    
                    # Получаем ID вакансии из Huntflow (external_id из нашей БД)
                    vacancy_id = int(vacancy.external_id) if vacancy.external_id else None
                    
                    if not vacancy_id:
                        ChatMessage.objects.create(
                            session=chat_session,
                            message_type='system',
                            content=f"❌ У выбранной вакансии '{vacancy.name}' не указан ID для связи с Huntflow"
                        )
                    else:
                        # Проверяем наличие ссылок на резюме (hh.ru или rabota.by) в сообщении
                        resume_url_info = None
                        if message_text:
                            resume_url_info = huntflow_service._extract_resume_url(message_text)
                        
                        # Проверяем, есть ли файл в запросе
                        resume_file = None
                        parsed_data = None
                        
                        # Если есть файл в FormData (для AJAX с файлами)
                        if hasattr(request, 'FILES') and 'resume_file' in request.FILES:
                            resume_file = request.FILES['resume_file']
                            print(f"🔍 CHAT AJAX: Получен файл резюме: {resume_file.name} ({resume_file.size} байт)")
                            
                            try:
                                # Читаем файл
                                file_data = resume_file.read()
                                file_name = resume_file.name
                                
                                # Загружаем и парсим файл через Huntflow API
                                parsed_data = huntflow_service.upload_file(
                                    account_id=correct_account_id,
                                    file_data=file_data,
                                    file_name=file_name,
                                    parse_file=True
                                )
                                
                                if parsed_data:
                                    print(f"✅ CHAT AJAX: Файл успешно обработан парсером Huntflow")
                                else:
                                    print(f"⚠️ CHAT AJAX: Не удалось обработать файл через парсер Huntflow")
                            except Exception as e:
                                print(f"❌ CHAT AJAX: Ошибка при обработке файла: {e}")
                                import traceback
                                traceback.print_exc()
                        
                        # Если найдена ссылка на резюме и нет файла, создаем кандидата по ссылке
                        if resume_url_info and not parsed_data and not resume_file:
                            print(f"🔍 CHAT AJAX: Найдена ссылка на резюме: {resume_url_info}")
                            created_applicant = huntflow_service.create_applicant_from_url(
                                account_id=correct_account_id,
                                resume_url=resume_url_info['url'],
                                vacancy_id=vacancy_id,
                                source_type=resume_url_info['source_type'],
                                resume_id=resume_url_info.get('resume_id')
                            )
                            
                            if created_applicant:
                                applicant_id = created_applicant.get('id')
                                candidate_name = f"{created_applicant.get('last_name', '')} {created_applicant.get('first_name', '')} {created_applicant.get('middle_name', '')}".strip()
                                if not candidate_name:
                                    candidate_name = "Кандидат"
                                
                                # Формируем ссылку на кандидата
                                candidate_url = f"https://huntflow.ru/my/org{correct_account_id}#/applicants/{applicant_id}"
                                
                                # Формируем источник для отображения
                                source_display = f"{resume_url_info['source_type'].lower()}.ru" if resume_url_info['source_type'] == 'HH' else "rabota.by"
                                resume_id_display = resume_url_info.get('resume_id', 'N/A')
                                
                                response_content = f"✅ **Кандидат успешно создан и привязан к вакансии**\n\n"
                                response_content += f"**Кандидат:** {candidate_name}\n"
                                response_content += f"**Вакансия:** {vacancy.name}\n"
                                response_content += f"**ID кандидата:** {applicant_id}\n\n"
                                response_content += f"**{source_display}:** {resume_id_display}\n\n"
                                response_content += f"[Открыть кандидата в Huntflow]({candidate_url})"
                                
                                ChatMessage.objects.create(
                                    session=chat_session,
                                    message_type='system',
                                    content=response_content,
                                    metadata={
                                        'action_type': 'add_candidate',
                                        'applicant_id': applicant_id,
                                        'candidate_name': candidate_name,
                                        'vacancy_name': vacancy.name,
                                        'candidate_url': candidate_url,
                                        'resume_source': source_display,
                                        'resume_id': resume_id_display
                                    }
                                )
                                
                                print(f"✅ CHAT AJAX: Кандидат успешно создан по ссылке: {applicant_id}")
                            else:
                                ChatMessage.objects.create(
                                    session=chat_session,
                                    message_type='system',
                                    content="❌ Не удалось создать кандидата по ссылке. Проверьте ссылку и попробуйте снова."
                                )
                        else:
                            # Парсим текст сообщения для извлечения данных кандидата
                            # Формат: Имя Фамилия Отчество, email, телефон, должность, компания, зарплата
                            # Или просто текст резюме
                            candidate_data = {
                                'first_name': '',
                                'last_name': '',
                                'middle_name': '',
                                'email': '',
                                'phone': '',
                                'position': '',
                                'company': '',
                                'salary': '',
                                'resume_text': message_text if message_text else ''
                            }
                            
                            # Если есть распарсенные данные из файла, используем их
                            if parsed_data:
                                fields = parsed_data.get('fields', {})
                                name_data = fields.get('name', {})
                                
                                candidate_data['first_name'] = name_data.get('first', '') or candidate_data['first_name']
                                candidate_data['last_name'] = name_data.get('last', '') or candidate_data['last_name']
                                candidate_data['middle_name'] = name_data.get('middle', '') or candidate_data['middle_name']
                                candidate_data['email'] = fields.get('email', '') or candidate_data['email']
                                
                                if fields.get('phones'):
                                    phones = fields.get('phones', [])
                                    if phones and len(phones) > 0:
                                        candidate_data['phone'] = phones[0] or candidate_data['phone']
                                
                                candidate_data['position'] = fields.get('position', '') or candidate_data['position']
                                candidate_data['salary'] = str(fields.get('salary', '')) or candidate_data['salary']
                                
                                if parsed_data.get('text'):
                                    candidate_data['resume_text'] = parsed_data.get('text') or candidate_data['resume_text']
                            
                            # Если имя и фамилия не заполнены, пытаемся извлечь из текста
                            if not candidate_data['first_name'] and not candidate_data['last_name'] and message_text:
                                # Простая попытка извлечь имя из первой строки
                                lines = message_text.split('\n')
                                if lines:
                                    first_line = lines[0].strip()
                                    name_parts = first_line.split()
                                    if len(name_parts) >= 2:
                                        candidate_data['first_name'] = name_parts[0]
                                        candidate_data['last_name'] = name_parts[1]
                                        if len(name_parts) >= 3:
                                            candidate_data['middle_name'] = name_parts[2]
                            
                            # Проверяем обязательные поля
                            if not candidate_data['first_name'] or not candidate_data['last_name']:
                                ChatMessage.objects.create(
                                    session=chat_session,
                                    message_type='system',
                                    content="❌ Не указаны имя и фамилия кандидата. Укажите их в сообщении или прикрепите файл резюме."
                                )
                            else:
                                # Создаем кандидата в Huntflow
                                if parsed_data:
                                    # Используем create_applicant_from_parsed_data для полной поддержки парсера
                                    created_applicant = huntflow_service.create_applicant_from_parsed_data(
                                        account_id=correct_account_id,
                                        parsed_data=parsed_data,
                                        vacancy_id=vacancy_id
                                    )
                                else:
                                    # Создаем кандидата вручную
                                    created_applicant = huntflow_service.create_applicant_manual(
                                        account_id=correct_account_id,
                                        candidate_data=candidate_data,
                                        vacancy_id=vacancy_id
                                    )
                                
                                if created_applicant:
                                    applicant_id = created_applicant.get('id')
                                    candidate_name = f"{candidate_data.get('last_name', '')} {candidate_data.get('first_name', '')} {candidate_data.get('middle_name', '')}".strip()
                                    
                                    # Формируем ссылку на кандидата
                                    candidate_url = f"https://huntflow.ru/my/org{correct_account_id}#/applicants/{applicant_id}"
                                    
                                    response_content = f"✅ **Кандидат успешно создан и привязан к вакансии**\n\n"
                                    response_content += f"**Кандидат:** {candidate_name}\n"
                                    response_content += f"**Вакансия:** {vacancy.name}\n"
                                    response_content += f"**ID кандидата:** {applicant_id}\n\n"
                                    response_content += f"[Открыть кандидата в Huntflow]({candidate_url})"
                                    
                                    ChatMessage.objects.create(
                                        session=chat_session,
                                        message_type='system',
                                        content=response_content,
                                        metadata={
                                            'action_type': 'add_candidate',
                                            'applicant_id': applicant_id,
                                            'candidate_name': candidate_name,
                                            'vacancy_name': vacancy.name,
                                            'candidate_url': candidate_url
                                        }
                                    )
                                    
                                    print(f"✅ CHAT AJAX: Кандидат успешно создан: {applicant_id}")
                                else:
                                    ChatMessage.objects.create(
                                        session=chat_session,
                                        message_type='system',
                                        content="❌ Не удалось создать кандидата в Huntflow. Проверьте данные и попробуйте снова."
                                    )
                                
            except Exception as e:
                print(f"❌ CHAT AJAX: Ошибка создания кандидата: {e}")
                import traceback
                traceback.print_exc()
                ChatMessage.objects.create(
                    session=chat_session,
                    message_type='system',
                    content=f"❌ Ошибка при создании кандидата: {str(e)}"
                )
        
        # Получаем последнее СИСТЕМНОЕ сообщение из чата (то, что только что создали)
        # Исключаем пользовательские сообщения, чтобы получить именно результат обработки
        last_message = ChatMessage.objects.filter(
            session=chat_session,
            message_type__in=['hrscreening', 'invite', 'system', 'delete']
        ).order_by('-created_at').first()
        
        # Если не нашли системное, пытаемся найти любое сообщение кроме пользовательского
        if not last_message:
            last_message = ChatMessage.objects.filter(
                session=chat_session
            ).exclude(message_type='user').order_by('-created_at').first()
        
        # Если всё ещё не нашли, берём просто последнее
        if not last_message:
            last_message = ChatMessage.objects.filter(session=chat_session).order_by('-created_at').first()
        
        print(f"🔍 CHAT AJAX: Последнее системное сообщение: {last_message} (type: {last_message.message_type if last_message else None})")
        
        # Формируем HTML для нового сообщения
        if last_message:
            print(f"🔍 CHAT AJAX: Рендерим HTML для сообщения типа: {last_message.message_type}")
            try:
                message_html = render_to_string('google_oauth/partials/chat_message.html', {
                    'message': last_message,
                    'user': request.user
                })
                print(f"🔍 CHAT AJAX: HTML сгенерирован, длина: {len(message_html)}")
                
                # Получаем контактную информацию кандидата из metadata сообщения (если есть)
                candidate_contact_info = last_message.metadata.get('candidate_contact_info', {}) if last_message.metadata else {}
                if not candidate_contact_info:
                    # Если нет в metadata, пытаемся получить из кандидата
                    if last_message.message_type == 'hrscreening' and last_message.hr_screening:
                        if last_message.hr_screening.candidate_id:
                            candidate_contact_info = _get_candidate_contact_info(request.user, last_message.hr_screening.candidate_id)
                            print(f"🔍 CHAT AJAX: Получена контактная информация для ответа (из API): {candidate_contact_info}")
                            # Обновляем метаданные сообщения, чтобы сохранить контактную информацию
                            if last_message.metadata:
                                last_message.metadata['candidate_contact_info'] = candidate_contact_info
                                
                                # Также обновляем show_rejection_form, если его нет
                                if 'show_rejection_form' not in last_message.metadata:
                                    # Проверяем потенциальный отказ
                                    hr_screening = last_message.hr_screening
                                    show_rejection_form = False
                                    
                                    # Проверяем превышение зарплаты
                                    if hr_screening.extracted_salary and hr_screening.salary_currency:
                                        salary_above_range = hr_screening.is_salary_above_range()
                                        if salary_above_range:
                                            show_rejection_form = True
                                    
                                    # Проверяем офисный формат
                                    if not show_rejection_form:
                                        office_format_rejected = hr_screening.is_office_format_rejected()
                                        if office_format_rejected:
                                            show_rejection_form = True
                                    
                                    last_message.metadata['show_rejection_form'] = show_rejection_form
                                    last_message.metadata['hr_screening_id'] = hr_screening.id  # Убеждаемся, что ID есть
                                    print(f"🔍 CHAT AJAX: Обновлен show_rejection_form={show_rejection_form} для существующего сообщения")
                                
                                last_message.save(update_fields=['metadata'])
                    elif last_message.message_type == 'invite' and last_message.invite:
                        if last_message.invite.candidate_id:
                            candidate_contact_info = _get_candidate_contact_info(request.user, last_message.invite.candidate_id)
                            print(f"🔍 CHAT AJAX: Получена контактная информация для ответа (из API): {candidate_contact_info}")
                            # Обновляем метаданные сообщения, чтобы сохранить контактную информацию
                            if last_message.metadata:
                                last_message.metadata['candidate_contact_info'] = candidate_contact_info
                                last_message.save(update_fields=['metadata'])
                    elif last_message.metadata and last_message.metadata.get('action_type') == 'add_candidate':
                        # Для add_candidate получаем по applicant_id из метаданных
                        applicant_id = last_message.metadata.get('applicant_id')
                        if applicant_id:
                            candidate_contact_info = _get_candidate_contact_info(request.user, applicant_id)
                            print(f"🔍 CHAT AJAX: Получена контактная информация для add_candidate (из API): {candidate_contact_info}")
                            # Обновляем метаданные сообщения, чтобы сохранить контактную информацию
                            if last_message.metadata:
                                last_message.metadata['candidate_contact_info'] = candidate_contact_info
                                last_message.save(update_fields=['metadata'])
                else:
                    print(f"🔍 CHAT AJAX: Используем контактную информацию из metadata: {candidate_contact_info}")
                
                return JsonResponse({
                    "success": True,
                    "message_html": message_html,
                    "message_type": last_message.message_type,
                    "message_id": last_message.id,
                    "candidate_contact_info": candidate_contact_info
                })
            except Exception as e:
                import traceback
                error_trace = traceback.format_exc()
                print(f"❌ CHAT AJAX: Ошибка рендеринга HTML: {str(e)}")
                print(f"❌ CHAT AJAX: Traceback: {error_trace}")
                return JsonResponse({
                    "success": False,
                    "error": f"Ошибка отображения сообщения: {str(e)}",
                    "message_type": last_message.message_type if last_message else None
                })
        else:
            print(f"❌ CHAT AJAX: Сообщение не найдено после обработки")
            return JsonResponse({
                "success": False,
                "error": "Сообщение не было создано"
            })
        
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Неверный JSON'})
    except Exception as e:
        print(f"🔍 CHAT AJAX: Ошибка обработки действия: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)})


def _get_candidate_contact_info(user, candidate_id):
    """
    Получает контактную информацию кандидата из Huntflow
    
    Returns:
        dict: Словарь с ключами: email, telegram, linkedin, communication_where
    """
    contact_info = {
        'email': None,
        'telegram': None,
        'linkedin': None,
        'communication_where': None
    }
    
    try:
        from apps.huntflow.services import HuntflowService
        
        huntflow_service = HuntflowService(user)
        accounts = huntflow_service.get_accounts()
        
        if not accounts or 'items' not in accounts or not accounts['items']:
            return contact_info
        
        account_id = accounts['items'][0]['id']
        candidate_data = huntflow_service.get_applicant(account_id, int(candidate_id))
        
        if not candidate_data:
            return contact_info
        
        # Получаем email
        contact_info['email'] = candidate_data.get('email')
        
        # Получаем социальные сети
        social = candidate_data.get('social', [])
        print(f"🔍 LINKEDIN_SEARCH: Проверяем social: {social}")
        for soc in social:
            # В спецификации API поле называется social_type, но проверяем оба варианта
            soc_type = (soc.get('social_type', '') or soc.get('type', '') or '').upper()
            # В спецификации API поле называется value
            soc_value = soc.get('value', '') or soc.get('url', '') or ''
            
            if not soc_value:
                continue
            
            print(f"🔍 LINKEDIN_SEARCH: Соцсеть type={soc_type}, value={soc_value}, полный объект: {soc}")
            
            # Проверяем Telegram
            if soc_type == 'TELEGRAM' or 'TELEGRAM' in soc_type:
                contact_info['telegram'] = soc_value.lstrip('@')
                print(f"✅ LINKEDIN_SEARCH: Найден Telegram: {contact_info['telegram']}")
            # Проверяем LinkedIn - может быть в разных форматах
            elif soc_type == 'LINKEDIN' or 'LINKEDIN' in soc_type or soc_type == 'LI':
                # Если value содержит linkedin.com, это URL
                if 'linkedin.com' in soc_value.lower():
                    contact_info['linkedin'] = soc_value if 'http' in soc_value.lower() else f"https://{soc_value}"
                else:
                    # Если это username, формируем URL
                    contact_info['linkedin'] = f"https://www.linkedin.com/in/{soc_value.lstrip('/')}"
                print(f"✅ LINKEDIN_SEARCH: Найден LinkedIn в social: {contact_info['linkedin']}")
            # Также проверяем, может быть value содержит linkedin.com даже если тип другой
            elif 'linkedin.com' in soc_value.lower():
                contact_info['linkedin'] = soc_value if 'http' in soc_value.lower() else f"https://{soc_value}"
                print(f"✅ LINKEDIN_SEARCH: Найден LinkedIn в social (по URL в value): {contact_info['linkedin']}")
        
        # Если LinkedIn не найден в social, проверяем источник резюме (external/externals)
        if not contact_info['linkedin']:
            # Проверяем оба варианта: external и externals
            external = candidate_data.get('external', []) or candidate_data.get('externals', [])
            print(f"🔍 LINKEDIN_SEARCH: Проверяем external/externals: {external}")
            
            for ext in external:
                print(f"🔍 LINKEDIN_SEARCH: Обрабатываем external: {ext}")
                auth_type = ext.get('auth_type', '').upper()
                external_id = ext.get('id')
                print(f"🔍 LINKEDIN_SEARCH: auth_type={auth_type}, external_id={external_id}")
                
                if auth_type == 'LI' or 'LINKEDIN' in auth_type:
                    print(f"✅ LINKEDIN_SEARCH: Найден LinkedIn в external с auth_type={auth_type}")
                    
                    # Согласно спецификации API, для получения полной информации о резюме
                    # нужно делать запрос к /accounts/{account_id}/applicants/{applicant_id}/externals/{external_id}
                    # Там будет поле source_url с ссылкой на LinkedIn профиль
                    if external_id:
                        try:
                            print(f"🔍 LINKEDIN_SEARCH: Получаем детали резюме для external_id={external_id}")
                            external_detail = huntflow_service._make_request(
                                'GET', 
                                f"/accounts/{account_id}/applicants/{int(candidate_id)}/externals/{external_id}"
                            )
                            if external_detail:
                                print(f"🔍 LINKEDIN_SEARCH: Получены детали резюме, ключи: {list(external_detail.keys())}")
                                # Проверяем source_url - это основное поле для LinkedIn URL
                                source_url = external_detail.get('source_url')
                                if source_url and 'linkedin.com' in source_url.lower():
                                    contact_info['linkedin'] = source_url
                                    print(f"✅ LINKEDIN_SEARCH: Найден LinkedIn в external_detail.source_url: {contact_info['linkedin']}")
                                    break
                                # Также проверяем data и resume
                                ext_data = external_detail.get('data', {})
                                if isinstance(ext_data, dict):
                                    for key in ['url', 'profile_url', 'linkedin_url', 'link', 'source_url']:
                                        if key in ext_data and ext_data[key]:
                                            value = ext_data[key]
                                            if isinstance(value, str) and 'linkedin.com' in value.lower():
                                                contact_info['linkedin'] = value if 'http' in value.lower() else f"https://{value}"
                                                print(f"✅ LINKEDIN_SEARCH: Найден LinkedIn в external_detail.data.{key}: {contact_info['linkedin']}")
                                                break
                        except Exception as e:
                            print(f"⚠️ LINKEDIN_SEARCH: Ошибка получения деталей резюме: {e}")
                            import traceback
                            traceback.print_exc()
                    
                    # Если не получили через API, проверяем локальные данные
                    if not contact_info['linkedin']:
                        ext_data = ext.get('data', {})
                        print(f"🔍 LINKEDIN_SEARCH: ext_data: {ext_data}")
                        
                        if isinstance(ext_data, dict):
                            for key in ['url', 'profile_url', 'linkedin_url', 'link', 'source_url']:
                                if key in ext_data and ext_data[key]:
                                    value = ext_data[key]
                                    if isinstance(value, str) and 'linkedin.com' in value.lower():
                                        contact_info['linkedin'] = value if 'http' in value.lower() else f"https://{value}"
                                        print(f"✅ LINKEDIN_SEARCH: Найден LinkedIn в ext.data.{key}: {contact_info['linkedin']}")
                                        break
                        
                        if not contact_info['linkedin']:
                            # Проверяем поле resume
                            resume_data = ext.get('resume', {})
                            if isinstance(resume_data, dict) and 'url' in resume_data:
                                resume_url = resume_data['url']
                                if 'linkedin.com' in resume_url.lower():
                                    contact_info['linkedin'] = resume_url if 'http' in resume_url.lower() else f"https://{resume_url}"
                                    print(f"✅ LINKEDIN_SEARCH: Найден LinkedIn в ext.resume.url: {contact_info['linkedin']}")
                    
                    if contact_info['linkedin']:
                        break
        
        # Если LinkedIn не найден в social и external, проверяем questionary
        if not contact_info['linkedin']:
            print(f"🔍 LINKEDIN_SEARCH: LinkedIn не найден в social/external, проверяем questionary")
            questionary = huntflow_service.get_applicant_questionary(account_id, int(candidate_id))
            if questionary:
                print(f"🔍 LINKEDIN_SEARCH: Получена анкета, полей: {len(questionary)}")
                questionary_schema = huntflow_service.get_applicant_questionary_schema(account_id)
                for field_key, field_value in questionary.items():
                    if field_value and isinstance(field_value, str):
                        field_title = ""
                        if questionary_schema and field_key in questionary_schema:
                            field_title = questionary_schema[field_key].get('title', '')
                        
                        print(f"🔍 LINKEDIN_SEARCH: Поле questionary: {field_key} '{field_title}' = {field_value[:100]}")
                        if 'linkedin.com' in field_value.lower() or ('linkedin' in field_value.lower() and 'http' in field_value.lower()):
                            contact_info['linkedin'] = field_value if 'http' in field_value.lower() else f"https://{field_value}"
                            print(f"✅ LINKEDIN_SEARCH: Найден LinkedIn в questionary: {contact_info['linkedin']}")
                            break
        
        # Если все еще не нашли, делаем глубокий поиск по всему объекту candidate_data
        if not contact_info['linkedin']:
            print(f"⚠️ LINKEDIN_SEARCH: LinkedIn не найден стандартными методами, делаем глубокий поиск")
            import json
            
            # Рекурсивно ищем все строки, содержащие linkedin.com
            def find_linkedin_recursive(obj, path=""):
                if isinstance(obj, dict):
                    for key, value in obj.items():
                        current_path = f"{path}.{key}" if path else key
                        if isinstance(value, str) and ('linkedin.com' in value.lower() or ('linkedin' in value.lower() and 'http' in value.lower())):
                            print(f"🔍 LINKEDIN_SEARCH: Найден LinkedIn в {current_path}: {value[:100]}")
                            return value
                        result = find_linkedin_recursive(value, current_path)
                        if result:
                            return result
                elif isinstance(obj, list):
                    for i, item in enumerate(obj):
                        current_path = f"{path}[{i}]" if path else f"[{i}]"
                        result = find_linkedin_recursive(item, current_path)
                        if result:
                            return result
                return None
            
            linkedin_found = find_linkedin_recursive(candidate_data)
            if linkedin_found:
                contact_info['linkedin'] = linkedin_found if 'http' in linkedin_found.lower() else f"https://{linkedin_found}"
                print(f"✅ LINKEDIN_SEARCH: Найден LinkedIn через глубокий поиск: {contact_info['linkedin']}")
        
        # Если все еще не нашли, выводим полную структуру данных для отладки
        if not contact_info['linkedin']:
            print(f"⚠️ LINKEDIN_SEARCH: LinkedIn не найден. Структура candidate_data:")
            print(f"  - Ключи верхнего уровня: {list(candidate_data.keys())}")
            print(f"  - social: {candidate_data.get('social', [])}")
            print(f"  - external: {candidate_data.get('external', [])}")
            print(f"  - externals: {candidate_data.get('externals', [])}")
            # Выводим первые 500 символов JSON для отладки
            try:
                import json
                candidate_json = json.dumps(candidate_data, ensure_ascii=False, indent=2)
                print(f"  - Первые 1000 символов JSON: {candidate_json[:1000]}")
            except:
                pass
        
        # Получаем поле "Где ведется коммуникация" из questionary
        questionary = huntflow_service.get_applicant_questionary(account_id, int(candidate_id))
        if questionary:
            questionary_schema = huntflow_service.get_applicant_questionary_schema(account_id)
            if questionary_schema:
                for field_id, field_info in questionary_schema.items():
                    field_title = field_info.get('title', '').lower()
                    if ('коммуникац' in field_title or 'communication' in field_title or 
                        'где ведется' in field_title or 'где ведётся' in field_title):
                        if field_id in questionary:
                            contact_info['communication_where'] = questionary[field_id]
                            break
        
    except Exception as e:
        print(f"⚠️ Ошибка получения контактной информации кандидата: {e}")
        import traceback
        traceback.print_exc()
    
    return contact_info


def _generate_full_huntflow_link(vacancy_id, candidate_id, user):
    """
    Генерирует полную ссылку на кандидата в Huntflow в формате:
    https://huntflow.ru/my/{account_nick}#/vacancy/{vacancy_id}/filter/workon/id/{candidate_id}
    
    Args:
        vacancy_id: ID вакансии
        candidate_id: ID кандидата
        user: Пользователь Django
    
    Returns:
        str: Полная ссылка на кандидата или None в случае ошибки
    """
    try:
        from apps.huntflow.services import HuntflowService
        
        huntflow_service = HuntflowService(user)
        accounts = huntflow_service.get_accounts()
        
        if accounts and 'items' in accounts and accounts['items']:
            account_data = accounts['items'][0]
            account_id = account_data.get('id')
            account_nick = account_data.get('nick', '')
            
            # Формируем ссылку в зависимости от активной системы
            if user.active_system == 'prod':
                # Для прода используем nickname
                huntflow_link = f"https://huntflow.ru/my/{account_nick}#/vacancy/{vacancy_id}/filter/workon/id/{candidate_id}"
            else:
                # Для sandbox используем account_id
                huntflow_link = f"https://sandbox.huntflow.dev/my/org{account_id}#/vacancy/{vacancy_id}/filter/workon/id/{candidate_id}"
            
            print(f"🔗 Сгенерирована полная ссылка на Huntflow ({user.active_system}): {huntflow_link}")
            return huntflow_link
        else:
            print(f"⚠️ Не удалось получить данные аккаунта из API")
            return None
            
    except Exception as e:
        print(f"❌ Ошибка генерации полной ссылки на Huntflow: {e}")
        return None


@login_required
@permission_required('google_oauth.view_hrscreening', raise_exception=True)
@csrf_exempt
@require_http_methods(["POST"])
def _determine_vacancy_from_candidate_link(candidate_url, user):
    """
    Определяет вакансию кандидата по ссылке на кандидата без указания вакансии
    Формат ссылки: https://huntflow.ru/my/softnetix#/applicants/filter/all/77231621
    
    Returns:
        tuple: (vacancy_id, candidate_id, error_message) или (None, None, error_message)
    """
    import re
    from apps.huntflow.services import HuntflowService
    from apps.vacancies.models import Vacancy
    from apps.accounts.models import User
    
    try:
        # Проверяем, что user является объектом пользователя
        if not user:
            return None, None, "Пользователь не указан"
        
        if isinstance(user, str):
            # Если user является строкой, получаем объект пользователя
            try:
                user = User.objects.get(username=user)
                print(f"🔍 DETERMINE_VACANCY: Преобразована строка в объект пользователя: {user.username}")
            except User.DoesNotExist:
                return None, None, f"Пользователь с username '{user}' не найден"
        elif not isinstance(user, User):
            print(f"❌ DETERMINE_VACANCY: Неверный тип user: {type(user)}, значение: {user}")
            return None, None, f"Ожидается объект User, получен {type(user)}"
        
        # Извлекаем ID кандидата из ссылки формата /applicants/filter/all/77231621
        applicant_pattern = r'/applicants/filter/[^/]+/(\d+)'
        match = re.search(applicant_pattern, candidate_url)
        
        if not match:
            return None, None, "Не удалось извлечь ID кандидата из ссылки"
        
        candidate_id = match.group(1)
        print(f"🔍 DETERMINE_VACANCY: Извлечен ID кандидата: {candidate_id}")
        
        # Получаем информацию о кандидате через Huntflow API
        huntflow_service = HuntflowService(user)
        accounts = huntflow_service.get_accounts()
        
        if not accounts or 'items' not in accounts or not accounts['items']:
            return None, None, "Нет доступных аккаунтов Huntflow"
        
        account_id = accounts['items'][0]['id']
        print(f"🔍 DETERMINE_VACANCY: Используем account_id: {account_id}")
        
        # Получаем данные кандидата
        candidate_data = huntflow_service.get_applicant(account_id, int(candidate_id))
        
        if not candidate_data:
            return None, None, f"Кандидат {candidate_id} не найден в Huntflow"
        
        # Получаем вакансию из links кандидата
        links = candidate_data.get('links', [])
        if not links:
            return None, None, f"У кандидата {candidate_id} нет привязанных вакансий"
        
        # Берем первую активную вакансию
        vacancy_id = None
        for link in links:
            if link.get('vacancy'):
                vacancy_id = link.get('vacancy')
                break
        
        if not vacancy_id:
            return None, None, f"Не удалось определить вакансию для кандидата {candidate_id}"
        
        print(f"✅ DETERMINE_VACANCY: Определена вакансия {vacancy_id} для кандидата {candidate_id}")
        
        # Проверяем, существует ли вакансия в локальной БД
        try:
            vacancy = Vacancy.objects.get(external_id=str(vacancy_id))
            print(f"✅ DETERMINE_VACANCY: Вакансия найдена в локальной БД: {vacancy.name}")
            return str(vacancy_id), candidate_id, None
        except Vacancy.DoesNotExist:
            print(f"⚠️ DETERMINE_VACANCY: Вакансия {vacancy_id} не найдена в локальной БД, но продолжаем работу")
            return str(vacancy_id), candidate_id, None
            
    except Exception as e:
        print(f"❌ DETERMINE_VACANCY: Ошибка определения вакансии: {e}")
        import traceback
        traceback.print_exc()
        return None, None, f"Ошибка определения вакансии: {str(e)}"


def _determine_vacancy_from_text(message_text, user):
    """
    Определяет вакансию из текста сообщения по названию вакансии
    
    Args:
        message_text: Текст сообщения
        user: Пользователь Django
    
    Returns:
        Vacancy объект или None
    """
    from apps.vacancies.models import Vacancy
    from django.db.models import Q
    from apps.accounts.models import User
    
    # Проверяем, что user является объектом пользователя
    if not user:
        print(f"⚠️ DETERMINE_VACANCY_FROM_TEXT: Пользователь не указан")
        return None
    
    if isinstance(user, str):
        # Если user является строкой, получаем объект пользователя
        try:
            user = User.objects.get(username=user)
            print(f"🔍 DETERMINE_VACANCY_FROM_TEXT: Преобразована строка в объект пользователя: {user.username}")
        except User.DoesNotExist:
            print(f"❌ DETERMINE_VACANCY_FROM_TEXT: Пользователь с username '{user}' не найден")
            return None
    elif not isinstance(user, User):
        print(f"❌ DETERMINE_VACANCY_FROM_TEXT: Неверный тип user: {type(user)}, значение: {user}")
        return None
    
    if not message_text or not message_text.strip():
        return None
    
    # Получаем все активные вакансии пользователя
    vacancies = Vacancy.objects.filter(is_active=True).order_by('name')
    
    # Ищем упоминания названий вакансий в тексте
    message_lower = message_text.lower()
    
    # Сначала пытаемся найти точное совпадение (регистронезависимое)
    for vacancy in vacancies:
        vacancy_name_lower = vacancy.name.lower()
        # Проверяем, содержит ли текст название вакансии как отдельное слово
        # Используем границы слов для более точного поиска
        import re
        pattern = r'\b' + re.escape(vacancy_name_lower) + r'\b'
        if re.search(pattern, message_lower):
            print(f"✅ DETERMINE_VACANCY_FROM_TEXT: Найдено точное совпадение: {vacancy.name}")
            return vacancy
    
    # Если точного совпадения нет, ищем частичное совпадение
    # Разбиваем текст на слова и ищем вакансии, содержащие эти слова
    words = [w.strip() for w in message_lower.split() if len(w.strip()) > 2]
    
    best_match = None
    best_score = 0
    
    for vacancy in vacancies:
        vacancy_name_lower = vacancy.name.lower()
        score = 0
        
        # Подсчитываем количество совпадающих слов
        for word in words:
            if word in vacancy_name_lower:
                score += len(word)
        
        # Если название вакансии содержит значительную часть слов из сообщения
        if score > best_score and score >= 5:  # Минимальный порог совпадения
            best_score = score
            best_match = vacancy
    
    if best_match:
        print(f"✅ DETERMINE_VACANCY_FROM_TEXT: Найдено частичное совпадение: {best_match.name} (score: {best_score})")
        return best_match
    
    return None


def _get_or_create_chat_session_for_vacancy(user, vacancy):
    """
    Находит или создает сессию чата для указанной вакансии
    
    Args:
        user: Пользователь Django
        vacancy: Объект Vacancy
    
    Returns:
        ChatSession: Сессия чата для вакансии
    """
    from .models import ChatSession
    from apps.accounts.models import User
    
    # Проверяем, что user является объектом пользователя
    if not user:
        raise ValueError("Пользователь не указан для создания сессии чата")
    
    if isinstance(user, str):
        # Если user является строкой, получаем объект пользователя
        try:
            user = User.objects.get(username=user)
            print(f"🔍 GET_OR_CREATE_CHAT_SESSION: Преобразована строка в объект пользователя: {user.username}")
        except User.DoesNotExist:
            raise ValueError(f"Пользователь с username '{user}' не найден")
    elif not isinstance(user, User):
        print(f"❌ GET_OR_CREATE_CHAT_SESSION: Неверный тип user: {type(user)}, значение: {user}")
        raise ValueError(f"Ожидается объект User, получен {type(user)}")
    
    # Ищем существующую сессию чата для этой вакансии
    chat_session, created = ChatSession.objects.get_or_create(
        user=user,
        vacancy=vacancy,
        defaults={'title': vacancy.name}
    )
    
    if created:
        print(f"✅ Создана новая сессия чата для вакансии: {vacancy.name}")
    else:
        print(f"✅ Найдена существующая сессия чата для вакансии: {vacancy.name}")
    
    return chat_session


def send_chat_message(request):
    """
    AJAX endpoint для отправки сообщения в Google OAuth чат
    Автоматически определяет вакансию из сообщения и переключает на соответствующий чат
    """
    try:
        from apps.accounts.models import User
        
        # Проверяем, что request.user является объектом пользователя
        print(f"🔍 SEND_CHAT_MESSAGE: request.user: {request.user} (тип: {type(request.user)})")
        if not request.user or not isinstance(request.user, User):
            print(f"❌ SEND_CHAT_MESSAGE: request.user не является объектом User: {type(request.user)}")
            return JsonResponse({'success': False, 'error': 'Пользователь не авторизован'})
        
        data = json.loads(request.body)
        print(f"🔍 SEND_CHAT_MESSAGE: Получены данные: {data}")
        session_id = data.get('session_id')
        # Поддерживаем оба варианта: 'message' и 'text'
        message_text = data.get('message', data.get('text', '')).strip()
        message_text = _normalize_chat_command_ru_to_en(message_text)
        print(f"🔍 SEND_CHAT_MESSAGE: message_text (длина: {len(message_text)}): {message_text[:100]}...")
        
        if not message_text:
            return JsonResponse({'success': False, 'error': 'Пустое сообщение'})
        
        if not session_id:
            return JsonResponse({'success': False, 'error': 'ID сессии не указан'})
        
        # Получаем текущую сессию чата
        try:
            print(f"🔍 SEND_CHAT_MESSAGE: Ищем сессию {session_id} для пользователя {request.user.id}")
            current_chat_session = ChatSession.objects.get(id=session_id, user=request.user)
        except ChatSession.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Сессия чата не найдена'})
        
        # Определяем тип действия ПЕРЕД определением вакансии, чтобы пропустить обработку ссылок на резюме
        action_type = None
        parsed_file_data = data.get('parsed_file_data')
        is_add_command = parsed_file_data or message_text.strip() == '/add' or message_text.startswith('/add ')
        
        # Определяем вакансию из сообщения (только если это не команда /add)
        determined_vacancy = None
        
        # 1. Проверяем, есть ли в сообщении ссылка на кандидата (только если не команда /add)
        if not is_add_command:
            import re
            url_pattern = r'https?://[^\s]+'
            urls = re.findall(url_pattern, message_text)
            
            candidate_url_found = None
            for url in urls:
                if 'huntflow' in url.lower():
                    candidate_url_found = url
                    break
            
            # Если найдена ссылка на кандидата, определяем вакансию
            if candidate_url_found:
                print(f"🔍 SEND_CHAT_MESSAGE: Найдена ссылка на кандидата: {candidate_url_found}")
                
                # Проверяем, есть ли в ссылке вакансия
                if '/vacancy/' in candidate_url_found:
                    # Извлекаем vacancy_id из ссылки
                    vacancy_match = re.search(r'/vacancy/(\d+)/', candidate_url_found)
                    if vacancy_match:
                        vacancy_id = vacancy_match.group(1)
                        from apps.vacancies.models import Vacancy
                        try:
                            determined_vacancy = Vacancy.objects.get(external_id=str(vacancy_id))
                            print(f"✅ SEND_CHAT_MESSAGE: Вакансия определена из ссылки: {determined_vacancy.name}")
                        except Vacancy.DoesNotExist:
                            print(f"⚠️ SEND_CHAT_MESSAGE: Вакансия {vacancy_id} не найдена в локальной БД")
                elif '/applicants/filter/' in candidate_url_found:
                    # Ссылка без вакансии - определяем через API
                    vacancy_id, candidate_id, error = _determine_vacancy_from_candidate_link(
                        candidate_url_found, 
                        request.user
                    )
                    
                    if error:
                        return JsonResponse({
                            'success': False, 
                            'error': f'Ошибка определения вакансии: {error}'
                        })
                    
                    if vacancy_id:
                        from apps.vacancies.models import Vacancy
                        try:
                            determined_vacancy = Vacancy.objects.get(external_id=str(vacancy_id))
                            print(f"✅ SEND_CHAT_MESSAGE: Вакансия определена через API: {determined_vacancy.name}")
                        except Vacancy.DoesNotExist:
                            print(f"⚠️ SEND_CHAT_MESSAGE: Вакансия {vacancy_id} не найдена в локальной БД")
        
        # 2. Если вакансия не определена из ссылки, пытаемся определить из текста сообщения (только если не команда /add)
        if not determined_vacancy and not is_add_command:
            print(f"🔍 SEND_CHAT_MESSAGE: Вакансия не найдена в ссылке, пытаемся определить из текста")
            determined_vacancy = _determine_vacancy_from_text(message_text, request.user)
            if determined_vacancy:
                print(f"✅ SEND_CHAT_MESSAGE: Вакансия определена из текста: {determined_vacancy.name}")
        
        # Если вакансия определена и отличается от текущей, переключаемся на правильный чат
        if determined_vacancy and (not current_chat_session.vacancy or current_chat_session.vacancy.id != determined_vacancy.id):
            print(f"🔄 SEND_CHAT_MESSAGE: Переключаемся с вакансии '{current_chat_session.vacancy.name if current_chat_session.vacancy else 'Без вакансии'}' на '{determined_vacancy.name}'")
            # Находим или создаем сессию чата для правильной вакансии
            chat_session = _get_or_create_chat_session_for_vacancy(request.user, determined_vacancy)
        else:
            # Используем текущую сессию или определяем вакансию из текущей сессии
            chat_session = current_chat_session
            if not chat_session.vacancy:
                # Если в текущей сессии нет вакансии, но мы определили её из сообщения
                if determined_vacancy:
                    chat_session.vacancy = determined_vacancy
                    chat_session.title = determined_vacancy.name
                    chat_session.save()
                    print(f"✅ SEND_CHAT_MESSAGE: Обновлена текущая сессия с вакансией: {determined_vacancy.name}")
        
        # Сохраняем исходный текст сообщения для проверки ссылок на резюме
        original_message_text = message_text
        
        # Определяем тип действия (action_type уже определен выше, если это команда /add)
        if is_add_command:
            action_type = 'add_candidate'
            # Убираем префикс '/add ' из сообщения для обработки, если он есть
            if message_text.startswith('/add '):
                message_text = message_text[5:].strip()
            elif message_text.strip() == '/add':
                message_text = ''
        elif message_text.startswith('/t '):
            action_type = 'tech_screening'
        elif message_text.startswith('/in '):
            action_type = 'final_interview'
        elif message_text.startswith('/s '):
            action_type = 'hrscreening'
            # Убираем префикс '/s ' из сообщения для обработки
            message_text = message_text[3:].strip()
        else:
            # Проверяем, есть ли ссылка на резюме (hh.ru или rabota.by) - это тоже команда /add
            # Проверяем в исходном тексте (до удаления префиксов)
            if original_message_text:
                from apps.huntflow.services import HuntflowService
                temp_service = HuntflowService(request.user)
                resume_url_info = temp_service._extract_resume_url(original_message_text)
                if resume_url_info:
                    action_type = 'add_candidate'
                    is_add_command = True
                    # Если в исходном тексте был префикс /add, он уже удален выше
                    # Если нет, но есть ссылка на резюме, используем текст как есть
                else:
                    action_type = 'hrscreening'  # По умолчанию HR-скрининг
            else:
                action_type = 'hrscreening'  # По умолчанию HR-скрининг
        
        # Получаем информацию о файле из запроса (если есть)
        attached_file_name = data.get('attached_file_name', '')
        attached_file_type = data.get('attached_file_type', '')
        
        # Формируем текст сообщения с информацией о файле, если он был прикреплен
        display_message_text = message_text
        if attached_file_name:
            file_info = f"📎 Прикреплен файл: {attached_file_name}"
            if attached_file_type:
                file_info += f" ({attached_file_type})"
            if display_message_text:
                display_message_text = f"{display_message_text}\n\n{file_info}"
            else:
                display_message_text = file_info
        
        # Создаем пользовательское сообщение в правильном чате ДО обработки действий
        user_message = ChatMessage.objects.create(
            session=chat_session,
            message_type='user',
            content=display_message_text
        )
        print(f"✅ SEND_CHAT_MESSAGE: Создано пользовательское сообщение в сессии {chat_session.id}")
        
        print(f"🔍 SEND_CHAT_MESSAGE: action_type: {action_type}, message_text после обработки: {message_text[:100]}...")
        
        # Обрабатываем действие
        if action_type == 'add_candidate':
            # Создаем кандидата в Huntflow с привязкой к вакансии
            print(f"🔍 SEND_CHAT_MESSAGE: Обрабатываем команду /add для создания кандидата")
            
            try:
                from apps.huntflow.views import get_correct_account_id
                from apps.huntflow.services import HuntflowService
                
                # Получаем правильный account_id
                correct_account_id = get_correct_account_id(request.user)
                if not correct_account_id:
                    ChatMessage.objects.create(
                        session=chat_session,
                        message_type='system',
                        content="❌ Не удалось определить организацию Huntflow. Проверьте настройки."
                    )
                    return JsonResponse({'success': False, 'error': 'Не удалось определить организацию Huntflow'})
                
                huntflow_service = HuntflowService(request.user)
                
                # Получаем вакансию из сессии чата
                if not chat_session.vacancy:
                    ChatMessage.objects.create(
                        session=chat_session,
                        message_type='system',
                        content="❌ Не выбрана вакансия. Выберите вакансию перед созданием кандидата."
                    )
                    return JsonResponse({'success': False, 'error': 'Не выбрана вакансия'})
                
                vacancy = chat_session.vacancy
                vacancy_id = int(vacancy.external_id) if vacancy.external_id else None
                
                if not vacancy_id:
                    ChatMessage.objects.create(
                        session=chat_session,
                        message_type='system',
                        content=f"❌ У выбранной вакансии '{vacancy.name}' не указан ID для связи с Huntflow"
                    )
                    return JsonResponse({'success': False, 'error': f'У вакансии "{vacancy.name}" не указан ID для связи с Huntflow'})
                
                # Проверяем наличие ссылок на резюме (hh.ru или rabota.by) в сообщении
                # Используем исходный текст (до удаления префикса /add)
                resume_url_info = None
                # Проверяем в обрезанном message_text (после удаления /add) и в исходном original_message_text
                check_text = message_text if message_text else original_message_text
                if check_text:
                    resume_url_info = huntflow_service._extract_resume_url(check_text)
                
                # Используем распарсенные данные из файла (передаются через JSON)
                parsed_data = parsed_file_data
                
                if parsed_data:
                    print(f"🔍 SEND_CHAT_MESSAGE: Получены распарсенные данные из файла")
                    # Проверяем, что parsed_data - это словарь
                    if not isinstance(parsed_data, dict):
                        print(f"⚠️ SEND_CHAT_MESSAGE: parsed_data не является словарем: {type(parsed_data)}")
                        parsed_data = None
                
                # Если найдена ссылка на резюме, создаем кандидата по ссылке
                if resume_url_info and not parsed_data:
                    print(f"🔍 SEND_CHAT_MESSAGE: Найдена ссылка на резюме: {resume_url_info}")
                    created_applicant = huntflow_service.create_applicant_from_url(
                        account_id=correct_account_id,
                        resume_url=resume_url_info['url'],
                        vacancy_id=vacancy_id,
                        source_type=resume_url_info['source_type'],
                        resume_id=resume_url_info.get('resume_id')
                    )
                    
                    if created_applicant:
                        applicant_id = created_applicant.get('id')
                        candidate_name = f"{created_applicant.get('last_name', '')} {created_applicant.get('first_name', '')} {created_applicant.get('middle_name', '')}".strip()
                        if not candidate_name:
                            candidate_name = "Кандидат"
                        
                        # Формируем ссылку на кандидата
                        candidate_url = _generate_full_huntflow_link(
                            vacancy_id,
                            applicant_id,
                            request.user
                        )
                        if not candidate_url:
                            accounts = huntflow_service.get_accounts()
                            account_nick = ''
                            if accounts and 'items' in accounts and accounts['items']:
                                account_data = accounts['items'][0]
                                account_nick = account_data.get('nick', '')
                            
                            if account_nick:
                                if hasattr(request.user, 'active_system') and request.user.active_system == 'prod':
                                    candidate_url = f"https://huntflow.ru/my/{account_nick}#/vacancy/{vacancy_id}/filter/workon/id/{applicant_id}"
                                else:
                                    candidate_url = f"https://sandbox.huntflow.dev/my/org{correct_account_id}#/vacancy/{vacancy_id}/filter/workon/id/{applicant_id}"
                            else:
                                candidate_url = f"https://huntflow.ru/my/org{correct_account_id}#/applicants/{applicant_id}"
                        
                        # Получаем контактную информацию
                        candidate_contact_info = _get_candidate_contact_info(request.user, applicant_id)
                        
                        # Формируем источник для отображения
                        source_display = f"{resume_url_info['source_type'].lower()}.ru" if resume_url_info['source_type'] == 'HH' else "rabota.by"
                        resume_id_display = resume_url_info.get('resume_id', 'N/A')
                        
                        # Формируем ответ
                        response_content = f"✅ **Кандидат успешно создан и привязан к вакансии**\n\n"
                        response_content += f"👤 **Кандидат:** {candidate_name}\n"
                        response_content += f"💼 **Вакансия:** {vacancy.name}\n"
                        response_content += f"🆔 **ID кандидата:** {applicant_id}\n\n"
                        response_content += f"📎 **{source_display}:** {resume_id_display}\n\n"
                        response_content += f"🔗 [Открыть кандидата в Huntflow]({candidate_url})"
                        
                        metadata = {
                            'action_type': 'add_candidate',
                            'applicant_id': applicant_id,
                            'candidate_name': candidate_name,
                            'vacancy_name': vacancy.name,
                            'candidate_url': candidate_url,
                            'candidate_contact_info': candidate_contact_info,
                            'resume_source': source_display,
                            'resume_id': resume_id_display
                        }
                        
                        response_message = ChatMessage.objects.create(
                            session=chat_session,
                            message_type='system',
                            content=response_content,
                            metadata=metadata
                        )
                        
                        from django.template.loader import render_to_string
                        try:
                            message_html = render_to_string('google_oauth/partials/chat_message.html', {
                                'message': response_message,
                                'user': request.user
                            })
                        except Exception as e:
                            print(f"⚠️ SEND_CHAT_MESSAGE: Ошибка генерации HTML: {e}")
                            message_html = f"<div class='chat-message system'>{response_content}</div>"
                        
                        return JsonResponse({
                            'success': True,
                            'message_html': message_html,
                            'message_id': response_message.id
                        })
                    else:
                        ChatMessage.objects.create(
                            session=chat_session,
                            message_type='system',
                            content="❌ Не удалось создать кандидата по ссылке. Проверьте ссылку и попробуйте снова."
                        )
                        return JsonResponse({'success': False, 'error': 'Не удалось создать кандидата по ссылке'})
                
                # Парсим текст сообщения для извлечения данных кандидата
                candidate_data = {
                    'first_name': '',
                    'last_name': '',
                    'middle_name': '',
                    'email': '',
                    'phone': '',
                    'position': '',
                    'company': '',
                    'salary': '',
                    'resume_text': message_text if message_text else ''
                }
                
                # Если есть распарсенные данные из файла, используем их напрямую без проверок
                # Huntflow сам извлечет все необходимые данные из файла, включая имя и фамилию
                if parsed_data and isinstance(parsed_data, dict):
                    print(f"🔍 SEND_CHAT_MESSAGE: Создаем кандидата из распарсенных данных файла (без проверок)")
                    # Используем create_applicant_from_parsed_data для полной поддержки парсера
                    # Метод сам обработает все данные из файла, включая имя и фамилию
                    created_applicant = huntflow_service.create_applicant_from_parsed_data(
                        account_id=correct_account_id,
                        parsed_data=parsed_data,
                        vacancy_id=vacancy_id
                    )
                else:
                    # Если нет распарсенных данных, пытаемся извлечь имя из текста
                    if not candidate_data['first_name'] and not candidate_data['last_name'] and message_text:
                        lines = message_text.split('\n')
                        if lines:
                            first_line = lines[0].strip()
                            name_parts = first_line.split()
                            if len(name_parts) >= 2:
                                candidate_data['first_name'] = name_parts[0]
                                candidate_data['last_name'] = name_parts[1]
                                if len(name_parts) >= 3:
                                    candidate_data['middle_name'] = name_parts[2]
                    
                    # Проверяем обязательные поля только если нет распарсенных данных
                    if not candidate_data['first_name'] or not candidate_data['last_name']:
                        ChatMessage.objects.create(
                            session=chat_session,
                            message_type='system',
                            content="❌ Не указаны имя и фамилия кандидата. Укажите их в сообщении или прикрепите файл резюме.\n\nПример: `/add Иван Иванов\nemail@example.com\n+7 999 123-45-67`"
                        )
                        return JsonResponse({'success': False, 'error': 'Не указаны имя и фамилия кандидата'})
                    
                    # Создаем кандидата вручную
                    created_applicant = huntflow_service.create_applicant_manual(
                        account_id=correct_account_id,
                        candidate_data=candidate_data,
                        vacancy_id=vacancy_id
                    )
                
                if created_applicant:
                    applicant_id = created_applicant.get('id')
                    
                    # Получаем имя кандидата из созданного объекта или из распарсенных данных
                    candidate_name = ''
                    if parsed_data and isinstance(parsed_data, dict):
                        # Извлекаем имя из распарсенных данных
                        fields = parsed_data.get('fields', {})
                        name_data = fields.get('name', {}) if fields else {}
                        last_name = name_data.get('last', '') if name_data else ''
                        first_name = name_data.get('first', '') if name_data else ''
                        middle_name = name_data.get('middle', '') if name_data else ''
                        candidate_name = f"{last_name} {first_name} {middle_name}".strip()
                    
                    # Если имя не извлечено, используем данные из созданного кандидата
                    if not candidate_name:
                        candidate_name = f"{created_applicant.get('last_name', '')} {created_applicant.get('first_name', '')} {created_applicant.get('middle_name', '')}".strip()
                    
                    # Если имя все еще пустое, используем данные из candidate_data (для ручного ввода)
                    if not candidate_name:
                        candidate_name = f"{candidate_data.get('last_name', '')} {candidate_data.get('first_name', '')} {candidate_data.get('middle_name', '')}".strip()
                    
                    # Если имя все еще пустое, используем дефолтное значение
                    if not candidate_name:
                        candidate_name = "Кандидат"
                    
                    # Формируем ссылку на кандидата в правильном формате
                    # Используем функцию генерации ссылки с account_nick
                    candidate_url = _generate_full_huntflow_link(
                        vacancy_id,
                        applicant_id,
                        request.user
                    )
                    
                    # Если функция вернула None, формируем ссылку вручную
                    if not candidate_url:
                        # Получаем account_nick из API
                        accounts = huntflow_service.get_accounts()
                        account_nick = ''
                        if accounts and 'items' in accounts and accounts['items']:
                            account_data = accounts['items'][0]
                            account_nick = account_data.get('nick', '')
                        
                        if account_nick:
                            # Используем account_nick для прода
                            if hasattr(request.user, 'active_system') and request.user.active_system == 'prod':
                                candidate_url = f"https://huntflow.ru/my/{account_nick}#/vacancy/{vacancy_id}/filter/workon/id/{applicant_id}"
                            else:
                                candidate_url = f"https://sandbox.huntflow.dev/my/org{correct_account_id}#/vacancy/{vacancy_id}/filter/workon/id/{applicant_id}"
                        else:
                            # Fallback на старый формат
                            candidate_url = f"https://huntflow.ru/my/org{correct_account_id}#/applicants/{applicant_id}"
                    
                    # Получаем контактную информацию кандидата для истории
                    candidate_contact_info = _get_candidate_contact_info(request.user, applicant_id)
                    print(f"🔍 SEND_CHAT_MESSAGE: Получена контактная информация для созданного кандидата: {candidate_contact_info}")
                    
                    # Формируем улучшенное сообщение о созданном кандидате
                    response_content = f"✅ **Кандидат успешно создан и привязан к вакансии**\n\n"
                    response_content += f"👤 **Кандидат:** {candidate_name}\n"
                    response_content += f"💼 **Вакансия:** {vacancy.name}\n"
                    response_content += f"🆔 **ID кандидата:** {applicant_id}\n\n"
                    if attached_file_name:
                        file_info = f"📎 **Файл:** {attached_file_name}"
                        if attached_file_type:
                            file_info += f" ({attached_file_type})"
                        response_content += f"{file_info}\n\n"
                    response_content += f"🔗 [Открыть кандидата в Huntflow]({candidate_url})"
                    
                    # Формируем метаданные с информацией о файле и контактах
                    metadata = {
                        'action_type': 'add_candidate',
                        'applicant_id': applicant_id,
                        'candidate_name': candidate_name,
                        'vacancy_name': vacancy.name,
                        'candidate_url': candidate_url,
                        'candidate_contact_info': candidate_contact_info
                    }
                    if attached_file_name:
                        metadata['attached_file_name'] = attached_file_name
                        if attached_file_type:
                            metadata['attached_file_type'] = attached_file_type
                    
                    response_message = ChatMessage.objects.create(
                        session=chat_session,
                        message_type='system',
                        content=response_content,
                        metadata=metadata
                    )
                    
                    # Генерируем HTML для ответного сообщения
                    from django.template.loader import render_to_string
                    try:
                        message_html = render_to_string('google_oauth/partials/chat_message.html', {
                            'message': response_message,
                            'user': request.user
                        })
                    except Exception as e:
                        print(f"⚠️ SEND_CHAT_MESSAGE: Ошибка генерации HTML: {e}")
                        message_html = None
                    
                    print(f"✅ SEND_CHAT_MESSAGE: Кандидат успешно создан: {applicant_id}")
                    
                    return JsonResponse({
                        'success': True,
                        'message_type': 'system',
                        'message_html': message_html,
                        'reload_page': True,  # Флаг для обновления страницы
                        'metadata': {
                            'action_type': 'add_candidate',
                            'applicant_id': applicant_id,
                            'candidate_name': candidate_name,
                            'vacancy_name': vacancy.name,
                            'candidate_url': candidate_url
                        }
                    })
                else:
                    ChatMessage.objects.create(
                        session=chat_session,
                        message_type='system',
                        content="❌ Не удалось создать кандидата в Huntflow. Проверьте данные и попробуйте снова."
                    )
                    return JsonResponse({'success': False, 'error': 'Не удалось создать кандидата в Huntflow'})
                    
            except Exception as e:
                print(f"❌ SEND_CHAT_MESSAGE: Ошибка создания кандидата: {e}")
                import traceback
                traceback.print_exc()
                ChatMessage.objects.create(
                    session=chat_session,
                    message_type='system',
                    content=f"❌ Ошибка при создании кандидата: {str(e)}"
                )
                return JsonResponse({'success': False, 'error': f'Ошибка при создании кандидата: {str(e)}'})
        
        elif action_type == 'hrscreening':
            # Пропускаем обработку hrscreening, если это была команда /add (даже если ссылка на резюме не найдена)
            if is_add_command:
                ChatMessage.objects.create(
                    session=chat_session,
                    message_type='system',
                    content="❌ Не удалось создать кандидата. Проверьте ссылку на резюме (hh.ru или rabota.by) или прикрепите файл."
                )
                return JsonResponse({'success': False, 'error': 'Не удалось создать кандидата по ссылке'})
            # Создаем HR-скрининг
            print(f"🔍 SEND_CHAT_MESSAGE: Создаем HRScreeningForm с user: {request.user} (тип: {type(request.user)})")
            screening_form_data = {'input_data': message_text}
            screening_form = HRScreeningForm(screening_form_data, user=request.user)
            print(f"🔍 SEND_CHAT_MESSAGE: Форма создана, user в форме: {screening_form.user} (тип: {type(screening_form.user)})")
            
            if screening_form.is_valid():
                try:
                    screening = screening_form.save()
                    
                    # Определяем вакансию из созданного скрининга
                    screening_vacancy = None
                    if screening.vacancy_id:
                        from apps.vacancies.models import Vacancy
                        try:
                            screening_vacancy = Vacancy.objects.get(external_id=str(screening.vacancy_id))
                            print(f"✅ SEND_CHAT_MESSAGE: Вакансия определена из скрининга: {screening_vacancy.name}")
                        except Vacancy.DoesNotExist:
                            print(f"⚠️ SEND_CHAT_MESSAGE: Вакансия {screening.vacancy_id} не найдена в локальной БД")
                    
                    # Если вакансия из скрининга отличается от текущей, переключаемся на правильный чат
                    if screening_vacancy and (not chat_session.vacancy or chat_session.vacancy.id != screening_vacancy.id):
                        print(f"🔄 SEND_CHAT_MESSAGE: Переключаемся на правильный чат для вакансии: {screening_vacancy.name}")
                        # Находим или создаем сессию чата для правильной вакансии
                        correct_chat_session = _get_or_create_chat_session_for_vacancy(request.user, screening_vacancy)
                        # Перемещаем пользовательское сообщение в правильную сессию
                        user_message.session = correct_chat_session
                        user_message.save()
                        chat_session = correct_chat_session
                    
                    # Генерируем полную ссылку с вакансией
                    full_candidate_url = None
                    if screening.vacancy_id and screening.candidate_id:
                        full_candidate_url = _generate_full_huntflow_link(
                            screening.vacancy_id,
                            screening.candidate_id,
                            request.user
                        )
                    
                    # Используем полную ссылку, если она сгенерирована, иначе исходную
                    candidate_url_for_metadata = full_candidate_url or screening.candidate_url
                    
                    # Получаем контактную информацию кандидата
                    candidate_contact_info = {}
                    if screening.candidate_id:
                        candidate_contact_info = _get_candidate_contact_info(request.user, screening.candidate_id)
                        print(f"🔍 SEND_CHAT_MESSAGE: Получена контактная информация кандидата: {candidate_contact_info}")
                    
                    # Проверяем, превышает ли зарплата максимальную вилку
                    print(f"🔍 SEND_CHAT_MESSAGE: Проверяем превышение зарплаты над вилкой...")
                    salary_above_range = screening.is_salary_above_range()
                    print(f"🔍 SEND_CHAT_MESSAGE: Результат проверки превышения зарплаты: {salary_above_range}")
                    
                    finance_more_template = None
                    if salary_above_range:
                        print(f"🔍 SEND_CHAT_MESSAGE: Зарплата превышает вилку, получаем шаблон отказа 'Финансы - больше'...")
                        finance_more_template = screening.get_finance_more_rejection_template()
                        if finance_more_template:
                            print(f"✅ SEND_CHAT_MESSAGE: Найден шаблон отказа 'Финансы - больше': {finance_more_template.title} (ID: {finance_more_template.id})")
                        else:
                            print(f"⚠️ SEND_CHAT_MESSAGE: Шаблон отказа 'Финансы - больше' не найден")
                    
                    response_content = ""  # Пустой контент, данные будут браться из metadata
                    
                    # Определяем, нужно ли показывать форму отказа (только при потенциальном отказе)
                    show_rejection_form = False
                    
                    # Проверяем превышение зарплаты
                    if salary_above_range:
                        show_rejection_form = True
                    
                    # Проверяем офисный формат
                    office_format_rejected = screening.is_office_format_rejected()
                    if office_format_rejected:
                        show_rejection_form = True
                    
                    metadata = {
                        'action_type': 'hrscreening',
                        'hr_screening_id': screening.id,  # Исправлено: было screening_id
                        'candidate_name': screening.candidate_name,
                        'vacancy_name': screening.vacancy_title,
                        'determined_grade': screening.determined_grade,
                        'candidate_url': candidate_url_for_metadata,
                        'extracted_salary': str(screening.extracted_salary) if screening.extracted_salary else None,
                        'salary_currency': screening.salary_currency,
                        'candidate_contact_info': candidate_contact_info,
                        'show_rejection_form': show_rejection_form
                    }
                    
                    # Добавляем информацию о шаблоне отказа "Финансы - больше", если зарплата превышает вилку
                    if salary_above_range:
                        metadata['salary_above_range'] = True
                        if finance_more_template:
                            metadata['finance_more_template_id'] = finance_more_template.id
                            metadata['finance_more_template_title'] = finance_more_template.title
                            metadata['finance_more_template_message'] = finance_more_template.message
                            print(f"✅ SEND_CHAT_MESSAGE: Метаданные обновлены с информацией об отказе 'Финансы - больше'")
                    
                    # Добавляем информацию об офисном формате
                    if office_format_rejected:
                        metadata['office_format_rejected'] = True
                        rejection_template = screening.get_office_format_rejection_template()
                        if rejection_template:
                            metadata['rejection_template_id'] = rejection_template.id
                            metadata['rejection_template_title'] = rejection_template.title
                            metadata['rejection_template_message'] = rejection_template.message
                    
                    print(f"🔍 SEND_CHAT_MESSAGE: show_rejection_form={show_rejection_form} (salary_above_range={salary_above_range}, office_format_rejected={office_format_rejected})")
                    
                    ChatMessage.objects.create(
                        session=chat_session,
                        message_type='hrscreening',
                        content=response_content,
                        hr_screening=screening,
                        metadata=metadata
                    )
                    
                    # Формируем URL для перенаправления
                    from django.urls import reverse
                    redirect_url = reverse('google_oauth:chat_workflow_session', args=[chat_session.id])
                    if chat_session.vacancy:
                        redirect_url += f'?vacancy_id={chat_session.vacancy.id}'
                    
                    # Генерируем HTML для ответного сообщения
                    from django.template.loader import render_to_string
                    try:
                        response_message = ChatMessage.objects.filter(
                            session=chat_session,
                            hr_screening=screening
                        ).order_by('-created_at').first()
                        if response_message:
                            message_html = render_to_string('google_oauth/partials/chat_message.html', {
                                'message': response_message,
                                'user': request.user
                            })
                        else:
                            message_html = None
                    except Exception as e:
                        print(f"⚠️ SEND_CHAT_MESSAGE: Ошибка генерации HTML: {e}")
                        message_html = None
                    
                    return JsonResponse({
                        'success': True,
                        'message_type': 'hrscreening',
                        'redirect_url': redirect_url,
                        'session_id': chat_session.id,
                        'message_html': message_html,
                        'metadata': {
                            'action_type': 'hrscreening',
                            'hr_screening_id': screening.id,
                            'candidate_name': screening.candidate_name,
                            'vacancy_name': screening.vacancy_title,
                            'determined_grade': screening.determined_grade,
                            'candidate_url': candidate_url_for_metadata,
                            'extracted_salary': str(screening.extracted_salary) if screening.extracted_salary else None,
                            'salary_currency': screening.salary_currency,
                            'show_rejection_form': show_rejection_form
                        }
                    })
                    
                except Exception as e:
                    print(f"❌ CHAT AJAX: Ошибка создания HR-скрининга: {e}")
                    error_content = f"Ошибка при обработке HR-скрининга: {str(e)}"
                    ChatMessage.objects.create(
                        session=chat_session,
                        message_type='system',
                        content=error_content
                    )
                    return JsonResponse({'success': False, 'error': error_content})
            else:
                error_content = f"Ошибка валидации HR-скрининга: {screening_form.errors}"
                ChatMessage.objects.create(
                    session=chat_session,
                    message_type='system',
                    content=error_content
                )
                return JsonResponse({'success': False, 'error': error_content})
        
        elif action_type == 'tech_screening':
            # Создаем Tech Screening (логика как для invite)
            invite_form_data = {'combined_data': message_text}
            
            # Передаем данные об интервьюере, если они есть
            if 'selected_interviewer' in data:
                invite_form_data['selected_interviewer'] = data['selected_interviewer']
            
            invite_form = InviteCombinedForm(invite_form_data, user=request.user)
            
            if invite_form.is_valid():
                # Проверка грейда: если в Huntflow не указан, спрашиваем пользователя
                if not data.get('confirm_create_without_grade'):
                    candidate_url = invite_form.cleaned_data.get('candidate_url')
                    if candidate_url:
                        needs_confirmation, grade = _check_tech_screening_grade_needs_confirmation(request.user, candidate_url)
                        if needs_confirmation:
                            print(f"🔍 SEND_CHAT_MESSAGE: Грейд не указан в Huntflow, требуем подтверждения")
                            return JsonResponse({
                                'success': False,
                                'requires_grade_confirmation': True,
                                'message': 'В Huntflow не указан грейд кандидата. Создать встречу без грейда?',
                                'original_text': message_text
                            })
                try:
                    invite = invite_form.save()
                    
                    # Определяем вакансию из созданного инвайта
                    invite_vacancy = None
                    if invite.vacancy_id:
                        from apps.vacancies.models import Vacancy
                        try:
                            invite_vacancy = Vacancy.objects.get(external_id=str(invite.vacancy_id))
                            print(f"✅ SEND_CHAT_MESSAGE: Вакансия определена из инвайта: {invite_vacancy.name}")
                        except Vacancy.DoesNotExist:
                            print(f"⚠️ SEND_CHAT_MESSAGE: Вакансия {invite.vacancy_id} не найдена в локальной БД")
                    
                    # Если вакансия из инвайта отличается от текущей, переключаемся на правильный чат
                    if invite_vacancy and (not chat_session.vacancy or chat_session.vacancy.id != invite_vacancy.id):
                        print(f"🔄 SEND_CHAT_MESSAGE: Переключаемся на правильный чат для вакансии: {invite_vacancy.name}")
                        # Находим или создаем сессию чата для правильной вакансии
                        correct_chat_session = _get_or_create_chat_session_for_vacancy(request.user, invite_vacancy)
                        # Перемещаем пользовательское сообщение в правильную сессию
                        user_message.session = correct_chat_session
                        user_message.save()
                        chat_session = correct_chat_session
                    
                    # Генерируем полную ссылку с вакансией
                    full_candidate_url = None
                    if invite.vacancy_id and invite.candidate_id:
                        full_candidate_url = _generate_full_huntflow_link(
                            invite.vacancy_id,
                            invite.candidate_id,
                            request.user
                        )
                    
                    # Используем полную ссылку, если она сгенерирована, иначе исходную
                    candidate_url_for_metadata = full_candidate_url or invite.candidate_url
                    
                    response_content = ""  # Пустой контент, данные будут браться из metadata
                    
                    ChatMessage.objects.create(
                        session=chat_session,
                        message_type='invite',  # Используем существующий тип для совместимости
                        content=response_content,
                        invite=invite,
                        metadata={
                            'action_type': 'tech_screening',
                            'invite_id': invite.id,
                            'candidate_name': invite.candidate_name,
                            'vacancy_name': invite.vacancy_title,
                            'interviewer_name': invite.interviewer.get_full_name() if invite.interviewer else None,
                            'interviewer_email': invite.interviewer.email if invite.interviewer else None,
                            'interview_datetime': invite.interview_datetime.isoformat() if invite.interview_datetime else None,
                            'candidate_url': candidate_url_for_metadata,
                            'calendar_event_url': invite.calendar_event_url,
                            'google_drive_file_url': invite.google_drive_file_url
                        }
                    )
                    
                    # Формируем URL для перенаправления
                    from django.urls import reverse
                    redirect_url = reverse('google_oauth:chat_workflow_session', args=[chat_session.id])
                    if chat_session.vacancy:
                        redirect_url += f'?vacancy_id={chat_session.vacancy.id}'
                    
                    # Генерируем HTML для ответного сообщения
                    from django.template.loader import render_to_string
                    try:
                        response_message = ChatMessage.objects.filter(
                            session=chat_session,
                            invite=invite
                        ).order_by('-created_at').first()
                        if response_message:
                            message_html = render_to_string('google_oauth/partials/chat_message.html', {
                                'message': response_message,
                                'user': request.user
                            })
                        else:
                            message_html = None
                    except Exception as e:
                        print(f"⚠️ SEND_CHAT_MESSAGE: Ошибка генерации HTML: {e}")
                        message_html = None
                    
                    return JsonResponse({
                        'success': True,
                        'message_type': 'invite',
                        'redirect_url': redirect_url,
                        'session_id': chat_session.id,
                        'message_html': message_html,
                        'metadata': {
                            'action_type': 'tech_screening',
                            'invite_id': invite.id,
                            'candidate_name': invite.candidate_name,
                            'vacancy_name': invite.vacancy_title,
                            'interviewer_name': invite.interviewer.get_full_name() if invite.interviewer else None,
                            'interviewer_email': invite.interviewer.email if invite.interviewer else None,
                            'interview_datetime': invite.interview_datetime.isoformat() if invite.interview_datetime else None,
                            'candidate_url': candidate_url_for_metadata,
                            'calendar_event_url': invite.calendar_event_url,
                            'google_drive_file_url': invite.google_drive_file_url
                        }
                    })
                    
                except Exception as e:
                    print(f"❌ CHAT AJAX: Ошибка создания инвайта: {e}")
                    error_content = f"Ошибка при обработке инвайта: {str(e)}"
                    ChatMessage.objects.create(
                        session=chat_session,
                        message_type='system',
                        content=error_content
                    )
                    return JsonResponse({'success': False, 'error': error_content})
            else:
                # Ошибки валидации
                error_content = "Ошибка при обработке Tech Screening:\n"
                for field, errors in invite_form.errors.items():
                    error_content += f"- {field}: {', '.join(errors)}\n"
                
                ChatMessage.objects.create(
                    session=chat_session,
                    message_type='system',
                    content=error_content
                )
                return JsonResponse({'success': False, 'error': error_content})
        
        elif action_type == 'final_interview':
            # Создаем Final Interview БЕЗ скоркарда (используется tech_invite_title)
            invite_form_data = {'combined_data': message_text}
            
            # Передаем данные об интервьюере, если они есть
            if 'selected_interviewer' in data:
                invite_form_data['selected_interviewer'] = data['selected_interviewer']

            # Поддержка множественного выбора интервьюеров из UI (пилюли).
            # Эти данные приходят из frontend как массив ID и используются для attendees календарного события.
            selected_interviewer_ids = data.get('selected_interviewer_ids') or []
            
            invite_form = InviteCombinedForm(invite_form_data, user=request.user)
            
            if invite_form.is_valid():
                try:
                    # Создаем инвайт без сохранения (commit=False)
                    invite = invite_form.save(commit=False)

                    # Если пользователь выбрал интервьюеров в UI, используем только их.
                    # 1) Сохраняем "первого" как основного (для отображения в UI, FK interviewer)
                    # 2) Все выбранные используем как attendees при создании события (через временный атрибут)
                    if selected_interviewer_ids:
                        try:
                            from apps.interviewers.models import Interviewer
                            selected_objs = list(Interviewer.objects.filter(id__in=selected_interviewer_ids, is_active=True))
                            if selected_objs:
                                # основной интервьюер для UI
                                invite.interviewer = selected_objs[0]
                                # все выбранные для календаря
                                invite._selected_interviewer_ids = [i.id for i in selected_objs]
                                print(f"✅ SEND_CHAT_MESSAGE: Выбраны интервьюеры из UI: {invite._selected_interviewer_ids}")
                        except Exception as e:
                            print(f"⚠️ SEND_CHAT_MESSAGE: Не удалось обработать выбранных интервьюеров: {e}")
                    
                    # Устанавливаем формат интервью (онлайн/офис)
                    interview_format = data.get('interview_format', 'online')
                    invite.interview_format = interview_format
                    print(f"🔍 SEND_CHAT_MESSAGE: Установлен формат интервью: {interview_format}")
                    
                    # Используем специальный метод для интервью (без скоркарда)
                    invite.save_for_interview()
                    
                    # Определяем вакансию из созданного инвайта
                    invite_vacancy = None
                    if invite.vacancy_id:
                        from apps.vacancies.models import Vacancy
                        try:
                            invite_vacancy = Vacancy.objects.get(external_id=str(invite.vacancy_id))
                            print(f"✅ SEND_CHAT_MESSAGE: Вакансия определена из инвайта (final_interview): {invite_vacancy.name}")
                        except Vacancy.DoesNotExist:
                            print(f"⚠️ SEND_CHAT_MESSAGE: Вакансия {invite.vacancy_id} не найдена в локальной БД")
                    
                    # Если вакансия из инвайта отличается от текущей, переключаемся на правильный чат
                    if invite_vacancy and (not chat_session.vacancy or chat_session.vacancy.id != invite_vacancy.id):
                        print(f"🔄 SEND_CHAT_MESSAGE: Переключаемся на правильный чат для вакансии (final_interview): {invite_vacancy.name}")
                        # Находим или создаем сессию чата для правильной вакансии
                        correct_chat_session = _get_or_create_chat_session_for_vacancy(request.user, invite_vacancy)
                        # Перемещаем пользовательское сообщение в правильную сессию
                        user_message.session = correct_chat_session
                        user_message.save()
                        chat_session = correct_chat_session
                    
                    # Генерируем полную ссылку с вакансией
                    full_candidate_url = None
                    if invite.vacancy_id and invite.candidate_id:
                        full_candidate_url = _generate_full_huntflow_link(
                            invite.vacancy_id,
                            invite.candidate_id,
                            request.user
                        )
                    
                    # Используем полную ссылку, если она сгенерирована, иначе исходную
                    candidate_url_for_metadata = full_candidate_url or invite.candidate_url
                    
                    response_content = ""  # Пустой контент, данные будут браться из metadata
                    
                    ChatMessage.objects.create(
                        session=chat_session,
                        message_type='invite',  # Используем существующий тип для совместимости
                        content=response_content,
                        invite=invite,
                        metadata={
                            'action_type': 'final_interview',
                            'invite_id': invite.id,
                            'candidate_name': invite.candidate_name,
                            'vacancy_name': invite.vacancy_title,
                            'interviewer_name': invite.interviewer.get_full_name() if invite.interviewer else None,
                            'interviewer_email': invite.interviewer.email if invite.interviewer else None,
                            'interview_datetime': invite.interview_datetime.isoformat() if invite.interview_datetime else None,
                            'candidate_url': candidate_url_for_metadata,
                            'calendar_event_url': invite.calendar_event_url,
                            # google_drive_file_url не создается для интервью
                        }
                    )
                    
                    # Формируем URL для перенаправления
                    from django.urls import reverse
                    redirect_url = reverse('google_oauth:chat_workflow_session', args=[chat_session.id])
                    if chat_session.vacancy:
                        redirect_url += f'?vacancy_id={chat_session.vacancy.id}'
                    
                    # Генерируем HTML для ответного сообщения
                    from django.template.loader import render_to_string
                    try:
                        response_message = ChatMessage.objects.filter(
                            session=chat_session,
                            invite=invite
                        ).order_by('-created_at').first()
                        if response_message:
                            message_html = render_to_string('google_oauth/partials/chat_message.html', {
                                'message': response_message,
                                'user': request.user
                            })
                        else:
                            message_html = None
                    except Exception as e:
                        print(f"⚠️ SEND_CHAT_MESSAGE: Ошибка генерации HTML: {e}")
                        message_html = None
                    
                    return JsonResponse({
                        'success': True,
                        'message_type': 'invite',
                        'redirect_url': redirect_url,
                        'session_id': chat_session.id,
                        'message_html': message_html,
                        'metadata': {
                            'action_type': 'final_interview',
                            'invite_id': invite.id,
                            'candidate_name': invite.candidate_name,
                            'vacancy_name': invite.vacancy_title,
                            'interviewer_name': invite.interviewer.get_full_name() if invite.interviewer else None,
                            'interviewer_email': invite.interviewer.email if invite.interviewer else None,
                            'interview_datetime': invite.interview_datetime.isoformat() if invite.interview_datetime else None,
                            'candidate_url': candidate_url_for_metadata,
                            'calendar_event_url': invite.calendar_event_url,
                            # google_drive_file_url не создается для интервью
                        }
                    })
                    
                except Exception as e:
                    print(f"❌ CHAT AJAX: Ошибка создания Final Interview: {e}")
                    import traceback
                    traceback.print_exc()
                    error_content = f"Ошибка при обработке Final Interview: {str(e)}"
                    ChatMessage.objects.create(
                        session=chat_session,
                        message_type='system',
                        content=error_content
                    )
                    return JsonResponse({'success': False, 'error': error_content})
            else:
                # Ошибки валидации
                error_content = "Ошибка при обработке Final Interview:\n"
                for field, errors in invite_form.errors.items():
                    error_content += f"- {field}: {', '.join(errors)}\n"
                
                ChatMessage.objects.create(
                    session=chat_session,
                    message_type='system',
                    content=error_content
                )
                return JsonResponse({'success': False, 'error': error_content})
        
        elif action_type == 'add_candidate':
            # Создаем кандидата в Huntflow с привязкой к вакансии
            print(f"🔍 SEND_CHAT_MESSAGE: Обрабатываем команду /add для создания кандидата")
            
            try:
                from apps.huntflow.views import get_correct_account_id
                from apps.huntflow.services import HuntflowService
                
                # Получаем правильный account_id
                correct_account_id = get_correct_account_id(request.user)
                if not correct_account_id:
                    ChatMessage.objects.create(
                        session=chat_session,
                        message_type='system',
                        content="❌ Не удалось определить организацию Huntflow. Проверьте настройки."
                    )
                    return JsonResponse({'success': False, 'error': 'Не удалось определить организацию Huntflow'})
                
                huntflow_service = HuntflowService(request.user)
                
                # Получаем вакансию из сессии чата
                if not chat_session.vacancy:
                    ChatMessage.objects.create(
                        session=chat_session,
                        message_type='system',
                        content="❌ Не выбрана вакансия. Выберите вакансию перед созданием кандидата."
                    )
                    return JsonResponse({'success': False, 'error': 'Не выбрана вакансия'})
                
                vacancy = chat_session.vacancy
                vacancy_id = int(vacancy.external_id) if vacancy.external_id else None
                
                if not vacancy_id:
                    ChatMessage.objects.create(
                        session=chat_session,
                        message_type='system',
                        content=f"❌ У выбранной вакансии '{vacancy.name}' не указан ID для связи с Huntflow"
                    )
                    return JsonResponse({'success': False, 'error': f'У вакансии "{vacancy.name}" не указан ID для связи с Huntflow'})
                
                # Парсим текст сообщения для извлечения данных кандидата
                candidate_data = {
                    'first_name': '',
                    'last_name': '',
                    'middle_name': '',
                    'email': '',
                    'phone': '',
                    'position': '',
                    'company': '',
                    'salary': '',
                    'resume_text': message_text if message_text else ''
                }
                
                # Если имя и фамилия не заполнены, пытаемся извлечь из текста
                if message_text:
                    lines = message_text.split('\n')
                    if lines:
                        first_line = lines[0].strip()
                        name_parts = first_line.split()
                        if len(name_parts) >= 2:
                            candidate_data['first_name'] = name_parts[0]
                            candidate_data['last_name'] = name_parts[1]
                            if len(name_parts) >= 3:
                                candidate_data['middle_name'] = name_parts[2]
                
                # Проверяем обязательные поля
                if not candidate_data['first_name'] or not candidate_data['last_name']:
                    ChatMessage.objects.create(
                        session=chat_session,
                        message_type='system',
                        content="❌ Не указаны имя и фамилия кандидата. Укажите их в сообщении или прикрепите файл резюме.\n\nПример: `/add Иван Иванов\nemail@example.com\n+7 999 123-45-67`"
                    )
                    return JsonResponse({'success': False, 'error': 'Не указаны имя и фамилия кандидата'})
                
                # Создаем кандидата вручную
                created_applicant = huntflow_service.create_applicant_manual(
                    account_id=correct_account_id,
                    candidate_data=candidate_data,
                    vacancy_id=vacancy_id
                )
                
                if created_applicant:
                    applicant_id = created_applicant.get('id')
                    candidate_name = f"{candidate_data.get('last_name', '')} {candidate_data.get('first_name', '')} {candidate_data.get('middle_name', '')}".strip()
                    
                    # Формируем ссылку на кандидата
                    candidate_url = f"https://huntflow.ru/my/org{correct_account_id}#/applicants/{applicant_id}"
                    
                    response_content = f"✅ **Кандидат успешно создан и привязан к вакансии**\n\n"
                    response_content += f"**Кандидат:** {candidate_name}\n"
                    response_content += f"**Вакансия:** {vacancy.name}\n"
                    response_content += f"**ID кандидата:** {applicant_id}\n\n"
                    response_content += f"[Открыть кандидата в Huntflow]({candidate_url})"
                    
                    response_message = ChatMessage.objects.create(
                        session=chat_session,
                        message_type='system',
                        content=response_content,
                        metadata={
                            'action_type': 'add_candidate',
                            'applicant_id': applicant_id,
                            'candidate_name': candidate_name,
                            'vacancy_name': vacancy.name,
                            'candidate_url': candidate_url
                        }
                    )
                    
                    # Генерируем HTML для ответного сообщения
                    from django.template.loader import render_to_string
                    try:
                        message_html = render_to_string('google_oauth/partials/chat_message.html', {
                            'message': response_message,
                            'user': request.user
                        })
                    except Exception as e:
                        print(f"⚠️ SEND_CHAT_MESSAGE: Ошибка генерации HTML: {e}")
                        message_html = None
                    
                    print(f"✅ SEND_CHAT_MESSAGE: Кандидат успешно создан: {applicant_id}")
                    
                    return JsonResponse({
                        'success': True,
                        'message_type': 'system',
                        'message_html': message_html,
                        'metadata': {
                            'action_type': 'add_candidate',
                            'applicant_id': applicant_id,
                            'candidate_name': candidate_name,
                            'vacancy_name': vacancy.name,
                            'candidate_url': candidate_url
                        }
                    })
                else:
                    ChatMessage.objects.create(
                        session=chat_session,
                        message_type='system',
                        content="❌ Не удалось создать кандидата в Huntflow. Проверьте данные и попробуйте снова."
                    )
                    return JsonResponse({'success': False, 'error': 'Не удалось создать кандидата в Huntflow'})
                    
            except Exception as e:
                print(f"❌ SEND_CHAT_MESSAGE: Ошибка создания кандидата: {e}")
                import traceback
                traceback.print_exc()
                ChatMessage.objects.create(
                    session=chat_session,
                    message_type='system',
                    content=f"❌ Ошибка при создании кандидата: {str(e)}"
                )
                return JsonResponse({'success': False, 'error': f'Ошибка при создании кандидата: {str(e)}'})
        
        return JsonResponse({'success': False, 'error': 'Неизвестный тип действия'})
        
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Неверный JSON в запросе'})
    except Exception as e:
        print(f"❌ CHAT AJAX: Общая ошибка: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': f'Внутренняя ошибка сервера: {str(e)}'})


@login_required
@permission_required('google_oauth.view_hrscreening', raise_exception=True)
def chat_workflow(request, session_id=None):
    """Чат-воркфлоу для HR-скрининга и инвайтов"""
    from .models import ChatSession, ChatMessage
    from .forms import ChatForm, HRScreeningForm, InviteCombinedForm

    # Получаем выбранную вакансию из параметров
    vacancy_id = request.GET.get('vacancy_id')
    force_refresh_slots = bool(request.GET.get('refresh_slots') or request.GET.get('force_refresh'))
    if not vacancy_id:
        # Если вакансия не указана: сначала «мои», затем «дополнительные»
        from apps.vacancies.models import Vacancy
        main = Vacancy.objects.filter(is_active=True, recruiter=request.user).order_by('name').first()
        if main:
            return redirect(f'{request.path}?vacancy_id={main.id}')
        additional = Vacancy.objects.filter(is_active=True, additional_recruiters=request.user).order_by('name').first()
        if additional:
            return redirect(f'{request.path}?vacancy_id={additional.id}')
        messages.error(request, 'Нет активных вакансий, назначенных вам для создания чата')
        return redirect('google_oauth:chat_workflow')
    
    try:
        from apps.vacancies.models import Vacancy
        vacancy = Vacancy.objects.get(id=vacancy_id, is_active=True)
        if vacancy.recruiter_id != request.user.id and not vacancy.additional_recruiters.filter(pk=request.user.pk).exists():
            messages.error(request, 'У вас нет доступа к этой вакансии')
            return redirect('google_oauth:chat_workflow')
    except Vacancy.DoesNotExist:
        messages.error(request, 'Выбранная вакансия не найдена, неактивна или не назначена вам')
        return redirect('google_oauth:chat_workflow')
    
    # Получаем или создаем сессию чата для конкретной вакансии
    if session_id:
        try:
            chat_session = ChatSession.objects.get(id=session_id, user=request.user, vacancy=vacancy)
        except ChatSession.DoesNotExist:
            # Если указанная сессия не найдена, ищем существующий чат для этой вакансии
            try:
                chat_session = ChatSession.objects.get(user=request.user, vacancy=vacancy)
            except ChatSession.DoesNotExist:
                # Если чата для этой вакансии нет, создаем новый
                chat_session = ChatSession.objects.create(user=request.user, vacancy=vacancy, title=vacancy.name)
    else:
        # Если session_id не указан, получаем или создаем чат для этой вакансии
        chat_session, created = ChatSession.objects.get_or_create(
            user=request.user, 
            vacancy=vacancy,
            defaults={'title': vacancy.name}
        )

    # Получаем все сообщения в этой сессии
    # Важно: используем select_related/prefetch_related если нужно, но для JSONField это не требуется
    messages_queryset = chat_session.messages.all().order_by('created_at')
    
    # Добавляем информацию о команде для каждого пользовательского сообщения
    messages_list = list(messages_queryset)
    
    # Логируем информацию о формах отказа для отладки и нормализуем данные
    # ВАЖНО: Инициализируем флаг для всех сообщений
    for msg in messages_list:
        msg.should_show_rejection_form = False  # По умолчанию форма не показывается
        
        if msg.message_type == 'hrscreening':
            # Принудительно обновляем объект из базы для получения актуальных данных
            msg.refresh_from_db()
            
            if msg.metadata:
                # КРИТИЧЕСКИ ВАЖНО: Создаем копию metadata для нормализации, чтобы не изменять оригинал
                normalized_metadata = dict(msg.metadata)
                
                # Нормализуем булевы значения - убеждаемся, что они действительно булевы
                if 'rejection_form_answered' in normalized_metadata:
                    val = normalized_metadata['rejection_form_answered']
                    if isinstance(val, str):
                        normalized_metadata['rejection_form_answered'] = val.lower() in ('true', '1', 'yes')
                    elif not isinstance(val, bool):
                        normalized_metadata['rejection_form_answered'] = bool(val)
                
                if 'rejected' in normalized_metadata:
                    val = normalized_metadata['rejected']
                    if isinstance(val, str):
                        normalized_metadata['rejected'] = val.lower() in ('true', '1', 'yes')
                    elif not isinstance(val, bool):
                        normalized_metadata['rejected'] = bool(val)
                
                # Присваиваем нормализованные значения обратно
                msg.metadata = normalized_metadata
                
                show_form = msg.metadata.get('show_rejection_form', False)
                answered = msg.metadata.get('rejection_form_answered', False)
                rejected = msg.metadata.get('rejected', False)
                answered_type = type(answered).__name__
                rejected_type = type(rejected).__name__
                
                # КРИТИЧЕСКИ ВАЖНО: Добавляем флаг прямо в объект сообщения для упрощения проверки в шаблоне
                should_show_rejection_form = bool(show_form and not answered and not rejected)
                msg.should_show_rejection_form = should_show_rejection_form
                
                print(f"🔍 CHAT_WORKFLOW: Сообщение {msg.id} - show_rejection_form={show_form} (тип: {type(show_form).__name__}), rejection_form_answered={answered} (тип: {answered_type}), rejected={rejected} (тип: {rejected_type}), metadata_keys={list(msg.metadata.keys())}")
                print(f"🔍 CHAT_WORKFLOW: Должна ли форма показываться? show_form=True AND answered=False AND rejected=False = {should_show_rejection_form}")
                print(f"🔍 CHAT_WORKFLOW: Установлен флаг msg.should_show_rejection_form = {should_show_rejection_form}")
            else:
                print(f"🔍 CHAT_WORKFLOW: Сообщение {msg.id} - metadata отсутствует или пуст")
    for i, msg in enumerate(messages_list):
        if msg.message_type == 'user':
            command_used = None
            # Проверяем следующее сообщение
            if i + 1 < len(messages_list):
                next_msg = messages_list[i + 1]
                if next_msg.message_type == 'hrscreening':
                    command_used = '/s'
                elif next_msg.message_type == 'invite':
                    # Определяем команду по metadata
                    metadata = next_msg.metadata or {}
                    action_type = metadata.get('action_type', '')
                    if action_type == 'tech_screening':
                        command_used = '/t'
                    elif action_type == 'final_interview':
                        command_used = '/in'
                    else:
                        command_used = '/t'  # По умолчанию для обратной совместимости
            # Если не нашли по следующему сообщению, проверяем текст
            if not command_used:
                content = msg.content or ''
                if content.startswith('/s ') or content.startswith('/hr '):
                    command_used = '/s'
                elif content.startswith('/t '):
                    command_used = '/t'
                elif content.startswith('/in ') or content.startswith('/invite '):
                    command_used = '/in'
            # Добавляем атрибут к объекту сообщения для использования в шаблоне
            msg.command_used = command_used
    
    messages = messages_list
    form = ChatForm(user=request.user)

    if request.method == 'POST':
        # Проверяем, это AJAX запрос или обычная форма
        if request.content_type == 'application/json':
            # AJAX запрос должен обрабатываться в chat_ajax_handler
            return JsonResponse({'success': False, 'error': 'AJAX запрос должен отправляться на /ajax/ URL'})
        
        form = ChatForm(request.POST, user=request.user)
        if form.is_valid():
            message_text = form.cleaned_data['message']
            message_text = _normalize_chat_command_ru_to_en(message_text)
            
            # Сохраняем пользовательское сообщение
            user_message = ChatMessage.objects.create(
                session=chat_session,
                message_type='user',
                content=message_text
            )

            # Определяем тип действия (с приоритетом команд)
            message_lower = message_text.strip().lower()
            
            if re.match(r'^/del(\s|$)', message_lower):
                action_type = 'delete_last'
                print(f"🔍 CHAT: Команда /del обнаружена - удаление последнего действия")
                message_text = re.sub(r'^/del\s*', '', message_text, flags=re.IGNORECASE).strip()
            elif re.match(r'^/s(\s|$)', message_lower):
                action_type = 'hrscreening'
                print(f"🔍 CHAT: Команда /s обнаружена - принудительный HR-скрининг")
                message_text = re.sub(r'^/s\s*', '', message_text, flags=re.IGNORECASE).strip()
            elif re.match(r'^/t(\s|$)', message_lower):
                action_type = 'tech_screening'
                print(f"🔍 CHAT: Команда /t обнаружена - Tech Screening")
                message_text = re.sub(r'^/t\s*', '', message_text, flags=re.IGNORECASE).strip()
            elif re.match(r'^/in(\s|$)', message_lower):
                action_type = 'final_interview'
                print(f"🔍 CHAT: Команда /in обнаружена - Final Interview")
                message_text = re.sub(r'^/in\s*', '', message_text, flags=re.IGNORECASE).strip()
            else:
                # Комбинированный/автоматический режим отключен: требуем явные команды
                ChatMessage.objects.create(
                    session=chat_session,
                    message_type='system',
                    content='Укажи команду: /s для HR-скрининга, /t для Tech Screening или /in для Final Interview'
                )
                # Возвращаемся на исходный URL с сохранением query-параметров
                return redirect(request.get_full_path())

            try:
                if action_type == 'delete_last':
                    # Проверяем, не была ли уже выполнена команда удаления
                    last_message = ChatMessage.objects.filter(
                        session=chat_session
                    ).order_by('-created_at').first()
                    
                    if last_message and last_message.message_type == 'delete':
                        ChatMessage.objects.create(
                            session=chat_session,
                            message_type='system',
                            content="⚠️ **Команда удаления уже была выполнена**\n\nКоманда `/del` может быть использована только один раз подряд. Сначала создайте новое действие (HR-скрининг или инвайт), а затем используйте команду удаления."
                        )
                    else:
                        # Обрабатываем команду удаления последнего действия
                        delete_result = delete_last_action(chat_session, request.user)
                        
                        if delete_result['success']:
                            # Создаем стилизованный ответ в виде карточки
                            action_type_display = {
                                'hrscreening': 'HR-скрининг',
                                'tech_screening': 'Tech Screening',
                        'final_interview': 'Final Interview'
                            }.get(delete_result['action_type'], delete_result['action_type'])
                            
                            # Формируем список изменений
                            changes_html = ""
                            if delete_result.get('changes'):
                                changes_list = []
                                for change in delete_result['changes']:
                                    changes_list.append(f"<li>{change}</li>")
                                changes_html = f"""
<div class="delete-changes">
<h6><i class="fas fa-list me-2"></i>Выполненные изменения:</h6>
<ul>{''.join(changes_list)}</ul>
</div>"""
                            
                            # Формируем ссылку на Huntflow
                            huntflow_link = ""
                            if delete_result.get('huntflow_candidate_url'):
                                huntflow_link = f"""
<div class="delete-item">
<span class="delete-label">Huntflow:</span> 
<a href="{delete_result['huntflow_candidate_url']}" target="_blank" class="btn btn-sm btn-outline-primary">
<i class="fas fa-external-link-alt me-1"></i>Открыть кандидата
</a>
</div>"""
                            
                            response_content = f"""<div class="delete-result-card">
<div class="delete-header">
<i class="fas fa-trash-alt text-danger me-2"></i>
<strong>Удалено</strong>
</div>
<div class="delete-info">
<div class="delete-item">
<span class="delete-label">Тип:</span> {action_type_display}
</div>
<div class="delete-item">
<span class="delete-label">Кандидат:</span> {delete_result.get('candidate_name', 'Не указан')}
</div>
<div class="delete-item">
<span class="delete-label">Вакансия:</span> {delete_result.get('vacancy_name', 'Не указана')}
</div>
{huntflow_link}
</div>
<div class="delete-status">
<i class="fas fa-check-circle text-success me-2"></i>
<span class="delete-status-text">Данные удалены и изменения отменены</span>
</div>
{changes_html if changes_html else ''}
</div>"""
                        
                            ChatMessage.objects.create(
                                session=chat_session,
                                message_type='delete',
                                content=response_content,
                                metadata={
                                    'action_type': 'delete_last',
                                    'deleted_action_type': delete_result['action_type'],
                                    'deleted_object_id': delete_result.get('deleted_object_id'),
                                    'deleted_candidate_name': delete_result.get('candidate_name'),
                                    'deleted_vacancy_name': delete_result.get('vacancy_name'),
                                    'huntflow_candidate_url': delete_result.get('huntflow_candidate_url'),
                                    'changes': delete_result.get('changes', [])
                                }
                            )
                        else:
                            ChatMessage.objects.create(
                                session=chat_session,
                                message_type='system',
                                content=f"❌ **Ошибка при удалении**\n\n{delete_result.get('message', 'Неизвестная ошибка')}"
                            )
                        
                elif action_type == 'hrscreening':
                    # Создаем HR-скрининг с ПРАВИЛЬНЫМИ данными
                    hr_form = HRScreeningForm({'input_data': message_text}, user=request.user)
                    
                    if hr_form.is_valid():
                        try:
                            hr_screening = hr_form.save()
                            
                            # ВАЖНО: Перезагружаем объект из БД, чтобы получить актуальные данные,
                            # включая зарплату, которая могла быть извлечена в analyze_with_gemini
                            from apps.google_oauth.models import HRScreening
                            hr_screening = HRScreening.objects.get(id=hr_screening.id)
                            
                            print(f"🔍 CHAT: HR-скрининг перезагружен, зарплата: {hr_screening.extracted_salary}, валюта: {hr_screening.salary_currency}")
                            
                            # Получаем контактную информацию кандидата
                            candidate_contact_info = {}
                            if hr_screening.candidate_id:
                                candidate_contact_info = _get_candidate_contact_info(request.user, hr_screening.candidate_id)
                                print(f"🔍 CHAT: Получена контактная информация кандидата: {candidate_contact_info}")
                            
                            # Проверяем, превышает ли зарплата максимальную вилку
                            print(f"🔍 CHAT: Проверяем превышение зарплаты над вилкой...")
                            salary_above_range = hr_screening.is_salary_above_range()
                            print(f"🔍 CHAT: Результат проверки превышения зарплаты: {salary_above_range}")
                            
                            finance_more_template = None
                            if salary_above_range:
                                print(f"🔍 CHAT: Зарплата превышает вилку, получаем шаблон отказа 'Финансы - больше'...")
                                finance_more_template = hr_screening.get_finance_more_rejection_template()
                                if finance_more_template:
                                    print(f"✅ CHAT: Найден шаблон отказа 'Финансы - больше': {finance_more_template.title} (ID: {finance_more_template.id})")
                                else:
                                    print(f"⚠️ CHAT: Шаблон отказа 'Финансы - больше' не найден")
                            
                            response_content = ""  # Пустой контент, данные будут браться из metadata
                            
                            # Определяем, нужно ли показывать форму отказа (только при потенциальном отказе)
                            show_rejection_form = False
                            
                            # Проверяем офисный формат
                            office_format_rejected = hr_screening.is_office_format_rejected()
                            if office_format_rejected:
                                show_rejection_form = True
                            
                            # Проверяем превышение зарплаты
                            if salary_above_range:
                                show_rejection_form = True
                            
                            metadata = {
                                'action_type': 'hrscreening',
                                'hr_screening_id': hr_screening.id,
                                'candidate_name': hr_screening.candidate_name,
                                'vacancy_name': hr_screening.vacancy_title,
                                'determined_grade': hr_screening.determined_grade,
                                'candidate_url': hr_screening.candidate_url,
                                'extracted_salary': str(hr_screening.extracted_salary) if hr_screening.extracted_salary else None,
                                'salary_currency': hr_screening.salary_currency,
                                'candidate_contact_info': candidate_contact_info,
                                'show_rejection_form': show_rejection_form
                            }
                            
                            # Добавляем информацию о шаблоне отказа "Финансы - больше", если зарплата превышает вилку
                            if salary_above_range:
                                metadata['salary_above_range'] = True
                                if finance_more_template:
                                    metadata['finance_more_template_id'] = finance_more_template.id
                                    metadata['finance_more_template_title'] = finance_more_template.title
                                    metadata['finance_more_template_message'] = finance_more_template.message
                                    print(f"✅ CHAT: Метаданные обновлены с информацией об отказе 'Финансы - больше'")
                            
                            # Добавляем информацию об офисном формате
                            if office_format_rejected:
                                metadata['office_format_rejected'] = True
                                rejection_template = hr_screening.get_office_format_rejection_template()
                                if rejection_template:
                                    metadata['rejection_template_id'] = rejection_template.id
                                    metadata['rejection_template_title'] = rejection_template.title
                                    metadata['rejection_template_message'] = rejection_template.message
                            
                            print(f"🔍 CHAT: show_rejection_form={show_rejection_form} (salary_above_range={salary_above_range}, office_format_rejected={office_format_rejected})")
                            
                            ChatMessage.objects.create(
                                session=chat_session,
                                message_type='hrscreening',
                                content=response_content,
                                hr_screening=hr_screening,
                                metadata=metadata
                            )
                        except Exception as e:
                            print(f"🔍 CHAT: Ошибка сохранения HR: {str(e)}")
                            ChatMessage.objects.create(
                                session=chat_session,
                                message_type='system',
                                content=f"Ошибка при обработке HR-скрининга: {str(e)}"
                            )
                    else:
                        # Ошибки валидации
                        error_content = "Ошибка при обработке HR-скрининга:\n"
                        for field, errors in hr_form.errors.items():
                            error_content += f"- {field}: {', '.join(errors)}\n"
                        
                        ChatMessage.objects.create(
                            session=chat_session,
                            message_type='system',
                            content=error_content
                        )

                elif action_type == 'tech_screening':
                    # Создаем Tech Screening с ПРАВИЛЬНЫМИ данными
                    invite_form_data = {'combined_data': message_text}
                    
                    # Передаем данные об интервьюере, если они есть
                    if 'selected_interviewer' in request.POST:
                        invite_form_data['selected_interviewer'] = request.POST['selected_interviewer']
                        print(f"🔍 CHAT: Передаем данные об интервьюере: {request.POST['selected_interviewer']}")
                    
                    invite_form = InviteCombinedForm(invite_form_data, user=request.user)
                    
                    if invite_form.is_valid():
                        try:
                            invite = invite_form.save()
                            
                            response_content = f"""**Tech Screening создан**

**Кандидат:** {invite.candidate_name or 'Не указан'}
**Вакансия:** {invite.vacancy_title or 'Не указана'}
**Уровень:** {invite.candidate_grade or 'Не определен'}
**Интервьюер:** {invite.interviewer.get_full_name() if invite.interviewer else 'Не назначен'}
**Scorecard:** {invite.google_drive_file_url or 'Создается...'}
**Дата интервью:** {invite.interview_datetime.strftime('%d.%m.%Y %H:%M') if invite.interview_datetime else 'Не указана'}
**Google Meet:** {invite.google_meet_url or 'Будет создана'}

✅ **Tech Screening отправлен и добавлен в календарь**"""
                            
                            ChatMessage.objects.create(
                                session=chat_session,
                                message_type='invite',  # Используем существующий тип для совместимости
                                content=response_content,
                                invite=invite,
                                metadata={
                                    'action_type': 'tech_screening',
                                    'invite_id': invite.id,
                                    'candidate_name': invite.candidate_name,
                                    'vacancy_name': invite.vacancy_title,
                                    'determined_grade': invite.candidate_grade,
                                    'interviewer_name': invite.interviewer.get_full_name() if invite.interviewer else None,
                                    'interviewer_email': invite.interviewer.email if invite.interviewer else None,
                                    'interview_datetime': invite.interview_datetime.isoformat() if invite.interview_datetime else None,
                                    'candidate_url': invite.candidate_url
                                }
                            )
                        except Exception as e:
                            print(f"🔍 CHAT: Ошибка сохранения Tech Screening: {str(e)}")
                            ChatMessage.objects.create(
                                session=chat_session,
                                message_type='system',
                                content=f"Ошибка при обработке Tech Screening: {str(e)}"
                            )
                    else:
                        # Ошибки валидации
                        error_content = "Ошибка при обработке Tech Screening:\n"
                        for field, errors in invite_form.errors.items():
                            error_content += f"- {field}: {', '.join(errors)}\n"
                        
                        ChatMessage.objects.create(
                            session=chat_session,
                            message_type='system',
                            content=error_content
                        )

            except Exception as e:
                print(f"🔍 CHAT: Критическая ошибка: {str(e)}")
                import traceback
                traceback.print_exc()
                ChatMessage.objects.create(
                    session=chat_session,
                    message_type='system',
                    content=f"Ошибка при обработке: {str(e)}"
                )

            # Обновляем время сессии и перенаправляем с сохранением vacancy_id
            chat_session.save()
            from django.urls import reverse
            return redirect(f"{reverse('google_oauth:chat_workflow_session', args=[chat_session.id])}?vacancy_id={vacancy.id}")

    print(f"🔍 DEBUG CHAT: Функция chat_workflow выполняется для пользователя: {request.user.username}")
    
    
    # Вакансии пользователя: сначала «мои», затем «дополнительные» (для селектора с optgroup)
    from apps.vacancies.models import Vacancy
    main_vacancies = list(Vacancy.objects.filter(is_active=True, recruiter=request.user).order_by('name'))
    additional_vacancies = list(Vacancy.objects.filter(is_active=True, additional_recruiters=request.user).order_by('name'))
    
    # Получаем календарь компании из настроек
    company_calendar_id = None
    company_calendar_warning = None
    print(f"🔍 КАЛЕНДАРЬ КОМПАНИИ: Начинаем получение настроек...")
    try:
        from apps.company_settings.models import CompanySettings
        print(f"🔍 КАЛЕНДАРЬ КОМПАНИИ: Импорт модели успешен")
        company_settings = CompanySettings.get_settings()
        print(f"🔍 КАЛЕНДАРЬ КОМПАНИИ: Получены настройки компании, ID записи: {company_settings.id}")
        print(f"🔍 КАЛЕНДАРЬ КОМПАНИИ: main_calendar_id = '{company_settings.main_calendar_id}'")
        
        if company_settings.main_calendar_id:
            # main_calendar_id может быть ссылкой или ID, извлекаем ID
            calendar_input = company_settings.main_calendar_id.strip()
            print(f"🔍 КАЛЕНДАРЬ КОМПАНИИ: Исходное значение из настроек: '{calendar_input}'")
            
            # Проверяем, является ли это ссылкой
            is_link = 'http' in calendar_input.lower() or 'calendar.google.com' in calendar_input.lower()
            if is_link:
                print(f"🔍 КАЛЕНДАРЬ КОМПАНИИ: Обнаружена ссылка, извлекаем calendar_id...")
            
            # Извлекаем calendar_id из ссылки или используем как есть, если это уже ID
            company_calendar_id = _extract_calendar_id_from_link(calendar_input)
            
            if company_calendar_id:
                print(f"✅ КАЛЕНДАРЬ КОМПАНИИ: Извлечен calendar_id из {'ссылки' if is_link else 'значения'}: '{company_calendar_id}'")
            else:
                # Если не удалось извлечь из ссылки, возможно это уже ID
                company_calendar_id = calendar_input
                print(f"⚠️ КАЛЕНДАРЬ КОМПАНИИ: Не удалось извлечь calendar_id, используем значение как есть: '{company_calendar_id}'")
            
            print(f"✅ КАЛЕНДАРЬ КОМПАНИИ: Финальный calendar_id для использования: '{company_calendar_id}'")
        else:
            company_calendar_warning = "Календарь компании не настроен. Пожалуйста, настройте главный календарь в разделе 'Настройки компании'."
            print(f"⚠️ КАЛЕНДАРЬ КОМПАНИИ: Календарь не настроен (main_calendar_id пустой или None)")
    except ImportError as e:
        print(f"❌ КАЛЕНДАРЬ КОМПАНИИ: Ошибка импорта модели: {e}")
        import traceback
        traceback.print_exc()
        company_calendar_warning = f"Ошибка импорта модели CompanySettings: {str(e)}"
        company_settings = None
    except Exception as e:
        print(f"❌ КАЛЕНДАРЬ КОМПАНИИ: Ошибка получения настроек: {e}")
        import traceback
        traceback.print_exc()
        company_calendar_warning = f"Не удалось получить настройки календаря компании: {str(e)}"
        company_settings = None
    
    # Получаем данные о событиях календаря для JavaScript (как на странице gdata_automation)
    calendar_events_data = []
    company_calendar_events_data = []
    try:
        from apps.google_oauth.services import GoogleOAuthService, GoogleCalendarService
        import json
        from datetime import datetime, timedelta
        import pytz
        
        print(f"🔍 DEBUG CHAT: Получение событий для пользователя: {request.user.username}")
        oauth_service = GoogleOAuthService(request.user)
        oauth_account = oauth_service.get_oauth_account()
        
        if oauth_account:
            # GoogleCalendarService ожидает oauth_service (с get_credentials), не oauth_account
            calendar_service = GoogleCalendarService(oauth_service)
            
            # Всегда запрашиваем свежие события при загрузке/обновлении страницы чата,
            # чтобы слоты скринингов и интервью пересчитывались корректно (без устаревшего кэша).
            primary_events_data = calendar_service.get_events(
                calendar_id='primary', days_ahead=14, force_refresh=True
            )
            
            print(f"🔍 DEBUG CHAT: Получено {len(primary_events_data)} событий из календаря пользователя (force_refresh)")
            
            # Получаем события календаря компании, если он настроен
            company_events_data = []
            if company_calendar_id:
                print(f"🔍 КАЛЕНДАРЬ КОМПАНИИ: Начинаем получение событий для calendar_id='{company_calendar_id}'")
                try:
                    company_events_data = calendar_service.get_events(
                        calendar_id=company_calendar_id, days_ahead=14, force_refresh=True
                    )
                    print(f"✅ КАЛЕНДАРЬ КОМПАНИИ: Успешно получено {len(company_events_data)} событий из календаря компании")
                    
                    if len(company_events_data) == 0:
                        print(f"⚠️ КАЛЕНДАРЬ КОМПАНИИ: Календарь существует, но событий не найдено (возможно, календарь пустой или нет прав доступа)")
                    
                    # Подсчитываем события по датам: сегодня и следующая неделя
                    from datetime import date, timedelta
                    today = date.today()
                    next_week_start = today + timedelta(days=(7 - today.weekday()))  # Понедельник следующей недели
                    next_week_end = next_week_start + timedelta(days=6)  # Воскресенье следующей недели
                    
                    events_today = []
                    events_next_week = []
                    
                    for event_data in company_events_data:
                        try:
                            event_date = None
                            if 'dateTime' in event_data.get('start', {}):
                                event_date_str = event_data['start']['dateTime'].replace('Z', '+00:00')
                                event_date = datetime.fromisoformat(event_date_str).date()
                            elif 'date' in event_data.get('start', {}):
                                event_date = datetime.fromisoformat(event_data['start']['date']).date()
                            
                            if event_date:
                                if event_date == today:
                                    events_today.append(event_data.get('summary', 'Без названия'))
                                elif next_week_start <= event_date <= next_week_end:
                                    events_next_week.append(event_data.get('summary', 'Без названия'))
                        except Exception as e:
                            print(f"⚠️ Ошибка обработки даты события: {e}")
                    
                    print(f"📅 КАЛЕНДАРЬ КОМПАНИИ: События сегодня ({today}): {len(events_today)}")
                    if events_today:
                        for event_title in events_today:
                            print(f"   - {event_title}")
                    else:
                        print(f"   (нет событий)")
                    
                    print(f"📅 КАЛЕНДАРЬ КОМПАНИИ: События на следующей неделе ({next_week_start} - {next_week_end}): {len(events_next_week)}")
                    if events_next_week:
                        for event_title in events_next_week:
                            print(f"   - {event_title}")
                    else:
                        print(f"   (нет событий)")
                        
                except Exception as e:
                    print(f"❌ КАЛЕНДАРЬ КОМПАНИИ: ОШИБКА получения событий календаря компании: {e}")
                    print(f"❌ КАЛЕНДАРЬ КОМПАНИИ: Тип ошибки: {type(e).__name__}")
                    import traceback
                    traceback.print_exc()
                    company_calendar_warning = f"Не удалось получить события календаря компании: {str(e)}"
            else:
                print(f"⚠️ КАЛЕНДАРЬ КОМПАНИИ: company_calendar_id = None, пропускаем получение событий календаря компании")
            
            # Объединяем события: сначала primary, потом company
            events_data = list(primary_events_data)  # Копируем события пользователя
            if company_events_data:
                events_data.extend(company_events_data)
                print(f"📅 КАЛЕНДАРЬ КОМПАНИИ: Всего событий после объединения: {len(events_data)} (primary: {len(primary_events_data)}, company: {len(company_events_data)})")
            else:
                print(f"📅 КАЛЕНДАРЬ КОМПАНИИ: Используются только события primary календаря ({len(events_data)} событий)")
            
            if events_data:
                # Преобразуем данные API в формат для JavaScript (как на странице gdata_automation)
                for idx, event_data in enumerate(events_data):
                    try:
                        # Определяем источник события (календарь) на основе индекса
                        event_calendar_source = "primary (пользователь)"
                        if company_calendar_id and company_events_data:
                            # Если индекс >= количества primary событий, то это событие из календаря компании
                            primary_events_count = len(primary_events_data)
                            if idx >= primary_events_count:
                                event_calendar_source = f"company ({company_calendar_id})"
                        
                        # Получаем информацию о владельце/организаторе события
                        organizer_email = None
                        organizer_name = None
                        creator_email = None
                        if 'organizer' in event_data:
                            organizer_email = event_data['organizer'].get('email', '')
                            organizer_name = event_data['organizer'].get('displayName', '')
                        if 'creator' in event_data:
                            creator_email = event_data['creator'].get('email', '')
                        
                        # Логируем информацию о событии (в серверную консоль)
                        event_title = event_data.get('summary', 'Без названия')
                        print(f"📅 СОБЫТИЕ [{idx+1}/{len(events_data)}]: '{event_title}'")
                        print(f"   📍 Источник календаря: {event_calendar_source}")
                        if organizer_email:
                            print(f"   👤 Организатор: {organizer_email}" + (f" ({organizer_name})" if organizer_name else ""))
                        if creator_email and creator_email != organizer_email:
                            print(f"   ✏️ Создатель: {creator_email}")
                        
                        # Парсим время начала
                        start_time = None
                        if 'dateTime' in event_data['start']:
                            start_time = datetime.fromisoformat(event_data['start']['dateTime'].replace('Z', '+00:00'))
                            # Конвертируем в локальный часовой пояс Minsk
                            import pytz
                            minsk_tz = pytz.timezone('Europe/Minsk')
                            start_time = start_time.astimezone(minsk_tz)
                        elif 'date' in event_data['start']:
                            start_time = datetime.fromisoformat(event_data['start']['date'] + 'T00:00:00+00:00')
                        
                        # Парсим время окончания
                        end_time = None
                        if 'dateTime' in event_data['end']:
                            end_time = datetime.fromisoformat(event_data['end']['dateTime'].replace('Z', '+00:00'))
                            end_time = end_time.astimezone(minsk_tz)
                        elif 'date' in event_data['end']:
                            end_time = datetime.fromisoformat(event_data['end']['date'] + 'T23:59:59+00:00')
                        
                        if start_time:
                            # Очищаем description от HTML-тегов для безопасного использования в JavaScript
                            description = event_data.get('description', '')
                            if description:
                                # Удаляем HTML-теги
                                description = re.sub(r'<[^>]+>', '', description)
                                # Заменяем кавычки на безопасные символы
                                description = description.replace('"', "'").replace("'", "'")
                            
                            is_all_day_event = 'date' in event_data['start']
                            
                            # Извлекаем участников для проверки статуса ответа
                            attendees = []
                            if 'attendees' in event_data:
                                for attendee in event_data['attendees']:
                                    attendee_info = {
                                        'email': attendee.get('email', ''),
                                        'name': attendee.get('displayName', ''),
                                        'response_status': attendee.get('responseStatus', 'needsAction'),
                                        'organizer': attendee.get('organizer', False),
                                    }
                                    attendees.append(attendee_info)
                            
                            # Получаем статус события
                            event_status = event_data.get('status', 'confirmed')
                            
                            # Добавляем информацию об организаторе и источнике в данные для фронтенда
                            event_obj = {
                                'id': event_data['id'],
                                'title': event_data.get('summary', 'Без названия'),
                                'start': start_time.isoformat(),
                                'end': end_time.isoformat() if end_time else start_time.isoformat(),
                                'is_all_day': is_all_day_event,
                                'isallday': is_all_day_event,  # Для совместимости с существующим кодом
                                'location': event_data.get('location', ''),
                                'description': description,
                                'status': event_status,  # Статус события для фильтрации отклоненных
                                'attendees': attendees,  # Участники для проверки статуса ответа
                            }
                            # Добавляем метаданные для отладки в браузерной консоли
                            if organizer_email:
                                event_obj['organizer_email'] = organizer_email
                                if organizer_name:
                                    event_obj['organizer_name'] = organizer_name
                            if creator_email and creator_email != organizer_email:
                                event_obj['creator_email'] = creator_email
                            event_obj['calendar_source'] = event_calendar_source
                            calendar_events_data.append(event_obj)
                    except Exception as e:
                        print(f"Ошибка обработки события {event_data.get('id', 'unknown')}: {e}")
                        continue
                if events_data and len(calendar_events_data) == 0:
                    print(f"⚠️ DEBUG CHAT: API вернул {len(events_data)} событий, но ни одно не сконвертировалось в calendar_events_data — проверьте формат событий")
        else:
            print(f"🔍 DEBUG CHAT: У пользователя нет Google OAuth аккаунта — события календаря не загружены")
    except Exception as e:
        print(f"❌ Ошибка получения данных о событиях календаря: {e}")
        import traceback
        traceback.print_exc()
    
    # Получаем настройки слотов для пользователя
    from apps.google_oauth.models import SlotsSettings
    slots_settings = SlotsSettings.get_or_create_for_user(request.user)
    
    # Получаем фото пользователя из Google OAuth аккаунта
    user_photo_url = None
    try:
        oauth_account = request.user.google_oauth_account
        if oauth_account and oauth_account.picture_url:
            user_photo_url = oauth_account.picture_url
            print(f"🔍 DEBUG CHAT: Найдено фото пользователя: {user_photo_url}")
        else:
            print(f"🔍 DEBUG CHAT: Фото пользователя не найдено")
    except Exception as e:
        print(f"🔍 DEBUG CHAT: Ошибка получения фото пользователя: {e}")
    
    # Получаем список обязательных интервьюеров для тех. интервью
    mandatory_interviewers = []
    if vacancy and hasattr(vacancy, 'mandatory_tech_interviewers'):
        mandatory_interviewers = list(vacancy.mandatory_tech_interviewers.all())
    
    # Вычисляем слоты для скринингов и интервью
    screening_slots = []
    interview_slots = []
    
    if vacancy:
        # Получаем эффективные рабочие часы (компания -> пользователь -> по умолчанию)
        from logic.working_hours_service import get_effective_working_hours
        hours = get_effective_working_hours(request.user, company_settings)
        work_start = hours['work_start_hour']
        work_end = hours['work_end_hour']
        meeting_interval = hours['meeting_interval_minutes']
        
        print(f"🕐 НАСТРОЙКИ: Рабочие часы {work_start}:00-{work_end}:00, интервал {meeting_interval} мин")
        
        from logic.slots_calculator import SlotsCalculator
        calculator = SlotsCalculator(
            work_start_hour=work_start,
            work_end_hour=work_end,
            meeting_interval_minutes=meeting_interval
        )
        
        # Слоты для скринингов (только календарь пользователя)
        screening_duration = None
        if hasattr(vacancy, 'screening_duration') and vacancy.screening_duration:
            screening_duration = vacancy.screening_duration
        else:
            screening_duration = 45
        
        print(f"📅 СЛОТЫ СКРИНИНГОВ: Начинаем поиск доступных слотов")
        print(f"📅 СЛОТЫ СКРИНИНГОВ: Длительность встречи: {screening_duration} минут")
        print(f"📅 СЛОТЫ СКРИНИНГОВ: События календаря: {len(calendar_events_data)}")
        if company_calendar_id:
            print(f"📅 СЛОТЫ СКРИНИНГОВ: Используются календари: пользователь {request.user.email} + компания ({company_calendar_id})")
        else:
            print(f"📅 СЛОТЫ СКРИНИНГОВ: Используется календарь пользователя {request.user.email} (календарь компании не настроен)")
        
        # Настройка: игнорировать не принятые встречи (ДА = слот занят при любом ответе кроме declined; НЕТ = слот занят только при accepted)
        try:
            from apps.company_settings.models import CompanySettings
            _cs = CompanySettings.get_settings()
            ignore_non_accepted_meetings = bool(getattr(_cs, 'ignore_non_accepted_meetings', True))
        except Exception:
            ignore_non_accepted_meetings = True
        
        current_user_email_lower = (request.user.email or '').strip().lower() or None
        # Принудительное обновление (force_refresh_slots задан в начале view): не использовать кэш слотов, пересчитать и обновить кэш
        from apps.google_oauth.cache_service import GoogleAPICache
        cached_both = None
        if not force_refresh_slots:
            cached_both = GoogleAPICache.get_slot_events_both_variants(
                request.user.id, scope='chat_workflow_14', days_ahead=14
            )
        if force_refresh_slots:
            print(f"📅 СЛОТЫ: Принудительное обновление (refresh_slots/force_refresh), кэш не используем")
        if cached_both and isinstance(cached_both, dict):
            base_list = (cached_both.get('ignore_non_accepted') or []) if ignore_non_accepted_meetings else (cached_both.get('consider_non_accepted') or [])
            screening_events_for_calc = list(base_list) if isinstance(base_list, list) else []
            interview_events_for_calc = list(screening_events_for_calc)
            print(f"📅 СЛОТЫ: Использованы оба варианта из кэша (ignore={ignore_non_accepted_meetings}), событий: {len(screening_events_for_calc)}")
        else:
            both = _build_slot_events_both_variants(calendar_events_data, current_user_email_lower)
            events_for_calc = list(both['ignore_non_accepted'] if ignore_non_accepted_meetings else both['consider_non_accepted'])
            screening_events_for_calc = events_for_calc
            interview_events_for_calc = list(events_for_calc)
            try:
                GoogleAPICache.set_slot_events_both_variants(
                    request.user.id,
                    {'ignore_non_accepted': list(both['ignore_non_accepted']), 'consider_non_accepted': list(both['consider_non_accepted'])},
                    scope='chat_workflow_14',
                    days_ahead=14,
                )
                print(f"📅 СЛОТЫ: Сохранены оба варианта в кэш (ignore: {len(both['ignore_non_accepted'])}, consider: {len(both['consider_non_accepted'])})")
            except Exception as e:
                print(f"⚠️ СЛОТЫ: Ошибка записи кэша слотов: {e}")
        
        print(f"📅 СЛОТЫ СКРИНИНГОВ: Подготовлено {len(screening_events_for_calc)} событий для расчета (пользователь + компания)")
        print(f"📅 СЛОТЫ СКРИНИНГОВ: Из них событий календаря компании: {len([e for e in calendar_events_data if e.get('calendar_source', '').startswith('company')])}")
        
        screening_slots = calculator.calculate_slots_for_two_weeks(
            screening_events_for_calc, 
            required_duration_minutes=screening_duration
        )
        
        print(f"📅 СЛОТЫ СКРИНИНГОВ: Рассчитано {len(screening_slots)} дней со слотами")
        
        print(f"📅 СЛОТЫ ИНТЕРВЬЮ: Начинаем поиск доступных слотов")
        print(f"📅 СЛОТЫ ИНТЕРВЬЮ: Базовые события от пользователя и компании: {len(interview_events_for_calc)}")
        print(f"📅 СЛОТЫ ИНТЕРВЬЮ: Из них событий календаря компании: {len([e for e in calendar_events_data if e.get('calendar_source', '').startswith('company')])}")
        
        # ВАЖНО: При загрузке страницы НЕ добавляем события интервьюеров
        # Слоты для интервью будут рассчитываться динамически через API
        # на основе выбранных участников (через JavaScript)
        # Это позволяет показывать слоты только для выбранных интервьюеров
        print(f"📅 СЛОТЫ ИНТЕРВЬЮ: Пропускаем добавление событий интервьюеров при загрузке страницы")
        print(f"📅 СЛОТЫ ИНТЕРВЬЮ: Слоты будут обновлены через API на основе выбранных участников")
        
        # Рассчитываем слоты для интервью только на основе событий пользователя и компании
        # JavaScript обновит их для выбранных участников
        interview_duration = None
        if hasattr(vacancy, 'tech_interview_duration') and vacancy.tech_interview_duration:
            interview_duration = vacancy.tech_interview_duration
        else:
            interview_duration = 90
        
        print(f"📅 СЛОТЫ ИНТЕРВЬЮ: Длительность встречи: {interview_duration} минут")
        print(f"📅 СЛОТЫ ИНТЕРВЬЮ: Рассчитываем базовые слоты (без интервьюеров) - будут обновлены через API")
        
        # Рассчитываем базовые слоты только для пользователя и компании
        # JavaScript обновит их для выбранных участников при загрузке страницы
        interview_slots = calculator.calculate_slots_for_two_weeks(
            interview_events_for_calc,
            required_duration_minutes=interview_duration
        )
        
        print(f"📅 СЛОТЫ ИНТЕРВЬЮ: Рассчитано {len(interview_slots)} дней со слотами (базовые, без интервьюеров)")
    
    # Получаем интервьюеров для технического интервью из обязательных участников
    vacancy_interviewers = []
    if vacancy:
        vacancy_interviewers = vacancy.mandatory_tech_interviewers.filter(is_active=True).order_by('last_name', 'first_name')
    
    # Получаем быстрые кнопки пользователя
    from apps.accounts.models import QuickButton
    quick_buttons = QuickButton.objects.filter(user=request.user).order_by('order', 'created_at')
    
    # Получаем ссылки на соцсети и контактную информацию из последнего HR-скрининга или инвайта
    candidate_social_links = {}
    candidate_contact_info = {}
    try:
        from apps.huntflow.services import HuntflowService
        
        # Ищем последний HR-скрининг или инвайт в сообщениях
        candidate_id = None
        
        # Проверяем последние сообщения с HR-скринингом или инвайтом
        for msg in reversed(messages_list):
            if msg.message_type == 'hrscreening' and msg.hr_screening:
                if msg.hr_screening.candidate_id:
                    candidate_id = msg.hr_screening.candidate_id
                    print(f"🔍 CANDIDATE_SOCIAL_LINKS: Найден candidate_id из HR-скрининга: {candidate_id}")
                    break
            elif msg.message_type == 'invite' and msg.invite:
                if msg.invite.candidate_id:
                    candidate_id = msg.invite.candidate_id
                    print(f"🔍 CANDIDATE_SOCIAL_LINKS: Найден candidate_id из инвайта: {candidate_id}")
                    break
        
        if candidate_id:
            # Получаем данные кандидата из Huntflow API
            huntflow_service = HuntflowService(request.user)
            accounts = huntflow_service.get_accounts()
            
            if accounts and 'items' in accounts and accounts['items']:
                account_id = accounts['items'][0]['id']
                print(f"🔍 CANDIDATE_SOCIAL_LINKS: Используем account_id: {account_id}, candidate_id: {candidate_id}")
                candidate_data = huntflow_service.get_applicant(account_id, int(candidate_id))
                
                if candidate_data:
                    print(f"🔍 CANDIDATE_SOCIAL_LINKS: Получены данные кандидата, social: {candidate_data.get('social', [])}")
                    # Извлекаем социальные сети из поля social
                    social = candidate_data.get('social', [])
                    for soc in social:
                        # В Huntflow API используется поле social_type
                        soc_type = (soc.get('social_type', '') or soc.get('type', '') or '').upper()
                        soc_value = soc.get('value', '') or soc.get('url', '') or ''
                        
                        if not soc_value:
                            continue
                        
                        print(f"🔍 CANDIDATE_SOCIAL_LINKS: Обрабатываем соцсеть: type={soc_type}, value={soc_value}")
                        
                        # Telegram
                        if soc_type == 'TELEGRAM' or 'TELEGRAM' in soc_type:
                            # Убираем @ если есть
                            telegram_value = soc_value.lstrip('@')
                            candidate_social_links['telegram'] = telegram_value
                            print(f"✅ CANDIDATE_SOCIAL_LINKS: Добавлен Telegram: {telegram_value}")
                        # WhatsApp
                        elif soc_type == 'WHATSAPP' or 'WHATSAPP' in soc_type:
                            candidate_social_links['whatsapp'] = soc_value
                            print(f"✅ CANDIDATE_SOCIAL_LINKS: Добавлен WhatsApp: {soc_value}")
                        # Viber
                        elif soc_type == 'VIBER' or 'VIBER' in soc_type:
                            candidate_social_links['viber'] = soc_value
                            print(f"✅ CANDIDATE_SOCIAL_LINKS: Добавлен Viber: {soc_value}")
                        # LinkedIn
                        elif soc_type == 'LINKEDIN' or 'LINKEDIN' in soc_type:
                            candidate_social_links['linkedin'] = soc_value
                            print(f"✅ CANDIDATE_SOCIAL_LINKS: Добавлен LinkedIn: {soc_value}")
                    
                    # Также проверяем questionary на наличие LinkedIn
                    if 'linkedin' not in candidate_social_links:
                        print(f"🔍 CANDIDATE_SOCIAL_LINKS: LinkedIn не найден в social, проверяем questionary")
                        questionary = huntflow_service.get_applicant_questionary(account_id, int(candidate_id))
                        if questionary:
                            print(f"🔍 CANDIDATE_SOCIAL_LINKS: Получена анкета, поля: {list(questionary.keys())}")
                            # Получаем схему для понимания названий полей
                            questionary_schema = huntflow_service.get_applicant_questionary_schema(account_id)
                            # Ищем LinkedIn в значениях questionary
                            for field_key, field_value in questionary.items():
                                if field_value and isinstance(field_value, str):
                                    field_title = ""
                                    if questionary_schema and field_key in questionary_schema:
                                        field_title = questionary_schema[field_key].get('title', '')
                                    # Проверяем, содержит ли значение LinkedIn URL
                                    if 'linkedin.com' in field_value.lower():
                                        linkedin_value = field_value if 'http' in field_value.lower() else f"https://{field_value}"
                                        candidate_social_links['linkedin'] = linkedin_value
                                        print(f"✅ CANDIDATE_SOCIAL_LINKS: Добавлен LinkedIn из questionary (поле {field_key} '{field_title}'): {linkedin_value}")
                                        break
                                    # Также логируем все поля для отладки
                                    if 'linkedin' in field_value.lower() or 'linkedin' in field_title.lower():
                                        print(f"🔍 CANDIDATE_SOCIAL_LINKS: Найдено похожее поле: {field_key} '{field_title}' = {field_value[:100]}")
                    # ФИО кандидата для отображения на кнопках (например, Viber)
                    name_parts = [
                        candidate_data.get('last_name', ''),
                        candidate_data.get('first_name', ''),
                        candidate_data.get('middle_name', ''),
                    ]
                    candidate_social_links['candidate_name'] = ' '.join(p for p in name_parts if p).strip() or candidate_data.get('name', '') or ''
                else:
                    print(f"⚠️ CANDIDATE_SOCIAL_LINKS: Данные кандидата не получены из Huntflow API")
            else:
                print(f"⚠️ CANDIDATE_SOCIAL_LINKS: Нет доступных аккаунтов Huntflow")
        else:
            print(f"⚠️ CANDIDATE_SOCIAL_LINKS: candidate_id не найден в последних HR-скринингах или инвайтах")
    except Exception as e:
        import traceback
        print(f"⚠️ Ошибка получения ссылок на соцсети: {e}")
        print(f"⚠️ Traceback: {traceback.format_exc()}")
    
    print(f"🔍 CANDIDATE_SOCIAL_LINKS: Итоговые ссылки: {candidate_social_links}")
    
    # Получаем полную контактную информацию кандидата
    if candidate_id:
        candidate_contact_info = _get_candidate_contact_info(request.user, candidate_id)
        print(f"🔍 CANDIDATE_CONTACT_INFO: Получена контактная информация: {candidate_contact_info}")
        
        # Объединяем данные из candidate_social_links и candidate_contact_info
        if candidate_contact_info.get('telegram'):
            candidate_social_links['telegram'] = candidate_contact_info['telegram']
        if candidate_contact_info.get('linkedin'):
            candidate_social_links['linkedin'] = candidate_contact_info['linkedin']
        if candidate_contact_info.get('email'):
            candidate_social_links['email'] = candidate_contact_info['email']
        if candidate_contact_info.get('communication_where'):
            candidate_social_links['communication_where'] = candidate_contact_info['communication_where']
    
    # Получаем историю контактной информации из сообщений сессии
    contact_history = []
    try:
        # Получаем все сообщения с контактной информацией (hrscreening, invite и add_candidate)
        # Для add_candidate ищем по metadata.action_type, так как message_type='system'
        from django.db.models import Q
        
        messages_with_contacts = ChatMessage.objects.filter(
            session=chat_session
        ).filter(
            Q(message_type__in=['hrscreening', 'invite']) |
            Q(message_type='system', metadata__action_type='add_candidate')
        ).order_by('-created_at')[:50]  # Берем последние 50
        
        for msg in messages_with_contacts:
            contact_info = msg.metadata.get('candidate_contact_info', {}) if msg.metadata else {}
            if contact_info and (contact_info.get('communication_where') or 
                                contact_info.get('telegram') or 
                                contact_info.get('linkedin') or 
                                contact_info.get('email')):
                contact_history.append({
                    'timestamp': msg.created_at.isoformat(),
                    'communication_where': contact_info.get('communication_where'),
                    'telegram': contact_info.get('telegram'),
                    'linkedin': contact_info.get('linkedin'),
                    'email': contact_info.get('email')
                })
        
        print(f"🔍 CONTACT_HISTORY: Получено {len(contact_history)} записей истории контактов")
    except Exception as e:
        print(f"⚠️ CONTACT_HISTORY: Ошибка получения истории: {e}")
        import traceback
        traceback.print_exc()
    
    # Сериализуем историю в JSON для передачи в шаблон
    import json
    contact_history_json = json.dumps(contact_history, ensure_ascii=False, default=str)
    print(f"🔍 CONTACT_HISTORY: JSON длина: {len(contact_history_json)} символов")
    
    # Загружаем данные по скринингам и интервью из БД для текущей вакансии
    screenings_data = []
    interviews_data = []
    try:
        from apps.google_oauth.models import HRScreening, Invite
        from datetime import datetime, timedelta
        
        # Получаем вакансию по external_id для фильтрации
        vacancy_external_id = None
        if vacancy and hasattr(vacancy, 'external_id'):
            vacancy_external_id = str(vacancy.external_id)
        
        # Загружаем скрининги за последние 30 дней
        if vacancy_external_id:
            screenings = HRScreening.objects.filter(
                vacancy_id=vacancy_external_id,
                created_at__gte=datetime.now() - timedelta(days=30)
            ).order_by('-created_at')[:50]  # Берем последние 50
            
            for screening in screenings:
                screenings_data.append({
                    'id': screening.id,
                    'candidate_name': screening.candidate_name or 'Не указан',
                    'candidate_id': screening.candidate_id,
                    'created_at': screening.created_at.isoformat() if screening.created_at else None,
                    'status': getattr(screening, 'status', None),  # поле status может отсутствовать в модели
                    'score': getattr(screening, 'score', None),
                })
            
            print(f"🔍 SCREENINGS_DATA: Загружено {len(screenings_data)} скринингов для вакансии {vacancy_external_id}")
        
        # Загружаем интервью (инвайты) за последние 30 дней
        if vacancy_external_id:
            invites = Invite.objects.filter(
                vacancy_id=vacancy_external_id,
                created_at__gte=datetime.now() - timedelta(days=30)
            ).order_by('-created_at')[:50]  # Берем последние 50
            
            for invite in invites:
                # Определяем тип события (скрининг или интервью)
                event_type = 'interview' if not invite.google_drive_file_id else 'screening'
                
                interviews_data.append({
                    'id': invite.id,
                    'candidate_name': invite.candidate_name or 'Не указан',
                    'candidate_id': invite.candidate_id,
                    'interview_datetime': invite.interview_datetime.isoformat() if invite.interview_datetime else None,
                    'status': invite.status,
                    'event_type': event_type,
                    'calendar_event_id': invite.calendar_event_id,
                    'interviewer_name': invite.interviewer.get_full_name() if invite.interviewer else None,
                    'created_at': invite.created_at.isoformat() if invite.created_at else None,
                })
            
            print(f"🔍 INTERVIEWS_DATA: Загружено {len(interviews_data)} интервью/скринингов для вакансии {vacancy_external_id}")
        
    except Exception as e:
        print(f"⚠️ Ошибка загрузки данных по скринингам и интервью: {e}")
        import traceback
        traceback.print_exc()
    
    # Получаем email текущего пользователя для фильтрации отклоненных событий
    current_user_email = request.user.email.lower() if request.user.email else None
    
    context = {
        'form': form,
        'chat_session': chat_session,
        'messages': messages_list,  # Используем messages_list, который обновлен через refresh_from_db
        'main_vacancies': main_vacancies,
        'additional_vacancies': additional_vacancies,
        'selected_vacancy': vacancy,
        'timestamp': int(time()),
        'contact_history': contact_history_json,  # Передаем JSON-строку для шаблона
        'calendar_events_data': calendar_events_data,
        'slots_settings': slots_settings,
        'slots_settings_json': json.dumps(slots_settings.to_dict()) if slots_settings else '{}',
        'user_photo_url': user_photo_url,
        'user_email': current_user_email,  # Email пользователя для фильтрации отклоненных событий
        'mandatory_interviewers': mandatory_interviewers,
        'vacancy_interviewers': vacancy_interviewers,
        'screening_slots_json': json.dumps(screening_slots),
        'interview_slots_json': json.dumps(interview_slots),
        'company_calendar_id': company_calendar_id,
        'company_calendar_warning': company_calendar_warning,
        'title': 'Чат-помощник',
        'quick_buttons': quick_buttons,
        'candidate_social_links': candidate_social_links,
        'candidate_contact_info': candidate_contact_info,
        'contact_history': contact_history_json,
        'screenings_data': json.dumps(screenings_data, ensure_ascii=False, default=str),
        'interviews_data': json.dumps(interviews_data, ensure_ascii=False, default=str),
    }

    # Метаданные для кнопки «Обновить слоты»: по каждой вакансии — список ID интервьюеров (обязательные + все по вакансии)
    all_vacancies_for_slots = list(main_vacancies) + list(additional_vacancies)
    all_vacancies_slots_meta = []
    for v in all_vacancies_for_slots:
        interviewer_ids = set()
        if hasattr(v, 'mandatory_tech_interviewers'):
            interviewer_ids.update(v.mandatory_tech_interviewers.filter(is_active=True).values_list('id', flat=True))
        if hasattr(v, 'interviewers'):
            interviewer_ids.update(v.interviewers.filter(is_active=True).values_list('id', flat=True))
        all_vacancies_slots_meta.append({
            'id': v.id,
            'name': getattr(v, 'name', ''),
            'interviewer_ids': list(interviewer_ids),
        })
    context['all_vacancies_slots_meta_json'] = json.dumps(all_vacancies_slots_meta)

    # Отладочная информация (как на странице gdata_automation)
    print(f"🔍 DEBUG CHAT: Передаем {len(calendar_events_data)} событий в шаблон")
    for event in calendar_events_data[:3]:  # Показываем первые 3 события
        print(f"🔍 DEBUG CHAT: Событие: {event['title']} в {event['start']}")

    # После принудительного обновления слотов убираем refresh_slots из URL (редирект на тот же путь без параметра)
    if force_refresh_slots:
        from django.http import HttpResponseRedirect
        q = request.GET.copy()
        q.pop('refresh_slots', None)
        q.pop('force_refresh', None)
        redirect_url = request.path + ('?' + q.urlencode() if q else '')
        return HttpResponseRedirect(redirect_url)

    return render(request, 'google_oauth/chat_workflow.html', context)


def delete_last_action(chat_session, user):
    """
    Удаляет последнее действие в чате с полной очисткой данных
    
    Args:
        chat_session: Сессия чата
        user: Пользователь
    
    Returns:
        dict: Результат операции с информацией об удаленном действии
    """
    try:
        from .models import ChatMessage, HRScreening, Invite
        
        print(f"🗑️ DELETE_LAST_ACTION: Начинаем удаление последнего действия в сессии {chat_session.id}")
        
        # Находим последнее действие (не пользовательское сообщение)
        last_action = ChatMessage.objects.filter(
            session=chat_session,
            message_type__in=['hrscreening', 'invite']
        ).order_by('-created_at').first()
        
        if not last_action:
            return {
                'success': False,
                'message': 'В чате нет действий для удаления'
            }
        
        print(f"🗑️ DELETE_LAST_ACTION: Найдено последнее действие: {last_action.message_type} (ID: {last_action.id})")
        
        result = {
            'success': True,
            'action_type': last_action.message_type,
            'deleted_object_id': None,
            'candidate_name': last_action.metadata.get('candidate_name'),
            'vacancy_name': last_action.metadata.get('vacancy_name'),
            'huntflow_candidate_url': None,
            'changes': []
        }
        
        # Удаляем объект в зависимости от типа действия
        if last_action.message_type == 'hrscreening' and last_action.hr_screening:
            hr_screening = last_action.hr_screening
            result['deleted_object_id'] = hr_screening.id
            
            # Формируем ссылку на кандидата в Huntflow
            result['huntflow_candidate_url'] = f"https://huntflow.ru/applicants/{hr_screening.candidate_id}"
            
            print(f"🗑️ DELETE_LAST_ACTION: Удаляем HR-скрининг ID: {hr_screening.id}")
            
            # ВОССТАНАВЛИВАЕМ СОСТОЯНИЕ ИЗ СНИМКА
            try:
                from apps.huntflow.services import HuntflowService
                from .state_snapshot_service import snapshot_service
                
                huntflow_service = HuntflowService(user)
                
                # Получаем account_id
                accounts = huntflow_service.get_accounts()
                if accounts and accounts.get('items'):
                    account_id = accounts['items'][0]['id']
                    
                    # Получаем снимок состояния
                    snapshot = snapshot_service.get_candidate_snapshot(
                        user.id, 
                        hr_screening.candidate_id, 
                        'hrscreening'
                    )
                    
                    if snapshot:
                        print(f"📸 DELETE_LAST_ACTION: Восстанавливаем состояние из снимка")
                        
                        # Восстанавливаем основные поля кандидата
                        candidate_basic = snapshot.get('candidate_basic', {})
                        if candidate_basic:
                            # Убираем поля, которые не должны обновляться
                            restore_data = {k: v for k, v in candidate_basic.items() 
                                          if k in ['money', 'phone', 'email', 'first_name', 'last_name']}
                            if restore_data:
                                huntflow_service.update_applicant(account_id, int(hr_screening.candidate_id), restore_data)
                                print(f"📸 DELETE_LAST_ACTION: Основные поля восстановлены")
                        
                        # Восстанавливаем дополнительные поля (questionary)
                        candidate_questionary = snapshot.get('candidate_questionary', {})
                        if candidate_questionary:
                            huntflow_service.update_applicant_questionary(account_id, int(hr_screening.candidate_id), candidate_questionary)
                            print(f"📸 DELETE_LAST_ACTION: Дополнительные поля восстановлены")
                        
                        # Восстанавливаем статус кандидата
                        candidate_status = snapshot.get('candidate_status', {})
                        if candidate_status and candidate_status.get('status_id'):
                            huntflow_service.update_applicant_status(
                                account_id=account_id,
                                applicant_id=int(hr_screening.candidate_id),
                                status_id=candidate_status['status_id'],
                                comment="Восстановлено после отмены HR-скрининга",
                                vacancy_id=int(hr_screening.vacancy_id) if hr_screening.vacancy_id else None
                            )
                            print(f"📸 DELETE_LAST_ACTION: Статус восстановлен: {candidate_status['status_id']}")
                        
                        # Удаляем снимок после восстановления
                        snapshot_service.delete_candidate_snapshot(
                            user.id, 
                            hr_screening.candidate_id, 
                            'hrscreening'
                        )
                        print(f"🗑️ DELETE_LAST_ACTION: Снимок удален после восстановления")
                        
                        # Добавляем изменения в список
                        result['changes'].extend([
                            "Восстановлены основные поля кандидата",
                            "Восстановлены дополнительные поля (questionary)",
                            "Восстановлен предыдущий статус кандидата",
                            "Удален снимок состояния"
                        ])
                        
                    else:
                        print(f"⚠️ DELETE_LAST_ACTION: Снимок не найден, используем fallback")
                        # Fallback: возвращаем на статус "Contact"
                        statuses = huntflow_service.get_vacancy_statuses(account_id)
                        if statuses and 'items' in statuses:
                            previous_status_id = None
                            for status in statuses['items']:
                                if status.get('name', '').lower() == 'contact':
                                    previous_status_id = status.get('id')
                                    break
                            
                            if previous_status_id:
                                huntflow_service.update_applicant_status(
                                    account_id=account_id,
                                    applicant_id=int(hr_screening.candidate_id),
                                    status_id=previous_status_id,
                                    comment="Отменен HR-скрининг (fallback)",
                                    vacancy_id=int(hr_screening.vacancy_id) if hr_screening.vacancy_id else None
                                )
                                print(f"🗑️ DELETE_LAST_ACTION: Статус возвращен на Contact (fallback)")
                                result['changes'].append("Статус возвращен на Contact (fallback)")
            except Exception as e:
                print(f"⚠️ DELETE_LAST_ACTION: Ошибка восстановления состояния: {e}")
                result['changes'].append(f"Ошибка восстановления состояния: {str(e)}")
            
            # Удаляем HR-скрининг из базы данных
            hr_screening.delete()
            result['changes'].append("HR-скрининг удален из базы данных")
            print(f"🗑️ DELETE_LAST_ACTION: HR-скрининг удален из базы данных")
            
        elif last_action.message_type == 'invite' and last_action.invite:
            invite = last_action.invite
            result['deleted_object_id'] = invite.id
            
            # Формируем ссылку на кандидата в Huntflow
            result['huntflow_candidate_url'] = f"https://huntflow.ru/applicants/{invite.candidate_id}"
            
            print(f"🗑️ DELETE_LAST_ACTION: Удаляем инвайт ID: {invite.id}")
            
            # Удаляем календарное событие
            try:
                if invite.google_calendar_event_id:
                    from apps.google_oauth.services import GoogleCalendarService, GoogleOAuthService
                    oauth_service = GoogleOAuthService(user)
                    calendar_service = GoogleCalendarService(oauth_service)
                    calendar_service.delete_event(invite.google_calendar_event_id)
                    result['changes'].append("Календарное событие удалено")
                    print(f"🗑️ DELETE_LAST_ACTION: Календарное событие удалено")
            except Exception as e:
                print(f"⚠️ DELETE_LAST_ACTION: Ошибка удаления календарного события: {e}")
                result['changes'].append(f"Ошибка удаления календарного события: {str(e)}")
            
            # Удаляем файл scorecard из Google Drive
            try:
                if invite.google_drive_file_id:
                    from apps.google_oauth.services import GoogleDriveService, GoogleOAuthService
                    oauth_service = GoogleOAuthService(user)
                    drive_service = GoogleDriveService(oauth_service)
                    drive_service.delete_file(invite.google_drive_file_id)
                    result['changes'].append("Scorecard удален из Google Drive")
                    print(f"🗑️ DELETE_LAST_ACTION: Scorecard удален из Google Drive")
            except Exception as e:
                print(f"⚠️ DELETE_LAST_ACTION: Ошибка удаления scorecard: {e}")
                result['changes'].append(f"Ошибка удаления scorecard: {str(e)}")
            
            # Отменяем изменения в Huntflow (возвращаем предыдущий статус)
            try:
                from apps.huntflow.services import HuntflowService
                huntflow_service = HuntflowService(user)
                
                # Получаем account_id
                accounts = huntflow_service.get_accounts()
                if accounts and accounts.get('items'):
                    account_id = accounts['items'][0]['id']
                    
                    # Получаем статусы вакансий для поиска предыдущего статуса
                    statuses = huntflow_service.get_vacancy_statuses(account_id)
                    if statuses and 'items' in statuses:
                        # Ищем статус "Contact" как предыдущий для Tech Screening
                        previous_status_id = None
                        for status in statuses['items']:
                            if status.get('name', '').lower() == 'contact':
                                previous_status_id = status.get('id')
                                break
                        
                        if previous_status_id:
                            # Возвращаем кандидата на предыдущий статус
                            huntflow_service.update_applicant_status(
                                account_id=account_id,
                                applicant_id=int(invite.candidate_id),
                                status_id=previous_status_id,
                                comment="Отменен инвайт",
                                vacancy_id=int(invite.vacancy_id) if invite.vacancy_id else None
                            )
                            result['changes'].append("Статус кандидата возвращен на Contact")
                            print(f"🗑️ DELETE_LAST_ACTION: Статус кандидата возвращен на Contact")
            except Exception as e:
                print(f"⚠️ DELETE_LAST_ACTION: Ошибка отмены статуса в Huntflow: {e}")
                result['changes'].append(f"Ошибка отмены статуса в Huntflow: {str(e)}")
            
            # Удаляем инвайт из базы данных
            invite.delete()
            result['changes'].append("Инвайт удален из базы данных")
            print(f"🗑️ DELETE_LAST_ACTION: Инвайт удален из базы данных")
        
        # Удаляем сообщение о действии из чата
        last_action.delete()
        result['changes'].append("Сообщение о действии удалено из чата")
        print(f"🗑️ DELETE_LAST_ACTION: Сообщение о действии удалено из чата")
        
        print(f"✅ DELETE_LAST_ACTION: Удаление завершено успешно")
        return result
        
    except Exception as e:
        print(f"❌ DELETE_LAST_ACTION: Ошибка при удалении: {e}")
        import traceback
        traceback.print_exc()
        return {
            'success': False,
            'message': f'Ошибка при удалении: {str(e)}'
        }


@login_required
@permission_required('google_oauth.change_chatsession', raise_exception=True)
@require_POST
def update_chat_title(request, session_id):
    """Обновление названия чат-сессии"""
    from .models import ChatSession
    from .forms import ChatSessionTitleForm
    
    try:
        chat_session = ChatSession.objects.get(id=session_id, user=request.user)
    except ChatSession.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Сессия не найдена'})
    
    form = ChatSessionTitleForm(request.POST, instance=chat_session)
    if form.is_valid():
        form.save()
        return JsonResponse({
            'success': True, 
            'title': chat_session.title or f'Чат #{chat_session.id}'
        })
    else:
        return JsonResponse({
            'success': False, 
            'error': 'Ошибка валидации формы'
        })

