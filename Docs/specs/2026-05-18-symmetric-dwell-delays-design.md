# Symmetric Dwell Delays — Design Spec

> **Update (option A pivot):** This spec originally specified option B — re-entry during the leave dwell does NOT cancel the pending shrink, with a chained restore afterwards. After integration testing the option B behavior felt wrong (users saw a useless shrink-then-restore animation when they re-entered the window). The behavior was inverted to **option A**: re-entry during leave dwell DOES cancel the pending shrink, symmetric with leave cancelling enter dwell. The Behavior Matrix, State Machine, Logic Flow, Edge Cases, and Testing sections below were updated to reflect option A. References to option B in the original prose are kept for history.

## Summary

把 Exe (`plan-viewer-desktop`) 桌面窗口的 hover dwell 行为对称化：

- 鼠标进入应用 → **1.5s** 停留后才放大（原 2s）
- 鼠标离开应用 → **1.5s** 停留后才缩小（原立即缩小）

**Option A**：两个 dwell timer 对称地被对方的 cursor 边沿即时取消。leave 取消正在等的 enter dwell；enter 取消正在等的 leave dwell。窗口要么完成完整的 1.5s dwell 后转换状态，要么保持当前状态——不存在 shrink-then-restore 的多余动画。

## Context

现有 `useWindowAutoShrink` 在 cursor `true → false` 边沿时立即调用 `performShrink()`。`restoreDelayMs` 默认 2000ms。这两个不对称的延迟使得：

- 进入时 2s 太长，用户感觉迟钝。
- 离开时 0s 太敏感，鼠标稍微划出窗口就触发缩小动画。

把进入延迟收紧到 1.5s、给离开补上 1.5s，整体节奏更平滑。

## Behavior Matrix（option A — 修改后）

| 当前状态 | 鼠标动作 | 结果 |
|---|---|---|
| 已放大 + 不透明 | leave | 启动 1.5s shrinkTimer；窗口尺寸暂不变 |
| 已放大 + leave dwell 中 | t < 1.5s 内 enter | **shrinkTimer 立即被取消**；窗口保持已放大尺寸（无 shrink，无后续 restore 循环） |
| 已放大 + leave dwell 中 | t < 1.5s 内 leave 再触发 | **重置 shrinkTimer**（旧 timer 清掉，重启 1.5s）|
| 已放大 + leave dwell 满 1.5s | timer fired | `performShrink()`；进入 SHRUNKEN 状态 |
| 缩小 + 透明 | enter | 立即不透明（CSS via `opacityState`）；启动 1.5s restoreTimer |
| 缩小 + 不透明（enter dwell 中）| 停留 ≥ 1.5s | `performRestore()` 到 savedSize |
| 缩小 + 不透明（enter dwell 中）| t < 1.5s 内 leave | **取消 restoreTimer**；启动 shrinkTimer（窗口已是 initialSize，到期 performShrink no-op）|

## Architecture

### Scope of Change

- `plan-viewer-desktop/src/hooks/useWindowAutoShrink.js` — 加 shrinkDelay 参数与 shrinkTimer。
- `plan-viewer-desktop/src/hooks/useWindowAutoShrink.test.js` 与 4 个 property test 文件 — 适配新延迟语义。
- 新增 1 个或扩展现有 property test 文件覆盖新不变量。

`useWindowHover.js` 与 `App.jsx` 不变。

### Interface

```js
useWindowAutoShrink({
  cursorPresent,           // boolean（来自 useWindowHover，现有）
  enabled,                 // boolean（现有）
  initialSize,             // { width, height }（现有）
  restoreDelayMs = 1500,   // 默认从 2000 改为 1500
  shrinkDelayMs  = 1500,   // 新增
});

// 返回
{
  savedSize,           // 现有
  isShrunk,            // 现有
  isWaitingRestore,    // 现有 — enter dwell 中
  isWaitingShrink,     // 新增 — leave dwell 中
}
```

`App.jsx` 当前只解构 `{ savedSize }`，无需改动。`isWaitingShrink` 暴露便于测试与未来 UI 反馈。

### State Machine

四个状态由 `cursorPresent` 边沿驱动：

