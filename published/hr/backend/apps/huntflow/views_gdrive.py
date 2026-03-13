"""
Google Drive Integration API Views

Эндпоинты для интеграции с Google Drive:
- Получение списка активных вакансий
- Парсинг резюме из Google Drive
- Создание кандидата в Huntflow из распарсенного резюме
"""

import requests
import logging
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

logger = logging.getLogger(__name__)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_active_vacancies(request):
    """
    Получение списка активных вакансий из Huntflow
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - request.user: аутентифицированный пользователь
    
    ИСТОЧНИКИ ДАННЫХ:
    - Huntflow API: /account/{account_id}/vacancies
    
    ОБРАБОТКА:
    - Получение account_id пользователя
    - Запрос к Huntflow API
    - Фильтрация активных вакансий
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - JSON с массивом вакансий: [{id, position, company, huntflow_url}]
    """
    try:
        from apps.huntflow.services import HuntflowService
        
        service = HuntflowService(user=request.user)
        
        # Получаем account_id из профиля пользователя или из первой организации
        account_id = getattr(request.user, 'huntflow_account_id', None)
        
        if not account_id:
            # Пробуем получить из списка аккаунтов
            accounts = service.get_accounts()
            if accounts and len(accounts) > 0:
                # Берём первый аккаунт, если он есть в items
                if isinstance(accounts, dict) and 'items' in accounts:
                    items = accounts.get('items', [])
                    if items:
                        account_id = items[0].get('id')
                elif isinstance(accounts, list) and len(accounts) > 0:
                    account_id = accounts[0].get('id')
        
        if not account_id:
            return Response({
                'vacancies': [],
                'error': 'Не найден account_id. Проверьте настройки Huntflow в профиле.'
            })
        
        vacancies_data = service.get_vacancies(account_id=account_id, state="OPEN")
        
        if not vacancies_data:
            return Response({
                'vacancies': [],
                'message': 'Нет активных вакансий'
            })
        
        vacancies = []
        items = vacancies_data.get('items', [])
        
        for v in items:
            vacancy = {
                'id': v.get('id'),
                'position': v.get('position', ''),
                'company': v.get('company', ''),
                'huntflow_url': service.build_vacancy_url(v.get('id')) if hasattr(service, 'build_vacancy_url') else ''
            }
            vacancies.append(vacancy)
        
        return Response({
            'vacancies': vacancies
        })
        
    except Exception as e:
        logger.error(f'Error getting active vacancies: {e}')
        return Response({
            'error': f'Ошибка получения вакансий: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def parse_and_create_candidate(request):
    """
    Скачивание резюме из Google Drive/Docs, парсинг и создание кандидата в Huntflow
    одним запросом.
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - file_id: ID файла в Google Drive/Docs
    - vacancy_id: ID вакансии в Huntflow
    - source_url: (опционально) исходный URL страницы для определения типа файла
    
    ИСТОЧНИКИ ДАННЫХ:
    - Google Drive: публичный файл по file_id
    - Google Docs: экспорт в DOCX
    - Huntflow API: парсинг резюме и создание кандидата
    
    ОБРАБОТКА:
    - Скачивание/экспорт файла из Google Drive/Docs
    - Загрузка и парсинг в Huntflow
    - Создание кандидата с привязкой к вакансии
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - JSON с данными созданного кандидата: {applicant_id, full_name, huntflow_url}
    """
    file_id = request.data.get('file_id')
    vacancy_id = request.data.get('vacancy_id')
    source_url = request.data.get('source_url', '')
    
    if not file_id:
        return Response({
            'error': 'file_id is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    if not vacancy_id:
        return Response({
            'error': 'vacancy_id is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        from apps.huntflow.services import HuntflowService
        import re
        
        service = HuntflowService(user=request.user)
        
        # Получаем account_id и nick организации
        account_id = getattr(request.user, 'huntflow_account_id', None)
        account_nick = None
        
        accounts = service.get_accounts()
        if accounts and isinstance(accounts, dict) and 'items' in accounts:
            items = accounts.get('items', [])
            if items:
                if not account_id:
                    account_id = items[0].get('id')
                # Ищем nick для нашего account_id
                for acc in items:
                    if acc.get('id') == account_id:
                        account_nick = acc.get('nick')
                        break
                if not account_nick and items:
                    account_nick = items[0].get('nick')
        elif accounts and isinstance(accounts, list) and len(accounts) > 0:
            if not account_id:
                account_id = accounts[0].get('id')
            account_nick = accounts[0].get('nick')
        
        if not account_id:
            return Response({
                'error': 'Не найден account_id. Проверьте настройки Huntflow.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Определяем тип файла по source_url
        file_type = 'drive'  # По умолчанию - обычный файл Drive
        if source_url:
            if '/document/d/' in source_url or 'docs.google.com/document' in source_url:
                file_type = 'document'
            elif '/spreadsheets/d/' in source_url or 'docs.google.com/spreadsheets' in source_url:
                file_type = 'spreadsheet'
            elif '/presentation/d/' in source_url or 'docs.google.com/presentation' in source_url:
                file_type = 'presentation'
        
        logger.info(f'Downloading file from Google, type: {file_type}, file_id: {file_id}')
        
        # Формируем URL для скачивания в зависимости от типа
        if file_type == 'document':
            # Google Docs -> DOCX
            download_url = f"https://docs.google.com/document/d/{file_id}/export?format=docx"
            filename = f'resume_{file_id}.docx'
        elif file_type == 'spreadsheet':
            # Google Sheets -> XLSX
            download_url = f"https://docs.google.com/spreadsheets/d/{file_id}/export?format=xlsx"
            filename = f'resume_{file_id}.xlsx'
        elif file_type == 'presentation':
            # Google Slides -> PPTX
            download_url = f"https://docs.google.com/presentation/d/{file_id}/export?format=pptx"
            filename = f'resume_{file_id}.pptx'
        else:
            # Обычный файл Drive (PDF и др.)
            download_url = f"https://drive.google.com/uc?export=download&id={file_id}"
            filename = None  # Определим позже по Content-Type
        
        response = requests.get(download_url, timeout=30, allow_redirects=True)
        
        # Обработка предупреждения о скачивании больших файлов (только для Drive)
        if file_type == 'drive' and response.status_code == 200 and 'text/html' in response.headers.get('Content-Type', ''):
            confirm_token = None
            for key, value in response.cookies.items():
                if key.startswith('download_warning'):
                    confirm_token = value
                    break
            
            if confirm_token:
                download_url = f"https://drive.google.com/uc?export=download&confirm={confirm_token}&id={file_id}"
                response = requests.get(download_url, timeout=30)
        
        response.raise_for_status()
        file_bytes = response.content
        
        if not file_bytes or len(file_bytes) < 100:
            return Response({
                'error': 'Не удалось скачать файл. Убедитесь, что файл доступен для скачивания.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        logger.info(f'File downloaded, size: {len(file_bytes)} bytes')
        
        # Определяем имя файла для обычных файлов Drive
        if filename is None:
            content_type = response.headers.get('Content-Type', 'application/octet-stream')
            if 'pdf' in content_type.lower():
                filename = f'resume_{file_id}.pdf'
            elif 'word' in content_type.lower() or 'document' in content_type.lower():
                filename = f'resume_{file_id}.docx'
            else:
                filename = f'resume_{file_id}.pdf'
        
        # Загружаем и парсим файл в Huntflow
        parse_result = service.upload_file(account_id, file_bytes, filename, parse_file=True)
        
        if not parse_result:
            return Response({
                'error': 'Не удалось загрузить файл в Huntflow'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        logger.info(f'File uploaded to Huntflow: {parse_result.get("id")}')
        
        # Создаём кандидата из распарсенных данных
        applicant_result = service.create_applicant_from_parsed_data(
            account_id=account_id,
            parsed_data=parse_result,
            vacancy_id=vacancy_id
        )
        
        if not applicant_result or not applicant_result.get('id'):
            return Response({
                'error': 'Не удалось создать кандидата в Huntflow'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        applicant_id = applicant_result.get('id')

        # Формируем URL кандидата в веб-интерфейсе Huntflow
        # Формат: https://huntflow.ru/my/{nick}#/vacancy/{vacancy_id}/filter/workon/id/{applicant_id}
        if account_nick and vacancy_id:
            huntflow_url = f"https://huntflow.ru/my/{account_nick}#/vacancy/{vacancy_id}/filter/workon/id/{applicant_id}"
        elif account_nick:
            # Без вакансии - просто ссылка на кандидата
            huntflow_url = f"https://huntflow.ru/my/{account_nick}#/applicant/{applicant_id}"
        else:
            # Fallback на старый формат если nick не найден
            huntflow_url = f"https://huntflow.ru/my/{account_id}/applicants/{applicant_id}"
        
        # Извлекаем ФИО для ответа
        fields = parse_result.get('fields') or {}
        name_data = fields.get('name') or {}
        full_name = ' '.join(filter(None, [
            name_data.get('last', '') if isinstance(name_data, dict) else '',
            name_data.get('first', '') if isinstance(name_data, dict) else '',
            name_data.get('middle', '') if isinstance(name_data, dict) else ''
        ])).strip() or applicant_result.get('last_name', '') + ' ' + applicant_result.get('first_name', '') or 'Кандидат'
        
        # Сохраняем связку GDrive -> Huntflow
        try:
            from .models import GDriveHuntflowLink
            
            # Получаем название вакансии
            vacancy_name = ''
            try:
                vacancies_data = service.get_vacancies(account_id=account_id, state="OPEN")
                if vacancies_data and vacancies_data.get('items'):
                    for v in vacancies_data.get('items', []):
                        if v.get('id') == int(vacancy_id):
                            vacancy_name = v.get('position', '')
                            break
            except:
                pass
            
            # Используем исходный URL если он есть, иначе формируем стандартный
            gdrive_url = source_url if source_url else f"https://drive.google.com/file/d/{file_id}/view"
            
            # Преобразуем vacancy_id в int если это строка
            vacancy_id_int = None
            try:
                vacancy_id_int = int(vacancy_id) if vacancy_id else None
            except (ValueError, TypeError):
                pass
            
            link, created = GDriveHuntflowLink.objects.update_or_create(
                gdrive_file_id=file_id,
                defaults={
                    'gdrive_url': gdrive_url,
                    'huntflow_url': huntflow_url,
                    'applicant_id': applicant_id,
                    'account_id': account_id,
                    'vacancy_id': vacancy_id_int,
                    'vacancy_name': vacancy_name,
                    'candidate_name': full_name,
                    'updated_by_id': request.user.id,
                }
            )
            if created:
                link.created_by_id = request.user.id
                link.save(update_fields=['created_by_id'])
            logger.info(f'GDriveHuntflowLink {"created" if created else "updated"}: {file_id} -> {applicant_id}')
        except Exception as link_error:
            logger.warning(f'Failed to save GDriveHuntflowLink: {link_error}')
        
        return Response({
            'success': True,
            'applicant_id': applicant_id,
            'full_name': full_name,
            'vacancy_id': vacancy_id,
            'huntflow_url': huntflow_url,
            'message': f'Кандидат "{full_name}" успешно создан и добавлен на вакансию'
        })
        
    except requests.RequestException as e:
        logger.error(f'Error downloading file from Google Drive: {e}')
        return Response({
            'error': f'Ошибка скачивания файла: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    except Exception as e:
        logger.error(f'Error creating candidate: {e}')
        import traceback
        traceback.print_exc()
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Оставляем старые эндпоинты для обратной совместимости
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def parse_gdrive_resume(request):
    """
    Только парсинг резюме из Google Drive (без создания кандидата)
    Используйте parse_and_create_candidate для полного процесса
    """
    return parse_and_create_candidate(request)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_candidate_from_gdrive(request):
    """
    Deprecated: используйте parse_and_create_candidate
    """
    return Response({
        'error': 'Этот эндпоинт устарел. Используйте /api/gdrive/parse-and-create/'
    }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_gdrive_link(request):
    """
    Получение связки GDrive -> Huntflow по file_id
    
    GET /api/gdrive/link/?file_id=...
    
    Возвращает информацию о кандидате, если файл уже был обработан.
    """
    file_id = request.query_params.get('file_id', '').strip()
    
    if not file_id:
        return Response({
            'success': False,
            'error': 'file_id is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        from .models import GDriveHuntflowLink
        
        link = GDriveHuntflowLink.objects.filter(gdrive_file_id=file_id).first()
        
        if not link:
            return Response({
                'success': True,
                'found': False,
                'file_id': file_id
            })
        
        return Response({
            'success': True,
            'found': True,
            'file_id': file_id,
            'gdrive_url': link.gdrive_url,
            'huntflow_url': link.huntflow_url,
            'applicant_id': link.applicant_id,
            'account_id': link.account_id,
            'vacancy_id': link.vacancy_id,
            'vacancy_name': link.vacancy_name,
            'candidate_name': link.candidate_name,
            'created_at': link.created_at.isoformat() if link.created_at else None,
        })
        
    except Exception as e:
        logger.error(f'Error getting GDrive link: {e}')
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_gdrive_link(request):
    """
    Обновление связки GDrive -> Huntflow

    POST /api/gdrive/link/update/
    
    Body: {
        "file_id": "...",
        "huntflow_url": "https://huntflow.ru/my/..."
    }
    """
    file_id = request.data.get('file_id', '').strip()
    huntflow_url = request.data.get('huntflow_url', '').strip()

    if not file_id:
        return Response({
            'success': False,
            'error': 'file_id is required'
        }, status=status.HTTP_400_BAD_REQUEST)

    if not huntflow_url:
        return Response({
            'success': False,
            'error': 'huntflow_url is required'
        }, status=status.HTTP_400_BAD_REQUEST)

    try:
        from .models import GDriveHuntflowLink

        link = GDriveHuntflowLink.objects.filter(gdrive_file_id=file_id).first()

        if not link:
            # Создаём новую связь
            link = GDriveHuntflowLink(
                gdrive_file_id=file_id,
                gdrive_url=f'https://drive.google.com/file/d/{file_id}/view',
                huntflow_url=huntflow_url,
                created_by=request.user,
                updated_by=request.user
            )
            link.save()
        else:
            # Обновляем существующую
            link.huntflow_url = huntflow_url
            link.updated_by = request.user
            link.save()

        return Response({
            'success': True,
            'file_id': file_id,
            'huntflow_url': huntflow_url,
            'message': 'Ссылка успешно обновлена'
        })

    except Exception as e:
        logger.error(f'Error updating GDrive link: {e}')
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
