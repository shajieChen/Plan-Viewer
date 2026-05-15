# Design: Dashboard Glassmorphism 样式翻新

## 概述

对 Plan_Viewer 的 dashboard_template.html 进行全面视觉翻新，从当前的扁平深色主题升级为 Glassmorphism（毛玻璃）风格。引入 Tailwind CSS Play CDN 作为样式基础设施，重写所有组件的视觉表现，同时保持现有功能逻辑完全不变。

## 约束

- 单文件 HTML 架构不变（遵循 D-001 决策）
- React 组件逻辑、数据流、API 接口不变
- 允许引入 Tailwind CSS Play CDN
- 目标浏览器：Chrome 88+, Firefox 78+, Safari 14+（本地工具，用户可控）

## Section 1：视觉语言与色彩体系

### 背景系统

- **主背景**：深色渐变 `bg-gradient-to-br from-slate-900 via-purple-900/20 to-slate-900`，取代纯色 `#1a1a2e`
- **表面层级**（由低到高）：
  - Level 0（页面底）：渐变背景
  - Level 1（主内容区、sidebar）：`bg-white/5 backdrop-blur-xl border border-white/10`
  - Level 2（卡片、toolbar）：`bg-white/10 backdrop-blur-md border border-white/15`
  - Level 3（弹窗、hover 态）：`bg-white/15 backdrop-blur-lg border border-white/20`

### Glassmorphism 核心参数

| 元素 | 背景透明度 | Blur 强度 | 边框 | 阴影 |
|------|-----------|----------|------|------|
| Toolbar | white/10 | backdrop-blur-xl | white/10 | shadow-lg shadow-black/20 |
| Sidebar | white/5 | backdrop-blur-xl | white/10 | shadow-xl shadow-black/30 |
| 卡片 (artifact-card) | white/10 | backdrop-blur-sm | white/15 | shadow-md |
| Modal | white/10 | backdrop-blur-2xl | white/15 | shadow-2xl shadow-black/40 |
| 按钮 (default) | white/5 | backdrop-blur-sm | white/10 | — |
| 按钮 (hover) | white/15 | — | white/20 | shadow-lg |

### 强调色

保留现有状态色映射：
- draft: `#6b7280` (Gray)
- reviewed: `#3b82f6` (Blue)
- approved: `#6366f1` (Indigo)
- ready: `#10b981` (Green)
- blocked: `#ef4444` (Red)
- needs_update: `#f59e0b` (Amber)
- invalidated: `#991b1b` (Dark red)
- deprecated: `#78716c` (Brown-gray)
- archived: `#d1d5db` (Light gray)

在 glassmorphism 语境下增加发光效果：
- 活跃 tab：`bg-blue-500/20 border-blue-400/50 shadow-blue-500/25`
- Status badge：保持实色背景，加 `shadow-[color]/30` 微光

### 文字层次

- 主标题：`text-white`
- 正文：`text-white/80`
- 次要信息：`text-white/50`
- 禁用/占位：`text-white/30`

## Section 2：布局重构

### Toolbar

- 从贴顶实色条改为浮动毛玻璃条：`mx-4 mt-4 rounded-2xl`
- 内部三区布局：左（项目名+选择器）、中（pill 形 tab）、右（过滤器+按钮）
- 活跃 tab：`bg-blue-500/20 border border-blue-400/40 shadow-lg shadow-blue-500/20`

### 主内容区

- 间距 `p-4`，与 toolbar 一致
- 视图容器：`bg-white/5 backdrop-blur-xl rounded-2xl border border-white/10 p-4`

### Sidebar

- 背景：`bg-white/5 backdrop-blur-2xl border-l border-white/10`
- 字段分隔：`divide-y divide-white/5`
- Markdown Preview 区块用 Level 2 毛玻璃卡片包裹

### Swim Lane Grid

- 列头/行标签：`bg-white/5 backdrop-blur-sm rounded-lg`
- 单元格：`bg-white/3 rounded-xl border border-white/5`，hover 时 `bg-white/8 border-white/15`
- Artifact 卡片：`bg-[statusColor]/20 backdrop-blur-sm border border-[statusColor]/30`，hover 时 `bg-[statusColor]/40 scale-105`

### Hotspot Panel → Bento Grid

- CSS Grid 不对称布局：如果存在 blocked 项，第一个 blocked 项占 `col-span-2`（大卡片突出显示）；如果没有 blocked 项但有 needs_update 项，则第一个 needs_update 项占 `col-span-2`；如果只有 1 个 hotspot 项，则不使用 col-span-2，正常单列显示
- 卡片：`bg-white/5 backdrop-blur-xl rounded-2xl border border-white/10 p-6`
- 左侧色条改为渐变背景：`bg-gradient-to-r from-red-500/20 to-transparent`（blocked）或 `from-amber-500/20`（needs_update）

