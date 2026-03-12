"""Управление пользователями"""
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout
from django.contrib import messages
from django.http import JsonResponse, HttpResponseNotAllowed
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
import json
import re
from functools import lru_cache

from django.contrib.staticfiles import finders

from apps.accounts.models import User
from apps.accounts.forms import ProfileEditForm
from logic.utilities.account_services import UserService
from logic.base.response_handler import UnifiedResponseHandler


@lru_cache(maxsize=1)
def get_fontawesome_icon_names_from_css():
    """
    Достаём имена иконок из подключенного Font Awesome CSS (static `css/all.min.css`).

    Возвращает список имён без префикса стиля, например: ['address-book', 'calendar', ...]
    """
    css_path = finders.find('css/all.min.css')
    if not css_path:
        return []

    try:
        with open(css_path, 'r', encoding='utf-8', errors='ignore') as f:
            css = f.read()
    except OSError:
        return []

    names = set(re.findall(r'\.fa-([a-z0-9-]+):before', css))
    return sorted(names)


# =============================================================================
# УНИВЕРСАЛЬНЫЕ ФУНКЦИИ
# =============================================================================

def unified_template_view(request, template_name, handler_func=None, context=None):
    """
    Универсальная функция для рендеринга HTML-шаблонов
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - request: HTTP запрос
    - template_name: строка, путь к шаблону
    - handler_func: функция-обработчик для подготовки контекста (опционально)
    - context: словарь с данными для шаблона (опционально)
    
    ИСТОЧНИКИ ДАННЫХ:
    - Переданный context или пустой словарь
    - Результат выполнения handler_func (если указан)
    
    ОБРАБОТКА:
    - Объединение переданного контекста с результатом handler_func
    - Обработка ошибок при выполнении handler_func
    - Рендеринг шаблона с финальным контекстом
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - render: HTML страница по указанному template_name
    
    СВЯЗИ:
    - Использует: Django render function
    - Передает данные в: указанный template_name
    - Может вызываться из: любые views функции
    """
    if context is None:
        context = {}
    
    # Если передан handler_func, вызываем его для подготовки контекста
    if handler_func:
        try:
            handler_context = handler_func(request)
            if isinstance(handler_context, dict):
                context.update(handler_context)
        except Exception as e:
            # Если handler_func выдает ошибку, добавляем сообщение об ошибке
            context['error'] = f'Ошибка обработки: {str(e)}'
    
    return render(request, template_name, context)


@csrf_exempt
def unified_api_view(request, handler_func):
    """
    Универсальная функция для обработки JSON-запросов.
    - handler_func: функция, которая принимает словарь data и request, возвращает словарь response_data
    """
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    
    try:
        data = json.loads(request.body.decode('utf-8'))
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    
    # Вызов пользовательского обработчика
    response_data = handler_func(data, request)
    return JsonResponse(response_data)


# =============================================================================
# ФУНКЦИИ-ОБРАБОТЧИКИ ДЛЯ API
# =============================================================================

def login_api_handler(data, request):
    """Обработчик API для входа в систему"""
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return {'error': 'Имя пользователя и пароль обязательны'}
    
    from django.contrib.auth import authenticate
    user = authenticate(request, username=username, password=password)
    
    if user is not None:
        if user.is_active:
            login(request, user)
            from apps.accounts.serializers import UserSerializer
            serializer = UserSerializer(user)
            return {
                'success': True,
                'message': 'Вход выполнен успешно',
                'user': serializer.data
            }
        else:
            return {'error': 'Аккаунт деактивирован'}
    else:
        return {'error': 'Неверное имя пользователя или пароль'}


def logout_api_handler(data, request):
    """Обработчик API для выхода из системы"""
    logout(request)
    return {
        'success': True,
        'message': 'Выход выполнен успешно'
    }


def test_gemini_api_handler(data, request):
    """Обработчик API для тестирования Gemini API"""
    api_key = data.get('api_key')
    if not api_key:
        return {'success': False, 'message': 'API ключ не указан'}
    
    try:
        # Используем реальный сервис для тестирования
        from logic.utilities.account_services import UserService
        success, message = UserService.test_api_key_integration('gemini', api_key)
        return {'success': success, 'message': message}
    except Exception as e:
        return {'success': False, 'message': f'Ошибка тестирования: {str(e)}'}


