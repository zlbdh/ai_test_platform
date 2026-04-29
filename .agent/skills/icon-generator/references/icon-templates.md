# 图标代码模板

各框架的图标使用模板和最佳实践。

## React + Lucide（推荐）

### 基本使用

```tsx
import { Home, Search, Settings } from 'lucide-react'

function Navbar() {
  return (
    <nav>
      <Home className="w-5 h-5" />
      <Search className="w-5 h-5" />
      <Settings className="w-5 h-5" />
    </nav>
  )
}
```

### 动态图标映射（✅ Tree-Shaking 安全）

```tsx
import { Home, Search, Settings, User, Bell, type LucideIcon } from 'lucide-react'

// ✅ 显式映射，只打包使用到的图标
const ICON_MAP: Record<string, LucideIcon> = {
  home:     Home,
  search:   Search,
  settings: Settings,
  user:     User,
  bell:     Bell,
}

interface IconProps {
  name: keyof typeof ICON_MAP
  size?: number
  className?: string
}

function DynamicIcon({ name, size = 20, className }: IconProps) {
  const Icon = ICON_MAP[name]
  if (!Icon) return null
  return <Icon size={size} className={className} />
}
```

### ❌ 错误做法

```tsx
// ❌ 导入全部图标，无法 Tree-Shaking
import * as Icons from 'lucide-react'
const Icon = Icons[iconName]  // 全部 1400+ 图标都会被打包！
```

### 带颜色和事件

```tsx
<Heart
  className="w-5 h-5 text-red-500 hover:scale-110 transition-transform cursor-pointer"
  fill={liked ? 'currentColor' : 'none'}
  onClick={() => setLiked(!liked)}
/>
```

## Vue + Lucide

### Vue 基本使用

```vue
<script setup>
import { Home, Search, Settings } from 'lucide-vue-next'
</script>

<template>
  <nav>
    <Home :size="20" />
    <Search :size="20" />
    <Settings :size="20" />
  </nav>
</template>
```

### 动态组件

```vue
<script setup>
import { Home, Search, Settings } from 'lucide-vue-next'
import { computed } from 'vue'

const props = defineProps<{ iconName: string }>()

const iconMap = { Home, Search, Settings }
const IconComponent = computed(() => iconMap[props.iconName])
</script>

<template>
  <component :is="IconComponent" :size="20" v-if="IconComponent" />
</template>
```

## 纯 HTML + Iconify CDN

### Web Component 方式

```html
<!-- 引入 Iconify -->
<script src="https://code.iconify.design/3/3.1.0/iconify.min.js"></script>

<!-- 使用图标 -->
<span class="iconify" data-icon="lucide:home" data-width="24"></span>
<span class="iconify" data-icon="mdi:settings" data-width="24" style="color: #333;"></span>
<span class="iconify" data-icon="heroicons:bell" data-width="24"></span>
```

### SVG URL 直接引用

```html
<!-- 通过 Iconify API 获取 SVG -->
<img src="https://api.iconify.design/lucide/home.svg?color=%23333&height=24" alt="首页" width="24" height="24" />

<!-- 导航栏示例 -->
<nav style="display: flex; gap: 16px; align-items: center;">
  <img src="https://api.iconify.design/lucide/home.svg?height=20" alt="首页" />
  <img src="https://api.iconify.design/lucide/search.svg?height=20" alt="搜索" />
  <img src="https://api.iconify.design/lucide/bell.svg?height=20" alt="通知" />
  <img src="https://api.iconify.design/lucide/user.svg?height=20" alt="用户" />
</nav>
```

### 内联 SVG

```html
<!-- 最佳性能（无网络请求），但代码较多 -->
<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24"
     fill="none" stroke="currentColor" stroke-width="2"
     stroke-linecap="round" stroke-linejoin="round">
  <path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>
  <polyline points="9 22 9 12 15 12 15 22"/>
</svg>
```

## React + Heroicons（Tailwind 项目）

```tsx
// 线条风格（Outline）
import { HomeIcon, MagnifyingGlassIcon } from '@heroicons/react/24/outline'
// 实心风格（Solid）
import { HomeIcon, MagnifyingGlassIcon } from '@heroicons/react/24/solid'
// 迷你风格（Mini）
import { HomeIcon, MagnifyingGlassIcon } from '@heroicons/react/20/solid'

function Example() {
  return <HomeIcon className="h-6 w-6 text-gray-500" />
}
```

## React + Phosphor（多粗细）

```tsx
import { House, MagnifyingGlass, Gear } from '@phosphor-icons/react'

function Example() {
  return (
    <>
      {/* 支持 6 种粗细 */}
      <House size={24} weight="thin" />
      <House size={24} weight="light" />
      <House size={24} weight="regular" />    {/* 默认 */}
      <House size={24} weight="bold" />
      <House size={24} weight="fill" />
      <House size={24} weight="duotone" />
    </>
  )
}
```

## 图标按钮通用模式

```tsx
interface IconButtonProps {
  icon: React.ComponentType<{ className?: string }>
  label: string
  onClick?: () => void
  variant?: 'ghost' | 'outline' | 'solid'
}

function IconButton({ icon: Icon, label, onClick, variant = 'ghost' }: IconButtonProps) {
  const baseClass = 'p-2 rounded-lg transition-colors'
  const variantClass = {
    ghost:   'hover:bg-gray-100',
    outline: 'border border-gray-300 hover:bg-gray-50',
    solid:   'bg-primary text-white hover:bg-primary/90',
  }

  return (
    <button className={`${baseClass} ${variantClass[variant]}`} onClick={onClick} aria-label={label}>
      <Icon className="w-5 h-5" />
    </button>
  )
}
```
