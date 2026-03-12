# Пошаговая инструкция по обновлению HH Extension для проверки статусов кандидатов

## Оглавление

\begin{itemize}
\item Обзор изменений
\item Часть 1: Обновление Backend (Django)
\item Часть 2: Обновление Chrome Extension
\item Часть 3: Тестирование
\item Часть 4: Деплой и мониторинг
\end{itemize}

## Обзор изменений

### Что мы добавляем

Новый функционал проверки статуса кандидата перед показом кнопки "Пригласить". Система будет:

\begin{enumerate}
\item Получать список всех откликов/приглашений по вакансии через HH.ru API
\item Кэшировать данные для быстрой проверки
\item Определять, показывать ли кнопку приглашения для конкретного кандидата
\item Отображать текущий статус взаимодействия с кандидатом
\end{enumerate}

### Архитектура решения

\begin{figure}
\centering
\caption{Схема взаимодействия компонентов}
\end{figure}

\begin{itemize}
\item \textbf{Backend (Django)}: API endpoint для проверки статуса + кэширование negotiations
\item \textbf{Extension}: Запрос статуса перед отображением UI + обновление интерфейса
\item \textbf{HH.ru API}: Источник данных о negotiations
\end{itemize}

## Часть 1: Обновление Backend (Django)

### Шаг 1.1: Создание нового API endpoint

**Файл:** `backend/api/views.py` (или создайте `backend/api/views/negotiations.py`)

