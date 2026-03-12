"""Помощники для работы с контекстом и данными"""
from django.contrib.auth.models import User
from django.db.models import Q
from logic.base.response_handler import UnifiedResponseHandler
import json

class ContextHelper:
    """Класс для работы с контекстом страниц"""
    
    @staticmethod
    def get_base_context(request, title="", extra_data=None):
        """Получение базового контекста для страниц"""
        try:
            context = {
                'title': title,
                'user': request.user,
                'is_authenticated': request.user.is_authenticated,
                'user_permissions': request.user.get_all_permissions() if request.user.is_authenticated else set(),
            }
            
            if extra_data:
                context.update(extra_data)
                
            return context
        except Exception as e:
            return {'error': str(e), 'title': title}
    
    @staticmethod
    def get_pagination_context(queryset, page_number=1, per_page=20):
        """Получение контекста для пагинации"""
        try:
            from django.core.paginator import Paginator
            
            paginator = Paginator(queryset, per_page)
            page_obj = paginator.get_page(page_number)
            
            return {
                'page_obj': page_obj,
                'paginator': paginator,
                'has_previous': page_obj.has_previous(),
                'has_next': page_obj.has_next(),
                'previous_page_number': page_obj.previous_page_number() if page_obj.has_previous() else None,
                'next_page_number': page_obj.next_page_number() if page_obj.has_next() else None,
                'num_pages': paginator.num_pages,
                'current_page': page_obj.number
            }
        except Exception as e:
            return {'error': str(e)}

class DataHelper:
    """Класс для работы с данными"""
    
    @staticmethod
    def safe_json_loads(json_string, default=None):
        """Безопасная загрузка JSON"""
        try:
            return json.loads(json_string)
        except (json.JSONDecodeError, TypeError):
            return default or {}
    
    @staticmethod
    def safe_json_dumps(data, default="{}"):
        """Безопасная сериализация в JSON"""
        try:
            return json.dumps(data, ensure_ascii=False, indent=2)
        except (TypeError, ValueError):
            return default
    
    @staticmethod
    def filter_queryset_by_user(queryset, user, user_field='created_by'):
        """Фильтрация queryset по пользователю"""
        try:
            if user.is_superuser:
                return queryset
            return queryset.filter(**{user_field: user})
        except Exception:
            return queryset.none()

class SearchHelper:
    """Класс для работы с поиском"""
    
    @staticmethod
    def build_search_query(search_fields, search_term):
        """Построение поискового запроса"""
        if not search_term or not search_fields:
            return Q()
        
        query = Q()
        for field in search_fields:
            query |= Q(**{f"{field}__icontains": search_term})
        
        return query
    
    @staticmethod
    def filter_queryset_search(queryset, search_term, search_fields):
        """Фильтрация queryset по поисковому запросу"""
        try:
            if not search_term:
                return queryset
            
            search_query = SearchHelper.build_search_query(search_fields, search_term)
            return queryset.filter(search_query)
        except Exception:
            return queryset

class PermissionHelper:
    """Класс для работы с правами доступа"""
    
    @staticmethod
    def check_user_permission(user, permission_name):
        """Проверка права пользователя"""
        try:
            return user.is_superuser or user.has_perm(permission_name)
        except Exception:
            return False
    
    @staticmethod
    def get_user_accessible_objects(queryset, user, permission_field='created_by'):
        """Получение объектов, доступных пользователю"""
        try:
            if user.is_superuser:
                return queryset
            
            return queryset.filter(**{permission_field: user})
        except Exception:
            return queryset.none()
    
    @staticmethod
    def can_user_edit_object(user, obj, owner_field='created_by'):
        """Проверка возможности редактирования объекта пользователем"""
        try:
            if user.is_superuser:
                return True
            
            if hasattr(obj, owner_field):
                return getattr(obj, owner_field) == user
            
            return False
        except Exception:
            return False
