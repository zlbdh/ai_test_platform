---
name: ui-design-system
description: |
  全能 UI 设计系统。覆盖网站、APP、小程序、桌面端四大平台的 UI 设计，
  包含配色方案、字体排版、CSS 动画、布局模式、组件规范、响应式策略。

  使用场景：任何 UI 设计相关任务——选配色方案、选字体、做动画效果、
  设计网站/APP/小程序/桌面应用界面、处理响应式适配、生成设计系统时。
---

# 全能 UI 设计系统

一站式解决所有 UI 设计问题：配色 · 字体 · 动画 · 网站 · APP · 小程序 · 桌面端。

---

# AI 工作流：收到 UI 请求时按此流程执行

## Step 1: 分析需求

从用户请求中提取关键信息：
- **产品类型**: SaaS、电商、Dashboard、Landing Page、博客、Portfolio……
- **行业**: 科技、医疗、金融、教育、餐饮、游戏……
- **风格关键词**: 极简、高端、活泼、暗黑、毛玻璃……
- **目标平台**: 网站 / APP(iOS/Android) / 小程序 / 桌面端

## Step 2: 生成设计系统（查下方决策树）

根据 Step 1 的信息，组合推荐：配色 + 字体 + 设计风格 + 布局模式。

## Step 3: 选择平台规范

根据目标平台，查阅对应章节获取平台特有规范。

## Step 4: 生成代码 + 交付检查

编写代码后，**必须**执行末尾的 Pre-Delivery Checklist。

---

# Quick Reference（按优先级排序）

## CRITICAL — 必须遵守

| 规则 | 做法 | 不要 |
|------|------|------|
| 色彩对比度 | 正文 ≥ 4.5:1，大文本 ≥ 3:1 | 浅灰文字在白色背景上 |
| 焦点状态 | 所有交互元素有可见 focus ring | 去掉 outline 不补偿 |
| 触摸目标 | ≥ 44×44pt (iOS) / 48×48dp (Android) | 小于 40px 的可点击元素 |
| cursor 指针 | 所有可点击元素加 `cursor: pointer` | 交互元素用默认光标 |
| alt 文本 | 有意义的图片写描述性 alt | alt="" 用于装饰图 |
| 键盘导航 | Tab 顺序与视觉顺序一致 | tabindex 随意乱设 |
| 表单标签 | 每个 input 关联 label | 无 label 的孤立输入框 |

## HIGH — 强烈建议

| 规则 | 做法 | 不要 |
|------|------|------|
| 响应式 | 测试 375px / 768px / 1024px / 1440px | 只在一个尺寸测试 |
| 图片优化 | WebP + srcset + `loading="lazy"` | 无压缩大图直接用 |
| 内容跳动 | 异步内容预留占位空间 | 加载完成后布局抖动 |
| reduced-motion | 检查 `prefers-reduced-motion` | 忽略动画敏感用户 |
| z-index 管理 | 定义层级 (10/20/30/50/999) | 随意写 z-index: 99999 |
| 语义化标签 | `header/nav/main/section/footer` | 全部用 div 嵌套 |
| 正文字号 | 移动端 ≥ 16px | 中文正文 < 14px |

## MEDIUM — 应当遵循

| 规则 | 做法 | 不要 |
|------|------|------|
| 行高 | 正文 1.5-1.75（中文 1.7-1.8） | 行高 < 1.4 |
| 行宽 | 限制 60-75ch | 满屏宽度正文 |
| 动画时长 | 微交互 150-300ms | 超过 1s 的过渡 |
| 动画属性 | 只动画 transform/opacity | 动画 width/height/margin |
| 图标 | SVG 图标 (Heroicons/Lucide) | Emoji 当图标 🎨🚀⚙️ |
| hover 反馈 | 颜色/阴影变化 + smooth transition | 无反馈或瞬间变化 |
| 配色数量 | ≤ 5 色，60-30-10 法则 | 页面超过 7 种颜色 |

---

# 设计系统推理决策树

