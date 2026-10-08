---
name: icon-generator
description: |
  Comprehensive icon generation and management. Search 200K+ icons, map natural-language concepts, export for multiple frameworks (React/Vue/SVG/HTML),
  generate a full favicon set, and create custom SVG icons.

  Use when choosing icons for a UI, generating website favicons, creating custom SVG icons,
  finding AI/technology brand icons, or applying icon best practices.
---

# Comprehensive Icon Generator

A single skill for searching, recommending, creating, and exporting icons.

## Quick Reference: Concepts → Icons

| Concept | Lucide | Heroicons | Usage |
| ------ | -------- | ----------- | ------ |
| Home | `Home` | `home` | Navigation, home entry |
| Search | `Search` | `magnifying-glass` | Search bar, global search |
| Settings | `Settings` | `cog-6-tooth` | System settings, preferences |
| User | `User` | `user` | Profile, avatar |
| Team | `Users` | `user-group` | Teams, member management |
| Notifications | `Bell` | `bell` | Alerts, notification center |
| Cart | `ShoppingCart` | `shopping-cart` | Shopping, checkout |
| Favorites | `Heart` | `heart` | Likes, favorites |
| Security | `Shield` | `shield-check` | Security settings, permissions |
| Lightning/speed | `Zap` | `bolt` | Speed, performance |
| Calendar | `Calendar` | `calendar` | Schedules, appointments |
| Clock | `Clock` | `clock` | Time, countdown |
| Mail | `Mail` | `envelope` | Email, messages |
| Phone | `Phone` | `phone` | Contact information |
| Location | `MapPin` | `map-pin` | Maps, positioning |
| Download | `Download` | `arrow-down-tray` | File downloads |
| Upload | `Upload` | `arrow-up-tray` | File uploads |
| Edit | `Pencil` | `pencil` | Editing, updates |
| Delete | `Trash2` | `trash` | Deletion |
| Add | `Plus` | `plus` | Add, create |
| Success | `CheckCircle` | `check-circle` | Successful actions |
| Warning | `AlertTriangle` | `exclamation-triangle` | Risk alerts |
| Error | `XCircle` | `x-circle` | Failed actions |
| Information | `Info` | `information-circle` | Information messages |
| Refresh | `RefreshCw` | `arrow-path` | Refresh, retry |
| Filter | `Filter` | `funnel` | Filtering |
| Share | `Share2` | `share` | Social sharing |
| Link | `Link` | `link` | Hyperlinks |
| Chart | `BarChart3` | `chart-bar` | Data statistics |
| File | `File` | `document` | Documents, files |

> See `references/semantic-mapping.md` for the complete mapping.

## Icon Search Workflow

### Method 1: Iconify API Search (Recommended)

Search 200,000+ icons across 150+ collections through the Iconify REST API:

```bash
# Search icons
curl "https://api.iconify.design/search?query=arrow&limit=10"

# Get an icon's SVG
curl "https://api.iconify.design/lucide/home.svg"
curl "https://api.iconify.design/mdi/home.svg?color=%23333&height=24"

# Get the collection list
curl "https://api.iconify.design/collections"
```

**Icon ID format**: `prefix:name`, such as `lucide:home`, `mdi:arrow-right`, or `heroicons:check`.

### Method 2: Helper Script

```bash
# Search icons
node scripts/iconify-search.js search arrow
node scripts/iconify-search.js search home --prefix lucide --limit 5

# Get an icon SVG
node scripts/iconify-search.js get lucide:home
node scripts/iconify-search.js get mdi:settings --color "#333" --size 24
```

### Method 3: AI Brand Icons

Get AI/technology brand icons from lobe-icons:

```bash
# CDN URL pattern
# SVG: https://raw.githubusercontent.com/lobehub/lobe-icons/refs/heads/master/packages/static-svg/{light|dark}/{name}.svg
# PNG: https://raw.githubusercontent.com/lobehub/lobe-icons/refs/heads/master/packages/static-png/{light|dark}/{name}.png

# Examples
curl -o claude.svg "https://raw.githubusercontent.com/lobehub/lobe-icons/refs/heads/master/packages/static-svg/dark/claude.svg"
```

Common AI icon names: `openai`, `claude`, `gemini`, `chatglm` (Zhipu), `moonshot` (Moonshot AI).

## Icon Recommendation Decision Tree

```text
What type of icon is needed?
├─ Specific concept/action → Consult the concept-to-icon mapping
├─ Industry/business concept → Search the Iconify API
├─ AI/technology brand → Use the lobe-icons CDN
├─ Browser tab icon → Follow the favicon generation workflow
└─ Fully custom → Write an SVG icon
    ├─ Simple geometry → Use basic SVG elements
    └─ Complex shape → Use path elements and Bézier curves
```

