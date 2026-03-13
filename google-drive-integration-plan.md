# План интеграции Google Drive в HR Helper расширение

**Цель:** Добавить возможность парсинга резюме из Google Drive через расширение Chrome и создание кандидатов в Huntflow.

**Дата:** 13 марта 2026

---

## ШАГ 1: Обновляем manifest.json

**Файл:** `published/hr/chrome-extension/hrhelper-linkedin-huntflow/manifest.json`

### Что делать:

1. Открой файл `manifest.json`
2. Найди секцию `"host_permissions":`
3. Добавь в конец списка (перед последней скобкой):

```json
"https://drive.google.com/*",
"https://www.googleapis.com/*"
```

4. Найди секцию `"content_scripts":`
5. Добавь в конец массива (перед закрывающей скобкой `]`):

```json
,
{
  "matches": [
    "https://drive.google.com/file/d/*"
  ],
  "js": [
    "shared/constants.js",
    "shared/utils/debounce.js",
    "shared/utils/token.js",
    "shared/utils/url.js",
    "shared/utils/date.js",
    "shared/utils/color.js",
    "shared/domain/status-logic.js",
    "shared/api/client.js",
    "shared/api/status.js",
    "content-gdrive.js"
  ],
  "run_at": "document_end"
}
```

6. Сохрани файл

---

## ШАГ 2: Создаём новый файл content-gdrive.js

**Файл:** `published/hr/chrome-extension/hrhelper-linkedin-huntflow/content-gdrive.js`

### Что делать:

1. Создай новый файл с именем `content-gdrive.js`
2. Скопируй и вставь туда весь этот код:

```javascript
(function() {
  'use strict';

  console.log('[HR Helper] Google Drive content script loaded');

  // Извлечение fileId из URL
  function extractFileId() {
    const url = window.location.href;
    const match = url.match(/\/file\/d\/([a-zA-Z0-9_-]+)/);
    return match ? match[1] : null;
  }

  // Наблюдение за изменениями URL
  let lastFileId = null;

  function checkAndNotifyFileId() {
    const fileId = extractFileId();
    if (fileId && fileId !== lastFileId) {
      lastFileId = fileId;
      
      // Отправляем в background для хранения
      chrome.runtime.sendMessage({
        type: 'HRHELPER_GDRIVE_FILE_DETECTED',
        payload: { 
          fileId: fileId, 
          url: window.location.href 
        }
      });
      
      console.log('[HR Helper] Google Drive file detected:', fileId);
    }
  }

  // Проверяем при загрузке
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', checkAndNotifyFileId);
  } else {
    checkAndNotifyFileId();
  }

  // Наблюдаем за изменениями истории (SPA)
  let lastUrl = location.href;
  new MutationObserver(() => {
    const url = location.href;
    if (url !== lastUrl) {
      lastUrl = url;
      checkAndNotifyFileId();
    }
  }).observe(document, { subtree: true, childList: true });

})();
```

3. Сохрани файл

---

## ШАГ 3: Обновляем background.js

**Файл:** `published/hr/chrome-extension/hrhelper-linkedin-huntflow/background.js`

### 3.1: Добавляем распознавание Google Drive

1. Открой файл `background.js`
2. Найди функцию `getPageTypeFromUrl`
3. Найди строчку с `if (host.includes("huntflow")...`
4. **ПЕРЕД** этой строкой добавь:

```javascript
    if (host.includes("drive.google.com") && path.includes("/file/d/")) {
      return "gdrive";
    }
```

### 3.2: Добавляем обработчик сообщений

1. Найди строчку `chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {`
2. Найди проверку `if (msg.type === "HRHELPER_OPEN_TABS") {`
3. **ПЕРЕД** этой проверкой добавь:

```javascript
  if (msg.type === 'HRHELPER_GDRIVE_FILE_DETECTED') {
    // Сохраняем fileId в storage для доступа из popup
    chrome.storage.local.set({
      currentGDriveFile: msg.payload
    }).then(() => {
      sendResponse({ success: true });
    }).catch((error) => {
      sendResponse({ success: false, error: error.message });
    });
    return true;
  }

```

4. Сохрани файл

---