```text
产品类型 → 风格 → 配色 → 字体

SaaS/科技
├─ 风格: Dark Premium / Glassmorphism / Minimalism
├─ 配色: 靛蓝#6366F1 + 紫#8B5CF6 + 青#06B6D4
├─ 字体: Inter + 思源黑体
└─ 布局: Dashboard(侧栏+顶栏) / Landing(单列Hero)

电商
├─ 风格: Minimalism + 鲜明色彩
├─ 配色: 红#EF4444 + 橙#F97316 + 金#FBBF24
├─ 字体: Poppins + 思源黑体
└─ 布局: Grid 商品网格 + 筛选侧栏

医疗健康
├─ 风格: 柔和极简 / Soft UI
├─ 配色: 绿#10B981 + 青#06B6D4 + 蓝#3B82F6
├─ 字体: Plus Jakarta Sans + 思源黑体
└─ 布局: 卡片式信息展示

金融理财
├─ 风格: Dark Premium / 稳重极简
├─ 配色: 深蓝#1E40AF + 墨绿#0F766E + 琥珀#D97706
├─ 字体: Inter + 思源黑体
└─ 布局: Dashboard(数据图表密集)

教育学习
├─ 风格: 明亮友好 / Claymorphism
├─ 配色: 蓝#3B82F6 + 紫#8B5CF6 + 琥珀#F59E0B
├─ 字体: Nunito + 思源黑体
└─ 布局: 卡片式课程网格

社交/娱乐
├─ 风格: 渐变 + 动效丰富
├─ 配色: 粉#EC4899 + 紫#8B5CF6 + 青#06B6D4
├─ 字体: Poppins + 思源黑体
└─ 布局: Feed流 / 瀑布流

文创/品牌
├─ 风格: Brutalism / 大胆排版
├─ 配色: 紫#7C3AED + 玫红#DB2777 + 金#F59E0B
├─ 字体: Playfair Display + 思源宋体
└─ 布局: Bento Grid / 全屏大图

游戏
├─ 风格: 暗黑 + 霓虹 + 渐变
├─ 配色: 紫#7C3AED + 粉#EC4899 + 荧光青#22D3EE
├─ 字体: Space Grotesk + 思源黑体
└─ 布局: 沉浸式全屏
```

---

# 配色方案

## 行业配色速查

| 行业 | 主色 | 辅助色 | 强调色 |
|------|------|--------|--------|
| SaaS/科技 | `#6366F1` 靛蓝 | `#8B5CF6` 紫 | `#06B6D4` 青 |
| 电商 | `#EF4444` 红 | `#F97316` 橙 | `#FBBF24` 金 |
| 医疗 | `#10B981` 绿 | `#06B6D4` 青 | `#3B82F6` 蓝 |
| 金融 | `#1E40AF` 深蓝 | `#0F766E` 墨绿 | `#D97706` 琥珀 |
| 教育 | `#3B82F6` 蓝 | `#8B5CF6` 紫 | `#F59E0B` 琥珀 |
| 社交 | `#EC4899` 粉 | `#8B5CF6` 紫 | `#06B6D4` 青 |
| 企业 | `#1E3A5F` 藏蓝 | `#64748B` 灰蓝 | `#0EA5E9` 天蓝 |
| 餐饮 | `#DC2626` 红 | `#EA580C` 橘红 | `#65A30D` 绿 |
| 旅游 | `#0284C7` 天蓝 | `#059669` 翠绿 | `#F59E0B` 暖黄 |
| 文创 | `#7C3AED` 紫 | `#DB2777` 玫红 | `#F59E0B` 金 |
| 母婴 | `#F9A8D4` 粉 | `#93C5FD` 浅蓝 | `#FCD34D` 浅黄 |
| 游戏 | `#7C3AED` 紫 | `#EC4899` 粉 | `#22D3EE` 荧光青 |
| 政务 | `#DC2626` 红 | `#1D4ED8` 蓝 | `#CA8A04` 金 |

配色比例: `60% 背景 | 30% 辅助 | 10% 强调(CTA)`

## 中性色 + 暗色模式

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
// 主题切换
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

# 字体排版

## 字体搭配速查

| 类型 | 西文 | 中文 | Google Fonts |
|------|------|------|-------------|
| **通用首选** | Inter | 思源黑体 Noto Sans SC | `Inter\|Noto+Sans+SC` |
| SaaS | Plus Jakarta Sans | 思源黑体 | `Plus+Jakarta+Sans\|Noto+Sans+SC` |
| 极客 | Space Grotesk | 思源黑体 | `Space+Grotesk\|Noto+Sans+SC` |
| 高端品牌 | Playfair Display | 思源宋体 Noto Serif SC | `Playfair+Display\|Noto+Serif+SC` |
| 古典文艺 | Cormorant Garamond | 霞鹜文楷 LXGW WenKai | `Cormorant+Garamond\|LXGW+WenKai` |
| 友好圆润 | Poppins | 思源黑体 | `Poppins\|Noto+Sans+SC` |
| 儿童教育 | Nunito | 圆体 | `Nunito` |