## Framework Export Templates

### React（Lucide）

```tsx
import { Home, Search, Settings, type LucideIcon } from 'lucide-react'

// ✅ Explicit mapping supports tree shaking
const ICON_MAP: Record<string, LucideIcon> = { Home, Search, Settings }

// Usage
<Home className="w-5 h-5" />
```

### Vue（Lucide）

```vue
<script setup>
import { Home, Search, Settings } from 'lucide-vue-next'
</script>
<template>
  <Home :size="20" />
</template>
```

### Plain HTML + SVG URL

```html
<img src="https://api.iconify.design/lucide/home.svg?color=%23333&height=24" alt="Home" />
```

### Iconify Web Component

```html
<script src="https://code.iconify.design/3/3.1.0/iconify.min.js"></script>
<span class="iconify" data-icon="lucide:home" data-width="24"></span>
```

> See `references/icon-templates.md` for more templates.

## Quick Favicon Generation

### 1. Create a Source SVG (32×32 viewBox)

**Letter-based**:

```xml
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
  <rect width="32" height="32" rx="6" fill="#0066cc"/>
  <text x="16" y="22" font-size="18" font-weight="bold"
        text-anchor="middle" fill="#ffffff" font-family="system-ui, sans-serif">A</text>
</svg>
```

**Shape-based**:

```xml
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
  <circle cx="16" cy="16" r="14" fill="#10b981"/>
  <path d="M10 16l4 4 8-8" stroke="#fff" stroke-width="2.5"
        fill="none" stroke-linecap="round" stroke-linejoin="round"/>
</svg>
```

### 2. Generate the Full File Set

```bash
# Use ImageMagick if installed
convert favicon.svg -define icon:auto-resize=16,32 favicon.ico
convert favicon.svg -resize 180x180 -background "#0066cc" -alpha remove apple-touch-icon.png
convert favicon.svg -resize 192x192 icon-192.png
convert favicon.svg -resize 512x512 icon-512.png
```

### 3. HTML Integration

```html
<link rel="icon" href="/favicon.ico" sizes="32x32">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<link rel="manifest" href="/site.webmanifest">
```

> See `references/favicon-guide.md` for the complete favicon guide.

## SVG Icon Design Rules

### Basic Conventions

| Rule | Description |
| ------ | ------ |
| viewBox | Always use `0 0 24 24` for standard icons or `0 0 32 32` for favicons |
| Stroke | Use `stroke="currentColor"` to inherit the text color |
| Stroke width | Use `stroke-width="2"` consistently for outline icons |
| Fill | Use `fill="none"` for outline icons and `fill="currentColor"` for solid icons |
| Rounded ends | Use `stroke-linecap="round"` + `stroke-linejoin="round"` |

### Sizing

| Context | Recommended size | CSS classes |
| ------ | ---------- | -------- |
| Inline with text | 16–20px | `w-4 h-4` / `w-5 h-5` |
| Cards/buttons | 24–32px | `w-6 h-6` / `w-8 h-8` |
| Hero sections | 40–48px | `w-10 h-10` / `w-12 h-12` |
| Large decorative icons | 64px | `w-16 h-16` |

### ❌ Prohibited Practices

1. **Do not replace icons with emoji** — emoji are difficult to control and inconsistent across platforms.
2. **Do not use `import * as Icons`** — it bundles every icon and defeats tree shaking.
3. **Do not mix outline and solid styles** — keep each region visually consistent.
4. **Do not hardcode colors** — use `currentColor` or CSS variables.

## Choosing an Icon Library

| Library | Best for | Icon count | Package |
| -------- | -------- | ---------- | ------ |
| **Lucide** | General React projects | 1,400+ | `lucide-react` |
| **Heroicons** | Tailwind projects | 300+ | `@heroicons/react` |
| **Phosphor** | Multiple weights | 7,000+ | `@phosphor-icons/react` |
| **Material Design** | Android styling | 10,000+ | `@mdi/js` |
| **Tabler** | Broad feature coverage | 4,500+ | `@tabler/icons-react` |

**Default recommendation**: Lucide (small footprint, high quality, strong React integration).

## Additional Resources

- `references/semantic-mapping.md` — Complete concept-to-icon mapping
- `references/icon-templates.md` — Framework-specific icon templates
- `references/favicon-guide.md` — Complete favicon generation guide
- `references/popular-collections.md` — Popular icon library comparison
- `examples/search-workflow.md` — Icon search workflow examples
- `examples/svg-creation.md` — SVG creation examples
