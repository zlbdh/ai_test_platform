---
name: page-layout
description: |
  Page layout design specialist covering page structure and layout strategies for websites, mobile apps, mini programs, and desktop apps.
  Provides CSS Grid/Flexbox templates, responsive breakpoint strategies, safe-area handling,
  navigation-pattern selection, common page layouts, and platform-specific constraints.

  Use when designing page structure, choosing navigation patterns, implementing responsive layouts,
  handling safe areas, or building specific page types such as dashboards, landing pages, and feeds.
---

# Page Layout Design Specialist

Covers four platforms: websites · mobile apps · mini programs · desktop apps.

> Complements `ui-design-system`: that skill handles colors, typography, animation, and style; this skill focuses on **page structure and spatial organization**.

---

# AI Workflow

## Step 1: Identify the Platform and Page Type

```text
Target platform?        Page type?
├─ 🌐 Website           ├─ Landing / marketing page
├─ 📱 iOS/Android app   ├─ Dashboard / administration
├─ 🔷 Mini program     ├─ List / feed
├─ 🖥️ Desktop app      ├─ Detail / form page
└─ 📐 Cross-platform   ├─ E-commerce / product catalog
                        └─ Content / blog / documentation
```

## Step 2: Choose a Layout Pattern (See the Decision Tree Below)
## Step 3: Apply Platform Conventions (See Platform Sections Below)
## Step 4: Implement Responsive Behavior (See Responsive Strategies Below)
## Step 5: Complete the Delivery Checklist

---

# CRITICAL — Mandatory Layout Rules

| Rule | Do | Avoid |
|------|------|------|
| Grid for page structure | Define main regions with `display: grid` | Overall layouts built with float/position |
| Flexbox inside components | Arrange children with `display: flex` | Nested grids for one-dimensional arrangements |
| Handle safe areas | Use `env(safe-area-inset-*)` | Ignoring notches, rounded corners, or home indicators |
| Keep content within the viewport | Use `overflow` + `max-width` | Horizontal overflow |
| Fix bottom action bars | Use `position: fixed/sticky` + padding-bottom | Bars hidden by the virtual keyboard |
| Semantic region elements | Use `<header>/<nav>/<main>/<aside>/<footer>` | Using `<div>` for everything |
| Touch targets ≥ 44pt | Provide sufficient button/link hit areas | Dense controls without spacing |

---

# 1. Layout Decision Tree

```text
How many layout dimensions are needed?
│
├─ Two (rows + columns) → CSS Grid
│   ├─ Page structure (Header/Sidebar/Main/Footer)
│   ├─ Product or card grids
│   ├─ Bento grids / dashboards
│   └─ Image galleries / masonry
│
├─ One (rows or columns) → Flexbox
│   ├─ Navigation bars (horizontal)
│   ├─ List items (icon + text + arrow)
│   ├─ Button groups (horizontal spacing)
│   ├─ Forms (vertical)
│   └─ Center alignment
│
└─ Document flow → Normal flow + max-width
    ├─ Blog posts
    └─ Long forms
```

---

# 2. Website / Web App Layouts

## 2.1 Page Type Reference

### Landing Page (Single-Column Flow)
```css
.landing {
  display: flex;
  flex-direction: column;
  align-items: center;
}
.landing-section {
  width: 100%;
  max-width: 1200px;
  padding: 80px 24px;
  margin: 0 auto;
}
/* Typical structure: Hero → Features → Social proof → CTA → FAQ → Footer */
```

### Dashboard (Sidebar + Content)
```css
.dashboard {
  display: grid;
  grid-template-columns: var(--sidebar-width, 260px) 1fr;
  grid-template-rows: var(--header-height, 64px) 1fr;
  grid-template-areas:
    "sidebar header"
    "sidebar main";
  min-height: 100vh;
}
.dashboard-sidebar { grid-area: sidebar; }
.dashboard-header  { grid-area: header; }
.dashboard-main    { grid-area: main; padding: 24px; overflow-y: auto; }

/* Collapsed sidebar */
.dashboard.collapsed { grid-template-columns: 64px 1fr; }

/* Mobile: sidebar becomes a drawer */
@media (max-width: 768px) {
  .dashboard { grid-template-columns: 1fr; grid-template-areas: "header" "main"; }
  .dashboard-sidebar { position: fixed; left: -260px; transition: left 0.3s; z-index: 100; }
  .dashboard-sidebar.open { left: 0; }
}
```

