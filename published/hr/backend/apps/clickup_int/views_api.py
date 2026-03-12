from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model

from .models import ClickUpSettings, ClickUpTask, ClickUpSyncLog, ClickUpBulkImport
from .serializers import (
    ClickUpSettingsSerializer, ClickUpTaskSerializer, 
    ClickUpSyncLogSerializer, ClickUpBulkImportSerializer,
    ClickUpBulkImportCreateSerializer, ClickUpStatsSerializer,
    ClickUpApiRequestSerializer
)
from logic.integration.clickup.clickup_api import (
    ClickUpSettingsViewSet as LogicClickUpSettingsViewSet,
    ClickUpTaskViewSet as LogicClickUpTaskViewSet,
    ClickUpSyncLogViewSet as LogicClickUpSyncLogViewSet,
    ClickUpBulkImportViewSet as LogicClickUpBulkImportViewSet
)

User = get_user_model()


class ClickUpSettingsViewSet(LogicClickUpSettingsViewSet):
    """ViewSet для управления настройками ClickUp - расширенная версия"""
    permission_classes = [permissions.IsAuthenticated]


class ClickUpTaskViewSet(LogicClickUpTaskViewSet):
    """ViewSet для управления задачами ClickUp - расширенная версия"""
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ['status', 'priority', 'assignee']
    search_fields = ['name', 'description']
    ordering_fields = ['date_created', 'date_updated', 'priority']
    ordering = ['-date_updated']


class ClickUpSyncLogViewSet(LogicClickUpSyncLogViewSet):
    """ViewSet для просмотра логов синхронизации ClickUp - расширенная версия"""
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ['status']
    search_fields = ['message']
    ordering_fields = ['created_at']
    ordering = ['-created_at']


class ClickUpBulkImportViewSet(LogicClickUpBulkImportViewSet):
    """ViewSet для управления массовым импортом ClickUp - расширенная версия"""
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ['status']
    ordering_fields = ['created_at']
    ordering = ['-created_at']