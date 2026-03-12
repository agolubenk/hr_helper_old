from django.utils.deprecation import MiddlewareMixin
from django.views.decorators.csrf import csrf_exempt


class DisableCSRFForAPI(MiddlewareMixin):
    """Middleware для отключения CSRF для API endpoints"""
    
    def process_view(self, request, view_func, view_args, view_kwargs):
        # Отключаем CSRF для API endpoints
        if request.path.startswith('/api/'):
            return csrf_exempt(view_func)(request, *view_args, **view_kwargs)
        return None
