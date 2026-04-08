# Track A — Frontend Visual Identity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace all hardcoded styles with a design token system, build a shared component library via 21st.dev MCP, and redesign all product pages with a premium visual identity.

**Architecture:** Three-stage pipeline — (1) Gemini CLI audits the entire frontend in one pass and produces a design spec, (2) Claude Code builds design tokens + component library using 21st.dev MCP against the spec, (3) Claude Code rewires every page to use the new components. No backend changes. No routing changes.

**Tech Stack:** React 19, Vite 7, Tailwind v4, Framer Motion (already installed), 21st.dev MCP (`mcp__magic__21st_magic_component_builder`), Gemini CLI for audit

**Executor tools:**
- Tasks 1–2: Gemini CLI (large-context audit of entire codebase)
- Tasks 3–9: Claude Code + 21st.dev MCP (component fabrication + page integration)

**Design direction:** Keep `#4F46E5` indigo as primary. Add deep slate backgrounds for dark/premium feel. Warm amber (`#F59E0B`) for accents/CTAs. Proper dark-mode token set. Typography: Inter or system-sans for UI, slightly larger type scale.

---

## Current State (read before starting)

```
D:/Projects/AltairGO-Platform/src/
  pages/
    HomePage.jsx                 # Landing page
    PlannerPage.jsx              # Trip generation form
    GeneratingPage.jsx           # SSE progress page
    BlogsPage.jsx
    DiscoverPage.jsx
    auth/
      LoginPage.jsx
      RegisterPage.jsx
    trips/
      DashboardPage.jsx
      TripViewerPage.jsx
      tabs/
        ItineraryTab.jsx
        BookingsTab.jsx
        ExpensesTab.jsx
        ReadinessTab.jsx
        NotesTab.jsx
        SummaryTab.jsx
    admin/
      AdminDashboard.jsx
      ... (admin pages)
  components/
    ... (existing components)
  context/
    AuthContext.jsx
  design-system/       ← DOES NOT EXIST YET (create in Task 2)
  components/ui/       ← DOES NOT EXIST YET (create in Task 3)
```

**Existing hardcoded patterns to replace:**
```jsx
// Colors (replace with tokens)
className="bg-indigo-600"  → className="bg-primary"
className="text-gray-600"  → className="text-muted"
style={{color: '#4F46E5'}} → style={{color: 'var(--color-primary)'}}

// Spacing (replace with tokens)
className="p-4 gap-2"     → keep Tailwind but driven by token scale

// Components (replace with library)
<button className="bg-indigo-600 text-white px-4 py-2 rounded-lg ...">
→ <Button variant="primary">
```

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `src/design-system/tokens.css` | CREATE | CSS custom properties for all design tokens |
| `src/design-system/typography.css` | CREATE | Font scale and text utilities |
| `src/design-system/animations.js` | CREATE | Shared Framer Motion variants |
| `src/design-system/index.css` | CREATE | Imports tokens + typography |
| `src/components/ui/Button.jsx` | CREATE | Button variants |
| `src/components/ui/Card.jsx` | CREATE | Card container |
| `src/components/ui/Badge.jsx` | CREATE | Status + label badges |
| `src/components/ui/Input.jsx` | CREATE | Form input with label + error |
| `src/components/ui/Select.jsx` | CREATE | Styled select |
| `src/components/ui/Modal.jsx` | CREATE | Accessible modal dialog |
| `src/components/ui/Skeleton.jsx` | CREATE | Loading skeleton |
| `src/components/ui/EmptyState.jsx` | CREATE | Empty state pattern |
| `src/components/ui/Toast.jsx` | CREATE | Toast notification |
| `src/components/ui/ProgressBar.jsx` | CREATE | Progress indicator |
| `src/components/ui/index.js` | CREATE | Re-export barrel |
| `src/index.css` | MODIFY | Import design-system/index.css |
| `src/pages/HomePage.jsx` | REDESIGN | Premium landing page |
| `src/pages/PlannerPage.jsx` | REDESIGN | Multi-step wizard |
| `src/pages/trips/DashboardPage.jsx` | REDESIGN | Trip grid + stats |
| `src/pages/trips/TripViewerPage.jsx` | REDESIGN | Premium itinerary view |
| `src/pages/BlogsPage.jsx` | REDESIGN | Editorial grid |
| `src/pages/DiscoverPage.jsx` | REDESIGN | Destination cards |
| `src/pages/auth/LoginPage.jsx` | REDESIGN | Clean auth form |
| `src/pages/auth/RegisterPage.jsx` | REDESIGN | Clean auth form |

