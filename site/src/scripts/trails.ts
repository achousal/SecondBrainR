/** Trail selection: stores role in sessionStorage and toggles DOM state. */

const STORAGE_KEY = "engramr-trail";

type Trail = "researcher" | "evaluator" | "developer";

function getTrail(): Trail | null {
  try {
    const stored = sessionStorage.getItem(STORAGE_KEY);
    if (stored === "researcher" || stored === "evaluator" || stored === "developer") {
      return stored;
    }
  } catch {
    // sessionStorage unavailable
  }
  return null;
}

function setTrail(trail: Trail): void {
  try {
    sessionStorage.setItem(STORAGE_KEY, trail);
  } catch {
    // sessionStorage unavailable
  }
}

function applyTrail(trail: Trail | null): void {
  // Update trail selector buttons
  document.querySelectorAll<HTMLButtonElement>(".trail-btn").forEach((btn) => {
    const isActive = btn.dataset.trail === trail;
    btn.classList.toggle("border-accent", isActive);
    btn.classList.toggle("text-accent", isActive);
    btn.classList.toggle("border-border", !isActive);
    btn.classList.toggle("text-text-muted", !isActive);
  });

  // Update trail-conditioned elements
  document.querySelectorAll<HTMLElement>("[data-trail]").forEach((el) => {
    if (el.classList.contains("trail-btn")) return; // skip selector buttons
    const elTrail = el.dataset.trail;
    const isMatch = elTrail === trail;
    el.classList.toggle("trail-active", isMatch);
  });

  // Update role tabs in GetStarted
  document.querySelectorAll<HTMLElement>("[data-role-tab]").forEach((tab) => {
    const isActive = tab.dataset.roleTab === trail;
    tab.classList.toggle("border-accent", isActive);
    tab.classList.toggle("text-accent", isActive);
    tab.classList.toggle("border-transparent", !isActive);
    tab.classList.toggle("text-text-muted", !isActive);
  });

  document.querySelectorAll<HTMLElement>("[data-role-panel]").forEach((panel) => {
    const isActive = panel.dataset.rolePanel === trail;
    panel.classList.toggle("hidden", !isActive);
  });
}

function init(): void {
  const stored = getTrail();
  if (stored) {
    applyTrail(stored);
  }

  // Trail selector clicks
  document.querySelectorAll<HTMLButtonElement>(".trail-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const trail = btn.dataset.trail as Trail;
      setTrail(trail);
      applyTrail(trail);
    });
  });

  // Role tab clicks
  document.querySelectorAll<HTMLElement>("[data-role-tab]").forEach((tab) => {
    tab.addEventListener("click", () => {
      const trail = tab.dataset.roleTab as Trail;
      setTrail(trail);
      applyTrail(trail);
    });
  });

  // Scaling card clicks -- select trail and scroll to Get Started
  document.querySelectorAll<HTMLButtonElement>(".scaling-card").forEach((card) => {
    card.addEventListener("click", () => {
      const trail = card.dataset.trail as Trail;
      setTrail(trail);
      applyTrail(trail);
      const target = document.getElementById("get-started");
      if (target) {
        target.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    });
  });

  // Hash navigation: open targeted <details> elements
  function openHashTarget(): void {
    const hash = location.hash.slice(1);
    if (!hash) return;
    const target = document.getElementById(hash);
    if (target instanceof HTMLDetailsElement) {
      target.open = true;
      target.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }

  openHashTarget();
  window.addEventListener("hashchange", openHashTarget);
}

document.addEventListener("DOMContentLoaded", init);
