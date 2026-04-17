document.addEventListener("DOMContentLoaded", () => {
  const accountState = {
    search: "",
    codex: "all",
    sort: "newest",
  };

  const accountsBody = document.getElementById("accounts-body");
  const accountCount = document.getElementById("account-count");
  const codexCount = document.getElementById("codex-count");
  const visibleCount = document.getElementById("account-visible");
  const emptyState = document.getElementById("accounts-empty");
  const searchInput = document.getElementById("account-search");
  const codexSelect = document.getElementById("account-status");
  const sortSelect = document.getElementById("account-sort");
  const resetButton = document.getElementById("account-reset");
  const rows = Array.from(accountsBody.querySelectorAll("tr"));

  function normalized(value) {
    return String(value || "").trim().toLowerCase();
  }

  function compareRows(a, b) {
    if (accountState.sort === "email") {
      return normalized(a.dataset.email).localeCompare(normalized(b.dataset.email));
    }
    if (accountState.sort === "name") {
      return normalized(a.dataset.name).localeCompare(normalized(b.dataset.name));
    }
    const aTime = new Date(a.dataset.created || 0).getTime();
    const bTime = new Date(b.dataset.created || 0).getTime();
    return accountState.sort === "oldest" ? aTime - bTime : bTime - aTime;
  }

  function matchesRow(row) {
    const query = accountState.search;
    const blob = [row.dataset.email, row.dataset.name, row.dataset.userId].map(normalized).join(" ");
    const codex = normalized(row.dataset.codex);
    if (query && !blob.includes(query)) return false;
    if (accountState.codex === "enabled" && codex !== "true") return false;
    if (accountState.codex === "disabled" && codex !== "false") return false;
    return true;
  }

  function renderAccounts() {
    const visible = rows.slice().sort(compareRows).filter(matchesRow);
    accountsBody.innerHTML = "";
    visible.forEach((row) => accountsBody.appendChild(row));
    visibleCount.textContent = String(visible.length);
    emptyState.style.display = visible.length ? "none" : "block";
    accountCount.textContent = String(rows.length);
    codexCount.textContent = String(rows.filter((row) => normalized(row.dataset.codex) === "true").length);
  }

  searchInput.addEventListener("input", (event) => {
    accountState.search = normalized(event.target.value);
    renderAccounts();
  });
  codexSelect.addEventListener("change", (event) => {
    accountState.codex = event.target.value;
    renderAccounts();
  });
  sortSelect.addEventListener("change", (event) => {
    accountState.sort = event.target.value;
    renderAccounts();
  });
  resetButton.addEventListener("click", () => {
    searchInput.value = "";
    codexSelect.value = "all";
    sortSelect.value = "newest";
    accountState.search = "";
    accountState.codex = "all";
    accountState.sort = "newest";
    renderAccounts();
  });

  renderAccounts();
});
