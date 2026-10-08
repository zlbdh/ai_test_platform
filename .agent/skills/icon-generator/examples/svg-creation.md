# SVG Icon Creation Examples

Practical examples of writing SVG icons from scratch.

## Basic Template

```xml
<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24"
     fill="none" stroke="currentColor" stroke-width="2"
     stroke-linecap="round" stroke-linejoin="round">
  <!-- Icon paths -->
</svg>
```

## Example 1: Completion Icon (Checkmark in a Circle)

```xml
<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24"
     fill="none" stroke="currentColor" stroke-width="2"
     stroke-linecap="round" stroke-linejoin="round">
  <circle cx="12" cy="12" r="10"/>
  <path d="M8 12l3 3 5-5"/>
</svg>
```

## Example 2: Gradient Shield

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

## Example 3: Heartbeat Pulse

```xml
<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24"
     fill="none" stroke="currentColor" stroke-width="2"
     stroke-linecap="round" stroke-linejoin="round">
  <polyline points="2,12 6,12 8,8 10,16 12,10 14,14 16,12 22,12"/>
</svg>
```

## SVG Element Reference

| Element | Purpose | Key attributes |
| ---- | ---- | -------- |
| `<line>` | Straight line | `x1, y1, x2, y2` |
| `<rect>` | Rectangle | `x, y, width, height, rx` |
| `<circle>` | Circle | `cx, cy, r` |
| `<polyline>` | Connected line segments | `points` |
| `<path>` | Arbitrary shape | `d` (path commands) |

## Path Command Reference

| Command | Operation | Example |
| ---- | ---- | ---- |
| `M x y` | Move to | `M 10 10` |
| `L x y` | Line to | `L 20 20` |
| `Q cx cy x y` | Quadratic Bézier curve | `Q 15 5 20 10` |
| `C cx1 cy1 cx2 cy2 x y` | Cubic Bézier curve | `C 10 5 15 5 20 10` |
| `A rx ry angle large sweep x y` | Arc | `A 10 10 0 0 1 20 20` |

## Design Tips

1. **24×24 canvas** — standard industry size.
2. **2px padding** — keep content within the 2–22 range.
3. **Use `currentColor`** — inherit the text color.
4. **Consistent strokes** — `stroke-width="2"`.
5. **Rounded ends and joins** — `stroke-linecap="round"` + `stroke-linejoin="round"`.
6. **Prefer simplicity** — icons must remain recognizable at 16×16.