导入模板:
```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Noto+Sans+SC:wght@400;500;700&display=swap" rel="stylesheet">
```

## 字号系统 (Major Third 1.25)

```css
:root {
  --text-xs: 0.64rem;  --text-sm: 0.8rem;  --text-base: 1rem;
  --text-lg: 1.25rem;  --text-xl: 1.563rem; --text-2xl: 1.953rem;
  --text-3xl: 2.441rem; --text-4xl: 3.052rem;
}
/* 响应式 clamp */
:root {
  --text-base: clamp(0.875rem, 0.8rem + 0.25vw, 1rem);
  --text-lg:   clamp(1.1rem, 1rem + 0.35vw, 1.25rem);
  --text-2xl:  clamp(1.5rem, 1.2rem + 0.8vw, 1.953rem);
  --text-4xl:  clamp(2rem, 1.5rem + 1.5vw, 3.052rem);
}
```

## 排版重置

```css
html { font-size: 16px; -webkit-font-smoothing: antialiased; }
body { font-family: 'Inter','Noto Sans SC',system-ui,sans-serif; line-height: 1.7; color: var(--color-text); }
h1,h2,h3,h4 { line-height: 1.3; font-weight: 700; letter-spacing: -0.02em; }
h1 { font-size: var(--text-4xl); } h2 { font-size: var(--text-3xl); }
h3 { font-size: var(--text-2xl); } h4 { font-size: var(--text-xl); }
p { margin-bottom: 1em; max-width: 65ch; }
code,pre { font-family: 'JetBrains Mono','Fira Code',monospace; font-size: 0.875em; }
```

---

# CSS 动画

## 按钮

```css
.btn-float { transition: transform 0.2s, box-shadow 0.2s; }
.btn-float:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(99,102,241,0.4); }
.btn-float:active { transform: translateY(0); }

.btn-slide { position: relative; overflow: hidden; z-index: 1; }
.btn-slide::before { content:''; position:absolute; inset:0; background:rgba(255,255,255,0.15); transform:translateX(-100%); transition:transform 0.3s; z-index:-1; }
.btn-slide:hover::before { transform: translateX(0); }
```

## 卡片

```css
.card-hover { transition: transform 0.3s, box-shadow 0.3s; }
.card-hover:hover { transform: translateY(-4px); box-shadow: 0 12px 24px rgba(0,0,0,0.15); }

/* 交错入场 */
.card-enter { opacity:0; transform:translateY(20px); animation:fadeInUp 0.5s ease forwards; }
@keyframes fadeInUp { to { opacity:1; transform:translateY(0); } }
.card-enter:nth-child(1) { animation-delay:0s; }
.card-enter:nth-child(2) { animation-delay:0.1s; }
.card-enter:nth-child(3) { animation-delay:0.2s; }
```

## 加载

```css
.skeleton {
  background: linear-gradient(90deg, var(--color-bg-secondary) 25%, var(--color-bg-elevated) 50%, var(--color-bg-secondary) 75%);
  background-size: 200% 100%; animation: shimmer 1.5s infinite;
}
@keyframes shimmer { 0%{background-position:200% 0} 100%{background-position:-200% 0} }

.spinner { width:24px; height:24px; border:3px solid var(--color-border); border-top-color:var(--color-accent); border-radius:50%; animation:spin 0.8s linear infinite; }
@keyframes spin { to{transform:rotate(360deg)} }
```

## 反馈

```css
.shake { animation: shake 0.4s; }
@keyframes shake { 0%,100%{transform:translateX(0)} 20%,60%{transform:translateX(-6px)} 40%,80%{transform:translateX(6px)} }

.toast-enter { animation: slideInRight 0.3s; }
@keyframes slideInRight { from{transform:translateX(100%);opacity:0} }
```

## 滚动触发

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

## prefers-reduced-motion（必须）

```css
@media (prefers-reduced-motion: reduce) {
  *,*::before,*::after { animation-duration:0.01ms!important; transition-duration:0.01ms!important; }
}
```

---

# 网站 / Web 应用

## 布局决策树

```text
页面类型？
├─ Landing Page → 单列流式: Hero + 特性 + 社会证明 + CTA
├─ SaaS 主页 → 全宽分区: 导航 + Hero + 功能卡片 + 定价 + FAQ
├─ Dashboard → 侧边栏(240px) + 顶栏(64px) + 内容区
├─ 博客/文档 → 居中内容(max-width:720px) + 右侧 TOC
├─ 电商 → Grid 商品网格 + 筛选侧栏
└─ Portfolio → Bento Grid / Masonry
```

