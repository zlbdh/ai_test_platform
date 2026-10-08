---
name: ui-design-system
description: |
  Comprehensive UI design system for websites, mobile apps, mini programs, and desktop apps,
  covering color palettes, typography, CSS animation, layout patterns, component conventions, and responsive strategies.

  Use for any UI design task: choosing palettes or fonts, creating animations,
  designing website/app/mini program/desktop interfaces, handling responsive behavior, or generating a design system.
---

# Comprehensive UI Design System

A single resource for UI design: color · typography · animation · websites · mobile apps · mini programs · desktop apps.

---

# AI Workflow: Follow This Process for UI Requests

## Step 1: Analyze Requirements

Extract key information from the user's request:
- **Product type**: SaaS, e-commerce, dashboard, landing page, blog, portfolio, etc.
- **Industry**: technology, healthcare, finance, education, food service, gaming, etc.
- **Style keywords**: minimal, premium, playful, dark, frosted glass, etc.
- **Target platform**: website / iOS or Android app / mini program / desktop app

## Step 2: Generate a Design System (See the Decision Tree Below)

Use Step 1 to recommend a combination of palette, typography, visual style, and layout pattern.

## Step 3: Choose Platform Conventions

Consult the relevant section for platform-specific conventions.

## Step 4: Generate Code and Verify Delivery

After writing code, you **must** complete the Pre-Delivery Checklist at the end.

---

# Quick Reference (Ordered by Priority)

## CRITICAL — Mandatory

| Rule | Do | Avoid |
|------|------|------|
| Color contrast | Body text ≥4.5:1, large text ≥3:1 | Light gray text on white |
| Focus states | Visible focus rings on all interactive elements | Removing outlines without a replacement |
| Touch targets | ≥44×44pt (iOS) / 48×48dp (Android) | Clickable targets below 40px |
| Cursor | Add `cursor: pointer` to all clickable elements | Default cursor on interactive elements |
| Alt text | Descriptive alt text for meaningful images | Reserve alt="" for decorative images |
| Keyboard navigation | Tab order matches visual order | Arbitrary tabindex values |
| Form labels | Associate every input with a label | Isolated, unlabeled inputs |

## HIGH — Strongly Recommended

| Rule | Do | Avoid |
|------|------|------|
| Responsive layout | Test 375px / 768px / 1024px / 1440px | Testing only one size |
| Image optimization | WebP + srcset + `loading="lazy"` | Large, uncompressed images |
| Layout stability | Reserve space for asynchronous content | Layout shifts after loading |
| Reduced motion | Check `prefers-reduced-motion` | Ignoring motion-sensitive users |
| z-index management | Define levels (10/20/30/50/999) | Arbitrary z-index: 99999 |
| Semantic elements | `header/nav/main/section/footer` | Nested divs for everything |
| Body font size | Mobile ≥16px | Body text below 14px |

## MEDIUM — Recommended

| Rule | Do | Avoid |
|------|------|------|
| Line height | Body text 1.5–1.75 | Line height below 1.4 |
| Line length | Limit to 60–75ch | Full-screen-width body text |
| Animation duration | Microinteractions 150–300ms | Transitions longer than 1s |
| Animated properties | Animate only transform/opacity | Animating width/height/margin |
| Icons | SVG icons (Heroicons/Lucide) | Emoji as icons 🎨🚀⚙️ |
| Hover feedback | Color/shadow changes + smooth transitions | No feedback or abrupt changes |
| Palette size | ≤5 colors, 60-30-10 rule | More than seven page colors |

---

# Design System Decision Tree