### Product Grid (Adaptive Column Count)
```css
.product-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 24px;
  padding: 24px;
}
/* Responsive without media queries */
```

### Bento Grid
```css
.bento {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  grid-auto-rows: 180px;
  gap: 16px;
}
.bento-wide  { grid-column: span 2; }
.bento-tall  { grid-row: span 2; }
.bento-large { grid-column: span 2; grid-row: span 2; }

@media (max-width: 768px) {
  .bento { grid-template-columns: repeat(2, 1fr); grid-auto-rows: 140px; }
  .bento-wide, .bento-large { grid-column: span 2; }
}
@media (max-width: 480px) {
  .bento { grid-template-columns: 1fr; }
  .bento-wide, .bento-large { grid-column: span 1; }
}
```

### Blog / Documentation (Centered Content + Sidebar TOC)
```css
.article-layout {
  display: grid;
  grid-template-columns: 1fr min(720px, calc(100% - 48px)) 1fr;
}
.article-layout > * { grid-column: 2; }
.article-layout > .full-bleed { grid-column: 1 / -1; }

/* With a TOC sidebar */
@media (min-width: 1200px) {
  .article-with-toc {
    grid-template-columns: 1fr min(720px, 100%) 240px;
    gap: 40px;
  }
  .toc { position: sticky; top: 80px; align-self: start; }
}
```

## 2.2 Choosing Navigation Patterns

| Pattern | Best for | Item count | Key CSS |
|------|---------|--------|---------|
| Horizontal navigation | Company sites/landing pages | 3–7 | `flex + justify-content` |
| Sidebar navigation | Dashboards/administration | 5–20+ | `grid-template-columns` |
| Hamburger menu | Mobile/many items | 5–15 | `position:fixed + transform` |
| Tabs | Content categories | 2–5 | `flex + border-bottom` |
| Breadcrumbs | Multiple hierarchy levels | -- | `flex + gap + ::before` |

## 2.3 Responsive Breakpoint Strategy

```css
/* Mobile first (recommended) */
/* Base styles = phone */
@media (min-width: 640px)  { /* Large phones/small tablets */ }
@media (min-width: 768px)  { /* Portrait tablets */ }
@media (min-width: 1024px) { /* Laptops */ }
@media (min-width: 1280px) { /* Desktop monitors */ }
@media (min-width: 1536px) { /* Large/2K displays */ }
```

```css
/* Container queries (component-level responsiveness, recommended in 2025) */
.card-container { container-type: inline-size; }

@container (min-width: 400px) {
  .card { flex-direction: row; /* Horizontal layout */ }
}
@container (max-width: 399px) {
  .card { flex-direction: column; /* Vertical stack */ }
}
```

## 2.4 Spacing System

```css
:root {
  /* Spacing based on 4px increments */
  --space-1:  4px;   --space-2:  8px;
  --space-3:  12px;  --space-4:  16px;
  --space-5:  20px;  --space-6:  24px;
  --space-8:  32px;  --space-10: 40px;
  --space-12: 48px;  --space-16: 64px;
  --space-20: 80px;  --space-24: 96px;

  /* Page padding */
  --page-padding: clamp(16px, 4vw, 80px);

  /* Maximum content widths */
  --max-width-sm: 640px;   /* Blog body */
  --max-width-md: 960px;   /* Standard content */
  --max-width-lg: 1200px;  /* Wide content */
  --max-width-xl: 1440px;  /* Extra-wide layout */
}
```

---

# 3. Mobile App Layouts

## 3.1 iOS vs. Android Layout Comparison

| Dimension | iOS (HIG) | Android (Material 3) |
|------|-----------|---------------------|
| **Navigation bar height** | 44pt (Large Title: 96pt) | 64dp (TopAppBar) |
| **Bottom bar height** | 49pt + safe-area | 80dp |
| **Bottom bar items** | 2–5 (recommend ≤5) | 3–5 (recommend 3–4) |
| **Status bar** | 47pt (notched display) | 24dp |
| **Minimum touch target** | 44×44pt | 48×48dp |
| **Margins** | 16pt | 16dp |
| **Title style** | Collapsible Large Title | Centered/left-aligned |
| **Back navigation** | ← button + swipe right | System back + ← button |

