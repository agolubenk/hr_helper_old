import json
import hashlib
from datetime import datetime, timedelta
from django.core.cache import cache
from django.conf import settings
from django.utils import timezone


class CacheService:
    """Сервис для работы с кэшем API данных"""
    
    @staticmethod
    def _generate_cache_key(service, user_id, **kwargs):
        """Генерирует ключ кэша на основе сервиса, пользователя и параметров"""
        # Создаем строку из всех параметров
        params_str = '_'.join([f"{k}_{v}" for k, v in sorted(kwargs.items())])
        # Создаем хэш для уникальности
        params_hash = hashlib.md5(params_str.encode()).hexdigest()[:8]
        return f"api_cache_{service}_{user_id}_{params_hash}"
    
    @staticmethod
    def get_cached_data(service, user_id, **kwargs):
        """Получить данные из кэша"""
        cache_key = CacheService._generate_cache_key(service, user_id, **kwargs)
        cached_data = cache.get(cache_key)
        
        if cached_data:
            # Проверяем, не истек ли кэш
            cache_time = cached_data.get('cached_at')
            if cache_time:
                cache_time = datetime.fromisoformat(cache_time)
                timeout = settings.API_CACHE_TIMEOUT.get(service, 300)
                if timezone.now() - cache_time < timedelta(seconds=timeout):
                    return cached_data.get('data')
        
        return None
    
    @staticmethod
    def set_cached_data(service, user_id, data, **kwargs):
        """Сохранить данные в кэш"""
        cache_key = CacheService._generate_cache_key(service, user_id, **kwargs)
        timeout = settings.API_CACHE_TIMEOUT.get(service, 300)
        
        cache_data = {
            'data': data,
            'cached_at': timezone.now().isoformat(),
            'service': service,
            'user_id': user_id,
            'params': kwargs
        }
        
        cache.set(cache_key, cache_data, timeout)
        return cache_key
    
    @staticmethod
    def invalidate_cache(service, user_id=None, **kwargs):
        """Инвалидировать кэш для определенного сервиса"""
        if user_id:
            # Инвалидируем кэш для конкретного пользователя
            cache_key = CacheService._generate_cache_key(service, user_id, **kwargs)
            cache.delete(cache_key)
        else:
            # Инвалидируем весь кэш для сервиса
            # Это более агрессивный подход, но эффективный
            cache.delete_many(cache.keys(f"api_cache_{service}_*"))
    
    @staticmethod
    def clear_all_cache():
        """Очистить весь кэш"""
        cache.clear()
    
    @staticmethod
    def get_cache_stats():
        """Получить статистику кэша"""
        # Получаем все ключи кэша
        cache_keys = cache.keys("api_cache_*")
        stats = {
            'total_keys': len(cache_keys),
            'services': {},
            'oldest_cache': None,
            'newest_cache': None
        }
        
        oldest_time = None
        newest_time = None
        
        for key in cache_keys:
            cached_data = cache.get(key)
            if cached_data:
                service = cached_data.get('service', 'unknown')
                if service not in stats['services']:
                    stats['services'][service] = 0
                stats['services'][service] += 1
                
                cache_time_str = cached_data.get('cached_at')
                if cache_time_str:
                    cache_time = datetime.fromisoformat(cache_time_str)
                    if oldest_time is None or cache_time < oldest_time:
                        oldest_time = cache_time
                        stats['oldest_cache'] = cache_time.isoformat()
                    if newest_time is None or cache_time > newest_time:
                        newest_time = cache_time
                        stats['newest_cache'] = cache_time.isoformat()
        
        return stats