```text
Product type → Style → Palette → Typography

SaaS/technology
├─ Style: Dark Premium / Glassmorphism / Minimalism
├─ Palette: indigo #6366F1 + purple #8B5CF6 + cyan #06B6D4
├─ Typography: Inter + Source Sans 3
└─ Layout: dashboard (sidebar + top bar) / landing page (single-column hero)

E-commerce
├─ Style: Minimalism + vivid colors
├─ Palette: red #EF4444 + orange #F97316 + gold #FBBF24
├─ Typography: Poppins + Source Sans 3
└─ Layout: product grid + filter sidebar

Healthcare
├─ Style: soft minimalism / Soft UI
├─ Palette: green #10B981 + cyan #06B6D4 + blue #3B82F6
├─ Typography: Plus Jakarta Sans + Source Sans 3
└─ Layout: card-based information

Finance
├─ Style: Dark Premium / understated minimalism
├─ Palette: dark blue #1E40AF + deep green #0F766E + amber #D97706
├─ Typography: Inter + Source Sans 3
└─ Layout: dashboard with dense data charts

Education
├─ Style: bright and friendly / Claymorphism
├─ Palette: blue #3B82F6 + purple #8B5CF6 + amber #F59E0B
├─ Typography: Nunito + Source Sans 3
└─ Layout: course-card grid

Social/entertainment
├─ Style: gradients + rich motion
├─ Palette: pink #EC4899 + purple #8B5CF6 + cyan #06B6D4
├─ Typography: Poppins + Source Sans 3
└─ Layout: feed / masonry

Creative/brand
├─ Style: Brutalism / bold typography
├─ Palette: purple #7C3AED + magenta #DB2777 + gold #F59E0B
├─ Typography: Playfair Display + Source Serif 4
└─ Layout: bento grid / full-screen imagery

Gaming
├─ Style: dark + neon + gradients
├─ Palette: purple #7C3AED + pink #EC4899 + neon cyan #22D3EE
├─ Typography: Space Grotesk + Source Sans 3
└─ Layout: immersive full screen
```

---

# Color Palettes

## Industry Palette Reference

| Industry | Primary | Secondary | Accent |
|------|------|--------|--------|
| SaaS/technology | `#6366F1` Indigo | `#8B5CF6` Purple | `#06B6D4` Cyan |
| E-commerce | `#EF4444` Red | `#F97316` Orange | `#FBBF24` Gold |
| Healthcare | `#10B981` Green | `#06B6D4` Cyan | `#3B82F6` Blue |
| Finance | `#1E40AF` Dark blue | `#0F766E` Deep green | `#D97706` Amber |
| Education | `#3B82F6` Blue | `#8B5CF6` Purple | `#F59E0B` Amber |
| Social | `#EC4899` Pink | `#8B5CF6` Purple | `#06B6D4` Cyan |
| Enterprise | `#1E3A5F` Navy | `#64748B` Slate | `#0EA5E9` Sky blue |
| Food service | `#DC2626` Red | `#EA580C` Red-orange | `#65A30D` Green |
| Travel | `#0284C7` Sky blue | `#059669` Emerald | `#F59E0B` Warm yellow |
| Creative | `#7C3AED` Purple | `#DB2777` Magenta | `#F59E0B` Gold |
| Family/baby | `#F9A8D4` Pink | `#93C5FD` Light blue | `#FCD34D` Light yellow |
| Gaming | `#7C3AED` Purple | `#EC4899` Pink | `#22D3EE` Neon cyan |
| Government | `#DC2626` Red | `#1D4ED8` Blue | `#CA8A04` Gold |

Color proportions: `60% background | 30% secondary | 10% accent (CTA)`

## Neutrals and Dark Mode

```css
:root {
  --color-bg: #FFFFFF;          --color-bg-secondary: #F8FAFC;
  --color-bg-elevated: #FFFFFF; --color-text: #0F172A;
  --color-text-secondary: #64748B; --color-border: #E2E8F0;
  --color-accent: #6366F1;      --color-accent-hover: #4F46E5;
  --color-success: #10B981;     --color-warning: #F59E0B;
  --color-error: #EF4444;
  --shadow-sm: 0 1px 2px rgba(0,0,0,0.05);
  --shadow-md: 0 4px 6px rgba(0,0,0,0.07);
  --shadow-lg: 0 10px 15px rgba(0,0,0,0.1);
}
[data-theme="dark"] {
  --color-bg: #0F172A;          --color-bg-secondary: #1E293B;
  --color-bg-elevated: #334155; --color-text: #F1F5F9;
  --color-text-secondary: #94A3B8; --color-border: #475569;
  --color-accent: #818CF8;      --color-accent-hover: #6366F1;
  --color-success: #34D399;     --color-warning: #FBBF24;
  --color-error: #F87171;
  --shadow-sm: 0 1px 2px rgba(0,0,0,0.3);
  --shadow-md: 0 4px 6px rgba(0,0,0,0.4);
  --shadow-lg: 0 10px 15px rgba(0,0,0,0.5);
}
```

