(() => {
  function initTicketForm() {
    const form = document.getElementById("ticket-form");
    const output = document.getElementById("ticket-result");
    const emailInput = document.getElementById("email");
    const categoryInput = document.getElementById("category");
    const subjectInput = document.getElementById("subject");
    const messageLabel = document.getElementById("message-label");
    const messageInput = document.getElementById("message");
    const attachmentsInput = document.getElementById("attachments");
    const bugFieldsBox = document.getElementById("bug-report-fields");
    const bugSurfaceInput = document.getElementById("bug-surface");
    const bugSeverityInput = document.getElementById("bug-severity");
    const bugReproducibleInput = document.getElementById("bug-reproducible");
    const paymentFieldsBox = document.getElementById("payment-issue-fields");
    const paymentTxidInput = document.getElementById("payment-txid");
    const paymentChainInput = document.getElementById("payment-chain");
    const historyBody = document.getElementById("ticket-history-body");
    const historyWrap = document.getElementById("ticket-history-wrap");
    const historyEmpty = document.getElementById("ticket-history-empty");
    if (!form || !output) {
      return;
    }

    const isEmailLocked = !!(emailInput && emailInput.hasAttribute("readonly"));
    const lockedEmail = String(emailInput?.dataset?.lockedEmail || emailInput?.value || "").trim();
    const canTrackHistory = isEmailLocked && !!historyBody && !!historyWrap;
    const bugFieldInputs = [bugSurfaceInput, bugSeverityInput, bugReproducibleInput].filter(Boolean);
    const paymentFieldInputs = [paymentTxidInput, paymentChainInput].filter(Boolean);
    const BUG_SURFACE_LABELS = { website: "Website", app: "App" };
    const BUG_SEVERITY_LABELS = { low: "Low", medium: "Medium", high: "High", very_high: "Very High" };
    const BUG_REPRODUCIBLE_LABELS = { yes: "Yes", no: "No" };
    const PAYMENT_CHAIN_LABELS = {
      ethereum: "Ethereum",
      bsc: "BNB Smart Chain",
      tron: "Tron",
      solana: "Solana",
      bitcoin: "Bitcoin",
      polygon: "Polygon",
      arbitrum: "Arbitrum",
      optimism: "Optimism",
      avalanche: "Avalanche",
      base: "Base",
      other: "Other",
    };
    const categoryValue = () => String(categoryInput?.value || "").trim().toLowerCase();

    function isBugReportCategory() {
      return categoryValue() === "bug_report";
    }

    function isPaymentIssueCategory() {
      return categoryValue() === "payment_issue";
    }

    function normalizeLabel(value) {
      const raw = String(value || "").trim();
      if (!raw) return "";
      return raw.replaceAll("_", " ").replace(/\b\w/g, (ch) => ch.toUpperCase());
    }

    function buildTicketDetails(ticket) {
      const details = [];
      const category = String(ticket?.category || "").trim().toLowerCase().replaceAll(" ", "_");
      if (category === "bug_report") {
        const surface = String(ticket?.bug_surface || "").trim().toLowerCase();
        const severity = String(ticket?.bug_severity || "").trim().toLowerCase();
        const reproducible = String(ticket?.bug_reproducible || "").trim().toLowerCase();
        if (surface) details.push({ label: "Bug Location", value: BUG_SURFACE_LABELS[surface] || normalizeLabel(surface) });
        if (severity) details.push({ label: "Severity", value: BUG_SEVERITY_LABELS[severity] || normalizeLabel(severity) });
        if (reproducible) details.push({ label: "Reproducible", value: BUG_REPRODUCIBLE_LABELS[reproducible] || normalizeLabel(reproducible) });
      } else if (category === "payment_issue") {
        const txid = String(ticket?.payment_txid || "").trim();
        const chain = String(ticket?.payment_chain || "").trim().toLowerCase();
        if (txid) details.push({ label: "TxID", value: txid });
        if (chain) details.push({ label: "Blockchain", value: PAYMENT_CHAIN_LABELS[chain] || normalizeLabel(chain) });
      }
      return details;
    }

    function buildTicketAttachments(ticket) {
      const ticketRef = String(ticket?.ticket_ref || "").trim();
      const attachments = Array.isArray(ticket?.attachments) ? ticket.attachments : [];
      return attachments
        .map((item) => {
          const id = Number(item?.id || 0);
          const filename = String(item?.filename || item?.original_filename || "").trim();
          if (!ticketRef || id <= 0 || !filename) return null;
          return {
            filename,
            url: `/help-center/tickets/${encodeURIComponent(ticketRef)}/attachments/${id}`,
          };
        })
        .filter(Boolean);
    }

    function renderDetailsCell(cell, details) {
      if (!Array.isArray(details) || details.length === 0) {
        cell.textContent = "-";
        return;
      }
      const list = document.createElement("ul");
      list.className = "ticket-detail-list";
      details.forEach((item) => {
        const li = document.createElement("li");
        const label = document.createElement("strong");
        label.textContent = `${String(item?.label || "").trim()}: `;
        li.appendChild(label);
        li.append(document.createTextNode(String(item?.value || "").trim()));
        list.appendChild(li);
      });
      cell.appendChild(list);
    }

    function renderAttachmentsCell(cell, attachments) {
      if (!Array.isArray(attachments) || attachments.length === 0) {
        cell.textContent = "-";
        return;
      }
      const list = document.createElement("ul");
      list.className = "ticket-attachments-list";
      attachments.forEach((item) => {
        const li = document.createElement("li");
        const anchor = document.createElement("a");
        anchor.href = String(item.url || "#");
        anchor.textContent = String(item.filename || "").trim();
        li.appendChild(anchor);
        list.appendChild(li);
      });
      cell.appendChild(list);
    }

    function syncDynamicFields() {
      const bugMode = isBugReportCategory();
      const paymentMode = isPaymentIssueCategory();
      if (bugFieldsBox) {
        bugFieldsBox.hidden = !bugMode;
      }
      bugFieldInputs.forEach((input) => {
        if (input) {
          input.required = bugMode;
          if (!bugMode) {
            input.value = "";
          }
        }
      });
      if (paymentFieldsBox) {
        paymentFieldsBox.hidden = !paymentMode;
      }
      paymentFieldInputs.forEach((input) => {
        if (input) {
          input.required = paymentMode;
          if (!paymentMode) {
            input.value = "";
          }
        }
      });
      if (messageLabel) {
        messageLabel.textContent = bugMode
          ? "Message (steps to reproduce + expected vs actual)"
          : paymentMode
            ? "Message (what happened with the payment)"
            : "Message";
      }
      if (messageInput) {
        messageInput.placeholder = bugMode
          ? "Describe reproducible steps, expected behavior, actual behavior, and any error shown."
          : paymentMode
            ? "Describe what happened, expected result, paid amount, and any wallet/explorer context."
          : "";
      }
    }

    function prependTicketRow(ticket) {
      if (!historyBody || !historyWrap) {
        return;
      }
      const row = document.createElement("tr");

      const idCell = document.createElement("td");
      const idCode = document.createElement("code");
      idCode.textContent = String(ticket.ticket_ref || "");
      idCell.appendChild(idCode);

      const createdCell = document.createElement("td");
      createdCell.textContent = String(ticket.created_at_utc || "");

      const categoryCell = document.createElement("td");
      categoryCell.textContent = String(ticket.category || "");

      const statusCell = document.createElement("td");
      statusCell.textContent = String(ticket.status || "");

      const subjectCell = document.createElement("td");
      subjectCell.textContent = String(ticket.subject || "");

      const detailsCell = document.createElement("td");
      renderDetailsCell(detailsCell, buildTicketDetails(ticket));

      const attachmentsCell = document.createElement("td");
      renderAttachmentsCell(attachmentsCell, buildTicketAttachments(ticket));

      row.appendChild(idCell);
      row.appendChild(createdCell);
      row.appendChild(categoryCell);
      row.appendChild(statusCell);
      row.appendChild(subjectCell);
      row.appendChild(detailsCell);
      row.appendChild(attachmentsCell);

      historyBody.prepend(row);
      while (historyBody.children.length > 100) {
        historyBody.removeChild(historyBody.lastElementChild);
      }
      historyWrap.hidden = false;
      if (historyEmpty) {
        historyEmpty.hidden = true;
      }
    }

    if (categoryInput) {
      categoryInput.addEventListener("change", syncDynamicFields);
    }
    syncDynamicFields();

    form.addEventListener("submit", async (event) => {
      event.preventDefault();

      const payload = {
        email: isEmailLocked ? lockedEmail : String(emailInput?.value || "").trim(),
        category: String(categoryInput?.value || "").trim(),
        subject: String(subjectInput?.value || "").trim(),
        message: String(messageInput?.value || "").trim(),
        bug_surface: String(bugSurfaceInput?.value || "").trim(),
        bug_severity: String(bugSeverityInput?.value || "").trim(),
        bug_reproducible: String(bugReproducibleInput?.value || "").trim(),
        payment_txid: String(paymentTxidInput?.value || "").trim(),
        payment_chain: String(paymentChainInput?.value || "").trim(),
      };
      const body = new FormData();
      Object.entries(payload).forEach(([key, value]) => {
        body.append(key, value);
      });
      const files = attachmentsInput?.files ? Array.from(attachmentsInput.files) : [];
      files.forEach((file) => body.append("attachments", file));

      if (isEmailLocked && emailInput) {
        emailInput.value = lockedEmail;
      }

      output.textContent = "Sending ticket...";

      try {
        const response = await fetch("/api/v1/support/tickets", {
          method: "POST",
          body,
        });
        const data = await response.json().catch(() => ({}));

        if (response.ok && typeof data.ticket_id === "string" && data.ticket_id.length > 0) {
          if (canTrackHistory) {
            prependTicketRow({
              ticket_ref: String(data.ticket_id || ""),
              created_at_utc: String(data.created_at_utc || ""),
              category: String(data.category || payload.category || ""),
              status: String(data.status || "open"),
              subject: payload.subject,
              bug_surface: String(data.bug_surface || payload.bug_surface || ""),
              bug_severity: String(data.bug_severity || payload.bug_severity || ""),
              bug_reproducible: String(data.bug_reproducible || payload.bug_reproducible || ""),
              payment_txid: String(data.payment_txid || payload.payment_txid || ""),
              payment_chain: String(data.payment_chain || payload.payment_chain || ""),
              attachments: Array.isArray(data.attachments) ? data.attachments : [],
            });
          }
          if (isEmailLocked) {
            if (categoryInput) categoryInput.value = "general";
            if (subjectInput) subjectInput.value = "";
            if (messageInput) messageInput.value = "";
            if (attachmentsInput) attachmentsInput.value = "";
            if (emailInput) emailInput.value = lockedEmail;
            syncDynamicFields();
          } else {
            form.reset();
            syncDynamicFields();
          }
          const attachmentCount = Number(data.attachment_count || 0);
          output.textContent = attachmentCount > 0
            ? `Ticket Sent Correctly! (${attachmentCount} attachment${attachmentCount === 1 ? "" : "s"} scanned and uploaded)`
            : "Ticket Sent Correctly!";
          return;
        }

        const message = String(data.message || "Unable to create ticket.");
        output.textContent = message;
      } catch (_error) {
        output.textContent = "Unable to create ticket. Please try again.";
      }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initTicketForm);
    return;
  }
  initTicketForm();
})();
