# Dwell Cancel via Immediate Cursor Signal — Design Spec

## Summary

修复 `useWindowAutoShrink` 在窗口缩小后无法正确"取消放大恢复"和"鼠标移出后透明化"的 Bug。根因是 dwell 取消逻辑依赖了带 3s 防抖的 `hoverState`，使得 2s 的 restore dwell 计时器永远先于"离开"信号到期。修复方式是把 `useWindowHover` 拆成两路信号：即时的 `cursorPresent`（驱动 dwell 与 shrink 触发）和 3s 防抖的 `opacityState`（驱动透明度），并让 `useWindowAutoShrink` 改用 `cursorPresent` 作为输入。

## Bug Description

**复现路径**：

1. 窗口处于缩小状态（400×300，透明）。
2. 鼠标进入窗口 → 立即不透明，启动 2s restoreTimer（dwell 等待）。
3. 在 2s 内（如 1s 后）鼠标移出窗口。

**预期**：

- restoreTimer 被取消，窗口保持 400×300。
- 一段时间（约 3s）后窗口透明化，回到初始外观。

**实际**：

- restoreTimer 仍在 t=2s 触发，窗口被错误放大到 savedSize。
- 透明度也未按预期恢复（被新的 active 状态续上）。

### 根因分析

`useWindowHover` 当前返回单一 `state`：

- `mouseenter` 立即设为 `'active'`。
- `mouseleave` 启动 3s 计时器后才设为 `'idle'`。

`useWindowAutoShrink` 用这个 `hoverState` 既驱动 shrink，也驱动 dwell 取消：

```js
if (prevState === 'active' && hoverState === 'idle') {
  if (restoreTimerRef.current) clearTimeout(restoreTimerRef.current);
  if (enabled) performShrink();
}
```

时序冲突：

| 时间 | 事件 | hoverState | restoreTimer |
|------|------|------------|--------------|
| t=0 | enter | active | 启动 (2s) |
| t=1s | leave | active（仍在 3s 防抖窗口内） | 仍在跑 |
| **t=2s** | **dwell 到期** | **active** | **触发 performRestore** ❌ |
| t=4s | leave + 3s 到期 | idle | （已晚） |

由于 hoverState 的"离开"通知被推迟 3s，dwell 取消条件永远不会在 dwell 期间被满足。这是一个状态机时序错配 bug，不是简单的边界条件。

## Fix Strategy

让透明度防抖与 dwell 取消解耦——它们时序无关，本就不该共用一个状态机。

`useWindowHover` 暴露两路独立信号：

- **`cursorPresent: boolean`** — 即时反映鼠标是否在窗口内。`mouseenter` → true，`mouseleave` → false。
- **`opacityState: 'idle' | 'active'`** — 保留 3s 防抖行为，专门驱动 CSS 透明度。

`useWindowAutoShrink` 输入参数从 `hoverState` 改为 `cursorPresent`。dwell timer 启动 / 取消、shrink 触发条件全部基于 `cursorPresent` 的即时翻转，opacity 仍走 `opacityState`。

## Architecture

### Scope of Change

- `plan-viewer-desktop/src/hooks/useWindowHover.js` — 返回值从 string 改为对象。
- `plan-viewer-desktop/src/hooks/useWindowAutoShrink.js` — 入参 `hoverState` 替换为 `cursorPresent`。
- `plan-viewer-desktop/src/App.jsx` — 解构调整，未使用解构清理。
- 现有 5 个 useWindowAutoShrink 测试文件 + 待新增的 useWindowHover 测试 — 适配新接口。

### `useWindowHover` 新接口

```js
function useWindowHover() {
  return {
    opacityState: 'idle' | 'active',  // 3s 离开防抖（保留旧行为）
    cursorPresent: boolean,           // 即时（mouseenter=true / mouseleave=false）
  };
}
```

实现要点：

- `mouseenter`：清离开计时器；同时设 `cursorPresent=true` 与 `opacityState='active'`。
- `mouseleave`：立即设 `cursorPresent=false`；启动 3s 计时器，到期后设 `opacityState='idle'`。
- 头部 JSDoc 把过时的 "1.5s" 注释更新为 "3s"。

### `useWindowAutoShrink` 新接口

```js
useWindowAutoShrink({
  cursorPresent,          // boolean ← 替代原 hoverState
  enabled,                // boolean
  initialSize,            // { width, height }
  restoreDelayMs = 2000,  // 不变
});
// 返回值不变：{ savedSize, isShrunk, isWaitingRestore }
```

内部状态机改为基于 `cursorPresent` 的边沿（boolean prevRef 翻转）：

- **false → true**：若 `savedSize` 存在则启动 restoreTimer；设 `isWaitingRestore=true`。
- **true → false**：若 restoreTimer 存在则清除并设 `isWaitingRestore=false`；若 `enabled` 则触发 `performShrink()`。
- 手动 resize 监听挂载条件由 `hoverState === 'active'` 改为 `cursorPresent === true`，行为等价。

### 数据流

```
DOM mouseenter/leave
       │
       ▼
 useWindowHover
   ├── opacityState ──► <div class="app-container {opacityState}"> ──► CSS opacity/blur
   └── cursorPresent ──► useWindowAutoShrink ──► restoreTimer / performShrink ──► Tauri setSize
```

两路独立计时、互不阻塞。

## Behavior Matrix（修复后）

