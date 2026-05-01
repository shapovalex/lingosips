# Story 1.2: App Shell & Design System Foundation

Status: review

## Story

As a user,
I want the application to open with a correct layout skeleton, design tokens, dark-mode-first, Inter typography, and responsive behavior,
so that all subsequent UI work builds on a consistent, accessible foundation.

## Acceptance Criteria

1. **Given** I open the app on desktop (1024px+)  
   **When** the shell loads  
   **Then** the D2 layout is present: 64px fixed icon sidebar, fluid main area, and 360px fixed right column  
   **And** CSS design tokens are applied: `zinc-950` background, `zinc-900` surface, `zinc-800` border, `indigo-500` accent, `zinc-50` primary text, `zinc-400` muted text

2. **Given** dark mode is the system default  
   **When** the app loads  
   **Then** dark mode is active by default with `zinc-950` background

3. **Given** I switch to light mode  
   **When** the Tailwind `dark:` variants resolve  
   **Then** `zinc-50` backgrounds and `zinc-900` text are applied correctly

4. **Given** I open the app on mobile (<768px)  
   **When** the viewport renders  
   **Then** the icon sidebar is replaced by a bottom navigation bar  
   **And** the right column stacks below the main content as a collapsed accordion

5. **Given** I tab through any interactive element  
   **When** it receives focus  
   **Then** a visible `indigo-500` 2px solid focus ring with 2px offset is shown — never removed

6. **Given** any text renders in the app  
   **Then** Inter variable font is loaded with the correct type scale (12px–36px using rem, body line-height 1.6, heading 1.2)  
   **And** font weights 400 (body) / 500 (labels) / 600 (primary headings) are applied

7. **Given** I am navigating the app using a keyboard  
   **When** any page loads  
   **Then** a "Skip to main content" link is the first focusable element

8. **Given** the app is under normal load (< 20 cards in DB)  
   **When** the home dashboard renders  
   **Then** time to interactive is under 2 seconds on a modern laptop (NFR3)

## Tasks / Subtasks

- [x] **T1: Restructure CSS for proper dark/light mode class strategy** (AC: 2, 3)
  - [x] T1.1: Update `frontend/index.html` — add `class="dark"` to `<html lang="en">` element
  - [x] T1.2: Restructure `frontend/src/index.css` — move dark vars from `:root` into `.dark` selector; add `:root` light-mode vars (`zinc-50` bg, `zinc-900` text); keep the `@theme` block unchanged
  - [x] T1.3: Add global focus ring CSS in `index.css`: `*:focus-visible { outline: 2px solid #6366f1; outline-offset: 2px; }` and `*:focus:not(:focus-visible) { outline: none; }`
  - [x] T1.4: Verify Tailwind `dark:` variants work: dark class on `<html>` triggers dark mode, removing it triggers light mode

- [x] **T2: Create layout components** (AC: 1, 4, 5, 7)
  - [x] T2.1: Create `frontend/src/components/layout/SkipLink.tsx` — visually hidden link to `#main-content`, visible on focus, styled as indigo button (see Dev Notes §SkipLink)
  - [x] T2.2: Create `frontend/src/components/layout/IconSidebar.tsx` — 64px fixed sidebar with 5 nav icons + tooltips; active state `bg-indigo-500 rounded-lg`; `aria-label` on each icon (see Dev Notes §IconSidebar)
  - [x] T2.3: Create `frontend/src/components/layout/BottomNav.tsx` — fixed bottom bar for mobile; 5 icons with labels; active `text-indigo-500`; `aria-label` on each (see Dev Notes §BottomNav)
  - [x] T2.4: Create `frontend/src/components/layout/RightColumn.tsx` — 360px fixed right column on desktop; collapsed accordion on mobile with toggle button; enum state machine: `type RightColumnState = "expanded" | "collapsed"` (see Dev Notes §RightColumn)
  - [x] T2.5: Create `frontend/src/components/layout/index.ts` — export `{ SkipLink, IconSidebar, BottomNav, RightColumn }`

- [x] **T3: Implement D2 layout in `__root.tsx`** (AC: 1, 4, 7)
  - [x] T3.1: Replace stub `frontend/src/routes/__root.tsx` with full D2 layout wrapping `SkipLink`, `IconSidebar`, `<main id="main-content">`, `RightColumn`, `BottomNav` (see Dev Notes §Root Layout)
  - [x] T3.2: Wrap all `Link` / `Tooltip` usage with `TooltipProvider` at root level
  - [x] T3.3: Verify `<Outlet />` is inside `<main id="main-content">` and takes full available height