def test_huntflow_api_handler(data, request):
    """Обработчик API для тестирования Huntflow API"""
    api_key = data.get('api_key')
    api_url = data.get('api_url')
    system = data.get('system', 'sandbox')
    
    
    if not api_key:
        return {'success': False, 'message': 'API ключ обязателен'}
    
    if not api_url:
        return {'success': False, 'message': 'URL обязателен'}
    
    if len(api_key) < 10:
        return {'success': False, 'message': 'API ключ слишком короткий'}
    
    return {'success': True, 'message': f'Huntflow {system} API ключ валиден'}


def test_clickup_api_handler(data, request):
    """Обработчик API для тестирования ClickUp API"""
    api_key = data.get('api_key')
    if not api_key:
        return {'success': False, 'message': 'API ключ не указан'}
    
    try:
        # Используем реальный сервис для тестирования
        from logic.utilities.account_services import UserService
        success, message = UserService.test_api_key_integration('clickup', api_key)
        return {'success': success, 'message': message}
    except Exception as e:
        return {'success': False, 'message': f'Ошибка тестирования: {str(e)}'}


def test_notion_api_handler(data, request):
    """Обработчик API для тестирования Notion API"""
    api_key = data.get('api_key')
    if not api_key:
        return {'success': False, 'message': 'Integration Token не указан'}
    
    try:
        # Используем реальный сервис для тестирования
        from logic.utilities.account_services import UserService
        success, message = UserService.test_api_key_integration('notion', api_key)
        return {'success': success, 'message': message}
    except Exception as e:
        return {'success': False, 'message': f'Ошибка тестирования: {str(e)}'}


# =============================================================================
# ФУНКЦИИ-ОБРАБОТЧИКИ ДЛЯ ШАБЛОНОВ
# =============================================================================

def profile_template_handler(request):
    """Обработчик для страницы профиля"""
    from django.contrib import messages
    from apps.accounts.logic.user_service import UserService
    
    # Используем сервисный слой для получения данных профиля
    context = UserService.get_user_profile_data(request.user)
    context['messages'] = messages.get_messages(request)
    return context


def profile_edit_template_handler(request):
    """Обработчик для страницы редактирования профиля"""
    from django.contrib import messages
    
    user = request.user
    
    # Получаем информацию о Google OAuth аккаунте
    oauth_account = None
    is_google_oauth_connected = False
    try:
        from apps.google_oauth.models import GoogleOAuthAccount
        oauth_account = GoogleOAuthAccount.objects.get(user=user)
        is_google_oauth_connected = oauth_account is not None
        token_valid = oauth_account.is_token_valid() if oauth_account else False
    except:
        token_valid = False
    
    if request.method == 'POST':
        form = ProfileEditForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Профиль успешно обновлен!')
            # После сохранения создаем новую форму с обновленными данными
            form = ProfileEditForm(instance=request.user)
        # Если форма не валидна, она уже содержит данные и ошибки
    else:
        form = ProfileEditForm(instance=request.user)
    
    context = {
        'form': form,
        'oauth_account': oauth_account,
        'is_google_oauth_connected': is_google_oauth_connected,
        'token_valid': token_valid,
        'messages': messages.get_messages(request),
    }
    
    return context


