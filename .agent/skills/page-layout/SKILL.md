---
name: page-layout
description: |
  页面布局设计专家。覆盖网站、APP、小程序、桌面端四大平台的页面结构与布局策略。
  提供 CSS Grid/Flexbox 布局模板、响应式断点策略、安全区域适配、
  导航模式选型、常见页面类型布局方案，以及各平台特有的布局约束。

  使用场景：设计页面结构、选择导航模式、处理响应式适配、
  解决安全区域问题、实现特定页面类型（Dashboard/Landing/Feed 等）的布局时。
---

# 页面布局设计专家

覆盖四大平台：网站 · APP · 小程序 · 桌面端。

> 与 `ui-design-system` 互补：该 Skill 负责配色/字体/动画/风格，本 Skill 专注于**页面结构与空间组织**。

---

# AI 工作流

## Step 1: 确定平台与页面类型

```text
目标平台？              页面类型？
├─ 🌐 网站             ├─ Landing Page / 营销页
├─ 📱 APP (iOS/Android) ├─ Dashboard / 管理后台
├─ 🔷 小程序            ├─ 列表 / Feed 流
├─ 🖥️ 桌面端           ├─ 详情页 / 表单页
└─ 📐 跨平台            ├─ 电商 / 商品展示
                        └─ 内容/博客/文档
```

## Step 2: 选择布局模式（查下方布局决策树）
## Step 3: 应用平台规范（查下方平台章节）
## Step 4: 实现响应式适配（查下方响应式策略）
## Step 5: 执行交付检查清单

---

# CRITICAL — 布局必须遵守

| 规则 | 做法 | 不要 |
|------|------|------|
| 用 Grid 做页面骨架 | `display: grid` 定义主区域 | 用 float/position 做整体布局 |
| 用 Flexbox 做组件内部 | `display: flex` 排列子元素 | Grid 嵌 Grid 处理一维排列 |
| 安全区域必须适配 | `env(safe-area-inset-*)` | 忽略刘海/圆角/底部指示条 |
| 内容不超出视口 | `overflow` + `max-width` | 出现水平滚动条 |
| 底部操作栏固定 | `position: fixed/sticky` + padding-bottom | 被虚拟键盘遮挡 |
| 语义化区域标签 | `<header>/<nav>/<main>/<aside>/<footer>` | 全部用 `<div>` |
| 触摸目标 ≥ 44pt | 按钮/链接可点击面积足够 | 紧凑排列无间距 |

---

# 一、布局决策树

```text
需要几个维度排列？
│
├─ 二维（行+列） → CSS Grid
│   ├─ 页面骨架（Header/Sidebar/Main/Footer）
│   ├─ 商品网格 / 卡片网格
│   ├─ Bento Grid / 仪表盘
│   └─ 图片画廊 / Masonry
│
├─ 一维（行 或 列） → Flexbox
│   ├─ 导航栏（水平排列）
│   ├─ 列表项（图标+文字+箭头）
│   ├─ 按钮组（水平间距）
│   ├─ 表单（纵向排列）
│   └─ 居中对齐
│
└─ 文档流 → 正常流 + max-width
    ├─ 博客文章
    └─ 长表单
```

---

# 二、网站 / Web 应用布局

## 2.1 页面类型速查

### Landing Page（单列流式）
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
/* 典型结构: Hero → 功能介绍 → 社会证明 → CTA → FAQ → Footer */
```

### Dashboard（侧栏+内容区）
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

/* 折叠侧栏 */
.dashboard.collapsed { grid-template-columns: 64px 1fr; }

/* 移动端：侧栏变抽屉 */
@media (max-width: 768px) {
  .dashboard { grid-template-columns: 1fr; grid-template-areas: "header" "main"; }
  .dashboard-sidebar { position: fixed; left: -260px; transition: left 0.3s; z-index: 100; }
  .dashboard-sidebar.open { left: 0; }
}
```

### 商品网格（自适应列数）
```css
.product-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 24px;
  padding: 24px;
}
/* 无需媒体查询，自动响应 */
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

### 博客 / 文档（居中+侧边 TOC）
```css
.article-layout {
  display: grid;
  grid-template-columns: 1fr min(720px, calc(100% - 48px)) 1fr;
}
.article-layout > * { grid-column: 2; }
.article-layout > .full-bleed { grid-column: 1 / -1; }

