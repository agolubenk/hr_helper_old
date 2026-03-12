"""
Задачи Celery для Google OAuth
"""
from celery import shared_task
from django.utils import timezone
from django.db import models
from datetime import datetime, timedelta
import logging
import pytz

from .models import GoogleOAuthAccount
from .services import GoogleOAuthService, GoogleCalendarService

logger = logging.getLogger(__name__)


@shared_task
def refresh_google_oauth_tokens():
    """
    Автоматическое обновление истекших токенов Google OAuth
    
    Запускается каждые 30 минут для проверки и обновления токенов,
    которые истекают в ближайшие 10 минут
    """
    try:
        # Находим токены, которые истекают в ближайшие 10 минут
        expiry_threshold = timezone.now() + timedelta(minutes=10)
        
        accounts_to_refresh = GoogleOAuthAccount.objects.filter(
            token_expires_at__lte=expiry_threshold,
            refresh_token__isnull=False
        ).exclude(refresh_token='')
        
        refreshed_count = 0
        failed_count = 0
        
        for account in accounts_to_refresh:
            try:
                oauth_service = GoogleOAuthService(account.user)
                
                # Пытаемся обновить токен
                if oauth_service.refresh_token():
                    refreshed_count += 1
                    logger.info(f"✅ Токен обновлен для пользователя: {account.user.username}")
                else:
                    failed_count += 1
                    logger.warning(f"❌ Не удалось обновить токен для пользователя: {account.user.username}")
                    
            except Exception as e:
                failed_count += 1
                logger.error(f"❌ Ошибка при обновлении токена для {account.user.username}: {e}")
        
        logger.info(f"🔄 Обновление токенов завершено. Обновлено: {refreshed_count}, Ошибок: {failed_count}")
        
        return {
            'success': True,
            'refreshed_count': refreshed_count,
            'failed_count': failed_count,
            'total_checked': len(accounts_to_refresh)
        }
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка при обновлении токенов: {e}")
        return {
            'success': False,
            'error': str(e)
        }


@shared_task
def cleanup_expired_oauth_accounts():
    """
    ОТКЛЮЧЕНО: Очистка истекших OAuth аккаунтов
    
    Эта функция отключена, так как удаление OAuth аккаунтов может привести
    к потере доступа пользователей после отпусков или длительного отсутствия.
    Токены должны обновляться автоматически, а не удаляться.
    """
    logger.info("⚠️ Очистка OAuth аккаунтов отключена для безопасности пользователей")
    
    return {
        'success': True,
        'message': 'Очистка OAuth аккаунтов отключена для безопасности',
        'deleted_count': 0
    }


@shared_task
def validate_oauth_tokens():
    """
    Валидация всех OAuth токенов
    
    Проверяет валидность всех токенов и обновляет статистику
    """
    try:
        total_accounts = GoogleOAuthAccount.objects.count()
        valid_tokens = 0
        expired_tokens = 0
        needs_refresh = 0
        
        for account in GoogleOAuthAccount.objects.all():
            if account.is_token_valid():
                valid_tokens += 1
            else:
                expired_tokens += 1
                if account.needs_refresh():
                    needs_refresh += 1
        
        logger.info(f"📊 Статистика OAuth токенов: Всего: {total_accounts}, Валидных: {valid_tokens}, Истекших: {expired_tokens}, Требуют обновления: {needs_refresh}")
        
        return {
            'success': True,
            'total_accounts': total_accounts,
            'valid_tokens': valid_tokens,
            'expired_tokens': expired_tokens,
            'needs_refresh': needs_refresh
        }
        
    except Exception as e:
        logger.error(f"❌ Ошибка при валидации токенов: {e}")
        return {
            'success': False,
            'error': str(e)
        }


