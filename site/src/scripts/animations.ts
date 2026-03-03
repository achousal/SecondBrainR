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

/** Ambient graph canvas in the hero background */
function initGraphCanvas(): void {
  const canvas = document.getElementById("graph-canvas") as HTMLCanvasElement;
  if (!canvas) return;

  const ctx = canvas.getContext("2d");
  if (!ctx) return;

  const prefersReduced = window.matchMedia(
    "(prefers-reduced-motion: reduce)"
  ).matches;

  const ACCENT = "#d4a24e";
  const NODE_COUNT = 40;
  const EDGE_DISTANCE = 150;

  interface Node {
    x: number;
    y: number;
    vx: number;
    vy: number;
    r: number;
  }

  let nodes: Node[] = [];
  let w = 0;
  let h = 0;

  function resize(): void {
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    w = rect.width;
    h = rect.height;
    canvas.width = w * dpr;
    canvas.height = h * dpr;
    ctx!.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  function seed(): void {
    nodes = Array.from({ length: NODE_COUNT }, () => ({
      x: Math.random() * w,
      y: Math.random() * h,
      vx: (Math.random() - 0.5) * 0.3,
      vy: (Math.random() - 0.5) * 0.3,
      r: Math.random() * 1.5 + 1,
    }));
  }

  function draw(): void {
    ctx!.clearRect(0, 0, w, h);

    // edges
    ctx!.strokeStyle = ACCENT;
    ctx!.lineWidth = 0.5;
    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        const dx = nodes[i].x - nodes[j].x;
        const dy = nodes[i].y - nodes[j].y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < EDGE_DISTANCE) {
          ctx!.globalAlpha = (1 - dist / EDGE_DISTANCE) * 0.15;
          ctx!.beginPath();
          ctx!.moveTo(nodes[i].x, nodes[i].y);
          ctx!.lineTo(nodes[j].x, nodes[j].y);
          ctx!.stroke();
        }
      }
    }

    // nodes
    ctx!.fillStyle = ACCENT;
    ctx!.globalAlpha = 0.4;
    for (const node of nodes) {
      ctx!.beginPath();
      ctx!.arc(node.x, node.y, node.r, 0, Math.PI * 2);
      ctx!.fill();
    }
    ctx!.globalAlpha = 1;
  }

  function update(): void {
    for (const node of nodes) {
      node.x += node.vx;
      node.y += node.vy;
      if (node.x < 0 || node.x > w) node.vx *= -1;
      if (node.y < 0 || node.y > h) node.vy *= -1;
    }
  }

  function loop(): void {
    update();
    draw();
    requestAnimationFrame(loop);
  }

  resize();
  seed();

  if (prefersReduced) {
    draw();
  } else {
    loop();
  }

  window.addEventListener("resize", () => {
    resize();
    if (prefersReduced) draw();
  });
}

/** Cycle diagram: hover/focus updates description */
function initCycleDiagram(): void {
  const desc = document.getElementById("cycle-desc");
  if (!desc) return;

  const defaultText = "Hover or focus a node to see its role in the cycle.";

  document.querySelectorAll<SVGGElement>(".cycle-node").forEach((node) => {
    const label = node.getAttribute("aria-label") || "";

    node.addEventListener("mouseenter", () => {
      desc.textContent = label;
    });
    node.addEventListener("focus", () => {
      desc.textContent = label;
    });
    node.addEventListener("mouseleave", () => {
      desc.textContent = defaultText;
    });
    node.addEventListener("blur", () => {
      desc.textContent = defaultText;
    });
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

// Init all systems
document.addEventListener("DOMContentLoaded", () => {
  initHeroReveal();
  initScrollReveal();
  initGraphCanvas();
  initCycleDiagram();
  initNavScroll();
});