Добавьте новый view:

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.core.cache import cache
import requests
from datetime import timedelta

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def check_candidate_status(request):
    """
    Проверяет статус кандидата для определения показа кнопки приглашения
    
    POST /api/negotiations/check-status/
    Body: {
        "vacancy_id": "123456",
        "resume_id": "abc123def456",
        "force_refresh": false  # опционально
    }
    
    Response: {
        "show_button": true/false,
        "reason": "no_negotiation" | "already_invited" | "hired" etc,
        "state": "invitation" | null,
        "negotiation_id": "789" | null,
        "state_name": "Приглашен" | null
    }
    """
    vacancy_id = request.data.get('vacancy_id')
    resume_id = request.data.get('resume_id')
    force_refresh = request.data.get('force_refresh', False)
    
    # Валидация входных данных
    if not vacancy_id or not resume_id:
        return Response(
            {'error': 'vacancy_id and resume_id are required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Получаем токен HH.ru для текущего пользователя
    hh_token = get_user_hh_token(request.user)
    if not hh_token:
        return Response(
            {'error': 'HH.ru token not found'},
            status=status.HTTP_401_UNAUTHORIZED
        )
    
    try:
        # Проверяем negotiation
        negotiation = get_negotiation_for_resume(
            vacancy_id=vacancy_id,
            resume_id=resume_id,
            hh_token=hh_token,
            force_refresh=force_refresh
        )
        
        if not negotiation:
            return Response({
                'show_button': True,
                'reason': 'no_negotiation',
                'state': None,
                'negotiation_id': None,
                'state_name': None
            })
        
        # Анализируем состояние
        state_id = negotiation.get('state', {}).get('id')
        state_name = negotiation.get('state', {}).get('name')
        
        # Список состояний, когда кнопку НЕ показываем
        blocked_states = [
            'invitation',      # уже пригласили
            'response',        # кандидат откликнулся
            'discard',         # отказ
            'hired',           # нанят
            'offer',           # предложение сделано
        ]
        
        show_button = state_id not in blocked_states
        
        return Response({
            'show_button': show_button,
            'reason': 'can_reinvite' if show_button else 'already_exists',
            'state': state_id,
            'negotiation_id': negotiation.get('id'),
            'state_name': state_name
        })
        
    except requests.RequestException as e:
        return Response(
            {'error': f'HH.ru API error: {str(e)}'},
            status=status.HTTP_503_SERVICE_UNAVAILABLE
        )
    except Exception as e:
        return Response(
            {'error': f'Internal error: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

### Шаг 1.2: Создание вспомогательных функций

**Файл:** `backend/api/utils/hh_negotiations.py` (создайте новый файл)

import requests
from django.core.cache import cache
from typing import Optional, Dict, List
import logging

logger = logging.getLogger(__name__)

def get_user_hh_token(user) -> Optional[str]:
    """
    Получает HH.ru токен для пользователя
    Адаптируйте под вашу модель хранения токенов
    """
    try:
        # Вариант 1: Если токен в модели User
        return user.hh_access_token
        
        # Вариант 2: Если токен в отдельной модели
        # from your_app.models import HHToken
        # token_obj = HHToken.objects.filter(user=user).first()
        # return token_obj.access_token if token_obj else None
        
    except AttributeError:
        logger.error(f"User {user.id} has no HH token")
        return None


def get_negotiations_for_vacancy(
    vacancy_id: str,
    hh_token: str,
    force_refresh: bool = False
) -> List[Dict]:
    """
    Получает ВСЕ negotiations для вакансии с кэшированием
    
    Args:
        vacancy_id: ID вакансии в HH.ru
        hh_token: Access token для HH.ru API
        force_refresh: Принудительно обновить кэш
    
    Returns:
        List of negotiation objects
    """
    cache_key = f'hh_negotiations_vacancy_{vacancy_id}'
    cache_timeout = 300  # 5 минут
    
    # Проверяем кэш
    if not force_refresh:
        cached_data = cache.get(cache_key)
        if cached_data is not None:
            logger.info(f"Negotiations for vacancy {vacancy_id} loaded from cache")
            return cached_data
    
    # Загружаем из API
    logger.info(f"Fetching negotiations for vacancy {vacancy_id} from HH.ru API")
    
    all_negotiations = []
    page = 0
    per_page = 100
    
    while True:
        url = f'https://api.hh.ru/negotiations'
        params = {
            'vacancy_id': vacancy_id,
            'page': page,
            'per_page': per_page
        }
        headers = {
            'Authorization': f'Bearer {hh_token}',
            'HH-User-Agent': 'HRHelper/1.0 (your@email.com)'  # Замените на свой
        }
        
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        items = data.get('items', [])
        all_negotiations.extend(items)
        
        # Проверяем, есть ли еще страницы
        total_pages = data.get('pages', 1)
        if page >= total_pages - 1:
            break
            
        page += 1
    
    # Сохраняем в кэш
    cache.set(cache_key, all_negotiations, cache_timeout)
    logger.info(f"Cached {len(all_negotiations)} negotiations for vacancy {vacancy_id}")
    
    return all_negotiations


def get_negotiation_for_resume(
    vacancy_id: str,
    resume_id: str,
    hh_token: str,
    force_refresh: bool = False
) -> Optional[Dict]:
    """
    Находит negotiation для конкретного резюме в рамках вакансии
    
    Args:
        vacancy_id: ID вакансии
        resume_id: Hash резюме (из URL или API)
        hh_token: Access token
        force_refresh: Обновить кэш
    
    Returns:
        Negotiation object или None если не найден
    """
    negotiations = get_negotiations_for_vacancy(
        vacancy_id=vacancy_id,
        hh_token=hh_token,
        force_refresh=force_refresh
    )
    
    # Ищем negotiation для данного резюме
    for neg in negotiations:
        resume = neg.get('resume')
        if resume and resume.get('id') == resume_id:
            logger.info(f"Found negotiation {neg.get('id')} for resume {resume_id}")
            return neg
    
    logger.info(f"No negotiation found for resume {resume_id} in vacancy {vacancy_id}")
    return None


def invalidate_vacancy_cache(vacancy_id: str):
    """
    Инвалидирует кэш negotiations для вакансии
    Вызывайте после создания нового приглашения
    """
    cache_key = f'hh_negotiations_vacancy_{vacancy_id}'
    cache.delete(cache_key)
    logger.info(f"Invalidated cache for vacancy {vacancy_id}")

### Шаг 1.3: Регистрация URL endpoint

**Файл:** `backend/api/urls.py`

from django.urls import path
from .views import check_candidate_status

urlpatterns = [
    # ... существующие пути ...
    
    # Новый endpoint
    path('negotiations/check-status/', check_candidate_status, name='check_candidate_status'),
]

### Шаг 1.4: Обновление функции отправки приглашения

**Файл:** `backend/api/views.py` (или где у вас функция send_invitation)

Добавьте инвалидацию кэша после успешной отправки приглашения:

from .utils.hh_negotiations import invalidate_vacancy_cache

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def send_invitation(request):
    """Существующая функция отправки приглашения"""
    
    vacancy_id = request.data.get('vacancy_id')
    # ... ваш существующий код ...
    
    # После успешной отправки приглашения
    response = requests.post(...)  # ваш запрос к HH API
    
    if response.status_code == 201:
        # НОВОЕ: Инвалидируем кэш
        invalidate_vacancy_cache(vacancy_id)
        
        return Response({'success': True, 'message': 'Invitation sent'})
    
    # ... остальной код ...

### Шаг 1.5: Установка зависимостей (если нужно)

**Файл:** `backend/requirements.txt`

Убедитесь, что у вас есть:

Django>=4.0
djangorestframework>=3.14
requests>=2.28
django-redis>=5.2  # для продакшн кэша (опционально)

Установите:

cd backend
pip install -r requirements.txt

### Шаг 1.6: Настройка кэша (опционально, для production)

**Файл:** `backend/settings.py`

Для development (используется встроенный кэш):

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-snowflake',
    }
}

Для production (Redis рекомендуется):

CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/1',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        },
        'KEY_PREFIX': 'hh_extension',
        'TIMEOUT': 300,  # 5 минут по умолчанию
    }
}

