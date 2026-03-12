from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Count, Q
from .models import Interviewer, InterviewRule
from .serializers import (
    InterviewerSerializer, InterviewerCreateSerializer, InterviewerListSerializer,
    InterviewRuleSerializer, InterviewRuleCreateSerializer, InterviewerStatsSerializer
)
from logic.candidate.interviewer_api import InterviewerViewSet as LogicInterviewerViewSet, InterviewRuleViewSet as LogicInterviewRuleViewSet


class InterviewerViewSet(LogicInterviewerViewSet):
    """ViewSet для управления интервьюерами - расширенная версия"""
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ['is_active']
    search_fields = ['first_name', 'last_name', 'middle_name', 'email']
    ordering_fields = ['first_name', 'last_name', 'email', 'created_at']
    ordering = ['last_name', 'first_name']


class InterviewRuleViewSet(LogicInterviewRuleViewSet):
    """ViewSet для управления правилами интервью - расширенная версия"""
    permission_classes = [permissions.IsAuthenticated]