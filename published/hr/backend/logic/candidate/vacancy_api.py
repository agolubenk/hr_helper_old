"""API для работы с вакансиями"""
from django.db.models import Q
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from logic.base.api_views import BaseAPIViewSet
from logic.base.response_handler import UnifiedResponseHandler
from logic.utilities.context_helpers import PermissionHelper
from apps.vacancies.models import Vacancy
from apps.vacancies.serializers import VacancySerializer


def _user_can_edit_vacancy(user, vacancy):
    """Доступ: основной рекрутер или один из дополнительных."""
    return (
        user.is_superuser or
        vacancy.recruiter_id == user.pk or
        vacancy.additional_recruiters.filter(pk=user.pk).exists()
    )


class VacancyViewSet(BaseAPIViewSet):
    """ViewSet для управления вакансиями"""
    queryset = Vacancy.objects.all()
    serializer_class = VacancySerializer

    def get_queryset(self):
        """Вакансии, где пользователь — основной или дополнительный рекрутер."""
        queryset = super().get_queryset()
        if self.request.user.is_superuser:
            return queryset
        return queryset.filter(
            Q(recruiter=self.request.user) | Q(additional_recruiters=self.request.user)
        ).distinct()
    
    def create(self, request, *args, **kwargs):
        """Создание новой вакансии"""
        try:
            serializer = self.get_serializer(data=request.data)
            if serializer.is_valid():
                # Сохраняем вакансию
                serializer.save()
                
                response_data = UnifiedResponseHandler.success_response(
                    serializer.data, 
                    "Вакансия успешно создана"
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
        """Обновление вакансии"""
        try:
            instance = self.get_object()
            
            # Проверяем права доступа (основной или один из дополнительных рекрутеров)
            if not _user_can_edit_vacancy(request.user, instance):
                response_data = UnifiedResponseHandler.error_response(
                    "У вас нет прав для редактирования этой вакансии",
                    403
                )
                return Response(response_data, status=status.HTTP_403_FORBIDDEN)

            serializer = self.get_serializer(instance, data=request.data, partial=kwargs.get('partial', False))
            if serializer.is_valid():
                serializer.save()
                
                response_data = UnifiedResponseHandler.success_response(
                    serializer.data,
                    "Вакансия успешно обновлена"
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
        """Удаление вакансии"""
        try:
            instance = self.get_object()
            
            # Проверяем права доступа (основной или один из дополнительных рекрутеров)
            if not _user_can_edit_vacancy(request.user, instance):
                response_data = UnifiedResponseHandler.error_response(
                    "У вас нет прав для удаления этой вакансии",
                    403
                )
                return Response(response_data, status=status.HTTP_403_FORBIDDEN)

            instance.delete()
            response_data = UnifiedResponseHandler.success_response(
                None,
                "Вакансия успешно удалена"
            )
            return Response(response_data, status=status.HTTP_204_NO_CONTENT)
            
        except Exception as e:
            response_data = UnifiedResponseHandler.error_response(str(e))
            return Response(response_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'], url_path='by-external-id')
    def by_external_id(self, request):
        """Получить вакансию по external_id (Huntflow vacancy_id)."""
        try:
            ext = (request.query_params.get('external_id') or '').strip()
            if not ext:
                response_data = UnifiedResponseHandler.error_response("Не указан external_id")
                return Response(response_data, status=status.HTTP_400_BAD_REQUEST)

            try:
                vacancy = self.get_queryset().get(external_id=ext)
            except Vacancy.DoesNotExist:
                response_data = UnifiedResponseHandler.error_response("Вакансия не найдена")
                return Response(response_data, status=status.HTTP_404_NOT_FOUND)

            serializer = self.get_serializer(vacancy)
            response_data = UnifiedResponseHandler.success_response(serializer.data, "OK")
            return Response(response_data)
        except Exception as e:
            response_data = UnifiedResponseHandler.error_response(str(e))
            return Response(response_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def duplicate(self, request, pk=None):
        """Дублирование вакансии"""
        try:
            original_vacancy = self.get_object()
            
            # Проверяем права доступа (основной или один из дополнительных рекрутеров)
            if not _user_can_edit_vacancy(request.user, original_vacancy):
                response_data = UnifiedResponseHandler.error_response(
                    "У вас нет прав для копирования этой вакансии",
                    403
                )
                return Response(response_data, status=status.HTTP_403_FORBIDDEN)

            # Создаем копию
            new_name = request.data.get('name', f"{original_vacancy.name} (копия)")
            vacancy_data = {
                'name': new_name,
                'external_id': f"{original_vacancy.external_id}_copy",
                'recruiter': original_vacancy.recruiter.id,
                'invite_title': original_vacancy.invite_title,
                'invite_text': original_vacancy.invite_text,
                'scorecard_title': original_vacancy.scorecard_title
            }
            
            serializer = self.get_serializer(data=vacancy_data)
            if serializer.is_valid():
                serializer.save()
                
                
                response_data = UnifiedResponseHandler.success_response(
                    serializer.data,
                    "Вакансия успешно скопирована"
                )
                return Response(response_data, status=status.HTTP_201_CREATED)
            else:
                response_data = UnifiedResponseHandler.error_response(
                    "Ошибка при копировании вакансии",
                    400
                )
                response_data['errors'] = serializer.errors
                return Response(response_data, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            response_data = UnifiedResponseHandler.error_response(str(e))
            return Response(response_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def search(self, request):
        """Поиск вакансий"""
        try:
            search_term = request.query_params.get('q', '')
            if not search_term:
                response_data = UnifiedResponseHandler.error_response(
                    "Не указан поисковый запрос",
                    400
                )
                return Response(response_data, status=status.HTTP_400_BAD_REQUEST)
            
            from logic.utilities.context_helpers import SearchHelper
            search_fields = ['name', 'invite_title', 'invite_text', 'scorecard_title']
            queryset = SearchHelper.filter_queryset_search(
                self.get_queryset(), 
                search_term, 
                search_fields
            )
            
            serializer = self.get_serializer(queryset, many=True)
            response_data = UnifiedResponseHandler.success_response(
                serializer.data,
                f"Найдено {len(serializer.data)} вакансий"
            )
            return Response(response_data)
            
        except Exception as e:
            response_data = UnifiedResponseHandler.error_response(str(e))
            return Response(response_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
