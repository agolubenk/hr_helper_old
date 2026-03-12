"""
Библиотека ответов: справочник тем/триггеров/примеров и чат с ИИ.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods, require_POST, require_GET
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.urls import reverse
import json
import logging

from django.db.models import Q

from .models import TriggerTopic, AnswerLibrarySession, AnswerLibraryMessage
from .services import (
    get_matching_topics,
    build_context_blocks,
    build_unified_message,
    build_prompt_for_gemini,
)

logger = logging.getLogger(__name__)


# ——— Справочник (темы, триггеры, примеры) ———

@login_required
def topic_list(request):
    """Список тем справочника."""
    topics = TriggerTopic.objects.all().order_by('order', 'title')
    return render(request, 'answer_library/topic_list.html', {'topics': topics})


@login_required
def topic_create(request):
    """Создание темы."""
    from .forms import TriggerTopicForm
    if request.method == 'POST':
        form = TriggerTopicForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Тема добавлена.')
            return redirect('answer_library:topic_list')
    else:
        form = TriggerTopicForm()
    return render(request, 'answer_library/topic_form.html', {'form': form, 'title': 'Добавить тему'})


@login_required
def topic_edit(request, pk):
    """Редактирование темы."""
    from .forms import TriggerTopicForm
    topic = get_object_or_404(TriggerTopic, pk=pk)
    if request.method == 'POST':
        form = TriggerTopicForm(request.POST, instance=topic)
        if form.is_valid():
            form.save()
            messages.success(request, 'Тема сохранена.')
            return redirect('answer_library:topic_list')
    else:
        form = TriggerTopicForm(instance=topic)
    return render(request, 'answer_library/topic_form.html', {'form': form, 'topic': topic, 'title': 'Редактировать тему'})


@login_required
@require_POST
def topic_delete(request, pk):
    """Удаление темы."""
    topic = get_object_or_404(TriggerTopic, pk=pk)
    topic.delete()
    messages.success(request, 'Тема удалена.')
    return redirect('answer_library:topic_list')


# ——— Импорт / экспорт библиотеки (JSON) ———

def _topic_to_dict(topic):
    """Сериализация темы для JSON (без id, created_at, updated_at)."""
    return {
        'title': topic.title,
        'trigger_words': topic.trigger_words or '',
        'example_answer': topic.example_answer or '',
        'extra_data': topic.extra_data or '',
        'order': topic.order,
        'is_active': topic.is_active,
        'vacancy_id': topic.vacancy_id,
    }


@login_required
@require_GET
def topic_export_json(request):
    """Экспорт всей библиотеки тем в JSON."""
    topics = TriggerTopic.objects.all().order_by('order', 'title').select_related('vacancy')
    data = {
        'version': 1,
        'exported_at': timezone.now().isoformat(),
        'topics': [_topic_to_dict(t) for t in topics],
    }
    response = HttpResponse(
        json.dumps(data, ensure_ascii=False, indent=2),
        content_type='application/json; charset=utf-8',
    )
    response['Content-Disposition'] = 'attachment; filename="answer_library_topics.json"'
    return response


@login_required
@require_http_methods(["POST"])
def topic_import_json(request):
    """Импорт библиотеки тем из JSON (файл в поле 'file' или raw body)."""
    is_form_upload = bool(request.FILES.get('file'))

    try:
        if request.FILES.get('file'):
            raw = request.FILES['file'].read().decode('utf-8')
        else:
            raw = request.body.decode('utf-8')
        data = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        if is_form_upload:
            messages.error(request, f'Неверный JSON: {e}')
            return redirect('answer_library:topic_list')
        return JsonResponse({'success': False, 'error': f'Неверный JSON: {e}'})

    if not isinstance(data, dict) or 'topics' not in data:
        err = 'В JSON ожидается объект с полем "topics" (массив тем)'
        if is_form_upload:
            messages.error(request, err)
            return redirect('answer_library:topic_list')
        return JsonResponse({'success': False, 'error': err})

    topics_data = data['topics']
    if not isinstance(topics_data, list):
        err = '"topics" должен быть массивом'
        if is_form_upload:
            messages.error(request, err)
            return redirect('answer_library:topic_list')
        return JsonResponse({'success': False, 'error': err})

    created = 0
    errors = []
    for i, item in enumerate(topics_data):
        if not isinstance(item, dict):
            errors.append(f'Тема #{i + 1}: не объект')
            continue
        title = (item.get('title') or '').strip()
        if not title:
            errors.append(f'Тема #{i + 1}: пустое название')
            continue
        vacancy_id = item.get('vacancy_id')
        if vacancy_id is not None:
            from apps.vacancies.models import Vacancy
            if not Vacancy.objects.filter(pk=vacancy_id).exists():
                vacancy_id = None
        try:
            TriggerTopic.objects.create(
                title=title[:255],
                trigger_words=(item.get('trigger_words') or '')[:10000],
                example_answer=(item.get('example_answer') or '')[:50000],
                extra_data=(item.get('extra_data') or '')[:50000],
                order=min(32767, max(0, int(item.get('order', 0)))),
                is_active=bool(item.get('is_active', True)),
                vacancy_id=vacancy_id,
            )
            created += 1
        except Exception as e:
            errors.append(f'Тема "{title[:30]}...": {e}')

    if is_form_upload:
        if created:
            messages.success(request, f'Импортировано тем: {created}.')
        if errors:
            messages.warning(request, 'Предупреждения: ' + '; '.join(errors[:5]) + (' ...' if len(errors) > 5 else ''))
        return redirect('answer_library:topic_list')

    if errors:
        return JsonResponse({'success': True, 'created': created, 'warnings': errors})
    return JsonResponse({'success': True, 'created': created})


# ——— Чат ———

def _get_user_active_vacancies(user):
    """Вакансии, активные у пользователя (is_active и пользователь — рекрутер или доп. рекрутер)."""
    from apps.vacancies.models import Vacancy
    qs = Vacancy.objects.filter(is_active=True).order_by('name')
    if user.is_superuser:
        return qs
    return qs.filter(Q(recruiter=user) | Q(additional_recruiters=user)).distinct()


@login_required
def chat(request, session_id=None):
    """Страница чата: у пользователя одна сессия, получаем или создаём её."""
    if not getattr(request.user, 'gemini_api_key', None):
        messages.warning(request, 'Настройте API ключ Gemini в разделе Gemini.')
        return redirect('gemini:settings')
    # Одна сессия на пользователя: get_or_create
    session, _ = AnswerLibrarySession.objects.get_or_create(
        user=request.user,
        defaults={'title': 'Чат библиотеки ответов'},
    )
    # Если зашли по старой ссылке с другим session_id — редирект на общий чат
    if session_id and session.pk != session_id:
        return redirect('answer_library:chat')
    messages_list = AnswerLibraryMessage.objects.filter(session=session).order_by('-created_at')
    active_vacancies = _get_user_active_vacancies(request.user)
    return render(request, 'answer_library/chat.html', {
        'session': session,
        'chat_messages': messages_list,
        'active_vacancies': active_vacancies,
    })


@login_required
@require_http_methods(["POST"])
@csrf_exempt
def clear_chat_history(request):
    """Очистка истории чата: удаление всех сообщений сессии пользователя."""
    session = AnswerLibrarySession.objects.filter(user=request.user).first()
    if session:
        AnswerLibraryMessage.objects.filter(session=session).delete()
        session.updated_at = timezone.now()
        session.save(update_fields=['updated_at'])
    return JsonResponse({'success': True})


@login_required
@require_http_methods(["POST"])
@csrf_exempt
def send_message(request):
    """AJAX: вопросы кандидата → подбор блоков по триггерам → Gemini → ответ в чат."""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Неверный JSON'})
    session_id = data.get('session_id')
    message = (data.get('message') or '').strip()
    intro = (data.get('intro') or '').strip()
    outro = (data.get('outro') or '').strip()
    vacancy_id = data.get('vacancy_id')
    if not session_id:
        return JsonResponse({'success': False, 'error': 'Нужен session_id'})
    unified_message = build_unified_message(message, intro=intro, outro=outro)
    if not unified_message:
        return JsonResponse({'success': False, 'error': 'Нужен текст вопроса (сообщение кандидата)'})
    if not getattr(request.user, 'gemini_api_key', None):
        return JsonResponse({'success': False, 'error': 'Не настроен API ключ Gemini'})
    session = get_object_or_404(AnswerLibrarySession, pk=session_id, user=request.user)

    # Обновляем выбранную вакансию сессии, если передана
    if vacancy_id is not None:
        session.vacancy_id = vacancy_id if vacancy_id else None
        session.save(update_fields=['vacancy_id', 'updated_at'])
    else:
        session.updated_at = timezone.now()
        session.save(update_fields=['updated_at'])

    # Сохраняем сообщение пользователя (в чат показываем как есть: intro + message + outro или только message)
    user_display_content = "\n\n".join(p for p in [intro, message, outro] if p.strip()) if (intro or outro) else message
    AnswerLibraryMessage.objects.create(session=session, role=AnswerLibraryMessage.ROLE_USER, content=user_display_content)

    # Подбор блоков по триггерам и выбранной вакансии (если есть)
    topics = get_matching_topics(unified_message, vacancy_id=session.vacancy_id)
    if not topics:
        hint = (
            "По ключевым словам в вопросе не подобрано ни одной темы из справочника. "
            "Добавьте в разделе «Справочник: темы и примеры ответов» темы с триггерами, например: "
            "«компания», «формат работы», «рассказать» — и укажите примеры ответов по этим темам. "
            "После сохранения тем отправьте сообщение снова."
        )
        AnswerLibraryMessage.objects.create(
            session=session,
            role=AnswerLibraryMessage.ROLE_ASSISTANT,
            content=hint,
        )
        return JsonResponse({'success': True, 'response': hint})

    context_blocks = build_context_blocks(topics)
    prompt = build_prompt_for_gemini(unified_message, context_blocks)

    # Вызов Gemini (один запрос без истории, т.к. контекст уже в промпте)
    try:
        from apps.gemini.logic.services import GeminiService
        gemini = GeminiService(request.user.gemini_api_key)
        success, response_text, metadata = gemini.generate_content(prompt, history=None)
    except Exception as e:
        logger.exception('Answer library Gemini call failed')
        return JsonResponse({'success': False, 'error': str(e)})

    if not success:
        return JsonResponse({'success': False, 'error': response_text or 'Ошибка Gemini'})

    # Сохраняем ответ ИИ
    msg = AnswerLibraryMessage.objects.create(
        session=session,
        role=AnswerLibraryMessage.ROLE_ASSISTANT,
        content=response_text,
    )
    return JsonResponse({
        'success': True,
        'response': response_text,
        'assistant_message_id': msg.id,
    })


@login_required
def library_index(request):
    """Главная библиотеки: ссылки на справочник и чат."""
    return render(request, 'answer_library/index.html')
