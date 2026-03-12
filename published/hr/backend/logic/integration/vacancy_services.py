"""Сервисы для интеграции с внешними системами через вакансии"""
from logic.base.api_client import BaseAPIClient
from logic.base.response_handler import UnifiedResponseHandler
from apps.vacancies.models import Vacancy
import json

class VacancyIntegrationService(BaseAPIClient):
    """Базовый сервис для интеграции вакансий с внешними системами"""
    
    def __init__(self, api_key="", base_url="", timeout=30):
        super().__init__(api_key, base_url, timeout)
    
    def sync_vacancy_to_external(self, vacancy_id, external_system):
        """Синхронизация вакансии во внешнюю систему"""
        try:
            vacancy = Vacancy.objects.get(id=vacancy_id)
            
            # Формируем данные для внешней системы
            vacancy_data = self._prepare_vacancy_data(vacancy)
            
            # Отправляем во внешнюю систему
            response = self.post(f"{external_system}/vacancies", data=vacancy_data)
            
            if response.get('success'):
                return UnifiedResponseHandler.success_response(
                    response.get('data'),
                    f"Вакансия синхронизирована с {external_system}"
                )
            else:
                return UnifiedResponseHandler.error_response(
                    f"Ошибка синхронизации с {external_system}: {response.get('error', 'Неизвестная ошибка')}"
                )
                
        except Vacancy.DoesNotExist:
            return UnifiedResponseHandler.error_response("Вакансия не найдена")
        except Exception as e:
            return UnifiedResponseHandler.error_response(str(e))
    
    def _prepare_vacancy_data(self, vacancy):
        """Подготовка данных вакансии для внешней системы"""
        try:
            vacancy_data = {
                'name': vacancy.name,
                'external_id': vacancy.external_id,
                'recruiter': vacancy.recruiter.username if vacancy.recruiter else None,
                'invite_title': vacancy.invite_title,
                'invite_text': vacancy.invite_text,
                'scorecard_title': vacancy.scorecard_title,
                'created_at': vacancy.created_at.isoformat(),
                'updated_at': vacancy.updated_at.isoformat()
            }
            
            return vacancy_data
        except Exception as e:
            raise Exception(f"Ошибка подготовки данных вакансии: {str(e)}")
    
    def get_vacancy_from_external(self, external_id, external_system):
        """Получение вакансии из внешней системы"""
        try:
            response = self.get(f"{external_system}/vacancies/{external_id}")
            
            if response.get('success'):
                external_data = response.get('data', {})
                
                # Преобразуем данные внешней системы в формат нашей системы
                vacancy_data = self._convert_external_vacancy_data(external_data)
                
                return UnifiedResponseHandler.success_response(
                    vacancy_data,
                    f"Вакансия получена из {external_system}"
                )
            else:
                return UnifiedResponseHandler.error_response(
                    f"Ошибка получения вакансии из {external_system}: {response.get('error', 'Неизвестная ошибка')}"
                )
                
        except Exception as e:
            return UnifiedResponseHandler.error_response(str(e))
    
    def _convert_external_vacancy_data(self, external_data):
        """Преобразование данных внешней системы в формат нашей системы"""
        try:
            vacancy_data = {
                'name': external_data.get('name', external_data.get('title', '')),
                'external_id': external_data.get('external_id', external_data.get('id', '')),
                'recruiter': external_data.get('recruiter'),
                'invite_title': external_data.get('invite_title', ''),
                'invite_text': external_data.get('invite_text', external_data.get('description', '')),
                'scorecard_title': external_data.get('scorecard_title', ''),
                'external_system': external_data.get('system')
            }
            
            return vacancy_data
        except Exception as e:
            raise Exception(f"Ошибка преобразования данных: {str(e)}")
    
    def bulk_sync_vacancies(self, vacancy_ids, external_system):
        """Массовая синхронизация вакансий"""
        try:
            results = []
            success_count = 0
            error_count = 0
            
            for vacancy_id in vacancy_ids:
                result = self.sync_vacancy_to_external(vacancy_id, external_system)
                results.append({
                    'vacancy_id': vacancy_id,
                    'success': result.get('success'),
                    'message': result.get('message')
                })
                
                if result.get('success'):
                    success_count += 1
                else:
                    error_count += 1
            
            return UnifiedResponseHandler.success_response(
                {
                    'results': results,
                    'summary': {
                        'total': len(vacancy_ids),
                        'success': success_count,
                        'errors': error_count
                    }
                },
                f"Синхронизация завершена: {success_count} успешно, {error_count} ошибок"
            )
            
        except Exception as e:
            return UnifiedResponseHandler.error_response(str(e))
    
    def test_external_connection(self, external_system):
        """Тест подключения к внешней системе"""
        try:
            response = self.get(f"{external_system}/health")
            
            if response.get('success'):
                return UnifiedResponseHandler.success_response(
                    response.get('data'),
                    f"Подключение к {external_system} работает"
                )
            else:
                return UnifiedResponseHandler.error_response(
                    f"Ошибка подключения к {external_system}"
                )
                
        except Exception as e:
            return UnifiedResponseHandler.error_response(str(e))
