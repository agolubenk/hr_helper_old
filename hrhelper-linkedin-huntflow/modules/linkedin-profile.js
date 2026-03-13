/**
 * Модуль LinkedIn Profile: поиск контейнеров и кнопок на странице профиля (/in/).
 * Подключается до content.js; экспорт в window.__HRH__.linkedinProfile.
 */
(function () {
  const g = typeof window !== "undefined" ? window : globalThis;
  g.__HRH__ = g.__HRH__ || {};
  const HRH = g.__HRH__;
  const DEBUG = !!(HRH.DEBUG_CONTENT);
  const log = (...args) => DEBUG && console.log("[HRHelper]", ...args);

  const COVER_SELECTORS = [
    ".pv-top-card__cover-photo-container",
    ".profile-background-image",
    "[data-view-name='profile-top-card']",
    ".scaffold-layout__main section:first-child"
  ];

  function findAllMoreButtons() {
    const ariaNeedles = ["more", "more actions", "ещё", "еще", "дополнительно"];
    const buttons = Array.from(document.querySelectorAll("button[aria-label], [role='button'][aria-label]"));
    const res = [];
    for (const el of buttons) {
      const aria = (el.getAttribute("aria-label") || "").trim().toLowerCase();
      const txt = (el.textContent || "").trim().toLowerCase();
      if ((aria && ariaNeedles.some((n) => aria.includes(n))) || ariaNeedles.some((n) => txt.includes(n))) {
        res.push(el);
      }
    }
    return Array.from(new Set(res));
  }

  function looksLikeProfileActionArea(moreBtn) {
    const inTop = !!moreBtn.closest('[data-view-name="profile-top-card"]') || !!moreBtn.closest(".pv-top-card") || !!moreBtn.closest(".pv-top-card-v2-ctas") || !!moreBtn.closest(".pv-top-card__actions");
    const inSticky = !!moreBtn.closest(".scaffold-layout__sticky");
    if (inTop || inSticky) return true;
    const root = moreBtn.closest("header") || moreBtn.closest("section");
    if (!root) return false;
    const needles = ["connect", "message", "follow", "соедин", "сообщ"];
    const nearby = Array.from(root.querySelectorAll("button[aria-label]")).slice(0, 40);
    for (const b of nearby) {
      const aria = (b.getAttribute("aria-label") || "").toLowerCase();
      if (needles.some((n) => aria.includes(n))) return true;
    }
    return false;
  }

  function findActionContainer() {
    const candidates = [
      document.querySelector(".pv-top-card-v2-ctas"),
      document.querySelector(".pv-top-card__actions"),
      document.querySelector('[data-view-name="profile-top-card"]'),
      document.querySelector("main")
    ].filter(Boolean);
    for (const el of candidates) {
      const btnBar = el.querySelector('div[role="group"]') || el.querySelector(".artdeco-button__text")?.closest("div") || el;
      if (btnBar) return btnBar;
    }
    return null;
  }

  function findActivitySection() {
    const activityHeadings = ["Activity", "Действия", "Activité", "Actividad", "Aktivität", "Attività", "Atividade"];
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null);
    let textNode;
    while ((textNode = walker.nextNode())) {
      const text = (textNode.textContent || "").trim();
      if (!text) continue;
      for (const heading of activityHeadings) {
        if (text !== heading && !text.startsWith(heading + "\n") && !text.startsWith(heading + " ")) continue;
        let el = textNode.parentElement;
        for (let i = 0; i < 15 && el; i++) {
          const tag = (el.tagName || "").toLowerCase();
          const role = (el.getAttribute?.("role") || "").toLowerCase();
          const cn = el.className || "";
          const isSectionLike = tag === "section" || role === "region" || /scaffold-layout|pv-profile-section|pvs-list__outer-container|artdeco-card/.test(cn);
          if (isSectionLike && el.offsetParent != null) return el;
          el = el.parentElement;
        }
        return textNode.parentElement || null;
      }
    }
    return null;
  }

  function findCoverContainer() {
    for (const sel of COVER_SELECTORS) {
      const el = document.querySelector(sel);
      if (el) {
        log(" Floating widget: found cover container:", sel);
        return el;
      }
    }
    const topCard = document.querySelector(".pv-top-card") || document.querySelector("[data-view-name='profile-top-card']");
    if (topCard) {
      log(" Floating widget: using top-card as container");
      return topCard;
    }
    return null;
  }

  HRH.linkedinProfile = {
    COVER_SELECTORS,
    findAllMoreButtons,
    looksLikeProfileActionArea,
    findActionContainer,
    findActivitySection,
    findCoverContainer
  };
})();
