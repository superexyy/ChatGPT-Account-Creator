document.addEventListener("DOMContentLoaded", () => {
  const bootstrapEl = document.getElementById("job-bootstrap");
  if (!bootstrapEl) {
    return;
  }

  const bootstrap = JSON.parse(bootstrapEl.textContent);
  const jobId = bootstrap.job_id;
  const locale = window.__ui.locale || "ko";
  let pollTimer = null;

  function formatResult(value) {
    if (value === null || value === undefined) {
      return "null";
    }
    return JSON.stringify(value, null, 2);
  }

  function updateJobView(payload) {
    const job = payload.job;
    const progress = payload.progress;
    document.getElementById("job-status").textContent = job.status;
    document.getElementById("job-status-badge").textContent = job.status;
    document.getElementById("job-status-badge").dataset.tone = window.badgeToneForStatus(job.status);
    document.getElementById("account-line").textContent = progress.account_line;
    document.getElementById("email-line").textContent = progress.current_email || "-";
    document.getElementById("step-line").textContent = progress.step_line;
    document.getElementById("status-text").textContent = progress.status_text;
    document.getElementById("progress-percent").textContent = `${progress.progress_percent}%`;
    document.getElementById("progress-percent-label").textContent = `${progress.progress_percent}%`;
    document.getElementById("progress-bar").style.width = `${progress.progress_percent}%`;
    document.getElementById("progress-bar").dataset.status = job.status;
    document.getElementById("progress-bar").classList.toggle("running", job.status === "running");
    document.getElementById("job-updated").textContent = window.formatHumanDateTime(job.updatedAt);
    document.getElementById("job-error").textContent = job.error || "none";
    document.getElementById("job-result").textContent = formatResult(job.result);

    if (!["pending", "running"].includes(job.status) && pollTimer) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
  }

  async function fetchJob() {
    try {
      const response = await fetch(`/backend/jobs/${jobId}/data?lang=${encodeURIComponent(locale)}`, { cache: "no-store" });
      if (!response.ok) {
        return;
      }
      updateJobView(await response.json());
    } catch (_) {
    }
  }

  const progressBar = document.getElementById("progress-bar");
  progressBar.style.width = `${progressBar.dataset.progressPercent || 0}%`;
  progressBar.classList.toggle("running", (progressBar.dataset.status || "") === "running");

  if (["pending", "running"].includes(bootstrap.status)) {
    pollTimer = setInterval(fetchJob, 2000);
    fetchJob();
  }
});
