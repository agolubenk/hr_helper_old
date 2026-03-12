"""Базовые операции с кандидатами для всех интеграций"""
from abc import ABC, abstractmethod
from logic.base.response_handler import UnifiedResponseHandler

class BaseCandidateOperations(ABC):
    """
    Базовый класс для операций с кандидатами
    
    ВХОДЯЩИЕ ДАННЫЕ: Данные кандидатов
    ИСТОЧНИКИ ДАННЫЕ: Внешние API интеграций
    ОБРАБОТКА: Абстрактный базовый класс для операций с кандидатами
    ВЫХОДЯЩИЕ ДАННЫЕ: Результаты операций с кандидатами
    СВЯЗИ: UnifiedResponseHandler
    ФОРМАТ: Абстрактный класс с общими методами
    """
    
    @abstractmethod
    def create_candidate(self, candidate_data):
        """Создание кандидата - должен быть реализован в наследниках"""
        pass
    
    @abstractmethod
    def update_candidate(self, candidate_id, candidate_data):
        """Обновление кандидата - должен быть реализован в наследниках"""
        pass
    
    @abstractmethod
    def get_candidate(self, candidate_id):
        """Получение кандидата - должен быть реализован в наследниках"""
        pass
    
    @abstractmethod
    def delete_candidate(self, candidate_id):
        """Удаление кандидата - должен быть реализован в наследниках"""
        pass
    
    def search_candidates(self, search_params):
        """
        Поиск кандидатов - базовая реализация
        
        ВХОДЯЩИЕ ДАННЫЕ: search_params (словарь)
        ИСТОЧНИКИ ДАННЫЕ: Параметры поиска кандидатов
        ОБРАБОТКА: Поиск кандидатов по параметрам
        ВЫХОДЯЩИЕ ДАННЫЕ: Список найденных кандидатов
        СВЯЗИ: UnifiedResponseHandler
        ФОРМАТ: Словарь с результатами поиска
        """
        try:
            # Этот метод должен быть переопределен в конкретных реализациях
            return UnifiedResponseHandler.success_response(
                [],
                "Поиск кандидатов (базовая реализация)"
            )
                
        except Exception as e:
            return UnifiedResponseHandler.error_response(str(e))
    
    def link_candidate_to_vacancy(self, candidate_id, vacancy_id):
        """
        Привязка кандидата к вакансии - базовая реализация
        
        ВХОДЯЩИЕ ДАННЫЕ: candidate_id (строка), vacancy_id (строка)
        ИСТОЧНИКИ ДАННЫЕ: ID кандидата и вакансии
        ОБРАБОТКА: Привязка кандидата к вакансии
        ВЫХОДЯЩИЕ ДАННЫЕ: Результат привязки
        СВЯЗИ: UnifiedResponseHandler
        ФОРМАТ: Словарь с результатом операции
        """
        try:
            # Этот метод должен быть переопределен в конкретных реализациях
            return UnifiedResponseHandler.success_response(
                {'candidate_id': candidate_id, 'vacancy_id': vacancy_id},
                "Кандидат привязан к вакансии (базовая реализация)"
            )
                
        except Exception as e:
            return UnifiedResponseHandler.error_response(str(e))
    
    def unlink_candidate_from_vacancy(self, candidate_id, vacancy_id):
        """Отвязка кандидата от вакансии - базовая реализация"""
        try:
            # Этот метод должен быть переопределен в конкретных реализациях
            return UnifiedResponseHandler.success_response(
                {'candidate_id': candidate_id, 'vacancy_id': vacancy_id},
                "Кандидат отвязан от вакансии (базовая реализация)"
            )
                
        except Exception as e:
            return UnifiedResponseHandler.error_response(str(e))
    
    def get_candidate_vacancies(self, candidate_id):
        """Получение вакансий кандидата - базовая реализация"""
        try:
            # Этот метод должен быть переопределен в конкретных реализациях
            return UnifiedResponseHandler.success_response(
                [],
                f"Вакансии кандидата {candidate_id} (базовая реализация)"
            )
                
        except Exception as e:
            return UnifiedResponseHandler.error_response(str(e))
    
    def bulk_create_candidates(self, candidates_data):
        """Массовое создание кандидатов - базовая реализация"""
        try:
            results = []
            success_count = 0
            error_count = 0
            
            for candidate_data in candidates_data:
                result = self.create_candidate(candidate_data)
                results.append({
                    'candidate_data': candidate_data,
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
                        'total': len(candidates_data),
                        'success': success_count,
                        'errors': error_count
                    }
                },
                f"Массовое создание завершено: {success_count} успешно, {error_count} ошибок"
            )
            
        except Exception as e:
            return UnifiedResponseHandler.error_response(str(e))