# 🔌 HRHelper LinkedIn → Huntflow Chrome Extension

Chrome расширение для интеграции LinkedIn с Huntflow через HRHelper.

## 🚀 Быстрый старт

1. **Установите расширение** из Chrome Web Store по ссылке:  
   [Chrome Web Store — HR Helper](https://chromewebstore.google.com/detail/hr-helper/dccabghccldhpkichoejklfmbcclmepl)  
   (подробнее: [INSTALL.md](./INSTALL.md))
2. **Настройте Base URL** и **API Token** в настройках расширения (токен: https://hr.sftntx.com/api/v1/accounts/users/token/)
3. **Откройте LinkedIn** (или hh.ru / rabota.by / Meet) — кнопки расширения появятся на странице

## 📚 Документация

- **[CHANGELOG.md](./CHANGELOG.md)** — история версий и описание функциональности
- **[INSTALL.md](./INSTALL.md)** — установка из Chrome Web Store (по прямой ссылке) или из архива, получение токена, настройка
- **[USER_GUIDE.md](./USER_GUIDE.md)** — работа с расширением: где что делать, что вставлять, что получать (LinkedIn, popup, Meet, статусы)
- **[SETUP_GUIDE.md](./SETUP_GUIDE.md)** — полное руководство по настройке
- **[PRODUCTION_SETUP.md](./PRODUCTION_SETUP.md)** — быстрая инструкция для продакшена
- **[PUBLISHING.md](./PUBLISHING.md)** — публикация в Chrome Web Store (упаковка, Store Listing, Unlisted)
- **[privacy.md](./privacy.md)** — политика конфиденциальности (нужна ссылка для Web Store)

## ⚙️ Настройка для продакшена

### Автоматическое обновление manifest.json

Используйте скрипт для добавления продакшен домена:

```bash
./update_manifest.sh https://your-production-domain.com
```

### Ручное обновление

Откройте `manifest.json` и добавьте ваш домен в `host_permissions`:

```json
"host_permissions": [
  "https://www.linkedin.com/*",
  "https://your-production-domain.com/*"  // ← Добавьте ваш домен
]
```

## 🔑 Получение API токена

1. Откройте HRHelper в браузере
2. Перейдите: `https://your-domain.com/api/v1/accounts/users/token/`
3. Скопируйте токен из ответа
4. Вставьте в настройки расширения

## ✅ Функции (v1.1.6)

- ✅ Кнопка "Huntflow" на профилях LinkedIn и в переписке
- ✅ Сохранение связи LinkedIn / rabota.by / hh.ru → Huntflow
- ✅ Множественные вакансии: карточки, отказы, «В новый цикл», «+ Взять на другую вакансию»
- ✅ Быстрое открытие кандидатов в Huntflow, копирование ссылки
- ✅ Изменение статуса и причины отказа
- ✅ Google Meet: Scorecard, Контакт, копирование текста уровня

## 🐛 Устранение проблем

См. раздел [Устранение проблем](./SETUP_GUIDE.md#устранение-проблем) в SETUP_GUIDE.md

## 📝 Лицензия

Внутренний проект HRHelper
