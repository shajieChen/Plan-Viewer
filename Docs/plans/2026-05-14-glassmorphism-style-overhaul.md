# Glassmorphism 样式翻新 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 dashboard_template.html 从扁平深色主题全面升级为 Glassmorphism 毛玻璃风格，引入 Tailwind CSS Play CDN，重写所有组件视觉表现。

**Architecture:** 在现有单文件 HTML 中引入 Tailwind CDN script 标签，渐进替换现有 BEM CSS 为 Tailwind utility classes + 少量自定义 CSS。React 组件逻辑不变，只改 className 属性。

**Tech Stack:** Tailwind CSS Play CDN, React 18 (CDN), Mermaid.js, CSS backdrop-filter

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `dashboard_template.html` | Modify | 唯一需要修改的文件 — 引入 Tailwind CDN、重写 style 块、重写所有组件 JSX className |

本次翻新只涉及一个文件。由于是纯样式变更，不需要新建测试文件。现有的 `tests/test_dashboard_generator.py` 等测试验证的是数据生成逻辑，不受影响。

---

## Task 1: 引入 Tailwind CDN 和自定义配置

**Files:**
- Modify: `dashboard_template.html:8-22` (head 区域，CDN 引入位置)

- [ ] **Step 1: 在 marked.js CDN 之后、`<style>` 标签之前插入 Tailwind CDN**

在 `dashboard_template.html` 第 22 行（`<!-- marked.js -->` script 标签之后）插入：

```html
    <!-- Tailwind CSS Play CDN -->
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

- [ ] **Step 2: 验证页面仍能正常加载**

在浏览器中打开 `http://localhost:8000/dashboard.html`，确认：
- 页面正常渲染（Tailwind CDN 加载不影响现有样式）
- 控制台无报错
- 现有功能正常

---

## Task 2: 重写 body 背景和全局基础样式

**Files:**
- Modify: `dashboard_template.html:24-40` (style 块开头的 Reset & Base 部分)

- [ ] **Step 1: 替换 body 样式**

将现有的 body CSS：
```css
body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
    background: #1a1a2e;
    color: #e0e0e0;
    min-height: 100vh;
    overflow: hidden;
}
```

替换为：
```css
body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
    min-height: 100vh;
    overflow: hidden;
}
```

- [ ] **Step 2: 在 `<body>` 标签上添加 Tailwind class**

将 `<body>` 改为：
```html
<body class="bg-gradient-to-br from-slate-900 via-purple-900/20 to-slate-900 text-white/80">
```

- [ ] **Step 3: 添加自定义滚动条和动画 CSS**

在 `<style>` 块末尾（`</style>` 之前）添加：
```css
/* === Custom Scrollbar === */
::-webkit-scrollbar {
    width: 6px;
}
::-webkit-scrollbar-track {
    background: transparent;
}
::-webkit-scrollbar-thumb {
    background: rgba(255, 255, 255, 0.2);
    border-radius: 9999px;
}
::-webkit-scrollbar-thumb:hover {
    background: rgba(255, 255, 255, 0.3);
}

/* === Mermaid Node Hover === */
.node:hover rect,
.node:hover polygon,
.node:hover circle {
    filter: brightness(1.2) drop-shadow(0 0 8px currentColor);
    transition: filter 0.2s ease;
}

/* === Card Stagger Animation === */
.stagger-item {
    opacity: 0;
    animation: fadeSlideUp 0.4s ease-out forwards;
}

@keyframes fadeSlideUp {
    0% { opacity: 0; transform: translateY(8px); }
    100% { opacity: 1; transform: translateY(0); }
}
```

- [ ] **Step 4: 验证渐变背景生效**

刷新页面，确认背景从纯色变为深色渐变，文字颜色正常。

---

## Task 3: 重写 Toolbar 组件

**Files:**
- Modify: `dashboard_template.html` — App 组件 JSX 中 toolbar 部分（约第 1870-1930 行）

- [ ] **Step 1: 删除旧的 toolbar CSS 规则**

从 `<style>` 块中删除所有 `.toolbar` 相关的 CSS 规则（约第 55-130 行的 toolbar 相关样式）。

- [ ] **Step 2: 重写 App 组件中 toolbar 的 JSX**

将 toolbar 的 JSX 从：
```jsx
<div className="toolbar">
    <span className="toolbar__title">
        {selectedProject || 'Dashboard'}
    </span>
    ...
</div>
```

