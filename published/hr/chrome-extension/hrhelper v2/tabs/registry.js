/**
 * Реестр контекстов попапа: маппинг контекста вкладки на ID блока и имя вкладки.
 * Strategy: один блок может обслуживать несколько контекстов (LinkedIn, Resume, Huntflow → context-linkedin).
 */
(function () {
  const g = typeof window !== "undefined" ? window : globalThis;
  g.__HRH__ = g.__HRH__ || {};
  g.__HRH__.tabs = g.__HRH__.tabs || {};

  const CONTEXT = {
    LINKEDIN: "linkedin",
    CALENDAR: "calendar",
    MEET: "meet",
    RESUME: "resume",
    HUNTFLOW: "huntflow",
    OTHER: "other"
  };

  /** Контекст → ID DOM-блока (.context-block) */
  const CONTEXT_TO_BLOCK = {
    [CONTEXT.LINKEDIN]: "context-linkedin",
    [CONTEXT.RESUME]: "context-linkedin",
    [CONTEXT.HUNTFLOW]: "context-linkedin",
    [CONTEXT.MEET]: "context-meet",
    [CONTEXT.CALENDAR]: "context-calendar",
    [CONTEXT.OTHER]: "context-other"
  };

  function getBlockId(ctx) {
    return CONTEXT_TO_BLOCK[ctx] || "context-other";
  }

  function getTabName(ctx) {
    const names = {
      [CONTEXT.LINKEDIN]: "linkedin",
      [CONTEXT.RESUME]: "resume",
      [CONTEXT.HUNTFLOW]: "huntflow",
      [CONTEXT.MEET]: "meet",
      [CONTEXT.CALENDAR]: "calendar",
      [CONTEXT.OTHER]: "other"
    };
    return names[ctx] || "other";
  }

  /** Нужно ли показывать блок LinkedIn (форма Huntflow, вакансии, статусы) */
  function isLinkedInBlock(ctx) {
    return ctx === CONTEXT.LINKEDIN || ctx === CONTEXT.RESUME || ctx === CONTEXT.HUNTFLOW;
  }

  g.__HRH__.tabs.CONTEXT = CONTEXT;
  g.__HRH__.tabs.getBlockId = getBlockId;
  g.__HRH__.tabs.getTabName = getTabName;
  g.__HRH__.tabs.isLinkedInBlock = isLinkedInBlock;
})();
