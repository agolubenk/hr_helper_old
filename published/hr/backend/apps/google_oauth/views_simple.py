from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth import get_user_model, login
import requests

from .models import GoogleOAuthAccount

User = get_user_model()

def google_oauth_callback_simple(request):
    """Упрощенный callback от Google OAuth"""
    print(f"=== SIMPLE OAUTH CALLBACK DEBUG ===")
    print(f"GET params: {request.GET}")

    state = request.session.get('google_oauth_state')
    if not state:
        print("❌ State not found in session")
        messages.error(request, 'Ошибка авторизации: неверный state')
        return redirect('accounts:account_login')

    code = request.GET.get('code')
    if not code:
        print("❌ Code not found in GET params")
        messages.error(request, 'Ошибка авторизации: код не получен')
        return redirect('accounts:account_login')

    print(f"✅ Code received: {code[:20]}...")
    print(f"✅ State: {state[:20]}...")

    try:
        # Получаем токены напрямую через requests
        token_url = 'https://oauth2.googleapis.com/token'
        token_data = {
            'client_id': settings.GOOGLE_OAUTH2_CLIENT_ID,
            'client_secret': settings.GOOGLE_OAUTH2_CLIENT_SECRET,
            'code': code,
            'grant_type': 'authorization_code',
            'redirect_uri': settings.GOOGLE_OAUTH_REDIRECT_URI,
        }
        
        print(f"🔄 Requesting tokens from Google...")
        token_response = requests.post(token_url, data=token_data)
        token_response.raise_for_status()
        tokens = token_response.json()
        
        print(f"✅ Tokens received:")
        print(f"   - Access Token: {'Есть' if tokens.get('access_token') else 'Нет'}")
        print(f"   - Refresh Token: {'Есть' if tokens.get('refresh_token') else 'Нет'}")
        
        # Получаем данные пользователя из Google
        user_info_url = 'https://www.googleapis.com/oauth2/v2/userinfo'
        headers = {'Authorization': f"Bearer {tokens['access_token']}"}
        user_info_response = requests.get(user_info_url, headers=headers)
        user_info_response.raise_for_status()
        user_info = user_info_response.json()
        
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
            username = f'google_user_{int(timezone.now().timestamp())}'
            user = User.objects.create(
                username=username,
                email=f'user_{int(timezone.now().timestamp())}@google.com',
                first_name=google_name.split(' ')[0] if google_name else 'Google',
                last_name=' '.join(google_name.split(' ')[1:]) if len(google_name.split(' ')) > 1 else 'User',
                is_active=True,
            )
            print(f"✅ Создан пользователь без email: {user.username}")

        # Создаем или обновляем OAuth аккаунт
        oauth_account, created = GoogleOAuthAccount.objects.get_or_create(
            user=user,
            defaults={
                'google_id': user_info.get('id', ''),
                'email': google_email or user.email,
                'name': google_name or user.first_name or user.username,
                'picture_url': user_info.get('picture', ''),
                'access_token': tokens.get('access_token'),
                'refresh_token': tokens.get('refresh_token'),
                'token_expires_at': timezone.now() + timedelta(seconds=tokens.get('expires_in', 3600)),
                'scopes': [
                    'https://www.googleapis.com/auth/userinfo.email',
                    'https://www.googleapis.com/auth/userinfo.profile',
                    'https://www.googleapis.com/auth/calendar',
                    'https://www.googleapis.com/auth/drive',
                    'https://www.googleapis.com/auth/spreadsheets',
                ]
            }
        )
        
        # Если аккаунт уже существовал, обновляем токены
        if not created:
            oauth_account.google_id = user_info.get('id', '')
            oauth_account.email = google_email or user.email
            oauth_account.name = google_name or user.first_name or user.username
            oauth_account.picture_url = user_info.get('picture', '')
            oauth_account.access_token = tokens.get('access_token')
            oauth_account.refresh_token = tokens.get('refresh_token')
            oauth_account.token_expires_at = timezone.now() + timedelta(seconds=tokens.get('expires_in', 3600))
            oauth_account.scopes = [
                'https://www.googleapis.com/auth/userinfo.email',
                'https://www.googleapis.com/auth/userinfo.profile',
                'https://www.googleapis.com/auth/calendar',
                'https://www.googleapis.com/auth/drive',
                'https://www.googleapis.com/auth/spreadsheets',
            ]
            oauth_account.save()
            print(f"✅ Обновлен существующий OAuth аккаунт для пользователя: {user.username}")
        else:
            print(f"✅ Создан новый OAuth аккаунт для пользователя: {user.username}")
        print(f"✅ OAuth account created: {oauth_account.id}")

        # Удаляем state из сессии
        if 'google_oauth_state' in request.session:
            del request.session['google_oauth_state']

        # Авторизуем пользователя
        login(request, user)

        print(f"✅ User logged in: {user.username}")
        print(f"✅ Redirecting to dashboard")

        messages.success(request, f'Добро пожаловать, {user.first_name}! Google аккаунт {google_email} успешно подключен!')
        return redirect('huntflow:dashboard')

    except Exception as e:
        print(f"❌ Error in callback: {e}")
        import traceback
        traceback.print_exc()
        messages.error(request, f'Ошибка при подключении Google аккаунта: {str(e)}')
        return redirect('accounts:account_login')