替换为：
```jsx
<div className="mx-4 mt-4 px-6 py-3 rounded-2xl bg-white/10 backdrop-blur-xl border border-white/10 shadow-lg shadow-black/20 flex items-center gap-4 z-10">
    <span className="text-lg font-semibold text-white mr-2">
        {selectedProject || 'Dashboard'}
    </span>

    {/* Project selector */}
    {projectNames.length >= 2 && (
        <select
            className="px-3 py-1.5 rounded-lg border border-white/10 bg-white/5 backdrop-blur-sm text-white/80 text-sm cursor-pointer focus:outline-none focus:ring-2 focus:ring-blue-400/50"
            value={selectedProject || ''}
            onChange={(e) => handleProjectChange(e.target.value)}
        >
            {projectNames.map(name => (
                <option key={name} value={name} className="bg-slate-800 text-white">{name}</option>
            ))}
        </select>
    )}

    {/* View tabs */}
    <div className="flex gap-1 ml-4">
        {views.map(view => (
            <button
                key={view.id}
                className={`px-4 py-1.5 rounded-lg text-sm transition-all duration-200 ${
                    activeView === view.id
                        ? 'bg-blue-500/20 border border-blue-400/40 text-white shadow-lg shadow-blue-500/20'
                        : 'border border-transparent text-white/50 hover:bg-white/10 hover:text-white/80'
                }`}
                onClick={() => setActiveView(view.id)}
            >
                {view.label}
            </button>
        ))}
    </div>

    {/* Filters + actions */}
    <div className="flex gap-3 ml-auto items-center">
        {filterTypes.map(filter => (
            <label key={filter.id} className="flex items-center gap-1.5 text-xs text-white/50 cursor-pointer hover:text-white/70 transition-colors">
                <input
                    type="checkbox"
                    checked={activeFilters[filter.id]}
                    onChange={() => handleFilterToggle(filter.id)}
                    className="accent-blue-500 w-3.5 h-3.5"
                />
                {filter.label}
            </label>
        ))}

        <button
            className="px-3 py-1.5 rounded-lg border border-white/10 bg-white/5 text-white/50 text-sm cursor-pointer transition-all duration-200 hover:bg-white/15 hover:text-white/80 hover:shadow-lg hover:-translate-y-px active:translate-y-0 active:shadow-sm"
            onClick={handleRefresh}
            title="Refresh dashboard"
        >
            ↻ Refresh
        </button>

        <button
            className="px-3 py-1.5 rounded-lg border border-white/10 bg-white/5 text-white/50 text-sm cursor-pointer transition-all duration-200 hover:bg-white/15 hover:text-white/80 hover:shadow-lg hover:-translate-y-px active:translate-y-0 active:shadow-sm"
            onClick={() => setShowProjectManager(true)}
            title="管理项目"
        >
            管理项目
        </button>
    </div>
</div>
```

- [ ] **Step 3: 验证 toolbar 渲染正确**

刷新页面，确认：
- Toolbar 呈现浮动毛玻璃效果（圆角、半透明、模糊背景）
- Tab 切换正常，活跃 tab 有蓝色发光效果
- 过滤器和按钮功能正常

---

## Task 4: 重写主内容区布局和 App Container

**Files:**
- Modify: `dashboard_template.html` — style 块中 `.app-container` 和 `.main-content` 规则，以及 App JSX

- [ ] **Step 1: 删除旧的 layout CSS**

从 `<style>` 块中删除 `.app-container` 和 `.main-content` 的 CSS 规则。

- [ ] **Step 2: 重写 App 组件的外层容器 JSX**

将：
```jsx
<div className="app-container">
```

替换为：
```jsx
<div className="h-screen w-screen grid grid-rows-[auto_1fr] grid-cols-[1fr_auto]" style={{gridTemplateAreas: '"toolbar toolbar" "main sidebar"'}}>
```

- [ ] **Step 3: 重写主内容区容器**

将：
```jsx
<div className="main-content">
```

替换为：
```jsx
<div className="p-4 overflow-hidden flex flex-col" style={{gridArea: 'main'}}>
```

- [ ] **Step 4: 为每个视图添加毛玻璃面板包裹**

在 DAGView、SwimLaneView、StateMachineView、HotspotPanel 的外层各加一个容器 div：

