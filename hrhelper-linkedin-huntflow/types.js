/**
 * JSDoc типы для множественных вакансий HR Helper
 * @fileoverview
 */

/**
 * @typedef {Object} VacancyItem
 * @property {number} vacancy_id
 * @property {string} vacancy_name
 * @property {number} status_id
 * @property {string} status_name
 * @property {'new'|'in_progress'|'rejected'|'hired'|'archived'} status_type
 * @property {number|null} rejection_reason_id
 * @property {string|null} rejection_reason_name
 * @property {string} last_change_at - ISO datetime
 * @property {string|null} last_comment_at - ISO datetime
 * @property {boolean} is_hired
 * @property {boolean} is_archived
 * @property {string} appurl
 */

/**
 * @typedef {Object} StatusMultiResponse
 * @property {boolean} success
 * @property {number} applicant_id
 * @property {string} applicant_name
 * @property {number|null} default_vacancy_id
 * @property {VacancyItem[]} items
 */

/**
 * @typedef {Object} AvailableVacanciesResponse
 * @property {boolean} success
 * @property {Array<{vacancy_id: number, vacancy_name: string, state: string}>} items
 */