## 布局模板

```css
/* Dashboard */
.admin-layout { display:grid; grid-template-columns:240px 1fr; grid-template-rows:64px 1fr; grid-template-areas:"sidebar header""sidebar main"; min-height:100vh; }
.admin-layout.collapsed { grid-template-columns:64px 1fr; }

/* Bento Grid */
.bento-grid { display:grid; grid-template-columns:repeat(4,1fr); grid-auto-rows:200px; gap:16px; }
.bento-item.large { grid-column:span 2; grid-row:span 2; }

/* 博客居中 */
.article-layout { display:grid; grid-template-columns:1fr min(720px,calc(100%-2rem)) 1fr; }
.article-layout>* { grid-column:2; }
.article-layout>.full-width { grid-column:1/-1; }
```

## 组件

```css
/* 表单输入 */
.form-input { padding:10px 14px; border:1px solid var(--color-border); border-radius:8px; font-size:1rem; outline:none; transition:border-color 0.2s,box-shadow 0.2s; }
.form-input:focus { border-color:var(--color-accent); box-shadow:0 0 0 3px rgba(99,102,241,0.15); }

/* 模态框 */
.modal-backdrop { position:fixed; inset:0; background:rgba(0,0,0,0.5); display:grid; place-items:center; z-index:1000; }
.modal-content { background:var(--color-bg); border-radius:16px; padding:24px; width:min(480px,calc(100vw-32px)); max-height:85vh; overflow-y:auto; }
```

## 设计风格

| 风格 | CSS 关键 | 适合 |
|------|---------|------|
| Glassmorphism | `backdrop-filter:blur(20px); background:rgba(255,255,255,0.1)` | 科技、创意 |
| Neumorphism | `box-shadow:8px 8px 16px #d1d1d1,-8px -8px 16px #fff` | 极简 |
| Brutalism | `border:3px solid #000; box-shadow:4px 4px 0 #000` | 艺术 |
| Dark Premium | 深色bg + 渐变强调 + 微光 | SaaS |
| Minimalism | 大留白 + 少装饰 + 高对比 | 企业 |

## 间距 Token + 断点

```css
:root { --space-1:4px; --space-2:8px; --space-3:12px; --space-4:16px; --space-6:24px; --space-8:32px; --space-12:48px; --space-16:64px; }

/* 移动优先断点 */
@media (min-width:640px) {/* 平板竖 */} @media (min-width:768px) {/* 平板横 */}
@media (min-width:1024px) {/* 笔记本 */} @media (min-width:1280px) {/* 桌面 */}
```

---

# 移动端 APP

## iOS vs Android

| 维度 | iOS (HIG) | Android (M3) |
|------|-----------|-------------|
| 导航 | Tab Bar底部(≤5) | Bottom Nav / Drawer |
| 返回 | 左上角+边缘右滑 | 系统返回键 |
| 标题 | Large Title(滚动缩小) | Top App Bar |
| 弹窗 | Action Sheet(底部) | Bottom Sheet/Dialog |
| 字体 | SF Pro | Roboto |
| 触摸最小 | 44×44pt | 48×48dp |

## 安全区域

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

## 手势

| 手势 | 操作 | 用途 |
|------|------|------|
| 左滑 | 删除/归档 | 列表 |
| 右滑 | 标记/已读 | 待办 |
| 下拉 | 刷新 | Pull-to-refresh |
| 捏合 | 缩放 | 图片/地图 |

## 移动端组件

```css
.list-item { display:flex; align-items:center; gap:12px; padding:12px 16px; min-height:48px; border-bottom:0.5px solid var(--color-border); }
.list-item-title { font-size:16px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
```

---

# 小程序

## 平台差异

| 维度 | 微信 | 支付宝 | 抖音 |
|------|------|--------|------|
| 规范 | WeUI | Ant Design Mini | 抖音规范 |
| 标签 | WXML | AXML | TTML |
| 样式 | WXSS | ACSS | TTSS |

## rpx 适配

`rpx = 屏幕宽度/750` — 设计稿750px上的尺寸直接写rpx

| 元素 | 推荐 |
|------|------|
| 按钮高度 | 88rpx |
| 列表项 | ≥88rpx |
| 页面padding | 32rpx |
| 卡片圆角 | 16rpx |
| 触摸最小 | 80×80rpx |

## 页面模板

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
  <view class="bottom-bar safe-area-bottom"><button class="btn-primary">提交</button></view>