```jsx
{!hasNoProjects && activeView === 'dag' && currentProjectData && (
    <div className="flex-1 bg-white/5 backdrop-blur-xl rounded-2xl border border-white/10 p-4 overflow-hidden flex flex-col">
        <DAGView
            artifacts={currentProjectData.artifacts}
            dependencies={currentProjectData.dependencies}
            activeFilters={activeFilters}
            onArtifactSelect={handleArtifactSelect}
        />
    </div>
)}
{!hasNoProjects && activeView === 'swimlane' && currentProjectData && (
    <div className="flex-1 bg-white/5 backdrop-blur-xl rounded-2xl border border-white/10 p-4 overflow-auto">
        <SwimLaneView
            artifacts={currentProjectData.artifacts || []}
            activeFilters={activeFilters}
            onArtifactSelect={handleArtifactSelect}
        />
    </div>
)}
{!hasNoProjects && activeView === 'statemachine' && currentProjectData && (
    <div className="flex-1 bg-white/5 backdrop-blur-xl rounded-2xl border border-white/10 p-4 overflow-auto">
        <StateMachineView artifacts={currentProjectData.artifacts || []} />
    </div>
)}
{!hasNoProjects && activeView === 'hotspots' && currentProjectData && (
    <div className="flex-1 bg-white/5 backdrop-blur-xl rounded-2xl border border-white/10 p-4 overflow-auto">
        <HotspotPanel
            artifacts={currentProjectData.artifacts || []}
            changeEvents={currentProjectData.change_events || []}
            onArtifactSelect={handleArtifactSelect}
        />
    </div>
)}
```

- [ ] **Step 5: 验证布局正确**

刷新页面，确认主内容区有毛玻璃面板包裹，各视图正常显示。

---

## Task 5: 重写 DetailSidebar 组件样式

**Files:**
- Modify: `dashboard_template.html` — DetailSidebar 组件 JSX（约第 1380-1500 行）

- [ ] **Step 1: 删除旧的 sidebar CSS**

从 `<style>` 块中删除所有 `.sidebar` 相关的 CSS 规则（`.sidebar`、`.sidebar--closed`、`.sidebar__header`、`.sidebar__title`、`.sidebar__close-btn`、`.sidebar__field`、`.sidebar__field-label`、`.sidebar__field-value`、`.sidebar__dep-list`、`.sidebar__preview` 等）。

- [ ] **Step 2: 重写 DetailSidebar 的外层容器**

将 sidebar 的外层 div 从：
```jsx
<div className={`sidebar ${!isOpen ? 'sidebar--closed' : ''}`} style={isOpen ? { width: sidebarWidth + 'px', position: 'relative' } : {}}>
```

替换为：
```jsx
<div
    className={`bg-white/5 backdrop-blur-2xl border-l border-white/10 shadow-xl shadow-black/30 overflow-y-auto transition-all duration-300 ease-out ${!isOpen ? 'w-0 p-0 overflow-hidden translate-x-full' : 'p-5'}`}
    style={isOpen ? { width: sidebarWidth + 'px', position: 'relative', gridArea: 'sidebar' } : { gridArea: 'sidebar' }}
>
```

- [ ] **Step 3: 重写 resize handle**

将：
```jsx
<div
    className={`sidebar__resize-handle ${isResizing ? 'sidebar__resize-handle--active' : ''}`}
    onMouseDown={handleResizeStart}
/>
```

替换为：
```jsx
<div
    className={`absolute left-0 top-0 w-1 h-full cursor-col-resize z-5 transition-colors duration-200 hover:bg-blue-500 ${isResizing ? 'bg-blue-500' : 'bg-transparent'}`}
    onMouseDown={handleResizeStart}
/>
```

- [ ] **Step 4: 重写 sidebar header**

将：
```jsx
<div className="sidebar__header">
    <span className="sidebar__title">Artifact Details</span>
    <button className="sidebar__close-btn" onClick={onClose} aria-label="Close sidebar">✕</button>
</div>
```

替换为：
```jsx
<div className="flex justify-between items-center mb-4">
    <span className="text-base font-semibold text-white">Artifact Details</span>
    <button
        className="bg-transparent border-none text-white/50 text-lg cursor-pointer p-1 px-2 rounded hover:bg-white/10 hover:text-white/80 transition-all duration-200"
        onClick={onClose}
        aria-label="Close sidebar"
    >
        ✕
    </button>
</div>
```

- [ ] **Step 5: 重写 sidebar 字段区域**

