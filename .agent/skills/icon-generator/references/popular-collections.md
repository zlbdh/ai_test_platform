# Popular Icon Library Reference

## Comparison

| Library | Icon count | Styles | Framework support | Features | Recommended use |
| ------ | -------- | ------ | ---------- | ------ | ---------- |
| [Lucide](https://lucide.dev) | 1,400+ | Outline | React/Vue/Svelte/Angular | Lightweight, consistent | **General default** |
| [Heroicons](https://heroicons.com) | 300+ | Outline + solid | React/Vue | Official Tailwind library | Tailwind projects |
| [Phosphor](https://phosphoricons.com) | 7,000+ | Six weights | React/Vue/Svelte/Flutter | Adjustable weights | Flexible styling |
| [Tabler](https://tabler.io/icons) | 4,500+ | Outline | React/Vue/Svelte | Broad selection | Large icon sets |
| [Material Design](https://fonts.google.com/icons) | 10,000+ | Multiple | React/Web | Google styling | Android/Material |
| [Remix Icon](https://remixicon.com) | 2,800+ | Outline + filled | React/Vue | Neutral styling | General use |
| [Feather](https://feathericons.com) | 280+ | Outline | React | Minimal | Small projects |
| [Bootstrap Icons](https://icons.getbootstrap.com) | 1,800+ | Outline + filled | React/Web | Bootstrap ecosystem | Bootstrap projects |
| [Font Awesome](https://fontawesome.com) | 7,800+ | Multiple | React/Vue/Angular | Long-established | Traditional projects |
| [Iconify](https://iconify.design) | 200,000+ | All | React/Vue/Svelte/Web | Aggregates libraries | Cross-library search |

## Installation Guide

### Lucide (Recommended)

```bash
# React
npm install lucide-react

# Vue
npm install lucide-vue-next

# Svelte
npm install lucide-svelte
```

### Heroicons

```bash
# React
npm install @heroicons/react

# Vue
npm install @heroicons/vue
```

### Phosphor

```bash
# React
npm install @phosphor-icons/react

# Vue
npm install @phosphor-icons/vue
```

### Tabler

```bash
# React
npm install @tabler/icons-react

# Vue
npm install @tabler/icons-vue
```

## Iconify (Unified API)

### Package Installation

```bash
npm install @iconify/react    # React
npm install @iconify/vue      # Vue
```

```tsx
// Use icons from any supported library
import { Icon } from '@iconify/react'

<Icon icon="lucide:home" width="24" />
<Icon icon="mdi:settings" width="24" />
<Icon icon="heroicons:bell" width="24" />
```

### CDN Usage

```html
<script src="https://code.iconify.design/3/3.1.0/iconify.min.js"></script>
<span class="iconify" data-icon="lucide:home" data-width="24"></span>
```

### REST API

```bash
Search: https://api.iconify.design/search?query=arrow&limit=10
Get SVG: https://api.iconify.design/{prefix}/{name}.svg
List collections: https://api.iconify.design/collections
```

## AI/Technology Brand Icons

Use [lobe-icons](https://lobehub.com/icons) for AI brand icons:

| Brand | Icon name | Display name |
| ------ | -------- | -------- |
| OpenAI | `openai` | — |
| Anthropic | `anthropic` | — |
| Claude | `claude` | — |
| GPT | `chatgpt` | — |
| Gemini | `gemini` | — |
| Hugging Face | `huggingface` | — |
| ChatGLM | `chatglm` | Zhipu |
| Moonshot | `moonshot` | Moonshot AI |
| DeepSeek | `deepseek` | DeepSeek |
| Qwen | `qwen` | Qwen |

```text
SVG: https://raw.githubusercontent.com/lobehub/lobe-icons/refs/heads/master/packages/static-svg/dark/{name}.svg
PNG: https://raw.githubusercontent.com/lobehub/lobe-icons/refs/heads/master/packages/static-png/dark/{name}.png
```

## Selection Recommendations

```text
Which framework does your project use?
├─ React + Tailwind → Heroicons or Lucide
├─ Other React projects → Lucide (default recommendation)
├─ Vue → Lucide or Phosphor
├─ Plain HTML → Iconify CDN
├─ Many icons needed → Tabler or Phosphor
├─ Multiple weights needed → Phosphor
├─ Material Design styling → Material Design Icons
├─ Cross-library search → Iconify API
└─ AI brand icons → lobe-icons
```