```javascript
// Switch themes
function toggleTheme() {
  const next = document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', next);
  localStorage.setItem('theme', next);
}
const saved = localStorage.getItem('theme')
  || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
document.documentElement.setAttribute('data-theme', saved);
```

---

# Typography

## Font Pairing Reference

| Type | Primary | Complementary | Google Fonts |
|------|------|------|-------------|
| **General default** | Inter | Source Sans 3 | `Inter\|Source+Sans+3` |
| SaaS | Plus Jakarta Sans | Source Sans 3 | `Plus+Jakarta+Sans\|Source+Sans+3` |
| Technical | Space Grotesk | Source Sans 3 | `Space+Grotesk\|Source+Sans+3` |
| Premium brands | Playfair Display | Source Serif 4 | `Playfair+Display\|Source+Serif+4` |
| Classical/literary | Cormorant Garamond | Lora | `Cormorant+Garamond\|Lora` |
| Friendly/rounded | Poppins | Source Sans 3 | `Poppins\|Source+Sans+3` |
| Children's education | Nunito | Rounded sans serif | `Nunito` |

Import template:
```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Source+Sans+3:wght@400;500;700&display=swap" rel="stylesheet">
```

## Type Scale (Major Third 1.25)

```css
:root {
  --text-xs: 0.64rem;  --text-sm: 0.8rem;  --text-base: 1rem;
  --text-lg: 1.25rem;  --text-xl: 1.563rem; --text-2xl: 1.953rem;
  --text-3xl: 2.441rem; --text-4xl: 3.052rem;
}
/* Responsive clamp */
:root {
  --text-base: clamp(0.875rem, 0.8rem + 0.25vw, 1rem);
  --text-lg:   clamp(1.1rem, 1rem + 0.35vw, 1.25rem);
  --text-2xl:  clamp(1.5rem, 1.2rem + 0.8vw, 1.953rem);
  --text-4xl:  clamp(2rem, 1.5rem + 1.5vw, 3.052rem);
}
```

## Typography Reset

```css
html { font-size: 16px; -webkit-font-smoothing: antialiased; }
body { font-family: 'Inter','Source Sans 3',system-ui,sans-serif; line-height: 1.7; color: var(--color-text); }
h1,h2,h3,h4 { line-height: 1.3; font-weight: 700; letter-spacing: -0.02em; }
h1 { font-size: var(--text-4xl); } h2 { font-size: var(--text-3xl); }
h3 { font-size: var(--text-2xl); } h4 { font-size: var(--text-xl); }
p { margin-bottom: 1em; max-width: 65ch; }
code,pre { font-family: 'JetBrains Mono','Fira Code',monospace; font-size: 0.875em; }
```

---

# CSS Animation

## Buttons

```css
.btn-float { transition: transform 0.2s, box-shadow 0.2s; }
.btn-float:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(99,102,241,0.4); }
.btn-float:active { transform: translateY(0); }

.btn-slide { position: relative; overflow: hidden; z-index: 1; }
.btn-slide::before { content:''; position:absolute; inset:0; background:rgba(255,255,255,0.15); transform:translateX(-100%); transition:transform 0.3s; z-index:-1; }
.btn-slide:hover::before { transform: translateX(0); }
```

## Cards

```css
.card-hover { transition: transform 0.3s, box-shadow 0.3s; }
.card-hover:hover { transform: translateY(-4px); box-shadow: 0 12px 24px rgba(0,0,0,0.15); }

/* Staggered entrance */
.card-enter { opacity:0; transform:translateY(20px); animation:fadeInUp 0.5s ease forwards; }
@keyframes fadeInUp { to { opacity:1; transform:translateY(0); } }
.card-enter:nth-child(1) { animation-delay:0s; }
.card-enter:nth-child(2) { animation-delay:0.1s; }
.card-enter:nth-child(3) { animation-delay:0.2s; }
```

## Loading