将每个 `sidebar__field` div 替换为带分隔线的样式：

```jsx
<div className="py-3 border-b border-white/5">
    <div className="text-[0.7rem] text-white/40 uppercase tracking-wider mb-1">ID</div>
    <div className="text-sm text-white/80">{artifact.id}</div>
</div>
```

对所有字段（ID、Source File、Type、Status、Group、Dependencies、Last Checked）应用相同模式。

- [ ] **Step 6: 重写 Markdown Preview 区块**

将：
```jsx
<div className="sidebar__preview">
    <div className="sidebar__preview-title">{preview.title}</div>
    ...
</div>
```

替换为：
```jsx
<div className="mt-1 p-3 bg-white/10 backdrop-blur-md rounded-xl border border-white/15">
    <div className="text-sm font-semibold text-white mb-1.5">{preview.title}</div>
    {preview.excerpt && (
        <div className="text-xs text-white/50 leading-relaxed">{preview.excerpt}</div>
    )}
</div>
```

- [ ] **Step 7: 验证 sidebar 功能**

点击一个 artifact 节点，确认 sidebar 滑出、显示详情、resize 拖拽正常、关闭按钮正常。

---

## Task 6: 重写 SwimLaneView 组件样式

**Files:**
- Modify: `dashboard_template.html` — SwimLaneView 组件 JSX（约第 780-870 行）

- [ ] **Step 1: 删除旧的 swimlane CSS**

从 `<style>` 块中删除 `.swimlane-grid`、`.swimlane-grid__header`、`.swimlane-grid__row-label`、`.swimlane-grid__cell`、`.artifact-card` 相关的 CSS 规则。

- [ ] **Step 2: 重写 SwimLaneView grid 容器**

将：
```jsx
<div
    className="swimlane-grid"
    style={{ gridTemplateColumns: `auto repeat(${GROUPS.length}, 1fr)`, gridTemplateRows: `auto repeat(${visibleTypes.length}, auto)` }}
>
```

替换为：
```jsx
<div
    className="grid gap-2 w-full"
    style={{ gridTemplateColumns: `auto repeat(${GROUPS.length}, 1fr)`, gridTemplateRows: `auto repeat(${visibleTypes.length}, auto)` }}
>
```

- [ ] **Step 3: 重写 header cells**

将：
```jsx
<div key={group} className="swimlane-grid__header">{group}</div>
```

替换为：
```jsx
<div key={group} className="text-xs font-semibold text-white/50 text-center py-2 px-1 bg-white/5 backdrop-blur-sm rounded-lg">{group}</div>
```

空角落 header 同样改为：
```jsx
<div className="text-xs font-semibold text-white/50 text-center py-2 px-1 bg-white/5 backdrop-blur-sm rounded-lg"></div>
```

- [ ] **Step 4: 重写 row labels**

将：
```jsx
<div className="swimlane-grid__row-label">{type}</div>
```

替换为：
```jsx
<div className="text-xs font-medium text-white/50 py-2 px-3 flex items-start bg-white/5 backdrop-blur-sm rounded-lg">{type}</div>
```

- [ ] **Step 5: 重写 grid cells**

将：
```jsx
<div key={`${group}-${type}`} className="swimlane-grid__cell">
```

替换为：
```jsx
<div key={`${group}-${type}`} className="flex flex-col gap-1.5 p-2 min-h-[60px] bg-white/[0.03] rounded-xl border border-white/5 transition-all duration-200 hover:bg-white/[0.08] hover:border-white/15">
```

- [ ] **Step 6: 重写 artifact cards**

将：
```jsx
<div
    key={artifact.id}
    className="artifact-card"
    style={{ backgroundColor: STATUS_COLORS[artifact.status] || '#6b7280' }}
    onClick={() => onArtifactSelect(artifact)}
    ...
>
    <div className="artifact-card__id">{artifact.id}</div>
    <div className="artifact-card__status">{artifact.status}</div>
</div>
```

