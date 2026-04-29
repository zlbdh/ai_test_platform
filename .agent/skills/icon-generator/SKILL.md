---
name: icon-generator
description: |
  综合图标生成与管理工具。支持从 200K+ 图标库搜索、中文语义映射、多框架导出（React/Vue/SVG/HTML）、
  Favicon 全流程生成、自定义 SVG 图标制作。

  使用场景：构建 UI 时需要选择图标、为网站生成 Favicon、创建自定义 SVG 图标、
  查找 AI/科技品牌图标，或需要图标使用最佳实践指导时。
---

# 综合图标生成器

搜索、推荐、创建、导出图标的一站式 Skill。

## 快速参考：中文概念 → 图标

| 概念 | Lucide | Heroicons | 用途 |
| ------ | -------- | ----------- | ------ |
| 首页 | `Home` | `home` | 导航、主页入口 |
| 搜索 | `Search` | `magnifying-glass` | 搜索栏、全局搜索 |
| 设置 | `Settings` | `cog-6-tooth` | 系统设置、偏好 |
| 用户 | `User` | `user` | 个人中心、头像 |
| 团队 | `Users` | `user-group` | 团队、成员管理 |
| 通知 | `Bell` | `bell` | 消息提醒、通知中心 |
| 购物车 | `ShoppingCart` | `shopping-cart` | 电商、结算 |
| 收藏 | `Heart` | `heart` | 点赞、收藏夹 |
| 安全 | `Shield` | `shield-check` | 安全设置、权限 |
| 闪电/快速 | `Zap` | `bolt` | 极速、性能 |
| 日历 | `Calendar` | `calendar` | 日程、预约 |
| 时钟 | `Clock` | `clock` | 时间、倒计时 |
| 邮件 | `Mail` | `envelope` | 邮箱、消息 |
| 电话 | `Phone` | `phone` | 联系方式 |
| 位置 | `MapPin` | `map-pin` | 地图、定位 |
| 下载 | `Download` | `arrow-down-tray` | 文件下载 |
| 上传 | `Upload` | `arrow-up-tray` | 文件上传 |
| 编辑 | `Pencil` | `pencil` | 编辑、修改 |
| 删除 | `Trash2` | `trash` | 删除操作 |
| 添加 | `Plus` | `plus` | 新增、创建 |
| 成功 | `CheckCircle` | `check-circle` | 操作成功 |
| 警告 | `AlertTriangle` | `exclamation-triangle` | 风险提示 |
| 错误 | `XCircle` | `x-circle` | 操作失败 |
| 信息 | `Info` | `information-circle` | 提示信息 |
| 刷新 | `RefreshCw` | `arrow-path` | 刷新、重试 |
| 筛选 | `Filter` | `funnel` | 过滤、筛选 |
| 分享 | `Share2` | `share` | 社交分享 |
| 链接 | `Link` | `link` | 超链接 |
| 图表 | `BarChart3` | `chart-bar` | 数据统计 |
| 文件 | `File` | `document` | 文档、文件 |

> 完整映射参见 `references/semantic-mapping.md`

## 图标搜索流程

### 方式一：Iconify API 搜索（推荐）

通过 Iconify REST API 搜索 200,000+ 图标，覆盖 150+ 图标集合：

```bash
# 搜索图标
curl "https://api.iconify.design/search?query=arrow&limit=10"

# 获取特定图标 SVG
curl "https://api.iconify.design/lucide/home.svg"
curl "https://api.iconify.design/mdi/home.svg?color=%23333&height=24"

# 获取图标集合列表
curl "https://api.iconify.design/collections"
```

**图标 ID 格式**：`前缀:名称`，例如 `lucide:home`、`mdi:arrow-right`、`heroicons:check`

### 方式二：使用辅助脚本

```bash
# 搜索图标
node scripts/iconify-search.js search arrow
node scripts/iconify-search.js search home --prefix lucide --limit 5

# 获取图标 SVG
node scripts/iconify-search.js get lucide:home
node scripts/iconify-search.js get mdi:settings --color "#333" --size 24
```

### 方式三：AI 品牌图标

从 lobe-icons 获取 AI/科技品牌图标：

```bash
# CDN URL 模式
# SVG: https://raw.githubusercontent.com/lobehub/lobe-icons/refs/heads/master/packages/static-svg/{light|dark}/{name}.svg
# PNG: https://raw.githubusercontent.com/lobehub/lobe-icons/refs/heads/master/packages/static-png/{light|dark}/{name}.png

# 例如
curl -o claude.svg "https://raw.githubusercontent.com/lobehub/lobe-icons/refs/heads/master/packages/static-svg/dark/claude.svg"
```

常见 AI 图标名：`openai`、`claude`、`gemini`、`chatglm`（智谱）、`moonshot`（月之暗面）

## 图标推荐决策树

