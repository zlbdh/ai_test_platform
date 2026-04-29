# Favicon 生成完整指南

从零开始生成一套完整的网站 Favicon 文件。

## 决策树

```text
你有 Logo 吗？
├─ 有，包含图标元素 → 方法一：提取 Logo 中的图标
├─ 有，但只有文字   → 方法二：字母/首字母缩写 Favicon
└─ 没有             → 方法三：品牌几何形状 Favicon
```

## 需要生成的文件清单

| 文件 | 尺寸 | 用途 |
| ---- | ---- | ---- |
| `favicon.svg` | 32×32 viewBox | 现代浏览器，可缩放 |
| `favicon.ico` | 16×16 + 32×32 | 传统浏览器兼容 |
| `apple-touch-icon.png` | 180×180 | iOS 书签图标（必须实心背景） |
| `icon-192.png` | 192×192 | Android/PWA 图标 |
| `icon-512.png` | 512×512 | PWA 启动画面 |
| `site.webmanifest` | - | PWA 配置文件 |

## 方法一：提取 Logo 图标

1. 从 Logo 的 SVG 源文件中找到图标部分的 `<path>` 或 `<g>` 元素
2. 复制图标路径到新的 32×32 SVG
3. 居中并简化细节（16px 下看不清的细节要去掉）

```xml
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
  <!-- 从 Logo 提取的路径 -->
  <path d="..." fill="#品牌色"/>
</svg>
```

## 方法二：字母 Favicon

### 圆形背景 + 字母

```xml
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
  <circle cx="16" cy="16" r="16" fill="#0066cc"/>
  <text x="16" y="22" font-size="18" font-weight="700"
        text-anchor="middle" fill="#ffffff"
        font-family="system-ui, -apple-system, sans-serif">A</text>
</svg>
```

### 圆角矩形 + 字母

```xml
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
  <rect width="32" height="32" rx="6" fill="#10b981"/>
  <text x="16" y="22" font-size="16" font-weight="700"
        text-anchor="middle" fill="#ffffff"
        font-family="system-ui, -apple-system, sans-serif">AC</text>
</svg>
```

### 渐变背景 + 字母

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

## 方法三：品牌几何形状

### 行业推荐

| 行业 | 推荐形状 | 推荐颜色 |
| ---- | -------- | -------- |
| 科技/互联网 | 六边形、圆角方块 | 蓝、紫渐变 |
| 金融 | 盾牌、圆形 | 深蓝、金色 |
| 医疗 | 十字、心形 | 蓝、绿、白 |
| 教育 | 书本、帽子形状 | 蓝、红 |
| 餐饮 | 圆形、暖色 | 红、橙、黄 |
| 环保 | 叶子、圆形 | 绿色系 |

## 生成多尺寸文件

### 使用 ImageMagick

```bash
# 生成 ICO（包含 16×16 和 32×32）
convert favicon.svg -define icon:auto-resize=16,32 favicon.ico

# 生成 Apple Touch Icon（180×180，实心背景）
convert favicon.svg -resize 180x180 -background "#0066cc" -alpha remove apple-touch-icon.png

# 生成 PWA 图标
convert favicon.svg -resize 192x192 -background transparent icon-192.png
convert favicon.svg -resize 512x512 -background transparent icon-512.png
```

### 使用 Sharp (Node.js)

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

### 在线工具

- [favicon.io](https://favicon.io) — 从文字/图片/Emoji 生成
- [realfavicongenerator.net](https://realfavicongenerator.net) — 最全面的生成器

## HTML 集成

在 `<head>` 中添加：

```html
<!-- Favicon -->
<link rel="icon" href="/favicon.ico" sizes="32x32">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">

<!-- Apple Touch Icon（iOS 书签） -->
<link rel="apple-touch-icon" href="/apple-touch-icon.png">

<!-- PWA Manifest -->
<link rel="manifest" href="/site.webmanifest">

<!-- 主题色（浏览器工具栏颜色） -->
<meta name="theme-color" content="#0066cc">
```

## Web Manifest 模板

`site.webmanifest`：

```json
{
  "name": "你的网站名称",
  "short_name": "简称",
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

## 常见问题排查

| 工具 | 特点 | 命令/地址 |
| ---- | ---- | --------- |
| iOS 书签显示黑色方块 | 背景透明 | Apple Touch Icon 必须有实心背景 |
| 浏览器标签图标不更新 | 缓存 | 清理浏览器缓存 或 给文件名加版本号 |
| 16×16 下图标模糊 | 图标太复杂 | 简化设计，减少细节 |
| Android 主屏显示默认图标 | 缺少 Manifest | 确保 `site.webmanifest` 路径正确 |
| 使用了 CMS 默认图标 | 未替换 | 替换默认的 favicon 文件 |

## 检查清单

- [ ] `favicon.svg` — 32×32 viewBox，设计简洁
- [ ] `favicon.ico` — 包含 16×16 和 32×32
- [ ] `apple-touch-icon.png` — 180×180，**实心背景**
- [ ] `icon-192.png` — 192×192
- [ ] `icon-512.png` — 512×512
- [ ] `site.webmanifest` — 引用正确的图标路径
- [ ] HTML `<head>` — 包含所有 `<link>` 标签
- [ ] 在多设备上测试显示效果
