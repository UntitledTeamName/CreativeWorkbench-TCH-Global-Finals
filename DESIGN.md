---
name: CharacterOS
description: Industrial Brutalist & Paper Duotone workbench for narrative universe architecture
colors:
  bg-0: "#f6f3eb"
  bg-1: "#ffffff"
  bg-2: "#eee8dc"
  bg-3: "#e2d9c8"
  line: "#d5c8b4"
  line-soft: "#e6ddce"
  line-dark: "#181614"
  ink: "#181614"
  muted: "#524d46"
  faint: "#7a7266"
  accent: "#b45309"
  accent-2: "#0f766e"
  edge: "#8c8070"
  danger: "#b91c1c"
  warn: "#c2410c"
  ok: "#15803d"
  accent-rust: "#9a3412"
  cover-leather-dark: "#382519"
  cover-leather: "#543b2b"
  cover-linen-dark: "#172a28"
  cover-linen: "#244340"
  cover-cloth-dark: "#211f1d"
  cover-cloth: "#383531"
  cover-board-dark: "#3b2a1a"
  cover-board: "#5e4630"
  accent-deep: "#92400e"
  accent-bright: "#c25e10"
  accent-hover: "#9a440f"
typography:
  display:
    fontFamily: '"Iowan Old Style", "Palatino Linotype", "URW Palladio L", P052, Georgia, serif'
    fontSize: "clamp(2.25rem, 5vw, 3rem)"
    fontWeight: 700
    lineHeight: 1.08
    letterSpacing: "-0.01em"
  headline:
    fontFamily: '"Iowan Old Style", "Palatino Linotype", "URW Palladio L", P052, Georgia, serif'
    fontSize: "2.125rem"
    fontWeight: 700
    lineHeight: 1.15
    letterSpacing: "-0.01em"
  title:
    fontFamily: '"Iowan Old Style", "Palatino Linotype", "URW Palladio L", P052, Georgia, serif'
    fontSize: "1.625rem"
    fontWeight: 650
    lineHeight: 1.2
    letterSpacing: "normal"
  body:
    fontFamily: 'Inter, "Segoe UI", system-ui, -apple-system, sans-serif'
    fontSize: "0.875rem"
    fontWeight: 400
    lineHeight: 1.6
    letterSpacing: "normal"
  label:
    fontFamily: '"JetBrains Mono", "SF Mono", Menlo, Consolas, monospace'
    fontSize: "0.8125rem"
    fontWeight: 600
    lineHeight: 1.4
    letterSpacing: "0.05em"
  caption:
    fontFamily: '"JetBrains Mono", "SF Mono", Menlo, Consolas, monospace'
    fontSize: "0.6875rem"
    fontWeight: 500
    lineHeight: 1.4
    letterSpacing: "0.08em"
rounded:
  xs: "0px"
  sm: "0px"
  md: "0px"
  lg: "0px"
  xl: "0px"
  full: "0px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "16px"
  lg: "24px"
  xl: "32px"
components:
  button-primary:
    backgroundColor: "{colors.ink}"
    textColor: "#ffffff"
    rounded: "{rounded.sm}"
    padding: "9px 15px"
    shadow: "2px 2px 0 {colors.ink}"
  button-secondary:
    backgroundColor: "{colors.bg-1}"
    textColor: "{colors.ink}"
    rounded: "{rounded.sm}"
    padding: "9px 15px"
    shadow: "2px 2px 0 {colors.ink}"
  button-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.muted}"
    rounded: "{rounded.sm}"
    padding: "9px 15px"
  card:
    backgroundColor: "{colors.bg-1}"
    rounded: "{rounded.lg}"
    padding: "20px"
    shadow: "2px 2px 0 {colors.ink}"
  badge:
    backgroundColor: "{colors.bg-1}"
    textColor: "{colors.ink}"
    rounded: "0px"
    padding: "4px 9px"
    shadow: "2px 2px 0 {colors.ink}"
---

## Overview

CharacterOS is an offline-first creative workbench and narrative compiler. The visual language embodies **Industrial Brutalism & Paper Duotone**—an authentic architectural galley proof press where raw function, uncompromising structural hairlines, and tactile paper substrates converge. 

Every single corner across CSS and SVG geometries is an absolute 90° right angle (`0px`). Circular badges, avatars, and minimap markers are replaced with sharp square registration pips. Elevation is rendered through physical, hard-edged paper offset shadows (`2px 2px 0 var(--ink)` and `4px 4px 0 var(--ink)`) rather than blurred artificial lighting.