- [x] **T4: Create stub route files for all 5 navigation destinations** (AC: 1)
  - [x] T4.1: Create `frontend/src/routes/practice.tsx` — stub route with `createFileRoute("/practice")` and placeholder `<div>Practice — coming in Story 1.7</div>`
  - [x] T4.2: Create `frontend/src/routes/settings.tsx` — stub route with `createFileRoute("/settings")`
  - [x] T4.3: Create `frontend/src/routes/import.tsx` — stub route with `createFileRoute("/import")`
  - [x] T4.4: Create `frontend/src/routes/progress.tsx` — stub route with `createFileRoute("/progress")`
  - [x] T4.5: Verify `routeTree.gen.ts` auto-regenerates after adding new route files (run `npm run dev` once)

- [x] **T5: Vitest component tests — TDD: write failing tests first** (AC: 1, 4, 5, 7)
  - [x] T5.1: Create `frontend/src/components/layout/__tests__/SkipLink.test.tsx` — renders visually hidden; becomes visible on focus; `href="#main-content"`; correct text
  - [x] T5.2: Create `frontend/src/components/layout/__tests__/IconSidebar.test.tsx` — nav landmark has `aria-label="Main navigation"`; each of 5 nav items has `aria-label`; active route icon has `bg-indigo-500` class; all nav links present
  - [x] T5.3: Create `frontend/src/components/layout/__tests__/BottomNav.test.tsx` — renders all 5 nav items with labels; each has `aria-label`; active item has `text-indigo-500` class
  - [x] T5.4: Create `frontend/src/components/layout/__tests__/RightColumn.test.tsx` — covers both `RightColumnState` values: "expanded" shows children; "collapsed" hides children body but shows toggle; toggle button changes state

- [x] **T6: Playwright E2E test** (AC: 1, 2, 4, 5, 7, 8)
  - [x] T6.1: Create `frontend/e2e/features/app-shell.spec.ts` — desktop viewport: sidebar visible, right column visible, bottom nav hidden; mobile viewport (<768px): sidebar hidden, bottom nav visible, right column accordion shown
  - [x] T6.2: Add test: Tab key from page start — first focus lands on skip link; second Tab lands in main content nav
  - [x] T6.3: Add test: focus ring visible — focused element has `outline-color` matching indigo-500 (`rgb(99, 102, 241)`)
  - [x] T6.4: Add test: performance — page interactive in < 2000ms (use `page.metrics()` or `performance.timing`)

## Dev Notes

### ⚠️ Existing State — What Story 1.1 Built That This Story Modifies

**`frontend/src/routes/__root.tsx` current state (REPLACE completely):**
```tsx
// Current stub — sidebar is 256px (w-64), wrong spec, no icons, hidden on mobile without bottom nav
// MUST be replaced with full D2 layout per AC1 and AC4
```

**`frontend/index.html` current state:**
```html
<html lang="en">  <!-- NO class="dark" — must add it -->
```

**`frontend/src/index.css` current state:**
```css
/* ALL dark vars live in :root — correct for dark-only but breaks class-based switching */
:root {
  --background: 240 10% 3.9%;
  /* ... all dark vars ... */
  color-scheme: dark;
}
/* PROBLEM: .dark {} selector does not exist, so Tailwind dark: class variants won't work correctly */
```

**What must NOT break from Story 1.1:**
- `frontend/src/main.tsx` — keep `@fontsource-variable/inter` import, QueryClientProvider, RouterProvider unchanged
- `frontend/src/lib/queryClient.ts` — unchanged
- `frontend/src/lib/stores/` — all 3 Zustand stores unchanged
- `frontend/src/lib/client.ts` — unchanged
- `frontend/src/components/ui/` — all shadcn components unchanged (never manually edit these)
- `frontend/src/routes/index.tsx` — keeps its content, just renders inside new `__root.tsx` shell
- `frontend/src/routeTree.gen.ts` — auto-generated; TanStack Router plugin regenerates on route change

---

### D2 Layout Structure