---

## Task 1: Gemini CLI — Full Frontend Audit

**Tool:** Gemini CLI  
**Purpose:** Read every component in one pass, inventory all design decisions, produce the token spec.

- [ ] **Step 1.1: Run Gemini CLI audit**

Open Gemini CLI and run with this prompt (feed it the entire `src/` directory):

```
You are auditing the AltairGO frontend for a full visual identity overhaul.

Read every file in src/pages/, src/components/, and src/index.css.

Produce a structured audit report with these sections:

## 1. Color Inventory
List every hardcoded color value found (hex codes, Tailwind color classes like bg-indigo-600, text-gray-500).
Group by: primary/accent/neutral/semantic (success/warning/error/info).

## 2. Typography Inventory  
List every font-size, font-weight, line-height pattern found.
Identify: headings, body text, captions, labels, code.

## 3. Spacing Patterns
List repeated padding/margin/gap patterns. Identify the implicit grid unit.

## 4. Component Inventory
List every UI pattern that appears in 2+ places:
- Buttons (how many variants? what states?)
- Cards (how many layouts?)
- Form fields (patterns?)
- Loading states (spinners, skeletons?)
- Empty states
- Modals/overlays

## 5. Problems Found
List: inconsistencies, accessibility gaps, hardcoded values that should be tokens, components duplicated across pages.

## 6. Recommended Token Set
Based on the audit, produce the complete CSS custom property set:
--color-primary, --color-primary-dark, --color-primary-light
--color-accent, --color-accent-dark
--color-bg, --color-bg-subtle, --color-bg-elevated
--color-text, --color-text-muted, --color-text-inverted
--color-border, --color-border-subtle
--color-success, --color-warning, --color-error, --color-info
--space-1 through --space-16 (4px base grid)
--radius-sm, --radius-md, --radius-lg, --radius-full
--shadow-sm, --shadow-md, --shadow-lg
--font-size-xs through --font-size-4xl
--font-weight-normal, --font-weight-medium, --font-weight-bold

Use these specific values:
- Primary: #4F46E5 (indigo-600)
- Accent: #F59E0B (amber-500)  
- Background: #0F172A (slate-900) for dark, #F8FAFC for light
- Text: #1E293B primary, #64748B muted

## 7. Page Redesign Priorities
Rank pages by redesign impact (highest value first).
```

- [ ] **Step 1.2: Save the audit output**

Save Gemini's output to `docs/design-audit.md` in the frontend project:

```bash
# Save to D:/Projects/AltairGO-Platform/docs/design-audit.md
```

- [ ] **Step 1.3: Commit audit doc**

```bash
cd "D:/Projects/AltairGO-Platform"
git add docs/design-audit.md
git commit -m "docs: add Gemini frontend design audit"
```

---

## Task 2: Design Token System

**Tool:** Claude Code  
**Files:** `src/design-system/tokens.css`, `src/design-system/typography.css`, `src/design-system/animations.js`, `src/design-system/index.css`

- [ ] **Step 2.1: Create design tokens CSS**

