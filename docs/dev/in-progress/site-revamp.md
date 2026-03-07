# Site Revamp Plan

Implementation plan for modernizing the EngramR development site.
12 work items grouped into 4 phases by dependency and impact.

## Phase 1 -- Foundation (blocking everything else)

### 1.1 Mobile Navigation
**Files**: `Nav.astro`, `global.css`, `animations.ts`
**Steps**:
- Add hamburger icon (SVG, hidden above md breakpoint)
- Add slide-down mobile menu panel with backdrop
- Wire open/close toggle in animations.ts
- Add version badge pill next to logo (read from package.json or hardcode)
- Test at 320px, 375px, 768px breakpoints

**Acceptance**: nav links accessible on all screen sizes, menu closes on link click and outside tap

### 1.2 Copy-to-Clipboard on Code Blocks
**Files**: new `src/scripts/clipboard.ts`, `global.css`
**Steps**:
- Script: query all `pre > code` blocks, inject a copy button (top-right, absolute positioned)
- Button shows "Copied" state for 1.5s then reverts
- Style: subtle icon, visible on hover/focus of the `pre` block
- Apply to both landing page code blocks and doc-prose code blocks

**Acceptance**: every code block on every page has a working copy button

### 1.3 404 Page
**Files**: new `src/pages/404.astro`
**Steps**:
- Use Base layout + Nav
- Center message: "Lost in the graph" + subtext
- Links to Home and Docs
- Minimal -- no heavy components

**Acceptance**: navigating to a bad URL shows the 404 page with working links

---

## Phase 2 -- Hero and First Impression

### 2.1 Hero Visual -- Vault Structure Animation
**Files**: `Hero.astro`, `animations.ts` (replace `initGraphCanvas`)
**Steps**:
- Remove canvas element and `initGraphCanvas` function
- Replace with a styled `<div>` containing a monospace vault tree:
  ```
  notes/
    plasma p-tau217 achieves AUC 94-97...
    sex differences in kdm5c and kdm6a...
  _research/hypotheses/
    H-007: sFLT1 axonogenesis inhibition...
  inbox/
    new-paper.pdf
  ```
- Animate: lines appear sequentially (staggered fade-in, 80ms apart)
- After tree renders, draw 2-3 wiki-link edges (CSS animated dashed lines connecting claim names) to show the graph concept
- Keep existing hero text + CTA buttons unchanged
- Add gradient overlay so tree fades toward edges
- Respect prefers-reduced-motion

**Acceptance**: hero shows a product-specific visualization, not generic particles. Loads fast, no layout shift.

### 2.2 Problem Section -- Typographic Callout
**Files**: `Problem.astro`
**Steps**:
- Extract the key stat into a large typographic element above the paragraphs:
  `"10 good ideas compete for 3 experimental slots"`
  Style: font-display, text-2xl md:text-3xl, text-text, with accent color on the numbers
- Keep the three paragraphs below, unchanged
- Add a subtle top border or accent bar to separate from hero

**Acceptance**: section has visual hierarchy beyond uniform paragraphs

---

## Phase 3 -- Content Sections

### 3.1 Core Concepts Section (replaces VocabBridge)
**Files**: replace `VocabBridge.astro` with new `CoreConcepts.astro`, update `index.astro` import
**Steps**:
- Define 6 concepts as data array:
  - Atomic Claims, Wiki Links, Topic Maps, Hypothesis Tournaments, Elo Rankings, Provenance Chain
- Render as 3x2 grid (md) / 2x3 (sm) / stack (mobile)
- Each card: small inline SVG icon + term (font-display semibold) + one-sentence definition + docs link
- Cards use existing card-shadow style, border-border, hover:border-accent-dim
- Delete VocabBridge.astro after replacement

**Acceptance**: 6 concept cards render correctly at all breakpoints, links point to valid doc pages

### 3.2 Morning Timeline Polish
**Files**: `Morning.astro`, `global.css`
**Steps**:
- Add role icons: 3 small SVGs (beaker for tech, book for postdoc, circuit/gear for reactor)
- Display icon next to the event title or actor name
- Add subtle background tint per event type:
  - Observation/quote events: faint blue-tinted left border
  - Tournament/evolution events: faint gold-tinted left border
  - Default: current accent-dim border
- Add scroll-linked progress: CSS gradient on the timeline border that fills as user scrolls (use IntersectionObserver per event to toggle a class that extends the gradient)

**Acceptance**: timeline has visual variety, icons render, progress fills on scroll

### 3.3 How It Works -- Responsive Card Layout
**Files**: `HowItWorks.astro`, `global.css`
**Steps**:
- Wrap the three `<details>` elements in a container
- Above md: render as 3 side-by-side cards (always open, remove details/summary)
  - Use a `<template>` or conditional Astro rendering: `<details>` on mobile, `<div>` on desktop
  - Simpler approach: keep `<details>` but add CSS `details[open]` forced on desktop via media query and `pointer-events: none` on summary chevron
