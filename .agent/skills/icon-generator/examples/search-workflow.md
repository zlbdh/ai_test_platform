# 图标搜索工作流示例

## 场景一：为电商网站选择图标

### 需求

为一个电商应用的底部导航栏选择 5 个图标。

### 步骤

#### 步骤 1：确定概念

- 首页、分类、购物车、消息、我的

#### 步骤 2：查语义映射表

| 概念 | Lucide 图标 |
| ------ | ------------ |
| 首页 | `Home` |
| 分类 | `LayoutGrid` |
| 购物车 | `ShoppingCart` |
| 消息 | `MessageCircle` |
| 我的 | `User` |

#### 步骤 3：验证图标存在

```bash
# 通过 Iconify API 验证
curl "https://api.iconify.design/lucide/home.svg" -o /dev/null -s -w "%{http_code}"
# 200 = 存在
```

#### 步骤 4：导出代码

```tsx
import { Home, LayoutGrid, ShoppingCart, MessageCircle, User } from 'lucide-react'

const tabs = [
  { icon: Home,           label: '首页' },
  { icon: LayoutGrid,     label: '分类' },
  { icon: ShoppingCart,    label: '购物车' },
  { icon: MessageCircle,   label: '消息' },
  { icon: User,           label: '我的' },
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

## 场景二：通过 API 搜索未知图标

### 需求描述

需要一个"二维码"图标，不知道叫什么名字。

### 搜索步骤

#### 步骤 1：搜索 Iconify API

```bash
node scripts/iconify-search.js search "qr code"
# 或直接调用 API
curl "https://api.iconify.design/search?query=qr+code&limit=10"
```

#### 步骤 2：查看搜索结果

```text
找到 15 个结果：
1. lucide:qr-code
2. mdi:qrcode
3. heroicons:qr-code
4. tabler:qrcode
5. ph:qr-code
...
```

#### 步骤 3：预览并选择

访问 `https://api.iconify.design/lucide/qr-code.svg` 在浏览器中预览。

#### 步骤 4：获取 SVG 代码

```bash
node scripts/iconify-search.js get lucide:qr-code --size 24
```

---

## 场景三：为仪表盘选择一组图标

### 仪表盘需求

数据分析仪表盘，需要：概览、用户、收入、订单、趋势

### 推荐过程

```text
概览    → LayoutDashboard（仪表盘布局）
用户    → Users（多用户）
收入    → DollarSign 或 Wallet（钱相关）
订单    → Package（快递包裹）
趋势    → TrendingUp（上升趋势）
```

### 代码

```tsx
import {
  LayoutDashboard,
  Users,
  DollarSign,
  Package,
  TrendingUp,
} from 'lucide-react'

const menuItems = [
  { icon: LayoutDashboard, label: '概览',   path: '/dashboard' },
  { icon: Users,           label: '用户',   path: '/users' },
  { icon: DollarSign,      label: '收入',   path: '/revenue' },
  { icon: Package,         label: '订单',   path: '/orders' },
  { icon: TrendingUp,      label: '趋势',   path: '/analytics' },
]
```

---

## 场景四：获取 AI 品牌图标

### 品牌图标需求

在页面上展示支持的 AI 模型列表，需要品牌图标。

### 获取步骤

#### 步骤 1：确定图标名称

| 模型 | 图标名 |
| ------ | -------- |
| GPT-4 | `openai` |
| Claude | `claude` |
| Gemini | `gemini` |
| 通义千问 | `qwen` |

#### 步骤 2：构建 CDN URL

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
