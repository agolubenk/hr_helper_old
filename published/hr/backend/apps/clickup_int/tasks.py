import random
import time
import logging
import json
from celery import shared_task
from django.contrib.auth import get_user_model
from django.utils import timezone
from .models import ClickUpBulkImport, ClickUpTask
from .services import ClickUpService, ClickUpAPIError

User = get_user_model()
logger = logging.getLogger(__name__)


@shared_task(bind=True)
def bulk_import_clickup_tasks(self, user_id, bulk_import_id):
    """
    Массовый импорт задач ClickUp с рандомными интервалами
    
    Args:
        user_id: ID пользователя
        bulk_import_id: ID записи массового импорта
    """
    print(f"🎯 [WORKER] Начинаем обработку массового импорта: user_id={user_id}, bulk_import_id={bulk_import_id}")
    logger.info(f"🎯 [WORKER] Начинаем обработку массового импорта: user_id={user_id}, bulk_import_id={bulk_import_id}")
    
    try:
        user = User.objects.get(id=user_id)
        bulk_import = ClickUpBulkImport.objects.get(id=bulk_import_id)
        
        # Проверяем, не был ли импорт уже остановлен
        if bulk_import.status in ['stopped', 'cancelled', 'completed', 'failed']:
            print(f"⚠️ [WORKER] Массовый импорт {bulk_import_id} уже завершен со статусом: {bulk_import.status}")
            logger.warning(f"⚠️ [WORKER] Массовый импорт {bulk_import_id} уже завершен со статусом: {bulk_import.status}")
            return
        
        print(f"👤 [WORKER] Пользователь найден: {user.username}")
        logger.info(f"👤 [WORKER] Пользователь найден: {user.username}")
        
        # Сохраняем celery_task_id только если он есть (при асинхронном запуске)
        if hasattr(self, 'request') and self.request.id:
            bulk_import.celery_task_id = self.request.id
        bulk_import.save()
        
        # Получаем настройки пользователя
        from .models import ClickUpSettings
        try:
            settings = ClickUpSettings.objects.get(user=user)
        except ClickUpSettings.DoesNotExist:
            bulk_import.status = 'failed'
            bulk_import.error_message = 'Настройки ClickUp не найдены'
            bulk_import.save()
            return
        
        # Инициализируем сервис ClickUp
        service = ClickUpService(user.clickup_api_key)
        
        # Получаем все задачи из списка постранично
        print(f"🔍 [WORKER] Получаем список задач для пользователя {user.username}")
        logger.info(f"🔍 [WORKER] Получаем список задач для пользователя {user.username}")
        all_tasks = []
        page = 0
        
        try:
            print(f"🔍 [WORKER] Начинаем получение задач из ClickUp API...")
            print(f"🔍 [WORKER] Начинаем получение задач из ClickUp API...", flush=True)
            logger.info(f"🔍 [WORKER] Начинаем получение задач из ClickUp API...")
            
            while True:
                print(f"📄 [WORKER] Запрашиваем страницу {page}...")
                print(f"📄 [WORKER] Запрашиваем страницу {page}...", flush=True)
                logger.info(f"📄 [WORKER] Запрашиваем страницу {page}...")
                
                tasks = service.get_tasks(settings.list_id, include_closed=True, page=page, exclude_huntflow_tagged=True)
                if not tasks:
                    print(f"📄 Страница {page}: задач не найдено, завершаем")
                    print(f"📄 Страница {page}: задач не найдено, завершаем", flush=True)
                    logger.info(f"📄 Страница {page}: задач не найдено, завершаем")
                    break
                all_tasks.extend(tasks)
                page += 1
                logger.info(f"📄 Получена страница {page}, задач: {len(tasks)}")
                print(f"📄 Получена страница {page}, задач: {len(tasks)}")
                print(f"📄 Получена страница {page}, задач: {len(tasks)}", flush=True)
                
                # Ограничиваем количество страниц для безопасности
                if page > 100:  # Максимум 100 страниц
                    logger.warning(f"⚠️ Достигнут лимит страниц (100), останавливаемся")
                    print(f"⚠️ Достигнут лимит страниц (100), останавливаемся")
                    print(f"⚠️ Достигнут лимит страниц (100), останавливаемся", flush=True)
                    break
        except ClickUpAPIError as e:
            logger.error(f"❌ Ошибка получения задач из ClickUp: {e}")
            print(f"❌ Ошибка получения задач из ClickUp: {e}")
            bulk_import.status = 'failed'
            bulk_import.error_message = f'Ошибка получения задач: {str(e)}'
            bulk_import.save()
            return
        except Exception as e:
            logger.error(f"❌ Неожиданная ошибка при получении задач: {e}")
            print(f"❌ Неожиданная ошибка при получении задач: {e}")
            print(f"❌ Неожиданная ошибка при получении задач: {e}", flush=True)
            bulk_import.status = 'failed'
            bulk_import.error_message = f'Неожиданная ошибка: {str(e)}'
            bulk_import.save()
            return
        
        print(f"📊 [WORKER] Получено всего {len(all_tasks)} задач из ClickUp")
        print(f"📊 [WORKER] Получено всего {len(all_tasks)} задач из ClickUp", flush=True)
        logger.info(f"📊 [WORKER] Получено всего {len(all_tasks)} задач из ClickUp")
        
        print(f"🚀 [WORKER] Начинаем планирование {len(all_tasks)} задач...")
        print(f"🚀 [WORKER] Начинаем планирование {len(all_tasks)} задач...", flush=True)
        logger.info(f"🚀 [WORKER] Начинаем планирование {len(all_tasks)} задач...")
        
        if not all_tasks:
            print(f"⚠️ [WORKER] Задач не найдено, завершаем массовый импорт")
            print(f"⚠️ [WORKER] Задач не найдено, завершаем массовый импорт", flush=True)
            logger.info(f"⚠️ [WORKER] Задач не найдено, завершаем массовый импорт")
            bulk_import.status = 'completed'
            bulk_import.total_tasks = 0
            bulk_import.completed_at = timezone.now()
            bulk_import.save()
            return
        
        # Обновляем общее количество задач
        bulk_import.total_tasks = len(all_tasks)
        bulk_import.save()
        
        print(f"📊 [WORKER] Найдено {len(all_tasks)} задач для импорта")
        print(f"📊 [WORKER] Найдено {len(all_tasks)} задач для импорта", flush=True)
        logger.info(f"📊 [WORKER] Найдено {len(all_tasks)} задач для импорта")
        
        # Импортируем каждую задачу с задержками между отправкой
        print(f"🚀 [WORKER] Начинаем планирование {len(all_tasks)} задач...")
        print(f"🚀 [WORKER] Начинаем планирование {len(all_tasks)} задач...", flush=True)
        logger.info(f"🚀 [WORKER] Начинаем планирование {len(all_tasks)} задач...")
        
        # Отправляем все задачи с задержками через apply_async с countdown
        for i, task_data in enumerate(all_tasks):
            try:
                task_id = task_data.get('id', f'task_{i+1}')
                print(f"⏳ [WORKER] Планируем задачу {i+1}/{len(all_tasks)} (ID: {task_id})...")
                print(f"⏳ [WORKER] Планируем задачу {i+1}/{len(all_tasks)} (ID: {task_id})...", flush=True)
                logger.info(f"⏳ [WORKER] Планируем задачу {i+1}/{len(all_tasks)} (ID: {task_id})...")
                
                # Отправляем задачу с задержкой через countdown (не блокируем worker)
                delay_seconds = i * 8  # Каждая задача через 8 секунд после предыдущей
                result = import_single_task.apply_async(
                    args=[user_id, task_data, bulk_import_id],
                    countdown=delay_seconds
                )
                print(f"✅ [WORKER] Задача {i+1} запланирована на {delay_seconds}с с ID: {result.id}")
                print(f"✅ [WORKER] Задача {i+1} запланирована на {delay_seconds}с с ID: {result.id}", flush=True)
                logger.info(f"✅ [WORKER] Задача {i+1} запланирована на {delay_seconds}с с ID: {result.id}")
                
            except Exception as e:
                print(f"❌ [WORKER] Ошибка при планировании задачи {i+1}: {e}")
                print(f"❌ [WORKER] Ошибка при планировании задачи {i+1}: {e}", flush=True)
                logger.error(f"❌ [WORKER] Ошибка при планировании задачи {i+1}: {e}")
                bulk_import.failed_tasks += 1
                bulk_import.failed_task_ids.append(task_data.get('id', f'task_{i+1}'))
                bulk_import.save()
        
        # Обновляем статус - все задачи запланированы
        bulk_import.status = 'running'
        bulk_import.save()
        
        logger.info(f"✅ Массовый импорт запланирован. Всего задач: {len(all_tasks)}")
        print(f"✅ Массовый импорт запланирован. Всего задач: {len(all_tasks)}")
        print(f"✅ Массовый импорт запланирован. Всего задач: {len(all_tasks)}", flush=True)
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка в массовом импорте: {e}")
        print(f"❌ Критическая ошибка в массовом импорте: {e}")
        try:
            bulk_import = ClickUpBulkImport.objects.get(id=bulk_import_id)
            bulk_import.status = 'failed'
            bulk_import.error_message = str(e)
            bulk_import.save()
        except Exception as save_error:
            logger.error(f"❌ Ошибка сохранения статуса ошибки: {save_error}")
            print(f"❌ Ошибка сохранения статуса ошибки: {save_error}")