```css
/* src/design-system/tokens.css */

:root {
  /* ── Primary (Indigo) ── */
  --color-primary:        #4F46E5;
  --color-primary-dark:   #3730A3;
  --color-primary-light:  #818CF8;
  --color-primary-subtle: #EEF2FF;

  /* ── Accent (Amber) ── */
  --color-accent:         #F59E0B;
  --color-accent-dark:    #D97706;
  --color-accent-light:   #FCD34D;

  /* ── Backgrounds (Light mode) ── */
  --color-bg:             #F8FAFC;
  --color-bg-subtle:      #F1F5F9;
  --color-bg-elevated:    #FFFFFF;
  --color-bg-overlay:     rgba(15, 23, 42, 0.5);

  /* ── Text ── */
  --color-text:           #1E293B;
  --color-text-muted:     #64748B;
  --color-text-subtle:    #94A3B8;
  --color-text-inverted:  #FFFFFF;

  /* ── Borders ── */
  --color-border:         #E2E8F0;
  --color-border-subtle:  #F1F5F9;
  --color-border-strong:  #CBD5E1;

  /* ── Semantic ── */
  --color-success:        #10B981;
  --color-success-subtle: #ECFDF5;
  --color-warning:        #F59E0B;
  --color-warning-subtle: #FFFBEB;
  --color-error:          #EF4444;
  --color-error-subtle:   #FEF2F2;
  --color-info:           #3B82F6;
  --color-info-subtle:    #EFF6FF;

  /* ── Spacing (4px base) ── */
  --space-1:  0.25rem;   /* 4px  */
  --space-2:  0.5rem;    /* 8px  */
  --space-3:  0.75rem;   /* 12px */
  --space-4:  1rem;      /* 16px */
  --space-5:  1.25rem;   /* 20px */
  --space-6:  1.5rem;    /* 24px */
  --space-8:  2rem;      /* 32px */
  --space-10: 2.5rem;    /* 40px */
  --space-12: 3rem;      /* 48px */
  --space-16: 4rem;      /* 64px */
  --space-20: 5rem;      /* 80px */

  /* ── Border Radius ── */
  --radius-sm:   0.25rem;   /* 4px  */
  --radius-md:   0.5rem;    /* 8px  */
  --radius-lg:   0.75rem;   /* 12px */
  --radius-xl:   1rem;      /* 16px */
  --radius-2xl:  1.5rem;    /* 24px */
  --radius-full: 9999px;

  /* ── Shadows ── */
  --shadow-sm:  0 1px 2px 0 rgb(0 0 0 / 0.05);
  --shadow-md:  0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1);
  --shadow-lg:  0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1);
  --shadow-xl:  0 20px 25px -5px rgb(0 0 0 / 0.1), 0 8px 10px -6px rgb(0 0 0 / 0.1);

  /* ── Typography Scale ── */
  --font-size-xs:   0.75rem;    /* 12px */
  --font-size-sm:   0.875rem;   /* 14px */
  --font-size-base: 1rem;       /* 16px */
  --font-size-lg:   1.125rem;   /* 18px */
  --font-size-xl:   1.25rem;    /* 20px */
  --font-size-2xl:  1.5rem;     /* 24px */
  --font-size-3xl:  1.875rem;   /* 30px */
  --font-size-4xl:  2.25rem;    /* 36px */
  --font-size-5xl:  3rem;       /* 48px */
  --font-size-6xl:  3.75rem;    /* 60px */

  --font-weight-normal:    400;
  --font-weight-medium:    500;
  --font-weight-semibold:  600;
  --font-weight-bold:      700;
  --font-weight-extrabold: 800;

  --line-height-tight:  1.25;
  --line-height-normal: 1.5;
  --line-height-relaxed:1.75;

  /* ── Transitions ── */
  --transition-fast:   150ms ease;
  --transition-normal: 250ms ease;
  --transition-slow:   350ms ease;
}
```

- [ ] **Step 2.2: Create typography CSS**

```css
/* src/design-system/typography.css */

.text-display {
  font-size: var(--font-size-6xl);
  font-weight: var(--font-weight-extrabold);
  line-height: var(--line-height-tight);
  letter-spacing: -0.025em;
}

.text-h1 {
  font-size: var(--font-size-4xl);
  font-weight: var(--font-weight-bold);
  line-height: var(--line-height-tight);
  letter-spacing: -0.02em;
}

.text-h2 {
  font-size: var(--font-size-3xl);
  font-weight: var(--font-weight-bold);
  line-height: var(--line-height-tight);
}

.text-h3 {
  font-size: var(--font-size-2xl);
  font-weight: var(--font-weight-semibold);
  line-height: var(--line-height-normal);
}

.text-h4 {
  font-size: var(--font-size-xl);
  font-weight: var(--font-weight-semibold);
}

.text-body-lg {
  font-size: var(--font-size-lg);
  line-height: var(--line-height-relaxed);
}

.text-body {
  font-size: var(--font-size-base);
  line-height: var(--line-height-normal);
}

.text-body-sm {
  font-size: var(--font-size-sm);
  line-height: var(--line-height-normal);
}

.text-caption {
  font-size: var(--font-size-xs);
  line-height: var(--line-height-normal);
  color: var(--color-text-muted);
}

.text-label {
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-medium);
  letter-spacing: 0.025em;
}
```

- [ ] **Step 2.3: Create Framer Motion animation variants**

