# Dependency Link Click-to-Highlight Design

**Date:** 2026-05-15  
**Status:** Approved  
**Scope:** plan-viewer-desktop exe 右侧 DetailPanel 中的 Dependencies 链接交互

## Overview

右侧 DetailPanel 的 Dependencies 列表中的条目从纯文本改为可点击链接。点击后：
1. 左侧泳道视图自动滚动到目标卡片
2. 目标卡片闪烁高亮 ~2.5 秒后自动消失
3. 若目标不存在于当前泳道，显示短暂的"未找到"toast

## Architecture

采用 **事件回调 + CSS 动画** 方案（方案 A），符合现有 props-down / events-up 的数据流模式。

### Data Flow

```
DetailPanel --onNavigateDep(depId)--> App --highlightedId--> SwimLane
                                       |
                                       +-- setTimeout 2500ms --> setHighlightedId(null)
```

## State Changes (App Layer)

| State | Type | Purpose |
|-------|------|---------|
| `highlightedId` | `string \| null` | 当前需要高亮闪烁的 artifact ID |
| `notFoundToast` | `string \| null` | "未找到"提示文字，1.5 秒后自动清除 |

## Component Changes

### DetailPanel

- **新增 prop:** `onNavigateDep(depId: string)`
- 依赖项渲染从 `<li>{dep}</li>` 改为 `<li><a class="dep-link" onClick={...}>{dep}</a></li>`
- 点击时调用 `onNavigateDep(depId)`

### SwimLane

- **新增 prop:** `highlightedId: string | null`
- 每个卡片 DOM 添加 `data-artifact-id={artifact.id}` 属性
- 当 `highlightedId` 匹配时，给卡片添加 `swimlane-card--highlight` CSS class
- 匹配到的卡片调用 `element.scrollIntoView({ behavior: 'smooth', block: 'nearest' })`

### App

- 新增 `highlightedId` 和 `notFoundToast` state
- 新增 `handleNavigateDep(depId)` 函数：
  - 在当前 `artifacts` 数组中查找目标 ID
  - 找到 → `setHighlightedId(depId)` + setTimeout 2500ms 清除
  - 找不到 → `setNotFoundToast("未找到: " + depId)` + setTimeout 1500ms 清除

## CSS & Animation

### 高亮动画

```css
@keyframes card-flash {
  0%, 100% { box-shadow: 0 0 0 0 transparent; }
  50% { box-shadow: 0 0 12px 3px rgba(99, 102, 241, 0.7); }
}

.swimlane-card--highlight {
  animation: card-flash 0.8s ease-in-out 3;  /* 闪烁3次 ≈ 2.4秒 */
  z-index: 10;
}
```

### 依赖链接样式

```css
.dep-link {
  color: var(--accent);
  text-decoration: underline;
  text-decoration-style: dotted;
  cursor: pointer;
  transition: opacity 0.2s;
}

.dep-link:hover {
  opacity: 0.8;
}
```

### 未找到 Toast

```css
.nav-toast {
  position: absolute;
  top: 8px;
  right: 8px;
  background: rgba(239, 68, 68, 0.9);
  color: white;
  padding: 4px 10px;
  border-radius: 4px;
  font-size: 11px;
  animation: fade-in-out 1.5s ease forwards;
}

@keyframes fade-in-out {
  0% { opacity: 0; transform: translateY(-4px); }
  15% { opacity: 1; transform: translateY(0); }
  85% { opacity: 1; }
  100% { opacity: 0; }
}
```

## Edge Cases

| Scenario | Behavior |
|----------|----------|
| 目标 ID 不在当前泳道 | 显示红色 toast "未找到: {id}"，1.5s 消失 |
| 快速连续点击多个依赖 | 每次点击重置 timer，高亮切换到最新目标 |
| 窗口处于 compact 模式 | SwimLane 不渲染，链接点击无效果（静默忽略） |

## Files Affected

| File | Change |
|------|--------|
| `src/components/DetailPanel.jsx` | 依赖项改为可点击链接，新增 `onNavigateDep` prop |
| `src/components/SwimLane.jsx` | 新增 `highlightedId` prop，卡片添加 data 属性和高亮 class，scrollIntoView |
| `src/App.jsx` | 新增状态和 handler，传递 props |
| `src/styles.css` | 新增高亮动画、链接样式、toast 样式 |
