# ⚡ Быстрый старт

## 🎯 За 5 минут

### 1. Обновите manifest.json

```bash
cd chrome-extension/hrhelper-linkedin-huntflow
./update_manifest.sh https://your-production-domain.com
```

Или вручную добавьте домен в `manifest.json`:
```json
"host_permissions": [
  "https://your-production-domain.com/*"
]
```

### 2. Установите расширение

1. Откройте `chrome://extensions/`
2. Включите "Developer mode"
3. Нажмите "Load unpacked"
4. Выберите папку расширения
5. **Скопируйте Extension ID**

### 3. Настройте CORS на сервере

В `.env` файле:
```bash
CHROME_EXTENSION_ID=your-extension-id-here
```

В `config/settings_production.py` уже настроено автоматическое добавление Extension ID в CORS.

### 4. Настройте расширение

1. Откройте настройки расширения (правый клик → Options)
2. Base URL: `https://your-production-domain.com`
3. Получите токен: `https://your-production-domain.com/api/v1/accounts/users/token/`
4. Вставьте токен в настройки
5. Сохраните

### 5. Проверьте

1. Откройте LinkedIn профиль
2. Должна появиться кнопка "Huntflow"
3. Готово! ✅

---

**Подробная инструкция:** см. [SETUP_GUIDE.md](./SETUP_GUIDE.md)
