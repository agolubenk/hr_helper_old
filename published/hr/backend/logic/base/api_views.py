"""Базовые классы для API views"""
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from logic.base.response_handler import UnifiedResponseHandler

class BaseAPIViewSet(viewsets.ModelViewSet):
    """
    Базовый ViewSet с унифицированными ответами
    
    ВХОДЯЩИЕ ДАННЫЕ: viewsets.ModelViewSet параметры
    ИСТОЧНИКИ ДАННЫХ: Django REST Framework viewsets
    ОБРАБОТКА: Унифицированная обработка CRUD операций с унифицированными ответами
    ВЫХОДЯЩИЕ ДАННЫЕ: Стандартизированные API ответы
    СВЯЗИ: UnifiedResponseHandler, rest_framework
    ФОРМАТ: ModelViewSet с кастомными методами
    """
    
    def handle_exception(self, exc):
        """
        Унифицированная обработка исключений
        
        ВХОДЯЩИЕ ДАННЫЕ: exc (исключение)
        ИСТОЧНИКИ ДАННЫХ: Django REST Framework исключения
        ОБРАБОТКА: Логирование ошибки и возврат унифицированного ответа
        ВЫХОДЯЩИЕ ДАННЫЕ: HTTP 500 ответ с деталями ошибки
        СВЯЗИ: UnifiedResponseHandler.error_response()
        ФОРМАТ: Response с error_response
        """
        # Важно: DRF исключения (NotAuthenticated/PermissionDenied/ValidationError и т.п.)
        # должны отдавать корректный HTTP статус, иначе клиентам (в т.ч. расширению)
        # невозможно отличать 401/403 от реальной 500.
        try:
            from rest_framework.exceptions import APIException
        except Exception:
            APIException = None

        if APIException is not None and isinstance(exc, APIException):
            detail = getattr(exc, "detail", str(exc))
            # detail может быть dict/list/str
            return Response(
                UnifiedResponseHandler.error_response(str(detail), getattr(exc, "status_code", 400)),
                status=getattr(exc, "status_code", status.HTTP_400_BAD_REQUEST),
            )

        import traceback
        error_msg = f"BaseAPIViewSet error: {str(exc)}\n{traceback.format_exc()}"
        print(f"🚨 BaseAPIViewSet.handle_exception: {error_msg}")
        return Response(
            UnifiedResponseHandler.error_response(error_msg),
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    
    def create(self, request, *args, **kwargs):
        """
        Создание с унифицированным ответом
        
        ВХОДЯЩИЕ ДАННЫЕ: request (HTTP запрос), *args, **kwargs
        ИСТОЧНИКИ ДАННЫЕ: Django REST Framework request данные
        ОБРАБОТКА: Валидация и создание объекта с унифицированным ответом
        ВЫХОДЯЩИЕ ДАННЫЕ: HTTP 201 ответ с созданными данными
        СВЯЗИ: UnifiedResponseHandler.success_response()
        ФОРМАТ: Response с success_response или error_response
        """
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            instance = serializer.save()
            return Response(
                UnifiedResponseHandler.success_response(
                    serializer.data,
                    "Created successfully"
                ),
                status=status.HTTP_201_CREATED
            )
        except Exception as e:
            import traceback
            error_msg = f"BaseAPIViewSet.create error: {str(e)}\n{traceback.format_exc()}"
            return Response(
                UnifiedResponseHandler.error_response(error_msg),
                status=status.HTTP_400_BAD_REQUEST
            )
    
    def update(self, request, *args, **kwargs):
        """
        Обновление с унифицированным ответом
        
        ВХОДЯЩИЕ ДАННЫЕ: request (HTTP запрос), *args, **kwargs
        ИСТОЧНИКИ ДАННЫЕ: Django REST Framework request данные
        ОБРАБОТКА: Валидация и обновление объекта с унифицированным ответом
        ВЫХОДЯЩИЕ ДАННЫЕ: HTTP 200 ответ с обновленными данными
        СВЯЗИ: UnifiedResponseHandler.success_response()
        ФОРМАТ: Response с success_response или error_response
        """
        try:
            partial = kwargs.pop('partial', False)
            instance = self.get_object()
            serializer = self.get_serializer(instance, data=request.data, partial=partial)
            serializer.is_valid(raise_exception=True)
            instance = serializer.save()
            return Response(
                UnifiedResponseHandler.success_response(
                    serializer.data,
                    "Updated successfully"
                )
            )
        except Exception as e:
            return Response(
                UnifiedResponseHandler.error_response(str(e)),
                status=status.HTTP_400_BAD_REQUEST
            )
    
    def destroy(self, request, *args, **kwargs):
        """
        Удаление с унифицированным ответом
        
        ВХОДЯЩИЕ ДАННЫЕ: request (HTTP запрос), *args, **kwargs
        ИСТОЧНИКИ ДАННЫЕ: Django REST Framework request данные
        ОБРАБОТКА: Удаление объекта с унифицированным ответом
        ВЫХОДЯЩИЕ ДАННЫЕ: HTTP 204 ответ об успешном удалении
        СВЯЗИ: UnifiedResponseHandler.success_response()
        ФОРМАТ: Response с success_response или error_response
        """
        try:
            instance = self.get_object()
            instance.delete()
            return Response(
                UnifiedResponseHandler.success_response(
                    message="Deleted successfully"
                ),
                status=status.HTTP_204_NO_CONTENT
            )
        except Exception as e:
            return Response(
                UnifiedResponseHandler.error_response(str(e)),
                status=status.HTTP_400_BAD_REQUEST
            )
    
    def list(self, request, *args, **kwargs):
        """
        Список с унифицированным ответом
        
        ВХОДЯЩИЕ ДАННЫЕ: request (HTTP запрос), *args, **kwargs
        ИСТОЧНИКИ ДАННЫЕ: Django REST Framework request данные
        ОБРАБОТКА: Получение списка объектов с пагинацией и унифицированным ответом
        ВЫХОДЯЩИЕ ДАННЫЕ: HTTP 200 ответ со списком данных
        СВЯЗИ: UnifiedResponseHandler.success_response()
        ФОРМАТ: Response с success_response или error_response
        """
        try:
            queryset = self.filter_queryset(self.get_queryset())
            page = self.paginate_queryset(queryset)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data)
            
            serializer = self.get_serializer(queryset, many=True)
            return Response(
                UnifiedResponseHandler.success_response(serializer.data)
            )
        except Exception as e:
            return Response(
                UnifiedResponseHandler.error_response(str(e)),
                status=status.HTTP_400_BAD_REQUEST
            )
    
    def retrieve(self, request, *args, **kwargs):
        """
        Получение одного объекта с унифицированным ответом
        
        ВХОДЯЩИЕ ДАННЫЕ: request (HTTP запрос), *args, **kwargs
        ИСТОЧНИКИ ДАННЫЕ: Django REST Framework request данные
        ОБРАБОТКА: Получение одного объекта по ID с унифицированным ответом
        ВЫХОДЯЩИЕ ДАННЫЕ: HTTP 200 ответ с данными объекта
        СВЯЗИ: UnifiedResponseHandler.success_response()
        ФОРМАТ: Response с success_response или error_response
        """
        try:
            instance = self.get_object()
            serializer = self.get_serializer(instance)
            return Response(
                UnifiedResponseHandler.success_response(serializer.data)
            )
        except Exception as e:
            return Response(
                UnifiedResponseHandler.error_response(str(e)),
                status=status.HTTP_400_BAD_REQUEST
            )

