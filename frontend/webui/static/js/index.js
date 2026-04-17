document.addEventListener("DOMContentLoaded", () => {
  const jobsBody = document.getElementById("jobs-body");
  const jobCount = document.getElementById("job-count");
  const activeCount = document.getElementById("active-count");
  const locale = window.__ui.locale || "ko";

  function renderJobs(jobs) {
    jobsBody.innerHTML = "";
    let running = 0;
    for (const job of jobs) {
      if ((job.status || "").toLowerCase() === "running") {
        running += 1;
      }
      const row = document.createElement("tr");
      row.dataset.status = job.status || "";
      const shortId = (job.id || "").slice(0, 8);
      const statusCell = document.createElement("td");
      const badge = document.createElement("span");
      badge.className = "badge";
      badge.dataset.tone = window.badgeToneForStatus(job.status);
      badge.textContent = window.t(`badge.${String(job.status || "").toLowerCase()}`, job.status || "");
      for (const value of [shortId, job.type || ""]) {
        const cell = document.createElement("td");
        cell.textContent = value;
        row.appendChild(cell);
      }
      statusCell.appendChild(badge);
      row.appendChild(statusCell);
      const updatedCell = document.createElement("td");
      updatedCell.textContent = window.formatHumanDateTime(job.updatedAt);
      row.appendChild(updatedCell);
      const openCell = document.createElement("td");
      const link = document.createElement("a");
      link.href = `/backend/jobs/${encodeURIComponent(job.id)}`;
      link.textContent = "view";
      openCell.appendChild(link);
      row.appendChild(openCell);
      jobsBody.appendChild(row);
    }
    jobCount.textContent = String(jobs.length);
    activeCount.textContent = String(running);
  }

  async function fetchJobs() {
    try {
      const response = await fetch(`/backend/jobs?lang=${encodeURIComponent(locale)}`, { cache: "no-store" });
      if (!response.ok) {
        return;
      }
      const payload = await response.json();
      renderJobs(payload.jobs || []);
    } catch (_) {
    }
  }

  fetchJobs();
  setInterval(fetchJobs, 3000);
});