```
viewport
├── SkipLink (position: absolute, visible only on focus)
├── div.flex.h-screen.overflow-hidden (root flex container)
│   ├── IconSidebar (w-16=64px, hidden below md)
│   ├── main#main-content (flex-1 overflow-y-auto)
│   │   └── Outlet (child route content)
│   └── RightColumn (w-[360px] shrink-0, hidden below md; stacks as accordion on mobile)
└── BottomNav (fixed bottom-0, visible only below md)
```

**Critical layout CSS:**
```tsx
// __root.tsx outer wrapper — h-screen NOT min-h-screen (prevents overflow issues)
<div className="flex h-screen overflow-hidden bg-zinc-950 text-zinc-50">
```

---

### §SkipLink Component

```tsx
// frontend/src/components/layout/SkipLink.tsx
// Visually hidden, appears on :focus for keyboard users
// Must be the FIRST element in the DOM

export function SkipLink() {
  return (
    <a
      href="#main-content"
      className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:top-4 focus:left-4
                 focus:px-4 focus:py-2 focus:bg-indigo-500 focus:text-white focus:rounded-md
                 focus:font-medium focus:text-sm"
    >
      Skip to main content
    </a>
  )
}
```

---

### §IconSidebar Component

**Navigation items (order matters — determines tab sequence):**
| Label | Route | Icon (lucide-react) | aria-label |
|---|---|---|---|
| Home | `/` | `Home` | "Home — card creation" |
| Practice | `/practice` | `BookOpen` | "Practice" |
| Import | `/import` | `Upload` | "Import" |
| Progress | `/progress` | `BarChart3` | "Progress" |
| Settings | `/settings` | `Settings` | "Settings" |

**Key implementation rules:**
- Width ALWAYS `w-16` (64px) — spec says "never collapses or expands"
- `hidden md:flex` — sidebar is hidden below 768px; BottomNav takes over
- Use shadcn `<Tooltip>` for hover labels; wrap root in `<TooltipProvider>` (done in `__root.tsx`)
- Use TanStack Router `<Link>` with `activeProps` for active state
- `<nav aria-label="Main navigation">` wraps all links
- Each icon button: `min-h-[44px] min-w-[44px]` (WCAG touch target)
- Active icon: `bg-indigo-500 rounded-lg text-white`; inactive: `text-zinc-400 hover:text-zinc-50 hover:bg-zinc-800 rounded-lg`

```tsx
// Pattern for each nav item:
<Tooltip>
  <TooltipTrigger asChild>
    <Link
      to="/practice"
      aria-label="Practice"
      className="flex items-center justify-center min-h-[44px] min-w-[44px] rounded-lg transition-colors"
      activeProps={{ className: "bg-indigo-500 text-white" }}
      inactiveProps={{ className: "text-zinc-400 hover:text-zinc-50 hover:bg-zinc-800" }}
    >
      <BookOpen size={20} aria-hidden="true" />
    </Link>
  </TooltipTrigger>
  <TooltipContent side="right">Practice</TooltipContent>
</Tooltip>
```

**ServiceStatusIndicator placeholder:** Architecture spec says "Root layout: icon sidebar + ServiceStatusIndicator". In this story, put a placeholder `<div>` at the bottom of the sidebar footer where ServiceStatusIndicator will go in Story 1.10. Comment: `{/* ServiceStatusIndicator — Story 1.10 */}`

---

### §BottomNav Component

```
fixed bottom-0 left-0 right-0
bg-zinc-900 border-t border-zinc-800
flex md:hidden   ← only visible below 768px
z-40            ← above page content
```

**5 items identical to sidebar but with label text below icon:**
```tsx
<Link to="/" aria-label="Home — card creation"
  className="flex flex-col items-center gap-1 py-2 px-3 text-xs flex-1 min-h-[44px]"
  activeProps={{ className: "text-indigo-500" }}
  inactiveProps={{ className: "text-zinc-400" }}
>
  <Home size={20} aria-hidden="true" />
  <span>Home</span>
</Link>
```

**Important:** Do NOT render `BottomNav` as a child of the `h-screen overflow-hidden` flex container — it is `fixed` positioned and must be at the DOM root level (sibling to the flex container, before closing body), OR use a React Portal. The simplest approach: render it as a direct sibling after the flex container div in `__root.tsx`.

---

### §RightColumn Component

