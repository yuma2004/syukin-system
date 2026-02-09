document.addEventListener("DOMContentLoaded", () => {
  const modalEl = document.getElementById("shiftEditModal");
  if (!modalEl) {
    return;
  }

  const modal = new bootstrap.Modal(modalEl);
  const form = document.getElementById("shiftEditForm");
  const clockInInput = document.getElementById("shiftEditClockIn");
  const clockOutInput = document.getElementById("shiftEditClockOut");
  const userLabel = document.getElementById("shiftEditUser");
  const summaryLabel = document.getElementById("shiftEditSummary");
  const workedLabel = document.getElementById("shiftEditWorked");
  const breaksLabel = document.getElementById("shiftEditBreaks");
  const breakCountLabel = document.getElementById("shiftEditBreakCount");
  const ipLabel = document.getElementById("shiftEditIp");
  const errorBox = document.getElementById("shiftEditError");
  const statusBox = document.getElementById("shiftEditStatus");
  const loadingBox = modalEl.querySelector("[data-loading]");
  const clockInMeta = document.getElementById("shiftEditClockInMeta");
  const clockOutMeta = document.getElementById("shiftEditClockOutMeta");

  if (ipLabel) {
    ipLabel.style.whiteSpace = "pre-line";
  }

  const toggleLoading = (state) => {
    if (!loadingBox) {
      return;
    }
    loadingBox.classList.toggle("d-none", !state);
    form.setAttribute("aria-busy", state ? "true" : "false");
  };

  const announceStatus = (message) => {
    if (!statusBox) {
      return;
    }
    statusBox.textContent = message || "";
  };

  const pad2 = (num) => String(num).padStart(2, "0");

  const formatForInput = (date) => {
    if (!(date instanceof Date) || Number.isNaN(date.getTime())) {
      return "";
    }
    return `${date.getFullYear()}-${pad2(date.getMonth() + 1)}-${pad2(date.getDate())}T${pad2(date.getHours())}:${pad2(date.getMinutes())}`;
  };

  const parseInputValue = (value) => {
    if (!value) {
      return null;
    }
    const parsed = new Date(value);
    return Number.isNaN(parsed.getTime()) ? null : parsed;
  };

  const setInputDate = (input, dateObj) => {
    if (!input || !(dateObj instanceof Date) || Number.isNaN(dateObj.getTime())) {
      return;
    }
    input.value = formatForInput(dateObj);
    input.dispatchEvent(new Event("change", { bubbles: true }));
    input.dispatchEvent(new Event("input", { bubbles: true }));
  };

  const adjustInputMinutes = (input, minutes) => {
    if (!input) {
      return;
    }
    const base = parseInputValue(input.value) || new Date();
    base.setMinutes(base.getMinutes() + minutes);
    setInputDate(input, base);
  };

  const roundInputMinutes = (input, stepMinutes) => {
    if (!input || !stepMinutes) {
      return;
    }
    const base = parseInputValue(input.value) || new Date();
    const ms = base.getTime();
    const stepMs = stepMinutes * 60 * 1000;
    const rounded = new Date(Math.round(ms / stepMs) * stepMs);
    setInputDate(input, rounded);
  };

  const buildMetaText = (local, utc) => {
    if (!local && !utc) {
      return "未設定";
    }
    if (local && utc) {
      return `${local} (UTC: ${utc})`;
    }
    return local || `UTC: ${utc}`;
  };

  const showError = (message) => {
    errorBox.textContent = message;
    errorBox.classList.toggle("d-none", !message);
    if (message) {
      announceStatus(`エラー: ${message}`);
    }
  };

  modalEl.querySelectorAll("[data-clear-target]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const target = modalEl.querySelector(btn.getAttribute("data-clear-target"));
      if (target) {
        target.value = "";
        target.dispatchEvent(new Event("change", { bubbles: true }));
        target.dispatchEvent(new Event("input", { bubbles: true }));
      }
    });
  });

  modalEl.querySelectorAll("[data-set-now]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const target = modalEl.querySelector(btn.getAttribute("data-set-now"));
      if (target) {
        setInputDate(target, new Date());
      }
    });
  });

  modalEl.querySelectorAll("[data-adjust-minutes]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const selector = btn.getAttribute("data-adjust-target");
      const target = modalEl.querySelector(selector);
      if (!target) {
        return;
      }
      const minutes = Number(btn.getAttribute("data-adjust-minutes"));
      if (Number.isNaN(minutes)) {
        return;
      }
      adjustInputMinutes(target, minutes);
    });
  });

  modalEl.querySelectorAll("[data-round-target]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const target = modalEl.querySelector(btn.getAttribute("data-round-target"));
      if (!target) {
        return;
      }
      const minutes = Number(btn.getAttribute("data-round-minutes"));
      if (!minutes || Number.isNaN(minutes)) {
        return;
      }
      roundInputMinutes(target, minutes);
    });
  });

  modalEl.querySelectorAll("[data-copy-from]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const source = modalEl.querySelector(btn.getAttribute("data-copy-from"));
      const target = modalEl.querySelector(btn.getAttribute("data-copy-target"));
      if (!source || !target) {
        return;
      }
      const parsed = parseInputValue(source.value);
      if (!parsed) {
        return;
      }
      setInputDate(target, parsed);
    });
  });

  document.querySelectorAll("[data-shift-edit]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const detailUrl = btn.getAttribute("data-detail-url");
      const actionUrl = btn.getAttribute("data-action-url");
      form.setAttribute("action", actionUrl);
      clockInInput.value = "";
      clockOutInput.value = "";
      userLabel.textContent = "読み込み中…";
      summaryLabel.textContent = "";
      workedLabel.textContent = "--:--";
      breaksLabel.textContent = "--:--";
      breakCountLabel.textContent = "";
      ipLabel.textContent = "";
      clockInMeta.textContent = "";
      clockOutMeta.textContent = "";
      showError("");
      toggleLoading(true);
      announceStatus("シフト情報を読み込み中です。");
      modal.show();

      try {
        const response = await fetch(detailUrl, { headers: { Accept: "application/json" } });
        if (!response.ok) {
          throw new Error("データの取得に失敗しました");
        }

        const data = await response.json();
        userLabel.textContent = `${data.user_name || data.user_username || ""}`;
        const summaryParts = [];
        if (data.user_username) {
          summaryParts.push(`ユーザーID: ${data.user_username}`);
        }
        if (data.user_email) {
          summaryParts.push(`メール: ${data.user_email}`);
        }
        if (data.worked_hms) {
          summaryParts.push(`実働: ${data.worked_hms}`);
        }
        summaryLabel.textContent = summaryParts.join(" ／ ");
        clockInInput.value = data.clock_in_form || "";
        clockOutInput.value = data.clock_out_form || "";
        workedLabel.textContent = data.worked_hms || "--:--";
        breaksLabel.textContent = data.break_hms || "--:--";
        breakCountLabel.textContent = data.break_count !== undefined ? `休憩回数: ${data.break_count}` : "";
        const clockInIp = data.clock_in_ip || "-";
        const clockOutIp = data.clock_out_ip || "-";
        ipLabel.textContent = `出勤: ${clockInIp}\n退勤: ${clockOutIp}`;
        clockInMeta.textContent = buildMetaText(data.clock_in_at, data.clock_in_utc);
        clockOutMeta.textContent = buildMetaText(data.clock_out_at, data.clock_out_utc);
        announceStatus("シフト情報を読み込みました。");
      } catch (err) {
        showError(err.message);
      } finally {
        toggleLoading(false);
      }
    });
  });

  modalEl.addEventListener("hidden.bs.modal", () => {
    showError("");
    announceStatus("");
    form.removeAttribute("aria-busy");
  });
});