## ШАГ 4: Обновляем shared/constants.js

**Файл:** `published/hr/chrome-extension/hrhelper-linkedin-huntflow/shared/constants.js`

### Что делать:

1. Открой файл `shared/constants.js`
2. Найди объект `DEFAULT_ACTIVE_PAGES:`
3. Добавь в конец (перед закрывающей скобкой):

```javascript
    gdrive: true,
```

4. Сохрани файл

---

## ШАГ 5: Создаём API методы для Google Drive

**Файл:** `published/hr/chrome-extension/hrhelper-linkedin-huntflow/shared/api/gdrive.js`

### Что делать:

1. Создай новый файл `gdrive.js` в папке `shared/api/`
2. Скопируй и вставь туда весь этот код:

```javascript
(function() {
  'use strict';

  if (typeof self !== 'undefined' && self.__HRH__) {
    self.__HRH__.api = self.__HRH__.api || {};

    /**
     * Отправка Google Drive файла на бэкенд для парсинга
     */
    self.__HRH__.api.parseGDriveResume = async function(fileId, vacancyId) {
      return await self.__HRH__.apiCall({
        path: '/api/parse-gdrive-resume/',
        method: 'POST',
        body: { file_id: fileId, vacancy_id: vacancyId }
      });
    };

    /**
     * Получение списка активных вакансий
     */
    self.__HRH__.api.getActiveVacancies = async function() {
      return await self.__HRH__.apiCall({
        path: '/api/vacancies/active/',
        method: 'GET'
      });
    };

    /**
     * Создание кандидата в Huntflow из распарсенного резюме
     */
    self.__HRH__.api.createCandidateFromGDrive = async function(candidateData, vacancyId) {
      return await self.__HRH__.apiCall({
        path: '/api/candidates/create-from-gdrive/',
        method: 'POST',
        body: {
          ...candidateData,
          vacancy_id: vacancyId
        }
      });
    };

  }
})();
```

3. Сохрани файл

---

## ШАГ 6: Обновляем popup.html

**Файл:** `published/hr/chrome-extension/hrhelper-linkedin-huntflow/popup.html`

### Что делать:

1. Открой файл `popup.html`
2. Найди **ПОСЛЕДНЮЮ** закрывающую `</div>` перед `<script src="popup.js"></script>`
3. **ПЕРЕД** строкой `<script src="popup.js"></script>` добавь:

```html
<!-- Google Drive Section -->
<div id="gdrive-section" class="section" style="display: none;">
  <h3>📄 Резюме из Google Drive</h3>
  
  <div id="gdrive-file-info" class="info-box" style="background: #f0f0f0; padding: 10px; margin: 10px 0; border-radius: 5px;">
    <p><strong>File ID:</strong> <span id="gdrive-file-id" style="font-family: monospace;">—</span></p>
  </div>

  <!-- Выбор вакансии -->
  <div class="form-group" style="margin: 15px 0;">
    <label for="gdrive-vacancy-select"><strong>Выберите вакансию:</strong></label>
    <select id="gdrive-vacancy-select" class="form-control" style="width: 100%; padding: 8px; margin-top: 5px;" disabled>
      <option value="">— Загрузка вакансий —</option>
    </select>
  </div>

  <!-- Предпросмотр распарсенных данных -->
  <div id="gdrive-parsed-preview" style="display: none; background: #e8f5e9; padding: 15px; margin: 10px 0; border-radius: 5px;">
    <h4 style="margin-top: 0;">✅ Предпросмотр данных</h4>
    <div class="candidate-preview">
      <p><strong>ФИО:</strong> <span id="preview-name">—</span></p>
      <p><strong>Email:</strong> <span id="preview-email">—</span></p>
      <p><strong>Телефон:</strong> <span id="preview-phone">—</span></p>
      <p><strong>Позиция:</strong> <span id="preview-position">—</span></p>
    </div>
  </div>

  <!-- Кнопки действий -->
  <div class="button-group" style="margin: 15px 0;">
    <button id="gdrive-parse-btn" class="btn btn-primary" style="padding: 10px 20px; margin-right: 10px;" disabled>
      🔍 Распарсить резюме
    </button>
    <button id="gdrive-save-btn" class="btn btn-success" style="padding: 10px 20px; display: none;" disabled>
      ✅ Сохранить в Huntflow
    </button>
  </div>

  <!-- Результат -->
  <div id="gdrive-result" class="result-box" style="display: none; background: #e3f2fd; padding: 15px; margin: 10px 0; border-radius: 5px;">
    <div class="success-message">
      <p><strong>✅ Кандидат создан успешно!</strong></p>
      <p><strong>ФИО:</strong> <span id="result-name"></span></p>
      <p><strong>Вакансия:</strong> <span id="result-vacancy"></span></p>
      <a id="result-link" href="#" target="_blank" class="btn btn-link" style="display: inline-block; margin: 10px 0; padding: 8px 15px; background: #2196F3; color: white; text-decoration: none; border-radius: 4px;">
        🔗 Открыть в Huntflow
      </a>
      <button id="result-change-status" class="btn btn-secondary" style="padding: 8px 15px; margin-left: 10px;">
        📝 Изменить статус
      </button>
    </div>
  </div>

  <!-- Сообщения об ошибках -->
  <div id="gdrive-error" class="error-box" style="display: none; background: #ffebee; color: #c62828; padding: 15px; margin: 10px 0; border-radius: 5px; border-left: 4px solid #c62828;"></div>
</div>
```

