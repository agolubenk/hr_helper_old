"""
Адаптеры для аутентификации и социальных аккаунтов
Объединяет логику из adapters.py с использованием сервисного слоя
"""
from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib import messages

from .user_service import UserService

User = get_user_model()


class CustomAccountAdapter(DefaultAccountAdapter):
    """Адаптер для кастомной модели пользователя"""
    
    def save_user(self, request, user, form, commit=True):
        """Сохраняет пользователя с дополнительными полями"""
        user = super().save_user(request, user, form, commit=False)
        
        # Дополнительные поля обрабатываются автоматически
        
        if commit:
            user.save()
        
        return user


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    """Адаптер для социальных аккаунтов с использованием сервисного слоя"""
    
    def pre_social_login(self, request, sociallogin):
        """
        Связываем существующих пользователей по email при входе через Google
        """
        user = sociallogin.user
        if user.email:
            try:
                # Используем сервисный слой для связывания аккаунтов
                existing_user = UserService.link_social_account_to_existing_user(sociallogin, user.email)
                
                if existing_user:
                    print(f"🔍 OAUTH: Найден существующий пользователь: {existing_user.username} ({existing_user.email})")
                    print(f"✅ OAUTH: Социальный аккаунт связан с существующим пользователем")
                else:
                    print(f"🔍 OAUTH: Пользователь с email {user.email} не найден, будет создан новый")
                    
            except Exception as e:
                print(f"❌ OAUTH: Ошибка при связывании аккаунта: {e}")
                
        return sociallogin

    def populate_user(self, request, sociallogin, data):
        """Заполняет данные пользователя из социального аккаунта"""
        user = super().populate_user(request, sociallogin, data)
        
        # Дополнительная обработка для Google OAuth
        if sociallogin.account.provider == 'google':
            # Устанавливаем username как email, если username не задан
            if not user.username and user.email:
                user.username = user.email.split('@')[0]
        
        return user
    
    def save_user(self, request, sociallogin, form=None):
        """
        Создаем нового пользователя с правами наблюдателя при первом входе через Google
        """
        # Проверяем, является ли пользователь новым
        is_new_user = sociallogin.is_new
        
        user = super().save_user(request, sociallogin, form)
        
        # Автоматически заполняем данные из Google
        if sociallogin.account.provider == 'google':
            
            # Даем права наблюдателя ТОЛЬКО новым пользователям
            if is_new_user:
                from .role_service import RoleService
                success, message = RoleService.assign_role_to_user(user, 'Наблюдатели')
                if success:
                    print(f"✅ OAUTH: Новому пользователю {user.username} назначены права наблюдателя")
                else:
                    print(f"⚠️ OAUTH: Не удалось назначить права наблюдателя: {message}")
                
                print(f"✅ OAUTH: Создан новый пользователь: {user.username} ({user.email})")
                
                # Добавляем сообщение для нового пользователя
                display_name = f"{user.first_name} {user.last_name}".strip() or user.username
                messages.success(request, 
                    f"Добро пожаловать, {display_name}! "
                    f"Ваш Google аккаунт успешно подключен. Вам назначены права наблюдателя."
                )
            else:
                print(f"✅ OAUTH: Существующий пользователь {user.username} авторизован через Google")
                
                # Добавляем сообщение для существующего пользователя
                display_name = f"{user.first_name} {user.last_name}".strip() or user.username
                messages.success(request, 
                    f"Добро пожаловать обратно, {display_name}! "
                    f"Ваш Google аккаунт успешно подключен."
                )
            
            user.save()
        
        return user