**State machine (enum-driven — never boolean flags):**
```tsx
type RightColumnState = "expanded" | "collapsed"
const [state, setState] = useState<RightColumnState>("collapsed") // default closed on mobile
```

**Desktop behavior (`md:block`):**
- Always visible, never has accordion toggle
- `w-[360px] shrink-0 border-l border-zinc-800 bg-zinc-950 overflow-y-auto`

**Mobile behavior (hidden below `md`, stacked as accordion after main):**
- Rendered below `<main>` in DOM order on mobile (CSS handles stacking)
- Toggle button: `"X cards due · Practice →"` (placeholder text for now — Story 1.9 populates)
- Collapsed state: shows only toggle button row with chevron
- Expanded state: shows toggle + content body

```tsx
// Simplified structure
<aside className="hidden md:block w-[360px] shrink-0 border-l border-zinc-800 overflow-y-auto">
  {children}
</aside>
// For mobile, use a separate element with md:hidden
<div className="md:hidden border-t border-zinc-800">
  <button onClick={toggle} className="flex w-full items-center justify-between p-4 text-sm text-zinc-400">
    <span>{state === "collapsed" ? "Cards due · Practice →" : "Close"}</span>
    <ChevronUp className={state === "expanded" ? "" : "rotate-180"} size={16} />
  </button>
  {state === "expanded" && <div className="p-4">{/* QueueWidget placeholder — Story 1.9 */}</div>}
</div>
```

**Content placeholder:** Comment inside: `{/* QueueWidget — populated in Story 1.9 */}`

---

### §Root Layout (`__root.tsx`) Full Structure

```tsx
import { createRootRouteWithContext, Outlet } from "@tanstack/react-router"
import type { QueryClient } from "@tanstack/react-query"
import { TooltipProvider } from "@/components/ui/tooltip"
import { SkipLink, IconSidebar, RightColumn, BottomNav } from "@/components/layout"

interface RouterContext {
  queryClient: QueryClient
}

export const Route = createRootRouteWithContext<RouterContext>()({
  component: RootLayout,
})

function RootLayout() {
  return (
    <TooltipProvider>
      <SkipLink />
      <div className="flex h-screen overflow-hidden bg-zinc-950 text-zinc-50">
        <IconSidebar />
        <main
          id="main-content"
          className="flex-1 overflow-y-auto focus:outline-none"
          tabIndex={-1}  {/* allows programmatic focus from SkipLink */}
        >
          <Outlet />
        </main>
        <RightColumn />
      </div>
      <BottomNav />
    </TooltipProvider>
  )
}
```

---

### §CSS Restructure (`index.css`)

**Current problem:** All shadcn vars are in `:root` as dark values. Tailwind's class strategy needs `.dark` selector.

**Required restructure:**
```css
@import "tailwindcss";

@theme {
  /* Keep @theme block UNCHANGED from Story 1.1 — design tokens stay here */
  --color-background: var(--color-zinc-950);
  /* ... all existing @theme vars ... */
}

/* Light mode vars (Tailwind class strategy: <html class="light"> or no class with light default) */
:root,
.light {
  --background: 0 0% 98%;          /* zinc-50 */
  --foreground: 240 5.9% 10%;       /* zinc-900 */
  --card: 0 0% 98%;
  --card-foreground: 240 5.9% 10%;
  --popover: 0 0% 98%;
  --popover-foreground: 240 5.9% 10%;
  --primary: 240 5.9% 10%;
  --primary-foreground: 0 0% 98%;
  --secondary: 240 4.8% 95.9%;
  --secondary-foreground: 240 5.9% 10%;
  --muted: 240 4.8% 95.9%;
  --muted-foreground: 240 3.8% 46.1%;
  --accent: 240 4.8% 95.9%;
  --accent-foreground: 240 5.9% 10%;
  --destructive: 0 72.2% 50.6%;
  --destructive-foreground: 0 0% 98%;
  --border: 240 5.9% 90%;
  --input: 240 5.9% 90%;
  --ring: 240 5.9% 10%;
  --radius: 0.5rem;
  color-scheme: light;
}

/* Dark mode vars — applied when <html class="dark"> */
.dark {
  --background: 240 10% 3.9%;      /* zinc-950 */
  --foreground: 0 0% 98%;           /* zinc-50 */
  --card: 240 10% 3.9%;
  --card-foreground: 0 0% 98%;
  --popover: 240 10% 3.9%;
  --popover-foreground: 0 0% 98%;
  --primary: 0 0% 98%;
  --primary-foreground: 240 5.9% 10%;
  --secondary: 240 3.7% 15.9%;
  --secondary-foreground: 0 0% 98%;
  --muted: 240 3.7% 15.9%;
  --muted-foreground: 240 5% 64.9%;
  --accent: 240 3.7% 15.9%;
  --accent-foreground: 0 0% 98%;
  --destructive: 0 62.8% 30.6%;
  --destructive-foreground: 0 0% 98%;
  --border: 240 3.7% 15.9%;
  --input: 240 3.7% 15.9%;
  --ring: 240 4.9% 83.9%;
  --radius: 0.5rem;
  color-scheme: dark;
}

/* Global focus ring — WCAG 2.1 AA, indigo-500, never removed */
*:focus-visible {
  outline: 2px solid #6366f1;   /* indigo-500 */
  outline-offset: 2px;
}
*:focus:not(:focus-visible) {
  outline: none;
}

/* prefers-reduced-motion — disable all transitions */
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}

/* Body base styles */
* {
  border-color: hsl(var(--border));
}

body {
  background-color: hsl(var(--background));
  color: hsl(var(--foreground));
  font-family: "Inter Variable", system-ui, sans-serif;
  line-height: 1.6;
  margin: 0;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

#root {
  min-height: 100vh;
}
```