替换为：
```jsx
<div
    key={artifact.id}
    className="p-2 px-3 rounded-lg cursor-pointer transition-all duration-200 backdrop-blur-sm border hover:scale-[1.02] hover:shadow-xl active:scale-[0.98]"
    style={{
        backgroundColor: (STATUS_COLORS[artifact.status] || '#6b7280') + '33',
        borderColor: (STATUS_COLORS[artifact.status] || '#6b7280') + '4D',
    }}
    onClick={() => onArtifactSelect(artifact)}
    role="button"
    tabIndex={0}
    onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') onArtifactSelect(artifact); }}
    aria-label={`Artifact ${artifact.id}, status ${artifact.status}`}
>
    <div className="text-xs font-medium text-white break-all">{artifact.id}</div>
    <div className="text-[0.65rem] text-white/60 mt-0.5">{artifact.status}</div>
</div>
```

- [ ] **Step 7: 验证 Swim Lane 视图**

切换到 Swim Lane tab，确认 grid 布局正常、卡片有半透明状态色、hover 效果流畅。

---

## Task 7: 重写 HotspotPanel 为 Bento Grid 布局

**Files:**
- Modify: `dashboard_template.html` — HotspotPanel 组件 JSX（约第 1260-1370 行）

- [ ] **Step 1: 删除旧的 hotspot CSS**

从 `<style>` 块中删除 `.hotspot-panel`、`.hotspot-card`、`.hotspot-card--blocked`、`.hotspot-card--needs_update`、`.hotspot-card__id`、`.hotspot-card__reason`、`.hotspot-card__action` 相关的 CSS 规则。

- [ ] **Step 2: 重写 HotspotPanel 容器和布局**

将 HotspotPanel 的 return JSX 从：
```jsx
<div className="hotspot-panel">
    {hotspots.map(artifact => (
        <div
            key={artifact.id}
            className={`hotspot-card hotspot-card--${artifact.status}`}
            ...
        >
```

替换为：
```jsx
<div className="grid grid-cols-2 gap-4 auto-rows-auto">
    {hotspots.map((artifact, index) => {
        // First blocked item or first item overall gets col-span-2 (if more than 1 total)
        const isHero = index === 0 && hotspots.length > 1;
        return (
            <div
                key={artifact.id}
                className={`${isHero ? 'col-span-2' : ''} bg-white/5 backdrop-blur-xl rounded-2xl border border-white/10 p-6 cursor-pointer transition-all duration-300 hover:bg-white/10 hover:scale-[1.01] hover:shadow-xl ${artifact.status === 'blocked' ? 'animate-pulse-glow' : ''}`}
                onClick={() => onArtifactSelect(artifact)}
            >
                {/* Gradient accent bar */}
                <div className={`h-1 w-16 rounded-full mb-4 ${
                    artifact.status === 'blocked'
                        ? 'bg-gradient-to-r from-red-500 to-red-500/0'
                        : 'bg-gradient-to-r from-amber-500 to-amber-500/0'
                }`} />
                <div className="text-base font-semibold text-white mb-1">{artifact.id}</div>
                <div className="text-sm text-white/50 mb-3">
                    {getReasonForArtifact(artifact.id)}
                </div>
                <div className={`text-xs font-medium ${
                    artifact.status === 'blocked' ? 'text-red-400' : 'text-amber-400'
                }`}>
                    {getSuggestedAction(artifact.status)}
                </div>
            </div>
        );
    })}
</div>
```

- [ ] **Step 3: 重写空状态**

将：
```jsx
<div className="hotspot-panel">
    <div className="empty-state">No items currently need attention</div>
</div>
```

替换为：
```jsx
<div className="flex items-center justify-center h-full">
    <div className="text-center text-white/40 text-sm">No items currently need attention</div>
</div>
```

- [ ] **Step 4: 验证 Hotspot 面板**

切换到 Hotspots tab，确认：
- Bento Grid 布局生效（第一项占两列）
- Blocked 卡片有脉冲发光动画
- 渐变色条正确显示
- 点击卡片能打开 sidebar

---

## Task 8: 重写 DAGView 控制按钮和容器样式

**Files:**
- Modify: `dashboard_template.html` — DAGView 组件 JSX（约第 1050-1250 行）

- [ ] **Step 1: 删除旧的 DAG CSS**

从 `<style>` 块中删除 `.dag-view`、`.dag-view__diagram`、`.dag-view__diagram--dragging`、`.dag-view__diagram-inner`、`.dag-view__zoom-controls`、`.dag-view__zoom-btn`、`.dag-view__controls`、`.dag-view__group-toggle` 相关的 CSS 规则。

- [ ] **Step 2: 重写 DAGView 外层容器**

将：
```jsx
<div className="dag-view">
```

替换为：
```jsx
<div className="w-full flex flex-col flex-1 min-h-0 overflow-hidden">
```