/* 带 TOC 侧栏 */
@media (min-width: 1200px) {
  .article-with-toc {
    grid-template-columns: 1fr min(720px, 100%) 240px;
    gap: 40px;
  }
  .toc { position: sticky; top: 80px; align-self: start; }
}
```

## 2.2 导航模式选型

| 模式 | 适合场景 | 项目数 | CSS 关键 |
|------|---------|--------|---------|
| 水平导航栏 | 企业官网/Landing | 3-7 | `flex + justify-content` |
| 侧边栏导航 | Dashboard/管理后台 | 5-20+ | `grid-template-columns` |
| 汉堡菜单 | 移动端/项目多 | 5-15 | `position:fixed + transform` |
| Tab 切换 | 内容分类 | 2-5 | `flex + border-bottom` |
| 面包屑 | 多级层次 | -- | `flex + gap + ::before` |

## 2.3 响应式断点策略

```css
/* 移动优先（推荐） */
/* 基础样式 = 手机  */
@media (min-width: 640px)  { /* 大手机/小平板 */ }
@media (min-width: 768px)  { /* 平板竖屏     */ }
@media (min-width: 1024px) { /* 笔记本       */ }
@media (min-width: 1280px) { /* 桌面显示器    */ }
@media (min-width: 1536px) { /* 大屏/2K      */ }
```

```css
/* Container Queries（组件级响应式，2025推荐） */
.card-container { container-type: inline-size; }

@container (min-width: 400px) {
  .card { flex-direction: row; /* 水平布局 */ }
}
@container (max-width: 399px) {
  .card { flex-direction: column; /* 垂直堆叠 */ }
}
```

## 2.4 间距系统

```css
:root {
  /* 4px 基数间距 */
  --space-1:  4px;   --space-2:  8px;
  --space-3:  12px;  --space-4:  16px;
  --space-5:  20px;  --space-6:  24px;
  --space-8:  32px;  --space-10: 40px;
  --space-12: 48px;  --space-16: 64px;
  --space-20: 80px;  --space-24: 96px;

  /* 页面内边距 */
  --page-padding: clamp(16px, 4vw, 80px);

  /* 内容最大宽度 */
  --max-width-sm: 640px;   /* 博客正文 */
  --max-width-md: 960px;   /* 通常内容 */
  --max-width-lg: 1200px;  /* 宽版内容 */
  --max-width-xl: 1440px;  /* 超宽版面 */
}
```

---

# 三、移动端 APP 布局

## 3.1 iOS vs Android 布局对比

| 维度 | iOS (HIG) | Android (Material 3) |
|------|-----------|---------------------|
| **导航栏高度** | 44pt (Large Title: 96pt) | 64dp (TopAppBar) |
| **底栏高度** | 49pt + safe-area | 80dp |
| **底栏项数** | 2-5（推荐≤5） | 3-5（推荐3-4） |
| **状态栏** | 47pt（刘海屏） | 24dp |
| **触摸最小** | 44×44pt | 48×48dp |
| **边距** | 16pt | 16dp |
| **标题风格** | Large Title 可折叠 | 居中/左对齐 |
| **返回方式** | ← 按钮 + 右滑手势 | 系统返回 + ← 按钮 |

## 3.2 安全区域适配

### CSS 方案（WebView / Hybrid）
```css
/* 必须在 viewport 中设置 */
/* <meta name="viewport" content="..., viewport-fit=cover"> */

:root {
  --sat: env(safe-area-inset-top);
  --sab: env(safe-area-inset-bottom);
  --sal: env(safe-area-inset-left);
  --sar: env(safe-area-inset-right);
}

/* 页面顶部适配 */
.app-header {
  padding-top: calc(var(--space-4) + var(--sat));
}

/* 底部固定栏适配 */
.bottom-nav {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  padding-bottom: calc(12px + var(--sab));
  /* 最小高度保证可点击 */
  min-height: calc(56px + var(--sab));
}

/* 底部弹窗适配 */
.bottom-sheet {
  padding-bottom: calc(var(--space-6) + var(--sab));
  border-radius: 20px 20px 0 0;
}
```

### React Native 方案
```jsx
import { SafeAreaView, useSafeAreaInsets } from 'react-native-safe-area-context';

// 方式1：整页包裹
<SafeAreaView style={{ flex: 1 }}>{children}</SafeAreaView>

// 方式2：精确控制
function MyScreen() {
  const insets = useSafeAreaInsets();
  return (
    <View style={{ paddingTop: insets.top, paddingBottom: insets.bottom }}>
      {/* 内容 */}
    </View>
  );
}
```

### Flutter 方案
```dart
Scaffold(
  body: SafeArea(
    child: YourContent(),
  ),
  bottomNavigationBar: BottomNav(), // 自动适配
)
```

## 3.3 APP 常见页面布局

### 列表页（Feed / Timeline）
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
  -webkit-overflow-scrolling: touch; /* iOS 惯性滚动 */
}
.feed-bottom {
  flex-shrink: 0;
  padding-bottom: var(--sab);
}
```

