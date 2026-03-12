"""API views для Accounts приложения - расширенные версии"""
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.contrib.auth.models import Group
from .models import User
from .serializers import (
    UserSerializer, UserCreateSerializer, UserProfileSerializer,
    UserChangePasswordSerializer, UserSettingsSerializer, GroupSerializer,
    UserStatsSerializer, IntegrationStatusSerializer, ApiKeyTestSerializer
)
from logic.utilities.user_api import UserViewSet as LogicUserViewSet, GroupViewSet as LogicGroupViewSet
from logic.base.response_handler import UnifiedResponseHandler
from rest_framework.authtoken.models import Token


class UserViewSet(LogicUserViewSet):
    """
    ViewSet для управления пользователями - расширенная версия
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - HTTP запросы (GET, POST, PUT, DELETE, PATCH)
    - request.user: аутентифицированный пользователь
    
    ИСТОЧНИКИ ДАННЫЕ:
    - User.objects: все пользователи системы
    - UserSerializer, UserCreateSerializer, UserProfileSerializer, UserChangePasswordSerializer, UserSettingsSerializer
    
    ОБРАБОТКА:
    - Наследование от LogicUserViewSet
    - Расширенные методы для работы с пользователями
    - Управление профилями и настройками пользователей
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - DRF Response с данными пользователей
    - JSON ответы через UnifiedResponseHandler
    
    СВЯЗИ:
    - Использует: LogicUserViewSet, UserSerializer, UnifiedResponseHandler
    - Передает: DRF API responses
    - Может вызываться из: DRF API endpoints
    """
    
    permission_classes = [permissions.IsAuthenticated]
    
    @action(detail=False, methods=['get'])
    def profile_dashboard(self, request):
        """
        Получить данные профиля для дашборда
        
        ВХОДЯЩИЕ ДАННЫЕ:
        - request.user: аутентифицированный пользователь
        
        ИСТОЧНИКИ ДАННЫЕ:
        - request.user: текущий пользователь
        - UserService: сервис для работы с пользователями
        
        ОБРАБОТКА:
        - Получение данных профиля пользователя
        - Формирование данных для дашборда
        - Формирование ответа через UnifiedResponseHandler
        
        ВЫХОДЯЩИЕ ДАННЫЕ:
        - DRF Response с данными профиля для дашборда
        
        СВЯЗИ:
        - Использует: UserService, UnifiedResponseHandler
        - Передает: DRF Response
        - Может вызываться из: DRF API endpoints
        """
        try:
            from logic.utilities.account_services import UserService
            
            profile_data = UserService.get_user_profile_data(request.user)
            # Сериализуем для JSON: модели user и oauth_account не сериализуются автоматически
            user = profile_data.get('user')
            payload = {
                'user': {
                    'id': user.id,
                    'username': getattr(user, 'username', None),
                    'email': getattr(user, 'email', None),
                    'first_name': getattr(user, 'first_name', None),
                    'last_name': getattr(user, 'last_name', None),
                } if user else None,
                'social_accounts': profile_data.get('social_accounts', []),
                'is_google_oauth_connected': profile_data.get('is_google_oauth_connected', False),
                'is_google_social_connected': profile_data.get('is_google_social_connected', False),
                'token_valid': profile_data.get('token_valid', False),
                'google_stats': profile_data.get('google_stats', {}),
                'user_groups': profile_data.get('user_groups', []),
                'integrations': profile_data.get('integrations', {}),
            }
            response_data = UnifiedResponseHandler.success_response(
                payload,
                "Данные профиля получены"
            )
            return Response(response_data)
            
        except Exception as e:
            response_data = UnifiedResponseHandler.error_response(str(e))
            return Response(response_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def update_api_keys(self, request):
        """
        Обновление API ключей пользователя
        
        ВХОДЯЩИЕ ДАННЫЕ:
        - request.data: данные с API ключами для обновления
        - request.user: аутентифицированный пользователь
        
        ИСТОЧНИКИ ДАННЫЕ:
        - request.data: API ключи для обновления
        - request.user: пользователь для обновления ключей
        - UserService: сервис для работы с пользователями
        
        ОБРАБОТКА:
        - Получение API ключей из данных запроса
        - Обновление API ключей пользователя
        - Валидация ключей
        - Формирование ответа через UnifiedResponseHandler
        
        ВЫХОДЯЩИЕ ДАННЫЕ:
        - DRF Response с результатом операции
        
        СВЯЗИ:
        - Использует: UserService, UnifiedResponseHandler
        - Передает: DRF Response
        - Может вызываться из: DRF API endpoints
        """
        try:
            from logic.utilities.account_services import UserService
            
            success, message = UserService.update_user_api_keys(request.user, request.data)
            
            if success:
                response_data = UnifiedResponseHandler.success_response(
                    {'message': message},
                    "API ключи обновлены"
                )
                return Response(response_data)
            else:
                response_data = UnifiedResponseHandler.error_response(message, 400)
                return Response(response_data, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            response_data = UnifiedResponseHandler.error_response(str(e))
            return Response(response_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def test_integration(self, request):
        """
        Тестирование интеграции
        
        ВХОДЯЩИЕ ДАННЫЕ:
        - request.data: данные для тестирования интеграции
        - request.user: аутентифицированный пользователь
        
        ИСТОЧНИКИ ДАННЫЕ:
        - request.data: данные для тестирования
        - request.user: пользователь для тестирования
        - UserService: сервис для работы с пользователями
        
        ОБРАБОТКА:
        - Получение данных для тестирования
        - Тестирование интеграции
        - Проверка подключения к внешним сервисам
        - Формирование ответа через UnifiedResponseHandler
        
        ВЫХОДЯЩИЕ ДАННЫЕ:
        - DRF Response с результатом тестирования
        
        СВЯЗИ:
        - Использует: UserService, UnifiedResponseHandler
        - Передает: DRF Response
        - Может вызываться из: DRF API endpoints
        """
        try:
            serializer = ApiKeyTestSerializer(data=request.data)
            if serializer.is_valid():
                from logic.utilities.account_services import UserService
                
                success, message = UserService.test_api_key_integration(
                    serializer.validated_data['integration_type'],
                    serializer.validated_data['api_key'],
                    **serializer.validated_data
                )
                
                if success:
                    response_data = UnifiedResponseHandler.success_response(
                        {'message': message},
                        "Интеграция протестирована"
                    )
                    return Response(response_data)
                else:
                    response_data = UnifiedResponseHandler.error_response(message, 400)
                    return Response(response_data, status=status.HTTP_400_BAD_REQUEST)
            else:
                response_data = UnifiedResponseHandler.error_response(
                    "Ошибка валидации данных",
                    400
                )
                response_data['errors'] = serializer.errors
                return Response(response_data, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            response_data = UnifiedResponseHandler.error_response(str(e))
            return Response(response_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get', 'post'], url_path='reminder-phrase')
    def reminder_phrase(self, request):
        """
        GET: возвращает расшифрованную фразу-напоминание текущего пользователя.
        POST: сохраняет фразу (тело: {"reminder_phrase": "..."}).
        /api/v1/accounts/users/reminder_phrase/
        """
        try:
            from apps.accounts.models import UserReminderPhrase
            from apps.accounts.encryption import decrypt_for_user, encrypt_for_user

            if request.method == 'POST':
                phrase = (request.data.get('reminder_phrase') or '').strip()
                obj, _ = UserReminderPhrase.objects.get_or_create(user=request.user)
                obj.encrypted_value = encrypt_for_user(request.user, phrase)
                obj.save()
                return Response(
                    UnifiedResponseHandler.success_response(
                        {"reminder_phrase": phrase},
                        "Фраза-напоминание сохранена"
                    ),
                    status=status.HTTP_200_OK
                )

            obj = UserReminderPhrase.objects.filter(user=request.user).first()
            phrase = ""
            if obj and obj.encrypted_value:
                phrase = decrypt_for_user(request.user, obj.encrypted_value)

            return Response(
                UnifiedResponseHandler.success_response(
                    {"reminder_phrase": phrase},
                    "OK"
                ),
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response(
                UnifiedResponseHandler.error_response(str(e)),
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'], url_path='token')
    def token(self, request):
        """
        Возвращает (или создает) DRF Token для текущего пользователя.
        Удобно для интеграций, где cookies недоступны (например, Chrome extension на LinkedIn).
        
        GET /api/v1/accounts/users/token/
        """
        try:
            token, _ = Token.objects.get_or_create(user=request.user)
            return Response(
                UnifiedResponseHandler.success_response(
                    {"token": token.key},
                    "Токен получен"
                ),
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response(
                UnifiedResponseHandler.error_response(str(e)),
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class GroupViewSet(LogicGroupViewSet):
    """
    ViewSet для просмотра групп пользователей - расширенная версия
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - HTTP запросы (GET, POST, PUT, DELETE, PATCH)
    - request.user: аутентифицированный пользователь
    
    ИСТОЧНИКИ ДАННЫЕ:
    - Group.objects: все группы пользователей
    - GroupSerializer: для сериализации групп
    
    ОБРАБОТКА:
    - Наследование от LogicGroupViewSet
    - Расширенные методы для работы с группами
    - Управление пользователями в группах
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - DRF Response с данными групп
    - JSON ответы через UnifiedResponseHandler
    
    СВЯЗИ:
    - Использует: LogicGroupViewSet, GroupSerializer, UnifiedResponseHandler
    - Передает: DRF API responses
    - Может вызываться из: DRF API endpoints
    """
    
    permission_classes = [permissions.IsAuthenticated]
    
    @action(detail=True, methods=['get'])
    def users(self, request, pk=None):
        """
        Получить пользователей группы
        
        ВХОДЯЩИЕ ДАННЫЕ:
        - pk: ID группы для получения пользователей
        - request.user: аутентифицированный пользователь
        
        ИСТОЧНИКИ ДАННЫЕ:
        - URL параметр pk
        - Group.objects: конкретная группа
        - User.objects: пользователи группы
        
        ОБРАБОТКА:
        - Получение группы по ID
        - Получение пользователей группы
        - Сериализация данных пользователей
        - Формирование ответа через UnifiedResponseHandler
        
        ВЫХОДЯЩИЕ ДАННЫЕ:
        - DRF Response с данными пользователей группы
        
        СВЯЗИ:
        - Использует: UserSerializer, UnifiedResponseHandler
        - Передает: DRF Response
        - Может вызываться из: DRF API endpoints
        """
        try:
            group = self.get_object()
            users = group.user_set.all()
            serializer = UserSerializer(users, many=True)
            
            response_data = UnifiedResponseHandler.success_response(
                serializer.data,
                f"Пользователи группы '{group.name}' получены"
            )
            return Response(response_data)
            
        except Exception as e:
            response_data = UnifiedResponseHandler.error_response(str(e))
            return Response(response_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)