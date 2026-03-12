"""Сервисы для работы с интервьюерами"""
from logic.base.api_client import BaseAPIClient
from logic.base.response_handler import UnifiedResponseHandler
from apps.interviewers.models import Interviewer, InterviewRule


class InterviewerService(BaseAPIClient):
    """Сервис для работы с интервьюерами"""
    
    def __init__(self):
        super().__init__("", "https://api.interviewers.com", timeout=30)
    
    def _setup_auth(self):
        """Настройка аутентификации для API интервьюеров"""
        # Пока нет реального API, используем заглушку
        self.headers.update({
            'Authorization': 'Bearer dummy_token',
            'Content-Type': 'application/json'
        })
    
    def get_interviewer_info(self, interviewer_id):
        """Получение информации об интервьюере"""
        try:
            # Получаем интервьюера из базы данных
            interviewer = Interviewer.objects.get(id=interviewer_id)
            
            # Подготавливаем данные для внешнего API
            interviewer_data = self._prepare_interviewer_data(interviewer)
            
            return UnifiedResponseHandler.success_response(
                interviewer_data,
                "Информация об интервьюере получена"
            )
            
        except Interviewer.DoesNotExist:
            return UnifiedResponseHandler.error_response(
                f"Интервьюер с ID {interviewer_id} не найден",
                404
            )
        except Exception as e:
            return UnifiedResponseHandler.error_response(str(e))
    
    def sync_interviewer_calendar(self, interviewer_id):
        """Синхронизация календаря интервьюера"""
        try:
            interviewer = Interviewer.objects.get(id=interviewer_id)
            
            if not interviewer.calendar_link:
                return UnifiedResponseHandler.error_response(
                    "У интервьюера не указана ссылка на календарь",
                    400
                )
            
            # Здесь должна быть логика синхронизации с внешним календарем
            # Пока возвращаем заглушку
            
            sync_data = {
                'interviewer_id': interviewer.id,
                'calendar_link': interviewer.calendar_link,
                'sync_status': 'success',
                'last_sync': '2024-01-01T00:00:00Z'
            }
            
            return UnifiedResponseHandler.success_response(
                sync_data,
                "Календарь интервьюера синхронизирован"
            )
            
        except Interviewer.DoesNotExist:
            return UnifiedResponseHandler.error_response(
                f"Интервьюер с ID {interviewer_id} не найден",
                404
            )
        except Exception as e:
            return UnifiedResponseHandler.error_response(str(e))
    
    def get_available_slots(self, interviewer_id, date_from, date_to):
        """Получение доступных слотов интервьюера"""
        try:
            interviewer = Interviewer.objects.get(id=interviewer_id)
            
            if not interviewer.is_active:
                return UnifiedResponseHandler.error_response(
                    "Интервьюер неактивен",
                    400
                )
            
            # Здесь должна быть логика получения слотов из календаря
            # Пока возвращаем заглушку
            
            available_slots = [
                {
                    'date': '2024-01-01',
                    'time_slots': ['09:00', '10:00', '11:00', '14:00', '15:00']
                },
                {
                    'date': '2024-01-02',
                    'time_slots': ['09:00', '10:00', '14:00', '15:00', '16:00']
                }
            ]
            
            return UnifiedResponseHandler.success_response(
                {
                    'interviewer_id': interviewer.id,
                    'interviewer_name': interviewer.get_full_name(),
                    'available_slots': available_slots
                },
                f"Найдено {len(available_slots)} дней с доступными слотами"
            )
            
        except Interviewer.DoesNotExist:
            return UnifiedResponseHandler.error_response(
                f"Интервьюер с ID {interviewer_id} не найден",
                404
            )
        except Exception as e:
            return UnifiedResponseHandler.error_response(str(e))
    
    def book_interview_slot(self, interviewer_id, date, time, candidate_info):
        """Бронирование слота для интервью"""
        try:
            interviewer = Interviewer.objects.get(id=interviewer_id)
            
            if not interviewer.is_active:
                return UnifiedResponseHandler.error_response(
                    "Интервьюер неактивен",
                    400
                )
            
            # Здесь должна быть логика бронирования слота
            # Пока возвращаем заглушку
            
            booking_data = {
                'interviewer_id': interviewer.id,
                'interviewer_name': interviewer.get_full_name(),
                'date': date,
                'time': time,
                'candidate_info': candidate_info,
                'booking_id': f"INT_{interviewer.id}_{date}_{time.replace(':', '')}",
                'status': 'confirmed'
            }
            
            return UnifiedResponseHandler.success_response(
                booking_data,
                "Слот успешно забронирован"
            )
            
        except Interviewer.DoesNotExist:
            return UnifiedResponseHandler.error_response(
                f"Интервьюер с ID {interviewer_id} не найден",
                404
            )
        except Exception as e:
            return UnifiedResponseHandler.error_response(str(e))
    
    def cancel_interview_booking(self, booking_id):
        """Отмена бронирования интервью"""
        try:
            # Здесь должна быть логика отмены бронирования
            # Пока возвращаем заглушку
            
            cancel_data = {
                'booking_id': booking_id,
                'status': 'cancelled',
                'cancelled_at': '2024-01-01T12:00:00Z'
            }
            
            return UnifiedResponseHandler.success_response(
                cancel_data,
                "Бронирование успешно отменено"
            )
            
        except Exception as e:
            return UnifiedResponseHandler.error_response(str(e))
    
    def get_interview_rules(self):
        """Получение правил интервью"""
        try:
            rules = InterviewRule.objects.all()
            
            rules_data = []
            for rule in rules:
                rule_data = self._prepare_rule_data(rule)
                rules_data.append(rule_data)
            
            return UnifiedResponseHandler.success_response(
                rules_data,
                f"Получено {len(rules_data)} правил интервью"
            )
            
        except Exception as e:
            return UnifiedResponseHandler.error_response(str(e))
    
    def test_connection(self):
        """Тест подключения к API интервьюеров"""
        try:
            # Пока нет реального API, возвращаем заглушку
            test_data = {
                'api_status': 'connected',
                'version': '1.0.0',
                'timestamp': '2024-01-01T00:00:00Z'
            }
            
            return UnifiedResponseHandler.success_response(
                test_data,
                "Подключение к API интервьюеров успешно"
            )
            
        except Exception as e:
            return UnifiedResponseHandler.error_response(str(e))
    
    def _prepare_interviewer_data(self, interviewer):
        """Подготовка данных интервьюера для внешнего API"""
        return {
            'id': interviewer.id,
            'first_name': interviewer.first_name,
            'last_name': interviewer.last_name,
            'middle_name': interviewer.middle_name,
            'full_name': interviewer.get_full_name(),
            'email': interviewer.email,
            'calendar_link': interviewer.calendar_link,
            'is_active': interviewer.is_active,
            'created_at': interviewer.created_at.isoformat(),
            'updated_at': interviewer.updated_at.isoformat()
        }
    
    def _prepare_rule_data(self, rule):
        """Подготовка данных правила для внешнего API"""
        return {
            'id': rule.id,
            'name': rule.name,
            'description': rule.description,
            'duration_minutes': rule.duration_minutes,
            'created_at': rule.created_at.isoformat(),
            'updated_at': rule.updated_at.isoformat()
        }

