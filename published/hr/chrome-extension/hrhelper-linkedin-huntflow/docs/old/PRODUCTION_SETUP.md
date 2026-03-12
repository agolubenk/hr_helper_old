# 🔧 Настройка расширения для продакшена

## 📋 Быстрая инструкция

### 1. Обновить manifest.json

Добавьте ваш продакшен домен в `host_permissions`:

```json
"host_permissions": [
  "https://www.linkedin.com/*",
  "https://calendar.google.com/*",
  "https://meet.google.com/*",
  "http://localhost:8000/*",
  "http://127.0.0.1:8000/*",
  "https://YOUR-PRODUCTION-DOMAIN.com/*"  // ← ЗАМЕНИТЕ НА ВАШ ДОМЕН
]
```

### 2. Настроить CORS на сервере

В `config/settings_production.py`:

```python
# После установки расширения получите Extension ID из chrome://extensions/
EXTENSION_ID = "your-extension-id-here"  # Замените на реальный ID

CORS_ALLOWED_ORIGINS = [
    f"chrome-extension://{EXTENSION_ID}",
    # Или разрешить все расширения (менее безопасно):
    # "chrome-extension://*",
]

CORS_ALLOW_CREDENTIALS = True
```

### 3. Установить расширение

1. Откройте `chrome://extensions/`
2. Включите "Developer mode"
3. Нажмите "Load unpacked"
4. Выберите папку `chrome-extension/hrhelper-linkedin-huntflow/`
5. Скопируйте Extension ID

### 4. Настроить расширение

1. Откройте настройки расширения (правый клик → Options)
2. Укажите Base URL: `https://YOUR-PRODUCTION-DOMAIN.com`
3. Получите API токен: `https://YOUR-PRODUCTION-DOMAIN.com/api/v1/accounts/users/token/`
4. Вставьте токен в настройки
5. Сохраните

### 5. Проверить работу

1. Откройте любой профиль LinkedIn
2. Должна появиться кнопка "Huntflow"
3. Проверьте сохранение связи

---

## 🔍 Получение Extension ID

После установки расширения:

1. Откройте `chrome://extensions/`
2. Найдите "HRHelper LinkedIn → Huntflow"
3. Скопируйте ID (например: `abcdefghijklmnopqrstuvwxyz123456`)
4. Используйте его в настройках CORS

---

## 📝 Шаблон для замены

Замените в файлах расширения:

- `YOUR-PRODUCTION-DOMAIN.com` → ваш реальный домен
- `your-extension-id-here` → реальный Extension ID

**Файлы для обновления:**
- `manifest.json` - добавить домен в host_permissions
- `config/settings_production.py` - добавить Extension ID в CORS

---

Подробная инструкция: см. `SETUP_GUIDE.md`
