"""
Views для статических страниц-примеров для тура
"""
from django.shortcuts import render
from django.contrib.auth.decorators import login_required


@login_required
def tour_company_settings_example(request):
    """Статическая страница-пример настроек компании"""
    return render(request, 'wiki/tour_examples/company_settings.html', {
        'is_tour_example': True,
        'page_title': 'Настройки компании - Пример'
    })


@login_required
def tour_user_profile_example(request):
    """Статическая страница-пример профиля пользователя"""
    return render(request, 'wiki/tour_examples/user_profile.html', {
        'is_tour_example': True,
        'page_title': 'Профиль пользователя - Пример'
    })


@login_required
def tour_vacancies_example(request):
    """Статическая страница-пример вакансий"""
    return render(request, 'wiki/tour_examples/vacancies.html', {
        'is_tour_example': True,
        'page_title': 'Вакансии - Пример'
    })


@login_required
def tour_finance_example(request):
    """Статическая страница-пример финансов"""
    return render(request, 'wiki/tour_examples/finance.html', {
        'is_tour_example': True,
        'page_title': 'Финансы - Пример'
    })


@login_required
def tour_google_oauth_example(request):
    """Статическая страница-пример Google OAuth"""
    return render(request, 'wiki/tour_examples/google_oauth.html', {
        'is_tour_example': True,
        'page_title': 'Google Calendar - Пример'
    })


@login_required
def tour_interviewers_example(request):
    """Статическая страница-пример интервьюеров"""
    return render(request, 'wiki/tour_examples/interviewers.html', {
        'is_tour_example': True,
        'page_title': 'Интервьюеры - Пример'
    })