```js
// src/design-system/animations.js

export const fadeIn = {
  initial: { opacity: 0 },
  animate: { opacity: 1 },
  exit: { opacity: 0 },
  transition: { duration: 0.2 },
};

export const slideUp = {
  initial: { opacity: 0, y: 16 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -8 },
  transition: { duration: 0.25, ease: 'easeOut' },
};

export const slideIn = {
  initial: { opacity: 0, x: -16 },
  animate: { opacity: 1, x: 0 },
  exit: { opacity: 0, x: 16 },
  transition: { duration: 0.2, ease: 'easeOut' },
};

export const staggerChildren = {
  animate: { transition: { staggerChildren: 0.07 } },
};

export const scaleIn = {
  initial: { opacity: 0, scale: 0.95 },
  animate: { opacity: 1, scale: 1 },
  exit: { opacity: 0, scale: 0.95 },
  transition: { duration: 0.2, ease: 'easeOut' },
};

export const cardHover = {
  rest: { scale: 1, boxShadow: 'var(--shadow-sm)' },
  hover: { scale: 1.02, boxShadow: 'var(--shadow-lg)', transition: { duration: 0.2 } },
};
```

- [ ] **Step 2.4: Create design-system index**

```css
/* src/design-system/index.css */
@import './tokens.css';
@import './typography.css';
```

- [ ] **Step 2.5: Import in main index.css**

Open `src/index.css`. Add at the very top:
```css
@import './design-system/index.css';
```

- [ ] **Step 2.6: Commit**

```bash
cd "D:/Projects/AltairGO-Platform"
git add src/design-system/ src/index.css
git commit -m "feat: add design token system and typography scale"
```

---

## Task 3: Component Library via 21st.dev MCP

**Tool:** Claude Code + `mcp__magic__21st_magic_component_builder`

Build each component using the MCP. All components must use CSS variables from `design-system/tokens.css`. Save each to `src/components/ui/`.

- [ ] **Step 3.1: Build Button component**

Prompt for `mcp__magic__21st_magic_component_builder`:
```
Build a React Button component using CSS custom properties (not hardcoded Tailwind colors).

Props: variant ('primary'|'secondary'|'ghost'|'danger'), size ('sm'|'md'|'lg'), loading (bool), disabled (bool), children, onClick, type, className.

Primary: background var(--color-primary), text white, hover var(--color-primary-dark)
Secondary: background var(--color-bg-elevated), border var(--color-border), text var(--color-text)
Ghost: no background, text var(--color-primary), hover var(--color-primary-subtle)
Danger: background var(--color-error), text white

Loading state: show a spinner (CSS border animation) replacing children, keep button width.
Disabled: opacity 0.5, no pointer events.
Transitions: var(--transition-fast) on all interactive properties.
Border radius: var(--radius-md)
```

Save to `src/components/ui/Button.jsx`.

- [ ] **Step 3.2: Build Card component**

Prompt:
```
Build a React Card component using CSS custom properties.

Props: children, variant ('default'|'elevated'|'bordered'), padding ('none'|'sm'|'md'|'lg'), hover (bool), onClick, className.

Default: background var(--color-bg-elevated), border 1px solid var(--color-border), border-radius var(--radius-xl), shadow var(--shadow-sm)
Elevated: shadow var(--shadow-lg), no border
Bordered: border 2px solid var(--color-border-strong)

When hover=true: transition transform and shadow on hover (scale 1.01, shadow-lg)
When onClick provided: cursor pointer.
```

Save to `src/components/ui/Card.jsx`.

- [ ] **Step 3.3: Build Badge component**

Prompt:
```
Build a React Badge component using CSS custom properties.

Props: variant ('default'|'success'|'warning'|'error'|'info'|'primary'), size ('sm'|'md'), children, className.

Each variant uses its --color-{variant} for background (at 15% opacity) and text color.
Primary badge: background var(--color-primary-subtle), text var(--color-primary)
Pill shape: border-radius var(--radius-full)
Small: font-size var(--font-size-xs), padding 2px 8px
Medium: font-size var(--font-size-sm), padding 4px 10px
```

Save to `src/components/ui/Badge.jsx`.

- [ ] **Step 3.4: Build Input component**

Prompt:
```
Build a React Input component using CSS custom properties.

Props: label (string), id (string), error (string), hint (string), type, value, onChange, placeholder, required, disabled, className.

Renders: <label> (if provided) + <input> + error message (if error) or hint text (if hint).
Label: font-size var(--font-size-sm), font-weight var(--font-weight-medium), color var(--color-text), margin-bottom var(--space-1)
Input: full width, border 1px solid var(--color-border), border-radius var(--radius-md), padding var(--space-2) var(--space-3), font-size var(--font-size-base), background var(--color-bg-elevated)
Focus: outline none, border-color var(--color-primary), box-shadow 0 0 0 3px rgba(79,70,229,0.1)
Error state: border-color var(--color-error)
Error text: color var(--color-error), font-size var(--font-size-sm), margin-top var(--space-1)
```

Save to `src/components/ui/Input.jsx`.

