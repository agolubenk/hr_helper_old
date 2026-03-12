"""
Сервис для работы с Google OAuth
Вынесен из views.py для улучшения архитектуры
"""
import requests
import urllib.parse
import secrets
import logging
from django.conf import settings
from django.contrib.auth import get_user_model, login
from django.contrib import messages

User = get_user_model()
logger = logging.getLogger(__name__)


class GoogleOAuthService:
    """Сервис для работы с Google OAuth"""
    
    CLIENT_ID = '968014303116-vtqq5f39tkaningitmj3dbq25snnmdgp.apps.googleusercontent.com'
    CLIENT_SECRET = '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'
    
    @staticmethod
    def get_authorization_url(request):
        """Получить URL для авторизации Google OAuth"""
        redirect_uri = f"{request.scheme}://{request.get_host()}/profile/google-oauth-callback/"
        
        # Генерируем state для безопасности
        state = secrets.token_urlsafe(32)
        request.session['oauth_state'] = state
        
        # Параметры OAuth
        params = {
            'client_id': GoogleOAuthService.CLIENT_ID,
            'redirect_uri': redirect_uri,
            'response_type': 'code',
            'scope': 'openid email profile',
            'state': state,
            'access_type': 'online',
            'prompt': 'select_account'
        }
        
        # Формируем URL для Google OAuth
        google_oauth_url = 'https://accounts.google.com/o/oauth2/v2/auth'
        query_string = urllib.parse.urlencode(params)
        return f"{google_oauth_url}?{query_string}"
    
    @staticmethod
    def handle_oauth_callback(request):
        """Обработка callback от Google OAuth"""
        # Получаем код авторизации
        code = request.GET.get('code')
        state = request.GET.get('state')
        
        logger.info(f"Google OAuth callback: code={code[:20] if code else None}..., state={state}")
        
        # Проверяем state
        session_state = request.session.get('oauth_state')
        logger.info(f"Session state: {session_state}")
        
        if state != session_state:
            logger.error(f"State mismatch: received={state}, expected={session_state}")
            return {'success': False, 'error': 'Ошибка безопасности OAuth'}
        
        if not code:
            logger.error("No authorization code received")
            return {'success': False, 'error': 'Код авторизации не получен'}
        
        try:
            # Обмениваем код на токен
            token_data = GoogleOAuthService._exchange_code_for_token(code, request)
            if not token_data['success']:
                return token_data
            
            access_token = token_data['access_token']
            
            # Получаем информацию о пользователе
            user_info = GoogleOAuthService._get_user_info(access_token)
            if not user_info['success']:
                return user_info
            
            # Создаем или находим пользователя
            user_result = GoogleOAuthService._create_or_get_user(user_info['user_data'])
            if not user_result['success']:
                return user_result
            
            user = user_result['user']
            
            # Авторизуем пользователя
            backend = settings.AUTHENTICATION_BACKENDS[0]
            login(request, user, backend=backend)
            logger.info(f"User {user.username} logged in successfully with backend {backend}")
            
            # Очищаем state из сессии
            if 'oauth_state' in request.session:
                del request.session['oauth_state']
            
            return {
                'success': True,
                'user': user,
                'message': f'Добро пожаловать{" обратно" if user_result["existing"] else ""}, {user.first_name or user.username}!'
            }
            
        except Exception as e:
            logger.error(f"OAuth error: {str(e)}", exc_info=True)
            return {'success': False, 'error': f'Ошибка авторизации: {str(e)}'}
    
    @staticmethod
    def _exchange_code_for_token(code, request):
        """Обмен кода авторизации на токен доступа"""
        token_url = 'https://oauth2.googleapis.com/token'
        redirect_uri = f"{request.scheme}://{request.get_host()}/profile/google-oauth-callback/"
        
        token_data = {
            'client_id': GoogleOAuthService.CLIENT_ID,
            'client_secret': GoogleOAuthService.CLIENT_SECRET,
            'code': code,
            'grant_type': 'authorization_code',
            'redirect_uri': redirect_uri
        }
        
        logger.info(f"Exchanging code for token with redirect_uri: {redirect_uri}")
        
        try:
            token_response = requests.post(token_url, data=token_data)
            token_json = token_response.json()
            
            logger.info(f"Token response status: {token_response.status_code}")
            logger.info(f"Token response: {token_json}")
            
            if 'access_token' not in token_json:
                logger.error(f"No access token in response: {token_json}")
                return {
                    'success': False,
                    'error': f'Ошибка получения токена от Google: {token_json.get("error_description", "Unknown error")}'
                }
            
            return {'success': True, 'access_token': token_json['access_token']}
            
        except Exception as e:
            logger.error(f"Error exchanging code for token: {str(e)}")
            return {'success': False, 'error': f'Ошибка при обмене кода на токен: {str(e)}'}
    
    @staticmethod
    def _get_user_info(access_token):
        """Получение информации о пользователе от Google"""
        user_info_url = 'https://www.googleapis.com/oauth2/v2/userinfo'
        headers = {'Authorization': f'Bearer {access_token}'}
        
        try:
            user_response = requests.get(user_info_url, headers=headers)
            user_info = user_response.json()
            
            logger.info(f"User info response: {user_info}")
            
            if 'email' not in user_info:
                logger.error(f"No email in user info: {user_info}")
                return {'success': False, 'error': 'Не удалось получить информацию о пользователе'}
            
            return {
                'success': True,
                'user_data': {
                    'email': user_info['email'],
                    'first_name': user_info.get('given_name', ''),
                    'last_name': user_info.get('family_name', ''),
                    'name': user_info.get('name', '')
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting user info: {str(e)}")
            return {'success': False, 'error': f'Ошибка при получении информации о пользователе: {str(e)}'}
    
    @staticmethod
    def _create_or_get_user(user_data):
        """Создание или поиск пользователя"""
        email = user_data['email']
        first_name = user_data['first_name']
        last_name = user_data['last_name']
        
        logger.info(f"Processing user: {email}, {first_name} {last_name}")
        
        try:
            # Пытаемся найти пользователя по email
            user = User.objects.get(email=email)
            logger.info(f"Found existing user: {user.username}")
            return {'success': True, 'user': user, 'existing': True}
            
        except User.DoesNotExist:
            # Создаем нового пользователя
            username = email.split('@')[0]
            
            # Проверяем, что username уникален
            original_username = username
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f"{original_username}{counter}"
                counter += 1
            
            user = User.objects.create_user(
                username=username,
                email=email,
                first_name=first_name,
                last_name=last_name
            )
            logger.info(f"Created new user: {username}")
            return {'success': True, 'user': user, 'existing': False}
