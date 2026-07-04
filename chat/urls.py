from django.urls import path
from . import views

urlpatterns = [
    path('', views.chat_hub, name='chat_hub'),
    path('<int:conversation_id>/', views.chat_hub, name='chat_room'),
    path('start/<int:owner_id>/', views.start_conversation, name='start_conversation'),
    path('<int:conversation_id>/poll/', views.poll_messages, name='poll_messages'),
    path('ai-assistant/', views.ai_assistant, name='ai_assistant'),
]