- [ ] **Step 3.5: Build Modal component**

Prompt:
```
Build a React Modal component using CSS custom properties and Framer Motion.

Props: isOpen (bool), onClose (fn), title (string), children, size ('sm'|'md'|'lg'|'xl'), footer (ReactNode).

Renders: backdrop overlay (var(--color-bg-overlay)) + centered dialog.
Backdrop: click to close (calls onClose).
Dialog: background var(--color-bg-elevated), border-radius var(--radius-2xl), shadow var(--shadow-xl), padding var(--space-6).
Title: text-h3 class, margin-bottom var(--space-4).
Close button: top-right corner, ghost icon button.
Animation: use Framer Motion AnimatePresence + scaleIn variant (scale 0.95 → 1, opacity 0 → 1, 200ms).
Sizes: sm=400px, md=560px, lg=720px, xl=900px max-width.
Accessible: role="dialog", aria-modal="true", aria-labelledby pointing to title.
```

Save to `src/components/ui/Modal.jsx`.

- [ ] **Step 3.6: Build Skeleton component**

Prompt:
```
Build a React Skeleton loading component using CSS custom properties.

Props: width (string|number), height (string|number), borderRadius (string), count (number, default 1), className.

Uses a shimmer animation: CSS background gradient animating from --color-bg-subtle to --color-border and back, 1.5s infinite.
When count > 1: render count stacked skeletons with var(--space-2) gap.
```

Save to `src/components/ui/Skeleton.jsx`.

- [ ] **Step 3.7: Build EmptyState component**

Prompt:
```
Build a React EmptyState component using CSS custom properties.

Props: icon (string emoji or ReactNode), title (string), description (string), action (ReactNode — usually a Button).

Layout: centered vertically and horizontally, flex column, gap var(--space-4).
Icon: large (3rem font-size or 48px if ReactNode), color var(--color-text-muted).
Title: text-h4 class, color var(--color-text).
Description: text-body class, color var(--color-text-muted), max-width 320px, text-center.
Action: centered below description.
```

Save to `src/components/ui/EmptyState.jsx`.

- [ ] **Step 3.8: Build Toast component**

Prompt:
```
Build a React Toast notification system using CSS custom properties and Framer Motion.

Two exports: useToast hook + ToastContainer component.

useToast returns: { success(msg), error(msg), warning(msg), info(msg) }
Each call adds a toast to global state.

ToastContainer: fixed bottom-right, z-index 9999, stacked list of toasts.
Each toast: background var(--color-bg-elevated), border-left 4px solid (color by variant), shadow var(--shadow-lg), border-radius var(--radius-lg), padding var(--space-3) var(--space-4), max-width 360px.
Auto-dismisses after 4000ms.
Animation: slide in from right, slide out to right (Framer Motion AnimatePresence).
Close button: small X on right.
```

Save to `src/components/ui/Toast.jsx`.

- [ ] **Step 3.9: Build ProgressBar component**

Prompt:
```
Build a React ProgressBar component using CSS custom properties.

Props: value (0-100), variant ('primary'|'success'|'warning'|'error'), size ('sm'|'md'|'lg'), showLabel (bool), animated (bool).

Track: full width, background var(--color-bg-subtle), border-radius var(--radius-full).
Fill: background var(--color-{variant}), border-radius var(--radius-full), transition width 500ms ease.
Sizes: sm=4px height, md=8px, lg=12px.
Label: right-aligned text-caption showing value%.
Animated: add CSS shimmer animation on the fill when value < 100.
```

Save to `src/components/ui/ProgressBar.jsx`.

- [ ] **Step 3.10: Create barrel export**

```js
// src/components/ui/index.js
export { default as Button } from './Button';
export { default as Card } from './Card';
export { default as Badge } from './Badge';
export { default as Input } from './Input';
export { default as Modal } from './Modal';
export { default as Skeleton } from './Skeleton';
export { default as EmptyState } from './EmptyState';
export { useToast, ToastContainer } from './Toast';
export { default as ProgressBar } from './ProgressBar';
```

- [ ] **Step 3.11: Verify build**

```bash
cd "D:/Projects/AltairGO-Platform"
npm run build 2>&1 | tail -20
```

Expected: build succeeds with no errors. Fix any import/export issues.

- [ ] **Step 3.12: Commit component library**

```bash
git add src/components/ui/
git commit -m "feat: add shared UI component library (Button, Card, Badge, Input, Modal, Skeleton, EmptyState, Toast, ProgressBar)"
```

---

## Task 4: Redesign HomePage

