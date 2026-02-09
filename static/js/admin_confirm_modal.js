document.addEventListener("DOMContentLoaded", () => {
  const modalEl = document.getElementById("confirmActionModal");
  if (!modalEl || !window.bootstrap) {
    return;
  }

  const modal = new bootstrap.Modal(modalEl);
  const titleEl = document.getElementById("confirmActionTitle");
  const messageEl = document.getElementById("confirmActionMessage");
  const dangerEl = document.getElementById("confirmActionDanger");
  const acknowledgeInput = document.getElementById("confirmActionAcknowledge");
  const submitBtn = document.getElementById("confirmActionSubmit");

  if (!titleEl || !messageEl || !dangerEl || !acknowledgeInput || !submitBtn) {
    return;
  }

  let targetForm = null;

  const resetModal = () => {
    targetForm = null;
    titleEl.textContent = "操作を確認";
    messageEl.textContent = "この操作を実行しますか？";
    dangerEl.textContent = "";
    dangerEl.classList.add("d-none");
    acknowledgeInput.checked = false;
    submitBtn.disabled = true;
  };

  document.addEventListener("click", (event) => {
    const trigger = event.target.closest("[data-confirm-form]");
    if (!trigger) {
      return;
    }

    event.preventDefault();
    const formId = trigger.getAttribute("data-confirm-form");
    if (!formId) {
      return;
    }

    const form = document.getElementById(formId);
    if (!form) {
      return;
    }

    targetForm = form;
    titleEl.textContent = trigger.getAttribute("data-confirm-title") || "操作を確認";
    messageEl.textContent = trigger.getAttribute("data-confirm-message") || "この操作を実行しますか？";

    const dangerText = trigger.getAttribute("data-confirm-danger") || "";
    if (dangerText) {
      dangerEl.textContent = dangerText;
      dangerEl.classList.remove("d-none");
    } else {
      dangerEl.textContent = "";
      dangerEl.classList.add("d-none");
    }

    acknowledgeInput.checked = false;
    submitBtn.disabled = true;
    modal.show();
  });

  acknowledgeInput.addEventListener("change", () => {
    submitBtn.disabled = !acknowledgeInput.checked || !targetForm;
  });

  submitBtn.addEventListener("click", () => {
    if (!targetForm || !acknowledgeInput.checked) {
      return;
    }
    submitBtn.disabled = true;
    targetForm.submit();
  });

  modalEl.addEventListener("hidden.bs.modal", resetModal);
});