@shared_task(bind=True)
def import_single_task(self, user_id, task_data, bulk_import_id):
    """
    Импорт одной задачи ClickUp
    
    Args:
        user_id: ID пользователя
        task_data: Данные задачи из ClickUp API
        bulk_import_id: ID записи массового импорта
    """
    task_id = task_data.get('id', 'unknown')
    print(f"🎯 [TASK] Начинаем импорт задачи {task_id}")
    logger.info(f"🎯 [TASK] Начинаем импорт задачи {task_id}")
    
    try:
        user = User.objects.get(id=user_id)
        bulk_import = ClickUpBulkImport.objects.get(id=bulk_import_id)
        
        if not task_id:
            raise ValueError("ID задачи не найден")
        
        print(f"🔄 [TASK] Импортируем задачу {task_id}")
        logger.info(f"🔄 [TASK] Импортируем задачу {task_id}")
        
        # Инициализируем сервис ClickUp
        service = ClickUpService(user.clickup_api_key)
        
        # Парсим данные задачи
        try:
            parsed_data = service.parse_task_data(task_data)
        except Exception as e:
            logger.error(f"❌ Ошибка парсинга данных задачи {task_id}: {e}")
            print(f"❌ Ошибка парсинга данных задачи {task_id}: {e}")
            raise
        
        # Сохраняем или обновляем задачу
        task = None
        created = False
        try:
            task, created = ClickUpTask.objects.update_or_create(
                task_id=task_id,
                user=user,
                defaults=parsed_data
            )
            logger.info(f"✅ Задача {task_id} сохранена в БД")
            print(f"✅ Задача {task_id} сохранена в БД")
        except Exception as e:
            error_msg = str(e)
            if "database is locked" in error_msg.lower():
                # Временная ошибка - пробуем еще раз через некоторое время
                logger.warning(f"⚠️ Временная ошибка БД для задачи {task_id}: {e}")
                print(f"⚠️ Временная ошибка БД для задачи {task_id}: {e}")
                # Retry через 5 секунд
                import time
                time.sleep(5)
                try:
                    task, created = ClickUpTask.objects.update_or_create(
                        task_id=task_id,
                        user=user,
                        defaults=parsed_data
                    )
                    logger.info(f"✅ Задача {task_id} сохранена в БД после retry")
                    print(f"✅ Задача {task_id} сохранена в БД после retry")
                except Exception as retry_error:
                    logger.error(f"❌ Критическая ошибка сохранения задачи {task_id} в БД после retry: {retry_error}")
                    print(f"❌ Критическая ошибка сохранения задачи {task_id} в БД после retry: {retry_error}")
                    raise
            else:
                logger.error(f"❌ Критическая ошибка сохранения задачи {task_id} в БД: {e}")
                print(f"❌ Критическая ошибка сохранения задачи {task_id} в БД: {e}")
                raise
        
        # Переносим в Huntflow, если есть вложения - ИСПОЛЬЗУЕМ ОБЩУЮ ЛОГИКУ
        huntflow_success = False
        if task.attachments and task.attachments != '[]':
            try:
                logger.info(f"🔄 Переносим задачу {task_id} в Huntflow...")
                print(f"🔄 Переносим задачу {task_id} в Huntflow...")
                logger.debug(f"📎 Вложения: {task.attachments}")
                print(f"📎 Вложения: {task.attachments}")
                
                # ИСПОЛЬЗУЕМ ОБЩУЮ ЛОГИКУ ВМЕСТО ДУБЛИРОВАННОГО КОДА
                from logic.integration.shared.huntflow_operations import HuntflowOperations
                
                huntflow_ops = HuntflowOperations(user)
                
                # Получаем первую доступную организацию
                accounts = huntflow_ops.get_accounts()
                if not accounts:
                    logger.warning(f"❌ Не найдено организаций Huntflow для пользователя {user.username}")
                    print(f"❌ Не найдено организаций Huntflow для пользователя {user.username}")
                else:
                    account_id = accounts[0]['id']
                    
                    # Получаем комментарии ТОЛЬКО если опция включена
                    comments = []
                    if bulk_import.include_comments:
                        try:
                            comments = service.get_task_comments(task_id)
                            print(f"💬 Получено комментариев для задачи {task_id}: {len(comments)} (опция включена)")
                            logger.info(f"💬 Получено комментариев для задачи {task_id}: {len(comments)} (опция включена)")
                        except Exception as e:
                            logger.warning(f"Не удалось получить комментарии для задачи {task_id}: {e}")
                            print(f"⚠️ Не удалось получить комментарии для задачи {task_id}: {e}")
                    else:
                        print(f"🚫 Комментарии для задачи {task_id} не запрашиваются (опция отключена)")
                        logger.info(f"🚫 Комментарии для задачи {task_id} не запрашиваются (опция отключена)")
                    
                    # Подготавливаем данные задачи
                    task_data_for_huntflow = {
                        'id': task_id,  # Добавляем ID задачи для ссылки
                        'name': task.name,
                        'description': task.description,
                        'status': task.status,
                        'attachments': json.loads(task.attachments) if isinstance(task.attachments, str) else task.attachments,
                        'comments': comments,  # Используем полученные комментарии
                        'assignees': json.loads(task.assignees) if isinstance(task.assignees, str) else task.assignees,
                        'custom_fields': task.custom_fields
                    }
                    
                    # Создаем кандидата через общую логику
                    # Используем выбранную вакансию из массового импорта
                    vacancy_id = bulk_import.huntflow_vacancy_id
                    if vacancy_id is None or vacancy_id == '' or str(vacancy_id).lower() == 'none':
                        vacancy_id = None
                    
                    print(f"🎯 [VACANCY] Используем вакансию: {vacancy_id} (тип: {type(vacancy_id)})")
                    
                    applicant = huntflow_ops.create_candidate_from_task_data(
                        task_data=task_data_for_huntflow,
                        account_id=account_id,
                        vacancy_id=vacancy_id,  # Используем выбранную вакансию
                        source_type='clickup'
                    )
                    
                    if applicant and isinstance(applicant, dict):
                        huntflow_success = True
                        applicant_id = applicant.get('id', 'unknown')
                        logger.info(f"✅ Задача {task_id} успешно перенесена в Huntflow (кандидат ID: {applicant_id})")
                        print(f"✅ Задача {task_id} успешно перенесена в Huntflow (кандидат ID: {applicant_id})")
                        
                        # Добавляем тег huntflow к задаче в ClickUp
                        try:
                            tag_added = service.add_tag_to_task(task_id, 'huntflow')
                            if tag_added:
                                logger.info(f"🏷️ Тег 'huntflow' успешно добавлен к задаче {task_id}")
                                print(f"🏷️ Тег 'huntflow' успешно добавлен к задаче {task_id}")
                            else:
                                logger.warning(f"⚠️ Не удалось добавить тег 'huntflow' к задаче {task_id}")
                                print(f"⚠️ Не удалось добавить тег 'huntflow' к задаче {task_id}")
                        except Exception as tag_error:
                            logger.error(f"❌ Ошибка при добавлении тега 'huntflow' к задаче {task_id}: {tag_error}")
                            print(f"❌ Ошибка при добавлении тега 'huntflow' к задаче {task_id}: {tag_error}")
                    else:
                        logger.warning(f"❌ Ошибка переноса задачи {task_id} в Huntflow: неожиданный результат")
                        print(f"❌ Ошибка переноса задачи {task_id} в Huntflow: неожиданный результат")
                
            except Exception as huntflow_error:
                logger.error(f"❌ Ошибка переноса в Huntflow: {huntflow_error}")
                print(f"❌ Ошибка переноса в Huntflow: {huntflow_error}")
                import traceback
                traceback.print_exc()
        
        # Обновляем статистику
        bulk_import.processed_tasks += 1
        # Если задача сохранена в БД - это уже успех
        # Huntflow - это дополнительная функция, не критичная
        bulk_import.successful_tasks += 1
        if not huntflow_success and task.attachments and task.attachments != '[]':
            # Только если были вложения, но не удалось перенести в Huntflow
            logger.warning(f"⚠️ Задача {task_id} сохранена, но не перенесена в Huntflow")
            print(f"⚠️ Задача {task_id} сохранена, но не перенесена в Huntflow")
        bulk_import.save()
        
        # Проверяем, завершен ли массовый импорт
        if bulk_import.processed_tasks >= bulk_import.total_tasks:
            bulk_import.status = 'completed'
            bulk_import.completed_at = timezone.now()
            bulk_import.save()
            logger.info(f"🎉 Массовый импорт завершен! Обработано: {bulk_import.processed_tasks}, успешно: {bulk_import.successful_tasks}, неудачно: {bulk_import.failed_tasks}")
            print(f"🎉 Массовый импорт завершен! Обработано: {bulk_import.processed_tasks}, успешно: {bulk_import.successful_tasks}, неудачно: {bulk_import.failed_tasks}")
        
        action = "создана" if created else "обновлена"
        huntflow_status = " и перенесена в Huntflow" if huntflow_success else ""
        logger.info(f"✅ Задача {task_id} {action}{huntflow_status}")
        print(f"✅ Задача {task_id} {action}{huntflow_status}")
        
    except Exception as e:
        task_id = task_data.get('id', 'unknown')
        print(f"❌ [TASK] Критическая ошибка импорта задачи {task_id}: {e}")
        logger.error(f"❌ [TASK] Критическая ошибка импорта задачи {task_id}: {e}")
        try:
            bulk_import = ClickUpBulkImport.objects.get(id=bulk_import_id)
            bulk_import.processed_tasks += 1
            bulk_import.failed_tasks += 1
            bulk_import.failed_task_ids.append(task_id)
            bulk_import.save()
            print(f"📊 [TASK] Обновлена статистика: processed={bulk_import.processed_tasks}, successful={bulk_import.successful_tasks}, failed={bulk_import.failed_tasks}")
            logger.info(f"📊 [TASK] Обновлена статистика: processed={bulk_import.processed_tasks}, successful={bulk_import.successful_tasks}, failed={bulk_import.failed_tasks}")
            
            # Проверяем, завершен ли массовый импорт
            if bulk_import.processed_tasks >= bulk_import.total_tasks:
                bulk_import.status = 'completed'
                bulk_import.completed_at = timezone.now()
                bulk_import.save()
                print(f"🎉 [TASK] Массовый импорт завершен! Обработано: {bulk_import.processed_tasks}, успешно: {bulk_import.successful_tasks}, неудачно: {bulk_import.failed_tasks}")
                logger.info(f"🎉 [TASK] Массовый импорт завершен! Обработано: {bulk_import.processed_tasks}, успешно: {bulk_import.successful_tasks}, неудачно: {bulk_import.failed_tasks}")
        except Exception as save_error:
            print(f"❌ [TASK] Ошибка сохранения статистики: {save_error}")
            logger.error(f"❌ [TASK] Ошибка сохранения статистики: {save_error}")