**Tool:** Claude Code + `mcp__magic__21st_magic_component_builder`

- [ ] **Step 4.1: Read current HomePage.jsx**

Read `src/pages/HomePage.jsx` to understand current layout and links.

- [ ] **Step 4.2: Build new HomePage via 21st.dev MCP**

Prompt for `mcp__magic__21st_magic_component_builder`:
```
Redesign a React HomePage for AltairGO — an AI travel planning platform for India.

Import from '../components/ui': Button, Card, Badge
Import from '../design-system/animations': fadeIn, slideUp, staggerChildren
Use Framer Motion (motion.div, AnimatePresence).
Use React Router: import { Link, useNavigate } from 'react-router-dom'

Sections:

1. HERO — Full-width, min-height 100vh, gradient background (from var(--color-primary) to #7C3AED).
   - Large centered text: "Plan Your Perfect India Trip" (text-display class, white)
   - Subtitle: "AI-powered itineraries with real costs, real routes, real India" (text-body-lg, white/80)
   - Two CTAs: primary Button "Start Planning →" (links to /planner) + ghost Button "Explore Destinations" (links to /discover)
   - Animate in with slideUp variant

2. FEATURES — 3-column card grid (responsive: 1 col mobile, 3 col desktop)
   Cards with: emoji icon, bold title, description text.
   Features: "AI Itinerary" / "Real Costs" / "Live Weather" / "Day Briefings" / "Booking Automation" / "Crowd Alerts"
   Use Card component with hover=true

3. HOW IT WORKS — 3-step horizontal flow with numbered circles
   Steps: "1. Tell us your dream trip" / "2. AI builds your itinerary" / "3. Track, book, and go"

4. BLOGS TEASER — "Travel Inspiration" heading + 3 blog card placeholders (no API call, static)

5. CTA BANNER — Full-width indigo gradient banner: "Ready to explore India?" + Button "Plan My Trip Free →"

6. FOOTER — Simple: logo text + nav links (About, Blogs, Discover, Login) + copyright

Keep all existing React Router <Link> destinations intact. Do not change any URL paths.
Use CSS variables from the design token system, not hardcoded colors.
```

- [ ] **Step 4.3: Save output and verify links**

Save to `src/pages/HomePage.jsx`. Check that:
- `/planner` link is present
- `/discover` link is present  
- No hardcoded hex colors

- [ ] **Step 4.4: Commit**

```bash
git add src/pages/HomePage.jsx
git commit -m "redesign: premium landing page for HomePage"
```

---

## Task 5: Redesign PlannerPage

**Tool:** Claude Code + 21st.dev MCP

- [ ] **Step 5.1: Read current PlannerPage.jsx**

Read `src/pages/PlannerPage.jsx` fully to understand: form fields, state shape, and `handleSubmit` signature (must be preserved exactly).

- [ ] **Step 5.2: Build redesigned PlannerPage via 21st.dev MCP**

Prompt:
```
Redesign a React PlannerPage for AltairGO. This is a multi-step trip planning wizard.

Import from '../components/ui': Button, Input, Card, Badge, ProgressBar
Keep all existing state variables and the handleSubmit function — only redesign the JSX.

The form has these fields (preserve all state bindings):
- originCity (text input)
- selectedDestinations (multi-select from suggestions)
- budget (number input, Indian Rupees)
- duration (number, days)
- travelers (number)
- style (select: budget/standard/premium)
- travelerType (select: solo_male/solo_female/couple/family/group)
- travelMonth (select: 1-12)
- interests (multi-checkbox: heritage/adventure/food/nature/culture/shopping)

Visual design:
- 3-step wizard with ProgressBar showing progress
- Step 1: Where & When (origin, destinations, travel month, duration)
- Step 2: Budget & Group (budget, travelers, style, traveler type)
- Step 3: Interests & Review (interests checkboxes, summary card, submit)
- Back/Next buttons between steps
- Final step: "Generate My Trip" Button (primary, large, full width)

Each step in a Card component with padding='lg'.
Destination suggestions: show as Badge list, clicking adds to selection.
Budget field: show estimated tier (budget/mid/luxury) based on value.
Preserve the EXACT same onSubmit handler call — don't change what gets submitted to the API.

Use CSS variables, not hardcoded colors.
```

- [ ] **Step 5.3: Verify form submission still works**

```bash
cd "D:/Projects/AltairGO-Platform"
npm run dev
```

Test the planner form locally: fill it out, submit, confirm it reaches `/generating` page.

- [ ] **Step 5.4: Commit**