```text
需要什么类型的图标？
├─ 具体概念/操作 → 查 "中文概念→图标" 映射表
├─ 行业/业务相关 → 搜索 Iconify API
├─ AI/科技品牌 → 使用 lobe-icons CDN
├─ 网站标签图标 → 走 Favicon 生成流程
└─ 完全自定义 → 手写 SVG 图标
    ├─ 简单几何形状 → 使用基础 SVG 元素
    └─ 复杂图案 → 使用 path 元素 + 贝塞尔曲线
```

## 多框架导出模板

### React（Lucide）

```tsx
import { Home, Search, Settings, type LucideIcon } from 'lucide-react'

// ✅ 明确映射，支持 Tree-Shaking
const ICON_MAP: Record<string, LucideIcon> = { Home, Search, Settings }

// 使用
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

### 纯 HTML + SVG URL

```html
<img src="https://api.iconify.design/lucide/home.svg?color=%23333&height=24" alt="首页" />
```

### Iconify Web Component

```html
<script src="https://code.iconify.design/3/3.1.0/iconify.min.js"></script>
<span class="iconify" data-icon="lucide:home" data-width="24"></span>
```

> 更多模板参见 `references/icon-templates.md`

## Favicon 快速生成

### 1. 创建源 SVG（32×32 viewBox）

**字母类型**：

```xml
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
  <rect width="32" height="32" rx="6" fill="#0066cc"/>
  <text x="16" y="22" font-size="18" font-weight="bold"
        text-anchor="middle" fill="#ffffff" font-family="system-ui, sans-serif">A</text>
</svg>
```

**图形类型**：

```xml
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
  <circle cx="16" cy="16" r="14" fill="#10b981"/>
  <path d="M10 16l4 4 8-8" stroke="#fff" stroke-width="2.5"
        fill="none" stroke-linecap="round" stroke-linejoin="round"/>
</svg>
```

### 2. 生成全套文件

```bash
# 使用 ImageMagick（如已安装）
convert favicon.svg -define icon:auto-resize=16,32 favicon.ico
convert favicon.svg -resize 180x180 -background "#0066cc" -alpha remove apple-touch-icon.png
convert favicon.svg -resize 192x192 icon-192.png
convert favicon.svg -resize 512x512 icon-512.png
```

### 3. HTML 集成

```html
<link rel="icon" href="/favicon.ico" sizes="32x32">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<link rel="manifest" href="/site.webmanifest">
```

> 完整 Favicon 指南参见 `references/favicon-guide.md`

## SVG 图标设计规则

### 基本规范

| 规则 | 说明 |
| ------ | ------ |
| viewBox | 始终使用 `0 0 24 24`（标准图标）或 `0 0 32 32`（Favicon） |
| 描边 | 使用 `stroke="currentColor"` 继承文字颜色 |
| 描边宽度 | 线条图标统一 `stroke-width="2"` |
| 填充 | 线条图标 `fill="none"`，实心图标 `fill="currentColor"` |
| 圆角 | `stroke-linecap="round"` + `stroke-linejoin="round"` |

### 尺寸规范

| 场景 | 推荐尺寸 | CSS 类 |
| ------ | ---------- | -------- |
| 行内文字旁 | 16-20px | `w-4 h-4` / `w-5 h-5` |
| 卡片/按钮 | 24-32px | `w-6 h-6` / `w-8 h-8` |
| 英雄区域 | 40-48px | `w-10 h-10` / `w-12 h-12` |
| 大装饰性 | 64px | `w-16 h-16` |

### ❌ 禁止事项

1. **不要使用 Emoji 代替图标** — Emoji 不可控，跨平台不一致
2. **不要 `import * as Icons`** — 会导致所有图标打包，破坏 Tree-Shaking
3. **不要混合使用线条和实心风格** — 同一区域保持视觉一致性
4. **不要使用硬编码颜色** — 使用 `currentColor` 或 CSS 变量

## 图标库选择建议

| 图标库 | 最适合 | 图标数量 | 包名 |
| -------- | -------- | ---------- | ------ |
| **Lucide** | React 通用项目 | 1,400+ | `lucide-react` |
| **Heroicons** | Tailwind 项目 | 300+ | `@heroicons/react` |
| **Phosphor** | 需要多种粗细 | 7,000+ | `@phosphor-icons/react` |
| **Material Design** | 安卓风格 | 10,000+ | `@mdi/js` |
| **Tabler** | 功能全面 | 4,500+ | `@tabler/icons-react` |

**默认推荐**：Lucide（体积小、质量高、React 集成好）

## 附加资源

- `references/semantic-mapping.md` — 完整中文概念→图标映射表
- `references/icon-templates.md` — 各框架图标代码模板
- `references/favicon-guide.md` — Favicon 生成完整指南
- `references/popular-collections.md` — 热门图标库速查对比
- `examples/search-workflow.md` — 图标搜索工作流示例
- `examples/svg-creation.md` — SVG 图标创建示例
