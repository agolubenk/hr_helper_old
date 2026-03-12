"""Совместимость для Interviewers приложения"""
import warnings
from apps.interviewers.views import * as old_interviewer_views
from logic.candidate.interviewer_management import * as new_interviewer_views

def get_interviewer_views():
    """Получить views для интервьюеров (новые или старые)"""
    warnings.warn(
        "Old interviewer views are deprecated. Use logic.candidate.interviewer_management",
        DeprecationWarning,
        stacklevel=2
    )
    return new_interviewer_views

# Экспорт основных функций для совместимости
interviewer_list = new_interviewer_views.interviewer_list
interviewer_detail = new_interviewer_views.interviewer_detail
interviewer_create = new_interviewer_views.interviewer_create
interviewer_edit = new_interviewer_views.interviewer_edit
interviewer_delete = new_interviewer_views.interviewer_delete
interviewer_toggle_active = new_interviewer_views.interviewer_toggle_active

interview_rule_list = new_interviewer_views.interview_rule_list
interview_rule_detail = new_interviewer_views.interview_rule_detail
interview_rule_create = new_interviewer_views.interview_rule_create
interview_rule_edit = new_interviewer_views.interview_rule_edit
interview_rule_delete = new_interviewer_views.interview_rule_delete

