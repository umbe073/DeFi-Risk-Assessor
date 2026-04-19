(function () {
  "use strict";

  const root = document.getElementById("risk-live-assessment-root");
  if (!root) {
    return;
  }

  const form = document.getElementById("risk-job-form");
  const feedback = document.getElementById("risk-create-feedback");
  const submitButton = form ? form.querySelector("button[type='submit']") : null;
  const modeSelect = form ? form.elements.namedItem("mode") : null;
  const jobProgressBar = document.getElementById("job-progress-bar");
  const jobProgressLabel = document.getElementById("job-progress-label");
  const jobStatus = document.getElementById("job-status");
  const jobStatusNote = document.getElementById("job-status-note");
  const jobStage = document.getElementById("job-stage");
  const jobToken = document.getElementById("job-token");
  const jobUpdatedAt = document.getElementById("job-updated-at");
  const jobLogBox = document.getElementById("job-log-box");
  const artifactBox = document.getElementById("job-artifact-box");
  const redFlagCardsRoot = document.getElementById("red-flag-cards");
  const phaseTracker = document.getElementById("phase-tracker");
  const jobIdNode = document.getElementById("job-id");

  const summaryRiskBand = document.getElementById("summary-risk-band");
  const summaryConfidence = document.getElementById("summary-confidence");
  const summaryHolders = document.getElementById("summary-holders");
  const summaryMarketCap = document.getElementById("summary-market-cap");
  const summaryLiquidity = document.getElementById("summary-liquidity");
  const summaryVolume24h = document.getElementById("summary-volume-24h");
  const riskPlanLabel = document.getElementById("risk-plan-label");
  const riskLimitLabel = document.getElementById("risk-limit-label");
  const riskUsedLabel = document.getElementById("risk-used-label");
  const riskRemainingLabel = document.getElementById("risk-remaining-label");
  const riskModesLabel = document.getElementById("risk-modes-label");
  const riskApiTierLabel = document.getElementById("risk-api-tier-label");
  const riskAccessNote = document.getElementById("risk-access-note");
  const stopBtn = document.getElementById("risk-stop-assessment-btn");
  const liveRunBtn = document.getElementById("risk-live-run-btn");
  const liveLayout = String(root.getAttribute("data-live-layout") || "single").trim();
  const listModeSelect = document.getElementById("risk-list-mode");
  const paidStartScansBtn = document.getElementById("risk-paid-start-scans");
  const listScanFeedback = document.getElementById("risk-list-scan-feedback");
  const tokensGridBody = document.getElementById("live-tokens-grid-body");
  const exportWrap = document.getElementById("live-assessment-export-wrap");
  const exportBtn = document.getElementById("risk-export-download-btn");
  const exportFormat = document.getElementById("risk-export-format");

  const stageOrder = ["queued", "fetching", "analyzing", "finalizing", "succeeded"];
  /* Wider per-stage spans so the bar does not sit at ~90% for most of a long run. */
  const stageProgressFloor = {
    queued: 0,
    fetching: 6,
    analyzing: 18,
    finalizing: 68,
    succeeded: 100,
    failed: 100,
    cancelled: 100,
  };
  const stageProgressCeiling = {
    queued: 5,
    fetching: 17,
    analyzing: 67,
    finalizing: 96,
    succeeded: 100,
    failed: 100,
    cancelled: 100,
  };
  const terminalStatuses = new Set(["succeeded", "failed", "cancelled"]);

  let activeJobId = String(root.getAttribute("data-initial-job-id") || "").trim();
  if (!activeJobId && jobIdNode) {
    activeJobId = String(jobIdNode.textContent || "").trim();
  }

  const state = {
    displayedProgress: Number(jobProgressLabel ? jobProgressLabel.textContent || 0 : 0),
    targetProgress: Number(jobProgressLabel ? jobProgressLabel.textContent || 0 : 0),
    animationFrame: null,
    pollTimer: null,
    /** @type {EventSource | null} */
    eventSource: null,
    streamDebounceTimer: null,
    lastLogPayload: "",
    lastArtifactPayload: "",
    lastRedFlagsPayload: "",
    lastKnownStage: "",
    lastKnownStatus: "",
    lastActiveStage: "",
  };

  let lastPolledJob = null;
  let lastGridJobs = [];
  let flagsFetchTimer = null;

  function clamp01(value) {
    return Math.max(0, Math.min(100, Number(value || 0)));
  }

  function escapeHtml(value) {
    return String(value || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function escapeAttr(value) {
    return String(value || "")
      .replace(/&/g, "&amp;")
      .replace(/"/g, "&quot;")
      .replace(/</g, "&lt;");
  }

  function tokenExplorerNameCell(row) {
    const name = row.token_name_label != null ? row.token_name_label : "—";
    const url = String(row.token_explorer_url || "").trim();
    if (url && (url.indexOf("https://") === 0 || url.indexOf("http://") === 0)) {
      return (
        '<a href="' +
        escapeAttr(url) +
        '" class="live-tokens-grid__explorer-link" target="_blank" rel="noopener noreferrer">' +
        escapeHtml(name) +
        "</a>"
      );
    }
    return escapeHtml(name);
  }

  function liveTokensGridStatusCell(row) {
    const st = String(row.status || "").trim();
    const stNorm = st.toLowerCase();
    const err = String(row.error_message || "").trim();
    let html =
      '<td class="live-tokens-grid__status">' +
      '<span class="live-tokens-grid__status-main">' +
      escapeHtml(st) +
      "</span>";
    if (stNorm === "failed" && err) {
      const short = err.length > 120 ? err.slice(0, 120) + "…" : err;
      html +=
        '<span class="live-tokens-grid__failure-note" title="' +
        escapeAttr(err) +
        '">' +
        escapeHtml(short) +
        "</span>";
    }
    html += "</td>";
    return html;
  }

  function syncTokensGridActiveRow() {
    if (!tokensGridBody || !root) {
      return;
    }
    const focusJid = String(root.getAttribute("data-focus-job-id") || "").trim();
    const focusAddr = String(root.getAttribute("data-focus-token-address") || "").trim().toLowerCase();
    const focusChain = String(root.getAttribute("data-focus-token-chain") || "").trim().toLowerCase();
    tokensGridBody.querySelectorAll("tr.live-tokens-grid__row").forEach(function (tr) {
      const jid = String(tr.getAttribute("data-job-id") || "").trim();
      const addr = String(tr.getAttribute("data-token-address") || "").trim().toLowerCase();
      const chain = String(tr.getAttribute("data-token-chain") || "").trim().toLowerCase();
      let active = false;
      if (focusJid && focusAddr) {
        active = jid === focusJid && addr === focusAddr && (!focusChain || !chain || chain === focusChain);
      } else if (focusJid) {
        active = jid === focusJid;
      } else if (focusAddr) {
        active = addr === focusAddr && (!focusChain || !chain || chain === focusChain);
      } else {
        active = jid && jid === activeJobId;
      }
      tr.classList.toggle("live-tokens-grid__row--active", active);
    });
  }

  function renderLiveTokensGrid(jobs) {
    if (!tokensGridBody) {
      return;
    }
    const list = Array.isArray(jobs) ? jobs : [];
    tokensGridBody.innerHTML = "";
    if (!list.length) {
      const tr = document.createElement("tr");
      tr.className = "live-tokens-grid__empty";
      tr.innerHTML = '<td colspan="15" class="muted">No rows yet.</td>';
      tokensGridBody.appendChild(tr);
      return;
    }
    list.forEach(function (row, idx) {
      const tr = document.createElement("tr");
      const rowStatus = String(row.status || "").trim().toLowerCase();
      tr.className = "live-tokens-grid__row";
      const jid = String(row.job_id || "").trim();
      tr.setAttribute("data-job-id", jid);
      tr.setAttribute("data-token-address", String(row.token_address || "").trim());
      tr.setAttribute("data-token-chain", String(row.token_chain || "").trim());
      tr.setAttribute("data-job-status", rowStatus);
      if (jid && jid === activeJobId) {
        tr.classList.add("live-tokens-grid__row--active");
      }
      if (rowStatus === "failed") {
        tr.classList.add("live-tokens-grid__row--failed");
      } else if (rowStatus === "cancelled") {
        tr.classList.add("live-tokens-grid__row--cancelled");
      }
      const band = String(row.risk_band || "unknown").trim().toLowerCase() || "unknown";
      const badgeLabel = row.risk_band_label != null && row.risk_band_label !== "" ? row.risk_band_label : "Unknown";
      const rowNum = row.grid_row_index != null ? Number(row.grid_row_index) : idx + 1;
      tr.innerHTML =
        '<td class="num live-tokens-grid__idx">#' +
        escapeHtml(String(rowNum)) +
        "</td>" +
        '<td class="live-tokens-grid__token-name">' +
        tokenExplorerNameCell(row) +
        "</td>" +
        '<td class="live-tokens-grid__symbol">' +
        escapeHtml(row.token_symbol_label != null ? row.token_symbol_label : "—") +
        "</td>" +
        "<td>" +
        escapeHtml(row.token_chain) +
        "</td>" +
        liveTokensGridStatusCell(row) +
        "<td>" +
        escapeHtml(row.stage) +
        "</td>" +
        '<td class="num">' +
        escapeHtml(row.progress != null ? String(row.progress) : "0") +
        "%</td>" +
        "<td><span class=\"status-badge dashboard-risk-badge risk-" +
        escapeHtml(band) +
        '">' +
        escapeHtml(badgeLabel) +
        "</span></td>" +
        '<td class="num">' +
        escapeHtml(row.confidence_label != null ? row.confidence_label : "n/a") +
        "</td>" +
        '<td class="num">' +
        escapeHtml(row.risk_score_label != null ? row.risk_score_label : "—") +
        "</td>" +
        '<td class="num">' +
        escapeHtml(row.total_score_minus_social_label != null ? row.total_score_minus_social_label : "—") +
        "</td>" +
        '<td class="num">' +
        escapeHtml(row.market_cap_label != null ? row.market_cap_label : "—") +
        "</td>" +
        '<td class="num">' +
        escapeHtml(row.volume_24h_label != null ? row.volume_24h_label : "—") +
        "</td>" +
        '<td class="num">' +
        escapeHtml(row.holders_label != null ? row.holders_label : "—") +
        "</td>" +
        '<td class="num">' +
        escapeHtml(row.liquidity_label != null ? row.liquidity_label : "—") +
        "</td>";
      tokensGridBody.appendChild(tr);
    });
    updateBatchProgressSummary(list);
  }

  function updateBatchProgressSummary(jobs) {
    const el = document.getElementById("live-batch-progress-summary");
    if (!el) {
      return;
    }
    const list = Array.isArray(jobs) ? jobs : [];
    if (!list.length) {
      el.textContent = "";
      return;
    }
    const total = list.length;
    let done = 0;
    let active = 0;
    let queued = 0;
    let failed = 0;
    let cancelled = 0;
    const failedLabels = [];
    list.forEach(function (row) {
      const s = String(row.status || "")
        .trim()
        .toLowerCase();
      if (s === "succeeded" || s === "failed" || s === "cancelled") {
        done += 1;
      } else if (s === "queued") {
        queued += 1;
      } else {
        active += 1;
      }
      if (s === "failed") {
        failed += 1;
        if (failedLabels.length < 3) {
          failedLabels.push(batchTokenLabel(row));
        }
      } else if (s === "cancelled") {
        cancelled += 1;
      }
    });
    const parts = [
      "Batch progress: " + String(done) + " of " + String(total) + " finished",
    ];
    if (failed) {
      let failedText = String(failed) + " failed";
      const visibleLabels = failedLabels.filter(Boolean);
      if (visibleLabels.length) {
        failedText += " (" + visibleLabels.join(", ");
        if (failed > visibleLabels.length) {
          failedText += ", +" + String(failed - visibleLabels.length) + " more";
        }
        failedText += ")";
      }
      parts.push(failedText);
    }
    if (cancelled) {
      parts.push(String(cancelled) + " cancelled");
    }
    if (active) {
      parts.push(String(active) + " in progress");
    }
    if (queued) {
      parts.push(String(queued) + " queued");
    }
    el.textContent = parts.join(" · ") + ".";
    el.classList.toggle("live-batch-progress-summary--has-failures", failed > 0);
    el.classList.toggle("live-batch-progress-summary--has-cancellations", cancelled > 0);
  }

  function batchTokenLabel(row) {
    const symbol = String(row.token_symbol_label || "").trim();
    if (symbol && symbol !== "—") {
      return symbol;
    }
    const name = String(row.token_name_label || "").trim();
    if (name && name !== "—") {
      return name;
    }
    const shortAddress = String(row.token_address_short || "").trim();
    if (shortAddress && shortAddress !== "—") {
      return shortAddress;
    }
    const address = String(row.token_address || "").trim();
    if (!address) {
      return "unknown";
    }
    return address.length <= 14 ? address : address.slice(0, 8) + "…" + address.slice(-4);
  }

  async function pollLiveBatchGrid() {
    const bid = String(root.getAttribute("data-list-batch-id") || "").trim();
    if (!bid || !tokensGridBody) {
      updateStopButtonVisibility(lastPolledJob);
      return;
    }
    try {
      const response = await fetch(
        "/api/v1/risk/live-batch/" + encodeURIComponent(bid) + "/snapshot",
        { credentials: "same-origin" }
      );
      if (!response.ok) {
        updateStopButtonVisibility(lastPolledJob);
        return;
      }
      const data = await response.json();
      lastGridJobs = data.jobs || [];
      renderLiveTokensGrid(lastGridJobs);
      updateDetailPanelsFromGridJobs(lastGridJobs);
    } catch (_err) {
      /* ignore */
    }
    updateStopButtonVisibility(lastPolledJob);
  }

  function setFeedback(message) {
    if (feedback) {
      feedback.textContent = String(message || "");
    }
  }

  function gridHasStoppableBatchJobs(jobs) {
    const list = Array.isArray(jobs) ? jobs : [];
    return list.some(function (row) {
      const s = String(row.status || "")
        .trim()
        .toLowerCase();
      return s === "queued" || s === "running";
    });
  }

  function updateStopButtonVisibility(job) {
    if (!stopBtn) {
      return;
    }
    if (!job || typeof job !== "object") {
      stopBtn.hidden = true;
      return;
    }
    const status = String(job.status || "").trim().toLowerCase();
    const batchId = root ? String(root.getAttribute("data-list-batch-id") || "").trim() : "";
    const gridMulti =
      String(root.getAttribute("data-tokens-grid-multi") || "").toLowerCase() === "true";
    const siblingActive =
      Boolean(batchId) && gridMulti && gridHasStoppableBatchJobs(lastGridJobs);
    stopBtn.hidden = terminalStatuses.has(status) && !siblingActive;
  }

  function applyRiskAccess(access) {
    if (!access || typeof access !== "object") {
      return;
    }
    const isAdminLike = Boolean(access.is_admin_like);
    const planName = String(access.plan_name || "").trim();
    const canUseEuMode = Boolean(access.can_use_eu_mode);
    const canSubmitAssessments = Boolean(access.can_submit_assessments);

    if (riskPlanLabel) {
      riskPlanLabel.textContent = planName || (isAdminLike ? "Staff Access" : "No Active Plan");
    }
    if (riskLimitLabel) {
      riskLimitLabel.textContent = String(access.daily_limit_label || access.scans_per_day_limit || "0");
    }
    if (riskUsedLabel) {
      riskUsedLabel.textContent = String(access.scans_used_today != null ? access.scans_used_today : "0");
    }
    if (riskRemainingLabel) {
      riskRemainingLabel.textContent = String(access.remaining_label || access.scans_remaining_today || "0");
    }
    if (riskModesLabel) {
      riskModesLabel.textContent = canUseEuMode ? "Global + EU" : "Global only";
    }
    if (riskApiTierLabel) {
      riskApiTierLabel.textContent = String(access.api_service_tier_label || "Unavailable");
    }
    if (riskAccessNote) {
      riskAccessNote.textContent = String(access.access_note || "");
    }
    if (modeSelect) {
      const euOption = modeSelect.querySelector("option[value='eu']");
      if (euOption) {
        euOption.disabled = !canUseEuMode;
        euOption.textContent = canUseEuMode ? "EU" : "EU (Basic+)";
      }
      if (!canUseEuMode && String(modeSelect.value || "").trim().toLowerCase() === "eu") {
        modeSelect.value = "global";
      }
    }
    if (listModeSelect) {
      const euOptList = listModeSelect.querySelector("option[value='eu']");
      if (euOptList) {
        euOptList.disabled = !canUseEuMode;
        euOptList.textContent = canUseEuMode ? "EU" : "EU (Basic+)";
      }
      if (!canUseEuMode && String(listModeSelect.value || "").trim().toLowerCase() === "eu") {
        listModeSelect.value = "global";
      }
    }
    if (submitButton) {
      submitButton.disabled = !canSubmitAssessments;
    }
    if (paidStartScansBtn) {
      paidStartScansBtn.disabled = !canSubmitAssessments;
    }
    root.setAttribute("data-can-submit-assessments", canSubmitAssessments ? "true" : "false");
    root.setAttribute("data-can-use-eu-mode", canUseEuMode ? "true" : "false");
  }

  function setListScanFeedback(message) {
    if (listScanFeedback) {
      listScanFeedback.textContent = String(message || "");
    }
  }

  if (exportBtn && exportFormat) {
    exportBtn.addEventListener("click", function () {
      if (!activeJobId) {
        return;
      }
      const fmt = String(exportFormat.value || "json").trim();
      window.location.href =
        "/api/v1/risk/jobs/" +
        encodeURIComponent(activeJobId) +
        "/export?format=" +
        encodeURIComponent(fmt);
    });
  }

  if (liveLayout === "list" && paidStartScansBtn) {
    paidStartScansBtn.addEventListener("click", async function () {
      const listId = String(root.getAttribute("data-active-list-id") || "").trim();
      if (!listId) {
        setListScanFeedback("Choose an active contract list under Settings → Crypto List.");
        return;
      }
      const mode = String((listModeSelect && listModeSelect.value) || "global")
        .trim()
        .toLowerCase();
      paidStartScansBtn.disabled = true;
      setListScanFeedback("Queueing assessment…");
      try {
        const response = await fetch(
          "/api/v1/risk/token-lists/" + encodeURIComponent(listId) + "/jobs",
          {
            method: "POST",
            credentials: "same-origin",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ mode: mode }),
          }
        );
        const data = await response.json().catch(function () {
          return {};
        });
        if (!response.ok) {
          const err = new Error(String(data.message || data.error || "queue_failed"));
          err.riskAccess = data.risk_access || null;
          throw err;
        }
        if (data.risk_access) {
          applyRiskAccess(data.risk_access);
        }
        const jobs = data.jobs || [];
        if (jobs.length && jobs[0].job_id) {
          window.location.href = "/live-assessment?job_id=" + encodeURIComponent(String(jobs[0].job_id));
          return;
        }
        setListScanFeedback(
          "Queued " + String(jobs.length) + " job(s). Check Recent Jobs or try again."
        );
      } catch (err) {
        if (err && err.riskAccess) {
          applyRiskAccess(err.riskAccess);
        }
        setListScanFeedback("Failed: " + String((err && err.message) || err || "unknown_error"));
      } finally {
        paidStartScansBtn.disabled = false;
      }
    });
  }

  function formatNumber(value) {
    const n = Number(value);
    if (!Number.isFinite(n)) {
      return "-";
    }
    return n.toLocaleString("en-US");
  }

  function formatCurrency(value) {
    const n = Number(value);
    if (!Number.isFinite(n)) {
      return "-";
    }
    return "$" + n.toLocaleString("en-US", { maximumFractionDigits: 0 });
  }

  function normalizeStage(rawStage, rawStatus) {
    const stage = String(rawStage || "").trim().toLowerCase();
    const status = String(rawStatus || "").trim().toLowerCase();
    if (stage) {
      return stage;
    }
    if (status) {
      return status;
    }
    return "queued";
  }

  function computeTargetProgress(job) {
    const stage = normalizeStage(job.stage, job.status);
    const status = String(job.status || "").trim().toLowerCase();
    const reportedRaw = clamp01(job.progress);
    const floor = stageProgressFloor[stage] != null ? stageProgressFloor[stage] : 0;
    const ceiling = stageProgressCeiling[stage] != null ? stageProgressCeiling[stage] : 100;

    if (terminalStatuses.has(status)) {
      return 100;
    }

    const span = Math.max(0, ceiling - floor);
    let frac = Math.min(1, Math.max(0, reportedRaw / 100));
    /* Slightly dampen early worker % spikes so the bar climbs more gradually. */
    frac = Math.pow(frac, 1.12);
    let target = floor + frac * span;
    if (!Number.isFinite(target)) {
      target = floor;
    }
    target = Math.max(target, floor);
    target = Math.min(target, ceiling);
    if (target < state.displayedProgress) {
      return state.displayedProgress;
    }
    return clamp01(target);
  }

  function statusNoteForJob(job) {
    const payload = job && typeof job === "object" ? job : {};
    const errorMessage = String(payload.error_message || "").trim();
    const summaryMessage = String(payload.summary_message || "").trim();
    const status = String(payload.status || "").trim().toLowerCase();
    if (errorMessage) {
      return errorMessage;
    }
    if (status === "queued") {
      const hint = String(payload.queue_hint || "").trim();
      if (hint) {
        return hint;
      }
    }
    if (summaryMessage) {
      return summaryMessage;
    }
    if (status === "failed") {
      return "Assessment failed.";
    }
    if (status === "cancelled") {
      return "Assessment cancelled.";
    }
    if (status === "succeeded") {
      return "Risk assessment complete!";
    }
    return "Waiting for worker updates...";
  }

  function animateProgressTo(nextProgress) {
    const target = clamp01(nextProgress);
    state.targetProgress = Math.max(state.targetProgress, target);
    if (state.animationFrame) {
      return;
    }

    const tick = function () {
      const delta = state.targetProgress - state.displayedProgress;
      if (Math.abs(delta) < 0.35) {
        state.displayedProgress = state.targetProgress;
      } else {
        state.displayedProgress += delta * 0.11;
      }
      if (jobProgressLabel) {
        jobProgressLabel.textContent = String(Math.round(state.displayedProgress));
      }
      if (jobProgressBar) {
        jobProgressBar.style.width = state.displayedProgress.toFixed(2) + "%";
      }

      if (Math.abs(state.targetProgress - state.displayedProgress) > 0.2) {
        state.animationFrame = window.requestAnimationFrame(tick);
      } else {
        state.animationFrame = null;
      }
    };

    state.animationFrame = window.requestAnimationFrame(tick);
  }

  function updatePhaseTracker(stage, status) {
    if (!phaseTracker) {
      return;
    }
    const normalizedStage = normalizeStage(stage, status);
    const normalizedStatus = String(status || "").trim().toLowerCase();
    let displayStage = normalizedStage;
    if (!terminalStatuses.has(normalizedStatus) && normalizedStage !== "failed" && normalizedStage !== "cancelled") {
      state.lastActiveStage = normalizedStage;
    } else if (normalizedStatus === "failed") {
      displayStage = state.lastActiveStage || "finalizing";
    } else if (normalizedStatus === "cancelled") {
      displayStage = state.lastActiveStage || "queued";
    }
    const currentIndex = Math.max(0, stageOrder.indexOf(displayStage));
    const nodes = phaseTracker.querySelectorAll("li[data-phase]");
    nodes.forEach(function (node) {
      const phaseName = String(node.getAttribute("data-phase") || "").trim().toLowerCase();
      const phaseIndex = stageOrder.indexOf(phaseName);
      node.classList.remove("done", "active", "pending", "failed");
      if (normalizedStatus === "failed") {
        if (phaseIndex >= 0 && phaseIndex < currentIndex) {
          node.classList.add("done");
        } else if (phaseIndex === currentIndex) {
          node.classList.add("failed");
        } else {
          node.classList.add("pending");
        }
        return;
      }
      if (normalizedStatus === "cancelled") {
        if (phaseIndex >= 0 && phaseIndex < currentIndex) {
          node.classList.add("done");
        } else {
          node.classList.add("pending");
        }
        return;
      }
      if (phaseIndex >= 0 && phaseIndex < currentIndex) {
        node.classList.add("done");
      } else if (phaseIndex === currentIndex) {
        node.classList.add("active");
      } else {
        node.classList.add("pending");
      }
    });
  }

  function renderLogs(events, job) {
    if (!jobLogBox) {
      return;
    }
    const ordered = Array.isArray(events) ? events.slice().reverse() : [];
    const j = job && typeof job === "object" ? job : {};
    const st = String(j.status || "").trim().toLowerCase();
    const qh = String(j.queue_hint || "").trim();
    const queueLine =
      st === "queued" && qh ? "[queue] " + qh : "";
    const lines = ordered.map(function (event) {
      const ts = String(event.created_at_utc || "");
      const stage = String(event.stage || "");
      const msg = String(event.message || event.event_type || "event");
      return "[" + ts + "] [" + stage + "] " + msg;
    });
    if (queueLine) {
      lines.unshift(queueLine);
    }
    const nextPayload =
      lines.length === 0
        ? "[queued] Waiting for worker updates..."
        : lines.join("\n");
    if (nextPayload !== state.lastLogPayload) {
      jobLogBox.textContent = nextPayload;
      state.lastLogPayload = nextPayload;
    }
  }

  function formatEngineScore(value) {
    if (value == null || value === "") {
      return "—";
    }
    const n = Number(value);
    if (!Number.isFinite(n)) {
      return "—";
    }
    if (Math.abs(n - Math.round(n)) < 1e-6) {
      return String(Math.round(n));
    }
    return n.toFixed(2);
  }

  function formatPctCell(pct) {
    if (pct == null || pct === "") {
      return "—";
    }
    const n = Number(pct);
    if (!Number.isFinite(n)) {
      return "—";
    }
    return String(Math.round(n)) + "%";
  }

  function deriveBandFromScore(raw) {
    const n = Number(raw);
    if (!Number.isFinite(n)) {
      return "";
    }
    if (n >= 105) {
      return "extreme";
    }
    if (n >= 75) {
      return "high";
    }
    if (n >= 45) {
      return "medium";
    }
    return "low";
  }

  function renderScoringTables(payload) {
    const p = payload && typeof payload === "object" ? payload : {};
    const confCell = formatPctCell(p.confidence_pct);

    const cellRiskScore = document.getElementById("cell-risk-score");
    const cellRiskConf = document.getElementById("cell-risk-conf");
    const cellTmsScore = document.getElementById("cell-tms-score");
    const cellTmsConf = document.getElementById("cell-tms-conf");
    const cellSocialScore = document.getElementById("cell-social-score");

    if (cellRiskScore) {
      cellRiskScore.textContent = formatEngineScore(p.risk_score);
    }
    if (cellRiskConf) {
      cellRiskConf.textContent = confCell;
    }
    if (cellTmsScore) {
      cellTmsScore.textContent = formatEngineScore(p.total_score_minus_social);
    }
    if (cellTmsConf) {
      cellTmsConf.textContent = confCell;
    }
    if (cellSocialScore) {
      cellSocialScore.textContent = formatEngineScore(p.social_risk_contribution);
    }

    const signals = p.signals && typeof p.signals === "object" ? p.signals : {};
    const catConf =
      p.category_confidence_pct && typeof p.category_confidence_pct === "object" ? p.category_confidence_pct : {};
    const catRows = [
      { scoreId: "cell-sig-liq-score", confId: "cell-sig-liq-conf", sigKey: "liquidity_signal", cat: "liquidity" },
      { scoreId: "cell-sig-ctr-score", confId: "cell-sig-ctr-conf", sigKey: "contract_signal", cat: "contract" },
      { scoreId: "cell-sig-mkt-score", confId: "cell-sig-mkt-conf", sigKey: "market_signal", cat: "market" },
      { scoreId: "cell-sig-beh-score", confId: "cell-sig-beh-conf", sigKey: "behavior_signal", cat: "behavior" },
    ];
    catRows.forEach(function (row) {
      const sEl = document.getElementById(row.scoreId);
      const cEl = document.getElementById(row.confId);
      const sv = signals[row.sigKey];
      if (sEl) {
        sEl.textContent = sv != null && sv !== "" ? String(sv) : "—";
      }
      const cv = catConf[row.cat];
      if (cEl) {
        cEl.textContent = cv != null && cv !== "" ? String(cv) + "%" : "—";
      }
    });
  }

  function renderSummary(metadata) {
    const payload = metadata && typeof metadata === "object" ? metadata : {};
    const keyMetrics = payload.key_metrics && typeof payload.key_metrics === "object" ? payload.key_metrics : {};

    let band = String(payload.risk_band || "").trim().toLowerCase();
    if (!band || band === "unknown") {
      const d = deriveBandFromScore(payload.risk_score);
      if (d) {
        band = d;
      }
    }
    const bandLabels = {
      low: "Low Risk",
      medium: "Medium Risk",
      high: "High Risk",
      extreme: "Extreme Risk",
    };
    if (summaryRiskBand) {
      summaryRiskBand.textContent = bandLabels[band] || (band && band !== "unknown" ? band : "Unknown");
      summaryRiskBand.className = "status-badge dashboard-risk-badge";
      summaryRiskBand.classList.add(band && band !== "unknown" ? "risk-" + band : "risk-unknown");
    }
    if (summaryConfidence) {
      summaryConfidence.textContent = formatPctCell(payload.confidence_pct);
    }
    if (summaryHolders) {
      summaryHolders.textContent = formatNumber(keyMetrics.holders);
    }
    if (summaryMarketCap) {
      summaryMarketCap.textContent = formatCurrency(keyMetrics.market_cap_usd);
    }
    if (summaryLiquidity) {
      summaryLiquidity.textContent = formatCurrency(keyMetrics.liquidity_usd);
    }
    if (summaryVolume24h) {
      summaryVolume24h.textContent = formatCurrency(keyMetrics.volume_24h_usd);
    }
    renderScoringTables(payload);
  }

  function pickFocusedGridRow(jobs) {
    const list = Array.isArray(jobs) ? jobs : [];
    if (!list.length) {
      return null;
    }
    const wantJ = root ? String(root.getAttribute("data-focus-job-id") || "").trim() : "";
    const wantA = root ? String(root.getAttribute("data-focus-token-address") || "").trim().toLowerCase() : "";
    const wantC = root ? String(root.getAttribute("data-focus-token-chain") || "").trim().toLowerCase() : "";
    if (wantJ) {
      for (let i = 0; i < list.length; i++) {
        const r = list[i];
        if (String(r.job_id || "").trim() !== wantJ) {
          continue;
        }
        if (wantA) {
          const ra = String(r.token_address || "").trim().toLowerCase();
          const rc = String(r.token_chain || "").trim().toLowerCase();
          if (ra !== wantA || (wantC && rc && rc !== wantC)) {
            continue;
          }
        }
        return r;
      }
    }
    if (wantA) {
      for (let i = 0; i < list.length; i++) {
        const r = list[i];
        const ra = String(r.token_address || "").trim().toLowerCase();
        if (ra !== wantA) {
          continue;
        }
        if (wantC) {
          const rc = String(r.token_chain || "").trim().toLowerCase();
          if (rc && rc !== wantC) {
            continue;
          }
        }
        return r;
      }
    }
    return list[0];
  }

  function renderSummaryFromGridRow(row) {
    if (!row || typeof row !== "object") {
      return;
    }
    const band = String(row.risk_band || "unknown").trim().toLowerCase() || "unknown";
    const bandLabel = row.risk_band_label != null && row.risk_band_label !== "" ? String(row.risk_band_label) : "Unknown";
    if (summaryRiskBand) {
      summaryRiskBand.textContent = bandLabel;
      summaryRiskBand.className = "status-badge dashboard-risk-badge";
      summaryRiskBand.classList.add(band && band !== "unknown" ? "risk-" + band : "risk-unknown");
    }
    if (summaryConfidence) {
      summaryConfidence.textContent = row.confidence_label != null ? String(row.confidence_label) : "n/a";
    }
    if (summaryHolders) {
      summaryHolders.textContent = row.holders_label != null ? String(row.holders_label) : "—";
    }
    if (summaryMarketCap) {
      summaryMarketCap.textContent = row.market_cap_label != null ? String(row.market_cap_label) : "—";
    }
    if (summaryLiquidity) {
      summaryLiquidity.textContent = row.liquidity_label != null ? String(row.liquidity_label) : "—";
    }
    if (summaryVolume24h) {
      summaryVolume24h.textContent = row.volume_24h_label != null ? String(row.volume_24h_label) : "—";
    }
  }

  function scheduleArtifactRefreshForFocus() {
    if (flagsFetchTimer) {
      window.clearTimeout(flagsFetchTimer);
    }
    flagsFetchTimer = window.setTimeout(function () {
      flagsFetchTimer = null;
      refreshArtifactsForFocusNow();
    }, 450);
  }

  async function refreshArtifactsForFocusNow() {
    if (!root) {
      return;
    }
    const jid = String(root.getAttribute("data-focus-job-id") || "").trim();
    if (!jid) {
      return;
    }
    try {
      const response = await fetch(
        "/api/v1/risk/jobs/" +
          encodeURIComponent(jid) +
          "?events=0&artifacts=1&artifact_limit=220",
        { credentials: "same-origin" }
      );
      if (!response.ok) {
        return;
      }
      const payload = await response.json();
      const job = payload.job;
      if (!job || typeof job !== "object") {
        return;
      }
      const meta =
        riskSummaryMetadataForJob({ artifacts: Array.isArray(job.artifacts) ? job.artifacts : [] }) || {};
      renderRedFlags(meta);
      renderArtifactRaw(meta);
    } catch (_err) {
      /* ignore */
    }
  }

  function updateDetailPanelsFromGridJobs(jobs) {
    const row = pickFocusedGridRow(jobs);
    if (!row) {
      return;
    }
    renderSummaryFromGridRow(row);
    scheduleArtifactRefreshForFocus();
    syncTokensGridActiveRow();
  }

  function humanizeRedFlag(code) {
    const s = String(code || "").trim();
    if (!s) {
      return "";
    }
    if (s === "is_wrapped_token") {
      return "Is a Wrapped-Token?";
    }
    return s.replace(/_/g, " ").replace(/\b\w/g, function (ch) {
      return ch.toUpperCase();
    });
  }

  function renderRedFlags(metadata) {
    if (!redFlagCardsRoot) {
      return;
    }
    if (metadata && metadata.red_flags_available === false) {
      const hiddenNote = String(metadata.red_flags_note || "Red flags are hidden by the current plan.");
      if (hiddenNote === state.lastRedFlagsPayload) {
        return;
      }
      state.lastRedFlagsPayload = hiddenNote;
      redFlagCardsRoot.innerHTML = "";
      const article = document.createElement("article");
      article.className = "red-flag-card red-flag-card--note";
      article.setAttribute("role", "listitem");
      const title = document.createElement("div");
      title.className = "red-flag-card__title";
      title.textContent = "Unavailable";
      const code = document.createElement("div");
      code.className = "red-flag-card__code";
      code.textContent = hiddenNote;
      article.appendChild(title);
      article.appendChild(code);
      redFlagCardsRoot.appendChild(article);
      return;
    }
    const flags = metadata && Array.isArray(metadata.red_flags) ? metadata.red_flags : [];
    const serialized = JSON.stringify(flags);
    if (serialized === state.lastRedFlagsPayload) {
      return;
    }
    state.lastRedFlagsPayload = serialized;
    redFlagCardsRoot.innerHTML = "";
    redFlagCardsRoot.setAttribute("role", "list");
    if (flags.length === 0) {
      const article = document.createElement("article");
      article.className = "red-flag-card red-flag-card--empty";
      article.setAttribute("role", "listitem");
      const title = document.createElement("div");
      title.className = "red-flag-card__title";
      title.textContent = "None detected";
      const code = document.createElement("div");
      code.className = "red-flag-card__code";
      code.textContent = "No red flags in the current snapshot.";
      article.appendChild(title);
      article.appendChild(code);
      redFlagCardsRoot.appendChild(article);
      return;
    }
    flags.forEach(function (flag) {
      const article = document.createElement("article");
      article.className = "red-flag-card";
      article.setAttribute("role", "listitem");
      const title = document.createElement("div");
      title.className = "red-flag-card__title";
      title.textContent = humanizeRedFlag(flag);
      const code = document.createElement("div");
      code.className = "red-flag-card__code";
      code.textContent = String(flag || "");
      article.appendChild(title);
      article.appendChild(code);
      redFlagCardsRoot.appendChild(article);
    });
  }

  function latestRiskSummaryMetadataFromJob(job) {
    const artifacts = Array.isArray(job.artifacts) ? job.artifacts : [];
    let bestId = -1;
    let meta = null;
    artifacts.forEach(function (art) {
      if (!art || typeof art !== "object") {
        return;
      }
      const kind = String(art.artifact_kind || "").trim().toLowerCase();
      if (kind !== "risk_summary") {
        return;
      }
      const id = Number(art.id || 0);
      const m = art.metadata;
      if (!m || typeof m !== "object") {
        return;
      }
      if (id > bestId) {
        bestId = id;
        meta = m;
      }
    });
    return meta;
  }

  function riskSummaryMetadataForJob(job) {
    const j = job && typeof job === "object" ? job : {};
    const artifacts = Array.isArray(j.artifacts) ? j.artifacts : [];
    const wantA = root ? String(root.getAttribute("data-focus-token-address") || "").trim().toLowerCase() : "";
    const wantC = root ? String(root.getAttribute("data-focus-token-chain") || "").trim().toLowerCase() : "";
    if (wantA) {
      let bestId = -1;
      let meta = null;
      artifacts.forEach(function (art) {
        if (!art || typeof art !== "object") {
          return;
        }
        const kind = String(art.artifact_kind || "").trim().toLowerCase();
        if (kind !== "risk_summary") {
          return;
        }
        const m = art.metadata;
        if (!m || typeof m !== "object") {
          return;
        }
        const ta = String(m.token_address || "").trim().toLowerCase();
        if (ta !== wantA) {
          return;
        }
        if (wantC) {
          const tc = String(m.token_chain || "").trim().toLowerCase();
          if (tc && tc !== wantC) {
            return;
          }
        }
        const id = Number(art.id || 0);
        if (id > bestId) {
          bestId = id;
          meta = m;
        }
      });
      if (meta) {
        return meta;
      }
    }
    if (!wantA) {
      return latestRiskSummaryMetadataFromJob(j);
    }
    return {};
  }

  function renderArtifactRaw(metadata) {
    if (!artifactBox) {
      return;
    }
    const payload = metadata && typeof metadata === "object" ? JSON.stringify(metadata, null, 2) : "No artifacts yet.";
    if (payload !== state.lastArtifactPayload) {
      artifactBox.textContent = payload;
      state.lastArtifactPayload = payload;
    }
  }

  function renderJob(job) {
    if (!job || typeof job !== "object") {
      return false;
    }

    activeJobId = String(job.job_id || "").trim();
    if (jobIdNode) {
      jobIdNode.textContent = activeJobId;
    }

    const status = String(job.status || "").trim().toLowerCase();
    const stage = normalizeStage(job.stage, status);

    state.lastKnownStatus = status;
    state.lastKnownStage = stage;

    if (jobStatus) {
      jobStatus.textContent = status || "-";
    }
    if (jobStage) {
      jobStage.textContent = stage || "-";
    }
    if (jobStatusNote) {
      jobStatusNote.textContent = statusNoteForJob(job);
    }
    if (jobUpdatedAt) {
      jobUpdatedAt.textContent = String(job.updated_at_utc || "-");
    }
    if (jobToken) {
      jobToken.innerHTML = "";
      const codeNode = document.createElement("code");
      const focusAddr = root ? String(root.getAttribute("data-focus-token-address") || "").trim() : "";
      codeNode.textContent = focusAddr || String(job.token_address || "");
      jobToken.appendChild(codeNode);
    }

    updatePhaseTracker(stage, status);
    animateProgressTo(computeTargetProgress(job));
    renderLogs(job.events, job);

    lastPolledJob = job;
    const gridMulti =
      String(root.getAttribute("data-tokens-grid-multi") || "").toLowerCase() === "true";
    if (gridMulti || lastGridJobs.length > 1) {
      if (lastGridJobs.length) {
        updateDetailPanelsFromGridJobs(lastGridJobs);
      }
    } else {
      const latestMetadata = riskSummaryMetadataForJob(job);
      renderSummary(latestMetadata || {});
      renderRedFlags(latestMetadata || {});
      renderArtifactRaw(latestMetadata || {});
    }

    updateStopButtonVisibility(job);
    if (exportWrap) {
      exportWrap.hidden = status !== "succeeded";
    }
    syncTokensGridActiveRow();
    const batchFromMeta = String(
      (job.metadata && typeof job.metadata === "object" && job.metadata.list_batch_id) || ""
    ).trim();
    if (root) {
      if (batchFromMeta) {
        root.setAttribute("data-list-batch-id", batchFromMeta);
      } else {
        root.removeAttribute("data-list-batch-id");
      }
    }
    return !terminalStatuses.has(status);
  }

  function stopRiskEventSource() {
    if (state.streamDebounceTimer) {
      window.clearTimeout(state.streamDebounceTimer);
      state.streamDebounceTimer = null;
    }
    if (state.eventSource) {
      try {
        state.eventSource.close();
      } catch (_err) {
        /* ignore */
      }
      state.eventSource = null;
    }
  }

  /**
   * Prefer Server-Sent Events for job updates; debounced full REST polls still load artifacts.
   * Falls back to timer-only polling if EventSource fails or disconnects.
   */
  function startRiskEventSource() {
    stopRiskEventSource();
    if (!activeJobId || typeof window.EventSource === "undefined") {
      return;
    }
    var url = "/api/v1/risk/jobs/" + encodeURIComponent(activeJobId) + "/stream";
    var es = null;
    try {
      es = new window.EventSource(url);
    } catch (_err) {
      return;
    }
    state.eventSource = es;
    es.onmessage = function (ev) {
      var text = String(ev.data || "").trim();
      if (!text) {
        return;
      }
      try {
        var o = JSON.parse(text);
        if (o.terminal) {
          stopRiskEventSource();
          pollJob();
          return;
        }
      } catch (_e) {
        /* ignore non-JSON */
      }
      if (state.streamDebounceTimer) {
        window.clearTimeout(state.streamDebounceTimer);
      }
      state.streamDebounceTimer = window.setTimeout(function () {
        state.streamDebounceTimer = null;
        pollJob();
      }, 400);
    };
    es.onerror = function () {
      stopRiskEventSource();
    };
  }

  function scheduleNextPoll(isActive) {
    if (state.pollTimer) {
      window.clearTimeout(state.pollTimer);
      state.pollTimer = null;
    }
    var usingStream = Boolean(state.eventSource);
    var delay = usingStream ? (isActive ? 8000 : 12000) : isActive ? 1800 : 7000;
    state.pollTimer = window.setTimeout(pollJob, delay);
  }

  async function refreshRiskAccessSnapshot() {
    try {
      const response = await fetch("/api/v1/risk/access", { credentials: "same-origin" });
      if (!response.ok) {
        return;
      }
      const payload = await response.json();
      if (payload && payload.risk_access) {
        applyRiskAccess(payload.risk_access);
      }
    } catch (_err) {
      /* ignore */
    }
  }

  async function pollJob() {
    if (!activeJobId) {
      return;
    }
    try {
      const response = await fetch(
        "/api/v1/risk/jobs/" +
          encodeURIComponent(activeJobId) +
          "?events=1&artifacts=1&event_limit=120&artifact_limit=200",
        { credentials: "same-origin" }
      );
      if (!response.ok) {
        scheduleNextPoll(true);
        return;
      }
      const payload = await response.json();
      if (!payload || !payload.job) {
        scheduleNextPoll(true);
        return;
      }
      const prevNorm = String(state.lastKnownStatus || "").trim().toLowerCase();
      const active = renderJob(payload.job);
      const nextStatus = String(payload.job.status || "").trim().toLowerCase();
      if (nextStatus === "succeeded" && prevNorm !== "succeeded") {
        refreshRiskAccessSnapshot();
      }
      if (!active) {
        stopRiskEventSource();
      }
      scheduleNextPoll(active);
      await pollLiveBatchGrid();
    } catch (_err) {
      scheduleNextPoll(true);
    }
  }

  function showStopBatchFeedback(message) {
    const msg = String(message || "").trim();
    if (!msg) {
      return;
    }
    if (listScanFeedback && liveLayout === "list") {
      setListScanFeedback(msg);
      window.setTimeout(function () {
        setListScanFeedback("");
      }, 10000);
    } else if (jobStatusNote) {
      jobStatusNote.textContent = msg;
    }
  }

  if (stopBtn) {
    stopBtn.addEventListener("click", async function () {
      if (!activeJobId) {
        return;
      }
      stopBtn.disabled = true;
      try {
        const batchId = root ? String(root.getAttribute("data-list-batch-id") || "").trim() : "";
        const cancelBody = { reason: "Stopped from Live Assessment" };
        if (batchId) {
          cancelBody.cancel_entire_list_batch = true;
        }
        const response = await fetch(
          "/api/v1/risk/jobs/" + encodeURIComponent(activeJobId) + "/cancel",
          {
            method: "POST",
            credentials: "same-origin",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(cancelBody),
          }
        );
        const data = await response.json().catch(function () {
          return {};
        });
        if (!response.ok) {
          showStopBatchFeedback(String(data.message || data.error || "Stop failed."));
        } else if (data.job) {
          const active = renderJob(data.job);
          scheduleNextPoll(active);
          const n = Number(data.cancelled_count);
          if (cancelBody.cancel_entire_list_batch && n > 1) {
            showStopBatchFeedback("Stopped " + String(n) + " assessments for this list batch.");
          }
        } else {
          await pollJob();
        }
        await refreshRiskAccessSnapshot();
        await pollLiveBatchGrid();
      } catch (_err) {
        await pollJob();
      } finally {
        stopBtn.disabled = false;
      }
    });
  }

  async function createJob(payload) {
    const response = await fetch("/api/v1/risk/jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok) {
      const error = new Error(String(data.message || data.error || "create_job_failed"));
      error.riskAccess = data.risk_access || null;
      throw error;
    }
    return data;
  }

  const batchChain = document.getElementById("risk-batch-chain");
  const batchMode = document.getElementById("risk-batch-mode");
  const batchText = document.getElementById("risk-batch-addresses");
  const batchBtn = document.getElementById("risk-batch-submit");
  const batchFeedback = document.getElementById("risk-batch-feedback");

  function setBatchFeedback(message) {
    if (batchFeedback) {
      batchFeedback.textContent = String(message || "");
    }
  }

  async function createBatchJobs(items) {
    const response = await fetch("/api/v1/risk/jobs/batch", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
      body: JSON.stringify({ items: items, source: "live_assessment_batch" }),
    });
    const data = await response.json();
    if (!response.ok) {
      const error = new Error(String(data.message || data.error || "batch_failed"));
      error.riskAccess = data.risk_access || null;
      throw error;
    }
    return data;
  }

  if (liveLayout !== "list" && batchBtn && batchText && batchChain) {
    batchBtn.addEventListener("click", async function () {
      const chain = String(batchChain.value || "").trim();
      if (!chain) {
        setBatchFeedback("Select a chain for the batch.");
        return;
      }
      const mode = String((batchMode && batchMode.value) || "global")
        .trim()
        .toLowerCase();
      const rawLines = String(batchText.value || "").split(/\r?\n/);
      const lines = [];
      const seen = new Set();
      rawLines.forEach(function (line) {
        const t = String(line || "").trim();
        if (!t) {
          return;
        }
        const key = t.toLowerCase();
        if (seen.has(key)) {
          return;
        }
        seen.add(key);
        lines.push(t);
      });
      if (!lines.length) {
        setBatchFeedback("Paste at least one address.");
        return;
      }
      batchBtn.disabled = true;
      setBatchFeedback("Queueing…");
      const items = lines.map(function (addr) {
        return { token_address: addr, token_chain: chain, mode: mode };
      });
      try {
        const created = await createBatchJobs(items);
        if (created.risk_access) {
          applyRiskAccess(created.risk_access);
        }
        const jobs = created.jobs || [];
        const rejected = created.rejected || [];
        if (jobs.length && jobs[0].job_id) {
          window.location.href = "/live-assessment?job_id=" + encodeURIComponent(String(jobs[0].job_id));
          return;
        }
        setBatchFeedback(
          "Queued " + String(jobs.length) + ", rejected " + String(rejected.length) + ". Check messages above."
        );
      } catch (err) {
        if (err && err.riskAccess) {
          applyRiskAccess(err.riskAccess);
        }
        setBatchFeedback("Batch failed: " + String((err && err.message) || err || "unknown_error"));
      } finally {
        batchBtn.disabled = false;
      }
    });
  }

  if (liveRunBtn && form) {
    liveRunBtn.addEventListener("click", function () {
      form.requestSubmit();
    });
  }

  if (form) {
    form.addEventListener("submit", async function (event) {
      event.preventDefault();
      if (submitButton) {
        submitButton.disabled = true;
      }
      setFeedback("Creating job...");
      const tokenAddress = String((form.elements.namedItem("token_address") || {}).value || "").trim();
      const tokenChain = String((form.elements.namedItem("token_chain") || {}).value || "").trim();
      const mode = String((form.elements.namedItem("mode") || {}).value || "global")
        .trim()
        .toLowerCase();

      try {
        const created = await createJob({
          token_address: tokenAddress,
          token_chain: tokenChain,
          mode: mode,
          source: "live_assessment_ui",
        });
        const job = created.job || {};
        if (created.risk_access) {
          applyRiskAccess(created.risk_access);
        }
        const jobId = String(job.job_id || "").trim();
        if (!jobId) {
          throw new Error("missing_job_id");
        }
        window.location.href = "/live-assessment?job_id=" + encodeURIComponent(jobId);
      } catch (err) {
        if (err && err.riskAccess) {
          applyRiskAccess(err.riskAccess);
        }
        setFeedback("Failed to create job: " + String((err && err.message) || err || "unknown_error"));
        if (submitButton && String(root.getAttribute("data-can-submit-assessments") || "false") === "true") {
          submitButton.disabled = false;
        }
      }
    });
  }

  if (tokensGridBody && root) {
    tokensGridBody.addEventListener("click", function (ev) {
      if (ev.target.closest("a.live-tokens-grid__explorer-link")) {
        return;
      }
      const tr = ev.target.closest("tr.live-tokens-grid__row");
      if (!tr) {
        return;
      }
      const addr = String(tr.getAttribute("data-token-address") || "").trim();
      const chain = String(tr.getAttribute("data-token-chain") || "").trim();
      if (!addr) {
        return;
      }
      root.setAttribute("data-focus-token-address", addr);
      root.setAttribute("data-focus-token-chain", chain);
      const jid = String(tr.getAttribute("data-job-id") || "").trim();
      if (jid) {
        root.setAttribute("data-focus-job-id", jid);
      } else {
        root.removeAttribute("data-focus-job-id");
      }
      if (jobToken) {
        jobToken.innerHTML = "";
        const codeNode = document.createElement("code");
        codeNode.textContent = addr;
        jobToken.appendChild(codeNode);
      }
      updateDetailPanelsFromGridJobs(lastGridJobs);
    });
  }

  function seedBatchSummaryFromDom() {
    if (!tokensGridBody) {
      return;
    }
    const rows = tokensGridBody.querySelectorAll("tr.live-tokens-grid__row");
    if (!rows.length) {
      return;
    }
    const jobs = [];
    rows.forEach(function (tr) {
      let status = String(tr.getAttribute("data-job-status") || "")
        .trim()
        .toLowerCase();
      if (!status) {
        const tds = tr.querySelectorAll("td");
        if (tds.length < 5) {
          return;
        }
        const main = tds[4].querySelector(".live-tokens-grid__status-main");
        status = String((main && main.textContent) || tds[4].textContent || "")
          .trim()
          .toLowerCase();
      }
      if (!status) {
        return;
      }
      const cells = tr.querySelectorAll("td");
      jobs.push({
        status: status,
        token_name_label: cells.length > 1 ? String(cells[1].textContent || "").trim() : "",
        token_symbol_label: cells.length > 2 ? String(cells[2].textContent || "").trim() : "",
        token_address_short: String(tr.getAttribute("data-token-address") || "").trim(),
      });
    });
    if (jobs.length) {
      updateBatchProgressSummary(jobs);
    }
  }

  seedBatchSummaryFromDom();
  syncTokensGridActiveRow();

  window.addEventListener("beforeunload", stopRiskEventSource);

  if (activeJobId) {
    startRiskEventSource();
    pollJob();
  } else {
    updatePhaseTracker("queued", "queued");
  }
})();