class GoogleAPICache:
    """Специализированный кэш для Google API"""
    
    @staticmethod
    def get_calendar_events(user_id, calendar_id='primary', days_ahead=100):
        """Получить события календаря из кэша"""
        return CacheService.get_cached_data(
            'google_calendar_events', 
            user_id, 
            calendar_id=calendar_id, 
            days_ahead=days_ahead
        )
    
    @staticmethod
    def set_calendar_events(user_id, events, calendar_id='primary', days_ahead=100):
        """Сохранить события календаря в кэш"""
        return CacheService.set_cached_data(
            'google_calendar_events', 
            user_id, 
            events,
            calendar_id=calendar_id, 
            days_ahead=days_ahead
        )
    
    @staticmethod
    def get_drive_files(user_id, max_results=100):
        """Получить файлы Drive из кэша"""
        return CacheService.get_cached_data(
            'google_drive_files', 
            user_id, 
            max_results=max_results
        )
    
    @staticmethod
    def set_drive_files(user_id, files, max_results=100):
        """Сохранить файлы Drive в кэш"""
        return CacheService.set_cached_data(
            'google_drive_files', 
            user_id, 
            files,
            max_results=max_results
        )
    
    @staticmethod
    def get_sheets(user_id, max_results=100):
        """Получить таблицы из кэша"""
        return CacheService.get_cached_data(
            'google_sheets', 
            user_id, 
            max_results=max_results
        )
    
    @staticmethod
    def set_sheets(user_id, sheets, max_results=100):
        """Сохранить таблицы в кэш"""
        return CacheService.set_cached_data(
            'google_sheets', 
            user_id, 
            sheets,
            max_results=max_results
        )
    
    @staticmethod
    def get_slot_events_both_variants(user_id, scope='chat_workflow_14', days_ahead=14):
        """
        Получить из кэша оба варианта списков событий для расчёта слотов:
        - ignore_non_accepted: слот занят при любом ответе кроме declined
        - consider_non_accepted: слот занят только при accepted
        """
        return CacheService.get_cached_data(
            'slot_events_both_variants',
            user_id,
            scope=scope,
            days_ahead=days_ahead,
        )

    @staticmethod
    def set_slot_events_both_variants(user_id, data, scope='chat_workflow_14', days_ahead=14):
        """
        Сохранить в кэш оба варианта списков для расчёта слотов.
        data: {'ignore_non_accepted': [...], 'consider_non_accepted': [...]}
        """
        return CacheService.set_cached_data(
            'slot_events_both_variants',
            user_id,
            data,
            scope=scope,
            days_ahead=days_ahead,
        )

    @staticmethod
    def invalidate_user_cache(user_id):
        """Инвалидировать весь кэш пользователя"""
        CacheService.invalidate_cache('google_calendar_events', user_id)
        CacheService.invalidate_cache('slot_events_both_variants', user_id)
        CacheService.invalidate_cache('google_drive_files', user_id)
        CacheService.invalidate_cache('google_sheets', user_id)


class HuntflowAPICache:
    """Специализированный кэш для Huntflow API"""
    
    @staticmethod
    def get_candidate(user_id, account_id, candidate_id):
        """Получить данные кандидата из кэша"""
        return CacheService.get_cached_data(
            'huntflow_candidates', 
            user_id, 
            account_id=account_id, 
            candidate_id=candidate_id
        )
    
    @staticmethod
    def set_candidate(user_id, candidate_data, account_id, candidate_id):
        """Сохранить данные кандидата в кэш"""
        return CacheService.set_cached_data(
            'huntflow_candidates', 
            user_id, 
            candidate_data,
            account_id=account_id, 
            candidate_id=candidate_id
        )
    
    @staticmethod
    def clear_candidate(user_id, account_id, candidate_id):
        """Очистить кэш для конкретного кандидата"""
        CacheService.invalidate_cache(
            'huntflow_candidates', 
            user_id, 
            account_id=account_id, 
            candidate_id=candidate_id
        )
    
    @staticmethod
    def get_vacancy(user_id, account_id, vacancy_id):
        """Получить данные вакансии из кэша"""
        return CacheService.get_cached_data(
            'huntflow_vacancies', 
            user_id, 
            account_id=account_id, 
            vacancy_id=vacancy_id
        )
    
    @staticmethod
    def set_vacancy(user_id, vacancy_data, account_id, vacancy_id):
        """Сохранить данные вакансии в кэш"""
        return CacheService.set_cached_data(
            'huntflow_vacancies', 
            user_id, 
            vacancy_data,
            account_id=account_id, 
            vacancy_id=vacancy_id
        )
    
    @staticmethod
    def clear_vacancy(user_id, account_id, vacancy_id):
        """Очистить кэш для конкретной вакансии"""
        CacheService.invalidate_cache(
            'huntflow_vacancies', 
            user_id, 
            account_id=account_id, 
            vacancy_id=vacancy_id
        )
    
    @staticmethod
    def get_accounts(user_id):
        """Получить список аккаунтов из кэша"""
        return CacheService.get_cached_data(
            'huntflow_accounts', 
            user_id
        )
    
    @staticmethod
    def set_accounts(user_id, accounts_data):
        """Сохранить список аккаунтов в кэш"""
        return CacheService.set_cached_data(
            'huntflow_accounts', 
            user_id, 
            accounts_data
        )
    
    @staticmethod
    def invalidate_user_cache(user_id):
        """Инвалидировать весь кэш пользователя"""
        CacheService.invalidate_cache('huntflow_candidates', user_id)
        CacheService.invalidate_cache('huntflow_vacancies', user_id)
        CacheService.invalidate_cache('huntflow_accounts', user_id)
