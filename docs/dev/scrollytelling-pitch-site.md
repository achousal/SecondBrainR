---
description: "Development plan for the EngramR scrollytelling pitch website -- an interactive, scroll-driven narrative that replaces slide decks for PI outreach."
type: development
status: planned
created: 2026-03-05
---

# Scrollytelling Pitch Site

Interactive scroll-driven website that pitches EngramR to PIs. Works live (presenter scrolls during talks), async (send the URL), and as a permanent landing page. Deploys to GitHub Pages.

---

## Why Not Slides

PIs see 50 decks a month. A scrollytelling site:
- IS the product signal -- it feels like software, not a lecture
- Self-distributes -- every PI who likes it forwards the URL
- Works in every context -- live talk, email follow-up, conference QR code, grant supplement link
- Lives permanently at a URL; no "can you share the slides?"
- Updates incrementally -- change content, redeploy, done

---

## Site Architecture

Single-page app. Each "section" is a scroll-triggered scene. Content is the existing pitch-and-business-plan.md rewritten for visual narrative.

### Scroll Sections

| # | Section | Scroll Trigger | Visual |
|---|---------|---------------|--------|
| 1 | Hook | Entry | Animated text: "Your postdoc reads 200 papers. Then they leave." Fade to black. |
| 2 | Problem Cascade | Scroll down | Four problem cards appear sequentially with simple icons. Each fades in on scroll position. |
| 3 | The Graph Grows | Scroll continues | Animated knowledge graph: nodes appear one-by-one, edges draw themselves. Starts sparse, becomes dense. |
| 4 | Pipeline Animation | Scroll continues | Horizontal pipeline: inbox -> /reduce -> claims -> /generate -> tournament -> leaderboard. Each step activates on scroll. |
| 5 | Timeline | Scroll continues | "Day 1... Week 1... Month 1... Year 1" -- the graph densifies at each stage. Counter shows claim count growing. |
| 6 | Comparison | Scroll continues | Clean table: EngramR vs Zotero vs Notion vs Elicit vs Google Co-Scientist. Checkmarks animate in. |
| 7 | Cost Calculator | Scroll continues | Interactive slider: lab size (3-15 people) -> monthly cost ($150-$500). Compare to: "one failed experiment costs more." |
| 8 | Adoption Gradient | Scroll continues | Four-step staircase: Observer -> Contributor -> Analyst -> Director. Each step lights up on scroll. |
| 9 | Federation | Scroll continues | Two vault icons connect via a bridge. Claims flow between them. "Your data stays local. Only insights cross boundaries." |
| 10 | Ask + CTA | Final section | Three cards: Pilot Labs, Co-Development, Institutional Partners. Each with a contact action. GitHub link. |

### Optional Enhancement: Embedded Terminal Recording

Between sections 4 and 5, embed an asciinema recording (or MP4) of a real EngramR session: paper drops into inbox -> `/reduce` -> claims appear -> `/generate` -> hypothesis -> leaderboard updates. 60-90 seconds, sped up 2x. Auto-plays when scrolled into view.

---

## Tech Stack

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Framework | **Astro** (static site generator) | Markdown-native, ships zero JS by default, islands architecture for interactive bits |
| Scroll engine | **GSAP ScrollTrigger** | Industry standard, handles pinning and timeline scrubbing, well-documented |
| Graph animation | **D3.js** (force-directed) or **Canvas/SVG** with GSAP | D3 for the knowledge graph scene; GSAP for simpler motion |
| Styling | **Tailwind CSS** | Utility-first, fast prototyping, consistent spacing/typography |
| Terminal embed | **asciinema-player** (web component) or MP4 fallback | Lightweight, no server dependency |
| Deployment | **GitHub Pages** via Astro adapter | Free, already in our workflow, custom domain ready |
| Cost slider | Vanilla JS + CSS | Too simple to need a framework |

### Why Astro over alternatives

- **vs Reveal.js**: Reveal is slide-shaped. We want scroll-shaped. Different interaction model.
- **vs plain HTML**: Astro gives us component reuse, markdown content loading, and build optimization for free.
- **vs Next.js/Nuxt**: Overkill. No server-side logic, no API routes, no auth. Static is correct.
- **vs Svelte/SvelteKit**: Good alternative. Astro chosen because it can use Svelte islands if needed, but defaults to zero-JS static.