### Tab 切换页
```css
.tab-page {
  display: flex;
  flex-direction: column;
  height: 100vh;
  height: 100dvh; /* 动态视口高度，排除虚拟键盘 */
}
.tab-header { flex-shrink: 0; }
.tab-content {
  flex: 1;
  overflow: hidden;
  /* 横向滑动切换 */
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

### 聊天页
```css
.chat-page {
  display: flex;
  flex-direction: column;
  height: 100dvh; /* 重要：使用 dvh 适配键盘 */
}
.chat-header { flex-shrink: 0; padding-top: var(--sat); }
.chat-messages {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column-reverse; /* 新消息在底部 */
  padding: 16px;
}
.chat-input {
  flex-shrink: 0;
  padding: 8px 16px;
  padding-bottom: calc(8px + var(--sab));
  border-top: 1px solid var(--color-border);
}
```

## 3.4 手势与滑动布局

```css
/* 左滑操作 */
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

/* 下拉刷新区域 */
.pull-to-refresh {
  margin-top: -60px; /* 隐藏区域 */
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: margin-top 0.3s;
}
```

---

# 四、小程序布局

## 4.1 核心约束

| 维度 | 微信规范 | 说明 |
|------|---------|------|
| **设计稿宽度** | 750rpx | 1rpx = 屏幕宽度/750 |
| **导航栏** | 128rpx + 胶囊按钮 | 右上角胶囊不可自定义 |
| **Tab Bar** | ≤5 项，高度 98rpx | 可自定义样式 |
| **栅格** | 24列 | 官方推荐 |
| **触摸区** | ≥ 75×75rpx | 防误触 |
| **状态栏** | `wx.getSystemInfo` | 不同机型高度不同 |

## 4.2 rpx 常用尺寸

```text
设计稿(750px)  →  rpx    →  iPhone6(375pt)
750px         →  750rpx →  375pt (满宽)
375px         →  375rpx →  187.5pt (半宽)
32px          →  32rpx  →  16pt
28px          →  28rpx  →  14pt (最小正文)
24px          →  24rpx  →  12pt (辅助文字)
```

## 4.3 自定义导航栏

```css
/* 自定义导航栏（需设置 navigationStyle: "custom"） */
.custom-nav {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 999;
}
.custom-nav-statusbar {
  /* 高度由 wx.getSystemInfo().statusBarHeight 动态设定 */
}
.custom-nav-titlebar {
  height: 88rpx; /* 标题栏固定高度 */
  display: flex;
  align-items: center;
  padding: 0 200rpx 0 32rpx; /* 右侧留出胶囊按钮空间 */
}
```

## 4.4 胶囊按钮适配

```javascript
// 获取胶囊按钮位置
const menuRect = wx.getMenuButtonBoundingClientRect()
// { top, bottom, left, right, width, height }

// 计算导航栏高度
const sysInfo = wx.getSystemInfoSync()
const statusBarHeight = sysInfo.statusBarHeight
const navBarHeight = (menuRect.top - statusBarHeight) * 2 + menuRect.height
// 页面内容从 statusBarHeight + navBarHeight 开始
```

## 4.5 安全区域

```css
/* 底部安全区适配 */
.mini-bottom-bar {
  padding-bottom: calc(20rpx + env(safe-area-inset-bottom));
}

/* 全面屏适配 */
page {
  padding-bottom: constant(safe-area-inset-bottom); /* iOS < 11.2 */
  padding-bottom: env(safe-area-inset-bottom);       /* iOS >= 11.2 */
}
```

## 4.6 小程序常见页面结构

```text
┌─────────────────────────┐
│     状态栏 (系统)         │ ← statusBarHeight
├─────────────────────────┤
│  ← 标题  ···     [胶囊] │ ← 自定义导航栏
├─────────────────────────┤
│                         │
│     可滚动内容区          │ ← scroll-view 或 页面滚动
│                         │
├─────────────────────────┤
│  Tab1  Tab2  Tab3  Tab4 │ ← TabBar (98rpx)
├─────────────────────────┤
│     安全区域              │ ← safe-area-inset-bottom
└─────────────────────────┘
```

---

# 五、桌面端布局

## 5.1 桌面端特有考虑

| 维度 | 规范 |
|------|------|
| **最小窗口** | 800×600 或 1024×600 |
| **侧栏宽度** | 200-300px（可拖拽调整） |
| **可折叠面板** | 支持折叠/展开侧栏 |
| **多面板** | 主面板 + 详情面板 + 属性面板 |
| **鼠标 hover** | 充分利用 hover 态 |
| **右键菜单** | 上下文操作 |
| **快捷键** | Ctrl+S 保存等 |
| **窗口标题栏** | 可自定义 (frameless) |

## 5.2 经典三栏布局（IDE/邮件客户端风格）

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

/* 拖拽调整面板宽度 */
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

## 5.3 自定义标题栏（Electron/Tauri）

```css
.custom-titlebar {
  -webkit-app-region: drag; /* 可拖拽移动窗口 */
  height: 36px;
  display: flex;
  align-items: center;
  padding: 0 12px;
  background: var(--color-bg-secondary);
  user-select: none;
}
.custom-titlebar button {
  -webkit-app-region: no-drag; /* 按钮可点击 */
}