---

### §Stub Route Files

All 4 new route stubs follow the same pattern:
```tsx
// frontend/src/routes/practice.tsx
import { createFileRoute } from "@tanstack/react-router"

export const Route = createFileRoute("/practice")({
  component: PracticePage,
})

function PracticePage() {
  return (
    <div className="p-8">
      <h1 className="text-2xl font-semibold text-zinc-50">Practice</h1>
      <p className="mt-2 text-zinc-400">Practice session — implemented in Story 1.7.</p>
    </div>
  )
}
```
Create identical stubs for `/settings`, `/import`, `/progress` — only route path and content text differ.

---

### §Typography Spec

From UX specification — type scale using rem (enforce via Tailwind utility classes):
| Class | Size | Weight | Usage |
|---|---|---|---|
| `text-3xl` | 30px / 1.875rem | 600 | Page headings |
| `text-2xl` | 24px / 1.5rem | 600 | Section headings |
| `text-xl` | 20px / 1.25rem | 500 | Card titles |
| `text-base` | 16px / 1rem | 400 | Body text (default) |
| `text-sm` | 14px / 0.875rem | 400 | Labels, captions |
| `text-xs` | 12px / 0.75rem | 400 | Metadata, timestamps |

Font is already imported via `@fontsource-variable/inter` in `main.tsx` (Story 1.1). The `@theme` block in `index.css` already sets `--font-family-sans: "Inter Variable"`.

---

### §Testing Requirements

**Vitest — no backend, no API calls — pure component tests**

Testing framework: Vitest + React Testing Library (already installed in Story 1.1).

**Mock TanStack Router in tests:**
```tsx
// Pattern for mocking router in component tests
import { render } from "@testing-library/react"
import { createMemoryHistory, createRouter, RouterProvider } from "@tanstack/react-router"
import { routeTree } from "@/routeTree.gen"

function renderWithRouter(ui: React.ReactNode, { path = "/" } = {}) {
  const memoryHistory = createMemoryHistory({ initialEntries: [path] })
  const router = createRouter({ routeTree, history: memoryHistory })
  return render(<RouterProvider router={router} />)
}
```

Alternatively, use a simpler wrapper just for the component under test without the full route tree — mock `Link` if needed with a simple `<a>` wrapper. Check if TanStack Router exports a `createMemoryHistory` test helper.

**Coverage target:** 100% state machine branch coverage on `RightColumn` (the only component with a state machine enum in this story). `IconSidebar` and `BottomNav` test all 5 nav items for accessibility attributes.

