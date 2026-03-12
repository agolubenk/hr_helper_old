/**
 * Вкладка Meet: обновление UI блока Google Meet по данным от content script (getPageContext).
 */
(function () {
  const g = typeof window !== "undefined" ? window : globalThis;
  g.__HRH__ = g.__HRH__ || {};
  g.__HRH__.tabs = g.__HRH__.tabs || {};

  /**
   * Обновляет DOM блока Meet по ответу getPageContext.
   * @param {Document} doc - document
   * @param {Object} response - ответ content script { level, vacancyName, scorecardLink, communicationLink, communicationLabel, huntflowUrl, ... }
   * @param {Object} helpers - { escapeHtml, getMeetContactIcon, updateHeaderActions }
   */
  function updateMeetUI(doc, response, helpers) {
    const escapeHtml = helpers.escapeHtml || ((s) => { const d = doc.createElement("div"); d.textContent = s; return d.innerHTML; });
    const getMeetContactIcon = helpers.getMeetContactIcon || (() => "");
    const updateHeaderActions = helpers.updateHeaderActions || (() => {});

    const meetHint = doc.getElementById("ctx-meet-hint");
    const meetOpenAll = doc.getElementById("ctx-meet-open-all");
    const meetCopy = doc.getElementById("ctx-meet-copy");
    const meetSettingsLink = doc.getElementById("ctx-meet-settings-link");
    const meetHuntflow = doc.getElementById("ctx-meet-huntflow");
    const meetScorecard = doc.getElementById("ctx-meet-scorecard");
    const meetContact = doc.getElementById("ctx-meet-contact");

    const hasCopyData = !!(response.level && (response.vacancyName || response.level));

    if (meetHint) meetHint.style.display = hasCopyData ? "none" : "block";
    if (meetOpenAll) {
      if (hasCopyData) {
        meetOpenAll.style.display = "inline-flex";
        meetOpenAll.disabled = false;
      } else {
        meetOpenAll.style.display = "none";
        meetOpenAll.disabled = true;
      }
    }
    if (meetCopy) {
      if (hasCopyData) {
        meetCopy.style.display = "inline-flex";
        meetCopy.disabled = false;
        const v = (response.vacancyName || "").trim();
        const l = (response.level || "").trim();
        meetCopy.textContent = (l && v) ? `${l}, ${v}` : (l || v || "Вакансия и грейд");
        meetCopy.title = (l && v) ? `${l}, ${v}` : (l || v || "Вакансия и грейд");
      } else {
        meetCopy.style.display = "none";
        meetCopy.disabled = true;
      }
    }
    if (meetSettingsLink) {
      meetSettingsLink.href = "https://hr.sftntx.com/extension/";
      meetSettingsLink.style.display = hasCopyData ? "none" : "inline-flex";
    }
    if (meetHuntflow) {
      if (response.huntflowUrl) {
        updateHeaderActions(true, response.huntflowUrl, false, false);
        meetHuntflow.style.display = "none";
        meetHuntflow.href = response.huntflowUrl;
        meetHuntflow.removeAttribute("aria-disabled");
      } else {
        updateHeaderActions(false);
        meetHuntflow.style.display = "none";
        meetHuntflow.href = "#";
        meetHuntflow.setAttribute("aria-disabled", "true");
      }
    }
    if (meetScorecard) {
      if (response.scorecardLink) {
        meetScorecard.href = response.scorecardLink;
        meetScorecard.setAttribute("aria-disabled", "false");
      }
    }
    if (meetContact) {
      if (response.communicationLink) {
        meetContact.href = response.communicationLink;
        meetContact.setAttribute("aria-disabled", "false");
      }
      const contactLabel = response.communicationLabel || "Контакт";
      const contactIcon = getMeetContactIcon(contactLabel, response.communicationLink || "");
      meetContact.innerHTML = contactIcon + "<span class=\"ctx-meet-contact-label\">" + escapeHtml(contactLabel) + "</span>";
      meetContact.title = contactLabel;
      meetContact.setAttribute("aria-label", contactLabel);
    }
  }

  /** Показывает состояние «нет данных»: подсказка и ссылка на настройки. */
  function setMeetNoDataUI(doc) {
    const hint = doc.getElementById("ctx-meet-hint");
    const copyBtn = doc.getElementById("ctx-meet-copy");
    const settingsLink = doc.getElementById("ctx-meet-settings-link");
    if (hint) hint.style.display = "block";
    if (copyBtn) {
      copyBtn.style.display = "none";
      copyBtn.disabled = true;
    }
    if (settingsLink) {
      settingsLink.href = "https://hr.sftntx.com/extension/";
      settingsLink.style.display = "inline-flex";
    }
  }

  g.__HRH__.tabs.meet = {
    updateMeetUI,
    setMeetNoDataUI
  };
})();