## Colors

The palette operates as a high-contrast two-tone print proofing system, calibrated to exceed WCAG AAA/AA contrast standards:

- **Tactile Proof Paper (`bg-0`: `#f6f3eb`)**: Matte unbleached drafting paper substrate with subtle mechanical dot matrix registration.
- **Index Card Surface (`bg-1`: `#ffffff`)**: Crisp white card surface for primary working areas, editors, and dialogs.
- **Recessed Drafting Tray (`bg-2`: `#eee8dc`)**: Deep unbleached paper trays, table headers, and inactive tabs.
- **Active State Tray (`bg-3`: `#e2d9c8`)**: Selected list items and hovered surfaces.
- **Ruled Hairlines (`line`: `#d5c8b4`, `line-dark`: `#181614`)**: Rigid architectural division borders and galley column lines.
- **Deep Carbon Letterpress Ink (`ink`: `#181614`)**: Stark carbon black ink offering >18:1 contrast for effortless, high-impact reading.
- **Graphite Gray (`muted`: `#524d46`)**: Secondary prose and metadata meeting >7:1 contrast.
- **Pencil Draft (`faint`: `#7a7266`)**: Micro annotations, timestamps, and hairline guides.
- **Burnt Terracotta / Sienna Amber (`accent`: `#b45309`)**: High-contrast primary proofing ink for active states, key CTAs, and focus frames.
- **Archival Verdigris (`accent-2`: `#0f766e`)**: Secondary duotone counterpoint for narrative relationship paths, tags, and cross-references.
- **Status Markers**: `#15803d` (canonical approved), `#c2410c` (editorial attention), `#b91c1c` (tension breaking point).

## Typography

Typographic hierarchy celebrates Swiss print precision and editorial book design:

- **Display & Titles**: Iowan Old Style / Palatino / Georgia (`var(--serif)`), 700 weight, deep carbon ink `#181614`. Evokes a typeset story bible or handset letterpress proof.
- **Body & Controls**: Inter (`var(--sans)`), 400/600 weights. Clean, unpretentious legibility for interface labels, character descriptions, and inputs.
- **Metadata & Technical Telemetry**: JetBrains Mono / SF Mono (`var(--mono)`), uppercase tracking. Typeset for bracketed proof stamps (`[ DRAFT // REV 01 ]`), registration tags, and communication lens IDs.

## Elevation & Geometry

- **Sharp 90-Degree Edges**: Zero rounded corners (`border-radius: 0; rx="0"`). Everything from buttons and badges to graph cards, modals, and minimap dots is mechanically rectangular.
- **Physical Hard Offset Shadows**:
  - Base cards / panels: `box-shadow: 2px 2px 0 var(--ink);`
  - Hover states: `transform: translate(-1px, -1px); box-shadow: 4px 4px 0 var(--ink);`
  - Active / pressed states: `transform: translate(1px, 1px); box-shadow: none;`
  - Modals: `box-shadow: 8px 8px 0 var(--ink);`

## Components

- **Buttons**:
  - *Primary*: Carbon black background (`var(--ink)`), white text, sharp 0px border, hard offset shadow.
  - *Secondary / Ghost*: White paper background with 1.5px carbon ink border; hover translates with hard shadow.
- **Relationship Atlas**:
  - Native SVG canvas with sharp rectangular character nodes, square status registration pips, and square minimap radar markers.
  - Connector paths render as dark ruled lines with square line caps, highlighting in burnt terracotta or archival verdigris on selection.
- **Visual Prompt Kit**:
  - High-contrast card layouts with monospace aspect-ratio tags, dark covers, and one-click copy actions.
- **Banners & Modals**:
  - Framed with 1.5px or 2px solid carbon ink rules and hard paper offset drop shadows.

## Do's and Don'ts

### Do's
- Keep every corner strictly sharp at 90 degrees (`0px`).
- Use hard physical offset box shadows (`Xpx Xpx 0 var(--ink)`) instead of soft blurry shadows.
- Maintain a minimum 4.5:1 text contrast ratio across all elements.
- Frame metadata with monospace proof brackets (`[ PROOF // APPROVED ]`).
- Use square pips instead of rounded dots for status and registration indicators.

### Don'ts
- Never use `border-radius` greater than 0.
- Do not use soft multi-stop blurry Gaussian box-shadows.
- Do not use side-accent borders (`border-left: 3px solid ...`).
- Do not use gradient text or decorative glassmorphism.
- Do not hardcode colors outside the semantic design tokens.
