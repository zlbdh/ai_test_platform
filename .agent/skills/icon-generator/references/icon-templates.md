# Icon Code Templates

Framework-specific icon templates and best practices.

## React + Lucide (Recommended)

### Basic Usage

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

### Dynamic Icon Mapping (✅ Safe for Tree Shaking)

```tsx
import { Home, Search, Settings, User, Bell, type LucideIcon } from 'lucide-react'

// ✅ Explicit mapping bundles only the icons in use
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

### ❌ Incorrect Approach

```tsx
// ❌ Importing every icon prevents tree shaking
import * as Icons from 'lucide-react'
const Icon = Icons[iconName]  // All 1,400+ icons will be bundled!
```

### Colors and Events

```tsx
<Heart
  className="w-5 h-5 text-red-500 hover:scale-110 transition-transform cursor-pointer"
  fill={liked ? 'currentColor' : 'none'}
  onClick={() => setLiked(!liked)}
/>
```

## Vue + Lucide

### Basic Vue Usage

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

### Dynamic Components

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

## Plain HTML + Iconify CDN

### Web Components

```html
<!-- Load Iconify -->
<script src="https://code.iconify.design/3/3.1.0/iconify.min.js"></script>

<!-- Use an icon -->
<span class="iconify" data-icon="lucide:home" data-width="24"></span>
<span class="iconify" data-icon="mdi:settings" data-width="24" style="color: #333;"></span>
<span class="iconify" data-icon="heroicons:bell" data-width="24"></span>
```

### Direct SVG URLs

```html
<!-- Retrieve an SVG through the Iconify API -->
<img src="https://api.iconify.design/lucide/home.svg?color=%23333&height=24" alt="Home" width="24" height="24" />

<!-- Navigation example -->
<nav style="display: flex; gap: 16px; align-items: center;">
  <img src="https://api.iconify.design/lucide/home.svg?height=20" alt="Home" />
  <img src="https://api.iconify.design/lucide/search.svg?height=20" alt="Search" />
  <img src="https://api.iconify.design/lucide/bell.svg?height=20" alt="Notifications" />
  <img src="https://api.iconify.design/lucide/user.svg?height=20" alt="User" />
</nav>
```

### Inline SVG

```html
<!-- Best performance (no network request), with more markup -->
<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24"
     fill="none" stroke="currentColor" stroke-width="2"
     stroke-linecap="round" stroke-linejoin="round">
  <path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>
  <polyline points="9 22 9 12 15 12 15 22"/>
</svg>
```

## React + Heroicons (Tailwind Projects)

```tsx
// Outline style
import { HomeIcon, MagnifyingGlassIcon } from '@heroicons/react/24/outline'
// Solid style
import { HomeIcon, MagnifyingGlassIcon } from '@heroicons/react/24/solid'
// Mini style
import { HomeIcon, MagnifyingGlassIcon } from '@heroicons/react/20/solid'

function Example() {
  return <HomeIcon className="h-6 w-6 text-gray-500" />
}
```

## React + Phosphor (Multiple Weights)

```tsx
import { House, MagnifyingGlass, Gear } from '@phosphor-icons/react'

function Example() {
  return (
    <>
      {/* Six supported weights */}
      <House size={24} weight="thin" />
      <House size={24} weight="light" />
      <House size={24} weight="regular" />    {/* Default */}
      <House size={24} weight="bold" />
      <House size={24} weight="fill" />
      <House size={24} weight="duotone" />
    </>
  )
}
```

## Reusable Icon Button Pattern

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
