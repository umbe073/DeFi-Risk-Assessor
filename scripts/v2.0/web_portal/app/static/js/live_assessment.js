(function () {
  "use strict";

  const root = document.getElementById("risk-live-assessment-root");
  if (!root) {
    return;
  }

  const form = document.getElementById("risk-job-form");
  const feedback = document.getElementById("risk-create-feedback");
  const submitButton = form ? form.querySelector("button[type='submit']") : null;
  const jobProgressBar = document.getElementById("job-progress-bar");
  const jobProgressLabel = document.getElementById("job-progress-label");
  const jobStatus = document.getElementById("job-status");
  const jobStage = document.getElementById("job-stage");
  const jobToken = document.getElementById("job-token");
  const jobLogBox = document.getElementById("job-log-box");
  const artifactBox = document.getElementById("job-artifact-box");
  const redFlagsList = document.getElementById("red-flags-list");
  const phaseTracker = document.getElementById("phase-tracker");
  const jobIdNode = document.getElementById("job-id");

  const summaryRiskScore = document.getElementById("summary-risk-score");
  const summaryRiskBand = document.getElementById("summary-risk-band");
  const summaryConfidence = document.getElementById("summary-confidence");
  const summaryHolders = document.getElementById("summary-holders");
  const summaryMarketCap = document.getElementById("summary-market-cap");
  const summaryLiquidity = document.getElementById("summary-liquidity");
  const summaryVolume24h = document.getElementById("summary-volume-24h");

  const stageOrder = ["queued", "fetching", "analyzing", "finalizing", "succeeded"];
  const stageProgressFloor = {
    queued: 4,
    fetching: 24,
    analyzing: 58,
    finalizing: 84,
    succeeded: 100,
    failed: 100,
    cancelled: 100,
  };
  const stageProgressCeiling = {
    queued: 12,
    fetching: 40,
    analyzing: 76,
    finalizing: 95,
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
    lastLogPayload: "",
    lastArtifactPayload: "",
    lastRedFlagsPayload: "",
    lastKnownStage: "",
    lastKnownStatus: "",
  };

  function clamp01(value) {
    return Math.max(0, Math.min(100, Number(value || 0)));
  }

  function setFeedback(message) {
    if (feedback) {
      feedback.textContent = String(message || "");
    }
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
    const reported = clamp01(job.progress);
    const floor = stageProgressFloor[stage] != null ? stageProgressFloor[stage] : reported;
    const ceiling = stageProgressCeiling[stage] != null ? stageProgressCeiling[stage] : 100;

    if (terminalStatuses.has(status)) {
      return 100;
    }

    let target = reported;
    if (!Number.isFinite(target) || target <= 0) {
      target = floor;
    }
    target = Math.max(target, floor);
    target = Math.min(target, ceiling);
    if (target < state.displayedProgress) {
      return state.displayedProgress;
    }
    return clamp01(target);
  }

  function animateProgressTo(nextProgress) {
    const target = clamp01(nextProgress);
    state.targetProgress = Math.max(state.targetProgress, target);
    if (state.animationFrame) {
      return;
    }

    const tick = function () {
      const delta = state.targetProgress - state.displayedProgress;
      if (Math.abs(delta) < 0.4) {
        state.displayedProgress = state.targetProgress;
      } else {
        state.displayedProgress += delta * 0.18;
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
    const currentIndex = Math.max(0, stageOrder.indexOf(normalizedStage));
    const nodes = phaseTracker.querySelectorAll("li[data-phase]");
    nodes.forEach(function (node) {
      const phaseName = String(node.getAttribute("data-phase") || "").trim().toLowerCase();
      const phaseIndex = stageOrder.indexOf(phaseName);
      node.classList.remove("done", "active", "pending", "failed");
      if (status === "failed") {
        if (phaseName === "finalizing" || phaseName === "succeeded") {
          node.classList.add("failed");
          return;
        }
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

  function renderLogs(events) {
    if (!jobLogBox) {
      return;
    }
    const ordered = Array.isArray(events) ? events.slice().reverse() : [];
    const nextPayload =
      ordered.length === 0
        ? "[queued] Waiting for worker updates..."
        : ordered
            .map(function (event) {
              const ts = String(event.created_at_utc || "");
              const stage = String(event.stage || "");
              const msg = String(event.message || event.event_type || "event");
              return "[" + ts + "] [" + stage + "] " + msg;
            })
            .join("\n");
    if (nextPayload !== state.lastLogPayload) {
      jobLogBox.textContent = nextPayload;
      state.lastLogPayload = nextPayload;
    }
  }

  function renderSummary(metadata) {
    const payload = metadata && typeof metadata === "object" ? metadata : {};
    const keyMetrics = payload.key_metrics && typeof payload.key_metrics === "object" ? payload.key_metrics : {};

    if (summaryRiskScore) {
      summaryRiskScore.textContent = String(payload.risk_score != null ? payload.risk_score : "-");
    }
    if (summaryRiskBand) {
      summaryRiskBand.textContent = String(payload.risk_band || "-");
    }
    if (summaryConfidence) {
      summaryConfidence.textContent =
        payload.confidence_pct != null ? String(payload.confidence_pct) + "%" : "-";
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
  }

  function renderRedFlags(metadata) {
    if (!redFlagsList) {
      return;
    }
    const flags = metadata && Array.isArray(metadata.red_flags) ? metadata.red_flags : [];
    const serialized = JSON.stringify(flags);
    if (serialized === state.lastRedFlagsPayload) {
      return;
    }
    state.lastRedFlagsPayload = serialized;
    redFlagsList.innerHTML = "";
    if (flags.length === 0) {
      const li = document.createElement("li");
      li.textContent = "No red flags detected in current snapshot.";
      redFlagsList.appendChild(li);
      return;
    }
    flags.forEach(function (flag) {
      const li = document.createElement("li");
      li.textContent = String(flag || "");
      redFlagsList.appendChild(li);
    });
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
    if (jobToken) {
      jobToken.innerHTML = "";
      const codeNode = document.createElement("code");
      codeNode.textContent = String(job.token_address || "");
      jobToken.appendChild(codeNode);
    }

    updatePhaseTracker(stage, status);
    animateProgressTo(computeTargetProgress(job));
    renderLogs(job.events);

    const artifacts = Array.isArray(job.artifacts) ? job.artifacts : [];
    const latestMetadata =
      artifacts.length > 0 && artifacts[0] && typeof artifacts[0].metadata === "object" ? artifacts[0].metadata : null;
    renderSummary(latestMetadata);
    renderRedFlags(latestMetadata);
    renderArtifactRaw(latestMetadata);

    return !terminalStatuses.has(status);
  }

  function scheduleNextPoll(isActive) {
    if (state.pollTimer) {
      window.clearTimeout(state.pollTimer);
      state.pollTimer = null;
    }
    const delay = isActive ? 1800 : 7000;
    state.pollTimer = window.setTimeout(pollJob, delay);
  }

  async function pollJob() {
    if (!activeJobId) {
      return;
    }
    try {
      const response = await fetch(
        "/api/v1/risk/jobs/" +
          encodeURIComponent(activeJobId) +
          "?events=1&artifacts=1&event_limit=120&artifact_limit=40",
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
      const active = renderJob(payload.job);
      scheduleNextPoll(active);
    } catch (_err) {
      scheduleNextPoll(true);
    }
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
      throw new Error(String(data.message || data.error || "create_job_failed"));
    }
    return data;
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
        const jobId = String(job.job_id || "").trim();
        if (!jobId) {
          throw new Error("missing_job_id");
        }
        window.location.href = "/live-assessment?job_id=" + encodeURIComponent(jobId);
      } catch (err) {
        setFeedback("Failed to create job: " + String((err && err.message) || err || "unknown_error"));
        if (submitButton) {
          submitButton.disabled = false;
        }
      }
    });
  }

  if (activeJobId) {
    pollJob();
  } else {
    updatePhaseTracker("queued", "queued");
  }
})();

