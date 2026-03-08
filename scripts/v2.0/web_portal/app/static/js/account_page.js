(() => {
  function initDeleteUserForms() {
    const forms = Array.from(document.querySelectorAll("form.delete-user-form"));
    if (!forms.length) {
      return;
    }

    forms.forEach((form) => {
      form.addEventListener("submit", (event) => {
        const hasActorTotp = String(form.dataset.actorTotpEnabled || "0") === "1";
        if (!hasActorTotp) {
          event.preventDefault();
          window.alert("You must enable 2FA on your account before deleting users.");
          return;
        }

        const targetUid = String(form.dataset.targetUid || "").trim();
        const targetEmail = String(form.dataset.targetEmail || "").trim();
        const label = targetUid ? `${targetUid}${targetEmail ? ` (${targetEmail})` : ""}` : targetEmail || "this user";
        const code = window.prompt(`Enter your 6-digit 2FA code to delete ${label}:`, "");

        if (code === null) {
          event.preventDefault();
          return;
        }

        const normalizedCode = String(code || "").trim();
        if (!/^[0-9]{6}$/.test(normalizedCode)) {
          event.preventDefault();
          window.alert("Invalid 2FA code format. Use exactly 6 digits.");
          return;
        }

        if (!window.confirm(`Delete ${label} permanently? This cannot be undone.`)) {
          event.preventDefault();
          return;
        }

        const codeField = form.querySelector("input[name='delete_2fa_code']");
        if (!codeField) {
          event.preventDefault();
          window.alert("Delete form is missing a 2FA field.");
          return;
        }
        codeField.value = normalizedCode;
      });
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initDeleteUserForms);
    return;
  }
  initDeleteUserForms();
})();
