# 热门图标库速查

## 综合对比

| 图标库 | 图标数 | 风格 | 框架支持 | 特点 | 推荐场景 |
| ------ | -------- | ------ | ---------- | ------ | ---------- |
| [Lucide](https://lucide.dev) | 1,400+ | 线条 | React/Vue/Svelte/Angular | 轻量、一致性好 | **通用首选** |
| [Heroicons](https://heroicons.com) | 300+ | 线条+实心 | React/Vue | Tailwind 官方 | Tailwind 项目 |
| [Phosphor](https://phosphoricons.com) | 7,000+ | 6种粗细 | React/Vue/Svelte/Flutter | 粗细可调 | 需灵活性 |
| [Tabler](https://tabler.io/icons) | 4,500+ | 线条 | React/Vue/Svelte | 数量丰富 | 需大量图标 |
| [Material Design](https://fonts.google.com/icons) | 10,000+ | 多种 | React/Web | Google 风格 | 安卓/Material |
| [Remix Icon](https://remixicon.com) | 2,800+ | 线条+填充 | React/Vue | 中立风格 | 通用 |
| [Feather](https://feathericons.com) | 280+ | 线条 | React | 极简 | 小项目 |
| [Bootstrap Icons](https://icons.getbootstrap.com) | 1,800+ | 线条+填充 | React/Web | Bootstrap 生态 | Bootstrap 项目 |
| [Font Awesome](https://fontawesome.com) | 7,800+ | 多种 | React/Vue/Angular | 历史悠久 | 传统项目 |
| [Iconify](https://iconify.design) | 200,000+ | 全部 | React/Vue/Svelte/Web | 聚合所有库 | 跨库搜索 |

## 安装指南

### Lucide（推荐）

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

## Iconify（统一 API）

### 作为包安装

```bash
npm install @iconify/react    # React
npm install @iconify/vue      # Vue
```

```tsx
// 使用任意图标库的图标
import { Icon } from '@iconify/react'

<Icon icon="lucide:home" width="24" />
<Icon icon="mdi:settings" width="24" />
<Icon icon="heroicons:bell" width="24" />
```

### 作为 CDN 使用

```html
<script src="https://code.iconify.design/3/3.1.0/iconify.min.js"></script>
<span class="iconify" data-icon="lucide:home" data-width="24"></span>
```

### REST API

```bash
搜索：https://api.iconify.design/search?query=arrow&limit=10
获取 SVG：https://api.iconify.design/{前缀}/{名称}.svg
获取集合列表：https://api.iconify.design/collections
```

## AI/科技品牌图标

使用 [lobe-icons](https://lobehub.com/icons) 获取 AI 品牌图标：

| 品牌 | 图标名 | 中文名 |
| ------ | -------- | -------- |
| OpenAI | `openai` | — |
| Anthropic | `anthropic` | — |
| Claude | `claude` | — |
| GPT | `chatgpt` | — |
| Gemini | `gemini` | — |
| Hugging Face | `huggingface` | — |
| ChatGLM | `chatglm` | 智谱 |
| Moonshot | `moonshot` | 月之暗面 |
| DeepSeek | `deepseek` | 深度求索 |
| Qwen | `qwen` | 通义千问 |

```text
SVG: https://raw.githubusercontent.com/lobehub/lobe-icons/refs/heads/master/packages/static-svg/dark/{name}.svg
PNG: https://raw.githubusercontent.com/lobehub/lobe-icons/refs/heads/master/packages/static-png/dark/{name}.png
```

## 选择建议

```text
你的项目用什么框架？
├─ React + Tailwind → Heroicons 或 Lucide
├─ React (其他) → Lucide（默认推荐）
├─ Vue → Lucide 或 Phosphor
├─ 纯 HTML → Iconify CDN
├─ 需要很多图标 → Tabler 或 Phosphor
├─ 需要多种粗细 → Phosphor
├─ Material Design 风格 → Material Design Icons
├─ 需要跨库搜索 → Iconify API
└─ AI 品牌图标 → lobe-icons
```