4. Сохрани файл

---

## ШАГ 7: Обновляем popup.js

**Файл:** `published/hr/chrome-extension/hrhelper-linkedin-huntflow/popup.js`

### 7.1: Добавляем переменные в начало файла

1. Открой файл `popup.js`
2. Найди самое начало файла (после всех комментариев)
3. В самом начале скрипта (после `'use strict';` если есть) добавь:

```javascript
// Google Drive state
let currentGDriveFileId = null;
let parsedCandidateData = null;
let selectedVacancyId = null;
```

### 7.2: Обновляем функцию определения страницы

1. Найди функцию, которая определяет тип активной страницы (обычно что-то вроде `init()` или проверка URL)
2. Добавь проверку на Google Drive. Найди где проверяется `url.includes` и добавь:

```javascript
  if (url.includes('drive.google.com/file/d/')) {
    await initGDriveSection();
    return;
  }
```

### 7.3: Добавляем все функции для Google Drive

1. Найди **КОНЕЦ** файла (перед последней закрывающей скобкой или перед `})();`)
2. Добавь туда все эти функции:

```javascript
// ============ GOOGLE DRIVE FUNCTIONS ============

async function initGDriveSection() {
  console.log('[HR Helper] Initializing Google Drive section');
  const section = document.getElementById('gdrive-section');
  if (!section) {
    console.error('[HR Helper] Google Drive section not found in popup.html');
    return;
  }
  
  section.style.display = 'block';
  
  // Получаем fileId из storage
  try {
    const data = await chrome.storage.local.get('currentGDriveFile');
    if (data.currentGDriveFile && data.currentGDriveFile.fileId) {
      currentGDriveFileId = data.currentGDriveFile.fileId;
      document.getElementById('gdrive-file-id').textContent = currentGDriveFileId;
      console.log('[HR Helper] File ID loaded:', currentGDriveFileId);
      
      // Загружаем список вакансий
      await loadActiveVacancies();
    } else {
      showGDriveError('Не удалось получить ID файла. Перезагрузите страницу.');
    }
  } catch (error) {
    console.error('[HR Helper] Error loading file ID:', error);
    showGDriveError('Ошибка загрузки данных файла: ' + error.message);
  }
  
  // Обработчики событий
  setupGDriveEventHandlers();
}

async function loadActiveVacancies() {
  console.log('[HR Helper] Loading active vacancies');
  const select = document.getElementById('gdrive-vacancy-select');
  
  try {
    const response = await chrome.runtime.sendMessage({
      type: 'HRHELPER_API',
      payload: {
        path: '/api/vacancies/active/',
        method: 'GET'
      }
    });
    
    console.log('[HR Helper] Vacancies response:', response);
    
    if (response.ok && response.json && response.json.vacancies) {
      select.innerHTML = '<option value="">— Выберите вакансию —</option>';
      
      response.json.vacancies.forEach(vacancy => {
        const option = document.createElement('option');
        option.value = vacancy.id;
        option.textContent = `${vacancy.position}${vacancy.company ? ' (' + vacancy.company + ')' : ''}`;
        option.dataset.vacancyUrl = vacancy.huntflow_url || '';
        option.dataset.vacancyName = vacancy.position;
        select.appendChild(option);
      });
      
      select.disabled = false;
      console.log('[HR Helper] Loaded', response.json.vacancies.length, 'vacancies');
    } else {
      throw new Error(response.json?.message || 'Не удалось загрузить вакансии');
    }
  } catch (error) {
    console.error('[HR Helper] Error loading vacancies:', error);
    showGDriveError('Ошибка загрузки вакансий: ' + error.message);
  }
}

function setupGDriveEventHandlers() {
  const vacancySelect = document.getElementById('gdrive-vacancy-select');
  const parseBtn = document.getElementById('gdrive-parse-btn');
  const saveBtn = document.getElementById('gdrive-save-btn');
  const changeStatusBtn = document.getElementById('result-change-status');
  
  // Выбор вакансии
  vacancySelect.addEventListener('change', (e) => {
    selectedVacancyId = e.target.value ? parseInt(e.target.value) : null;
    parseBtn.disabled = !selectedVacancyId || !currentGDriveFileId;
    console.log('[HR Helper] Vacancy selected:', selectedVacancyId);
  });
  
  // Парсинг резюме
  parseBtn.addEventListener('click', async () => {
    console.log('[HR Helper] Parse button clicked');
    await parseGDriveResume();
  });
  
  // Сохранение кандидата
  saveBtn.addEventListener('click', async () => {
    console.log('[HR Helper] Save button clicked');
    await saveCandidate();
  });
  
  // Изменение статуса (пока заглушка)
  changeStatusBtn.addEventListener('click', () => {
    alert('Функция изменения статуса будет добавлена позже');
  });
}

async function parseGDriveResume() {
  const parseBtn = document.getElementById('gdrive-parse-btn');
  const preview = document.getElementById('gdrive-parsed-preview');
  const errorBox = document.getElementById('gdrive-error');
  
  parseBtn.disabled = true;
  parseBtn.textContent = '⏳ Парсинг...';
  errorBox.style.display = 'none';
  
  try {
    console.log('[HR Helper] Sending parse request:', {
      fileId: currentGDriveFileId,
      vacancyId: selectedVacancyId
    });
    
    const response = await chrome.runtime.sendMessage({
      type: 'HRHELPER_API',
      payload: {
        path: '/api/parse-gdrive-resume/',
        method: 'POST',
        body: {
          file_id: currentGDriveFileId,
          vacancy_id: selectedVacancyId
        }
      }
    });
    
    console.log('[HR Helper] Parse response:', response);
    
    if (response.ok && response.json) {
      parsedCandidateData = response.json;
      
      // Показываем предпросмотр
      document.getElementById('preview-name').textContent = 
        parsedCandidateData.full_name || '—';
      document.getElementById('preview-email').textContent = 
        parsedCandidateData.email || '—';
      document.getElementById('preview-phone').textContent = 
        parsedCandidateData.phone || '—';
      document.getElementById('preview-position').textContent = 
        parsedCandidateData.position || '—';
      
      preview.style.display = 'block';
      
      // Показываем кнопку сохранения
      const saveBtn = document.getElementById('gdrive-save-btn');
      saveBtn.style.display = 'inline-block';
      saveBtn.disabled = false;
      
      console.log('[HR Helper] Parse successful, showing preview');
      
    } else {
      throw new Error(response.json?.message || response.json?.error || 'Ошибка парсинга резюме');
    }
    
  } catch (error) {
    console.error('[HR Helper] Parse error:', error);
    showGDriveError('Ошибка парсинга резюме: ' + error.message);
  } finally {
    parseBtn.disabled = false;
    parseBtn.textContent = '🔍 Распарсить резюме';
  }
}

async function saveCandidate() {
  const saveBtn = document.getElementById('gdrive-save-btn');
  const resultBox = document.getElementById('gdrive-result');
  const errorBox = document.getElementById('gdrive-error');
  const vacancySelect = document.getElementById('gdrive-vacancy-select');
  
  saveBtn.disabled = true;
  saveBtn.textContent = '⏳ Сохранение...';
  errorBox.style.display = 'none';
  
  try {
    console.log('[HR Helper] Sending save request:', parsedCandidateData);
    
    const response = await chrome.runtime.sendMessage({
      type: 'HRHELPER_API',
      payload: {
        path: '/api/candidates/create-from-gdrive/',
        method: 'POST',
        body: {
          ...parsedCandidateData,
          vacancy_id: selectedVacancyId,
          file_id: currentGDriveFileId
        }
      }
    });
    
    console.log('[HR Helper] Save response:', response);
    
    if (response.ok && response.json) {
      const candidate = response.json;
      
      // Получаем название вакансии
      const selectedOption = vacancySelect.options[vacancySelect.selectedIndex];
      const vacancyName = selectedOption ? selectedOption.dataset.vacancyName : 'Вакансия';
      
      // Показываем результат
      document.getElementById('result-name').textContent = candidate.full_name || parsedCandidateData.full_name;
      document.getElementById('result-vacancy').textContent = vacancyName;
      
      const link = document.getElementById('result-link');
      link.href = candidate.huntflow_url || '#';
      
      resultBox.style.display = 'block';
      
      // Скрываем форму
      document.getElementById('gdrive-parsed-preview').style.display = 'none';
      saveBtn.style.display = 'none';
      document.getElementById('gdrive-parse-btn').style.display = 'none';
      vacancySelect.disabled = true;
      
      console.log('[HR Helper] Candidate saved successfully');
      
    } else {
      throw new Error(response.json?.message || response.json?.error || 'Ошибка создания кандидата');
    }
    
  } catch (error) {
    console.error('[HR Helper] Save error:', error);
    showGDriveError('Ошибка сохранения: ' + error.message);
  } finally {
    saveBtn.disabled = false;
    saveBtn.textContent = '✅ Сохранить в Huntflow';
  }
}

function showGDriveError(message) {
  const errorBox = document.getElementById('gdrive-error');
  errorBox.textContent = '❌ ' + message;
  errorBox.style.display = 'block';
  console.error('[HR Helper]', message);
}
```