def integrations_template_handler(request):
    """Обработчик для страницы интеграций"""
    from django.contrib import messages
    from django.urls import reverse
    
    # Используем сервисный слой для получения статуса интеграций
    integrations_status = UserService.get_integrations_status(request.user)
    
    # Получаем информацию о Google OAuth аккаунте
    oauth_account = None
    is_google_oauth_connected = False
    is_google_social_connected = False
    
    try:
        from apps.google_oauth.models import GoogleOAuthAccount
        oauth_account = GoogleOAuthAccount.objects.get(user=request.user)
        is_google_oauth_connected = oauth_account is not None
        token_valid = oauth_account.is_token_valid() if oauth_account else False
    except Exception:
        token_valid = False
    
    # Проверяем социальные аккаунты
    if hasattr(request.user, 'socialaccount_set'):
        is_google_social_connected = any(
            account.provider == 'google'
            for account in request.user.socialaccount_set.all()
        )
    
    # URL для получения токена расширения Chrome (DRF Token)
    try:
        extension_token_url = request.build_absolute_uri(reverse('user-token'))
    except Exception:
        extension_token_url = '/api/v1/accounts/users/token/'
    
    context = {
        'user': request.user,
        'integrations': integrations_status,
        'oauth_account': oauth_account,
        'is_google_oauth_connected': is_google_oauth_connected,
        'is_google_social_connected': is_google_social_connected,
        'token_valid': token_valid,
        'extension_token_url': extension_token_url,
        'messages': messages.get_messages(request),
    }
    
    return context


def api_keys_template_handler(request):
    """Обработчик для страницы API ключей"""
    user = request.user
    
    if request.method == 'POST':
        # Используем сервисный слой для обновления API ключей
        data = {
            'gemini_api_key': request.POST.get('gemini_api_key', ''),
            'clickup_api_key': request.POST.get('clickup_api_key', ''),
            'notion_integration_token': request.POST.get('notion_integration_token', ''),
            'huntflow_sandbox_api_key': request.POST.get('huntflow_sandbox_api_key', ''),
            # huntflow_prod_api_key больше не используется, для PROD используются токены
            'huntflow_sandbox_url': request.POST.get('huntflow_sandbox_url', ''),
            'huntflow_prod_url': request.POST.get('huntflow_prod_url', ''),
            'huntflow_access_token': request.POST.get('huntflow_access_token', ''),
            'huntflow_refresh_token': request.POST.get('huntflow_refresh_token', ''),
            'active_system': request.POST.get('active_system', 'sandbox'),
        }
        
        UserService.update_user_api_keys(user, data)
        messages.success(request, 'API ключи успешно обновлены!')
        return redirect('accounts:api_keys')
    
    context = {'user': user}
    return context


