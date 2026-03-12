import time
import logging
from datetime import datetime, timedelta
from celery import shared_task
from django.utils import timezone
from django.conf import settings
from apps.accounts.models import User
from .token_service import HuntflowTokenService

logger = logging.getLogger(__name__)

@shared_task
def refresh_huntflow_tokens():
    """
    Периодическая задача для автоматического обновления токенов Huntflow
    Запускается каждый час и проверяет, нужно ли обновить токены
    """
    logger.info("🔄 Запуск периодического обновления токенов Huntflow")
    
    # Получаем всех пользователей с настроенными токенами Huntflow
    users_with_tokens = User.objects.filter(
        huntflow_access_token__isnull=False,
        huntflow_refresh_token__isnull=False,
        huntflow_access_token__gt='',
        huntflow_refresh_token__gt=''
    ).exclude(
        huntflow_access_token='',
        huntflow_refresh_token=''
    )
    
    updated_count = 0
    failed_count = 0
    
    for user in users_with_tokens:
        try:
            if should_refresh_tokens(user):
                logger.info(f"🔄 Обновляем токены для пользователя {user.email}")
                
                token_service = HuntflowTokenService(user)
                success = refresh_tokens_with_retry(token_service)
                
                if success:
                    updated_count += 1
                    logger.info(f"✅ Токены успешно обновлены для {user.email}")
                else:
                    failed_count += 1
                    logger.error(f"❌ Не удалось обновить токены для {user.email}")
                    
                    # Проверяем критическую ситуацию
                    if is_critical_situation(user):
                        logger.critical(f"🚨 КРИТИЧЕСКАЯ СИТУАЦИЯ: Токены истекли для {user.email}")
                        send_critical_alert(user)
                        
        except Exception as e:
            failed_count += 1
            logger.error(f"❌ Ошибка при обновлении токенов для {user.email}: {e}")
    
    logger.info(f"📊 Обновление токенов завершено: {updated_count} успешно, {failed_count} ошибок")
    return {
        'updated': updated_count,
        'failed': failed_count,
        'total': users_with_tokens.count()
    }

def should_refresh_tokens(user):
    """
    Проверяет, нужно ли обновить токены для пользователя
    Обновляем за 24 часа до истечения любого из токенов
    """
    now = timezone.now()
    
    # Проверяем access token
    if user.huntflow_token_expires_at:
        access_refresh_time = user.huntflow_token_expires_at - timedelta(hours=24)
        if now >= access_refresh_time:
            logger.info(f"⏰ Access token для {user.email} нужно обновить (истекает {user.huntflow_token_expires_at})")
            return True
    
    # Проверяем refresh token
    if user.huntflow_refresh_expires_at:
        refresh_refresh_time = user.huntflow_refresh_expires_at - timedelta(hours=24)
        if now >= refresh_refresh_time:
            logger.info(f"⏰ Refresh token для {user.email} нужно обновить (истекает {user.huntflow_refresh_expires_at})")
            return True
    
    return False

def refresh_tokens_with_retry(token_service, max_retries=5):
    """
    Обновляет токены с retry логикой и экспоненциальным backoff
    """
    backoff_delays = [30, 60, 120, 240, 480]  # в секундах
    
    for attempt in range(max_retries):
        try:
            success = token_service.refresh_access_token()
            if success:
                return True
                
        except Exception as e:
            logger.warning(f"⚠️ Попытка {attempt + 1} обновления токена не удалась: {e}")
            
            if attempt < max_retries - 1:
                delay = backoff_delays[attempt]
                logger.info(f"⏳ Повторная попытка через {delay} секунд...")
                time.sleep(delay)
            else:
                logger.error(f"❌ Все {max_retries} попыток обновления токена не удались")
                
    return False

def is_critical_situation(user):
    """
    Проверяет, является ли ситуация критической
    (оба токена истекли и обновление не удалось)
    """
    now = timezone.now()
    
    access_expired = user.huntflow_token_expires_at and now >= user.huntflow_token_expires_at
    refresh_expired = user.huntflow_refresh_expires_at and now >= user.huntflow_refresh_expires_at
    
    return access_expired and refresh_expired

def send_critical_alert(user):
    """
    Отправляет критическое уведомление о проблемах с токенами
    """
    message = f"""
🚨 КРИТИЧЕСКАЯ СИТУАЦИЯ С HUNTFLOW ТОКЕНАМИ

Пользователь: {user.email}
Access token истекает: {user.huntflow_token_expires_at}
Refresh token истекает: {user.huntflow_refresh_expires_at}

Требуется ручное вмешательство для восстановления интеграции с Huntflow.
"""
    
    logger.critical(message)
    
    # Здесь можно добавить отправку уведомлений в Slack, email и т.д.
    # Например:
    # send_slack_notification(message)
    # send_email_alert(user.email, "Критическая ошибка Huntflow", message)

@shared_task
def check_huntflow_token_health():
    """
    Задача для проверки здоровья токенов Huntflow
    Запускается каждые 6 часов для мониторинга
    """
    logger.info("🏥 Проверка здоровья токенов Huntflow")
    
    users_with_tokens = User.objects.filter(
        huntflow_access_token__isnull=False,
        huntflow_refresh_token__isnull=False,
        huntflow_access_token__gt='',
        huntflow_refresh_token__gt=''
    )
    
    now = timezone.now()
    health_report = {
        'total_users': users_with_tokens.count(),
        'healthy': 0,
        'warning': 0,
        'critical': 0,
        'details': []
    }
    
    for user in users_with_tokens:
        status = get_token_health_status(user, now)
        health_report[status] += 1
        health_report['details'].append({
            'user': user.email,
            'status': status,
            'access_expires': user.huntflow_token_expires_at,
            'refresh_expires': user.huntflow_refresh_expires_at
        })
    
    logger.info(f"🏥 Отчет о здоровье токенов: {health_report}")
    return health_report

def get_token_health_status(user, now):
    """
    Определяет статус здоровья токенов пользователя
    """
    access_expires = user.huntflow_token_expires_at
    refresh_expires = user.huntflow_refresh_expires_at
    
    if not access_expires or not refresh_expires:
        return 'critical'
    
    # Критический: токены истекли
    if now >= access_expires and now >= refresh_expires:
        return 'critical'
    
    # Предупреждение: токены истекают в течение 24 часов
    warning_threshold = now + timedelta(hours=24)
    if access_expires <= warning_threshold or refresh_expires <= warning_threshold:
        return 'warning'
    
    # Здоровый: токены валидны более 24 часов
    return 'healthy'
