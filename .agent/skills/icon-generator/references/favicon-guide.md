# Complete Favicon Generation Guide

Generate a complete website favicon set from scratch.

## Decision Tree

```text
Do you have a logo?
├─ Yes, with an icon → Method 1: extract the logo icon
├─ Yes, text only   → Method 2: letter/initials favicon
└─ No               → Method 3: brand geometry favicon
```

## Required Files

| File | Size | Purpose |
| ---- | ---- | ---- |
| `favicon.svg` | 32×32 viewBox | Scalable icon for modern browsers |
| `favicon.ico` | 16×16 + 32×32 | Legacy browser compatibility |
| `apple-touch-icon.png` | 180×180 | iOS bookmark icon (solid background required) |
| `icon-192.png` | 192×192 | Android/PWA icon |
| `icon-512.png` | 512×512 | PWA splash screen |
| `site.webmanifest` | - | PWA configuration |

## Method 1: Extract the Logo Icon

1. Find the icon's `<path>` or `<g>` elements in the logo's SVG source.
2. Copy the icon paths into a new 32×32 SVG.
3. Center the icon and simplify details that are unreadable at 16px.

```xml
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
  <!-- Path extracted from the logo -->
  <path d="..." fill="#BRAND_COLOR"/>
</svg>
```

## Method 2: Letter Favicon

### Circular Background + Letter

```xml
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
  <circle cx="16" cy="16" r="16" fill="#0066cc"/>
  <text x="16" y="22" font-size="18" font-weight="700"
        text-anchor="middle" fill="#ffffff"
        font-family="system-ui, -apple-system, sans-serif">A</text>
</svg>
```

### Rounded Rectangle + Letter

```xml
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
  <rect width="32" height="32" rx="6" fill="#10b981"/>
  <text x="16" y="22" font-size="16" font-weight="700"
        text-anchor="middle" fill="#ffffff"
        font-family="system-ui, -apple-system, sans-serif">AC</text>
</svg>
```

### Gradient Background + Letter

```xml
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#6366f1"/>
      <stop offset="100%" stop-color="#8b5cf6"/>
    </linearGradient>
  </defs>
  <rect width="32" height="32" rx="6" fill="url(#bg)"/>
  <text x="16" y="22" font-size="18" font-weight="700"
        text-anchor="middle" fill="#ffffff"
        font-family="system-ui, sans-serif">Z</text>
</svg>
```

## Method 3: Brand Geometry

### Industry Recommendations

| Industry | Suggested shapes | Suggested colors |
| ---- | -------- | -------- |
| Technology/internet | Hexagon, rounded square | Blue/purple gradient |
| Finance | Shield, circle | Dark blue, gold |
| Healthcare | Cross, heart | Blue, green, white |
| Education | Book, graduation cap | Blue, red |
| Food service | Circle, warm palette | Red, orange, yellow |
| Environment | Leaf, circle | Green palette |

## Generate Multiple Sizes

### Using ImageMagick

```bash
# Generate ICO with 16×16 and 32×32 sizes
convert favicon.svg -define icon:auto-resize=16,32 favicon.ico

# Generate Apple Touch Icon (180×180, solid background)
convert favicon.svg -resize 180x180 -background "#0066cc" -alpha remove apple-touch-icon.png

# Generate PWA icons
convert favicon.svg -resize 192x192 -background transparent icon-192.png
convert favicon.svg -resize 512x512 -background transparent icon-512.png
```

### Using Sharp (Node.js)

```javascript
const sharp = require('sharp')
const fs = require('fs')

const svgBuffer = fs.readFileSync('favicon.svg')

// Apple Touch Icon
await sharp(svgBuffer).resize(180, 180).flatten({ background: '#0066cc' }).png().toFile('apple-touch-icon.png')

// PWA Icons
await sharp(svgBuffer).resize(192, 192).png().toFile('icon-192.png')
await sharp(svgBuffer).resize(512, 512).png().toFile('icon-512.png')
```

### Online Tools

- [favicon.io](https://favicon.io) — Generate from text, images, or emoji
- [realfavicongenerator.net](https://realfavicongenerator.net) — Comprehensive generator

## HTML Integration

Add to `<head>`:

```html
<!-- Favicon -->
<link rel="icon" href="/favicon.ico" sizes="32x32">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">

<!-- Apple Touch Icon (iOS bookmarks) -->
<link rel="apple-touch-icon" href="/apple-touch-icon.png">

<!-- PWA Manifest -->
<link rel="manifest" href="/site.webmanifest">

<!-- Theme color (browser toolbar) -->
<meta name="theme-color" content="#0066cc">
```

## Web Manifest Template

`site.webmanifest`：

```json
{
  "name": "Your Website Name",
  "short_name": "Short Name",
  "icons": [
    {
      "src": "/icon-192.png",
      "sizes": "192x192",
      "type": "image/png"
    },
    {
      "src": "/icon-512.png",
      "sizes": "512x512",
      "type": "image/png"
    }
  ],
  "theme_color": "#0066cc",
  "background_color": "#ffffff",
  "display": "standalone"
}
```

## Troubleshooting

| Tool | Feature | Command/URL |
| ---- | ---- | --------- |
| iOS bookmark appears as a black square | Transparent background | Apple Touch Icon requires a solid background |
| Browser tab icon does not update | Cache | Clear the browser cache or version the filename |
| Blurry icon at 16×16 | Excessive complexity | Simplify the design and reduce details |
| Android home screen shows a default icon | Missing manifest | Verify the `site.webmanifest` path |
| CMS default icon appears | Default not replaced | Replace the default favicon file |

## Checklist

- [ ] `favicon.svg` — 32×32 viewBox, simple design
- [ ] `favicon.ico` — includes 16×16 and 32×32
- [ ] `apple-touch-icon.png` — 180×180, **solid background**
- [ ] `icon-192.png` — 192×192
- [ ] `icon-512.png` — 512×512
- [ ] `site.webmanifest` — references correct icon paths
- [ ] HTML `<head>` — includes all `<link>` tags
- [ ] Verify appearance on multiple devices
