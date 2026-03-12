from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.template.loader import render_to_string
import json

from .models import GoogleOAuthAccount, ScorecardPathSettings, SlotsSettings, ChatSession, ChatMessage
from apps.vacancies.models import Vacancy
from .models import Invite


@login_required
def chat_workflow_new(request, vacancy_id=None):
    """
    Новая страница чата с чистой архитектурой
    """
    user = request.user
    
    # Получаем или создаем сессию чата
    chat_session, created = ChatSession.objects.get_or_create(
        user=user,
        defaults={'is_active': True}
    )
    
    # Получаем выбранную вакансию
    selected_vacancy = None
    if vacancy_id:
        try:
            selected_vacancy = Vacancy.objects.get(id=vacancy_id)
        except Vacancy.DoesNotExist:
            pass
    
    # Получаем настройки слотов
    slots_settings, _ = SlotsSettings.objects.get_or_create(
        user=user,
        defaults={
            'work_start_hour': 11,
            'work_end_hour': 18,
            'meeting_interval_minutes': 15,
            'meeting_duration_minutes': 60
        }
    )
    
    # Получаем события календаря (заглушка для начала)
    calendar_events_data = []
    
    # Получаем сообщения чата
    messages = ChatMessage.objects.filter(session=chat_session).order_by('created_at')
    
    context = {
        'user': user,
        'chat_session': chat_session,
        'selected_vacancy': selected_vacancy,
        'slots_settings': slots_settings,
        'calendar_events_data': json.dumps(calendar_events_data),
        'messages': messages,
    }
    
    return render(request, 'google_oauth/chat_workflow_new.html', context)


@csrf_exempt
@require_http_methods(["POST"])
def chat_ajax_handler_new(request, session_id):
    """
    Обработчик AJAX запросов для нового чата
    """
    try:
        data = json.loads(request.body)
        action_type = data.get('action_type', 'hrscreening')
        text = data.get('text', '')
        session_id = data.get('session_id', session_id)
        
        print(f"🔄 [NEW CHAT AJAX] Получен запрос: {action_type} - {text}")
        
        # Получаем сессию чата
        try:
            chat_session = ChatSession.objects.get(id=session_id)
        except ChatSession.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Сессия чата не найдена'})
        
        # Создаем сообщение пользователя
        user_message = ChatMessage.objects.create(
            session=chat_session,
            message_type='user',
            content=text,
            metadata={'action_type': action_type}
        )
        
        print(f"✅ [NEW CHAT AJAX] Создано сообщение пользователя: {user_message.id}")
        
        # Создаем ответное сообщение
        response_content = f"Получено сообщение типа '{action_type}': {text}"
        
        response_message = ChatMessage.objects.create(
            session=chat_session,
            message_type='system',
            content=response_content,
            metadata={'action_type': action_type}
        )
        
        print(f"✅ [NEW CHAT AJAX] Создано ответное сообщение: {response_message.id}")
        
        # Рендерим HTML для ответного сообщения
        message_html = render_to_string('google_oauth/partials/chat_message.html', {
            'message': response_message
        })
        
        print(f"✅ [NEW CHAT AJAX] HTML сгенерирован, длина: {len(message_html)}")
        
        return JsonResponse({
            'success': True,
            'message_html': message_html,
            'message_id': response_message.id
        })
        
    except Exception as e:
        print(f"❌ [NEW CHAT AJAX] Ошибка: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': f'Ошибка обработки: {str(e)}'
        })
