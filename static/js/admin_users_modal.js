document.addEventListener("DOMContentLoaded", () => {
  const modalEl = document.getElementById("userEditModal");
  if (!modalEl || !window.bootstrap) {
    return;
  }

  const modal = new bootstrap.Modal(modalEl);
  const form = document.getElementById("userEditForm");
  const idInput = document.getElementById("edit-user-id");
  const usernameInput = document.getElementById("edit-username");
  const passwordInput = document.getElementById("edit-password");
  const nameInput = document.getElementById("edit-name");
  const emailInput = document.getElementById("edit-email");
  const roleInput = document.getElementById("edit-role");
  const title = document.getElementById("userEditModalTitle");

  if (!form || !idInput || !usernameInput || !passwordInput || !nameInput || !emailInput || !roleInput || !title) {
    return;
  }

  const resetForm = () => {
    idInput.value = "";
    usernameInput.value = "";
    passwordInput.value = "";
    nameInput.value = "";
    emailInput.value = "";
    roleInput.value = "user";
    title.textContent = "ユーザー編集";
  };

  const focusInitialField = () => {
    const initialTarget = modalEl.querySelector("[data-modal-initial-focus]");
    if (!initialTarget) {
      return;
    }
    const applyFocus = () => {
      if (!modalEl.classList.contains("show")) {
        return;
      }
      if (initialTarget.matches(":disabled")) {
        return;
      }
      initialTarget.focus({ preventScroll: true });
    };
    window.setTimeout(applyFocus, 0);
    window.setTimeout(applyFocus, 120);
  };

  document.querySelectorAll("[data-user-edit]").forEach((button) => {
    button.addEventListener("click", () => {
      const { userId, userUsername, userName, userEmail, userRole } = button.dataset;

      idInput.value = userId || "";
      usernameInput.value = userUsername || "";
      passwordInput.value = "";
      nameInput.value = userName || "";
      emailInput.value = userEmail || "";
      roleInput.value = userRole || "user";
      title.textContent = `ユーザー編集: ${userUsername || ""}`;
      modal.show();
    });
  });

  modalEl.addEventListener("hidden.bs.modal", resetForm);
  modalEl.addEventListener("shown.bs.modal", focusInitialField);
});
