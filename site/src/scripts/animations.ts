/** Scroll-reveal: blur-to-clear elements as they enter viewport */
function initScrollReveal(): void {
  const prefersReduced = window.matchMedia(
    "(prefers-reduced-motion: reduce)"
  ).matches;

  if (prefersReduced) {
    document
      .querySelectorAll<HTMLElement>("[data-animate]")
      .forEach((el) => el.classList.add("visible"));
    return;
  }

  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          (entry.target as HTMLElement).classList.add("visible");
          observer.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.15, rootMargin: "0px 0px -40px 0px" }
  );

  document
    .querySelectorAll<HTMLElement>("[data-animate]")
    .forEach((el) => observer.observe(el));
}

/** Hero staggered blur-to-clear reveal on page load */
function initHeroReveal(): void {
  const prefersReduced = window.matchMedia(
    "(prefers-reduced-motion: reduce)"
  ).matches;

  const els = document.querySelectorAll<HTMLElement>("[data-hero-reveal]");
  if (els.length === 0) return;

  if (prefersReduced) {
    els.forEach((el) => el.classList.add("visible"));
    return;
  }

  els.forEach((el) => {
    const delay = parseInt(el.dataset.heroReveal || "0", 10);
    setTimeout(() => el.classList.add("visible"), delay);
  });
}


/** Cycle diagram: hover/focus updates description + highlights HowItWorks cards */
function initCycleDiagram(): void {
  const desc = document.getElementById("cycle-desc");
  if (!desc) return;

  const defaultText = "Hover or focus a node to see its role in the cycle.";

  const cardMap: Record<string, string> = {
    reduce: "knowledge-layer",
    reflect: "knowledge-layer",
    generate: "hypothesis-layer",
    tournament: "hypothesis-layer",
    evolve: "hypothesis-layer",
    "meta-review": "hypothesis-layer",
  };

  document.querySelectorAll<SVGGElement>(".cycle-node").forEach((node) => {
    const label = node.getAttribute("aria-label") || "";
    const nodeId = node.dataset.nodeId || "";
    const cardId = cardMap[nodeId];

    function highlight(on: boolean): void {
      desc!.textContent = on ? label : defaultText;
      if (cardId) {
        const card = document.getElementById(cardId);
        card?.classList.toggle("how-card-highlight", on);
      }
    }

    node.addEventListener("mouseenter", () => highlight(true));
    node.addEventListener("focus", () => highlight(true));
    node.addEventListener("mouseleave", () => highlight(false));
    node.addEventListener("blur", () => highlight(false));
  });
}

/** Nav: toggle scrolled state for transparent nav on landing page */
function initNavScroll(): void {
  const nav = document.querySelector<HTMLElement>(".nav-transparent");
  if (!nav) return;

  function update(): void {
    nav!.classList.toggle("nav-scrolled", window.scrollY > 40);
  }

  update();
  window.addEventListener("scroll", update, { passive: true });
}

/** Mobile menu toggle */
function initMobileMenu(): void {
  const toggle = document.getElementById("mobile-menu-toggle");
  const menu = document.getElementById("mobile-menu");
  const backdrop = document.getElementById("mobile-menu-backdrop");
  if (!toggle || !menu) return;

  function setOpen(open: boolean): void {
    menu!.classList.toggle("hidden", !open);
    backdrop?.classList.toggle("hidden", !open);
    toggle!.setAttribute("aria-expanded", String(open));
    toggle!.querySelector(".hamburger-icon")?.classList.toggle("hidden", open);
    toggle!.querySelector(".close-icon")?.classList.toggle("hidden", !open);
  }

  toggle.addEventListener("click", () => {
    const isOpen = toggle.getAttribute("aria-expanded") === "true";
    setOpen(!isOpen);
  });

  backdrop?.addEventListener("click", () => setOpen(false));

  menu.querySelectorAll(".mobile-menu-link").forEach((link) => {
    link.addEventListener("click", () => setOpen(false));
  });
}

// Init all systems
document.addEventListener("DOMContentLoaded", () => {
  initHeroReveal();
  initScrollReveal();

  initCycleDiagram();
  initNavScroll();
  initMobileMenu();
});