@shared_task
def sync_calendar_events_by_vacancies():
    """
    Синхронизация событий календаря по вакансиям
    
    Для каждой вакансии:
    - Получает события из Google Calendar рекрутера
    - Фильтрует события по названию (invite_title или tech_invite_title)
    - Сохраняет/обновляет события за период (прошедшая неделя + текущая + 2 будущие)
    - Связывает события с рекрутером (организатором календаря)
    - Не удаляет старые события
    """
    try:
        from apps.vacancies.models import Vacancy
        from apps.reporting.models import CalendarEvent
        
        # Получаем все вакансии (независимо от активности)
        vacancies = Vacancy.objects.all()
        
        logger.info(f"🔄 Начинаем синхронизацию событий для {vacancies.count()} вакансий")
        
        # Определяем период синхронизации: прошедшая неделя + текущая + 2 будущие = 4 недели
        now = timezone.now()
        start_date = now - timedelta(weeks=1)  # Прошедшая неделя
        end_date = now + timedelta(weeks=2)    # 2 будущие недели
        
        # Нормализуем даты
        start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = end_date.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        logger.info(f"📅 Период синхронизации: {start_date.date()} - {end_date.date()}")
        
        total_synced = 0
        total_errors = 0
        vacancies_processed = 0
        
        for vacancy in vacancies:
            try:
                # Пропускаем вакансии без invite_title и tech_invite_title
                if not vacancy.invite_title and not vacancy.tech_invite_title:
                    logger.debug(f"⏭️  Пропускаем вакансию {vacancy.name}: нет invite_title и tech_invite_title")
                    continue
                
                # Получаем рекрутера
                recruiter = vacancy.recruiter
                if not recruiter:
                    logger.warning(f"⚠️  Вакансия {vacancy.name}: нет рекрутера, пропускаем")
                    continue
                
                # Проверяем наличие Google OAuth аккаунта у рекрутера
                try:
                    oauth_account = GoogleOAuthAccount.objects.get(user=recruiter)
                except GoogleOAuthAccount.DoesNotExist:
                    logger.debug(f"⏭️  Рекрутер {recruiter.username} не имеет Google OAuth аккаунта, пропускаем вакансию {vacancy.name}")
                    continue
                
                # Проверяем валидность токена
                if not oauth_account.is_token_valid():
                    logger.warning(f"⚠️  Токен рекрутера {recruiter.username} истек, пропускаем вакансию {vacancy.name}")
                    continue
                
                # Создаем сервисы для работы с календарем
                try:
                    oauth_service = GoogleOAuthService(recruiter)
                    calendar_service = GoogleCalendarService(oauth_service)
                    service = calendar_service._get_service()
                    
                    if not service:
                        logger.error(f"❌ Не удалось получить сервис Google Calendar для рекрутера {recruiter.username}")
                        total_errors += 1
                        continue
                except Exception as e:
                    logger.error(f"❌ Ошибка создания сервисов для рекрутера {recruiter.username}: {e}")
                    total_errors += 1
                    continue
                
                # Получаем события из Google Calendar
                try:
                    time_min = start_date.isoformat()
                    time_max = end_date.isoformat()
                    
                    events_result = service.events().list(
                        calendarId='primary',
                        timeMin=time_min,
                        timeMax=time_max,
                        maxResults=2500,
                        singleEvents=True,
                        orderBy='startTime'
                    ).execute()
                    
                    events = events_result.get('items', [])
                    logger.info(f"📅 Вакансия {vacancy.name}: получено {len(events)} событий из календаря рекрутера {recruiter.username}")
                except Exception as e:
                    logger.error(f"❌ Ошибка получения событий для вакансии {vacancy.name}: {e}")
                    total_errors += 1
                    continue
                
                # Фильтруем события по названию вакансии
                # Проверяем, что название события содержит часть из invite_title или tech_invite_title
                matching_events = []
                invite_title_lower = vacancy.invite_title.lower().strip() if vacancy.invite_title else ""
                tech_invite_title_lower = vacancy.tech_invite_title.lower().strip() if vacancy.tech_invite_title else ""
                
                for event in events:
                    event_title = event.get('summary', '')
                    if not event_title:
                        continue
                    
                    event_title_lower = event_title.lower().strip()
                    
                    # Проверяем соответствие по invite_title или tech_invite_title
                    # Событие должно содержать хотя бы часть из названия вакансии
                    matches = False
                    
                    # Проверяем invite_title (для скринингов)
                    if invite_title_lower:
                        # Извлекаем ключевые слова из invite_title (например, "JS Tech Screening" -> ["js", "tech", "screening"])
                        invite_keywords = [word for word in invite_title_lower.split() if len(word) > 1]
                        # Проверяем, содержит ли название события хотя бы 2 ключевых слова
                        matching_keywords = [kw for kw in invite_keywords if kw in event_title_lower]
                        if len(matching_keywords) >= 2:
                            matches = True
                        # Также проверяем полное вхождение
                        elif invite_title_lower in event_title_lower or event_title_lower in invite_title_lower:
                            matches = True
                    
                    # Проверяем tech_invite_title (для интервью)
                    if not matches and tech_invite_title_lower:
                        # Извлекаем ключевые слова из tech_invite_title
                        tech_keywords = [word for word in tech_invite_title_lower.split() if len(word) > 1]
                        # Проверяем, содержит ли название события хотя бы 2 ключевых слова
                        matching_keywords = [kw for kw in tech_keywords if kw in event_title_lower]
                        if len(matching_keywords) >= 2:
                            matches = True
                        # Также проверяем полное вхождение
                        elif tech_invite_title_lower in event_title_lower or event_title_lower in tech_invite_title_lower:
                            matches = True
                    
                    if matches:
                        matching_events.append(event)
                
                logger.info(f"✅ Вакансия {vacancy.name}: найдено {len(matching_events)} соответствующих событий")
                
                # Сохраняем/обновляем события
                synced_count = 0
                for event in matching_events:
                    try:
                        event_id = event.get('id')
                        if not event_id:
                            continue
                        
                        # Парсим время начала и окончания
                        start_time = _parse_event_time(event.get('start'))
                        end_time = _parse_event_time(event.get('end'))
                        
                        if not start_time or not end_time:
                            continue
                        
                        # Фильтруем по периоду (на всякий случай)
                        if start_time < start_date or start_time > end_date:
                            continue
                        
                        # Извлекаем участников
                        attendees = []
                        for attendee in event.get('attendees', []):
                            attendees.append({
                                'email': attendee.get('email', ''),
                                'name': attendee.get('displayName', attendee.get('email', ''))
                            })
                        
                        # Получаем время обновления из Google
                        google_updated = None
                        if 'updated' in event:
                            try:
                                google_updated = datetime.fromisoformat(event['updated'].replace('Z', '+00:00'))
                            except:
                                pass
                        
                        # Определяем тип события
                        event_type = 'unknown'
                        event_title_lower = event_title.lower()
                        if 'screening' in event_title_lower or 'скрининг' in event_title_lower:
                            event_type = 'screening'
                        elif 'interview' in event_title_lower or 'интервью' in event_title_lower:
                            event_type = 'interview'
                        
                        # Создаем или обновляем событие
                        calendar_event, created = CalendarEvent.objects.update_or_create(
                            event_id=event_id,
                            defaults={
                                'recruiter': recruiter,  # Связываем с рекрутером (организатором календаря)
                                'title': event_title,
                                'start_time': start_time,
                                'end_time': end_time,
                                'attendees': attendees,
                                'description': event.get('description', ''),
                                'location': event.get('location', ''),
                                'google_updated_at': google_updated,
                                'event_type': event_type,
                                'vacancy': vacancy,  # Связываем с вакансией
                            }
                        )
                        
                        synced_count += 1
                        total_synced += 1
                        
                    except Exception as e:
                        logger.error(f"❌ Ошибка сохранения события {event.get('id', 'unknown')} для вакансии {vacancy.name}: {e}")
                        total_errors += 1
                
                vacancies_processed += 1
                logger.info(f"✅ Вакансия {vacancy.name}: синхронизировано {synced_count} событий")
                
            except Exception as e:
                logger.error(f"❌ Ошибка обработки вакансии {vacancy.name}: {e}")
                import traceback
                logger.error(traceback.format_exc())
                total_errors += 1
        
        logger.info(
            f"✅ Синхронизация завершена! "
            f"Обработано вакансий: {vacancies_processed}, "
            f"Синхронизировано событий: {total_synced}, "
            f"Ошибок: {total_errors}"
        )
        
        return {
            'success': True,
            'vacancies_processed': vacancies_processed,
            'total_synced': total_synced,
            'total_errors': total_errors
        }
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка при синхронизации событий по вакансиям: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            'success': False,
            'error': str(e)
        }


def _parse_event_time(time_data):
    """Парсит время события из формата Google Calendar API"""
    if not time_data:
        return None
    
    if 'dateTime' in time_data:
        try:
            return datetime.fromisoformat(time_data['dateTime'].replace('Z', '+00:00'))
        except:
            pass
    
    if 'date' in time_data:
        try:
            return datetime.fromisoformat(time_data['date']).replace(tzinfo=timezone.utc)
        except:
            pass
    
    return None
