"""API для управления пользователями"""
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.contrib.auth.models import Group
from logic.base.api_views import BaseAPIViewSet
from logic.base.response_handler import UnifiedResponseHandler
from apps.accounts.models import User
from apps.accounts.serializers import (
    UserSerializer, UserCreateSerializer, UserProfileSerializer,
    UserChangePasswordSerializer, UserSettingsSerializer, GroupSerializer,
    UserStatsSerializer
)
from logic.utilities.account_services import UserService


class UserViewSet(BaseAPIViewSet):
    """ViewSet для управления пользователями"""
    
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]
    search_fields = ['username', 'email', 'first_name', 'last_name', 'full_name']
    ordering_fields = ['username', 'email', 'date_joined', 'last_login']
    ordering = ['username']
    
    def get_serializer_class(self):
        """Выбор сериализатора в зависимости от действия"""
        if self.action == 'create':
            return UserCreateSerializer
        elif self.action in ['profile', 'update_profile']:
            return UserProfileSerializer
        elif self.action == 'change_password':
            return UserChangePasswordSerializer
        elif self.action in ['user_settings', 'update_settings']:
            return UserSettingsSerializer
        return UserSerializer
    
    def get_queryset(self):
        """Фильтрация queryset в зависимости от прав пользователя"""
        user = self.request.user
        queryset = super().get_queryset()
        
        # Если пользователь не админ, показываем только себя
        if not user.is_superuser and not user.is_staff:
            queryset = queryset.filter(pk=user.pk)
        
        return queryset
    
    @action(detail=False, methods=['get'], url_path='profile')
    def profile(self, request):
        """Получение профиля текущего пользователя"""
        try:
            serializer = UserProfileSerializer(request.user)
            
            response_data = UnifiedResponseHandler.success_response(
                serializer.data,
                "Профиль пользователя получен"
            )
            return Response(response_data)
            
        except Exception as e:
            response_data = UnifiedResponseHandler.error_response(str(e))
            return Response(response_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['put'], url_path='profile')
    def update_profile(self, request):
        """Обновление профиля текущего пользователя"""
        try:
            serializer = UserProfileSerializer(request.user, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                
                response_data = UnifiedResponseHandler.success_response(
                    serializer.data,
                    "Профиль пользователя обновлен"
                )
                return Response(response_data)
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
    
    @action(detail=False, methods=['post'], url_path='change-password')
    def change_password(self, request):
        """Смена пароля текущего пользователя"""
        try:
            serializer = UserChangePasswordSerializer(data=request.data, context={'request': request})
            if serializer.is_valid():
                serializer.save()
                
                response_data = UnifiedResponseHandler.success_response(
                    {'message': 'Пароль успешно изменен'},
                    "Пароль изменен"
                )
                return Response(response_data)
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
    
    @action(detail=False, methods=['get'], url_path='settings')
    def user_settings(self, request):
        """Получение настроек текущего пользователя"""
        try:
            serializer = UserSettingsSerializer(request.user)
            
            response_data = UnifiedResponseHandler.success_response(
                serializer.data,
                "Настройки пользователя получены"
            )
            return Response(response_data)
            
        except Exception as e:
            response_data = UnifiedResponseHandler.error_response(str(e))
            return Response(response_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['put'], url_path='settings')
    def update_settings(self, request):
        """Обновление настроек текущего пользователя"""
        try:
            serializer = UserSettingsSerializer(request.user, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                
                response_data = UnifiedResponseHandler.success_response(
                    serializer.data,
                    "Настройки пользователя обновлены"
                )
                return Response(response_data)
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
    
    @action(detail=True, methods=['post'], url_path='assign-groups')
    def assign_groups(self, request, pk=None):
        """Назначение групп пользователю"""
        try:
            user = self.get_object()
            group_ids = request.data.get('group_ids', [])
            
            # Используем сервисный слой для назначения групп
            success, message = UserService.assign_groups_to_user(user, group_ids)
            
            if success:
                response_data = UnifiedResponseHandler.success_response(
                    {'message': message},
                    "Группы назначены"
                )
                return Response(response_data)
            else:
                response_data = UnifiedResponseHandler.error_response(message, 400)
                return Response(response_data, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            response_data = UnifiedResponseHandler.error_response(str(e))
            return Response(response_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'], url_path='stats')
    def stats(self, request):
        """Статистика пользователей"""
        try:
            # Используем сервисный слой для получения статистики
            stats_data = UserService.get_user_stats()
            
            if 'error' in stats_data:
                response_data = UnifiedResponseHandler.error_response(stats_data['error'])
                return Response(response_data, status=status.HTTP_400_BAD_REQUEST)
            
            response_data = UnifiedResponseHandler.success_response(
                stats_data,
                "Статистика пользователей получена"
            )
            return Response(response_data)
            
        except Exception as e:
            response_data = UnifiedResponseHandler.error_response(str(e))
            return Response(response_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'], url_path='integrations')
    def integrations(self, request):
        """Получение статуса интеграций пользователя"""
        try:
            integrations_status = UserService.get_integrations_status(request.user)
            
            response_data = UnifiedResponseHandler.success_response(
                integrations_status,
                "Статус интеграций получен"
            )
            return Response(response_data)
            
        except Exception as e:
            response_data = UnifiedResponseHandler.error_response(str(e))
            return Response(response_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'], url_path='test-api-key')
    def test_api_key(self, request):
        """Тестирование API ключа для интеграции"""
        try:
            integration_type = request.data.get('integration_type')
            api_key = request.data.get('api_key')
            
            if not integration_type or not api_key:
                response_data = UnifiedResponseHandler.error_response(
                    "Тип интеграции и API ключ обязательны",
                    400
                )
                return Response(response_data, status=status.HTTP_400_BAD_REQUEST)
            
            # Используем сервисный слой для тестирования API ключа
            success, message = UserService.test_api_key_integration(
                integration_type, 
                api_key, 
                **request.data
            )
            
            if success:
                response_data = UnifiedResponseHandler.success_response(
                    {'message': message},
                    "API ключ валиден"
                )
                return Response(response_data)
            else:
                response_data = UnifiedResponseHandler.error_response(message, 400)
                return Response(response_data, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            response_data = UnifiedResponseHandler.error_response(str(e))
            return Response(response_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class GroupViewSet(BaseAPIViewSet):
    """ViewSet для просмотра групп пользователей"""
    
    queryset = Group.objects.all()
    serializer_class = GroupSerializer
    permission_classes = [permissions.IsAuthenticated]
    search_fields = ['name']
    ordering_fields = ['name']
    ordering = ['name']