/* macOS 红绿灯按钮预留 */
.titlebar-macos { padding-left: 80px; }
/* Windows 关闭按钮预留 */
.titlebar-windows { padding-right: 140px; }
```

## 5.4 桌面端响应窗口大小

```css
/* 桌面应用内的响应式 */
.desktop-app {
  /* 窄窗口：隐藏列表面板 */
  &.narrow {
    grid-template-columns: var(--sidebar-w) 1fr;
    grid-template-areas:
      "titlebar titlebar"
      "sidebar  detail"
      "status   status";
  }
  /* 极窄：侧栏变图标模式 */
  &.compact {
    grid-template-columns: 48px 1fr;
  }
}
```

---

# 六、通用布局工具箱

## 6.1 居中方案速查

```css
/* Flex 居中（最常用） */
.center-flex { display: flex; justify-content: center; align-items: center; }

/* Grid 居中（最简洁） */
.center-grid { display: grid; place-items: center; }

/* 绝对定位居中 */
.center-abs { position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); }

/* 文本垂直居中 */
.center-text { display: flex; align-items: center; min-height: 48px; }
```

## 6.2 常用 Flex 模式

```css
/* 两端对齐（导航栏常用） */
.flex-between { display: flex; justify-content: space-between; align-items: center; }

/* 等间距排列 */
.flex-even { display: flex; gap: 16px; flex-wrap: wrap; }

/* 尾部推齐（设置行: 标题...值>） */
.flex-push-end { display: flex; align-items: center; gap: 8px; }
.flex-push-end > :last-child { margin-left: auto; }

/* Flex 换行网格 */
.flex-grid { display: flex; flex-wrap: wrap; gap: 16px; }
.flex-grid > * { flex: 1 1 calc(33.333% - 16px); min-width: 200px; }
```

## 6.3 常用 Grid 模式

```css
/* 自适应列数（最实用） */
.auto-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(var(--min-col, 250px), 1fr));
  gap: var(--grid-gap, 24px);
}

/* 固定比例网格 */
.ratio-grid { display: grid; grid-template-columns: 2fr 1fr; gap: 24px; }

/* 等高卡片 */
.equal-height-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  grid-auto-rows: 1fr;
  gap: 24px;
}
```

## 6.4 粘性布局

```css
/* 粘性头部 */
.sticky-header {
  position: sticky;
  top: 0;
  z-index: 50;
  backdrop-filter: blur(12px);
  background: rgba(255, 255, 255, 0.8);
}

/* 粘性侧栏 */
.sticky-sidebar {
  position: sticky;
  top: 80px; /* header 高度 */
  align-self: start;
  max-height: calc(100vh - 100px);
  overflow-y: auto;
}
```

## 6.5 视口单位速查

```css
/* 100vh 问题：移动端地址栏导致跳动 */
/* 解决方案：使用新视口单位 */
.full-height {
  height: 100vh;            /* 回退 */
  height: 100dvh;           /* 动态视口高度（推荐） */
}

/* svh = 最小视口高度（地址栏展开） */
/* lvh = 最大视口高度（地址栏隐藏） */
/* dvh = 动态视口高度（实时） */
```

---

# 七、交付检查清单

## 通用检查
- [ ] 无水平溢出（所有断点下无横向滚动条）
- [ ] 内容区有 `max-width` 限制（正文 ≤ 720px）
- [ ] 使用语义化 HTML 标签
- [ ] 交互元素触摸区 ≥ 44px
- [ ] 页面主轴使用 `min-height: 100dvh`
- [ ] 间距使用 4px 倍数

## 响应式检查
- [ ] 375px（小手机）布局正常
- [ ] 768px（平板）布局正常
- [ ] 1024px（笔记本）布局正常
- [ ] 1440px（桌面）布局正常

## 平台特有检查

### APP
- [ ] safe-area 适配（顶部 + 底部）
- [ ] 底部 Tab Bar 避开安全区
- [ ] 键盘弹起不遮挡输入框（使用 dvh）
- [ ] 下拉刷新区域预留

### 小程序
- [ ] 胶囊按钮区域无遮挡
- [ ] 自定义导航栏高度动态计算
- [ ] rpx 单位使用正确
- [ ] TabBar 不超过 5 项

### 桌面端
- [ ] 最小窗口尺寸下布局不崩
- [ ] 侧栏可折叠/展开
- [ ] 自定义标题栏拖拽区域正确
- [ ] macOS/Windows 窗口控制按钮不被遮挡