- [ ] **Step 3: 重写 group toggle 按钮**

将：
```jsx
<div className="dag-view__controls">
    {visibleGroups.map(groupName => (
        <button
            key={groupName}
            className={`dag-view__group-toggle ${collapsedGroups.has(groupName) ? 'dag-view__group-toggle--collapsed' : ''}`}
            ...
        >
```

替换为：
```jsx
<div className="flex gap-2 mb-3 flex-wrap">
    {visibleGroups.map(groupName => (
        <button
            key={groupName}
            className={`px-3 py-1 rounded-lg border text-xs cursor-pointer transition-all duration-200 ${
                collapsedGroups.has(groupName)
                    ? 'bg-white/10 border-white/20 text-white/80'
                    : 'bg-white/5 border-white/10 text-white/50 hover:bg-white/10 hover:text-white/70'
            }`}
            onClick={() => toggleGroup(groupName)}
            title={collapsedGroups.has(groupName) ? `Expand ${groupName}` : `Collapse ${groupName}`}
        >
            {collapsedGroups.has(groupName) ? '\u25B6' : '\u25BC'} {groupName}
        </button>
    ))}
</div>
```

- [ ] **Step 4: 重写 diagram 容器和 zoom controls**

将 diagram wrapper 从：
```jsx
<div
    ref={diagramWrapperRef}
    className={`dag-view__diagram ${isDragging ? 'dag-view__diagram--dragging' : ''}`}
    onMouseDown={handleMouseDown}
>
    <div
        ref={containerRef}
        className="dag-view__diagram-inner"
        style={{ transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})` }}
    />
    <div className="dag-view__zoom-controls">
        <button className="dag-view__zoom-btn" onClick={() => setZoom(z => z + 0.2)} title="Zoom in">+</button>
        <button className="dag-view__zoom-btn" onClick={() => setZoom(z => Math.max(z - 0.2, 0.1))} title="Zoom out">−</button>
        <button className="dag-view__zoom-btn" onClick={resetView} title="Fit to screen">⟲</button>
    </div>
</div>
```

替换为：
```jsx
<div
    ref={diagramWrapperRef}
    className={`overflow-hidden relative flex-1 ${isDragging ? 'cursor-grabbing' : 'cursor-grab'}`}
    onMouseDown={handleMouseDown}
>
    <div
        ref={containerRef}
        className="origin-top-left inline-block"
        style={{ transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})` }}
    />
    <div className="absolute bottom-3 right-3 flex gap-1 z-5">
        <button className="w-8 h-8 rounded-lg border border-white/10 bg-white/5 backdrop-blur-sm text-white/80 text-base cursor-pointer flex items-center justify-center transition-all duration-200 hover:bg-white/15 hover:shadow-lg" onClick={() => setZoom(z => z + 0.2)} title="Zoom in">+</button>
        <button className="w-8 h-8 rounded-lg border border-white/10 bg-white/5 backdrop-blur-sm text-white/80 text-base cursor-pointer flex items-center justify-center transition-all duration-200 hover:bg-white/15 hover:shadow-lg" onClick={() => setZoom(z => Math.max(z - 0.2, 0.1))} title="Zoom out">−</button>
        <button className="w-8 h-8 rounded-lg border border-white/10 bg-white/5 backdrop-blur-sm text-white/80 text-base cursor-pointer flex items-center justify-center transition-all duration-200 hover:bg-white/15 hover:shadow-lg" onClick={resetView} title="Fit to screen">⟲</button>
    </div>
</div>
```

- [ ] **Step 5: 验证 DAG 视图**

确认 DAG 图正常渲染、缩放/平移正常、group toggle 按钮正常、节点点击正常。

---

## Task 9: 重写 ProjectManager Modal 样式

**Files:**
- Modify: `dashboard_template.html` — ProjectManager 组件 JSX（约第 1500-1650 行）

- [ ] **Step 1: 删除旧的 project manager CSS**

从 `<style>` 块中删除所有 `.project-manager-overlay`、`.project-manager-panel` 相关的 CSS 规则。

- [ ] **Step 2: 重写 overlay**

将：
```jsx
<div className="project-manager-overlay" onClick={handleOverlayClick}>
```

替换为：
```jsx
<div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-[1000]" onClick={handleOverlayClick}>
```

- [ ] **Step 3: 重写 modal panel**

