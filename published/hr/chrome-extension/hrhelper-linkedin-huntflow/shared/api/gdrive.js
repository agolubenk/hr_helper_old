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