```bash
git add src/pages/PlannerPage.jsx
git commit -m "redesign: multi-step wizard UI for PlannerPage"
```

---

## Task 6: Redesign DashboardPage + TripViewerPage

**Tool:** Claude Code

- [ ] **Step 6.1: Redesign DashboardPage**

Use `mcp__magic__21st_magic_component_builder`:
```
Redesign a React DashboardPage (trip list) for AltairGO.

Import from '../components/ui': Card, Badge, Button, Skeleton, EmptyState
Keep all existing data fetching, state, and navigation logic intact. Only replace JSX.

Current page shows: stats strip (trips count, total invested, destinations) + trip grid.

New design:
- Page header: "My Trips" + "New Trip" Button (primary, links to /planner)
- Stats strip: 3 stat cards in a row — each has a large number, label below, subtle background
- Trip grid: responsive (1 col mobile, 2 col tablet, 3 col desktop), Card with hover=true
- Each trip card: trip title bold, destination + duration as text-caption, total cost as Badge (success), "View Trip →" button
- Loading state: 6 Skeleton cards in the same grid
- Empty state: EmptyState component with ✈️ icon, "No trips yet", "Plan your first trip" button

Use CSS variables, not hardcoded colors. Preserve all onClick and Link destinations.
```

Save to `src/pages/trips/DashboardPage.jsx`.

- [ ] **Step 6.2: Redesign TripViewerPage tab layout**

Open `src/pages/trips/TripViewerPage.jsx`. The tabs are already extracted (ItineraryTab, BookingsTab, etc.). 

Update the tab navigation bar using the Tabs component from the UI library (or build inline):

```jsx
// Replace existing tab buttons with this pattern:
const TABS = [
  { id: 'itinerary', label: '🗺 Itinerary' },
  { id: 'bookings',  label: '🏨 Bookings' },
  { id: 'expenses',  label: '💰 Expenses' },
  { id: 'readiness', label: '✅ Readiness' },
  { id: 'notes',     label: '📝 Notes' },
  { id: 'summary',   label: '📊 Summary' },
];

// Tab bar:
<div style={{ display: 'flex', gap: 'var(--space-1)', borderBottom: '1px solid var(--color-border)', marginBottom: 'var(--space-6)' }}>
  {TABS.map(tab => (
    <button
      key={tab.id}
      onClick={() => setActiveTab(tab.id)}
      style={{
        padding: 'var(--space-2) var(--space-4)',
        borderBottom: activeTab === tab.id ? '2px solid var(--color-primary)' : '2px solid transparent',
        color: activeTab === tab.id ? 'var(--color-primary)' : 'var(--color-text-muted)',
        fontWeight: activeTab === tab.id ? 'var(--font-weight-semibold)' : 'var(--font-weight-normal)',
        background: 'none', border: 'none', cursor: 'pointer',
        transition: 'var(--transition-fast)',
      }}
    >
      {tab.label}
    </button>
  ))}
</div>
```

- [ ] **Step 6.3: Commit**

```bash
git add src/pages/trips/DashboardPage.jsx src/pages/trips/TripViewerPage.jsx
git commit -m "redesign: DashboardPage trip grid and TripViewerPage tab navigation"
```

---

## Task 7: Redesign Auth Pages

**Tool:** Claude Code + 21st.dev MCP

- [ ] **Step 7.1: Build redesigned auth pages via 21st.dev MCP**

Prompt for LoginPage:
```
Redesign a React LoginPage for AltairGO.

Import from '../../components/ui': Button, Input, Card
Keep all existing state (email, password) and the handleSubmit function exactly as-is. Only replace JSX.

Layout: Split panel — left 40% is a gradient panel (var(--color-primary) → #7C3AED) with logo text "AltairGO" and tagline "AI-powered travel for India". Right 60% is the login form.
On mobile: single column, form only.

Form in a centered Card (variant='elevated', padding='lg'):
- "Welcome back" heading (text-h2)
- Email Input with label="Email address"
- Password Input with type="password", label="Password"
- "Forgot password?" link (right-aligned, text-sm, var(--color-primary))
- Login Button (variant='primary', full width, size='lg')
- "Don't have an account? Sign up" link at bottom (Link to /register)

Preserve all existing form state bindings and onSubmit handler.
Use CSS variables.
```

Save to `src/pages/auth/LoginPage.jsx`.

Repeat similarly for `RegisterPage.jsx` with fields: name, email, password, confirm password.

- [ ] **Step 7.2: Commit**

