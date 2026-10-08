# Icon Search Workflow Examples

## Scenario 1: Choose Icons for an Online Store

### Requirements

Choose five icons for an e-commerce app's bottom navigation bar.

### Steps

#### Step 1: Identify Concepts

- Home, categories, cart, messages, profile

#### Step 2: Consult the Semantic Mapping

| Concept | Lucide icon |
| ------ | ------------ |
| Home | `Home` |
| Categories | `LayoutGrid` |
| Cart | `ShoppingCart` |
| Messages | `MessageCircle` |
| Profile | `User` |

#### Step 3: Verify That Icons Exist

```bash
# Verify through the Iconify API
curl "https://api.iconify.design/lucide/home.svg" -o /dev/null -s -w "%{http_code}"
# 200 = exists
```

#### Step 4: Export Code

```tsx
import { Home, LayoutGrid, ShoppingCart, MessageCircle, User } from 'lucide-react'

const tabs = [
  { icon: Home,           label: 'Home' },
  { icon: LayoutGrid,     label: 'Categories' },
  { icon: ShoppingCart,    label: 'Cart' },
  { icon: MessageCircle,   label: 'Messages' },
  { icon: User,           label: 'Profile' },
]

function TabBar() {
  const [active, setActive] = useState(0)
  return (
    <nav className="fixed bottom-0 w-full bg-white border-t flex justify-around py-2">
      {tabs.map((tab, i) => (
        <button key={i} onClick={() => setActive(i)}
                className={`flex flex-col items-center ${active === i ? 'text-primary' : 'text-gray-400'}`}>
          <tab.icon className="w-6 h-6" />
          <span className="text-xs mt-1">{tab.label}</span>
        </button>
      ))}
    </nav>
  )
}
```

---

## Scenario 2: Search the API for an Unfamiliar Icon

### Requirement Description

Find a QR code icon without knowing its icon name.

### Search Steps

#### Step 1: Search the Iconify API

```bash
node scripts/iconify-search.js search "qr code"
# Or call the API directly
curl "https://api.iconify.design/search?query=qr+code&limit=10"
```

#### Step 2: Inspect Search Results

```text
Found 15 results:
1. lucide:qr-code
2. mdi:qrcode
3. heroicons:qr-code
4. tabler:qrcode
5. ph:qr-code
...
```

#### Step 3: Preview and Choose

Open `https://api.iconify.design/lucide/qr-code.svg` in a browser to preview it.

#### Step 4: Get the SVG Code

```bash
node scripts/iconify-search.js get lucide:qr-code --size 24
```

---

## Scenario 3: Choose Dashboard Icons

### Dashboard Requirements

A data analytics dashboard needs overview, users, revenue, orders, and trends.

### Recommendation Process

```text
Overview → LayoutDashboard (dashboard layout)
Users    → Users (multiple users)
Revenue  → DollarSign or Wallet (financial concepts)
Orders   → Package (delivery package)
Trends   → TrendingUp (upward trend)
```

### Code

```tsx
import {
  LayoutDashboard,
  Users,
  DollarSign,
  Package,
  TrendingUp,
} from 'lucide-react'

const menuItems = [
  { icon: LayoutDashboard, label: 'Overview', path: '/dashboard' },
  { icon: Users,           label: 'Users',    path: '/users' },
  { icon: DollarSign,      label: 'Revenue',  path: '/revenue' },
  { icon: Package,         label: 'Orders',   path: '/orders' },
  { icon: TrendingUp,      label: 'Trends',   path: '/analytics' },
]
```

---

## Scenario 4: Get AI Brand Icons

### Brand Icon Requirements

Display brand icons beside a list of supported AI models.

### Retrieval Steps

#### Step 1: Identify Icon Names

| Model | Icon name |
| ------ | -------- |
| GPT-4 | `openai` |
| Claude | `claude` |
| Gemini | `gemini` |
| Qwen | `qwen` |

#### Step 2: Build CDN URLs

```html
<div class="flex gap-4">
  <img src="https://raw.githubusercontent.com/lobehub/lobe-icons/refs/heads/master/packages/static-png/dark/openai.png"
       alt="OpenAI" width="32" height="32" />
  <img src="https://raw.githubusercontent.com/lobehub/lobe-icons/refs/heads/master/packages/static-png/dark/claude.png"
       alt="Claude" width="32" height="32" />
  <img src="https://raw.githubusercontent.com/lobehub/lobe-icons/refs/heads/master/packages/static-png/dark/gemini.png"
       alt="Gemini" width="32" height="32" />
  <img src="https://raw.githubusercontent.com/lobehub/lobe-icons/refs/heads/master/packages/static-png/dark/qwen.png"
       alt="Qwen" width="32" height="32" />
</div>
```