3. Сохрани файл

---

## ШАГ 8: Обновляем options.html (настройки)

**Файл:** `published/hr/chrome-extension/hrhelper-linkedin-huntflow/options.html`

### Что делать:

1. Открой файл `options.html`
2. Найди секцию с чекбоксами активных страниц (где есть `active-linkedin`, `active-calendar` и т.д.)
3. Добавь после последнего чекбокса:

```html
<div class="setting-item">
  <label>
    <input type="checkbox" id="active-gdrive" />
    <span>Google Drive (парсинг резюме)</span>
  </label>
</div>
```

4. Сохрани файл

---

## ШАГ 9: Обновляем options.js

**Файл:** `published/hr/chrome-extension/hrhelper-linkedin-huntflow/options.js`

### Что делать:

1. Открой файл `options.js`
2. Найди где сохраняются/загружаются чекбоксы активных страниц
3. Добавь обработку `gdrive` аналогично другим страницам (обычно это массив типа `['linkedin', 'calendar', 'meet', ...]`)
4. Добавь `'gdrive'` в этот массив
5. Сохрани файл

---

## ШАГ 10: Создаём API endpoints на бэкенде (Django)

**Путь:** Твой Django проект, например `hr_helper/api/views.py`

### Что делать:

1. Создай или открой файл с API views
2. Добавь три новых endpoint'а:

```python
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
import requests

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_active_vacancies(request):
    """
    Получение списка активных вакансий из Huntflow
    """
    try:
        # TODO: Получить токен из настроек пользователя
        huntflow_token = request.user.profile.huntflow_token
        
        # TODO: Твоя логика получения вакансий через Huntflow API
        # Пример структуры ответа:
        vacancies = [
            {
                'id': 123,
                'position': 'Python Developer',
                'company': 'Softnetix',
                'huntflow_url': 'https://softnetix.huntflow.ru/vacancy/123'
            },
            # ... другие вакансии
        ]
        
        return Response({
            'vacancies': vacancies
        })
        
    except Exception as e:
        return Response({'error': str(e)}, status=500)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def parse_gdrive_resume(request):
    """
    Скачивание и парсинг резюме из Google Drive
    """
    file_id = request.data.get('file_id')
    vacancy_id = request.data.get('vacancy_id')
    
    if not file_id:
        return Response({'error': 'file_id is required'}, status=400)
    
    try:
        # Формируем URL для скачивания
        download_url = f"https://drive.google.com/uc?export=download&id={file_id}"
        
        # Скачиваем файл
        response = requests.get(download_url, timeout=30)
        response.raise_for_status()
        file_bytes = response.content
        
        # TODO: Здесь твоя логика парсинга резюме
        # Пример заглушки:
        parsed_data = {
            'full_name': 'Иванов Иван Иванович',
            'email': 'ivanov@example.com',
            'phone': '+375291234567',
            'position': 'Python Developer',
            'file_id': file_id,
            'vacancy_id': vacancy_id
        }
        
        return Response(parsed_data)
        
    except requests.RequestException as e:
        return Response({'error': f'Ошибка скачивания файла: {str(e)}'}, status=500)
    except Exception as e:
        return Response({'error': str(e)}, status=500)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_candidate_from_gdrive(request):
    """
    Создание кандидата в Huntflow из распарсенного резюме
    """
    try:
        candidate_data = request.data
        vacancy_id = candidate_data.get('vacancy_id')
        file_id = candidate_data.get('file_id')
        
        # TODO: Твоя логика создания кандидата через Huntflow API
        # Используй существующую функцию создания кандидата
        
        # Пример структуры ответа:
        result = {
            'id': 456,
            'full_name': candidate_data.get('full_name'),
            'vacancy_name': 'Python Developer',
            'huntflow_url': f'https://softnetix.huntflow.ru/applicants/456',
            'status': 'created'
        }
        
        return Response(result)
        
    except Exception as e:
        return Response({'error': str(e)}, status=500)
```

