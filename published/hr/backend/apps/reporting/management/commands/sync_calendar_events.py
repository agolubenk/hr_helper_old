"""
Management команда для синхронизации событий календаря рекрутеров и интервьюеров
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import datetime, timedelta
import pytz
from apps.google_oauth.models import GoogleOAuthAccount
from apps.google_oauth.services import GoogleOAuthService, GoogleCalendarService
from apps.reporting.models import CalendarEvent
from apps.interviewers.models import Interviewer

User = get_user_model()


class Command(BaseCommand):
    help = 'Синхронизирует события календаря для всех рекрутеров и интервьюеров за указанный период'

    def add_arguments(self, parser):
        parser.add_argument(
            '--start-date',
            type=str,
            default='2024-12-12',
            help='Дата начала синхронизации (формат: YYYY-MM-DD)',
        )
        parser.add_argument(
            '--end-date',
            type=str,
            default=None,
            help='Дата окончания синхронизации (формат: YYYY-MM-DD). По умолчанию - сегодня',
        )
        parser.add_argument(
            '--recruiters-only',
            action='store_true',
            help='Синхронизировать только рекрутеров',
        )
        parser.add_argument(
            '--interviewers-only',
            action='store_true',
            help='Синхронизировать только интервьюеров',
        )

    def handle(self, *args, **options):
        start_date_str = options['start_date']
        end_date_str = options['end_date']
        recruiters_only = options['recruiters_only']
        interviewers_only = options['interviewers_only']

        # Парсим даты
        try:
            start_date_naive = datetime.fromisoformat(start_date_str)
            if timezone.is_naive(start_date_naive):
                start_date = timezone.make_aware(start_date_naive)
            else:
                start_date = start_date_naive
            start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        except ValueError:
            self.stdout.write(self.style.ERROR(f'Неверный формат даты начала: {start_date_str}'))
            return

        if end_date_str:
            try:
                end_date_naive = datetime.fromisoformat(end_date_str)
                if timezone.is_naive(end_date_naive):
                    end_date = timezone.make_aware(end_date_naive)
                else:
                    end_date = end_date_naive
                end_date = end_date.replace(hour=23, minute=59, second=59, microsecond=999999)
            except ValueError:
                self.stdout.write(self.style.ERROR(f'Неверный формат даты окончания: {end_date_str}'))
                return
        else:
            end_date = timezone.now()

        self.stdout.write(self.style.SUCCESS(
            f'Начинаем синхронизацию событий с {start_date.date()} по {end_date.date()}'
        ))

        total_synced = 0
        total_errors = 0

        # Синхронизируем рекрутеров
        if not interviewers_only:
            recruiters = User.objects.filter(
                groups__name='Рекрутер'
            ).exclude(username='admin').distinct()

            self.stdout.write(f'\n📋 Найдено рекрутеров: {recruiters.count()}')

            for recruiter in recruiters:
                synced, errors = self._sync_user_events(recruiter, start_date, end_date, 'рекрутер')
                total_synced += synced
                total_errors += errors

        # Синхронизируем интервьюеров через календарь пользователя andrei.golubenko
        if not recruiters_only:
            interviewers = Interviewer.objects.filter(is_active=True)

            self.stdout.write(f'\n📋 Найдено интервьюеров: {interviewers.count()}')

            # Получаем пользователя andrei.golubenko для доступа к календарям интервьюеров
            golubenko_user = User.objects.filter(email='andrei.golubenko@softnetix.io').first()
            if not golubenko_user:
                golubenko_user = User.objects.filter(username='andrei.golubenko').first()
            
            if not golubenko_user:
                self.stdout.write(
                    self.style.ERROR(
                        '❌ Пользователь andrei.golubenko не найден. Невозможно синхронизировать календари интервьюеров.'
                    )
                )
            else:
                try:
                    golubenko_oauth = GoogleOAuthAccount.objects.get(user=golubenko_user)
                    if not golubenko_oauth.is_token_valid():
                        self.stdout.write(
                            self.style.ERROR(
                                '❌ Токен Google OAuth истек для пользователя andrei.golubenko.'
                            )
                        )
                    else:
                        # Создаем сервисы для доступа к календарям интервьюеров
                        golubenko_oauth_service = GoogleOAuthService(golubenko_user)
                        golubenko_calendar_service = GoogleCalendarService(golubenko_oauth_service)
                        golubenko_service = golubenko_calendar_service._get_service()
                        
                        if not golubenko_service:
                            self.stdout.write(
                                self.style.ERROR(
                                    '❌ Не удалось получить сервис Google Calendar для пользователя andrei.golubenko.'
                                )
                            )
                        else:
                            # Импортируем функцию извлечения calendar_id
                            from apps.google_oauth.views import _extract_calendar_id_from_link
                            
                            for interviewer in interviewers:
                                synced, errors = self._sync_interviewer_events(
                                    interviewer, 
                                    golubenko_service, 
                                    golubenko_calendar_service,
                                    _extract_calendar_id_from_link,
                                    start_date, 
                                    end_date
                                )
                                total_synced += synced
                                total_errors += errors
                except GoogleOAuthAccount.DoesNotExist:
                    self.stdout.write(
                        self.style.ERROR(
                            '❌ У пользователя andrei.golubenko нет Google OAuth аккаунта.'
                        )
                    )
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(
                            f'❌ Ошибка при синхронизации календарей интервьюеров: {e}'
                        )
                    )
                    import traceback
                    self.stdout.write(traceback.format_exc())

        self.stdout.write(self.style.SUCCESS(
            f'\n✅ Синхронизация завершена!'
            f'\n   Всего синхронизировано событий: {total_synced}'
            f'\n   Ошибок: {total_errors}'
        ))

    def _sync_user_events(self, user: User, start_date: datetime, end_date: datetime, user_type: str) -> tuple:
        """
        Синхронизирует события календаря для пользователя
        
        Returns:
            tuple: (количество синхронизированных событий, количество ошибок)
        """
        self.stdout.write(f'\n🔄 Обработка {user_type}: {user.get_full_name() or user.username} ({user.email})')

        # Проверяем наличие Google OAuth аккаунта
        try:
            oauth_account = GoogleOAuthAccount.objects.get(user=user)
        except GoogleOAuthAccount.DoesNotExist:
            self.stdout.write(
                self.style.WARNING(f'   ⚠️  У пользователя нет подключенного Google OAuth аккаунта. Пропускаем.')
            )
            return 0, 0

        # Проверяем валидность токена
        if not oauth_account.is_token_valid():
            self.stdout.write(
                self.style.WARNING(f'   ⚠️  Токен Google OAuth истек. Пропускаем.')
            )
            return 0, 0

        # Создаем сервисы для работы с календарем
        try:
            oauth_service = GoogleOAuthService(user)
            calendar_service = GoogleCalendarService(oauth_service)
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'   ❌ Ошибка создания сервисов: {e}')
            )
            return 0, 1

        # Вычисляем количество дней от текущей даты до end_date
        # API получает события начиная с текущей даты, поэтому нужно запросить больше
        now = timezone.now()
        if start_date < now:
            # Если начальная дата в прошлом, нужно запросить события с прошлого периода
            # Используем timeMin для получения событий с нужной даты
            days_ahead = (end_date - now).days + 1 if end_date > now else 1
        else:
            days_ahead = (end_date - start_date).days + 1

        # Получаем события через API
        try:
            self.stdout.write(f'   📅 Запрашиваем события за {days_ahead} дней (период: {start_date.date()} - {end_date.date()})...')
            
            # Получаем события напрямую через API с указанием timeMin
            service = calendar_service._get_service()
            if not service:
                self.stdout.write(self.style.ERROR('   ❌ Не удалось получить сервис Google Calendar'))
                return 0, 1
            
            # Формируем запрос с timeMin и timeMax
            time_min = start_date.isoformat()
            time_max = end_date.isoformat()
            
            events_result = service.events().list(
                calendarId='primary',
                timeMin=time_min,
                timeMax=time_max,
                maxResults=2500,  # Максимальное количество событий
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            self.stdout.write(f'   📅 Получено {len(events)} событий из API')
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'   ❌ Ошибка получения событий: {e}')
            )
            import traceback
            self.stdout.write(traceback.format_exc())
            return 0, 1

        # Сохраняем события в БД
        synced_count = 0
        error_count = 0

        for event in events:
            try:
                event_id = event.get('id')
                if not event_id:
                    continue

                # Парсим время начала и окончания
                start_time = self._parse_event_time(event.get('start'))
                end_time = self._parse_event_time(event.get('end'))

                if not start_time or not end_time:
                    continue

                # Фильтруем по периоду (уже отфильтровано API, но проверяем на всякий случай)
                if start_time < start_date or start_time > end_date:
                    self.stdout.write(f'   ⏭️  Пропущено событие вне периода: {start_time}')
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

                # Определяем рекрутера (для интервьюеров используем связанного пользователя)
                recruiter = user
                if user.groups.filter(name='Рекрутер').exists():
                    recruiter = user
                else:
                    # Для интервьюеров ищем рекрутера по вакансиям или используем самого пользователя
                    recruiter = user

                # Создаем или обновляем событие
                calendar_event, created = CalendarEvent.objects.update_or_create(
                    event_id=event_id,
                    defaults={
                        'recruiter': recruiter,
                        'title': event.get('summary', 'Без названия'),
                        'start_time': start_time,
                        'end_time': end_time,
                        'attendees': attendees,
                        'description': event.get('description', ''),
                        'location': event.get('location', ''),
                        'google_updated_at': google_updated,
                    }
                )

                if created:
                    synced_count += 1
                else:
                    synced_count += 1  # Считаем обновления тоже

            except Exception as e:
                error_count += 1
                self.stdout.write(
                    self.style.ERROR(f'   ❌ Ошибка сохранения события {event.get("id", "unknown")}: {e}')
                )

        self.stdout.write(
            self.style.SUCCESS(
                f'   ✅ Синхронизировано событий: {synced_count} (ошибок: {error_count})'
            )
        )

        return synced_count, error_count

    def _sync_interviewer_events(
        self, 
        interviewer: Interviewer, 
        golubenko_service, 
        golubenko_calendar_service,
        extract_calendar_id_func,
        start_date: datetime, 
        end_date: datetime
    ) -> tuple:
        """
        Синхронизирует события календаря для интервьюера через календарь пользователя andrei.golubenko
        
        Returns:
            tuple: (количество синхронизированных событий, количество ошибок)
        """
        self.stdout.write(f'\n🔄 Обработка интервьюера: {interviewer.get_full_name()} ({interviewer.email})')
        
        # Определяем calendar_id интервьюера
        calendar_id = None
        
        # Способ 1: Извлекаем из calendar_link
        if interviewer.calendar_link:
            calendar_id = extract_calendar_id_func(interviewer.calendar_link)
            if calendar_id:
                self.stdout.write(f'   📅 Извлечен calendar_id из ссылки: {calendar_id}')
        
        # Способ 2: Ищем календарь по email
        if not calendar_id:
            try:
                calendar = golubenko_calendar_service.get_calendar_by_email(interviewer.email)
                if calendar:
                    calendar_id = calendar['id']
                    self.stdout.write(f'   📅 Найден календарь по email: {calendar_id}')
            except Exception as e:
                self.stdout.write(f'   ⚠️  Ошибка поиска календаря по email: {e}')
        
        # Способ 3: Используем email напрямую
        if not calendar_id:
            calendar_id = interviewer.email
            self.stdout.write(f'   📅 Используем email как calendar_id: {calendar_id}')
        
        if not calendar_id:
            self.stdout.write(
                self.style.WARNING('   ⚠️  Не удалось определить calendar_id. Пропускаем.')
            )
            return 0, 0
        
        # Запрашиваем события календаря интервьюера
        try:
            time_min = start_date.isoformat()
            time_max = end_date.isoformat()
            
            self.stdout.write(f'   📅 Запрашиваем события календаря интервьюера (период: {start_date.date()} - {end_date.date()})...')
            
            events_result = golubenko_service.events().list(
                calendarId=calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                maxResults=2500,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            self.stdout.write(f'   📅 Получено {len(events)} событий из календаря интервьюера')
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'   ❌ Ошибка запроса событий календаря: {e}')
            )
            import traceback
            self.stdout.write(traceback.format_exc())
            return 0, 1
        
        # Сохраняем события в БД
        synced_count = 0
        error_count = 0
        
        # Получаем всех рекрутеров для определения рекрутера события
        recruiters = User.objects.filter(groups__name='Рекрутер').exclude(username='admin').distinct()
        
        for event in events:
            try:
                event_id = event.get('id')
                if not event_id:
                    continue
                
                # Парсим время
                start_time = self._parse_event_time(event.get('start'))
                end_time = self._parse_event_time(event.get('end'))
                
                if not start_time or not end_time:
                    continue
                
                # Фильтруем по периоду
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
                
                # Определяем рекрутера для события интервьюера
                # Пытаемся найти рекрутера по участникам
                event_recruiter = None
                for attendee_email in [a.get('email', '') for a in attendees]:
                    recruiter_user = User.objects.filter(
                        email=attendee_email,
                        groups__name='Рекрутер'
                    ).first()
                    if recruiter_user:
                        event_recruiter = recruiter_user
                        break
                
                # Если не нашли, используем первого рекрутера
                if not event_recruiter:
                    event_recruiter = recruiters.first()
                
                if not event_recruiter:
                    self.stdout.write(
                        self.style.WARNING(
                            f'   ⚠️  Не найден рекрутер для события {event.get("summary", "Без названия")}. Пропускаем.'
                        )
                    )
                    continue
                
                # Сохраняем событие
                calendar_event, created = CalendarEvent.objects.update_or_create(
                    event_id=event_id,
                    defaults={
                        'recruiter': event_recruiter,
                        'title': event.get('summary', 'Без названия'),
                        'start_time': start_time,
                        'end_time': end_time,
                        'attendees': attendees,
                        'description': event.get('description', ''),
                        'location': event.get('location', ''),
                        'google_updated_at': google_updated,
                    }
                )
                
                synced_count += 1
                
            except Exception as e:
                error_count += 1
                self.stdout.write(
                    self.style.ERROR(f'   ❌ Ошибка сохранения события {event.get("id", "unknown")}: {e}')
                )
                import traceback
                self.stdout.write(traceback.format_exc())
        
        self.stdout.write(
            self.style.SUCCESS(
                f'   ✅ Синхронизировано событий: {synced_count} (ошибок: {error_count})'
            )
        )
        
        return synced_count, error_count

    def _parse_event_time(self, time_data):
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

