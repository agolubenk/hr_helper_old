/**
 * Утилиты для работы с множественными вакансиями
 * @fileoverview
 */

/**
 * Получить дефолтный VacancyItem из массива.
 * @param {Array} items - массив VacancyItem
 * @param {number|null} defaultVacancyId
 * @returns {Object|null}
 */
function getDefaultVacancyItem(items, defaultVacancyId) {
  if (!items || items.length === 0) return null;

  if (defaultVacancyId) {
    const found = items.find(function (i) { return i.vacancy_id === defaultVacancyId; });
    if (found) return found;
  }

  var active = items.filter(function (i) {
    return !i.is_hired && !i.is_archived && i.status_type !== 'rejected';
  });
  return active[0] || items[0];
}

/**
 * Преобразовать StatusMultiResponse в старый формат (для обратной совместимости).
 * @param {Object} multiData
 * @returns {Object}
 */
function convertMultiToLegacyFormat(multiData) {
  var defaultItem = getDefaultVacancyItem(multiData.items, multiData.default_vacancy_id);

  if (!defaultItem) {
    return {
      exists: false,
      appurl: null,
      vacancyname: null,
      statusname: null,
      statusid: null,
      rejectionreasonid: null,
      rejectionreasonname: null,
      lastcommentdatetime: null
    };
  }

  return {
    exists: true,
    appurl: defaultItem.appurl,
    vacancyname: defaultItem.vacancy_name,
    statusname: defaultItem.status_name,
    statusid: defaultItem.status_id,
    rejectionreasonid: defaultItem.rejection_reason_id,
    rejectionreasonname: defaultItem.rejection_reason_name,
    lastcommentdatetime: defaultItem.last_comment_at
  };
}

/**
 * Разделить вакансии по категориям.
 * @param {Array} items
 * @returns {{active: Array, rejected: Array, hired: Array, archived: Array}}
 */
function categorizeVacancies(items) {
  return {
    active: items.filter(function (i) {
      return !i.is_hired && !i.is_archived && i.status_type !== 'rejected';
    }),
    rejected: items.filter(function (i) {
      return i.status_type === 'rejected' && !i.is_hired && !i.is_archived;
    }),
    hired: items.filter(function (i) { return i.is_hired; }),
    archived: items.filter(function (i) { return i.is_archived; })
  };
}