```
        cursorPresent: false → true
   ┌────────────────────────────────────────┐
   │                                        ▼
ENLARGED  ──leave──►  LEAVE_DWELL  ──1.5s timer─►  performShrink()  ──►  SHRUNKEN
   ▲                      │                                                │
   │                      │ option B: re-entry does NOT cancel             │
   │                      ▼                                                │
   │                  fires regardless                                     │
   │                                                                       │
   │                                                                       ▼
   │                                                                  cursorPresent=true
   │                                                                       │
   │                                                                       ▼
   └────────────── performRestore() ◄──1.5s timer── ENTER_DWELL ──leave──► (cancel)
```

不变量：

- **enter dwell（restoreTimer）保留"被 cursor leave 即时取消"的行为** —— `dwell-cancel-cursor-signal-design` 已建立的修复，不破坏。
- **leave dwell（shrinkTimer）不被 cursor enter 取消**（option B）。
- 两个 timer 在边界上互斥：进入 LEAVE_DWELL 时清 restoreTimer；进入 ENTER_DWELL 时不清 shrinkTimer（option B 要求让它跑完）。

## Logic Flow

替代现有 `useEffect` 主体（cursor 边沿处理）：

```
cursor 边沿 false → true（enter）:
  // option B：不取消 shrinkTimer
  if (savedSize && !restoreTimerRef.current) {
    restoreTimerRef.current = setTimeout(performRestore, restoreDelayMs);
    isWaitingRestore = true;
  }

cursor 边沿 true → false（leave）:
  // 取消正在等待的 restore（保留现有修复）
  if (restoreTimerRef.current) {
    clearTimeout(restoreTimerRef.current);
    restoreTimerRef.current = null;
    isWaitingRestore = false;
  }
  if (enabled) {
    // 重置语义：连续 leave 重启计时（详见 Edge Case 2）
    if (shrinkTimerRef.current) {
      clearTimeout(shrinkTimerRef.current);
    }
    shrinkTimerRef.current = setTimeout(shrinkTimerCallback, shrinkDelayMs);
    isWaitingShrink = true;
  }
```

shrinkTimer 回调（关键 — 实现 option B 的"缩小后再放大"链式衔接）：

```
shrinkTimerCallback():
  shrinkTimerRef.current = null
  isWaitingShrink = false
  if (!enabled) return                // 用户在 dwell 期间关掉了 auto-shrink
  await performShrink()                // 写入 savedSize、setIsShrunk(true)、设小窗口
  // option B 衔接：shrink 完成后若 cursor 仍在窗口里，启动 restore dwell
  // prevCursorRef 由 cursor 边沿 useEffect 维护，反映最新 cursorPresent
  if (prevCursorRef.current === true && !restoreTimerRef.current) {
    restoreTimerRef.current = setTimeout(performRestore, restoreDelayMs)
    isWaitingRestore = true
  }
```

`performShrink` 与 `performRestore` 内部不变。`performShrink` 已有 "current ≤ initialSize 则 no-op" 的短路，对"shrink 时窗口已是 initialSize"的情况安全（此时不会写 savedSize，后续 restore 也无目标）。

卸载 cleanup：同时清 `shrinkTimerRef` 与 `restoreTimerRef`。

## Edge Cases

1. **leave → 1.5s 内 enter → 仍然缩小，然后再放大**：shrinkTimer 不被 enter 取消，到期 `performShrink()` 执行；shrink 回调结尾检查 `prevCursorRef.current === true`，若仍在窗口里则启动 restoreTimer。结果：用户看到"窗口先缩，再 1.5s 后放大"。这正是 option B 的明确预期，依赖 shrinkTimerCallback 末尾的衔接逻辑而非 cursor 边沿。
2. **连续 leave 抖动（leave → enter → leave …）**：第二次 leave 进入时若 shrinkTimer 仍在跑，**清掉重启**（reset 语义）。避免多 timer 共存导致状态混乱。
3. **enter dwell 中再 leave**：restoreTimer 即时取消（现有行为保留）；同时启动 shrinkTimer。窗口已是 initialSize，timer 到期时 `performShrink` 走 no-op 分支，savedSize 不会被覆盖。
4. **disabled 时 leave**：不启动 shrinkTimer；enter 仍然启动 restoreTimer（与现有逻辑一致——savedSize 可能从 enabled 被切换前残留）。
5. **shrinkTimer 跑到一半 enabled 翻 false**：让 timer 跑到底，到期回调里的 `if (enabled)` 检查会跳过 `performShrink`。不主动清 timer，简化状态。
6. **手动 resize**：现有挂载条件 `cursorPresent === true` 不变，savedSize 跟踪逻辑不变。
7. **组件卸载**：cleanup 必须同时清 shrinkTimer 与 restoreTimer。
8. **Tauri API 失败**：保留现有 try/catch + console.warn。

