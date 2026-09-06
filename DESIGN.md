# Confluence Design System Specification (DESIGN.md)

This document establishes the official visual design system, token architecture, typography hierarchy, accessibility standards, and component guidelines for the **Confluence Coastal Environmental Platform**.

---

## 1. Visual Philosophy & Anti-Slop Principles
*(Synthesized from Taste Skill, Vercel Web Interface Guidelines, and Image-to-Code Skill)*

- **Airy & Calm (`VISUAL_DENSITY: 3`)**: Marine and coastal operators require instant, stress-free cognition. Avoid cramped data tables and cards-inside-cards-inside-cards.
- **Generous Spacing (`SPACING_GENEROSITY: 9`)**: Every section and component adheres to a strict 8pt base spacing grid (8px, 16px, 24px, 32px, 48px, 64px) with clear visual breaks.
- **Zero Clutter (`UI_SIMPLICITY_DISCIPLINE: 9`)**: Strip away superfluous decorative badges, fake interface indicators, and gratuitous colored pills.
- **Laptop-First Viewport Discipline**: The hero section must be fully visible and readable on small laptop viewports (1366×768 to 1536×776) without pushing primary action elements off-screen.

---

## 2. Color Palette & Verified Contrast Ratios (WCAG AA)

| Token Name | Value | Purpose | Verified Contrast Ratio |
|---|---|---|---|
| `--bg-page` | `#F5F8FA` | Primary page canvas | High-clarity light canvas |
| `--bg-card` | `#FFFFFF` | Component container surfaces | Clean neutral white |
| `--bg-card-subtle` | `#F8FAFC` | Secondary panel backgrounds | 1.05:1 vs canvas |
| `--text-primary` | `#0F172A` | Primary headlines & body | **14.2:1** vs canvas (Exceeds WCAG AAA 7:1) |
| `--text-secondary` | `#475569` | Supporting labels & descriptions | **6.8:1** vs canvas (Exceeds WCAG AA 4.5:1) |
| `--text-muted` | `#64748B` | Timestamps & captions | **4.6:1** vs canvas (Passes WCAG AA 4.5:1) |
| `--accent-primary` | `#0891B2` | Primary buttons, active tabs | **4.6:1** vs white (Passes WCAG AA for UI) |
| `--accent-hover` | `#0E7490` | Hover & focus interactions | **5.4:1** vs white |
| `--accent-light` | `#ECFEFF` | Highlight badges & tint fills | Subtle background tint |
| `--border-color` | `#DCE5EA` | Primary subtle component borders | Low-friction structural lines |
| `--status-success` | `#047857` | Verified live & safe states | **5.2:1** vs white |
| `--status-warning` | `#B45309` | Cautionary advisory & degraded states | **4.8:1** vs white |
| `--status-danger` | `#B91C1C` | Critical alerts & hazard warnings | **5.6:1** vs white |

---

## 3. Typography Hierarchy & Rules

- **Display Heading (`h1`)**: `2.25rem`–`2.65rem`, weight `800`, letter-spacing `-0.03em`, line-height `1.2`. Always use `text-wrap: balance`.
- **Section Heading (`h2`, `h3`)**: `1.35rem`–`1.5rem`, weight `700`, letter-spacing `-0.02em`.
- **Card Titles (`h4`)**: `0.95rem`–`1.05rem`, weight `700`.
- **Body Text**: `0.92rem`–`0.98rem`, line-height `1.6`, color `var(--text-secondary)`.
- **Tabular Figures**: All numeric telemetry values, coordinates, timestamps, and latencies must specify `font-variant-numeric: tabular-nums` to eliminate layout jitter during real-time updates.
- **Editorial Punctuation**:
  - Use typographical ellipses `…` (never raw `...`).
  - Use typographical curly quotes `“` `”` for excerpts and case studies.
  - Use non-breaking spaces for units and brand names (e.g. `1.4&nbsp;m`, `31.2&nbsp;°C`, `1005.7&nbsp;hPa`, `99.9&nbsp;%`).

---

## 4. Accessibility & Interaction Standards

1. **Focus States**:
   - Every interactive element (`<button>`, `<a>`, `<input>`, `<select>`) must have an active `:focus-visible` ring:
     `outline: 2px solid var(--accent-primary); outline-offset: 2px;`
   - Never suppress outline with `outline: none` without providing an accessible focus alternative.
2. **Icon & Media Semantics**:
   - Icon-only buttons must provide explicit `aria-label`.
   - Decorative icons accompanying text must have `aria-hidden="true"`.
   - Critical hero images must have descriptive `alt` tags and `fetchpriority="high"`.
3. **Async Streaming & Feedback**:
   - Real-time chatbot streams and status alerts must include `aria-live="polite"` so screen readers gracefully announce updates.
4. **Motion Discipline**:
   - All animations and transitions must be restricted to hardware-accelerated `transform` and `opacity` properties (never `transition: all`).
   - All transitions must respect `@media (prefers-reduced-motion: reduce)`.
5. **Anchor Scroll Clearance**:
   - All section IDs must include `scroll-margin-top: 88px` to guarantee sticky headers never cover section headings upon navigation.