3. Сохрани файл

---

## ШАГ 11: Добавляем URL'ы в Django

**Файл:** `hr_helper/api/urls.py` (или где у тебя роуты API)

### Что делать:

1. Открой файл с URL'ами
2. Добавь три новых пути:

```python
from django.urls import path
from . import views

urlpatterns = [
    # ... существующие пути ...
    
    path('vacancies/active/', views.get_active_vacancies, name='get_active_vacancies'),
    path('parse-gdrive-resume/', views.parse_gdrive_resume, name='parse_gdrive_resume'),
    path('candidates/create-from-gdrive/', views.create_candidate_from_gdrive, name='create_candidate_from_gdrive'),
]
```

3. Сохрани файл

---

## ШАГ 12: Тестирование

### Что делать:

1. **Перезагрузи расширение в Chrome:**
   - Открой `chrome://extensions/`
   - Найди "HR Helper"
   - Нажми кнопку обновления (🔄)

2. **Открой страницу Google Drive файла:**
   - Открой https://drive.google.com/file/d/13JKJn18WMycM5nRglquex1XCyZevMMWG/view

3. **Открой консоль разработчика:**
   - Нажми `F12`
   - Должно появиться сообщение: `[HR Helper] Google Drive file detected: 13JKJn18WMycM5nRglquex1XCyZevMMWG`

4. **Открой popup расширения:**
   - Кликни на иконку расширения
   - Должна появиться секция "📄 Резюме из Google Drive"
   - Должен отображаться File ID

5. **Проверь работу:**
   - Выбери вакансию из списка
   - Нажми "Распарсить резюме"
   - Проверь предпросмотр данных
   - Нажми "Сохранить в Huntflow"
   - Проверь что кандидат создался

---

## ШАГ 13: Отладка (если что-то не работает)

### Что проверять:

1. **Проверь консоль background.js:**
   - `chrome://extensions/` → HR Helper → "service worker" (ссылка)
   - Смотри ошибки

2. **Проверь консоль popup:**
   - Открой popup → Правой кнопкой → "Inspect"
   - Смотри ошибки