```bash
git add src/pages/auth/
git commit -m "redesign: premium split-panel auth pages"
```

---

## Task 8: Redesign Remaining Pages

**Tool:** Claude Code + 21st.dev MCP

Apply the same redesign approach (read → MCP prompt → save → verify) to:

- [ ] **Step 8.1: BlogsPage** — editorial grid, category filter badges, Card for each post
- [ ] **Step 8.2: DiscoverPage** — destination cards grid with budget badge, seasonal info, Card hover

For each:
1. Read current file to understand data shape and handlers
2. Use `mcp__magic__21st_magic_component_builder` with similar prompt structure to Task 4-7
3. Preserve all API calls, state, and navigation logic
4. Save and verify build

- [ ] **Step 8.3: Commit**

```bash
git add src/pages/BlogsPage.jsx src/pages/DiscoverPage.jsx
git commit -m "redesign: BlogsPage editorial grid and DiscoverPage destination cards"
```

---

## Task 9: Activity Reorder UI (Depends on Track C Task 4)

**Tool:** Claude Code  
**Prerequisite:** Track C Task 4 must be complete (reorder endpoint exists at `POST /api/trip/:id/reorder-activity`)

- [ ] **Step 9.1: Add drag-to-reorder to ItineraryTab**

Open `src/pages/trips/tabs/ItineraryTab.jsx`. Read it fully.

Add drag-and-drop reorder using Framer Motion's `Reorder` component (already installed):

```jsx
import { Reorder } from 'framer-motion';

// Replace activities list rendering with:
<Reorder.Group
  axis="y"
  values={activities}
  onReorder={async (newOrder) => {
    const fromIndex = activities.findIndex((a, i) => a !== newOrder[i]);
    const toIndex = newOrder.findIndex((a, i) => a !== activities[i]);
    if (fromIndex === -1 || toIndex === -1) return;

    // Optimistic update
    onReorderActivities(dayIndex, newOrder);

    // Persist to API
    const resp = await fetch(`/api/trip/${tripId}/reorder-activity`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({ day_index: dayIndex, from_index: fromIndex, to_index: toIndex }),
    });
    if (!resp.ok) {
      // Revert on error
      onReorderActivities(dayIndex, activities);
    }
  }}
>
  {activities.map((activity) => (
    <Reorder.Item key={activity.name} value={activity} style={{ cursor: 'grab' }}>
      {/* existing activity card JSX */}
    </Reorder.Item>
  ))}
</Reorder.Group>
```

Add `onReorderActivities` prop to `ItineraryTab` and wire it in `TripViewerPage.jsx`:

```jsx
// In TripViewerPage.jsx
const handleReorderActivities = (dayIndex, newActivities) => {
  setTripData(prev => {
    const itinerary = [...(prev.itinerary_json?.itinerary || [])];
    itinerary[dayIndex] = { ...itinerary[dayIndex], activities: newActivities };
    return { ...prev, itinerary_json: { ...prev.itinerary_json, itinerary } };
  });
};
```

- [ ] **Step 9.2: Commit**

```bash
cd "D:/Projects/AltairGO-Platform"
git add src/pages/trips/tabs/ItineraryTab.jsx src/pages/trips/TripViewerPage.jsx
git commit -m "feat: add drag-to-reorder activities in itinerary tab"
```

---

## Task 10: Final Build Verification

- [ ] **Step 10.1: Production build**

```bash
cd "D:/Projects/AltairGO-Platform"
npm run build 2>&1
```

Expected: build succeeds, no TypeScript/lint errors.

- [ ] **Step 10.2: Audit token usage**

```bash
grep -r "bg-indigo\|text-gray\|#4F46\|#F59E\|color: '#" src/pages/ src/components/ui/ | grep -v "design-system"
```

Expected: zero or near-zero results — all colors now use CSS variables.

- [ ] **Step 10.3: Commit**

```bash
git add .
git commit -m "feat: complete frontend visual identity overhaul - design tokens, component library, page redesigns"
```

---

## Self-Review Checklist

- [x] Spec coverage: design tokens ✓, component library ✓ (9 components), all 8 page redesigns ✓, activity reorder UI ✓
- [x] No placeholders — all MCP prompts are complete and specific
- [x] Component barrel export defined before pages import from it
- [x] All pages preserve existing API calls, state, and navigation
- [x] Track C Task 4 dependency noted for Task 9
- [x] CSS variable names consistent: `--color-primary`, `--color-text`, etc. used everywhere
- [x] Framer Motion `Reorder` available in existing deps (no new installs needed)