```css
.skeleton {
  background: linear-gradient(90deg, var(--color-bg-secondary) 25%, var(--color-bg-elevated) 50%, var(--color-bg-secondary) 75%);
  background-size: 200% 100%; animation: shimmer 1.5s infinite;
}
@keyframes shimmer { 0%{background-position:200% 0} 100%{background-position:-200% 0} }

.spinner { width:24px; height:24px; border:3px solid var(--color-border); border-top-color:var(--color-accent); border-radius:50%; animation:spin 0.8s linear infinite; }
@keyframes spin { to{transform:rotate(360deg)} }
```

## Feedback

```css
.shake { animation: shake 0.4s; }
@keyframes shake { 0%,100%{transform:translateX(0)} 20%,60%{transform:translateX(-6px)} 40%,80%{transform:translateX(6px)} }

.toast-enter { animation: slideInRight 0.3s; }
@keyframes slideInRight { from{transform:translateX(100%);opacity:0} }
```

## Scroll Triggers

```javascript
const observer = new IntersectionObserver((entries) => {
  entries.forEach(e => { if(e.isIntersecting){e.target.classList.add('visible');observer.unobserve(e.target)} });
}, { threshold: 0.1 });
document.querySelectorAll('.animate-on-scroll').forEach(el => observer.observe(el));
```

```css
.animate-on-scroll { opacity:0; transform:translateY(30px); transition:opacity 0.6s, transform 0.6s; }
.animate-on-scroll.visible { opacity:1; transform:translateY(0); }
```

## prefers-reduced-motion (Required)

```css
@media (prefers-reduced-motion: reduce) {
  *,*::before,*::after { animation-duration:0.01ms!important; transition-duration:0.01ms!important; }
}
```

---

# Websites / Web Apps

## Layout Decision Tree

```text
Page type?
├─ Landing page → Single-column flow: hero + features + social proof + CTA
├─ SaaS home → Full-width sections: navigation + hero + feature cards + pricing + FAQ
├─ Dashboard → Sidebar (240px) + top bar (64px) + content
├─ Blog/documentation → Centered content (max-width:720px) + right-side TOC
├─ E-commerce → Product grid + filter sidebar
└─ Portfolio → Bento Grid / Masonry
```

## Layout Templates

```css
/* Dashboard */
.admin-layout { display:grid; grid-template-columns:240px 1fr; grid-template-rows:64px 1fr; grid-template-areas:"sidebar header""sidebar main"; min-height:100vh; }
.admin-layout.collapsed { grid-template-columns:64px 1fr; }

/* Bento Grid */
.bento-grid { display:grid; grid-template-columns:repeat(4,1fr); grid-auto-rows:200px; gap:16px; }
.bento-item.large { grid-column:span 2; grid-row:span 2; }

/* Centered blog */
.article-layout { display:grid; grid-template-columns:1fr min(720px,calc(100%-2rem)) 1fr; }
.article-layout>* { grid-column:2; }
.article-layout>.full-width { grid-column:1/-1; }
```

## Components

```css
/* Form inputs */
.form-input { padding:10px 14px; border:1px solid var(--color-border); border-radius:8px; font-size:1rem; outline:none; transition:border-color 0.2s,box-shadow 0.2s; }
.form-input:focus { border-color:var(--color-accent); box-shadow:0 0 0 3px rgba(99,102,241,0.15); }

/* Dialogs */
.modal-backdrop { position:fixed; inset:0; background:rgba(0,0,0,0.5); display:grid; place-items:center; z-index:1000; }
.modal-content { background:var(--color-bg); border-radius:16px; padding:24px; width:min(480px,calc(100vw-32px)); max-height:85vh; overflow-y:auto; }
```

## Visual Styles

| Style | Key CSS | Best for |
|------|---------|------|
| Glassmorphism | `backdrop-filter:blur(20px); background:rgba(255,255,255,0.1)` | Technology, creative products |
| Neumorphism | `box-shadow:8px 8px 16px #d1d1d1,-8px -8px 16px #fff` | Minimalism |
| Brutalism | `border:3px solid #000; box-shadow:4px 4px 0 #000` | Art |
| Dark Premium | Dark background + gradient accents + subtle glow | SaaS |
| Minimalism | Generous whitespace + little decoration + strong contrast | Enterprise |

## Spacing Tokens and Breakpoints

