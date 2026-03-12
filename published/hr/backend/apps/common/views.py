"""
Общие views для приложения common
"""
from django.shortcuts import render
from django.http import HttpResponseNotFound
import logging

logger = logging.getLogger(__name__)


def custom_404_view(request, exception=None):
    """
    Кастомная страница 404 ошибки
    
    Args:
        request: HTTP запрос
        exception: Исключение (опционально)
        
    Returns:
        HttpResponseNotFound: HTML страница с ошибкой 404
    """
    logger.warning(f"404 ошибка: {request.path} - {request.META.get('HTTP_USER_AGENT', 'Unknown')}")
    
    # Добавляем пользователя в контекст, если он аутентифицирован
    context = {
        'request_path': request.path,
        'user_agent': request.META.get('HTTP_USER_AGENT', 'Unknown'),
        'referer': request.META.get('HTTP_REFERER', ''),
    }
    
    # Если пользователь аутентифицирован, добавляем его в контекст
    if hasattr(request, 'user') and request.user.is_authenticated:
        context['user'] = request.user
    
    return HttpResponseNotFound(render(request, '404.html', context))


def custom_500_view(request):
    """
    Кастомная страница 500 ошибки
    
    Args:
        request: HTTP запрос
        
    Returns:
        HttpResponseServerError: HTML страница с ошибкой 500
    """
    logger.error(f"500 ошибка: {request.path} - {request.META.get('HTTP_USER_AGENT', 'Unknown')}")
    
    context = {
        'request_path': request.path,
    }
    
    return render(request, '500.html', context, status=500)


def custom_403_view(request, exception=None):
    """
    Кастомная страница 403 ошибки
    
    Args:
        request: HTTP запрос
        exception: Исключение (опционально)
        
    Returns:
        HttpResponseForbidden: HTML страница с ошибкой 403
    """
    logger.warning(f"403 ошибка: {request.path} - {request.META.get('HTTP_USER_AGENT', 'Unknown')}")
    
    context = {
        'request_path': request.path,
    }
    
    return render(request, '403.html', context, status=403)


# Тестовые views для отладки (работают при DEBUG=True)
def test_404_view(request):
    """Тестовая страница 404 для отладки"""
    return custom_404_view(request)


def test_500_view(request):
    """Тестовая страница 500 для отладки"""
    return custom_500_view(request)


def test_403_view(request):
    """Тестовая страница 403 для отладки"""
    return custom_403_view(request)


def debug_image_view(request):
    """Отладочная страница для проверки загрузки картинки"""
    from django.http import HttpResponse
    import os
    
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Debug Image</title>
    </head>
    <body>
        <h1>Тест загрузки картинки 404</h1>
        
        <h2>1. Прямая ссылка на картинку:</h2>
        <img src="/static/img/404.png" alt="404 Image" style="max-width: 200px; border: 2px solid red;">
        
        <h2>2. Background image test (left):</h2>
        <div style="width: 200px; height: 200px; background-image: url('/static/img/404.png'); background-size: 200% 100%; background-position: left center; background-repeat: no-repeat; border: 2px solid blue;"></div>
        
        <h2>3. Background image test (right):</h2>
        <div style="width: 200px; height: 200px; background-image: url('/static/img/404.png'); background-size: 200% 100%; background-position: right center; background-repeat: no-repeat; border: 2px solid green;"></div>
        
        <h2>4. Проверка файла:</h2>
        <p>Путь: /static/img/404.png</p>
        <p>Файл существует: """ + str(os.path.exists('/Users/agolubenko/hrhelper/fullstack/backend/static/img/404.png')) + """</p>
        <p>Если картинки не видны, проверьте консоль браузера на ошибки</p>
    </body>
    </html>
    """
    
    return HttpResponse(html_content)


def privacy_policy_view(request):
    """
    Публичная страница «Политика конфиденциальности» для расширения HR Helper.
    Доступна без авторизации. URL указывается в Chrome Web Store.
    """
    return render(request, 'common/privacy_policy.html')
