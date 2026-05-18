# Restore Dwell Delay — Design Spec

## Summary

为窗口自动放大恢复添加 2 秒停留延迟。鼠标进入缩小后的窗口时，先立即恢复不透明度，但尺寸保持缩小；光标需在窗口内连续停留 2 秒以上才触发放大恢复。如果鼠标在 2 秒内离开，取消放大，按现有逻辑进入透明化流程。

## Context

现有 `useWindowAutoShrink` hook 在鼠标进入（`idle → active` 转换）时立即恢复窗口尺寸。这导致鼠标快速划过窗口时频繁触发放大/缩小抖动，影响体验。

## Behavior Matrix

| 当前状态 | 鼠标动作 | 结果 |
|----------|----------|------|
| 缩小 + 透明 | 鼠标进入 | 立即恢复不透明，启动 2s 放大计时器 |
| 缩小 + 不透明（等待中） | 停留满 2s | 放大恢复到 Saved_Size |
| 缩小 + 不透明（等待中） | 2s 内离开 | 取消计时器，保持缩小，1.5s 后透明化 |
| 已放大 + 不透明 | 鼠标离开 | 现有逻辑不变（1.5s 后缩小 + 透明化） |

## Architecture

### Scope of Change

仅修改 `plan-viewer-desktop/src/hooks/useWindowAutoShrink.js`。对外接口保持向后兼容。

### Interface

```js
// 参数（新增 restoreDelayMs）
useWindowAutoShrink({
  hoverState,        // 'idle' | 'active'
  enabled,           // boolean
  initialSize,       // { width: number, height: number }
  restoreDelayMs,    // number, 默认 2000
})

// 返回值（新增 isWaitingRestore）
{
  savedSize,         // { width, height } | null
  isShrunk,          // boolean
  isWaitingRestore,  // boolean — 正在等待 dwell 延迟
}
```

### Opacity Decoupling

透明度由 CSS class 控制。当 `hoverState` 变为 `active` 时，App 根 div class 从 `idle` 变为 `active`，CSS 立即应用不透明样式。此行为独立于尺寸变化，无需改动。

## Logic Flow

```
鼠标进入（idle → active）:
  ├─ CSS class → 'active' → 不透明（即时，已有行为）
  ├─ 如果 isShrunk && savedSize 存在:
  │     启动 restoreTimer = setTimeout(performRestore, restoreDelayMs)
  │     设置 isWaitingRestore = true
  └─ 如果 !isShrunk: 无操作

鼠标离开（active → idle）:
  ├─ 如果 restoreTimer 存在:
  │     clearTimeout(restoreTimer) → 取消放大
  │     设置 isWaitingRestore = false
  │     窗口保持缩小（isShrunk 不变）
  ├─ 现有 useWindowHover 的延迟后:
  │     CSS class → 'idle' → 透明化
  └─ 如果已放大: 走现有 shrink 逻辑（不变）

restoreTimer 到期:
  ├─ 调用 performRestore()
  ├─ isShrunk = false
  └─ isWaitingRestore = false
```

## Edge Cases

1. **快速进出（< 2s）**：计时器取消，窗口保持缩小，随后走透明化流程。由于窗口已是 Initial_Size，shrink 逻辑 no-op。
2. **Auto-Shrink 禁用**：restoreDelay 不生效（窗口不会被缩小，无需恢复）。
3. **连续快速进出多次**：每次进入重新启动 2s 计时，不累积。每次离开清除计时。
4. **2s 内窗口被手动 resize**：如果用户在等待期间手动拉大窗口超过 Initial_Size，清除 restoreTimer，设置 `isShrunk = false`、`isWaitingRestore = false`，并将新尺寸更新到 savedSize。后续走正常的已放大状态流程。

## Testing

### New Property Tests

| Property | 描述 | 验证点 |
|----------|------|--------|
| Restore dwell cancellation | 生成随机 t ∈ (0, 2000ms)，在 t 时间离开 | 窗口尺寸未变（仍为 Initial_Size） |
| Restore after dwell | 停留 ≥ 2000ms | 窗口恢复到 savedSize |
| Multiple enter-leave cycles | 生成 N 次快速进出（每次 < 2s） | 窗口始终保持 Initial_Size |

### Existing Test Impact

- 现有 property test "shrink-then-restore round trip" 需更新：restore 路径现在有 2s 延迟，模拟中需 fake timer advance。
- 现有 "timer cancellation on re-entry" test 需更新以反映新行为。

## Requirements Traceability

此功能为 `window-auto-shrink` spec 的增量需求，新增：
- **Requirement 8: 恢复放大停留延迟** — 鼠标需在缩小窗口内停留 2s 才触发放大。

修改影响：
- Requirement 2（窗口恢复触发）的 AC 1 需修订：恢复不再是"立即"而是"2s 停留后"。

## Implementation Checklist

1. 修改 `useWindowAutoShrink.js`：添加 restoreTimerRef、restoreDelayMs 参数、isWaitingRestore 状态
2. 更新 restore 逻辑：idle→active 时启动 timer 而非直接 performRestore
3. 更新 shrink 逻辑：active→idle 时清除 restoreTimer
4. 更新现有 property tests 以适配 2s 延迟
5. 添加新 property tests
6. 验证 App.jsx 无需改动（接口向后兼容）