```css
:root { --space-1:4px; --space-2:8px; --space-3:12px; --space-4:16px; --space-6:24px; --space-8:32px; --space-12:48px; --space-16:64px; }

/* Mobile-first breakpoints */
@media (min-width:640px) {/* Portrait tablets */} @media (min-width:768px) {/* Landscape tablets */}
@media (min-width:1024px) {/* Laptops */} @media (min-width:1280px) {/* Desktop */}
```

---

# Mobile Apps

## iOS vs Android

| Dimension | iOS (HIG) | Android (M3) |
|------|-----------|-------------|
| Navigation | Bottom tab bar (≤5) | Bottom Nav / Drawer |
| Back | Upper-left + swipe from left edge | System back button |
| Title | Large Title (shrinks on scroll) | Top App Bar |
| Dialog | Bottom action sheet | Bottom Sheet/Dialog |
| Font | SF Pro | Roboto |
| Minimum touch target | 44×44pt | 48×48dp |

## Safe Areas

```css
.safe-page { padding: env(safe-area-inset-top) env(safe-area-inset-right) env(safe-area-inset-bottom) env(safe-area-inset-left); }
.bottom-bar { position:fixed; bottom:0; left:0; right:0; padding-bottom:calc(16px + env(safe-area-inset-bottom)); }
```

```dart
// Flutter: Scaffold(body: SafeArea(child: YourContent()))
```

```jsx
// RN: import { SafeAreaView } from 'react-native-safe-area-context';
// <SafeAreaView style={{ flex: 1 }}>{children}</SafeAreaView>
```

## Gestures

| Gesture | Action | Usage |
|------|------|------|
| Swipe left | Delete/archive | Lists |
| Swipe right | Flag/mark read | Tasks |
| Pull down | Refresh | Pull-to-refresh |
| Pinch | Zoom | Images/maps |

## Mobile Components

```css
.list-item { display:flex; align-items:center; gap:12px; padding:12px 16px; min-height:48px; border-bottom:0.5px solid var(--color-border); }
.list-item-title { font-size:16px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
```

---

# Mini Programs

## Platform Differences

| Dimension | WeChat | Alipay | Douyin |
|------|------|--------|------|
| Design system | WeUI | Ant Design Mini | Douyin conventions |
| Markup | WXML | AXML | TTML |
| Styles | WXSS | ACSS | TTSS |

## rpx Adaptation

`rpx = screen width / 750` — use dimensions from a 750px design directly as rpx values.

| Element | Recommendation |
|------|------|
| Button height | 88rpx |
| List item | ≥88rpx |
| Page padding | 32rpx |
| Card radius | 16rpx |
| Minimum touch target | 80×80rpx |

## Page Template

```xml
<view class="page">
  <scroll-view scroll-y class="content" refresher-enabled>
    <swiper class="banner" autoplay circular>
      <swiper-item wx:for="{{banners}}"><image src="{{item.url}}" mode="aspectFill"/></swiper-item>
    </swiper>
    <view class="grid-menu">
      <view class="grid-item" wx:for="{{menus}}"><image src="{{item.icon}}"/><text>{{item.name}}</text></view>
    </view>
  </scroll-view>
  <view class="bottom-bar safe-area-bottom"><button class="btn-primary">Submit</button></view>
</view>
```

```css
page{background:#F5F5F5} .page{display:flex;flex-direction:column;min-height:100vh}
.safe-area-bottom{padding-bottom:calc(32rpx+env(safe-area-inset-bottom))}
.grid-menu{display:grid;grid-template-columns:repeat(4,1fr);padding:24rpx 32rpx;background:#fff;border-radius:16rpx;margin:0 32rpx 24rpx}
.btn-primary{width:100%;height:88rpx;line-height:88rpx;background:#07C160;color:#fff;border-radius:8rpx;font-size:32rpx;border:none}
```

## WeUI Colors

WeChat green `#07C160` · Link blue `#576B95` · Error red `#FA5151` · Body `#333` · Secondary `#888` · Background `#F5F5F5`

## Share Cards

Direct shares 5:4 (500×400px) · Moments 1:1 (500×500px)

## Mini Program Pitfalls