## 3.2 Safe-Area Handling

### CSS (WebView / Hybrid)
```css
/* Required viewport setting */
/* <meta name="viewport" content="..., viewport-fit=cover"> */

:root {
  --sat: env(safe-area-inset-top);
  --sab: env(safe-area-inset-bottom);
  --sal: env(safe-area-inset-left);
  --sar: env(safe-area-inset-right);
}

/* Top safe-area handling */
.app-header {
  padding-top: calc(var(--space-4) + var(--sat));
}

/* Fixed bottom bar safe-area handling */
.bottom-nav {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  padding-bottom: calc(12px + var(--sab));
  /* Minimum height keeps the target tappable */
  min-height: calc(56px + var(--sab));
}

/* Bottom sheet safe-area handling */
.bottom-sheet {
  padding-bottom: calc(var(--space-6) + var(--sab));
  border-radius: 20px 20px 0 0;
}
```

### React Native
```jsx
import { SafeAreaView, useSafeAreaInsets } from 'react-native-safe-area-context';

// Method 1: wrap the entire page
<SafeAreaView style={{ flex: 1 }}>{children}</SafeAreaView>

// Method 2: precise control
function MyScreen() {
  const insets = useSafeAreaInsets();
  return (
    <View style={{ paddingTop: insets.top, paddingBottom: insets.bottom }}>
      {/* Content */}
    </View>
  );
}
```

### Flutter
```dart
Scaffold(
  body: SafeArea(
    child: YourContent(),
  ),
  bottomNavigationBar: BottomNav(), // Automatic safe-area handling
)
```

## 3.3 Common App Page Layouts

### List Page (Feed / Timeline)
```css
.feed-page {
  display: flex;
  flex-direction: column;
  height: 100vh;
}
.feed-header {
  flex-shrink: 0;
  height: 56px;
  padding-top: var(--sat);
}
.feed-content {
  flex: 1;
  overflow-y: auto;
  -webkit-overflow-scrolling: touch; /* iOS momentum scrolling */
}
.feed-bottom {
  flex-shrink: 0;
  padding-bottom: var(--sab);
}
```

### Tabbed Page
```css
.tab-page {
  display: flex;
  flex-direction: column;
  height: 100vh;
  height: 100dvh; /* Dynamic viewport height, excluding the virtual keyboard */
}
.tab-header { flex-shrink: 0; }
.tab-content {
  flex: 1;
  overflow: hidden;
  /* Switch with horizontal swipes */
  display: flex;
  scroll-snap-type: x mandatory;
  overflow-x: auto;
}
.tab-panel {
  flex: 0 0 100%;
  scroll-snap-align: start;
  overflow-y: auto;
}
```

### Chat Page
```css
.chat-page {
  display: flex;
  flex-direction: column;
  height: 100dvh; /* Important: use dvh for keyboard adaptation */
}
.chat-header { flex-shrink: 0; padding-top: var(--sat); }
.chat-messages {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column-reverse; /* New messages at the bottom */
  padding: 16px;
}
.chat-input {
  flex-shrink: 0;
  padding: 8px 16px;
  padding-bottom: calc(8px + var(--sab));
  border-top: 1px solid var(--color-border);
}
```

## 3.4 Gestures and Swipe Layouts

```css
/* Swipe-left actions */
.swipe-item {
  position: relative;
  overflow: hidden;
}
.swipe-actions {
  position: absolute;
  right: 0; top: 0; bottom: 0;
  display: flex;
  transform: translateX(100%);
  transition: transform 0.3s;
}
.swipe-item.swiped .swipe-actions {
  transform: translateX(0);
}

/* Pull-to-refresh region */
.pull-to-refresh {
  margin-top: -60px; /* Hidden region */
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: margin-top 0.3s;
}
```

---

# 4. Mini Program Layouts

## 4.1 Core Constraints

| Dimension | WeChat convention | Description |
|------|---------|------|
| **Design width** | 750rpx | 1rpx = screen width / 750 |
| **Navigation bar** | 128rpx + capsule button | Upper-right capsule cannot be customized |
| **Tab bar** | ≤5 items, 98rpx high | Custom styles allowed |
| **Grid** | 24 columns | Official recommendation |
| **Touch area** | ≥75×75rpx | Prevent accidental taps |
| **Status bar** | `wx.getSystemInfo` | Height varies by device |