### Project Manager Modal

- Overlay：`bg-black/60 backdrop-blur-sm`
- Modal：`bg-white/10 backdrop-blur-2xl rounded-3xl border border-white/15 shadow-2xl`
- 列表项：`bg-white/5 rounded-xl border border-white/10`，hover 时 `bg-white/10`

## Section 3：微交互与动效

### 基础过渡

所有交互元素：`transition-all duration-300 ease-out`

### 卡片交互

- Hover：`scale-[1.02] shadow-xl` + 边框亮度提升
- Active：`scale-[0.98]` 200ms 回弹
- 入场动画：`@keyframes fadeSlideUp`（opacity 0→1, translateY 8px→0），每卡片延迟 50ms

### Tab 切换

- 背景色 `transition-all duration-200`
- 视图切换：opacity 过渡 300ms

### Sidebar 展开/收起

- `transition-all duration-300 ease-out`（translateX + opacity）

### 按钮反馈

- Hover：`bg-white/15 shadow-lg translate-y-[-1px]`
- Active：`bg-white/20 translate-y-[0px] shadow-sm`
- Focus-visible：`ring-2 ring-blue-400/50 ring-offset-2 ring-offset-transparent`

### DAG 节点

- SVG 节点 hover：`filter: brightness(1.2) drop-shadow(0 0 8px currentColor)`

### Hotspot 脉冲

- Blocked 卡片：`@keyframes pulseGlow` 红色阴影 2s 循环

### 滚动条

- webkit scrollbar：6px 宽，thumb `bg-white/20 rounded-full`，hover `bg-white/30`

## Section 4：技术实现策略

### Tailwind CDN 引入

```html
<script src="https://cdn.tailwindcss.com"></script>
<script>
  tailwind.config = {
    theme: {
      extend: {
        animation: {
          'fade-slide-up': 'fadeSlideUp 0.4s ease-out forwards',
          'pulse-glow': 'pulseGlow 2s ease-in-out infinite',
        },
        keyframes: {
          fadeSlideUp: {
            '0%': { opacity: '0', transform: 'translateY(8px)' },
            '100%': { opacity: '1', transform: 'translateY(0)' },
          },
          pulseGlow: {
            '0%, 100%': { boxShadow: '0 0 8px rgba(239,68,68,0.2)' },
            '50%': { boxShadow: '0 0 16px rgba(239,68,68,0.4)' },
          },
        },
      },
    },
  }
</script>
```

### 迁移策略（渐进替换）

1. **Phase 1**：引入 Tailwind CDN + config，保留现有 CSS 作为 fallback
2. **Phase 2**：逐组件迁移（Toolbar → Sidebar → SwimLane → Hotspot → Modal → DAG）
3. **Phase 3**：删除已被 Tailwind 替代的旧 CSS 规则
4. **Phase 4**：保留必要的自定义 CSS（Mermaid 覆盖、scrollbar、复杂 keyframes）

### 保留的自定义 CSS

- `.node:hover` Mermaid SVG 节点效果
- `::-webkit-scrollbar` 系列
- Mermaid `classDef` 覆盖
- 无法用 Tailwind config 表达的复杂动画

### 组件变化程度

| 组件 | 变化程度 | 说明 |
|------|---------|------|
| App (layout) | 中 | grid 结构用 Tailwind 重写 |
| Toolbar | 高 | 完全用 Tailwind class 重写 |
| SwimLaneView | 中 | grid 保留，卡片样式重写 |
| DAGView | 低 | 只改外层容器和控制按钮 |
| StateMachineView | 低 | 只改容器样式 |
| HotspotPanel | 高 | 布局改为 Bento Grid + 全新卡片 |
| DetailSidebar | 中 | 毛玻璃背景 + 字段样式重写 |
| ProjectManager | 中 | Modal 样式重写 |

## 验收标准

1. 所有现有功能正常工作（DAG 渲染、节点点击、sidebar 展示、tab 切换、过滤器、auto-refresh、项目管理）
2. 页面呈现 Glassmorphism 视觉风格（毛玻璃背景、层次感、发光强调色）
3. 所有交互有流畅的过渡动画（无突变）
4. Hotspot 面板使用 Bento Grid 布局
5. 现有测试全部通过（render_dashboard.py 的测试不受影响，因为只改模板样式）
6. 页面在 Chrome/Edge 最新版中表现正常