将：
```jsx
<div className="project-manager-panel">
```

替换为：
```jsx
<div className="bg-white/10 backdrop-blur-2xl rounded-3xl border border-white/15 shadow-2xl shadow-black/40 p-6 w-[90%] max-w-[600px] max-h-[80vh] flex flex-col">
```

- [ ] **Step 4: 重写 modal header**

将：
```jsx
<div className="project-manager-panel__header">
    <span className="project-manager-panel__title">项目管理</span>
    <button className="project-manager-panel__close-btn" ...>×</button>
</div>
```

替换为：
```jsx
<div className="flex justify-between items-center mb-5">
    <span className="text-xl font-semibold text-white">项目管理</span>
    <button
        className="bg-transparent border-none text-white/50 text-2xl cursor-pointer p-1 px-2 rounded-lg leading-none hover:bg-white/10 hover:text-white/80 transition-all duration-200"
        onClick={onClose}
        aria-label="Close project manager"
    >
        ×
    </button>
</div>
```

- [ ] **Step 5: 重写 project list items**

将：
```jsx
<div key={project.path || index} className="project-manager-panel__item">
```

替换为：
```jsx
<div key={project.path || index} className="flex items-center justify-between p-3 px-4 bg-white/5 rounded-xl border border-white/10 mb-2 transition-all duration-200 hover:bg-white/10">
```

项目名和路径的 class 改为：
```jsx
<div className="text-sm font-medium text-white mb-0.5">{/* name */}</div>
<div className="text-xs text-white/30 break-all font-mono">{/* path */}</div>
```

删除按钮改为：
```jsx
<button
    className="bg-transparent border-none text-white/30 text-lg cursor-pointer p-1 px-2 rounded-lg ml-2 flex-shrink-0 hover:bg-red-500/15 hover:text-red-400 transition-all duration-200"
    onClick={() => onRemove && onRemove(project.path)}
    aria-label={`Remove project ${project.name || project.path}`}
>
    ×
</button>
```

- [ ] **Step 6: 重写 add area 和 footer**

输入框：
```jsx
<input
    className="flex-1 px-3 py-2 rounded-xl border border-white/10 bg-white/5 backdrop-blur-sm text-white/80 text-sm outline-none focus:border-blue-400/50 focus:ring-2 focus:ring-blue-400/20 placeholder:text-white/30"
    ...
/>
```

按钮（添加）：
```jsx
<button className="px-4 py-2 rounded-xl bg-blue-500/20 border border-blue-400/40 text-white text-sm cursor-pointer transition-all duration-200 hover:bg-blue-500/30 hover:shadow-lg hover:shadow-blue-500/20" ...>添加</button>
```

按钮（浏览）：
```jsx
<button className="px-4 py-2 rounded-xl border border-white/10 bg-white/5 text-white/70 text-sm cursor-pointer transition-all duration-200 hover:bg-white/10" ...>浏览</button>
```

清空全部按钮：
```jsx
<button className="px-4 py-2 rounded-xl border border-red-500/40 text-red-400 text-sm cursor-pointer transition-all duration-200 hover:bg-red-500/15" ...>清空全部</button>
```

- [ ] **Step 7: 验证 Modal 功能**

点击"管理项目"按钮，确认 modal 弹出、毛玻璃效果正确、添加/删除/清空功能正常。

---

## Task 10: 重写 StateMachineView 和 Empty State 样式

**Files:**
- Modify: `dashboard_template.html` — StateMachineView 和 empty state 相关 JSX

- [ ] **Step 1: 删除旧的 statemachine 和 empty-state CSS**

从 `<style>` 块中删除 `.statemachine-view` 和 `.empty-state` 的 CSS 规则。

- [ ] **Step 2: 重写 StateMachineView 容器**

将：
```jsx
<div className="statemachine-view" ref={containerRef}>
```

替换为：
```jsx
<div className="w-full overflow-auto" ref={containerRef}>
```

- [ ] **Step 3: 重写所有 empty-state 引用**

将所有：
```jsx
<div className="empty-state">...</div>
<p className="empty-state">...</p>
```

替换为：
```jsx
<div className="text-center py-10 px-5 text-white/40 text-sm">...</div>
<p className="text-center py-10 px-5 text-white/40 text-sm">...</p>
```

- [ ] **Step 4: 重写"请添加项目"空状态页面**