## Testing Strategy

### 现有测试影响

- 默认 `restoreDelayMs` 从 2000 → 1500：现有用 2000 推进时间的断言要么改为 1500，要么显式传 `restoreDelayMs: 2000` 保持原 fake-timer 推进步长。
- "leave 后立即缩小" 类断言改为"leave 后 ≥ shrinkDelayMs 才缩小"。
- 5 个文件涉及：`useWindowAutoShrink.test.js`、`.property.test.js`、`.property2.test.js`、`.property3.test.js`、`.property4.test.js`。

### 新增 Property Tests

合并进现有 property test 文件，或新建 `useWindowAutoShrink.shrinkDwell.property.test.js`（沿用现有命名风格）。

| Property | 输入 | 断言 |
|---|---|---|
| `leave dwell delays shrink` | enabled=true，已放大；leave；推进 t < shrinkDelayMs | `setSize(initialSize)` 未被调用 |
| `shrink fires after leave dwell` | leave；推进 t ≥ shrinkDelayMs | `setSize(initialSize)` 被调用 1 次 |
| `re-entry during leave dwell does NOT cancel shrink` | leave；t ∈ (0, shrinkDelayMs) 时 enter | `setSize(initialSize)` 在 t = shrinkDelayMs 触发；savedSize 不被清 |
| `shrink-then-restore chain when cursor stays inside` | leave；t ∈ (0, shrinkDelayMs) 时 enter；继续推进 shrinkDelayMs + restoreDelayMs | `setSize(initialSize)` 调用 1 次；随后 `setSize(savedSize)` 调用 1 次（链式衔接） |
| `repeated leave resets shrink dwell` | leave → 500ms → enter → leave；推进 (shrinkDelayMs - 1)ms | shrink 未触发；再推进 1ms → 触发 |
| `enter dwell still cancels on leave (regression)` | enter；t < restoreDelayMs 时 leave | `setSize(savedSize)` 未被调用，shrinkTimer 启动 |

### 集成手测

- 进入 → 默念 1.5s → 看到放大。
- 离开 → 默念 1.5s → 看到缩小。
- 进入 → < 1.5s 离开 → 不放大。
- 离开 → < 1.5s 进入 → 仍缩小，再 1.5s 后又放大（option B 表现）。

## Requirements Traceability

此变更影响 `window-auto-shrink` spec：

- **Requirement 1（窗口缩小触发）**：触发不再是即时，而是 leave 后 1.5s dwell。
- **Requirement 2（窗口恢复触发）AC 1**：dwell 时长由 2s 改为 1.5s。
- **新引入的不变量**：
  - leave dwell 期间的 cursor re-entry 不取消缩小（option B）。
  - 连续 leave 重置 shrinkTimer（reset 语义）。
  - enter dwell 期间的 leave 仍即时取消（保留 `dwell-cancel-cursor-signal-design` 修复）。

## Implementation Checklist

1. `useWindowAutoShrink.js`：
   - 默认 `restoreDelayMs` 改为 1500。
   - 加参数 `shrinkDelayMs = 1500`、ref `shrinkTimerRef`、状态 `isWaitingShrink`。
   - `useEffect` 主体按 §Logic Flow 重写。
   - shrinkTimer 回调：清 ref、置 `isWaitingShrink = false`、`if (enabled) performShrink()`。
   - 卸载 cleanup 同时清两个 timer。
   - 返回值新增 `isWaitingShrink`。
   - JSDoc 更新（默认值、新参数、新返回字段、option B 语义注释）。
2. 调整现有 5 个测试文件中的延迟期望。
3. 新增上述 5 条 property tests（合并或新建文件，按现有风格）。
4. 手测四条集成路径。
