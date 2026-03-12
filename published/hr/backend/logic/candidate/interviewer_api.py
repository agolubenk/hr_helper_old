"""API для работы с интервьюерами"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from logic.base.api_views import BaseAPIViewSet
from logic.base.response_handler import UnifiedResponseHandler
from logic.utilities.context_helpers import PermissionHelper
from apps.interviewers.models import Interviewer, InterviewRule
from apps.interviewers.serializers import (
    InterviewerSerializer, InterviewerCreateSerializer, InterviewerListSerializer,
    InterviewRuleSerializer, InterviewRuleCreateSerializer, InterviewerStatsSerializer
)


class InterviewerViewSet(BaseAPIViewSet):
    """ViewSet для управления интервьюерами"""
    queryset = Interviewer.objects.all()
    serializer_class = InterviewerSerializer
    
    def get_queryset(self):
        """Фильтрация queryset по пользователю"""
        queryset = super().get_queryset()
        # Для интервьюеров нет специфических прав доступа, показываем всех
        return queryset
    
    def create(self, request, *args, **kwargs):
        """Создание нового интервьюера"""
        try:
            serializer = self.get_serializer(data=request.data)
            if serializer.is_valid():
                # Сохраняем интервьюера
                serializer.save()
                
                response_data = UnifiedResponseHandler.success_response(
                    serializer.data, 
                    "Интервьюер успешно создан"
                )
                return Response(response_data, status=status.HTTP_201_CREATED)
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
    
    def update(self, request, *args, **kwargs):
        """Обновление интервьюера"""
        try:
            instance = self.get_object()
            
            # Проверяем права доступа (пока нет специфических прав)
            # if not PermissionHelper.can_user_edit_object(request.user, instance, 'created_by'):
            #     response_data = UnifiedResponseHandler.error_response(
            #         "У вас нет прав для редактирования этого интервьюера",
            #         403
            #     )
            #     return Response(response_data, status=status.HTTP_403_FORBIDDEN)
            
            serializer = self.get_serializer(instance, data=request.data, partial=kwargs.get('partial', False))
            if serializer.is_valid():
                serializer.save()
                
                response_data = UnifiedResponseHandler.success_response(
                    serializer.data,
                    "Интервьюер успешно обновлен"
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
    
    def destroy(self, request, *args, **kwargs):
        """Удаление интервьюера"""
        try:
            instance = self.get_object()
            
            # Проверяем права доступа (пока нет специфических прав)
            # if not PermissionHelper.can_user_edit_object(request.user, instance, 'created_by'):
            #     response_data = UnifiedResponseHandler.error_response(
            #         "У вас нет прав для удаления этого интервьюера",
            #         403
            #     )
            #     return Response(response_data, status=status.HTTP_403_FORBIDDEN)
            
            instance.delete()
            response_data = UnifiedResponseHandler.success_response(
                None,
                "Интервьюер успешно удален"
            )
            return Response(response_data, status=status.HTTP_204_NO_CONTENT)
            
        except Exception as e:
            response_data = UnifiedResponseHandler.error_response(str(e))
            return Response(response_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def get_serializer_class(self):
        """Выбор сериализатора в зависимости от действия"""
        if self.action == 'create':
            return InterviewerCreateSerializer
        elif self.action == 'list':
            return InterviewerListSerializer
        return InterviewerSerializer
    
    @action(detail=True, methods=['post'], url_path='toggle-active')
    def toggle_active(self, request, pk=None):
        """Переключение активности интервьюера"""
        try:
            interviewer = self.get_object()
            
            # Переключаем активность
            interviewer.is_active = not interviewer.is_active
            interviewer.save()
            
            serializer = InterviewerSerializer(interviewer)
            response_data = UnifiedResponseHandler.success_response(
                serializer.data,
                f"Интервьюер {'активирован' if interviewer.is_active else 'деактивирован'}"
            )
            return Response(response_data)
            
        except Exception as e:
            response_data = UnifiedResponseHandler.error_response(str(e))
            return Response(response_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'], url_path='active')
    def active(self, request):
        """Получение только активных интервьюеров"""
        try:
            active_interviewers = self.get_queryset().filter(is_active=True)
            
            serializer = InterviewerListSerializer(active_interviewers, many=True)
            response_data = UnifiedResponseHandler.success_response(
                serializer.data,
                f"Найдено {len(serializer.data)} активных интервьюеров"
            )
            return Response(response_data)
            
        except Exception as e:
            response_data = UnifiedResponseHandler.error_response(str(e))
            return Response(response_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'], url_path='stats')
    def stats(self, request):
        """Статистика по интервьюерам"""
        try:
            queryset = self.get_queryset()
            
            # Основная статистика
            total_interviewers = queryset.count()
            active_interviewers = queryset.filter(is_active=True).count()
            inactive_interviewers = total_interviewers - active_interviewers
            
            # Статистика по именам (первые буквы фамилий)
            from django.db.models import Count
            by_first_letter = dict(
                queryset.values('last_name__first')
                .annotate(count=Count('id'))
                .values_list('last_name__first', 'count')
            )
            
            # Последние интервьюеры
            recent_interviewers = queryset.order_by('-created_at')[:5]
            recent_serializer = InterviewerListSerializer(recent_interviewers, many=True)
            
            stats_data = {
                'total_interviewers': total_interviewers,
                'active_interviewers': active_interviewers,
                'inactive_interviewers': inactive_interviewers,
                'by_first_letter': by_first_letter,
                'recent_interviewers': recent_serializer.data
            }
            
            response_data = UnifiedResponseHandler.success_response(
                stats_data,
                "Статистика получена"
            )
            return Response(response_data)
            
        except Exception as e:
            response_data = UnifiedResponseHandler.error_response(str(e))
            return Response(response_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'], url_path='search')
    def search(self, request):
        """Поиск интервьюеров"""
        try:
            search_term = request.query_params.get('q', '')
            if not search_term:
                response_data = UnifiedResponseHandler.error_response(
                    "Не указан поисковый запрос",
                    400
                )
                return Response(response_data, status=status.HTTP_400_BAD_REQUEST)
            
            from logic.utilities.context_helpers import SearchHelper
            search_fields = ['first_name', 'last_name', 'middle_name', 'email']
            queryset = SearchHelper.filter_queryset_search(
                self.get_queryset(), 
                search_term, 
                search_fields
            )
            
            serializer = self.get_serializer(queryset, many=True)
            response_data = UnifiedResponseHandler.success_response(
                serializer.data,
                f"Найдено {len(serializer.data)} интервьюеров"
            )
            return Response(response_data)
            
        except Exception as e:
            response_data = UnifiedResponseHandler.error_response(str(e))
            return Response(response_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class InterviewRuleViewSet(BaseAPIViewSet):
    """ViewSet для управления правилами интервью"""
    queryset = InterviewRule.objects.all()
    serializer_class = InterviewRuleSerializer
    
    def get_serializer_class(self):
        """Выбор сериализатора в зависимости от действия"""
        if self.action == 'create':
            return InterviewRuleCreateSerializer
        return InterviewRuleSerializer
    
    def create(self, request, *args, **kwargs):
        """Создание нового правила интервью"""
        try:
            serializer = self.get_serializer(data=request.data)
            if serializer.is_valid():
                serializer.save()
                
                response_data = UnifiedResponseHandler.success_response(
                    serializer.data, 
                    "Правило интервью успешно создано"
                )
                return Response(response_data, status=status.HTTP_201_CREATED)
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
    
    def update(self, request, *args, **kwargs):
        """Обновление правила интервью"""
        try:
            instance = self.get_object()
            serializer = self.get_serializer(instance, data=request.data, partial=kwargs.get('partial', False))
            if serializer.is_valid():
                serializer.save()
                
                response_data = UnifiedResponseHandler.success_response(
                    serializer.data,
                    "Правило интервью успешно обновлено"
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
    
    def destroy(self, request, *args, **kwargs):
        """Удаление правила интервью"""
        try:
            instance = self.get_object()
            instance.delete()
            
            response_data = UnifiedResponseHandler.success_response(
                None,
                "Правило интервью успешно удалено"
            )
            return Response(response_data, status=status.HTTP_204_NO_CONTENT)
            
        except Exception as e:
            response_data = UnifiedResponseHandler.error_response(str(e))
            return Response(response_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

