---
name: prototype-test-code-quality
description: HTML原型测试 — 代码规范与可迁移性审计。检验CSS设计系统一致性、JS代码规范、组件模式可迁移性、HTML语义化、安全隐患等代码质量维度。
---

# 代码规范与可迁移性审计

## 适用场景
当需要从**开发者/架构师视角**评估 HTML 原型的代码质量和框架迁移准备度时使用本技能。重点检查代码规范度与迁移到目标管理后台框架的就绪度。

---

## 审计检查清单

### 1. CSS 设计系统一致性
- [ ] **CSS 变量体系**：使用 `:root` 定义全局 CSS 变量，并保持变量命名一致
  ```css
  :root {
    --primary: #409EFF;
    --success: #67C23A;
    --warning: #E6A23C;
    --danger: #F56C6C;
  }
  ```
- [ ] **变量复用率**：样式广泛使用 `var(--xxx)` 引用变量，避免硬编码颜色值
- [ ] **颜色语义正确**：`.tag-success` 的背景色保持绿色系，避免误用蓝色 `#f0f9ff` 等配色
- [ ] **字体大小层级**：建立清晰的字体大小梯度，如 11px/12px/13px/14px/16px
- [ ] **各模块 CSS 一致性**：抽取 5 个模块的 `:root` 变量定义，确认内容完全一致

### 2. JavaScript 代码规范
- [ ] **全局函数命名**：遵循统一的命名约定，如 `renderTable()`、`handleSearch()`、`handleReset()`、`showDetail()`、`backToList()`
- [ ] **数据数组命名**：主数据数组统一采用 `xxxList` + `filtered` 命名模式
- [ ] **状态映射对象**：使用 `statusMap` / `typeMap` 等映射对象统一管理标签样式
- [ ] **事件绑定方式**：统一事件绑定约定，避免混用内联 `onclick=""` 与 `addEventListener`
- [ ] **代码注释**：为模块补齐标头注释，包含文件名、功能描述和需求来源
  ```javascript
  // =============================================
  // 模块：XXX — 列表页
  // 文件：modules/xxx-list.html
  // 需求来源：xx_需求.md § 3.1
  // =============================================
  ```

### 3. 组件模式可迁移性
- [ ] **函数拆分清晰**：为每个功能提供独立函数，例如 renderTable、handleSearch、showDetail，避免逻辑混杂
- [ ] **数据与视图分离**：把数据存储在 JS 数组中，通过函数完成渲染，避免直接在 HTML 中硬编码数据
- [ ] **弹窗模式统一**：所有弹窗统一采用 `.modal-mask + .modal` 模式
- [ ] **确认弹窗复用**：提供通用的 `showConfirm(msg, callback)` 函数
- [ ] **Toast 提示复用**：提供通用的 `showToast(msg, type)` 函数
- [ ] **迁移难度评估**：
  - 低难度：数据数组 → `ref([])`，`renderTable()` → `v-for`，`onclick` → `@click`
  - 中难度：弹窗 → `el-dialog + v-model`（需参考 dialog_v_model_pattern）
  - 高难度：复杂图表 → ECharts 组件封装

### 4. HTML 结构与语义化
- [ ] **表单 name 属性**：为 `<input>` / `<select>` / `<textarea>` 配置 `name` 属性
- [ ] **表单 id 唯一性**：确保所有元素的 `id` 属性全局唯一
- [ ] **语义化标签**：合理使用 `<header>`、`<main>`、`<footer>`、`<section>` 等 HTML5 语义标签
- [ ] **表格可访问性**：为 `<table>` 分离 `<thead>` 和 `<tbody>`
- [ ] **图片 alt 属性**：为 `<img>` 提供 `alt` 描述

### 5. 安全与性能
- [ ] **XSS 风险**：在 `innerHTML` 赋值时对用户输入做转义处理
  - 原型阶段 Mock 数据无风险，但需标注开发时的处理方案
- [ ] **密码安全**：避免使用 `Math.random()` 生成密码，改用安全随机方案
- [ ] **定时器清理**：为 `setInterval` / `setTimeout` 配置对应的 `clearInterval` / `clearTimeout`
- [ ] **内存泄漏**：为动态创建的 DOM 元素（如 Toast）提供移除机制

---

## 审计方法

### 步骤 1：CSS 系统一致性扫描
```bash
# 提取所有模块的 :root 定义进行对比
grep -h ":root{" modules/*.html | sort | uniq -c
```

### 步骤 2：函数命名统一性扫描
```bash
# 提取所有模块的 function 定义
grep -oh "function [a-zA-Z]*(" modules/*.html | sort | uniq -c | sort -rn
```

### 步骤 3：组件模式一致性检查
```
1. 抽取 5 个列表模块，比较其 renderTable() 的实现模式
2. 抽取 5 个表单模块，比较其 openForm() / submitForm() 的实现模式
3. 列出所有模块使用的弹窗模式（showConfirm/showToast）签名
```

### 步骤 4：迁移就绪度评估
```
对照目标管理后台框架，逐一评估：
- 数据层：Mock 数组 → API 调用
- 视图层：innerHTML → Vue template
- 交互层：onclick → @click + methods
- 组件层：自定义弹窗 → Element Plus
- 路由层：display:none → Vue Router
```

---

## 输出模板

```markdown
## 代码质量审计结果 — [模块名/全局]

### CSS 设计系统
| 检查项 | 状态 | 说明 |
|-------|------|------|
| :root 变量定义 | ✅ 一致 | 70 个模块变量定义相同 |
| 颜色语义正确 | ❌ 有误 | tag-success 背景色为蓝色系 |

### 代码规范
| 检查项 | 状态 | 说明 |
|-------|------|------|
| 函数命名一致 | ✅ | renderTable/handleSearch 模式统一 |
| 模块注释 | ✅ | 每个文件有标头注释 |
| name 属性 | ❌ | 全部表单缺少 name 属性 |

### 迁移就绪度
| 迁移项 | 难度 | 说明 |
|-------|------|------|
| 数据层 → API | 低 | 数据数组结构清晰 |
| 弹窗 → el-dialog | 中 | 需采用 v-model 模式 |
| 图表 → ECharts | 高 | CSS 伪图表需全部重写 |
```

---

## 典型问题模式

1. **CSS 变量语义错误**：`.tag-success` 使用蓝色系背景而非绿色系
2. **表单缺少 name 属性**：所有 input 仅有 id 无 name
3. **innerHTML XSS 风险**：数据直接拼接进 HTML 字符串无转义
4. **密码使用 Math.random()**：密码生成不安全
5. **setInterval 无清理**：定时器在页面切换后仍在运行