### Шаг 1.7: Миграции (если добавляли модели)

Если вы создали новые модели для хранения кэша в БД:

cd backend
python manage.py makemigrations
python manage.py migrate

### Шаг 1.8: Проверка Backend

Запустите сервер и протестируйте endpoint:

python manage.py runserver

Тест через curl:

curl -X POST http://localhost:8000/api/negotiations/check-status/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "vacancy_id": "123456",
    "resume_id": "abc123def456"
  }'

Ожидаемый ответ:

{
  "show_button": true,
  "reason": "no_negotiation",
  "state": null,
  "negotiation_id": null,
  "state_name": null
}

## Часть 2: Обновление Chrome Extension

### Шаг 2.1: Создание API клиента для проверки статуса

**Файл:** `extension/src/api/negotiations.js` (создайте новый)

/**
 * API клиент для работы с negotiations
 */

const API_BASE_URL = 'http://localhost:8000/api';  // Замените на ваш URL

/**
 * Проверяет статус кандидата и определяет, показывать ли кнопку приглашения
 * 
 * @param {string} vacancyId - ID вакансии
 * @param {string} resumeId - Hash резюме
 * @param {boolean} forceRefresh - Принудительное обновление кэша
 * @returns {Promise<Object>} Статус кандидата
 */
export async function checkCandidateStatus(vacancyId, resumeId, forceRefresh = false) {
  try {
    // Получаем токен из chrome.storage
    const { authToken } = await chrome.storage.local.get('authToken');
    
    if (!authToken) {
      throw new Error('User not authenticated');
    }
    
    const response = await fetch(`${API_BASE_URL}/negotiations/check-status/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${authToken}`
      },
      body: JSON.stringify({
        vacancy_id: vacancyId,
        resume_id: resumeId,
        force_refresh: forceRefresh
      })
    });
    
    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.error || `HTTP ${response.status}`);
    }
    
    const data = await response.json();
    
    return {
      showButton: data.show_button,
      reason: data.reason,
      state: data.state,
      negotiationId: data.negotiation_id,
      stateName: data.state_name
    };
    
  } catch (error) {
    console.error('Error checking candidate status:', error);
    
    // В случае ошибки API - показываем кнопку (fail-safe)
    return {
      showButton: true,
      reason: 'api_error',
      state: null,
      negotiationId: null,
      stateName: null,
      error: error.message
    };
  }
}