- Add data attributes linking each card to cycle diagram nodes
- Wire: hovering a cycle-node highlights the corresponding card border (add/remove a class via JS)

**Acceptance**: cards always visible on desktop, collapsible on mobile, diagram-card hover link works

### 3.4 Scaling Section -- Progression Indicators
**Files**: `Scaling.astro`
**Steps**:
- Add tier icons at top of each card:
  - Solo: single-user SVG icon
  - Team: group SVG icon
  - Network: connected-nodes SVG icon
- Add connecting arrows between cards on md+ (CSS `::after` pseudo-elements with arrow character or thin SVG)
- Add "advanced" dashed border treatment to the Network card

**Acceptance**: visual progression reads left-to-right on desktop, icons render, arrows visible on md+

### 3.5 Get Started -- Streamline
**Files**: `GetStarted.astro`
**Steps**:
- Wrap prerequisites table in a `<details>` element, collapsed by default, summary: "Prerequisites"
- Add terminal mockup frame around each code block:
  - Wrapper div with rounded top, 3 dot circles (red/yellow/green, 8px), dark bg
  - Code block inside
- Copy buttons come from Phase 1.2 (already done by this phase)

**Acceptance**: prerequisites hidden by default, terminal frames render cleanly, steps are scannable

---

## Phase 4 -- Polish and Pages

### 4.1 Footer Restructure
**Files**: `Footer.astro`
**Steps**:
- Reorganize links into 3 columns:
  - Product: Docs, About, GitHub
  - Ecosystem: Ars Contexta, Claude Code, Obsidian
  - Community: Discussions, Issues (link to GitHub issues/discussions)
- Add "Built with Astro + Tailwind" small text at bottom
- Keep the tagline

**Acceptance**: footer has columnar layout on md+, stacks on mobile

### 4.2 About Page -- Visual Breaks
**Files**: `about.astro`
**Steps**:
- Add section dividers between major headings (subtle `<hr>` with accent dot or decorative element)
- Pull "Administration" subsections (Writing aims, Allocating resources, New direction) into card components matching the PI/Evaluator panel style from GetStarted
- Add a "Who is this for?" callout box near the top: 3 short bullets (researchers, PIs, developers)
- Keep all existing copy unchanged

**Acceptance**: about page has visual rhythm, not a monolithic text block

### 4.3 Docs Index -- Search and Reading Time
**Files**: `docs/index.astro`, new `src/scripts/doc-search.ts`
**Steps**:
- Add estimated reading time to each doc card (compute from markdown word count at build time via Astro content collection, assume 200 wpm)
- Add a search input at the top of the docs index:
  - Client-side fuzzy match over doc titles + descriptions
  - Filter the tier card grids live as user types
  - Use a simple substring or includes match (no external lib needed)
  - Show "No results" state

**Acceptance**: reading times display on cards, search filters docs in real time

---

## Dependency Graph

```
Phase 1 (foundation)
  1.1 Mobile Nav
  1.2 Clipboard        -- used by 3.5
  1.3 404 Page

Phase 2 (hero + first impression) -- after 1.1
  2.1 Hero Visual
  2.2 Problem Callout

Phase 3 (content) -- after 1.2
  3.1 Core Concepts    -- after 2.2 (section ordering)
  3.2 Morning Timeline
  3.3 How It Works
  3.4 Scaling
  3.5 Get Started      -- depends on 1.2

Phase 4 (polish) -- after Phase 3
  4.1 Footer
  4.2 About Page
  4.3 Docs Search
```

## Files Created / Modified Summary

| Item | New Files | Modified Files |
|------|-----------|----------------|
| 1.1 | -- | Nav.astro, global.css, animations.ts |
| 1.2 | clipboard.ts | global.css |
| 1.3 | 404.astro | -- |
| 2.1 | -- | Hero.astro, animations.ts |
| 2.2 | -- | Problem.astro |
| 3.1 | CoreConcepts.astro | index.astro (import swap) |
| 3.2 | -- | Morning.astro, global.css |
| 3.3 | -- | HowItWorks.astro, global.css, animations.ts |
| 3.4 | -- | Scaling.astro, global.css |
| 3.5 | -- | GetStarted.astro |
| 4.1 | -- | Footer.astro |
| 4.2 | -- | about.astro |
| 4.3 | doc-search.ts | docs/index.astro |

**Deleted**: VocabBridge.astro (replaced by CoreConcepts.astro in 3.1)

## Testing Strategy

- After each item: `npm run build` in site/ to verify no build errors
- Visual review at 320px, 768px, 1280px, 1920px
- Check prefers-reduced-motion for all animation changes
- Lighthouse audit after Phase 4 complete (target: 90+ performance, 100 accessibility)

Unresolved questions: none.