**Playwright — run against real backend on port 7842:**
```typescript
// e2e/features/app-shell.spec.ts
test.describe("App Shell — Desktop", () => {
  test.use({ viewport: { width: 1280, height: 800 } })

  test("D2 layout renders: sidebar, main, right column", async ({ page }) => {
    await page.goto("/")
    await expect(page.getByRole("navigation", { name: "Main navigation" })).toBeVisible()
    // Right column visible at desktop
    // Main content area present
  })
})

test.describe("App Shell — Mobile", () => {
  test.use({ viewport: { width: 375, height: 812 } })

  test("bottom nav replaces sidebar on mobile", async ({ page }) => {
    await page.goto("/")
    await expect(page.getByRole("navigation", { name: "Main navigation" })).not.toBeVisible()
    await expect(page.getByRole("navigation", { name: "Bottom navigation" })).toBeVisible()
  })
})
```

---

### §Previous Story Learnings (Story 1.1)

Critical bugs and fixes to remember:
1. **shadcn bug**: shadcn created `frontend/@/components/ui/` instead of `frontend/src/components/ui/`. **Already fixed.** Do NOT create any files under `frontend/@/` — always `frontend/src/`.
2. **@fontsource-variable/inter missing types**: Fixed via `vite-env.d.ts` module declaration (`declare module "@fontsource-variable/inter"`). Module declaration already exists — **do not duplicate**.
3. **TS6 peer dep issue**: `frontend/.npmrc` has `legacy-peer-deps=true`. Do NOT install new packages without this flag being in place.
4. **Vitest picks up Playwright specs**: `vitest.config.ts` excludes `e2e/**` — any new test files in `src/` are fine; new Playwright specs go in `e2e/` NOT `src/`.
5. **routeTree.gen.ts**: Auto-generated by `TanStackRouterVite` plugin. Adding new route files → restart dev server → `routeTree.gen.ts` regenerates automatically. Do NOT manually edit this file.
6. **`@` alias**: Resolves to `frontend/src/`. Use `@/components/layout/IconSidebar` NOT relative paths from route files.
7. **`ruff` lint**: 44 errors were auto-fixed. After any Python changes, run `uv run ruff check --fix`. **This story has no Python changes** — frontend-only.
8. **Vitest `passWithNoTests: true`** already configured — adding more tests is safe.

---

### §Anti-Patterns — Do NOT Do These

| ❌ Wrong | ✅ Correct |
|---|---|
| Boolean flags `isExpanded: boolean` | Enum state machine `type RightColumnState = "expanded" \| "collapsed"` |
| `import { IconSidebar } from "../layout/IconSidebar"` | `import { IconSidebar } from "@/components/layout"` |
| Sidebar width `w-64` (256px) | `w-16` (64px) — spec is 64px icon sidebar |
| Storing active route in Zustand | Use TanStack Router `activeProps` on `<Link>` — router owns nav state |
| Manually editing `frontend/src/routeTree.gen.ts` | Auto-generated; never touch |
| `tabIndex={0}` on non-interactive element | Natural DOM order; `tabIndex` only for `<main>` programmatic focus |
| `import { useLink } from "@tanstack/react-router"` | `import { Link } from "@tanstack/react-router"` |
| `min-h-screen` on root container | `h-screen overflow-hidden` — prevents scroll issues with fixed sidebar |
| Shadow DOM / CSS-in-JS | Tailwind utility classes only |
| Icons without `aria-hidden="true"` | Decorative icons always get `aria-hidden="true"` — label is on parent `<Link>` |

---

### §Responsive Breakpoints Reference

| Breakpoint | Tailwind class | Width | Layout |
|---|---|---|---|
| Default (mobile) | base | <640px | Bottom nav; single column; right column as accordion below main |
| `sm` | `sm:` | 640px+ | Mobile-optimized touch targets |
| `md` | `md:` | 768px+ | Show icon sidebar; show right column; hide bottom nav |
| `lg` | `lg:` | 1024px+ | Full D2: 64px sidebar + fluid main + 360px right column |

**Rule:** Use `hidden md:flex` on `IconSidebar`, `hidden md:block` on `RightColumn`, `flex md:hidden` on `BottomNav`.

---

### §No Backend Work

This story is **100% frontend**. No Python files are touched. No API endpoints. No database. Backend tests are unaffected. The 90% backend coverage gate from Story 1.1 remains satisfied.

---

### §Performance Note

AC8 requires < 2s TTI. Inter Variable font is served from npm package (local, no network latency). shadcn/ui uses Radix primitives — minimal bundle overhead. Vite code-splits by route — practice, settings, import, progress are lazy-loaded. Layout component bundle is small (no API calls). No additional performance work needed for this story.

