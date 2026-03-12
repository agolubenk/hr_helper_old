"""
Сервис для сохранения и восстановления снимков состояния кандидата в Redis
"""
import json
import redis
from django.conf import settings
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class StateSnapshotService:
    """Сервис для работы со снимками состояния кандидата"""
    
    def __init__(self):
        self.redis_client = redis.Redis(
            host=getattr(settings, 'REDIS_HOST', 'localhost'),
            port=getattr(settings, 'REDIS_PORT', 6379),
            db=getattr(settings, 'REDIS_DB', 0),
            decode_responses=True
        )
        self.snapshot_ttl = 86400  # 24 часа
    
    def _get_snapshot_key(self, user_id: int, candidate_id: str, action_type: str) -> str:
        """Генерирует ключ для снимка состояния"""
        return f"snapshot:{user_id}:{candidate_id}:{action_type}"
    
    def save_candidate_snapshot(self, user_id: int, candidate_id: str, action_type: str, 
                              candidate_data: Dict[str, Any]) -> bool:
        """
        Сохраняет снимок состояния кандидата перед выполнением действия
        
        Args:
            user_id: ID пользователя
            candidate_id: ID кандидата
            action_type: Тип действия (hrscreening, invite, etc.)
            candidate_data: Данные кандидата для сохранения
        
        Returns:
            bool: True если снимок сохранен успешно
        """
        try:
            key = self._get_snapshot_key(user_id, candidate_id, action_type)
            
            # Сохраняем снимок с временной меткой
            snapshot_data = {
                'timestamp': candidate_data.get('timestamp', ''),
                'candidate_basic': candidate_data.get('candidate_basic', {}),
                'candidate_questionary': candidate_data.get('candidate_questionary', {}),
                'candidate_status': candidate_data.get('candidate_status', {}),
                'candidate_level': candidate_data.get('candidate_level', {}),
                'metadata': candidate_data.get('metadata', {})
            }
            
            self.redis_client.setex(
                key, 
                self.snapshot_ttl, 
                json.dumps(snapshot_data, ensure_ascii=False)
            )
            
            logger.info(f"📸 SNAPSHOT_SAVE: Снимок сохранен для кандидата {candidate_id}, действие {action_type}")
            return True
            
        except Exception as e:
            logger.error(f"❌ SNAPSHOT_SAVE: Ошибка сохранения снимка: {e}")
            return False
    
    def get_candidate_snapshot(self, user_id: int, candidate_id: str, action_type: str) -> Optional[Dict[str, Any]]:
        """
        Получает снимок состояния кандидата
        
        Args:
            user_id: ID пользователя
            candidate_id: ID кандидата
            action_type: Тип действия
        
        Returns:
            Dict с данными снимка или None если не найден
        """
        try:
            key = self._get_snapshot_key(user_id, candidate_id, action_type)
            snapshot_data = self.redis_client.get(key)
            
            if snapshot_data:
                data = json.loads(snapshot_data)
                logger.info(f"📸 SNAPSHOT_GET: Снимок получен для кандидата {candidate_id}, действие {action_type}")
                return data
            else:
                logger.warning(f"⚠️ SNAPSHOT_GET: Снимок не найден для кандидата {candidate_id}, действие {action_type}")
                return None
                
        except Exception as e:
            logger.error(f"❌ SNAPSHOT_GET: Ошибка получения снимка: {e}")
            return None
    
    def delete_candidate_snapshot(self, user_id: int, candidate_id: str, action_type: str) -> bool:
        """
        Удаляет снимок состояния кандидата
        
        Args:
            user_id: ID пользователя
            candidate_id: ID кандидата
            action_type: Тип действия
        
        Returns:
            bool: True если снимок удален успешно
        """
        try:
            key = self._get_snapshot_key(user_id, candidate_id, action_type)
            result = self.redis_client.delete(key)
            
            if result:
                logger.info(f"🗑️ SNAPSHOT_DELETE: Снимок удален для кандидата {candidate_id}, действие {action_type}")
                return True
            else:
                logger.warning(f"⚠️ SNAPSHOT_DELETE: Снимок не найден для удаления: кандидата {candidate_id}, действие {action_type}")
                return False
                
        except Exception as e:
            logger.error(f"❌ SNAPSHOT_DELETE: Ошибка удаления снимка: {e}")
            return False
    
    def create_candidate_snapshot_data(self, huntflow_service, account_id: int, candidate_id: str) -> Dict[str, Any]:
        """
        Создает снимок данных кандидата из Huntflow
        
        Args:
            huntflow_service: Сервис Huntflow
            account_id: ID аккаунта
            candidate_id: ID кандидата
        
        Returns:
            Dict с данными кандидата
        """
        try:
            from datetime import datetime
            
            # Получаем основные данные кандидата
            candidate_basic = huntflow_service.get_applicant(account_id, int(candidate_id))
            
            # Получаем дополнительные поля (questionary)
            candidate_questionary = huntflow_service.get_applicant_questionary(account_id, int(candidate_id))
            
            # Получаем информацию о статусе кандидата
            candidate_status = {}
            try:
                # Получаем все связи кандидата с вакансиями
                links = candidate_basic.get('links', []) if candidate_basic else []
                if links:
                    # Берем последнюю связь (актуальный статус)
                    latest_link = max(links, key=lambda x: x.get('updated', ''))
                    candidate_status = {
                        'status_id': latest_link.get('status'),
                        'vacancy_id': latest_link.get('vacancy'),
                        'updated': latest_link.get('updated'),
                        'changed': latest_link.get('changed')
                    }
            except Exception as e:
                logger.warning(f"⚠️ SNAPSHOT_CREATE: Ошибка получения статуса: {e}")
            
            # Получаем информацию об уровне кандидата
            candidate_level = {}
            if candidate_questionary:
                # Ищем поле с уровнем (обычно это kIbah4MN0iHussXm3n2Ar)
                for key, value in candidate_questionary.items():
                    if isinstance(value, str) and value in ['Junior', 'Junior+', 'Middle', 'Middle+', 'Senior', 'Senior+']:
                        candidate_level = {
                            'field_key': key,
                            'grade': value
                        }
                        break
            
            snapshot_data = {
                'timestamp': datetime.now().isoformat(),
                'candidate_basic': candidate_basic or {},
                'candidate_questionary': candidate_questionary or {},
                'candidate_status': candidate_status,
                'candidate_level': candidate_level,
                'metadata': {
                    'account_id': account_id,
                    'candidate_id': candidate_id,
                    'created_at': datetime.now().isoformat()
                }
            }
            
            logger.info(f"📸 SNAPSHOT_CREATE: Снимок данных создан для кандидата {candidate_id}")
            return snapshot_data
            
        except Exception as e:
            logger.error(f"❌ SNAPSHOT_CREATE: Ошибка создания снимка данных: {e}")
            return {
                'timestamp': datetime.now().isoformat(),
                'candidate_basic': {},
                'candidate_questionary': {},
                'candidate_status': {},
                'candidate_level': {},
                'metadata': {
                    'account_id': account_id,
                    'candidate_id': candidate_id,
                    'error': str(e)
                }
            }


# Глобальный экземпляр сервиса
snapshot_service = StateSnapshotService()
