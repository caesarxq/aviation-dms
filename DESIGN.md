---
version: alpha
name: KFL Aviation DMS

description: Calm, operationally precise interface for aviation compliance, safety, fleet, and document control.
colors:
  primary: "#1B7ABF"
  brand-blue: "#1B7ABF"
  brand-blue-deep: "#0B2942"
  brand-blue-ink: "#123B5D"
  sky-tint: "#EAF4FB"
  canvas: "#F4F7FA"
  surface: "#FFFFFF"
  surface-subtle: "#F8FAFC"
  border: "#D9E2EC"
  text-primary: "#102A43"
  text-secondary: "#52606D"
  text-muted: "#7B8794"
  status-healthy: "#0F6B4C"
  status-warning: "#8A5A00"
  status-critical: "#C53030"
  status-info: "#2B6CB0"
  focus: "#63B3ED"
typography:
  display:
    fontFamily: Inter, ui-sans-serif, system-ui, sans-serif
    fontSize: 2rem
    fontWeight: 700
    lineHeight: 1.15
    letterSpacing: "-0.025em"
  heading:
    fontFamily: Inter, ui-sans-serif, system-ui, sans-serif
    fontSize: 1.125rem
    fontWeight: 700
    lineHeight: 1.35
    letterSpacing: "-0.01em"
  body:
    fontFamily: Inter, ui-sans-serif, system-ui, sans-serif
    fontSize: 0.875rem
    fontWeight: 400
    lineHeight: 1.5
  label:
    fontFamily: Inter, ui-sans-serif, system-ui, sans-serif
    fontSize: 0.6875rem
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "0.08em"
rounded:
  sm: 6px
  md: 10px
  lg: 16px
  pill: 999px
spacing:
  xs: 4px
  sm: 8px
  md: 12px
  lg: 16px
  xl: 24px
  2xl: 32px
  3xl: 48px
elevation:
  card: "0 1px 2px rgba(16, 42, 67, 0.04), 0 8px 24px rgba(16, 42, 67, 0.06)"
  popover: "0 12px 32px rgba(16, 42, 67, 0.14)"
components:
  app-shell:
    backgroundColor: "{colors.brand-blue-deep}"
    textColor: "#FFFFFF"
  page-canvas:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.text-primary}"
  surface-subtle:
    backgroundColor: "{colors.surface-subtle}"
    textColor: "{colors.text-secondary}"
  table-border:
    backgroundColor: "{colors.border}"
    textColor: "{colors.text-primary}"
  focus-ring:
    backgroundColor: "{colors.focus}"
    textColor: "{colors.brand-blue-deep}"
  muted-copy:
    textColor: "{colors.text-muted}"
  link:
    textColor: "{colors.brand-blue}"
  status-info:
    backgroundColor: "{colors.sky-tint}"
    textColor: "{colors.status-info}"
    rounded: "{rounded.pill}"
  status-healthy:
    backgroundColor: "#E7F6EF"
    textColor: "{colors.status-healthy}"
    rounded: "{rounded.pill}"
  status-warning:
    backgroundColor: "#FFF7DF"
    textColor: "{colors.status-warning}"
    rounded: "{rounded.pill}"
  status-critical:
    backgroundColor: "#FDECEC"
    textColor: "{colors.status-critical}"
    rounded: "{rounded.pill}"
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "#FFFFFF"
    rounded: "{rounded.sm}"
    padding: "10px 14px"
  button-primary-hover:
    backgroundColor: "{colors.brand-blue-ink}"
  card:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text-primary}"
    rounded: "{rounded.md}"
    padding: "20px"
---

## Overview

KFL Aviation DMS uses an **operations-room calm**: blue authority, light surfaces, restrained status colors, and dense-but-readable information. The interface should feel dependable under time pressure, never decorative or ambiguous.

The supplied Kenya Flying Labs wordmark is the primary brand asset. Its exact blue is `#1B7ABF`; pair it with deep aviation navy rather than black. Use the wordmark in the application chrome, login surfaces, and formal exports. Do not recolor or distort it.

## Colors

- **Brand blue:** primary action, active navigation, links, focus rings, and data highlights.
- **Deep aviation navy:** sidebar, top-level chrome, and high-contrast headings.
- **Sky tint:** selected rows, informational callouts, and subtle blue backgrounds.
- **Canvas gray:** application background that separates white work surfaces.
- **Status colors:** reserve green, amber, and red for operational state only; never use them as decoration.

## Typography

Use Inter or the system sans stack. Headings are compact and confident; body text remains 14px for data density. Labels use uppercase letter spacing sparingly for metadata and table headers. Avoid all-caps in long content.

## Layout

- Persistent left navigation: 248px desktop, collapsible below 1024px.
- Main content max-width: 1440px with 24–32px page padding.
- Use a 12-column grid for dashboards; cards align to a shared baseline.
- Every page starts with a page header containing title, context, and primary action.
- Tables prioritize scanability: sticky header, zebra-free rows, 12px–14px cell text, and explicit empty/loading/error states.

## Elevation & Depth

Prefer borders plus a very soft shadow. Cards should read as work surfaces, not floating tiles. Use stronger elevation only for menus, dialogs, and command surfaces.

## Shapes

Use 6px for controls, 10px for cards, and pill shapes only for status badges and compact filters. Avoid excessive rounding.

## Components

- **Primary action:** brand-blue filled button; one dominant action per page.
- **Secondary action:** white/transparent button with standard border.
- **Status badge:** semantic color with text, never color alone.
- **Metric card:** label, value, optional delta/context, and a small icon with blue-tinted container.
- **Deadline row:** title, entity reference, due date, priority badge, and clear overdue styling.
- **Navigation item:** icon + label, 40px height, active state uses blue tint and a 3px left accent.
- **Form controls:** minimum 40px height, visible labels, clear focus ring, inline validation.
- **Empty state:** concise explanation plus the next useful action.

## Do's and Don'ts

- Do keep safety-critical actions explicit and confirmable.
- Do show loading, error, empty, and success states for every data surface.
- Do use the logo on transparent backgrounds with adequate clear space.
- Do preserve reporter confidentiality in every surface.
- Don't use gradients, neon colors, or decorative animation in operational workflows.
- Don't communicate severity by color alone; include text and icons.
- Don't place more than one high-emphasis action in a card.

## Content Sanitization

Document content may contain HTML formatting from OEM manuals and controlled documents. To preserve formatting while preventing XSS attacks, all rendered document content passes through **DOMPurify sanitization** before insertion into the DOM:

- **Script tags** are stripped entirely.
- **Event handlers** (`onclick`, `onerror`, etc.) are removed.
- **Dangerous attributes** (`javascript:` URLs, `data:` URIs) are stripped.
- **Safe formatting** (bold, italic, lists, tables, headings, links with `target="_blank"` and `rel="noopener"`) is preserved.
- Sanitization applies to both the **Document Viewer** (read-only) and **Document Editor** (preview mode).

All document content is stored raw in the database; sanitization happens only at render time.