## 4.2 Common rpx Sizes

```text
Design (750px) → rpx    → iPhone 6 (375pt)
750px         → 750rpx → 375pt (full width)
375px         → 375rpx → 187.5pt (half width)
32px          →  32rpx  →  16pt
28px          → 28rpx  → 14pt (minimum body text)
24px          → 24rpx  → 12pt (secondary text)
```

## 4.3 Custom Navigation Bars

```css
/* Custom navigation bar (requires navigationStyle: "custom") */
.custom-nav {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 999;
}
.custom-nav-statusbar {
  /* Height set dynamically from wx.getSystemInfo().statusBarHeight */
}
.custom-nav-titlebar {
  height: 88rpx; /* Fixed title-bar height */
  display: flex;
  align-items: center;
  padding: 0 200rpx 0 32rpx; /* Reserve room for the capsule button on the right */
}
```

## 4.4 Capsule Button Positioning

```javascript
// Get the capsule button's position
const menuRect = wx.getMenuButtonBoundingClientRect()
// { top, bottom, left, right, width, height }

// Calculate navigation bar height
const sysInfo = wx.getSystemInfoSync()
const statusBarHeight = sysInfo.statusBarHeight
const navBarHeight = (menuRect.top - statusBarHeight) * 2 + menuRect.height
// Page content begins at statusBarHeight + navBarHeight
```

## 4.5 Safe Areas

```css
/* Bottom safe-area handling */
.mini-bottom-bar {
  padding-bottom: calc(20rpx + env(safe-area-inset-bottom));
}

/* Edge-to-edge display handling */
page {
  padding-bottom: constant(safe-area-inset-bottom); /* iOS < 11.2 */
  padding-bottom: env(safe-area-inset-bottom);       /* iOS >= 11.2 */
}
```

## 4.6 Common Mini Program Page Structure

```text
┌─────────────────────────┐
│     Status bar (system)   │ ← statusBarHeight
├─────────────────────────┤
│  ← Title  ···  [Capsule] │ ← Custom navigation bar
├─────────────────────────┤
│                         │
│     Scrollable content   │ ← scroll-view or page scrolling
│                         │
├─────────────────────────┤
│  Tab1  Tab2  Tab3  Tab4 │ ← TabBar (98rpx)
├─────────────────────────┤
│     Safe area            │ ← safe-area-inset-bottom
└─────────────────────────┘
```

---

# 5. Desktop Layouts

## 5.1 Desktop-Specific Considerations

| Dimension | Convention |
|------|------|
| **Minimum window** | 800×600 or 1024×600 |
| **Sidebar width** | 200–300px (resizable by dragging) |
| **Collapsible panels** | Support sidebar collapse/expand |
| **Multiple panels** | Main + detail + properties panels |
| **Mouse hover** | Make full use of hover states |
| **Context menus** | Contextual actions |
| **Keyboard shortcuts** | Ctrl+S to save, etc. |
| **Window title bar** | Can be customized (frameless) |

## 5.2 Classic Three-Column Layout (IDE/Email Client)

```css
.desktop-app {
  display: grid;
  grid-template-columns: var(--sidebar-w, 240px) var(--list-w, 320px) 1fr;
  grid-template-rows: var(--titlebar-h, 36px) 1fr var(--statusbar-h, 24px);
  grid-template-areas:
    "titlebar titlebar titlebar"
    "sidebar  list     detail"
    "status   status   status";
  height: 100vh;
  overflow: hidden;
}

/* Drag to resize panel widths */
.resize-handle {
  width: 4px;
  cursor: col-resize;
  background: transparent;
  transition: background 0.2s;
}
.resize-handle:hover {
  background: var(--color-accent);
}
```

## 5.3 Custom Title Bars (Electron/Tauri)

```css
.custom-titlebar {
  -webkit-app-region: drag; /* Drag to move the window */
  height: 36px;
  display: flex;
  align-items: center;
  padding: 0 12px;
  background: var(--color-bg-secondary);
  user-select: none;
}
.custom-titlebar button {
  -webkit-app-region: no-drag; /* Keep buttons clickable */
}

/* Reserve space for macOS traffic-light controls */
.titlebar-macos { padding-left: 80px; }
/* Reserve space for the Windows close button */
.titlebar-windows { padding-right: 140px; }
```

