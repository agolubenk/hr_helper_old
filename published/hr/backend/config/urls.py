from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect
from django.http import HttpResponse
from django.conf import settings
from django.conf.urls import handler404, handler500, handler403
from django.conf.urls.static import static
from django.views.static import serve
from apps.common.views import privacy_policy_view

def redirect_to_chat(request):
    return redirect('/google-oauth/chat/')

def health_check(request):
    return HttpResponse('ok', content_type='text/plain')

urlpatterns = [
    # Health check
    path('health/', health_check, name='health'),
    # Политика конфиденциальности (публичная, без входа — для Chrome Web Store)
    path('privacy/', privacy_policy_view),

    # API endpoints
    path('', include('config.api_urls')),
    
    # Simple API endpoints (без CSRF) - теперь в основном urls.py
    # path('simple-api/', include('apps.accounts.urls_simple')),  # Удалено - объединено в accounts/urls.py
    
    # Django admin
    path('admin/', admin.site.urls),
    
    # Главная страница
    path('', redirect_to_chat, name='home'),
    
    # Django Allauth (отдельный префикс)
    path('auth/', include('allauth.urls')),
    
    # Веб-интерфейс (старые URL)
    path('accounts/', include('apps.accounts.urls')),
    path('huntflow/', include('apps.huntflow.urls')),
    path('extension/', include(('apps.huntflow.urls_extension', 'extension'))),
    path('gemini/', include('apps.gemini.urls')),
    path('answer-library/', include('apps.answer_library.urls')),
    path('interviewers/', include('apps.interviewers.urls')),
    path('vacancies/', include('apps.vacancies.urls')),
    path('google-oauth/', include('apps.google_oauth.urls')),
    path('hh_app/', include('apps.hhru.urls')),
    path('finance/', include('apps.finance.urls')),
    path('clickup/', include('apps.clickup_int.urls')),
    path('hiring-plans/', include('apps.hiring_plan.urls')),
    path('company-settings/', include('apps.company_settings.urls')),
    path('wiki/', include('apps.wiki.urls')),
    path('reporting/', include('apps.reporting.urls')),
    path('summernote/', include('django_summernote.urls')),
    
    # Common URLs (обработчики ошибок)
    path('common/', include('apps.common.urls')),
]

# Обработчики ошибок
handler404 = 'apps.common.views.custom_404_view'
handler500 = 'apps.common.views.custom_500_view'
handler403 = 'apps.common.views.custom_403_view'

# Обслуживание статических файлов
if settings.DEBUG:
    # Разработка: раздаём из папки static/ (STATICFILES_DIRS)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
else:
    # Прод: раздаём из staticfiles/ (результат collectstatic), чтобы подтягивались все собранные файлы
    urlpatterns += [
        path('static/<path:path>', serve, {'document_root': settings.STATIC_ROOT}),
    ]