| 当前状态 | 鼠标动作 | cursorPresent | opacityState | 结果 |
|---------|---------|---------------|--------------|------|
| 缩小 + 透明 | 进入 | false→true | idle→active | 立即不透明；启动 2s restoreTimer |
| 缩小 + 不透明（dwell 中） | 停留 ≥ 2s | true | active | 放大到 savedSize |
| 缩小 + 不透明（dwell 中） | < 2s 内离开 | true→false（即时） | active（保持 3s）| 立即取消 restoreTimer，窗口保持 400×300；3s 后透明化 |
| 已放大 + 不透明 | 离开 | true→false | active（3s 防抖）| 立即触发 shrink + 保存 savedSize；3s 后透明化 |
| 缩小状态多次快速划过 | 多次 enter/leave | 多次切换 | 维持 active | 每次 enter 重启 timer，每次 leave 立即清；窗口始终 400×300 |

## Edge Cases

1. **快速进出（< 2s）**：`cursorPresent` 立即翻转，restoreTimer 立刻被清，窗口保留 400×300；`opacityState` 仍 active 直到 3s 防抖期满后变 idle。
2. **同窗口内连续进出多次**：每次 enter 重启 2s timer（不累积），每次 leave 立即清。setTimeout/clearTimeout 是 O(1)，无泄漏。
3. **shrink 期间鼠标重新进入**：shrink 是 async；期间若 `cursorPresent` 又变 true，会再启动一个 restoreTimer。`isResizingRef` 仍保护 resize listener 不被自身事件污染；`savedSize` 在 shrink 启动时已写入，restore 能正确读到。
4. **手动 resize 在 dwell 等待期间**：手动 resize 监听挂载条件改为 `cursorPresent === true`。用户在等待期手动拉大 → savedSize 更新到新尺寸；restoreTimer 到期后 `performRestore` 用最新 savedSize。原 dwell-delay 设计文档描述的"手动放大后清理 dwell 状态"已实现行为保留。
5. **disabled auto-shrink**：`cursorPresent` true→false 时不触发 shrink；窗口从未被缩小，`savedSize` 为 null，restoreTimer 也不会启动。
6. **Tauri API 失败**：保留现有 try/catch + console.warn，不抛出。

## Testing Strategy

### 受影响的现有测试

把 `hoverState: 'active' / 'idle'` 全部替换为 `cursorPresent: true / false`：

- `useWindowAutoShrink.test.js`
- `useWindowAutoShrink.property.test.js`
- `useWindowAutoShrink.property2.test.js`
- `useWindowAutoShrink.property3.test.js`
- `useWindowAutoShrink.property4.test.js`

App.jsx 之外没有别的地方消费 useWindowHover 的返回值。

### 新增 / 强化 Property Tests

新增两条 property，专门覆盖此 bug 触及的不变量：

| Property | 输入 | 断言 |
|----------|------|------|
| **dwell-cancel responds immediately to cursor leave** | 在缩小状态下 cursorPresent=true 并启动 restoreTimer，随后任意 t ∈ (0, 2000ms) 设 cursorPresent=false | `setSize(savedSize)` 从未被调用；`isWaitingRestore === false` |
| **shrink fires on cursor leave without 3s debounce** | 已放大状态下 cursorPresent 从 true 翻 false | `setSize(initialSize)` 在 next tick 内被调度，无须模拟 3s 流逝 |

### 新增 useWindowHover 单元测试

- `mouseenter` 后 `cursorPresent === true` 且 `opacityState === 'active'`。
- `mouseleave` 后 `cursorPresent === false` 立即生效；`opacityState` 在 3s fake timer 流逝后才变 'idle'。
- `mouseleave` 后 < 3s 再次 `mouseenter`，`opacityState` 始终保持 'active'，`cursorPresent` 跟随翻转。

### 集成手测

- 缩小 → 进入 → 1s 内离开 → 确认窗口未放大、约 3s 后透明化。
- 缩小 → 进入 → 停留 > 2s → 确认窗口放大恢复。
- 已放大 → 离开 → 确认窗口立即缩小（不必等 3s）。

## Requirements Traceability

此修复影响 `window-auto-shrink` spec 的以下点（不新增 Requirement）：

- **Requirement 2（窗口恢复触发）AC 1**：恢复需 2s dwell — 现在能正确执行。
- **Requirement 3（计时器取消）**：dwell 取消现在响应即时 cursor 信号而非 3s 防抖信号。
- **新引入的不变量**：cursor leave 在 dwell 期间必须取消 restore（已加入 PBT）。

## Implementation Checklist

1. 修改 `useWindowHover.js`：返回对象 `{ opacityState, cursorPresent }`；更新 JSDoc。
2. 修改 `useWindowAutoShrink.js`：参数 `hoverState` → `cursorPresent`；`prevHoverStateRef` 改为 `prevCursorRef`；resize listener 挂载条件改用 `cursorPresent`。
3. 修改 `App.jsx`：解构新接口；CSS class 用 `opacityState`；hook 入参用 `cursorPresent`；删除未使用的 `{ savedSize, isShrunk }` 解构。
4. 更新现有 5 个 `useWindowAutoShrink` 测试文件以使用新参数名。
5. 新增 useWindowHover 单元测试文件。
6. 新增上述两条 dwell/shrink 即时性 property tests。
7. 手测三条集成路径。