## 5.4 Responding to Desktop Window Sizes

```css
/* Responsive behavior within desktop apps */
.desktop-app {
  /* Narrow window: hide the list panel */
  &.narrow {
    grid-template-columns: var(--sidebar-w) 1fr;
    grid-template-areas:
      "titlebar titlebar"
      "sidebar  detail"
      "status   status";
  }
  /* Very narrow window: use an icon-only sidebar */
  &.compact {
    grid-template-columns: 48px 1fr;
  }
}
```

---

# 6. General Layout Toolkit

## 6.1 Centering Reference

```css
/* Flex centering (most common) */
.center-flex { display: flex; justify-content: center; align-items: center; }

/* Grid centering (most concise) */
.center-grid { display: grid; place-items: center; }

/* Absolute-position centering */
.center-abs { position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); }

/* Vertical text centering */
.center-text { display: flex; align-items: center; min-height: 48px; }
```

## 6.2 Common Flex Patterns

```css
/* Space-between alignment (common for navigation bars) */
.flex-between { display: flex; justify-content: space-between; align-items: center; }

/* Equal spacing */
.flex-even { display: flex; gap: 16px; flex-wrap: wrap; }

/* Push trailing content right (settings row: label...value>) */
.flex-push-end { display: flex; align-items: center; gap: 8px; }
.flex-push-end > :last-child { margin-left: auto; }

/* Wrapping flex grid */
.flex-grid { display: flex; flex-wrap: wrap; gap: 16px; }
.flex-grid > * { flex: 1 1 calc(33.333% - 16px); min-width: 200px; }
```

## 6.3 Common Grid Patterns

```css
/* Adaptive column count (most practical) */
.auto-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(var(--min-col, 250px), 1fr));
  gap: var(--grid-gap, 24px);
}

/* Fixed-ratio grid */
.ratio-grid { display: grid; grid-template-columns: 2fr 1fr; gap: 24px; }

/* Equal-height cards */
.equal-height-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  grid-auto-rows: 1fr;
  gap: 24px;
}
```

## 6.4 Sticky Layouts

```css
/* Sticky header */
.sticky-header {
  position: sticky;
  top: 0;
  z-index: 50;
  backdrop-filter: blur(12px);
  background: rgba(255, 255, 255, 0.8);
}

/* Sticky sidebar */
.sticky-sidebar {
  position: sticky;
  top: 80px; /* Header height */
  align-self: start;
  max-height: calc(100vh - 100px);
  overflow-y: auto;
}
```

## 6.5 Viewport Unit Reference

```css
/* 100vh issue: mobile address bars cause layout jumps */
/* Solution: use newer viewport units */
.full-height {
  height: 100vh;            /* Fallback */
  height: 100dvh;           /* Dynamic viewport height (recommended) */
}

/* svh = smallest viewport height (address bar expanded) */
/* lvh = largest viewport height (address bar hidden) */
/* dvh = dynamic viewport height (live) */
```

---

# 7. Delivery Checklist

## General Checks
- [ ] No horizontal overflow at any breakpoint
- [ ] Content has a `max-width` limit (body text ≤720px)
- [ ] Semantic HTML elements are used
- [ ] Interactive touch targets are ≥44px
- [ ] The page's main axis uses `min-height: 100dvh`
- [ ] Spacing uses multiples of 4px

## Responsive Checks
- [ ] Correct layout at 375px (small phone)
- [ ] Correct layout at 768px (tablet)
- [ ] Correct layout at 1024px (laptop)
- [ ] Correct layout at 1440px (desktop)

## Platform-Specific Checks

### APP
- [ ] Top and bottom safe areas are handled
- [ ] The bottom tab bar avoids the safe area
- [ ] The keyboard does not cover inputs (use dvh)
- [ ] Space is reserved for pull-to-refresh

### Mini Programs
- [ ] The capsule button area is unobstructed
- [ ] Custom navigation bar height is calculated dynamically
- [ ] rpx units are used correctly
- [ ] The tab bar has no more than five items

### Desktop
- [ ] Layout remains usable at the minimum window size
- [ ] Sidebar supports collapse/expand
- [ ] Custom title-bar drag regions are correct
- [ ] macOS/Windows window controls are unobstructed
