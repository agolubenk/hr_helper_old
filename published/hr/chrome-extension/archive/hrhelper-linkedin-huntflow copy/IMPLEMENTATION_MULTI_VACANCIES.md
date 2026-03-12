# Реализация: Множественные вакансии в HR Helper

**Цель:** Добавить поддержку отображения и управления кандидатом на нескольких вакансиях одновременно.

**Принцип:** Обратная совместимость на каждом этапе.

---

## ЭТАП 1: Backend — Django API

### Шаг 1.1: Эндпоинт `/status-multi/`

- [x] Добавить action `status_multi` в LinkedInApplicantsViewSet
- [x] Возвращать все связки applicant–vacancy из `applicant_data['links']`
- [x] Формат ответа: `{ success, applicant_id, applicant_name, default_vacancy_id, items: VacancyItem[] }`
- [x] URL: `/api/v1/huntflow/linkedin-applicants/status-multi/`

### Шаг 1.2: Эндпоинт `/available-vacancies/`

- [x] Action `available_vacancies` в LinkedInApplicantsViewSet
- [x] Исключать вакансии, на которых кандидат уже есть
- [x] URL: `/api/v1/huntflow/linkedin-applicants/available-vacancies/?linkedin_url=...`

### Шаг 1.3: Обновить `/update-status/` для `vacancy_id`

- [x] Читать `vacancy_id` из `request.data`
- [x] Если не указан — использовать дефолтную (как сейчас)
- [x] Передавать в `api.update_applicant_status(..., vacancy_id=...)`

### Шаг 1.4: Эндпоинт `/add-to-vacancy/`

- [x] POST: `linkedin_url`, `vacancy_id`
- [x] HuntflowService.add_applicant_to_vacancy()
- [x] URL: `/api/v1/huntflow/linkedin-applicants/add-to-vacancy/`

---

## ЭТАП 2: Extension — Типы и утилиты

### Шаг 2.1: types.js

- [x] Создать файл с JSDoc типами VacancyItem, StatusMultiResponse, AvailableVacanciesResponse

### Шаг 2.2: vacancy-utils.js

- [x] `getDefaultVacancyItem(items, defaultVacancyId)`
- [x] `convertMultiToLegacyFormat(multiData)` — для обратной совместимости
- [x] `categorizeVacancies(items)` — active, rejected, hired

---

## ЭТАП 3: Popup.js — Множественные вакансии

### Шаг 3.1: Расширить linkedinState

- [x] Добавить `vacancies`, `defaultVacancyId`, `selectedVacancyId`

### Шаг 3.2: fetchStatusMulti()

- [x] Вызов `/status-multi/?linkedin_url=...` или `?huntflow_url=...`
- [x] Преобразование в linkedinState

### Шаг 3.3: showContextForTab — использовать fetchStatusMulti

- [x] Заменить fetchStatus на fetchStatusMulti для LinkedIn
- [x] Для RESUME — fetchStatusMulti(null, huntflowUrl)

### Шаг 3.4: renderLinkedInUI — проверка hasMultipleVacancies

- [x] Если `vacancies.length > 1` → `renderMultiVacancyUI()`
- [x] Иначе — старый UI

### Шаг 3.5: renderMultiVacancyUI()

- [x] Категории: active, rejected, hired
- [x] Бейдж «Сотрудник» при hired (блокировка действий)
- [x] Карточки вакансий: createVacancyCard()
- [x] Кнопки: «В новый цикл», «Изменить статус», «+ Взять на другую вакансию»

### Шаг 3.6: Функции действий

- [x] `restartVacancyCycle(vacancy)` — перевод rejected в new
- [x] `showStatusChangeModal(vacancy)` — смена статуса активной
- [x] `showAddToVacancyModal()` — выбор вакансии и добавление
- [x] `addToVacancy(vacancyId)`
- [x] `refreshLinkedInState()`
- [x] `getNewStatusId()` — ID статуса «New»

### Шаг 3.7: applyLinkedInStatus — поддержка vacancy_id

- [x] Добавить `vacancy_id` в body при `selectedVacancyId`

---

## ЭТАП 4: Popup.html — Стили

- [x] Стили для `.ctx-employee-badge`
- [x] Стили для `.ctx-vacancy-card`
- [x] Контейнер `#ctx-linkedin-vacancies-list`

---

## ЭТАП 5: Manifest и подключение скриптов

- [x] Подключить vacancy-utils.js в popup.html (перед popup.js)
- [x] types.js — только JSDoc, не загружается

---

## ЭТАП 6: Content.js (опционально)

- [ ] Пока без изменений — виджет показывает дефолтную вакансию
- [ ] Позже: индикатор «+N» при нескольких вакансиях

---

## Статус выполнения

| Этап | Статус |
|------|--------|
| 1. Backend | ✅ Готово |
| 2. types.js, vacancy-utils.js | ✅ Готово |
| 3. Popup.js | ✅ Готово |
| 4. Popup.html | ✅ Готово |
| 5. Manifest | ✅ Готово |
| 6. Content.js | ⏸️ Отложено |

---

## Примечания по проекту

- **Модель:** LinkedInHuntflowLink (не ApplicantLink)
- **API параметры:** `linkedin_url`, `huntflow_url`, `status_id`, `rejection_reason_id`
- **HuntflowService:** уже есть `get_vacancies`, `get_applicant`, `update_applicant_status`
- **Добавление на вакансию:** POST `/accounts/{id}/applicants/{id}/vacancy` с `{vacancy, status}`
