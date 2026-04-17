document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("account-verify-form");
  const button = document.getElementById("account-verify-button");
  const statusBadge = document.getElementById("verify-status-badge");
  const accountLine = document.getElementById("verify-account-line");
  const emailLine = document.getElementById("verify-email-line");
  const stepLine = document.getElementById("verify-step-line");
  const statusText = document.getElementById("verify-status-text");
  const progressLabel = document.getElementById("verify-progress-label");
  const progressBar = document.getElementById("verify-progress-bar");
  const logsEl = document.getElementById("verify-logs");
  const resultEl = document.getElementById("verify-result");

  if (!form || !button || !statusBadge || !accountLine || !emailLine || !stepLine || !statusText || !progressLabel || !progressBar || !logsEl || !resultEl) {
    return;
  }

  const locale = window.__ui.locale || "ko";
  let pollTimer = null;
  let reloadTimer = null;
  let activeJobId = null;

  function setBadge(status) {
    const normalized = String(status || "").toLowerCase();
    statusBadge.textContent = normalized || "idle";
    statusBadge.dataset.tone = window.badgeToneForStatus(normalized === "idle" ? "pending" : normalized);
  }

  function setLogs(logs) {
    if (!Array.isArray(logs) || !logs.length) {
      logsEl.textContent = "no logs";
      return;
    }
    logsEl.textContent = logs
      .slice(-20)
      .map((entry) => `${window.formatHumanDateTime(entry.at)} ${entry.message}`)
      .join("\n");
  }

  function setResult(result) {
    try {
      resultEl.textContent = JSON.stringify(result, null, 2);
    } catch (_) {
      resultEl.textContent = String(result || "null");
    }
  }

  function updateProgress(progress) {
    accountLine.textContent = progress.account_line || accountLine.textContent;
    emailLine.textContent = progress.current_email || emailLine.textContent;
    stepLine.textContent = progress.step_line || stepLine.textContent;
    statusText.textContent = progress.status_text || statusText.textContent;
    progressLabel.textContent = `${progress.progress_percent ?? 0}%`;
    progressBar.style.width = `${progress.progress_percent ?? 0}%`;
    progressBar.classList.toggle("running", progress.progress_percent > 0 && progress.progress_percent < 100);
  }

  function scheduleReload() {
    if (reloadTimer) {
      return;
    }
    reloadTimer = window.setTimeout(() => {
      window.location.reload();
    }, 700);
  }

  function stopPolling() {
    if (pollTimer) {
      window.clearInterval(pollTimer);
      pollTimer = null;
    }
  }

  async function fetchJob() {
    if (!activeJobId) {
      return;
    }
    try {
      const response = await fetch(`/backend/jobs/${activeJobId}/data?lang=${encodeURIComponent(locale)}`, {
        cache: "no-store",
        headers: { Accept: "application/json" },
      });
      if (!response.ok) {
        return;
      }
      const payload = await response.json();
      const job = payload.job || {};
      const progress = payload.progress || {};
      setBadge(job.status || "idle");
      updateProgress(progress);
      setLogs(job.logs || []);
      setResult(job.result);
      if (!["pending", "running"].includes(String(job.status || "").toLowerCase())) {
        stopPolling();
        scheduleReload();
      }
    } catch (_) {
    }
  }

  async function startVerification(event) {
    event.preventDefault();
    if (activeJobId) {
      return;
    }

    const formData = new FormData(form);
    button.disabled = true;
    button.textContent = window.t("badge.running", "Running");
    setBadge("running");
    statusText.textContent = "검증 작업을 시작하는 중입니다.";
    logsEl.textContent = "starting...";
    progressLabel.textContent = "0%";
    progressBar.style.width = "0%";
    progressBar.classList.add("running");

    try {
      const response = await fetch(form.action, {
        method: "POST",
        headers: {
          "X-Requested-With": "XMLHttpRequest",
          Accept: "application/json",
        },
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`verify request failed: ${response.status}`);
      }

      const payload = await response.json();
      activeJobId = payload.jobId;
      logsEl.textContent = `job ${activeJobId} started`;
      updateProgress({
        account_line: accountLine.textContent,
        current_email: emailLine.textContent,
        step_line: "작업을 시작했습니다.",
        status_text: "백그라운드 작업을 기다리는 중입니다.",
        progress_percent: 5,
      });
      pollTimer = window.setInterval(fetchJob, 2000);
      await fetchJob();
    } catch (err) {
      setBadge("failed");
      statusText.textContent = err && err.message ? err.message : "검증 시작 실패";
      logsEl.textContent = String(err && err.message ? err.message : err);
      button.disabled = false;
      button.textContent = window.t("accounts.action.verify", "Verify by email");
      stopPolling();
      activeJobId = null;
      progressBar.classList.remove("running");
    }
  }

  form.addEventListener("submit", startVerification);
  setBadge("idle");
  if (!resultEl.textContent.trim()) {
    resultEl.textContent = "null";
  }
});
