window.__ui = window.__ui || {};

window.formatHumanDateTime = function(value) {
  if (!value) {
    return "-";
  }
  const date = new Date(String(value));
  if (Number.isNaN(date.getTime())) {
    return String(value);
  }
  return new Intl.DateTimeFormat("en-CA", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
    timeZone: "Asia/Seoul",
  }).format(date).replace(",", "");
};

window.badgeToneForStatus = function(status) {
  const normalized = String(status || "").toLowerCase();
  if (["completed"].includes(normalized)) return "completed";
  if (["failed", "error"].includes(normalized)) return "failed";
  if (["pending", "queued", "deleted", "cleared"].includes(normalized)) return "pending";
  if (["running", "active"].includes(normalized)) return "running";
  return "info";
};

window.t = function(key, fallback = "") {
  const translations = window.__ui.translations || {};
  const fallbackTable = window.__ui.fallback || {};
  const locale = window.__ui.locale || "ko";
  return translations[key] ?? fallbackTable[key] ?? fallback ?? key;
};

window.setTheme = function(theme) {
  const resolved = theme === "dark" ? "dark" : "light";
  document.documentElement.dataset.theme = resolved;
  localStorage.setItem("theme", resolved);
  const toggle = document.getElementById("theme-toggle");
  if (toggle) {
    toggle.textContent = resolved === "dark" ? "Light mode" : "Dark mode";
  }
};

document.addEventListener("DOMContentLoaded", () => {
  const storedTheme = localStorage.getItem("theme");
  const preferredDark = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
  window.setTheme(storedTheme || (preferredDark ? "dark" : "light"));

  const current = document.body.dataset.page;
  const nav = document.querySelectorAll("[data-nav]");
  nav.forEach((link) => {
    if (link.dataset.nav === current) {
      link.classList.add("active");
    }
  });

  const toggle = document.getElementById("theme-toggle");
  if (toggle) {
    toggle.addEventListener("click", () => {
      const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
      window.setTheme(next);
    });
  }
});