将 App 中无数据时的空状态 JSX 改为：
```jsx
<div className="flex items-center justify-center h-full">
    <div className="text-center text-white/40">
        <p className="text-xl mb-4">请添加项目目录以开始</p>
        <button
            className="px-5 py-2.5 rounded-xl bg-blue-500/20 border border-blue-400/40 text-white text-base cursor-pointer transition-all duration-200 hover:bg-blue-500/30 hover:shadow-lg hover:shadow-blue-500/20"
            onClick={() => setShowProjectManager(true)}
        >
            添加项目
        </button>
    </div>
</div>
```

- [ ] **Step 5: 验证**

确认 State Machine 视图正常渲染，空状态页面样式正确。

---

## Task 11: 清理旧 CSS 和 status-badge 样式

**Files:**
- Modify: `dashboard_template.html` — `<style>` 块

- [ ] **Step 1: 删除所有已被 Tailwind 替代的 CSS 规则**

删除以下 CSS 规则组（保留 Mermaid 覆盖和自定义 scrollbar/animation）：
- `.toolbar` 及所有 `toolbar__*` 规则
- `.main-content`
- `.sidebar` 及所有 `sidebar__*` 规则
- `.swimlane-grid` 及所有 `swimlane-grid__*` 规则
- `.artifact-card` 及所有 `artifact-card__*` 规则
- `.dag-view` 及所有 `dag-view__*` 规则
- `.statemachine-view`
- `.hotspot-panel` 及所有 `hotspot-card__*` 规则
- `.empty-state`
- `.project-manager-overlay` 及所有 `project-manager-panel__*` 规则
- `.toolbar__manage-btn`
- `.app-container`

- [ ] **Step 2: 保留并更新 status-badge**

将 `.status-badge` 改为 Tailwind 兼容的最小 CSS：
```css
.status-badge {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 6px;
    font-size: 0.75rem;
    font-weight: 500;
    color: #ffffff;
    box-shadow: 0 0 8px var(--badge-glow, transparent);
}
```

- [ ] **Step 3: 保留 Mermaid 相关 CSS**

确保以下规则保留在 `<style>` 块中：
```css
.mermaid {
    background: transparent;
}

.dag-view svg {
    max-width: none;
}
```

更新为：
```css
.mermaid {
    background: transparent;
}
```

（`dag-view svg` 规则已不需要，因为 DAGView 不再使用 `.dag-view` class）

- [ ] **Step 4: 确认最终 style 块内容**

最终 `<style>` 块应只包含：
1. Reset（box-sizing）
2. body 基础（font-family, min-height, overflow）
3. 自定义 scrollbar
4. Mermaid node hover 效果
5. Card stagger animation keyframes
6. `.status-badge` 规则
7. `.mermaid { background: transparent }`
8. 状态色 class（`.status--draft` 等，如果仍有引用的话；否则也删除）

- [ ] **Step 5: 验证全部功能**

完整测试所有功能：
- 切换所有 4 个 tab
- 点击 artifact 打开 sidebar
- 使用过滤器
- 打开/关闭项目管理 modal
- DAG 缩放/平移
- Auto-refresh（修改数据后确认页面自动刷新）

---

## Task 12: 最终验收和微调

**Files:**
- Modify: `dashboard_template.html`

- [ ] **Step 1: 浏览器兼容性检查**

在 Chrome/Edge 中打开页面，确认：
- backdrop-filter 效果正常（毛玻璃可见）
- 渐变背景正确
- 所有动画流畅（无卡顿）
- 无控制台错误

- [ ] **Step 2: 响应式检查**

缩小浏览器窗口到 1024px 宽度，确认：
- Toolbar 内容不溢出（必要时 flex-wrap）
- Sidebar 不遮挡主内容
- Bento Grid 在窄屏下降级为单列

- [ ] **Step 3: 性能检查**

打开 DevTools Performance tab，确认：
- 页面加载时间 < 3s（含 CDN）
- 滚动/动画无 layout thrashing
- backdrop-filter 不导致明显掉帧

- [ ] **Step 4: 运行现有测试**

```bash
python -m pytest tests/ -v
```

确认所有测试通过（样式变更不影响 Python 生成逻辑）。

- [ ] **Step 5: 微调**

根据视觉检查结果，微调：
- 毛玻璃透明度（如果太透或太不透明）
- 动画时长（如果感觉太快或太慢）
- 间距（如果某些区域太紧凑或太松散）

---