/**
 * Проверяет статусы нескольких кандидатов одновременно (batch)
 * 
 * @param {string} vacancyId - ID вакансии
 * @param {Array<string>} resumeIds - Массив hash резюме
 * @returns {Promise<Map>} Map: resumeId -> status
 */
export async function checkMultipleCandidates(vacancyId, resumeIds) {
  const results = new Map();
  
  // Можно оптимизировать: сделать batch endpoint на бэкенде
  // Пока делаем параллельные запросы с лимитом
  const chunkSize = 5;  // Максимум 5 одновременных запросов
  
  for (let i = 0; i < resumeIds.length; i += chunkSize) {
    const chunk = resumeIds.slice(i, i + chunkSize);
    
    const promises = chunk.map(resumeId =>
      checkCandidateStatus(vacancyId, resumeId)
        .then(status => ({ resumeId, status }))
    );
    
    const chunkResults = await Promise.all(promises);
    
    chunkResults.forEach(({ resumeId, status }) => {
      results.set(resumeId, status);
    });
    
    // Небольшая задержка между чанками
    if (i + chunkSize < resumeIds.length) {
      await sleep(500);
    }
  }
  
  return results;
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

### Шаг 2.2: Обновление Content Script

**Файл:** `extension/src/content/candidate-list.js` (или ваш content script)

import { checkCandidateStatus, checkMultipleCandidates } from '../api/negotiations.js';

/**
 * Инициализация проверки статусов при загрузке страницы
 */
async function initializeCandidateStatusCheck() {
  console.log('Initializing candidate status check...');
  
  // Получаем ID вакансии из URL или DOM
  const vacancyId = extractVacancyId();
  
  if (!vacancyId) {
    console.warn('Vacancy ID not found, skipping status check');
    return;
  }
  
  // Находим всех кандидатов на странице
  const candidates = document.querySelectorAll('.candidate-item');
  
  if (candidates.length === 0) {
    console.warn('No candidates found on page');
    return;
  }
  
  console.log(`Found ${candidates.length} candidates, checking statuses...`);
  
  // Извлекаем resume IDs
  const resumeIds = Array.from(candidates).map(extractResumeId).filter(Boolean);
  
  // Проверяем статусы (batch)
  const statuses = await checkMultipleCandidates(vacancyId, resumeIds);
  
  // Обновляем UI для каждого кандидата
  candidates.forEach(candidateElement => {
    const resumeId = extractResumeId(candidateElement);
    
    if (!resumeId) return;
    
    const status = statuses.get(resumeId);
    
    if (status) {
      updateCandidateUI(candidateElement, status);
    }
  });
  
  console.log('Candidate status check completed');
}

/**
 * Извлекает vacancy ID из URL или DOM
 */
function extractVacancyId() {
  // Вариант 1: Из URL (например, /vacancy/123456/candidates)
  const urlMatch = window.location.pathname.match(/\/vacancy\/(\d+)/);
  if (urlMatch) {
    return urlMatch[1];
  }
  
  // Вариант 2: Из data-атрибута
  const vacancyElement = document.querySelector('[data-vacancy-id]');
  if (vacancyElement) {
    return vacancyElement.dataset.vacancyId;
  }
  
  // Вариант 3: Из скрытого input
  const hiddenInput = document.querySelector('input[name="vacancy_id"]');
  if (hiddenInput) {
    return hiddenInput.value;
  }
  
  return null;
}

/**
 * Извлекает resume ID из элемента кандидата
 */
function extractResumeId(candidateElement) {
  // Вариант 1: Из data-атрибута
  if (candidateElement.dataset.resumeId) {
    return candidateElement.dataset.resumeId;
  }
  
  // Вариант 2: Из ссылки на резюме
  const resumeLink = candidateElement.querySelector('a[href*="/resume/"]');
  if (resumeLink) {
    const match = resumeLink.href.match(/\/resume\/([a-f0-9]+)/);
    if (match) {
      return match[1];
    }
  }
  
  // Вариант 3: Из JSON данных в атрибуте
  if (candidateElement.dataset.candidate) {
    try {
      const data = JSON.parse(candidateElement.dataset.candidate);
      return data.resume_id;
    } catch (e) {
      console.error('Error parsing candidate data:', e);
    }
  }
  
  return null;
}

/**
 * Обновляет UI кандидата на основе статуса
 */
function updateCandidateUI(candidateElement, status) {
  // Находим кнопку приглашения (или создаем контейнер для нее)
  let inviteButton = candidateElement.querySelector('.hh-extension-invite-btn');
  
  if (!inviteButton) {
    // Создаем кнопку если её нет
    inviteButton = createInviteButton(candidateElement);
  }
  
  // Показываем/скрываем кнопку
  if (status.showButton) {
    inviteButton.style.display = 'inline-block';
    inviteButton.disabled = false;
    inviteButton.title = 'Пригласить кандидата на вакансию';
    
    // Удаляем статус-бейдж если был
    const existingBadge = candidateElement.querySelector('.hh-extension-status-badge');
    if (existingBadge) {
      existingBadge.remove();
    }
    
  } else {
    inviteButton.style.display = 'none';
    
    // Показываем статус-бейдж
    showStatusBadge(candidateElement, status);
  }
}

/**
 * Создает кнопку приглашения
 */
function createInviteButton(candidateElement) {
  const button = document.createElement('button');
  button.className = 'hh-extension-invite-btn';
  button.textContent = '✉️ Пригласить';
  button.style.cssText = `
    padding: 6px 12px;
    background: #00A0DC;
    color: white;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    font-size: 14px;
    margin-left: 8px;
  `;
  
  // Добавляем обработчик клика
  button.addEventListener('click', async (e) => {
    e.preventDefault();
    e.stopPropagation();
    
    const resumeId = extractResumeId(candidateElement);
    const vacancyId = extractVacancyId();
    
    await handleInviteClick(vacancyId, resumeId, button);
  });
  
  // Находим место для вставки (адаптируйте под свою разметку)
  const actionContainer = candidateElement.querySelector('.candidate-actions') 
    || candidateElement.querySelector('.candidate-header')
    || candidateElement;
  
  actionContainer.appendChild(button);
  
  return button;
}

/**
 * Отображает бейдж со статусом
 */
function showStatusBadge(candidateElement, status) {
  // Удаляем старый бейдж если есть
  const existingBadge = candidateElement.querySelector('.hh-extension-status-badge');
  if (existingBadge) {
    existingBadge.remove();
  }
  
  // Создаем новый
  const badge = document.createElement('span');
  badge.className = 'hh-extension-status-badge';
  badge.textContent = status.stateName || translateState(status.state);
  
  // Стили в зависимости от состояния
  const colors = {
    'invitation': { bg: '#E3F2FD', text: '#1976D2' },  // голубой
    'response': { bg: '#FFF3E0', text: '#F57C00' },    // оранжевый
    'discard': { bg: '#FFEBEE', text: '#C62828' },     // красный
    'hired': { bg: '#E8F5E9', text: '#388E3C' },       // зеленый
    'offer': { bg: '#F3E5F5', text: '#7B1FA2' },       // фиолетовый
  };
  
  const color = colors[status.state] || { bg: '#F5F5F5', text: '#666' };
  
  badge.style.cssText = `
    display: inline-block;
    padding: 4px 10px;
    background: ${color.bg};
    color: ${color.text};
    border-radius: 12px;
    font-size: 12px;
    font-weight: 500;
    margin-left: 8px;
  `;
  
  // Вставляем рядом с кнопкой
  const actionContainer = candidateElement.querySelector('.candidate-actions') 
    || candidateElement.querySelector('.candidate-header')
    || candidateElement;
  
  actionContainer.appendChild(badge);
}

/**
 * Переводит state ID в читаемый текст
 */
function translateState(stateId) {
  const states = {
    'invitation': 'Приглашен',
    'response': 'Откликнулся',
    'discard': 'Отказ',
    'hired': 'Нанят',
    'offer': 'Предложение',
    'phone_interview': 'Телефонное интервью',
    'interview': 'Собеседование',
  };
  
  return states[stateId] || stateId;
}

/**
 * Обработчик клика по кнопке приглашения
 */
async function handleInviteClick(vacancyId, resumeId, button) {
  // Сохраняем оригинальный текст
  const originalText = button.textContent;
  
  // Показываем загрузку
  button.disabled = true;
  button.textContent = '⏳ Отправка...';
  
  try {
    // Отправляем приглашение (ваша существующая функция)
    await sendInvitation(vacancyId, resumeId);
    
    // Успех
    button.textContent = '✅ Отправлено';
    button.style.background = '#4CAF50';
    
    // Обновляем статус после отправки
    setTimeout(async () => {
      const newStatus = await checkCandidateStatus(vacancyId, resumeId, true);
      updateCandidateUI(button.closest('.candidate-item'), newStatus);
    }, 1000);
    
  } catch (error) {
    console.error('Error sending invitation:', error);
    
    // Показываем ошибку
    button.textContent = '❌ Ошибка';
    button.style.background = '#F44336';
    
    // Возвращаем исходное состояние через 3 секунды
    setTimeout(() => {
      button.textContent = originalText;
      button.style.background = '#00A0DC';
      button.disabled = false;
    }, 3000);
  }
}

/**
 * Функция отправки приглашения (ваша существующая)
 */
async function sendInvitation(vacancyId, resumeId) {
  // TODO: Адаптируйте под вашу реализацию
  const { authToken } = await chrome.storage.local.get('authToken');
  
  const response = await fetch(`${API_BASE_URL}/send-invitation/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${authToken}`
    },
    body: JSON.stringify({
      vacancy_id: vacancyId,
      resume_id: resumeId
    })
  });
  
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  
  return await response.json();
}

