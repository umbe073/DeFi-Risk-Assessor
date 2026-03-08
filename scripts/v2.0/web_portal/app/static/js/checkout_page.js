(function () {
  const root = document.getElementById("checkout-root");
  if (!root) return;

  const plans = JSON.parse(root.dataset.plans || "[]");
  const planById = new Map(plans.map((plan) => [String(plan.id), plan]));
  const defaultPlan = String(root.dataset.defaultPlan || "");
  const nowpaymentsEnabled = String(root.dataset.nowpaymentsEnabled || "false") === "true";
  const csrfToken = String(root.dataset.csrfToken || "");

  const selectorList = document.getElementById("plan-selector-list");
  const selectedPlanBox = document.getElementById("selected-plan-box");
  const form = document.getElementById("checkout-form");
  const planIdInput = document.getElementById("plan-id");
  const amountValueInput = document.getElementById("amount-value");
  const amountCurrencyInput = document.getElementById("amount-currency");
  const payCurrencyInput = document.getElementById("pay-currency");
  const enterpriseWrap = document.getElementById("enterprise-code-wrap");
  const enterpriseCodeInput = document.getElementById("enterprise-code");
  const submitBtn = document.getElementById("checkout-submit");
  const output = document.getElementById("checkout-result");

  function formatAmount(plan) {
    const amount = Number(plan.amount_value || 0);
    return amount > 0 ? amount.toFixed(2) : "0.00";
  }

  function appendQuery(url, key, value) {
    const raw = String(url || "").trim();
    if (!raw || !key) return raw;
    const separator = raw.includes("?") ? "&" : "?";
    return raw + separator + encodeURIComponent(String(key)) + "=" + encodeURIComponent(String(value));
  }

  function selectPlan(planId) {
    const selected = planById.get(planId);
    if (!selected) return;

    planIdInput.value = planId;
    amountValueInput.value = formatAmount(selected);
    amountCurrencyInput.value = String(selected.price_currency || "EUR").toUpperCase();

    const requiresEnterpriseCode = !!selected.requires_enterprise_code;
    enterpriseWrap.classList.toggle("hidden", !requiresEnterpriseCode);
    if (!requiresEnterpriseCode) {
      enterpriseCodeInput.value = "";
    }

    const needsProvider = !!selected.requires_payment;
    const providerDisabled = needsProvider && !nowpaymentsEnabled;
    submitBtn.disabled = providerDisabled;
    submitBtn.textContent = selected.requires_payment
      ? "Continue To Secure Checkout"
      : "Activate Free Trial";

    selectorList.querySelectorAll(".plan-chip").forEach((button) => {
      const active = button.getAttribute("data-plan-id") === planId;
      button.classList.toggle("is-active", active);
    });

    if (selectedPlanBox) {
      selectedPlanBox.innerHTML = [
        `<h3>${selected.name}</h3>`,
        `<p>${selected.tagline || ""}</p>`,
        `<p><strong>Daily scans:</strong> ${selected.scans_per_day > 0 ? selected.scans_per_day : "Custom"}</p>`,
        `<p><strong>Duration:</strong> ${selected.duration_days} day(s)</p>`,
        `<p><strong>Fee:</strong> ${selected.requires_payment ? `${formatAmount(selected)} ${selected.price_currency}` : "Free"}</p>`,
        `<p class="inline-note">${selected.fee_note || ""}</p>`,
      ].join("");
    }
  }

  selectorList.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) return;
    const button = target.closest(".plan-chip");
    if (!button) return;
    const planId = String(button.getAttribute("data-plan-id") || "");
    if (!planId) return;
    selectPlan(planId);
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const selected = planById.get(planIdInput.value);
    if (!selected) return;

    const payload = {
      plan_id: planIdInput.value,
      pay_currency: String(payCurrencyInput.value || "").trim().toLowerCase(),
    };
    if (selected.requires_enterprise_code) {
      payload.enterprise_code = String(enterpriseCodeInput.value || "").trim().toUpperCase();
    }

    submitBtn.disabled = true;
    const oldText = submitBtn.textContent;
    submitBtn.textContent = "Processing...";

    try {
      const response = await fetch("/api/v1/billing/checkout-session", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRF-Token": csrfToken,
        },
        body: JSON.stringify(payload),
      });
      const raw = await response.text();
      const contentType = String(response.headers.get("content-type") || "").toLowerCase();
      let data = null;
      if (contentType.includes("application/json")) {
        try {
          data = JSON.parse(raw || "{}");
        } catch (jsonError) {
          data = { error: "invalid_json_response", message: String(jsonError), raw: raw.slice(0, 800) };
        }
      } else {
        try {
          data = JSON.parse(raw || "{}");
        } catch (_ignore) {
          data = { error: "non_json_response", message: raw.slice(0, 800) || "(empty body)" };
        }
      }

      output.textContent = JSON.stringify(
        { status: response.status, ok: response.ok, content_type: contentType, body: data },
        null,
        2
      );

      if (response.ok) {
        const invoiceUrl = data && data.checkout ? data.checkout.invoice_url : "";
        const waitingUrl = data && data.urls ? String(data.urls.waiting || "") : "";
        if (invoiceUrl) {
          const popup = window.open(invoiceUrl, "hs_nowpayments_checkout", "noopener,width=1240,height=880");
          let popupOpened = false;
          if (!popup) {
            output.textContent = JSON.stringify(
              {
                warning: "popup_blocked",
                message:
                  "The checkout tab was blocked by your browser. Allow pop-ups for this site and open the invoice URL manually.",
                invoice_url: invoiceUrl,
              },
              null,
              2
            );
          } else {
            popupOpened = true;
            try {
              popup.focus();
            } catch (_focusError) {
              // Browser focus behavior varies; failing to focus should not block checkout.
            }
          }
          if (waitingUrl) {
            const waitingTarget = popupOpened ? appendQuery(waitingUrl, "from_popup", "1") : waitingUrl;
            window.location.href = waitingTarget;
            return;
          }
          window.location.href = invoiceUrl;
          return;
        }
        if (String(data.status || "") === "trial_activated") {
          submitBtn.textContent = "Trial Activated";
        }
      }
    } catch (error) {
      output.textContent = JSON.stringify({ error: String(error) }, null, 2);
    } finally {
      const selectedAgain = planById.get(planIdInput.value);
      const requiresProvider = selectedAgain && selectedAgain.requires_payment;
      submitBtn.disabled = !!(requiresProvider && !nowpaymentsEnabled);
      if (submitBtn.textContent !== "Trial Activated") {
        submitBtn.textContent = oldText || "Continue To Secure Checkout";
      }
    }
  });

  selectPlan(planById.has(defaultPlan) ? defaultPlan : (plans[0] ? String(plans[0].id) : ""));
})();