</view>
```

```css
page{background:#F5F5F5} .page{display:flex;flex-direction:column;min-height:100vh}
.safe-area-bottom{padding-bottom:calc(32rpx+env(safe-area-inset-bottom))}
.grid-menu{display:grid;grid-template-columns:repeat(4,1fr);padding:24rpx 32rpx;background:#fff;border-radius:16rpx;margin:0 32rpx 24rpx}
.btn-primary{width:100%;height:88rpx;line-height:88rpx;background:#07C160;color:#fff;border-radius:8rpx;font-size:32rpx;border:none}
```

## WeUI 色彩

微信绿`#07C160` · 链接蓝`#576B95` · 错误红`#FA5151` · 正文`#333` · 次要`#888` · 背景`#F5F5F5`

## 分享卡片

好友 5:4 (500×400px) · 朋友圈 1:1 (500×500px)

## 小程序陷阱

- swiper **必须**固定高度（height:auto 无效）
- 不要在 scroll-view 内用 textarea
- iOS 键盘弹起时 fixed 底部栏会 bug
- 用 rpx 不用 px

---

# 桌面端 APP

## 平台风格

| 维度 | macOS | Windows 11 |
|------|-------|-----------|
| 窗口控制 | 左上角(红黄绿) | 右上角(最小化/最大化/关闭) |
| 菜单栏 | 全局顶部 | 窗口内 |
| 字体 | SF Pro 13px | Segoe UI 14px |
| 动画 | 0.3-0.5s | 0.15-0.3s |

## Electron 标题栏

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

## 侧边栏

```css
.sidebar { width:240px; min-width:240px; background:var(--color-bg-secondary); border-right:1px solid var(--color-border); transition:width 0.2s; }
.sidebar.collapsed { width:48px; min-width:48px; }
.sidebar-item { display:flex; align-items:center; gap:12px; padding:8px 16px; border-radius:6px; margin:2px 8px; font-size:13px; cursor:pointer; }
.sidebar-item:hover { background:var(--color-bg-elevated); }
.sidebar-item.active { background:var(--color-accent); color:white; }
```

## 快捷键

| 操作 | macOS | Windows |
|------|-------|---------|
| 保存 | ⌘+S | Ctrl+S |
| 搜索 | ⌘+F | Ctrl+F |
| 命令面板 | ⌘+Shift+P | Ctrl+Shift+P |
| 设置 | ⌘+, | Ctrl+, |

```javascript
const MOD = navigator.platform.includes('Mac') ? 'metaKey' : 'ctrlKey';
document.addEventListener('keydown', e => { if(e[MOD]&&e.key==='s'){e.preventDefault();saveFile()} });
```

## 右键菜单

```css
.context-menu { position:fixed; min-width:180px; background:var(--color-bg); border:1px solid var(--color-border); border-radius:8px; box-shadow:0 8px 24px rgba(0,0,0,0.15); padding:4px; z-index:9999; }
.context-menu-item { display:flex; justify-content:space-between; padding:6px 12px; border-radius:4px; font-size:13px; cursor:pointer; }
.context-menu-item:hover { background:var(--color-accent); color:white; }
```

---

# Pre-Delivery Checklist（交付前必须验证）

## 视觉品质
- [ ] 未使用 Emoji 当图标（用 SVG: Heroicons/Lucide）
- [ ] 图标尺寸统一（viewBox 24x24）
- [ ] hover 状态不导致布局偏移
- [ ] 配色不超过 5 种，符合 60-30-10

## 交互
- [ ] 所有可点击元素有 `cursor: pointer`
- [ ] hover 有视觉反馈（颜色/阴影变化）
- [ ] transition 时长 150-300ms
- [ ] focus 州可见（键盘导航）

## 明暗模式
- [ ] 浅色模式文字对比度 ≥ 4.5:1
- [ ] 暗色模式下半透明元素仍可见
- [ ] 边框在两种模式下都可见
- [ ] 两种模式都已测试

## 布局
- [ ] 响应式: 375px / 768px / 1024px / 1440px
- [ ] 无水平滚动（移动端）
- [ ] 固定元素不遮挡内容
- [ ] 容器 max-width 一致

## 无障碍
- [ ] 所有图片有 alt 文本
- [ ] 表单输入有 label
- [ ] 颜色不是唯一的信息传达方式
- [ ] `prefers-reduced-motion` 已处理

## 平台特有
- [ ] 移动端: 触摸目标 ≥ 44pt/48dp
- [ ] 小程序: 使用 rpx 而非 px
- [ ] 小程序: 安全区域已处理
- [ ] 桌面端: macOS 窗口控制在左，Windows 在右
