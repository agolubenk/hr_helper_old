"""
Тестовые views для демонстрации работы декораторов прав доступа
"""
from django.shortcuts import render
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt

from .decorators import (
    permission_required_with_403,
    role_required,
    admin_required,
    recruiter_required,
    interviewer_required,
    observer_required
)


@login_required
def test_view_without_permission(request):
    """View без проверки прав - доступен всем авторизованным"""
    return JsonResponse({
        'message': 'Это view доступен всем авторизованным пользователям',
        'user': request.user.username,
        'is_authenticated': request.user.is_authenticated,
        'user_groups': [g.name for g in request.user.groups.all()],
    })


@permission_required_with_403('accounts.add_user', raise_exception=False)
def test_view_with_permission(request):
    """View с проверкой права accounts.add_user"""
    return JsonResponse({
        'message': 'У вас есть право accounts.add_user!',
        'user': request.user.username,
        'permission': 'accounts.add_user',
        'user_permissions': list(request.user.get_all_permissions()),
    })


@permission_required_with_403('huntflow.add_huntflowlog', raise_exception=False)
def test_view_with_huntflow_permission(request):
    """View с проверкой права huntflow.add_huntflowlog"""
    return JsonResponse({
        'message': 'У вас есть право huntflow.add_huntflowlog!',
        'user': request.user.username,
        'permission': 'huntflow.add_huntflowlog',
        'user_permissions': list(request.user.get_all_permissions()),
    })


@permission_required_with_403('some_app.nonexistent_permission', raise_exception=False)
def test_view_without_permission(request):
    """View с проверкой несуществующего права"""
    return JsonResponse({
        'message': 'У вас есть право some_app.nonexistent_permission!',
        'user': request.user.username,
        'permission': 'some_app.nonexistent_permission',
        'user_permissions': list(request.user.get_all_permissions()),
    })


@admin_required(raise_exception=False)
def test_admin_required(request):
    """View только для администраторов"""
    return JsonResponse({
        'message': 'Вы администратор!',
        'user': request.user.username,
        'user_roles': {
            'is_admin': request.user.is_admin,
            'is_recruiter': request.user.is_recruiter,
            'is_interviewer': request.user.is_interviewer,
            'is_observer': request.user.is_observer,
        }
    })


@recruiter_required(raise_exception=False)
def test_recruiter_required(request):
    """View только для рекрутеров"""
    return JsonResponse({
        'message': 'Вы рекрутер!',
        'user': request.user.username,
        'user_roles': {
            'is_admin': request.user.is_admin,
            'is_recruiter': request.user.is_recruiter,
            'is_interviewer': request.user.is_interviewer,
            'is_observer': request.user.is_observer,
        }
    })


@interviewer_required(raise_exception=False)
def test_interviewer_required(request):
    """View только для интервьюеров"""
    return JsonResponse({
        'message': 'Вы интервьюер!',
        'user': request.user.username,
        'user_roles': {
            'is_admin': request.user.is_admin,
            'is_recruiter': request.user.is_recruiter,
            'is_interviewer': request.user.is_interviewer,
            'is_observer': request.user.is_observer,
        }
    })


@observer_required(raise_exception=False)
def test_observer_required(request):
    """View только для наблюдателей"""
    return JsonResponse({
        'message': 'Вы наблюдатель!',
        'user': request.user.username,
        'user_roles': {
            'is_admin': request.user.is_admin,
            'is_recruiter': request.user.is_recruiter,
            'is_interviewer': request.user.is_interviewer,
            'is_observer': request.user.is_observer,
        }
    })


def test_permission_info(request):
    """View для отображения информации о правах пользователя"""
    if not request.user.is_authenticated:
        return JsonResponse({
            'error': 'Пользователь не авторизован'
        }, status=401)
    
    return JsonResponse({
        'user': {
            'username': request.user.username,
            'email': request.user.email,
            'is_superuser': request.user.is_superuser,
            'is_staff': request.user.is_staff,
            'is_active': request.user.is_active,
        },
        'groups': [g.name for g in request.user.groups.all()],
        'roles': {
            'is_admin': request.user.is_admin,
            'is_recruiter': request.user.is_recruiter,
            'is_interviewer': request.user.is_interviewer,
            'is_observer': request.user.is_observer,
        },
        'permissions': {
            'total': len(request.user.get_all_permissions()),
            'individual': len(request.user.user_permissions.all()),
            'group': len(request.user.get_group_permissions()),
            'examples': list(request.user.get_all_permissions())[:10],  # Первые 10 прав
        }
    })
