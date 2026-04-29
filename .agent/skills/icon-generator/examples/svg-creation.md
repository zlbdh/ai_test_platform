# SVG 图标创建示例

从零手写 SVG 图标的实战示例。

## 基础模板

```xml
<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24"
     fill="none" stroke="currentColor" stroke-width="2"
     stroke-linecap="round" stroke-linejoin="round">
  <!-- 图标路径 -->
</svg>
```

## 示例一：完成图标（✓ 圆圈）

```xml
<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24"
     fill="none" stroke="currentColor" stroke-width="2"
     stroke-linecap="round" stroke-linejoin="round">
  <circle cx="12" cy="12" r="10"/>
  <path d="M8 12l3 3 5-5"/>
</svg>
```

## 示例二：渐变盾牌

```xml
<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24">
  <defs>
    <linearGradient id="g" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#3b82f6"/>
      <stop offset="100%" stop-color="#1d4ed8"/>
    </linearGradient>
  </defs>
  <path d="M12 2L4 6v5c0 5.25 3.4 10.2 8 11.5 4.6-1.3 8-6.25 8-11.5V6L12 2z"
        fill="url(#g)" stroke="none"/>
  <path d="M9 12l2 2 4-4" fill="none" stroke="#fff" stroke-width="2"
        stroke-linecap="round" stroke-linejoin="round"/>
</svg>
```

## 示例三：脉搏心跳

```xml
<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24"
     fill="none" stroke="currentColor" stroke-width="2"
     stroke-linecap="round" stroke-linejoin="round">
  <polyline points="2,12 6,12 8,8 10,16 12,10 14,14 16,12 22,12"/>
</svg>
```

## SVG 元素速查

| 元素 | 用途 | 关键属性 |
| ---- | ---- | -------- |
| `<line>` | 直线 | `x1, y1, x2, y2` |
| `<rect>` | 矩形 | `x, y, width, height, rx` |
| `<circle>` | 圆形 | `cx, cy, r` |
| `<polyline>` | 折线 | `points` |
| `<path>` | 任意形状 | `d`（路径命令） |

## Path 命令速查

| 命令 | 元素 | 说明 |
| ---- | ---- | ---- |
| `M x y` | 移动到 | `M 10 10` |
| `L x y` | 直线到 | `L 20 20` |
| `Q cx cy x y` | 二次贝塞尔曲线 | `Q 15 5 20 10` |
| `C cx1 cy1 cx2 cy2 x y` | 三次贝塞尔曲线 | `C 10 5 15 5 20 10` |
| `A rx ry angle large sweep x y` | 弧线 | `A 10 10 0 0 1 20 20` |

## 设计技巧

1. **24×24 画布** — 行业标准尺寸
2. **留 2px 内边距** — 内容在 2~22 范围
3. **使用 `currentColor`** — 继承文字颜色
4. **统一描边** — `stroke-width="2"`
5. **圆角处理** — `stroke-linecap="round"` + `stroke-linejoin="round"`
6. **简单优先** — 16×16 下也能辨识