class FinanceAPIViewSet(BaseAPIViewSet):
    """
    Специализированный ViewSet для Finance приложения
    
    ВХОДЯЩИЕ ДАННЫЕ: BaseAPIViewSet параметры
    ИСТОЧНИКИ ДАННЫЕ: Django REST Framework viewsets
    ОБРАБОТКА: Специализированная обработка для Finance приложения
    ВЫХОДЯЩИЕ ДАННЫЕ: Стандартизированные API ответы для Finance
    СВЯЗИ: UnifiedResponseHandler, logging
    ФОРМАТ: ModelViewSet с Finance-специфичной обработкой
    """
    
    def handle_exception(self, exc):
        """
        Специальная обработка исключений для Finance
        
        ВХОДЯЩИЕ ДАННЫЕ: exc (исключение)
        ИСТОЧНИКИ ДАННЫЕ: Django REST Framework исключения
        ОБРАБОТКА: Логирование в Finance логгер и возврат унифицированного ответа
        ВЫХОДЯЩИЕ ДАННЫЕ: HTTP 500 ответ с Finance-специфичным кодом ошибки
        СВЯЗИ: UnifiedResponseHandler.error_response(), logging
        ФОРМАТ: Response с error_response и FINANCE_API_ERROR кодом
        """
        import logging
        logger = logging.getLogger('apps.finance')
        logger.error(f"Finance API error: {exc}")
        
        return Response(
            UnifiedResponseHandler.error_response(
                str(exc),
                error_code="FINANCE_API_ERROR"
            ),
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
