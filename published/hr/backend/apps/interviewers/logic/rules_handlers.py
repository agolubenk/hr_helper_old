"""
Обработчики для работы с правилами привлечения
Содержит общую логику для views.py и views_api.py
"""
from typing import Dict, Any, Optional
from django.shortcuts import get_object_or_404
from django.contrib import messages
from django.db.models import Q

from ..models import InterviewRule


class RuleHandler:
    """Обработчик для работы с правилами привлечения"""

    @staticmethod
    def search_rules_logic(query: str = '', is_active: Optional[str] = None, 
                          min_grade: Optional[int] = None) -> Q:
        """
        Общая логика поиска правил

        Args:
            query: Поисковый запрос
            is_active: Фильтр по активности
            min_grade: Фильтр по минимальному грейду

        Returns:
            Q: QuerySet фильтр
        """
        filter_q = Q()

        # Поиск по тексту
        if query:
            filter_q &= (
                Q(name__icontains=query) |
                Q(description__icontains=query)
            )

        # Фильтр по активности
        if is_active is not None:
            if is_active == 'true' or is_active == True:
                filter_q &= Q(is_active=True)
            elif is_active == 'false' or is_active == False:
                filter_q &= Q(is_active=False)

        # Фильтр по минимальному грейду
        if min_grade:
            filter_q &= Q(min_grade_id=min_grade)

        return filter_q

    @staticmethod
    def toggle_active_logic(rule_id: int, user=None) -> Dict[str, Any]:
        """
        Общая логика переключения активности правила

        Args:
            rule_id: ID правила
            user: Пользователь Django (для messages)

        Returns:
            Dict[str, Any]: Результат операции
        """
        try:
            rule = get_object_or_404(InterviewRule, pk=rule_id)
            
            # Переключаем активность
            rule.is_active = not rule.is_active
            rule.save()  # Автоматически деактивирует другие правила

            status = 'активировано' if rule.is_active else 'деактивировано'

            # Добавляем сообщение, если пользователь передан
            if user:
                messages.success(user, f'Правило "{rule.name}" {status}!')

            return {
                'success': True,
                'is_active': rule.is_active,
                'message': f'Правило {status}',
                'rule_name': rule.name
            }

        except Exception as e:
            error_message = f'Ошибка: {str(e)}'
            
            if user:
                messages.error(user, error_message)

            return {
                'success': False,
                'message': error_message
            }

    @staticmethod
    def activate_rule_logic(rule_id: int) -> Dict[str, Any]:
        """
        Общая логика активации правила

        Args:
            rule_id: ID правила

        Returns:
            Dict[str, Any]: Результат операции
        """
        try:
            rule = get_object_or_404(InterviewRule, pk=rule_id)
            
            # Активируем правило (деактивирует все остальные)
            InterviewRule.activate_rule(rule.id)

            return {
                'success': True,
                'message': f'Правило "{rule.name}" активировано',
                'rule_name': rule.name,
                'is_active': rule.is_active
            }

        except Exception as e:
            return {
                'success': False,
                'message': f'Ошибка: {str(e)}'
            }

    @staticmethod
    def get_rule_by_id(rule_id: int) -> InterviewRule:
        """
        Получение правила по ID

        Args:
            rule_id: ID правила

        Returns:
            InterviewRule: Объект правила
        """
        return get_object_or_404(InterviewRule, pk=rule_id)

    @staticmethod
    def get_active_rule():
        """
        Получение активного правила

        Returns:
            InterviewRule or None: Активное правило
        """
        return InterviewRule.get_active_rule()

    @staticmethod
    def get_recent_rules(limit: int = 5):
        """
        Получение последних добавленных правил

        Args:
            limit: Максимальное количество

        Returns:
            QuerySet: Последние правила
        """
        return InterviewRule.objects.select_related('min_grade', 'max_grade').order_by('-created_at')[:limit]

    @staticmethod
    def calculate_rule_stats():
        """
        Расчет статистики по правилам

        Returns:
            Dict[str, Any]: Статистика правил
        """
        total_rules = InterviewRule.objects.count()
        active_rules = InterviewRule.objects.filter(is_active=True).count()
        inactive_rules = total_rules - active_rules

        return {
            'total_rules': total_rules,
            'active_rules': active_rules,
            'inactive_rules': inactive_rules
        }

    @staticmethod
    def check_grade_in_range_logic(rule_id: int, grade_id: int) -> Dict[str, Any]:
        """
        Проверка, подходит ли грейд для правила

        Args:
            rule_id: ID правила
            grade_id: ID грейда

        Returns:
            Dict[str, Any]: Результат проверки
        """
        try:
            rule = get_object_or_404(InterviewRule, pk=rule_id)
            
            from apps.finance.models import Grade
            grade = Grade.objects.get(id=grade_id)
            
            is_in_range = rule.is_grade_in_range(grade)

            return {
                'success': True,
                'grade_name': grade.name,
                'rule_name': rule.name,
                'is_in_range': is_in_range,
                'grade_range': rule.get_grade_range()
            }

        except Grade.DoesNotExist:
            return {
                'success': False,
                'message': 'Грейд не найден'
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'Ошибка: {str(e)}'
            }