// Запускаем при загрузке страницы
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initializeCandidateStatusCheck);
} else {
  initializeCandidateStatusCheck();
}

// Наблюдаем за динамическим добавлением кандидатов
const observer = new MutationObserver((mutations) => {
  mutations.forEach((mutation) => {
    mutation.addedNodes.forEach((node) => {
      if (node.nodeType === 1 && node.classList.contains('candidate-item')) {
        // Проверяем статус для нового кандидата
        const vacancyId = extractVacancyId();
        const resumeId = extractResumeId(node);
        
        if (vacancyId && resumeId) {
          checkCandidateStatus(vacancyId, resumeId).then(status => {
            updateCandidateUI(node, status);
          });
        }
      }
    });
  });
});

observer.observe(document.body, {
  childList: true,
  subtree: true
});

### Шаг 2.3: Обновление manifest.json

**Файл:** `extension/manifest.json`

Убедитесь, что permissions включают необходимые API:

{
  "manifest_version": 3,
  "name": "HH Extension",
  "version": "2.0.0",
  
  "permissions": [
    "storage",
    "activeTab"
  ],
  
  "host_permissions": [
    "https://api.hh.ru/*",
    "http://localhost:8000/*",
    "https://your-backend.com/*"
  ],
  
  "content_scripts": [
    {
      "matches": [
        "https://hh.ru/*",
        "https://*.hh.ru/*"
      ],
      "js": [
        "content/candidate-list.js"
      ],
      "run_at": "document_idle"
    }
  ],
  
  "background": {
    "service_worker": "background.js"
  }
}