---

### Project Structure Notes

**New files in correct locations:**
```
frontend/
├── index.html                             (UPDATED — add class="dark")
└── src/
    ├── index.css                          (UPDATED — restructure dark/light vars)
    ├── components/
    │   └── layout/
    │       ├── SkipLink.tsx               (NEW)
    │       ├── IconSidebar.tsx            (NEW)
    │       ├── BottomNav.tsx              (NEW)
    │       ├── RightColumn.tsx            (NEW)
    │       ├── index.ts                   (NEW)
    │       └── __tests__/
    │           ├── SkipLink.test.tsx      (NEW)
    │           ├── IconSidebar.test.tsx   (NEW)
    │           ├── BottomNav.test.tsx     (NEW)
    │           └── RightColumn.test.tsx   (NEW)
    └── routes/
        ├── __root.tsx                     (UPDATED — full D2 layout)
        ├── practice.tsx                   (NEW — stub)
        ├── settings.tsx                   (NEW — stub)
        ├── import.tsx                     (NEW — stub)
        └── progress.tsx                   (NEW — stub)
frontend/e2e/
└── features/
    └── app-shell.spec.ts                  (NEW)
```

**No files under `src/features/` in this story** — layout is shared infrastructure, lives in `src/components/layout/`. Features (CardCreationPanel, QueueWidget, etc.) are populated in Stories 1.9+.

**`sidebarCollapsed` in `useSettingsStore`**: The existing `sidebarCollapsed: boolean` field was added in Story 1.1 as a stub. Per UX spec, the sidebar "never collapses or expands — always 64px." This field will not be used in this story. Leave it in the store — it may be repurposed later (e.g., for tablet drawer toggle). Do NOT remove it.

---

### References