class RuleApiHandler:
    """Обработчик для API endpoints правил"""

    @staticmethod
    def toggle_active_handler(data: Dict[str, Any], request) -> Dict[str, Any]:
        """
        Обработчик API для переключения активности

        Args:
            data: Данные запроса
            request: HTTP запрос

        Returns:
            Dict[str, Any]: Результат операции
        """
        rule_id = data.get('pk') or data.get('id')
        return RuleHandler.toggle_active_logic(rule_id, request.user)

    @staticmethod
    def activate_handler(data: Dict[str, Any], request) -> Dict[str, Any]:
        """
        Обработчик API для активации правила

        Args:
            data: Данные запроса
            request: HTTP запрос

        Returns:
            Dict[str, Any]: Результат операции
        """
        rule_id = data.get('pk') or data.get('id')
        return RuleHandler.activate_rule_logic(rule_id)

    @staticmethod
    def get_active_handler(data: Dict[str, Any], request) -> Dict[str, Any]:
        """
        Обработчик API для получения активного правила

        Args:
            data: Данные запроса (не используются)
            request: HTTP запрос

        Returns:
            Dict[str, Any]: Активное правило
        """
        active_rule = RuleHandler.get_active_rule()
        
        if active_rule:
            return {
                'success': True,
                'rule': active_rule
            }
        else:
            return {
                'success': False,
                'message': 'Нет активного правила'
            }

    @staticmethod
    def check_grade_handler(data: Dict[str, Any], request) -> Dict[str, Any]:
        """
        Обработчик API для проверки грейда

        Args:
            data: Данные запроса
            request: HTTP запрос

        Returns:
            Dict[str, Any]: Результат проверки
        """
        rule_id = data.get('pk') or data.get('id')
        grade_id = data.get('grade_id')

        if not grade_id:
            return {
                'success': False,
                'message': 'grade_id обязателен'
            }

        return RuleHandler.check_grade_in_range_logic(rule_id, grade_id)

    @staticmethod
    def get_stats_handler(data: Dict[str, Any], request) -> Dict[str, Any]:
        """
        Обработчик API для получения статистики

        Args:
            data: Данные запроса (не используются)
            request: HTTP запрос

        Returns:
            Dict[str, Any]: Статистика правил
        """
        stats = RuleHandler.calculate_rule_stats()
        
        return {
            'success': True,
            **stats
        }

    @staticmethod
    def search_handler(data: Dict[str, Any], request) -> Dict[str, Any]:
        """
        Обработчик API для поиска правил

        Args:
            data: Данные запроса
            request: HTTP запрос

        Returns:
            Dict[str, Any]: Результат поиска
        """
        query = data.get('q', '')
        is_active = data.get('is_active')
        min_grade = data.get('min_grade')

        # Применяем фильтр
        filter_q = RuleHandler.search_rules_logic(query, is_active, min_grade)
        
        # Получаем отфильтрованные правила
        rules = InterviewRule.objects.select_related('min_grade', 'max_grade').filter(filter_q)

        return {
            'success': True,
            'rules': rules,
            'count': rules.count()
        }