---

## Content Adaptation

The pitch-and-business-plan.md content maps to sections but needs rewriting for visual brevity:

| Source Section | Site Section | Adaptation |
|---------------|-------------|------------|
| Elevator Pitch | Hook (#1) | Compress to one sentence + subline |
| The Problem (5 subsections) | Problem Cascade (#2) | One headline + one sentence per problem. Icon per card. |
| The Solution (3 subsections) | Graph Grows (#3) + Pipeline (#4) | Visual, not text. Animation carries the explanation. |
| What It Looks Like in Practice | Timeline (#5) | Four stages, minimal text, graph densification visual |
| Comparison Table | Comparison (#6) | Direct table lift, animated checkmarks |
| Cost Structure | Cost Calculator (#7) | Interactive slider replaces static text |
| Adoption Path | Adoption Gradient (#8) | Staircase visual replaces numbered list |
| Multi-Lab Federation | Federation (#9) | Diagram replaces paragraphs |
| Ask | CTA (#10) | Action cards with contact links |

**Copy rule:** No paragraph on the site exceeds 2 sentences. If it takes more words, it needs a better visual.

---

## Design Principles

1. **Dark background, light text.** Research tools look serious on dark backgrounds. Avoid startup-bright aesthetics.
2. **Monospace for system output.** Anything that represents EngramR output uses monospace -- reinforces "this is real software."
3. **Minimal color palette.** White text, one accent color (teal or amber), graph nodes in accent color. No gradients, no purple (per coding style rules).
4. **Typography hierarchy.** Large serif for headlines (academic tone), clean sans-serif for body, monospace for system elements.
5. **No stock photos.** Every visual is either a diagram, an animation, or a screenshot of the actual system.
6. **Mobile-responsive.** Scroll interactions degrade to sequential fade-ins on mobile. Graph animation becomes a static image below 768px.

---

## Graph Animation Spec

The centerpiece: a knowledge graph that grows as the user scrolls.

### States

| Scroll % (of section) | Graph State | Label |
|----------------------|-------------|-------|
| 0-20% | 3 disconnected nodes | "Scattered observations" |
| 20-40% | 10 nodes, sparse edges | "Claims extracted" |
| 40-60% | 25 nodes, clusters forming | "Connections found" |
| 60-80% | 40 nodes, dense clusters, bridge edges | "Hypotheses generated" |
| 80-100% | Full graph + highlighted top-3 nodes (leaderboard) | "Priorities ranked" |

### Implementation

- Pre-compute 5 graph snapshots as JSON node/edge lists
- D3 force simulation interpolates between snapshots on scroll position
- Nodes are circles with short labels; edges are curved lines
- Top-3 highlighted nodes pulse with accent color glow
- Fallback: 5 static SVG frames for no-JS / mobile

---

## Pipeline Animation Spec

Horizontal pipeline showing the EngramR workflow.

```
[inbox] -> [/reduce] -> [claims] -> [/generate] -> [tournament] -> [leaderboard]
```

- Each box starts grayed out
- As user scrolls, boxes activate left-to-right with a fill animation
- Connecting arrows animate (dash-offset trick)
- When "leaderboard" activates, 3 ranked items fade in below it
- Total animation duration: tied to ~30% of viewport scroll

---

## Cost Calculator Spec

Interactive element in section 7.

- Slider: lab size (3 to 20 people, step 1)
- Output: estimated monthly API cost ($100-$600 range)
- Comparison line below: "One failed experiment costs $X,000. One missed connection costs more."
- Formula: `cost = 50 + (lab_size * 25)` (rough, tunable)
- No backend. Pure client-side JS.

---

## Derivative Asset: 90-Second Video

Once the site is built, record a screen capture of scrolling through it with voiceover narration. This becomes the "Option 2" video asset for async distribution.

**Recording setup:**
- Screen capture at 1080p of the scrollytelling site
- Scroll at a controlled pace (~15s per major section)
- Voiceover script adapted from section headlines
- Export as MP4, host on GitHub or embed in site as a "watch the overview" link
- Total: 90s final cut

---

## Project Structure

```
pitch-site/
  src/
    layouts/
      BaseLayout.astro          -- dark theme, fonts, meta tags
    components/
      HookSection.astro         -- animated opening text
      ProblemCascade.astro      -- four problem cards
      GraphAnimation.astro      -- D3 knowledge graph (Astro island)
      PipelineAnimation.astro   -- horizontal pipeline with scroll trigger
      Timeline.astro            -- Day 1 to Year 1
      ComparisonTable.astro     -- feature comparison
      CostCalculator.astro      -- interactive slider (Astro island)
      AdoptionGradient.astro    -- staircase visual
      FederationDiagram.astro   -- two-vault bridge
      CTASection.astro          -- ask + contact cards
      TerminalEmbed.astro       -- asciinema player wrapper
    pages/
      index.astro               -- assembles all sections
    styles/
      global.css                -- Tailwind config, custom properties
    data/
      graph-snapshots.json      -- pre-computed graph states for animation
  public/
    fonts/                      -- self-hosted serif + sans-serif
    recordings/                 -- asciinema cast files or MP4
  astro.config.mjs              -- GitHub Pages adapter config
  tailwind.config.mjs
  package.json
```

---

## Implementation Phases

### Phase 1 -- Skeleton + Content (1 day)

- Astro project init with Tailwind
- BaseLayout with dark theme, typography, meta tags
- All 10 sections as static components (no animation yet)
- Content adapted from pitch-and-business-plan.md
- Deploy to GitHub Pages -- confirms pipeline works
- **Gate:** site is readable as a static long-scroll page

### Phase 2 -- Scroll Animations (1 day)

- Add GSAP ScrollTrigger
- Wire fade-in animations for Problem Cascade, Timeline, Comparison, Adoption
- Wire pipeline horizontal animation
- Wire cost calculator slider
- **Gate:** scrolling through the site feels like a guided narrative

### Phase 3 -- Graph Animation (1 day)

- Pre-compute 5 graph snapshot JSON files from actual vault data (or representative mock)
- D3 force-directed island component
- Scroll-driven interpolation between snapshots
- Mobile fallback (static SVGs)
- **Gate:** the graph growing is the "wow" moment -- test on 3 people

### Phase 4 -- Polish + Terminal Recording (0.5 day)

- Record asciinema session of real EngramR workflow
- Embed between Pipeline and Timeline sections
- Typography fine-tuning, spacing, responsive breakpoints
- Favicon, OpenGraph meta tags, social preview image
- Final deploy
- **Gate:** send URL to one PI, get unprompted positive reaction

### Phase 5 -- Video Derivative (0.5 day)

- Screen-record a smooth scroll-through of the finished site
- Write and record voiceover (or use text-on-screen narration)
- Edit to 90 seconds
- Host and link from the site

---

## Acceptance Criteria

- [ ] Site loads in < 2s on a 4G connection (Lighthouse performance > 90)
- [ ] All 10 sections render correctly on desktop (1440px) and mobile (375px)
- [ ] Graph animation runs at 60fps on a 2020 MacBook Air
- [ ] Cost calculator produces correct values across the slider range
- [ ] No external service dependencies at runtime (fonts self-hosted, no analytics, no CDN)
- [ ] Deploys to GitHub Pages with a single `npm run build && deploy` command
- [ ] URL is shareable and self-contained -- no "you need to install X to view this"
- [ ] Terminal recording auto-plays when scrolled into view, does not auto-play audio

---

## Risks

| Risk | Mitigation |
|------|------------|
| Graph animation performance on low-end devices | Canvas fallback; static SVG below 768px; test on oldest target device |
| Scroll jank from too many simultaneous animations | Stagger triggers; only animate elements in viewport; use will-change CSS |
| Content too wordy for scroll format | Enforce 2-sentence max per section; visual carries the argument |
| Scope creep into full marketing site | This is ONE page. No nav, no blog, no docs section. Link to GitHub for everything else |
| Asciinema player bundle size | Lazy-load; only initialize when section enters viewport |

---

## Dependencies on Existing Work

- `docs/pitch-and-business-plan.md` -- source content (complete)
- Vault data for graph snapshots -- can use current vault (~200 notes) or representative mock
- No code dependencies on the EngramR Python/R codebase -- this is a standalone static site

## Relationship to Road Map

This is a marketing/outreach asset, not a feature. It does not appear in the feature road map (road-map.md) but supports the "Ask" section's goal of recruiting pilot labs. Success here accelerates adoption which validates the features in the road map.