def quick_buttons_template_handler(request):
    """Обработчик для страницы быстрых кнопок"""
    from apps.accounts.models import QuickButton
    from django.db import transaction
    
    user = request.user
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'create':
            # Создание новой кнопки
            try:
                name = request.POST.get('name', '').strip()
                icon = request.POST.get('icon', 'fas fa-circle').strip()
                button_type = request.POST.get('button_type', 'link')
                value = request.POST.get('value', '').strip()
                order = int(request.POST.get('order', 0))
                
                # Проверяем обязательные поля
                if not name:
                    messages.error(request, 'Название кнопки обязательно для заполнения')
                    return redirect('accounts:quick_buttons')
                
                if not icon:
                    messages.error(request, 'Иконка обязательна для заполнения')
                    return redirect('accounts:quick_buttons')
                
                if not button_type:
                    messages.error(request, 'Тип кнопки обязателен для заполнения')
                    return redirect('accounts:quick_buttons')
                
                if not value:
                    messages.error(request, 'Значение обязательно для заполнения')
                    return redirect('accounts:quick_buttons')
                
                color = request.POST.get('color', '#007bff').strip()
                if not color.startswith('#'):
                    color = '#' + color
                
                with transaction.atomic():
                    button = QuickButton(
                        user=user,
                        name=name,
                        icon=icon,
                        button_type=button_type,
                        value=value,
                        order=order,
                        color=color
                    )
                    button.full_clean()  # Валидация
                    button.save()
                messages.success(request, f'Быстрая кнопка "{button.name}" успешно создана!')
            except Exception as e:
                import traceback
                error_details = traceback.format_exc()
                print(f"❌ Ошибка при создании кнопки: {e}")
                print(f"❌ Детали: {error_details}")
                messages.error(request, f'Ошибка при создании кнопки: {str(e)}')
        
        elif action == 'update':
            # Обновление существующей кнопки
            button_id = request.POST.get('button_id')
            try:
                if not button_id:
                    messages.error(request, 'ID кнопки не указан')
                    return redirect('accounts:quick_buttons')
                
                button = QuickButton.objects.get(id=button_id, user=user)
                name = request.POST.get('name', '').strip()
                icon = request.POST.get('icon', 'fas fa-circle').strip()
                button_type = request.POST.get('button_type', 'link')
                value = request.POST.get('value', '').strip()
                order = int(request.POST.get('order', 0))
                
                # Проверяем обязательные поля
                if not name:
                    messages.error(request, 'Название кнопки обязательно для заполнения')
                    return redirect('accounts:quick_buttons')
                
                if not icon:
                    messages.error(request, 'Иконка обязательна для заполнения')
                    return redirect('accounts:quick_buttons')
                
                color = request.POST.get('color', '#007bff').strip()
                if not color.startswith('#'):
                    color = '#' + color
                
                button.name = name
                button.icon = icon
                button.button_type = button_type
                button.value = value
                button.order = order
                button.color = color
                button.full_clean()  # Валидация
                button.save()
                messages.success(request, f'Быстрая кнопка "{button.name}" успешно обновлена!')
            except QuickButton.DoesNotExist:
                messages.error(request, 'Кнопка не найдена.')
            except Exception as e:
                import traceback
                error_details = traceback.format_exc()
                print(f"❌ Ошибка при обновлении кнопки: {e}")
                print(f"❌ Детали: {error_details}")
                messages.error(request, f'Ошибка при обновлении кнопки: {str(e)}')
        
        elif action == 'delete':
            # Удаление кнопки
            button_id = request.POST.get('button_id')
            try:
                button = QuickButton.objects.get(id=button_id, user=user)
                button_name = button.name
                button.delete()
                messages.success(request, f'Быстрая кнопка "{button_name}" успешно удалена!')
            except QuickButton.DoesNotExist:
                messages.error(request, 'Кнопка не найдена.')
            except Exception as e:
                messages.error(request, f'Ошибка при удалении кнопки: {str(e)}')
        
        elif action == 'reorder':
            # Изменение порядка кнопок
            try:
                with transaction.atomic():
                    button_orders = request.POST.getlist('button_order[]')
                    for order_data in button_orders:
                        button_id, new_order = order_data.split(':')
                        QuickButton.objects.filter(id=button_id, user=user).update(order=int(new_order))
                messages.success(request, 'Порядок кнопок успешно обновлен!')
            except Exception as e:
                messages.error(request, f'Ошибка при изменении порядка: {str(e)}')
        
        elif action == 'save_reminder_phrase':
            # Сохранение зашифрованной фразы-напоминания
            from apps.accounts.models import UserReminderPhrase
            from apps.accounts.encryption import encrypt_for_user
            try:
                phrase = request.POST.get('reminder_phrase', '').strip()
                obj, _ = UserReminderPhrase.objects.get_or_create(user=user)
                obj.encrypted_value = encrypt_for_user(user, phrase)
                obj.save()
                messages.success(request, 'Фраза-напоминание сохранена.')
            except Exception as e:
                messages.error(request, f'Ошибка при сохранении: {str(e)}')
        
        return redirect('accounts:quick_buttons')
    
    # GET запрос - отображение списка кнопок
    from apps.accounts.models import QuickButtonType
    
    quick_buttons = QuickButton.objects.filter(user=user).order_by('order', 'created_at')
    
    # Отладочная информация
    print(f"🔍 QUICK_BUTTONS: Пользователь: {user.username}")
    print(f"🔍 QUICK_BUTTONS: Найдено кнопок: {quick_buttons.count()}")
    for btn in quick_buttons:
        print(f"🔍 QUICK_BUTTONS: - {btn.name} (ID: {btn.id}, тип: {btn.button_type})")
    
    # Используем choices напрямую - это уже список кортежей (value, label)
    button_types_list = list(QuickButtonType.choices)
    
    # Популярные иконки Font Awesome для быстрых кнопок
    popular_icons = [
        ('fas fa-link', 'Ссылка'),
        ('fas fa-calendar', 'Календарь'),
        ('fas fa-clock', 'Часы'),
        ('fas fa-envelope', 'Почта'),
        ('fas fa-phone', 'Телефон'),
        ('fas fa-map-marker-alt', 'Местоположение'),
        ('fas fa-file', 'Файл'),
        ('fas fa-folder', 'Папка'),
        ('fas fa-user', 'Пользователь'),
        ('fas fa-users', 'Пользователи'),
        ('fas fa-building', 'Здание'),
        ('fas fa-briefcase', 'Портфель'),
        ('fas fa-chart-line', 'График'),
        ('fas fa-tasks', 'Задачи'),
        ('fas fa-check-circle', 'Галочка'),
        ('fas fa-star', 'Звезда'),
        ('fas fa-heart', 'Сердце'),
        ('fas fa-bookmark', 'Закладка'),
        ('fas fa-bolt', 'Молния'),
        ('fas fa-fire', 'Огонь'),
        ('fas fa-gift', 'Подарок'),
        ('fas fa-home', 'Дом'),
        ('fas fa-globe', 'Глобус'),
        ('fas fa-share-alt', 'Поделиться'),
        ('fas fa-download', 'Скачать'),
        ('fas fa-upload', 'Загрузить'),
        ('fas fa-search', 'Поиск'),
        ('fas fa-cog', 'Настройки'),
        ('fas fa-info-circle', 'Информация'),
        ('fas fa-question-circle', 'Вопрос'),
        ('fas fa-exclamation-circle', 'Внимание'),
        ('fas fa-times-circle', 'Закрыть'),
        ('fas fa-plus-circle', 'Добавить'),
        ('fas fa-minus-circle', 'Удалить'),
        ('fas fa-edit', 'Редактировать'),
        ('fas fa-trash', 'Корзина'),
        ('fas fa-save', 'Сохранить'),
        ('fas fa-print', 'Печать'),
        ('fas fa-copy', 'Копировать'),
        ('fas fa-paste', 'Вставить'),
    ]

    # Полный список иконок из подключенного Font Awesome (если доступно).
    # Важно: у Font Awesome разные "семейства" (solid/regular/brands). В UI покажем все три варианта.
    popular_icon_classes = {cls for cls, _ in popular_icons}
    icon_names = get_fontawesome_icon_names_from_css()
    all_icons_by_style = {
        'fas': [(f'fas fa-{n}', n) for n in icon_names],
        'far': [(f'far fa-{n}', n) for n in icon_names],
        'fab': [(f'fab fa-{n}', n) for n in icon_names],
    }
    # Убираем дубли популярных из solid-группы (чтобы не повторялись подряд)
    all_icons_by_style['fas'] = [(cls, name) for cls, name in all_icons_by_style['fas'] if cls not in popular_icon_classes]
    
    # Преобразуем QuerySet в список для отладки
    quick_buttons_list = list(quick_buttons)
    print(f"🔍 QUICK_BUTTONS: Список кнопок (длина): {len(quick_buttons_list)}")
    
    # Расшифрованная фраза-напоминание (только для отображения владельцу)
    reminder_phrase_plain = ""
    try:
        from apps.accounts.models import UserReminderPhrase
        from apps.accounts.encryption import decrypt_for_user
        reminder_obj = UserReminderPhrase.objects.filter(user=user).first()
        if reminder_obj and reminder_obj.encrypted_value:
            reminder_phrase_plain = decrypt_for_user(user, reminder_obj.encrypted_value)
    except Exception:
        pass
    
    context = {
        'user': user,
        'quick_buttons': quick_buttons,  # Оставляем QuerySet для шаблона
        'button_types': button_types_list,
        'popular_icons': popular_icons,
        'all_icons_by_style': all_icons_by_style,
        'reminder_phrase': reminder_phrase_plain,
    }
    
    print(f"🔍 QUICK_BUTTONS: Контекст создан, quick_buttons в контексте: {len(context.get('quick_buttons', []))}")
    
    return context


