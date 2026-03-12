from django.urls import path
from . import views

app_name = 'answer_library'

urlpatterns = [
    path('', views.library_index, name='index'),
    path('topics/', views.topic_list, name='topic_list'),
    path('topics/create/', views.topic_create, name='topic_create'),
    path('topics/<int:pk>/edit/', views.topic_edit, name='topic_edit'),
    path('topics/<int:pk>/delete/', views.topic_delete, name='topic_delete'),
    path('topics/export/', views.topic_export_json, name='topic_export_json'),
    path('topics/import/', views.topic_import_json, name='topic_import_json'),
    path('chat/', views.chat, name='chat'),
    path('chat/<int:session_id>/', views.chat, name='chat_session'),  # редирект на общий чат
    path('api/send-message/', views.send_message, name='send_message'),
    path('api/clear-history/', views.clear_chat_history, name='clear_history'),
]