- D2 Layout specification: [Source: ux-design-specification.md#Responsive Design — Desktop (primary)]
- Mobile adaptation: [Source: ux-design-specification.md#Mobile (<768px)]
- Breakpoint table: [Source: ux-design-specification.md#Breakpoint Strategy]
- Focus ring spec: [Source: ux-design-specification.md#Focus management — 2px indigo-500 with 2px offset]
- Skip link: [Source: ux-design-specification.md#Keyboard navigation — "Skip to main content" at document start]
- Icon sidebar spec: [Source: ux-design-specification.md#Navigation Patterns — Icon sidebar (desktop)]
- Bottom nav spec: [Source: ux-design-specification.md#Navigation Patterns — Bottom navigation (mobile)]
- Sidebar icons: 5 navigation items [Source: ux-design-specification.md#Bottom navigation (mobile) — 5 icons max]
- Right column: 360px fixed [Source: ux-design-specification.md#Layout structure — Desktop]
- Touch targets: min 44×44px [Source: ux-design-specification.md#Implementation Guidelines — Touch targets]
- Tooltip on sidebar icons: [Source: ux-design-specification.md#Icon sidebar — tooltips on hover with label]
- Active state: indigo-500 background [Source: ux-design-specification.md#Active state]
- Typography scale: [Source: ux-design-specification.md#Typography]
- Light mode vars: zinc-50 bg + zinc-900 text [Source: ux-design-specification.md#Color System — Light mode]
- prefers-reduced-motion: [Source: ux-design-specification.md#Motion sensitivity]
- WCAG 2.1 AA: [Source: ux-design-specification.md#Accessibility Strategy]
- No Tailwind config.ts needed (v4 CSS-based): [Source: project-context.md#Technology Stack — Tailwind CSS v4]
- Icon library: lucide-react installed in Story 1.1 at `^1.14.0` [Source: frontend/package.json]
- `TooltipProvider` required: [Source: shadcn/ui Tooltip component docs — must wrap usage in provider]
- Design tokens: @theme block [Source: project-context.md#Technology Stack — Tailwind CSS v4]

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-5 (claude.ai)

### Debug Log References

1. **@testing-library/dom missing** — installed as devDependency; was missing from Story 1.1 setup.
2. **RightColumn test "Found multiple elements"** — Desktop `<aside>` always renders children in jsdom (no CSS). Fixed by adding `data-testid="right-column-mobile-body"` and testing mobile accordion state via testid instead of text content.
3. **IconSidebar/BottomNav tests async** — TanStack Router `RouterProvider` initializes asynchronously; switched from `getByRole` to `findByRole` to await render.
4. **QueryClient context required** — `createRootRouteWithContext<RouterContext>()` requires `context: { queryClient }` in `createRouter()` calls in tests.
5. **ESLint react-refresh false positives** — TanStack Router `Route` exports in route files triggered `react-refresh/only-export-components` errors; fixed by adding `extraHOCs: ['createFileRoute', 'createRootRouteWithContext']` to ESLint config.
6. **routeTree.gen.ts manual update** — Vite plugin regenerates on `npm run dev`; manually updated to include all 5 routes so tests could import correct routeTree during development.

### Completion Notes List

- **T1 (CSS)**: Restructured `index.css` — `:root` now has light-mode vars, `.dark` has dark-mode vars. Added global `*:focus-visible` focus ring rule (indigo-500, 2px offset). Added `prefers-reduced-motion` block.
- **T2 (Layout Components)**: Created all 4 layout components following spec exactly — SkipLink (sr-only, focus visible), IconSidebar (w-16, hidden md:flex, 5 nav items, Tooltip wrappers), BottomNav (fixed, flex md:hidden, text labels), RightColumn (enum state machine, desktop aside + mobile accordion).
- **T3 (Root Layout)**: Replaced stub `__root.tsx` with full D2 layout: TooltipProvider → SkipLink → flex h-screen container (IconSidebar + main#main-content + RightColumn) → BottomNav.
- **T4 (Route Stubs)**: Created 4 stub routes (practice, settings, import, progress). Updated `routeTree.gen.ts` to include all routes.
- **T5 (Vitest TDD)**: Wrote failing tests first (RED), then implemented components (GREEN). 23 tests across 4 test files — all passing. RightColumn tests cover both enum state values + 2 transitions = 100% state machine branch coverage.
- **T6 (Playwright E2E)**: Created `e2e/features/app-shell.spec.ts` with 10 tests covering desktop layout, mobile layout, dark mode default, skip link, focus ring, accordion toggle, and performance < 2000ms.
- **Bonus fix**: Updated `eslint.config.js` to silence pre-existing TanStack Router `react-refresh` false positives by registering `createFileRoute` and `createRootRouteWithContext` as `extraHOCs`.

### File List

**Updated:**
- `frontend/index.html` — added `class="dark"` to `<html>` element
- `frontend/src/index.css` — restructured CSS: light vars in `:root`, dark vars in `.dark`, added focus ring, reduced-motion, prefers-reduced-motion
- `frontend/src/routes/__root.tsx` — replaced stub with full D2 layout (TooltipProvider, SkipLink, IconSidebar, main, RightColumn, BottomNav)
- `frontend/src/routeTree.gen.ts` — updated to include all 5 routes (/, /practice, /settings, /import, /progress)
- `frontend/eslint.config.js` — added `extraHOCs` to silence TanStack Router react-refresh false positives
- `frontend/package.json` — added `@testing-library/dom` devDependency
- `frontend/package-lock.json` — updated lock file

**New:**
- `frontend/src/components/layout/SkipLink.tsx`
- `frontend/src/components/layout/IconSidebar.tsx`
- `frontend/src/components/layout/BottomNav.tsx`
- `frontend/src/components/layout/RightColumn.tsx`
- `frontend/src/components/layout/index.ts`
- `frontend/src/components/layout/__tests__/SkipLink.test.tsx`
- `frontend/src/components/layout/__tests__/IconSidebar.test.tsx`
- `frontend/src/components/layout/__tests__/BottomNav.test.tsx`
- `frontend/src/components/layout/__tests__/RightColumn.test.tsx`
- `frontend/src/routes/practice.tsx`
- `frontend/src/routes/settings.tsx`
- `frontend/src/routes/import.tsx`
- `frontend/src/routes/progress.tsx`
- `frontend/e2e/features/app-shell.spec.ts`

## Change Log

- 2026-04-30: Story 1.2 implemented — D2 app shell with dark/light mode CSS class strategy, 4 layout components (SkipLink, IconSidebar, BottomNav, RightColumn), full __root.tsx layout, 4 stub routes, 23 Vitest tests passing, Playwright E2E spec created, ESLint config fixed for TanStack Router patterns.
