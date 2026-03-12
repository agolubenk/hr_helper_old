"""
Декораторы для проверки прав доступа
"""
from functools import wraps
from django.shortcuts import render
from django.core.exceptions import PermissionDenied
from django.contrib.auth.views import redirect_to_login


def permission_required_with_403(perm, login_url=None, raise_exception=False):
    """
    Декоратор для проверки прав доступа с отображением страницы 403
    
    Args:
        perm: Право доступа (например, 'accounts.add_user')
        login_url: URL для перенаправления неавторизованных пользователей
        raise_exception: Если True, выбрасывает PermissionDenied вместо показа 403
    
    Returns:
        Декоратор функции
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            # Проверяем авторизацию
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path(), login_url)
            
            # Проверяем права
            if not request.user.has_perm(perm):
                if raise_exception:
                    raise PermissionDenied
                else:
                    # Показываем страницу 403 с дополнительной информацией
                    context = {
                        'request_path': request.path,
                        'permission_required': perm,
                        'user_permissions': list(request.user.get_all_permissions()),
                        'user_groups': [g.name for g in request.user.groups.all()],
                    }
                    return render(request, '403.html', context, status=403)
            
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator


def role_required(role_name, login_url=None, raise_exception=False):
    """
    Декоратор для проверки роли пользователя
    
    Args:
        role_name: Название роли ('admin', 'recruiter', 'interviewer', 'observer')
        login_url: URL для перенаправления неавторизованных пользователей
        raise_exception: Если True, выбрасывает PermissionDenied вместо показа 403
    
    Returns:
        Декоратор функции
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            # Проверяем авторизацию
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path(), login_url)
            
            # Проверяем роль
            has_role = False
            if role_name == 'admin':
                has_role = request.user.is_admin
            elif role_name == 'recruiter':
                has_role = request.user.is_recruiter
            elif role_name == 'interviewer':
                has_role = request.user.is_interviewer
            elif role_name == 'observer':
                has_role = request.user.is_observer
            
            if not has_role:
                if raise_exception:
                    raise PermissionDenied
                else:
                    # Показываем страницу 403 с дополнительной информацией
                    context = {
                        'request_path': request.path,
                        'role_required': role_name,
                        'user_groups': [g.name for g in request.user.groups.all()],
                        'user_roles': {
                            'is_admin': request.user.is_admin,
                            'is_recruiter': request.user.is_recruiter,
                            'is_interviewer': request.user.is_interviewer,
                            'is_observer': request.user.is_observer,
                        }
                    }
                    return render(request, '403.html', context, status=403)
            
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator


def admin_required(login_url=None, raise_exception=False):
    """
    Декоратор для проверки прав администратора
    """
    return role_required('admin', login_url, raise_exception)


def recruiter_required(login_url=None, raise_exception=False):
    """
    Декоратор для проверки прав рекрутера
    """
    return role_required('recruiter', login_url, raise_exception)


def interviewer_required(login_url=None, raise_exception=False):
    """
    Декоратор для проверки прав интервьюера
    """
    return role_required('interviewer', login_url, raise_exception)


def observer_required(login_url=None, raise_exception=False):
    """
    Декоратор для проверки прав наблюдателя
    """
    return role_required('observer', login_url, raise_exception)