@shared_task
def retry_failed_tasks(user_id, bulk_import_id):
    """
    Повторный импорт неудачных задач
    
    Args:
        user_id: ID пользователя
        bulk_import_id: ID записи массового импорта
    """
    try:
        user = User.objects.get(id=user_id)
        bulk_import = ClickUpBulkImport.objects.get(id=bulk_import_id)
        
        if not bulk_import.failed_task_ids:
            logger.info("Нет неудачных задач для повтора")
            return
        
        logger.info(f"🔄 Повторный импорт {len(bulk_import.failed_task_ids)} неудачных задач")
        print(f"🔄 Повторный импорт {len(bulk_import.failed_task_ids)} неудачных задач")
        
        # Сбрасываем счетчики неудачных задач
        failed_task_ids = bulk_import.failed_task_ids.copy()
        bulk_import.failed_tasks = 0
        bulk_import.failed_task_ids = []
        bulk_import.status = 'running'
        bulk_import.save()
        
        # Получаем настройки пользователя
        from .models import ClickUpSettings
        settings = ClickUpSettings.objects.get(user=user)
        
        # Инициализируем сервис ClickUp
        service = ClickUpService(user.clickup_api_key)
        
        # Повторно импортируем неудачные задачи
        for i, task_id in enumerate(failed_task_ids):
            try:
                # Получаем данные задачи из API
                task_data = service.get_task(task_id)
                if task_data:
                    logger.info(f"🔄 Отправляем повторный импорт задачи {task_id} в очередь")
                    print(f"🔄 Отправляем повторный импорт задачи {task_id} в очередь")
                    
                    # Отправляем задачу в очередь БЕЗ задержки - она выполнится сразу
                    import_single_task.apply_async(
                        args=[user_id, task_data, bulk_import_id]
                    )
                    
                    # Задержка между отправкой задач (кроме последней)
                    if i < len(failed_task_ids) - 1:
                        delay = 8  # Фиксированная задержка 8 секунд
                        logger.info(f"⏸️ Ждем {delay} секунд перед отправкой следующей задачи...")
                        print(f"⏸️ Ждем {delay} секунд перед отправкой следующей задачи...")
                        import time
                        time.sleep(delay)
                
            except Exception as e:
                logger.error(f"❌ Ошибка при повторном импорте задачи {task_id}: {e}")
                print(f"❌ Ошибка при повторном импорте задачи {task_id}: {e}")
                bulk_import.failed_tasks += 1
                bulk_import.failed_task_ids.append(task_id)
                bulk_import.save()
        
        logger.info("✅ Повторный импорт неудачных задач запланирован")
        print("✅ Повторный импорт неудачных задач запланирован")
        
    except Exception as e:
        logger.error(f"❌ Ошибка при повторном импорте: {e}")
        print(f"❌ Ошибка при повторном импорте: {e}")
        try:
            bulk_import = ClickUpBulkImport.objects.get(id=bulk_import_id)
            bulk_import.status = 'failed'
            bulk_import.error_message = str(e)
            bulk_import.save()
        except Exception as save_error:
            logger.error(f"❌ Ошибка сохранения статуса ошибки: {save_error}")
            print(f"❌ Ошибка сохранения статуса ошибки: {save_error}")