### Шаг 2.4: Добавление стилей

**Файл:** `extension/src/styles/content.css` (создайте если нет)

/* Кнопка приглашения */
.hh-extension-invite-btn {
  padding: 6px 12px;
  background: #00A0DC;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  margin-left: 8px;
  transition: all 0.3s ease;
}

.hh-extension-invite-btn:hover:not(:disabled) {
  background: #0088C2;
  transform: translateY(-1px);
  box-shadow: 0 2px 4px rgba(0, 160, 220, 0.3);
}

.hh-extension-invite-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* Статус-бейдж */
.hh-extension-status-badge {
  display: inline-block;
  padding: 4px 10px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 500;
  margin-left: 8px;
  white-space: nowrap;
}

/* Анимация появления */
.hh-extension-invite-btn,
.hh-extension-status-badge {
  animation: fadeIn 0.3s ease-in;
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(-5px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* Индикатор загрузки */
.hh-extension-loading {
  display: inline-block;
  width: 16px;
  height: 16px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  margin-right: 8px;
  vertical-align: middle;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

Подключите CSS в manifest.json:

"content_scripts": [
  {
    "matches": ["https://hh.ru/*"],
    "js": ["content/candidate-list.js"],
    "css": ["styles/content.css"],
    "run_at": "document_idle"
  }
]

### Шаг 2.5: Сборка расширения

Если используете сборщик (webpack/vite):

cd extension
npm run build

Если без сборщика - просто убедитесь что все файлы на месте.

### Шаг 2.6: Загрузка расширения в Chrome

\begin{enumerate}
\item Откройте Chrome
\item Перейдите в \texttt{chrome://extensions/}
\item Включите "Режим разработчика" (Developer mode)
\item Нажмите "Загрузить распакованное расширение" (Load unpacked)
\item Выберите папку \texttt{extension/} (или \texttt{extension/dist/} если есть сборка)
\item Расширение установлено!
\end{enumerate}

## Часть 3: Тестирование

### Шаг 3.1: Тестирование Backend

**Тест 1: Проверка статуса (нет negotiation)**

curl -X POST http://localhost:8000/api/negotiations/check-status/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "vacancy_id": "123456",
    "resume_id": "new_resume_hash"
  }'

Ожидаемый результат:

{
  "show_button": true,
  "reason": "no_negotiation",
  "state": null,
  "negotiation_id": null,
  "state_name": null
}

**Тест 2: Проверка статуса (есть приглашение)**

curl -X POST http://localhost:8000/api/negotiations/check-status/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "vacancy_id": "123456",
    "resume_id": "existing_resume_hash"
  }'

Ожидаемый результат:

{
  "show_button": false,
  "reason": "already_exists",
  "state": "invitation",
  "negotiation_id": "789012",
  "state_name": "Приглашение"
}

**Тест 3: Проверка кэширования**

Выполните тест 1 дважды подряд и проверьте логи:

# Первый запрос
Fetching negotiations for vacancy 123456 from HH.ru API
Cached 25 negotiations for vacancy 123456

# Второй запрос (должен быть из кэша)
Negotiations for vacancy 123456 loaded from cache

**Тест 4: Force refresh**

curl -X POST http://localhost:8000/api/negotiations/check-status/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "vacancy_id": "123456",
    "resume_id": "test_hash",
    "force_refresh": true
  }'

Должен обновить кэш даже если он не истек.

### Шаг 3.2: Тестирование Extension

**Тест 1: Проверка инициализации**

\begin{enumerate}
\item Откройте Developer Tools (F12)
\item Перейдите на страницу со списком кандидатов HH.ru
\item В Console должны появиться логи:
\end{enumerate}

Initializing candidate status check...
Found 15 candidates, checking statuses...
Candidate status check completed

**Тест 2: Визуальная проверка UI**

\begin{enumerate}
\item На странице должны появиться кнопки "✉️ Пригласить" у новых кандидатов
\item У кандидатов с существующими откликами - бейджи со статусом
\item Цвета бейджей соответствуют статусам
\end{enumerate}

**Тест 3: Проверка отправки приглашения**

\begin{enumerate}
\item Нажмите кнопку "Пригласить" у любого кандидата
\item Кнопка должна показать "⏳ Отправка..."
\item После успеха: "✅ Отправлено"
\item Через секунду кнопка скрывается, появляется бейдж "Приглашен"
\end{enumerate}

**Тест 4: Динамическое добавление кандидатов**

\begin{enumerate}
\item Прокрутите страницу вниз (если есть бесконечная прокрутка)
\item Новые кандидаты должны автоматически получить кнопки/бейджи
\item Проверьте в Network tab что запросы идут к API
\end{enumerate}

### Шаг 3.3: Чек-лист тестирования

\begin{table}
\begin{tabular}{|l|c|}
\hline
\textbf{Тест} & \textbf{Статус} \\
\hline
Backend endpoint доступен & ☐ \\
Кэш работает корректно & ☐ \\
Force refresh обновляет кэш & ☐ \\
Extension загружается без ошибок & ☐ \\
Кнопки появляются у новых кандидатов & ☐ \\
Бейджи показываются у существующих & ☐ \\
Отправка приглашения работает & ☐ \\
UI обновляется после отправки & ☐ \\
MutationObserver отслеживает новых кандидатов & ☐ \\
Нет ошибок в Console & ☐ \\
\hline
\end{tabular}
\caption{Чек-лист финального тестирования}
\end{table}

## Часть 4: Деплой и мониторинг

### Шаг 4.1: Настройка production окружения

**Backend (Django):**

\begin{enumerate}
\item Настройте Redis для кэша (см. Шаг 1.6)
\item Обновите \texttt{ALLOWED\_HOSTS} в settings.py
\item Настройте CORS если нужно
\item Соберите статику: \texttt{python manage.py collectstatic}
\item Настройте Gunicorn/uWSGI
\item Настройте Nginx как reverse proxy
\end{enumerate}

**Extension:**

\begin{enumerate}
\item Обновите \texttt{API\_BASE\_URL} на production URL
\item Создайте production build: \texttt{npm run build}
\item Упакуйте для Chrome Web Store (если публикуете)
\end{enumerate}

### Шаг 4.2: Мониторинг и логирование

**Добавьте логирование в Backend:**

import logging

logger = logging.getLogger(__name__)

@api_view(['POST'])
def check_candidate_status(request):
    logger.info(f"Checking status for vacancy={vacancy_id}, resume={resume_id}")
    # ... ваш код ...
    logger.info(f"Status check result: show_button={result['show_button']}")

**Настройте logging в settings.py:**

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': '/var/log/hh_extension/api.log',
        },
    },
    'loggers': {
        'api': {
            'handlers': ['file'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}

### Шаг 4.3: Метрики для отслеживания

Полезные метрики:

\begin{itemize}
\item Количество проверок статуса в день
\item Hit rate кэша (сколько запросов обслужено из кэша)
\item Среднее время ответа API
\item Количество ошибок при обращении к HH.ru API
\item Процент показа кнопок vs бейджей
\end{itemize}

### Шаг 4.4: Частые проблемы и решения

\begin{table}
\begin{tabular}{|l|l|}
\hline
\textbf{Проблема} & \textbf{Решение} \\
\hline
Кнопки не появляются & Проверьте селекторы в extractResumeId() \\
API возвращает 401 & Проверьте токен в chrome.storage \\
Кэш не работает & Проверьте настройки CACHES в settings.py \\
HH API rate limit & Увеличьте интервалы между запросами \\
Медленная загрузка & Уменьшите chunkSize в checkMultipleCandidates \\
\hline
\end{tabular}
\caption{Troubleshooting таблица}
\end{table}

## Заключение

Поздравляю! Вы успешно добавили функционал проверки статусов кандидатов.

**Что теперь умеет система:**

\begin{itemize}
\item Автоматически проверяет, есть ли уже отклик/приглашение
\item Кэширует данные для быстрой работы
\item Показывает кнопку только когда это уместно
\item Отображает текущий статус взаимодействия с кандидатом
\item Обновляет UI в реальном времени
\end{itemize}