# =============================================================================
# ОСНОВНЫЕ VIEW-ФУНКЦИИ
# =============================================================================

def google_oauth_redirect(request):
    """Прямой переход на Google OAuth"""
    from logic.utilities.oauth_services import GoogleOAuthService
    auth_url = GoogleOAuthService.get_authorization_url(request)
    return redirect(auth_url)


def google_oauth_callback(request):
    """Обработка callback от Google OAuth"""
    from logic.utilities.oauth_services import GoogleOAuthService
    
    result = GoogleOAuthService.handle_oauth_callback(request)
    
    if result['success']:
        messages.success(request, result['message'])
        return redirect('huntflow:dashboard')
    else:
        messages.error(request, result['error'])
        return redirect('account_login')


def _get_safe_next_url(request, default='/huntflow/'):
    """Возвращает безопасный next URL (только разрешённый хост)."""
    from django.utils.http import url_has_allowed_host_and_scheme
    next_url = request.GET.get('next') or request.POST.get('next', '')
    allowed_hosts = {request.get_host()}
    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts=allowed_hosts):
        return next_url
    return default


@csrf_exempt
def unified_login(request):
    """Универсальная функция входа (поддерживает HTML и JSON). Учитывает параметр next."""
    if request.user.is_authenticated:
        if request.content_type == 'application/json':
            return JsonResponse({'success': True, 'message': 'Уже авторизован'})
        next_url = _get_safe_next_url(request)
        return redirect(next_url)
    
    if request.method == 'POST':
        # Определяем тип запроса
        if request.content_type == 'application/json':
            # JSON API запрос
            try:
                data = json.loads(request.body)
                username = data.get('username')
                password = data.get('password')
            except json.JSONDecodeError:
                return JsonResponse({'error': 'Неверный JSON'}, status=400)
        else:
            # HTML форма
            username = request.POST.get('username')
            password = request.POST.get('password')
        
        if not username or not password:
            if request.content_type == 'application/json':
                return JsonResponse(
                    {'error': 'Имя пользователя и пароль обязательны'}, 
                    status=400
                )
            else:
                messages.error(request, 'Имя пользователя и пароль обязательны.')
                return render(request, 'accounts/login.html', {'next': request.GET.get('next', '')})
        
        from django.contrib.auth import authenticate
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            if user.is_active:
                login(request, user)
                if request.content_type == 'application/json':
                    from apps.accounts.serializers import UserSerializer
                    serializer = UserSerializer(user)
                    return JsonResponse({
                        'success': True,
                        'message': 'Вход выполнен успешно',
                        'user': serializer.data
                    })
                else:
                    messages.success(request, 'Вы успешно вошли в систему!')
                    next_url = _get_safe_next_url(request)
                    return redirect(next_url)
            else:
                if request.content_type == 'application/json':
                    return JsonResponse(
                        {'error': 'Аккаунт деактивирован'}, 
                        status=400
                    )
                else:
                    messages.error(request, 'Аккаунт деактивирован.')
        else:
            if request.content_type == 'application/json':
                return JsonResponse(
                    {'error': 'Неверное имя пользователя или пароль'}, 
                    status=401
                )
            else:
                messages.error(request, 'Неверное имя пользователя или пароль.')
    
    # GET запрос - показываем форму входа (передаём next в шаблон для скрытого поля)
    if request.content_type == 'application/json':
        return JsonResponse({'error': 'Метод не поддерживается'}, status=405)
    return render(request, 'accounts/login.html', {'next': request.GET.get('next', '')})


@csrf_exempt
def unified_logout(request):
    """Универсальная функция выхода (поддерживает HTML и JSON)"""
    logout(request)
    
    if request.content_type == 'application/json':
        return JsonResponse({
            'success': True,
            'message': 'Выход выполнен успешно'
        })
    else:
        messages.success(request, 'Вы успешно вышли из системы!')
        return redirect('/huntflow/')


def google_oauth_demo(request):
    """Демонстрация Google OAuth"""
    return render(request, 'account/google_oauth_demo.html')


def google_oauth_test(request):
    """Тестовая страница для Google OAuth"""
    return render(request, 'account/google_oauth_test.html')


def oauth_debug(request):
    """Диагностическая страница для Google OAuth"""
    return render(request, 'account/oauth_debug.html')