3. **Проверь консоль content script:**
   - На странице Google Drive → `F12` → Console
   - Должны быть логи `[HR Helper]`

4. **Проверь бэкенд:**
   - Смотри логи Django
   - Проверь что endpoints доступны
   - Проверь токен авторизации

5. **Частые проблемы:**
   - **Файл не определяется:** Проверь что URL содержит `/file/d/`
   - **Popup пустой:** Проверь что `gdrive-section` добавлен в HTML
   - **Ошибка 404 на API:** Проверь что URLs правильно настроены
   - **CORS ошибки:** Проверь что `host_permissions` добавлены в manifest
   - **Вакансии не загружаются:** Проверь endpoint `/api/vacancies/active/`
   - **Парсинг не работает:** Проверь что файл публичный в Google Drive

---

## Архитектура решения

```
┌─────────────────────────────────────────────────────────────┐
│                    GOOGLE DRIVE PAGE                        │
│  https://drive.google.com/file/d/FILE_ID/view              │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      │ content-gdrive.js
                      │ Извлекает FILE_ID
                      ↓
┌─────────────────────────────────────────────────────────────┐
│                    BACKGROUND.JS                            │
│  - Получает FILE_ID                                        │
│  - Сохраняет в chrome.storage.local                        │
│  - Обрабатывает API запросы                                │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ↓
┌─────────────────────────────────────────────────────────────┐
│                      POPUP.JS                               │
│  1. Загружает FILE_ID из storage                          │
│  2. Загружает список вакансий                              │
│  3. Отправляет FILE_ID на парсинг                          │
│  4. Показывает предпросмотр                                │
│  5. Создаёт кандидата                                      │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      │ HTTP API
                      ↓
┌─────────────────────────────────────────────────────────────┐
│                  DJANGO BACKEND                             │
│                                                             │
│  GET  /api/vacancies/active/                               │
│       → Список активных вакансий                           │
│                                                             │
│  POST /api/parse-gdrive-resume/                            │
│       → Скачивает файл из Google Drive                     │
│       → Парсит резюме                                      │
│       → Возвращает данные кандидата                        │
│                                                             │
│  POST /api/candidates/create-from-gdrive/                  │
│       → Создаёт кандидата в Huntflow                       │
│       → Возвращает ссылку на кандидата                     │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      │ Huntflow API
                      ↓
┌─────────────────────────────────────────────────────────────┐
│                    HUNTFLOW                                 │
│  - Создание кандидата                                      │
│  - Привязка к вакансии                                     │
│  - Установка статуса                                       │
└─────────────────────────────────────────────────────────────┘
```

---

## Готово! 🎉

Теперь при открытии Google Drive файла расширение будет:

1. ✅ Определять что это страница Google Drive
2. ✅ Извлекать ID файла из URL
3. ✅ Показывать секцию в popup
4. ✅ Загружать список активных вакансий
5. ✅ Позволять выбрать вакансию
6. ✅ Отправлять файл на парсинг через бэкенд
7. ✅ Показывать предпросмотр распарсенных данных
8. ✅ Создавать кандидата в Huntflow с привязкой к вакансии
9. ✅ Показывать ссылку на созданного кандидата

---

## Контрольный чеклист

- [ ] Обновлён `manifest.json` (host_permissions + content_scripts)
- [ ] Создан `content-gdrive.js`
- [ ] Обновлён `background.js` (getPageTypeFromUrl + обработчик сообщений)
- [ ] Обновлён `shared/constants.js` (добавлен gdrive в DEFAULT_ACTIVE_PAGES)
- [ ] Создан `shared/api/gdrive.js`
- [ ] Обновлён `popup.html` (добавлена секция gdrive-section)
- [ ] Обновлён `popup.js` (добавлены переменные и функции)
- [ ] Обновлён `options.html` (добавлен чекбокс)
- [ ] Обновлён `options.js` (добавлена обработка gdrive)
- [ ] Созданы Django endpoints (3 штуки)
- [ ] Добавлены URL'ы в Django urls.py
- [ ] Расширение перезагружено в Chrome
- [ ] Протестирована работа на реальном файле

---

**Дата создания:** 13 марта 2026
**Автор:** HR Helper Team
**Версия:** 1.0