"""Сервисы для управления аккаунтами пользователей"""
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import transaction
from django.utils import timezone
from datetime import timedelta

User = get_user_model()


class UserService:
    """Сервис для работы с пользователями"""
    
    @staticmethod
    def get_user_profile_data(user):
        """
        Получение данных профиля пользователя
        Используется как в API, так и в веб-интерфейсе
        """
        # Получаем информацию о социальных аккаунтах
        social_accounts = []
        if hasattr(user, 'socialaccount_set'):
            for account in user.socialaccount_set.all():
                social_accounts.append({
                    'provider': account.provider,
                    'uid': account.uid,
                    'extra_data': account.extra_data,
                    'date_joined': account.date_joined,
                })
        
        # Получаем информацию о Google OAuth аккаунте
        oauth_account = None
        is_google_oauth_connected = False
        is_google_social_connected = any(acc['provider'] == 'google' for acc in social_accounts)
        
        try:
            from apps.google_oauth.models import GoogleOAuthAccount
            oauth_account = GoogleOAuthAccount.objects.get(user=user)
            is_google_oauth_connected = oauth_account is not None
            token_valid = oauth_account.is_token_valid() if oauth_account else False
        except:
            token_valid = False
        
        # Получаем статистику Google сервисов
        google_stats = {
            'calendar_events': 0,
            'drive_files': 0,
            'sheets': 0,
        }
        
        if is_google_oauth_connected and token_valid:
            try:
                from apps.google_oauth.services import GoogleService
                google_service = GoogleService(oauth_account)
                google_stats = google_service.get_stats()
            except:
                pass
        
        # Получаем информацию о группах пользователя
        user_groups = [group.name for group in user.groups.all()]
        
        # Получаем статистику интеграций
        integrations_status = UserService.get_integrations_status(user)
        
        profile_data = {
            'user': user,
            'social_accounts': social_accounts,
            'oauth_account': oauth_account,
            'is_google_oauth_connected': is_google_oauth_connected,
            'is_google_social_connected': is_google_social_connected,
            'token_valid': token_valid,
            'google_stats': google_stats,
            'user_groups': user_groups,
            'integrations': integrations_status,
        }
        
        return profile_data
    
    @staticmethod
    def get_integrations_status(user):
        """
        Получение статуса интеграций пользователя
        """
        integrations = {}
        
        # Gemini
        integrations['gemini'] = {
            'name': 'Gemini AI',
            'enabled': True,
            'configured': bool(user.gemini_api_key),
            'api_key': user.gemini_api_key[:10] + '...' if user.gemini_api_key else None,
        }
        
        # Huntflow
        # Проверяем новую токенную систему
        huntflow_token_configured = bool(user.huntflow_access_token and user.huntflow_refresh_token)
        # Проверяем старую систему API ключей (только для sandbox)
        huntflow_sandbox_api_configured = bool(
            getattr(user, 'huntflow_sandbox_api_key', None) and user.huntflow_sandbox_url
        )
        # Для PROD нужны токены и URL
        huntflow_prod_configured = bool(
            user.huntflow_prod_url and user.huntflow_access_token
        )
        # Общая конфигурация (любая из систем)
        huntflow_configured = huntflow_token_configured or huntflow_sandbox_api_configured or huntflow_prod_configured
        
        integrations['huntflow'] = {
            'name': 'Huntflow',
            'enabled': True,
            'sandbox_configured': bool(
                (getattr(user, 'huntflow_sandbox_api_key', None) and user.huntflow_sandbox_url) or
                (user.huntflow_access_token and user.huntflow_sandbox_url)
            ),
            'prod_configured': bool(user.huntflow_prod_url and user.huntflow_access_token),
            'active_system': user.active_system,
            'configured': huntflow_configured,
            'token_configured': huntflow_token_configured,
            'api_configured': huntflow_sandbox_api_configured,
            'token_valid': user.is_huntflow_token_valid if huntflow_token_configured else False,
            'refresh_valid': user.is_huntflow_refresh_valid if huntflow_token_configured else False,
        }
        
        # ClickUp
        integrations['clickup'] = {
            'name': 'ClickUp',
            'enabled': True,
            'configured': bool(user.clickup_api_key),
            'api_key': user.clickup_api_key[:10] + '...' if user.clickup_api_key else None,
        }
        
        # Notion
        integrations['notion'] = {
            'name': 'Notion',
            'enabled': True,
            'configured': bool(user.notion_integration_token),
            'token': user.notion_integration_token[:10] + '...' if user.notion_integration_token else None,
        }
        
        # Telegram
        integrations['telegram'] = {
            'name': 'Telegram',
            'enabled': True,
            'configured': bool(user.telegram_username),
            'username': user.telegram_username,
        }
        
        # Google OAuth
        try:
            from apps.google_oauth.models import GoogleOAuthAccount
            oauth_account = GoogleOAuthAccount.objects.get(user=user)
            is_connected = oauth_account is not None
            token_valid = oauth_account.is_token_valid() if oauth_account else False
        except:
            is_connected = False
            token_valid = False
        
        integrations['google_oauth'] = {
            'name': 'Google OAuth',
            'enabled': True,
            'connected': is_connected,
            'token_valid': token_valid,
            'configured': is_connected and token_valid,
        }

        # HeadHunter.ru
        try:
            from apps.hhru.models import HHruOAuthAccount
            hhru_account = HHruOAuthAccount.objects.filter(user=user).order_by('-created_at').first()
            hhru_connected = hhru_account is not None
            hhru_token_valid = hhru_account.is_token_valid if hhru_account else False
        except Exception:
            hhru_connected = False
            hhru_token_valid = False
        integrations['hhru'] = {
            'name': 'HeadHunter.ru',
            'enabled': True,
            'connected': hhru_connected,
            'token_valid': hhru_token_valid,
            'configured': hhru_connected and hhru_token_valid,
        }
        
        return integrations
    
    @staticmethod
    def update_user_api_keys(user, data):
        """
        Обновление API ключей пользователя
        """
        try:
            with transaction.atomic():
                if 'gemini_api_key' in data:
                    old_key_preview = f"{user.gemini_api_key[:10]}...{user.gemini_api_key[-5:]}" if user.gemini_api_key and len(user.gemini_api_key) > 15 else "нет"
                    new_key = data['gemini_api_key'].strip() if data['gemini_api_key'] else ''
                    new_key_preview = f"{new_key[:10]}...{new_key[-5:]}" if new_key and len(new_key) > 15 else "нет"
                    print(f"🔑 UPDATE_API_KEYS: Обновление Gemini API ключа для пользователя {user.username}")
                    print(f"🔑 UPDATE_API_KEYS: Старый ключ: {old_key_preview}")
                    print(f"🔑 UPDATE_API_KEYS: Новый ключ: {new_key_preview}")
                    user.gemini_api_key = new_key
                
                if 'clickup_api_key' in data:
                    user.clickup_api_key = data['clickup_api_key']
                
                if 'notion_integration_token' in data:
                    user.notion_integration_token = data['notion_integration_token']
                
                if 'huntflow_sandbox_api_key' in data:
                    user.huntflow_sandbox_api_key = data['huntflow_sandbox_api_key']
                
                # huntflow_prod_api_key больше не используется, для PROD используются токены
                # Оставляем для обратной совместимости, но не сохраняем в модель
                if 'huntflow_prod_api_key' in data:
                    # Игнорируем, так как поле больше не существует в модели
                    pass
                
                if 'huntflow_sandbox_url' in data:
                    user.huntflow_sandbox_url = data['huntflow_sandbox_url']
                
                if 'huntflow_prod_url' in data:
                    user.huntflow_prod_url = data['huntflow_prod_url']
                
                if 'active_system' in data:
                    user.active_system = data['active_system']
                
                # Сохраняем токены Huntflow с установкой времени истечения
                if 'huntflow_access_token' in data or 'huntflow_refresh_token' in data:
                    access_token = data.get('huntflow_access_token', user.huntflow_access_token)
                    refresh_token = data.get('huntflow_refresh_token', user.huntflow_refresh_token)
                    
                    # Если оба токена указаны, используем метод set_huntflow_tokens для установки времени истечения
                    if access_token and refresh_token:
                        # Используем стандартные значения времени жизни токенов Huntflow
                        # access token: 7 дней (604800 секунд)
                        # refresh token: 14 дней (1209600 секунд)
                        user.set_huntflow_tokens(
                            access_token=access_token,
                            refresh_token=refresh_token,
                            expires_in=604800,  # 7 дней
                            refresh_expires_in=1209600  # 14 дней
                        )
                    elif access_token:
                        # Если указан только access token, сохраняем его отдельно
                        user.huntflow_access_token = access_token
                        # Устанавливаем время истечения по умолчанию
                        user.huntflow_token_expires_at = timezone.now() + timedelta(seconds=604800)
                        user.save(update_fields=['huntflow_access_token', 'huntflow_token_expires_at'])
                    elif refresh_token:
                        # Если указан только refresh token, сохраняем его отдельно
                        user.huntflow_refresh_token = refresh_token
                        # Устанавливаем время истечения по умолчанию
                        user.huntflow_refresh_expires_at = timezone.now() + timedelta(seconds=1209600)
                        user.save(update_fields=['huntflow_refresh_token', 'huntflow_refresh_expires_at'])
                
                # Сохраняем остальные изменения, если токены не были обновлены выше
                if 'huntflow_access_token' not in data and 'huntflow_refresh_token' not in data:
                    user.save()
                
                # Проверяем, что ключ действительно сохранился
                user.refresh_from_db()
                saved_key_preview = f"{user.gemini_api_key[:10]}...{user.gemini_api_key[-5:]}" if user.gemini_api_key and len(user.gemini_api_key) > 15 else "нет"
                print(f"✅ UPDATE_API_KEYS: Ключ сохранен в БД: {saved_key_preview}")
                
                return True, "API ключи успешно обновлены"
                
        except Exception as e:
            print(f"❌ UPDATE_API_KEYS: Ошибка обновления: {str(e)}")
            import traceback
            traceback.print_exc()
            return False, f"Ошибка обновления API ключей: {str(e)}"
    
    @staticmethod
    def assign_groups_to_user(user, group_ids):
        """
        Назначение групп пользователю
        """
        try:
            with transaction.atomic():
                # Получаем группы
                groups = Group.objects.filter(id__in=group_ids)
                
                # Очищаем текущие группы
                user.groups.clear()
                
                # Назначаем новые группы
                user.groups.set(groups)
                
                return True, f"Пользователю назначено {groups.count()} групп"
                
        except Exception as e:
            return False, f"Ошибка назначения групп: {str(e)}"
    
    @staticmethod
    def get_user_stats():
        """
        Получение статистики пользователей
        """
        try:
            total_users = User.objects.count()
            active_users = User.objects.filter(is_active=True).count()
            staff_users = User.objects.filter(is_staff=True).count()
            superusers = User.objects.filter(is_superuser=True).count()
            
            # Статистика по группам
            group_stats = {}
            for group in Group.objects.all():
                group_stats[group.name] = group.user_set.count()
            
            # Статистика по интеграциям
            integrations_stats = {
                'gemini_configured': User.objects.filter(gemini_api_key__isnull=False).exclude(gemini_api_key='').count(),
                'clickup_configured': User.objects.filter(clickup_api_key__isnull=False).exclude(clickup_api_key='').count(),
                'notion_configured': User.objects.filter(notion_integration_token__isnull=False).exclude(notion_integration_token='').count(),
                'huntflow_sandbox_configured': User.objects.filter(
                    huntflow_sandbox_api_key__isnull=False
                ).exclude(huntflow_sandbox_api_key='').count(),
                'huntflow_prod_configured': User.objects.filter(
                    huntflow_prod_url__isnull=False
                ).exclude(huntflow_prod_url='').filter(
                    huntflow_access_token__isnull=False
                ).exclude(huntflow_access_token='').count(),
            }
            
            stats = {
                'total_users': total_users,
                'active_users': active_users,
                'staff_users': staff_users,
                'superusers': superusers,
                'group_stats': group_stats,
                'integrations_stats': integrations_stats,
            }
            
            return stats
            
        except Exception as e:
            return {'error': f'Ошибка получения статистики: {str(e)}'}
    
    @staticmethod
    def test_api_key_integration(integration_type, api_key, **kwargs):
        """
        Тестирование API ключа для различных интеграций
        """
        try:
            if integration_type == 'gemini':
                from logic.ai_analysis.gemini_services import GeminiService
                service = GeminiService(api_key)
                result = service.test_connection()
                if hasattr(result, 'success'):
                    if result.success:
                        message = result.data.get('message', 'Подключение к Gemini API успешно')
                        return True, message
                    else:
                        error = result.data.get('error', 'Неизвестная ошибка подключения')
                        return False, error
                else:
                    # Если test_connection возвращает что-то другое
                    if len(api_key) < 10:
                        return False, "API ключ слишком короткий"
                    return True, "Gemini API ключ валиден"
            
            elif integration_type == 'huntflow':
                api_url = kwargs.get('api_url')
                if not api_url:
                    return False, "URL API не указан"
                
                # Здесь должна быть логика тестирования Huntflow API
                # Пока возвращаем простую проверку
                if len(api_key) < 10:
                    return False, "API ключ слишком короткий"
                return True, "Huntflow API ключ валиден"
            
            elif integration_type == 'clickup':
                # Здесь должна быть логика тестирования ClickUp API
                if len(api_key) < 10:
                    return False, "API ключ слишком короткий"
                return True, "ClickUp API ключ валиден"
            
            elif integration_type == 'notion':
                # Поддерживаем как старый формат (secret_), так и новый (ntn_)
                if not (api_key.startswith('secret_') or api_key.startswith('ntn_')):
                    return False, "Integration Token должен начинаться с 'secret_' или 'ntn_'"
                if len(api_key) < 20:
                    return False, "Integration Token слишком короткий"
                return True, "Notion Integration Token валиден"
            
            else:
                return False, f"Неизвестный тип интеграции: {integration_type}"
                
        except Exception as e:
            return False, f"Ошибка тестирования API ключа: {str(e)}"