- swiper **requires** a fixed height; height:auto does not work.
- Do not put textarea inside scroll-view.
- Fixed bottom bars can misbehave when the iOS keyboard opens.
- Use rpx rather than px.

---

# Desktop Apps

## Platform Styles

| Dimension | macOS | Windows 11 |
|------|-------|-----------|
| Window controls | Upper-left (red/yellow/green) | Upper-right (minimize/maximize/close) |
| Menu bar | Global, at the top | Inside the window |
| Font | SF Pro 13px | Segoe UI 14px |
| Animation | 0.3–0.5s | 0.15–0.3s |

## Electron Title Bar

```css
.titlebar { display:flex; align-items:center; height:32px; -webkit-app-region:drag; user-select:none; }
.titlebar-buttons { display:flex; -webkit-app-region:no-drag; }
.titlebar-btn { width:46px; height:32px; background:transparent; border:none; cursor:pointer; }
.titlebar-btn:hover { background:var(--color-bg-secondary); }
.titlebar-btn.close:hover { background:#E81123; color:white; }
```

```javascript
new BrowserWindow({ frame:false, titleBarStyle:'hidden', titleBarOverlay:{height:32}, minWidth:800, minHeight:600 });
```

## Sidebar

```css
.sidebar { width:240px; min-width:240px; background:var(--color-bg-secondary); border-right:1px solid var(--color-border); transition:width 0.2s; }
.sidebar.collapsed { width:48px; min-width:48px; }
.sidebar-item { display:flex; align-items:center; gap:12px; padding:8px 16px; border-radius:6px; margin:2px 8px; font-size:13px; cursor:pointer; }
.sidebar-item:hover { background:var(--color-bg-elevated); }
.sidebar-item.active { background:var(--color-accent); color:white; }
```

## Keyboard Shortcuts

| Action | macOS | Windows |
|------|-------|---------|
| Save | ⌘+S | Ctrl+S |
| Search | ⌘+F | Ctrl+F |
| Command palette | ⌘+Shift+P | Ctrl+Shift+P |
| Settings | ⌘+, | Ctrl+, |

```javascript
const MOD = navigator.platform.includes('Mac') ? 'metaKey' : 'ctrlKey';
document.addEventListener('keydown', e => { if(e[MOD]&&e.key==='s'){e.preventDefault();saveFile()} });
```

## Context Menus

```css
.context-menu { position:fixed; min-width:180px; background:var(--color-bg); border:1px solid var(--color-border); border-radius:8px; box-shadow:0 8px 24px rgba(0,0,0,0.15); padding:4px; z-index:9999; }
.context-menu-item { display:flex; justify-content:space-between; padding:6px 12px; border-radius:4px; font-size:13px; cursor:pointer; }
.context-menu-item:hover { background:var(--color-accent); color:white; }
```

---

# Pre-Delivery Checklist (Required Before Delivery)

## Visual Quality
- [ ] SVG icons (Heroicons/Lucide) are used instead of emoji icons
- [ ] Icon sizes are consistent (24×24 viewBox)
- [ ] Hover states do not shift layout
- [ ] Palette has no more than five colors and follows 60-30-10

## Interaction
- [ ] Every clickable element has `cursor: pointer`
- [ ] Hover provides visual feedback (color/shadow changes)
- [ ] Transitions last 150–300ms
- [ ] Focus states are visible for keyboard navigation

## Light and Dark Modes
- [ ] Light-mode text contrast is ≥4.5:1
- [ ] Translucent elements remain visible in dark mode
- [ ] Borders are visible in both modes
- [ ] Both modes have been tested

## Layout
- [ ] Responsive at 375px / 768px / 1024px / 1440px
- [ ] No horizontal scrolling on mobile
- [ ] Fixed elements do not obscure content
- [ ] Container max-width values are consistent

## Accessibility
- [ ] Every image has alt text
- [ ] Form inputs have labels
- [ ] Color is not the only way information is conveyed
- [ ] `prefers-reduced-motion` is handled

## Platform-Specific Checks
- [ ] Mobile: touch targets are ≥44pt/48dp
- [ ] Mini programs: use rpx rather than px
- [ ] Mini programs: safe areas are handled
- [ ] Desktop: macOS window controls are on the left, Windows controls on the right
