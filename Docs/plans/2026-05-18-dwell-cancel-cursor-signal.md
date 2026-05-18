# Dwell Cancel via Immediate Cursor Signal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复鼠标在缩小窗口内停留 < 2s 后离开仍触发放大、且窗口未恢复透明的 bug。

**Architecture:** 把 `useWindowHover` 拆为双信号 hook，返回 `{ opacityState, cursorPresent }` —— `opacityState` 保持 3s 离开防抖驱动 CSS 透明度，`cursorPresent` 即时反映鼠标在/不在窗口内。`useWindowAutoShrink` 入参从 `hoverState` 改为 `cursorPresent`，dwell timer 取消和 shrink 触发改用即时信号，避免与 3s 防抖错配。

**Tech Stack:** Preact 10 + `preact/hooks`、Tauri v2 (`@tauri-apps/api/window`)、Vitest + jsdom + `@testing-library/preact`、fast-check。

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `plan-viewer-desktop/src/hooks/useWindowHover.js` | Modify | 暴露 `{ opacityState, cursorPresent }` 双信号 |
| `plan-viewer-desktop/src/hooks/useWindowHover.test.js` | Create | 验证双信号时序 |
| `plan-viewer-desktop/src/hooks/useWindowAutoShrink.js` | Modify | 入参 `hoverState` → `cursorPresent`；状态机基于 boolean 边沿翻转 |
| `plan-viewer-desktop/src/hooks/useWindowAutoShrink.test.js` | Modify | 旧测试参数迁移 |
| `plan-viewer-desktop/src/hooks/useWindowAutoShrink.property.test.js` | Modify | property 测试参数迁移 + 新增即时性 property |
| `plan-viewer-desktop/src/hooks/useWindowAutoShrink.property2.test.js` | Modify | 参数迁移 |
| `plan-viewer-desktop/src/hooks/useWindowAutoShrink.property3.test.js` | Modify | 参数迁移 |
| `plan-viewer-desktop/src/hooks/useWindowAutoShrink.property4.test.js` | Modify | 参数迁移 |
| `plan-viewer-desktop/src/App.jsx` | Modify | 解构新接口；CSS class 用 `opacityState`；hook 入参用 `cursorPresent`；删除未用解构 |

---

## Task 1: 拆分 `useWindowHover` 为双信号

**Files:**
- Modify: `plan-viewer-desktop/src/hooks/useWindowHover.js`

- [ ] **Step 1: 用新版本替换整个文件**

```js
import { useState, useEffect, useRef } from 'preact/hooks';

/**
 * Track mouse enter/leave on the document and produce two signals:
 *
 * - `cursorPresent`: instantaneous boolean — `true` on mouseenter, `false` on mouseleave.
 *   Use this to drive logic that must respond immediately to the cursor leaving
 *   (e.g. cancelling a dwell timer).
 * - `opacityState`: debounced `'idle' | 'active'` — turns `'active'` immediately on
 *   mouseenter, returns to `'idle'` 3s after mouseleave. Use this to drive transparency
 *   so the window does not flicker when the user briefly grazes the edge.
 *
 * @returns {{ opacityState: 'idle' | 'active', cursorPresent: boolean }}
 */
export function useWindowHover() {
  const [opacityState, setOpacityState] = useState('idle');
  const [cursorPresent, setCursorPresent] = useState(false);
  const idleTimeoutRef = useRef(null);

  useEffect(() => {
    const handleEnter = () => {
      if (idleTimeoutRef.current) {
        clearTimeout(idleTimeoutRef.current);
        idleTimeoutRef.current = null;
      }
      setCursorPresent(true);
      setOpacityState('active');
    };

    const handleLeave = () => {
      setCursorPresent(false);
      idleTimeoutRef.current = setTimeout(() => {
        setOpacityState('idle');
        idleTimeoutRef.current = null;
      }, 3000);
    };

    document.addEventListener('mouseenter', handleEnter);
    document.addEventListener('mouseleave', handleLeave);

    return () => {
      document.removeEventListener('mouseenter', handleEnter);
      document.removeEventListener('mouseleave', handleLeave);
      if (idleTimeoutRef.current) clearTimeout(idleTimeoutRef.current);
    };
  }, []);

  return { opacityState, cursorPresent };
}
```

- [ ] **Step 2: 验证文件没有语法错误**

Run: `cd plan-viewer-desktop && npx vitest --run src/hooks/useWindowHover.test.js`
Expected: 测试文件还不存在，会报 `No test files found`，但 vitest 不应该报这个文件的语法错误。这一步是为了下个 task 做准备。

如果出现 import / parse 错误，修正后再继续。

- [ ] **Step 3: Commit**

```bash
git add plan-viewer-desktop/src/hooks/useWindowHover.js
git commit -m "refactor(useWindowHover): expose dual signals { opacityState, cursorPresent }"
```

---

## Task 2: 新增 `useWindowHover` 测试

**Files:**
- Create: `plan-viewer-desktop/src/hooks/useWindowHover.test.js`

- [ ] **Step 1: 写完整测试文件**

```js
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/preact';
import { useWindowHover } from './useWindowHover.js';

function fireDocumentEvent(eventName) {
  document.dispatchEvent(new Event(eventName));
}

describe('useWindowHover', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('returns { opacityState: "idle", cursorPresent: false } initially', () => {
    const { result } = renderHook(() => useWindowHover());
    expect(result.current.opacityState).toBe('idle');
    expect(result.current.cursorPresent).toBe(false);
  });

  it('on mouseenter sets cursorPresent=true and opacityState="active" immediately', () => {
    const { result } = renderHook(() => useWindowHover());

    act(() => {
      fireDocumentEvent('mouseenter');
    });

    expect(result.current.cursorPresent).toBe(true);
    expect(result.current.opacityState).toBe('active');
  });

  it('on mouseleave sets cursorPresent=false immediately, opacityState stays "active" until 3s elapses', () => {
    const { result } = renderHook(() => useWindowHover());

    act(() => {
      fireDocumentEvent('mouseenter');
    });

    act(() => {
      fireDocumentEvent('mouseleave');
    });

    // cursorPresent flips immediately
    expect(result.current.cursorPresent).toBe(false);
    // opacityState still active during 3s debounce
    expect(result.current.opacityState).toBe('active');

    // Just before 3s — still active
    act(() => {
      vi.advanceTimersByTime(2999);
    });
    expect(result.current.opacityState).toBe('active');

    // At 3s — flips to idle
    act(() => {
      vi.advanceTimersByTime(1);
    });
    expect(result.current.opacityState).toBe('idle');
  });

  it('mouseenter within 3s of mouseleave keeps opacityState="active" (no flicker)', () => {
    const { result } = renderHook(() => useWindowHover());

    act(() => {
      fireDocumentEvent('mouseenter');
    });
    act(() => {
      fireDocumentEvent('mouseleave');
    });

    // 1s into the leave debounce
    act(() => {
      vi.advanceTimersByTime(1000);
    });

    // Re-enter
    act(() => {
      fireDocumentEvent('mouseenter');
    });

    expect(result.current.cursorPresent).toBe(true);
    expect(result.current.opacityState).toBe('active');

    // Advance another 5s — opacityState must remain 'active' because the
    // leave timer was cancelled
    act(() => {
      vi.advanceTimersByTime(5000);
    });
    expect(result.current.opacityState).toBe('active');
    expect(result.current.cursorPresent).toBe(true);
  });

  it('cleans up listeners and pending timer on unmount', () => {
    const removeSpy = vi.spyOn(document, 'removeEventListener');
    const { result, unmount } = renderHook(() => useWindowHover());

    act(() => {
      fireDocumentEvent('mouseenter');
    });
    act(() => {
      fireDocumentEvent('mouseleave');
    });

    // Unmount while leave timer is pending
    unmount();

    // Both listeners removed
    expect(removeSpy).toHaveBeenCalledWith('mouseenter', expect.any(Function));
    expect(removeSpy).toHaveBeenCalledWith('mouseleave', expect.any(Function));

    // Advancing time after unmount must not throw or update state
    expect(() => {
      vi.advanceTimersByTime(5000);
    }).not.toThrow();

    removeSpy.mockRestore();
  });
});
```

- [ ] **Step 2: 运行新测试**

Run: `cd plan-viewer-desktop && npx vitest --run src/hooks/useWindowHover.test.js`
Expected: 全部 5 个测试 PASS。

- [ ] **Step 3: Commit**

```bash
git add plan-viewer-desktop/src/hooks/useWindowHover.test.js
git commit -m "test(useWindowHover): cover dual-signal behavior"
```

---

## Task 3: 切换 `useWindowAutoShrink` 入参为 `cursorPresent`

**Files:**
- Modify: `plan-viewer-desktop/src/hooks/useWindowAutoShrink.js`

- [ ] **Step 1: 更新 JSDoc 与解构参数**

替换文件顶部的 JSDoc + 函数签名（旧）：

```js
/**
 * Auto-shrink the window when hover state transitions from active → idle,
 * and restore it when transitioning from idle → active (after a dwell delay).
 * Tracks manual resize events to keep savedSize up-to-date.
 *
 * @param {{ hoverState: 'idle' | 'active', enabled: boolean, initialSize: { width: number, height: number }, restoreDelayMs?: number }} options
 * @param {number} [options.restoreDelayMs=2000] - Milliseconds the cursor must dwell before restore triggers
 * @returns {{ savedSize: { width: number, height: number } | null, isShrunk: boolean, isWaitingRestore: boolean }}
 */
export function useWindowAutoShrink({ hoverState, enabled, initialSize, restoreDelayMs = 2000 }) {
```

替换为（新）：

```js
/**
 * Auto-shrink the window when the cursor leaves, and restore it when the cursor
 * dwells inside the window for `restoreDelayMs` milliseconds. Tracks manual
 * resize events to keep savedSize up-to-date.
 *
 * `cursorPresent` is the instantaneous mouse-in-window boolean from
 * `useWindowHover`. We deliberately do NOT consume the debounced `opacityState`,
 * because the dwell-timer cancellation must respond immediately when the cursor
 * leaves — debouncing would let the dwell timer fire before the leave signal arrives.
 *
 * @param {{ cursorPresent: boolean, enabled: boolean, initialSize: { width: number, height: number }, restoreDelayMs?: number }} options
 * @param {number} [options.restoreDelayMs=2000] - Milliseconds the cursor must dwell before restore triggers
 * @returns {{ savedSize: { width: number, height: number } | null, isShrunk: boolean, isWaitingRestore: boolean }}
 */
export function useWindowAutoShrink({ cursorPresent, enabled, initialSize, restoreDelayMs = 2000 }) {
```

- [ ] **Step 2: 替换主 useEffect 中的状态机**

旧代码（要删掉的整段，不含 useEffect 包装 — 保留 useEffect 行和闭合）：

```js
    const prevState = prevHoverStateRef.current;
    prevHoverStateRef.current = hoverState;

    // Restore: idle → active transition when savedSize exists — start dwell timer
    if (prevState === 'idle' && hoverState === 'active' && savedSize) {
      restoreTimerRef.current = setTimeout(() => {
        restoreTimerRef.current = null;
        setIsWaitingRestore(false);
        performRestore();
      }, restoreDelayMs);
      setIsWaitingRestore(true);
    }

    // Shrink: active → idle transition
    if (prevState === 'active' && hoverState === 'idle') {
      // Cancel pending restore timer if still waiting
      if (restoreTimerRef.current) {
        clearTimeout(restoreTimerRef.current);
        restoreTimerRef.current = null;
        setIsWaitingRestore(false);
      }
      // Perform shrink if enabled
      if (enabled) {
        performShrink();
      }
    }
  }, [hoverState, enabled, initialSize, restoreDelayMs]);
```

替换为：

```js
    const prevCursor = prevCursorRef.current;
    prevCursorRef.current = cursorPresent;

    // Cursor entered: start dwell timer if there's a saved size to restore
    if (prevCursor === false && cursorPresent === true && savedSize) {
      restoreTimerRef.current = setTimeout(() => {
        restoreTimerRef.current = null;
        setIsWaitingRestore(false);
        performRestore();
      }, restoreDelayMs);
      setIsWaitingRestore(true);
    }

    // Cursor left: cancel any pending restore, then shrink if enabled
    if (prevCursor === true && cursorPresent === false) {
      if (restoreTimerRef.current) {
        clearTimeout(restoreTimerRef.current);
        restoreTimerRef.current = null;
        setIsWaitingRestore(false);
      }
      if (enabled) {
        performShrink();
      }
    }
  }, [cursorPresent, enabled, initialSize, restoreDelayMs]);
```

- [ ] **Step 3: 重命名 `prevHoverStateRef` 为 `prevCursorRef`**

旧（在文件顶部 useState/useRef 声明区域）：

```js
  const prevHoverStateRef = useRef(hoverState);
```

替换为：

```js
  const prevCursorRef = useRef(cursorPresent);
```

- [ ] **Step 4: 切换手动 resize 监听挂载条件**

旧代码（在文件中后部 `// Listen for window resize events ...` 区段）：

```js
  useEffect(() => {
    // Only track manual resizes when in active state
    if (hoverState !== 'active') {
      return;
    }
```

替换为：

```js
  useEffect(() => {
    // Only track manual resizes while the cursor is inside the window
    if (!cursorPresent) {
      return;
    }
```

同一个 useEffect 末尾的依赖数组：

旧：
```js
  }, [hoverState]);
```

替换为：
```js
  }, [cursorPresent]);
```

- [ ] **Step 5: 通过 vitest 验证 hook 可以加载（旧测试还会失败）**

Run: `cd plan-viewer-desktop && npx vitest --run src/hooks/useWindowAutoShrink.test.js -t "should return initial state"`
Expected: 这个测试用 `hoverState: 'active'`，重命名后参数名变了，会拿到 `cursorPresent: undefined`，但 hook 应能加载、`savedSize === null`、`isShrunk === false`、`isWaitingRestore === false`。该测试可能 PASS（因为旧测试只断言初始状态）。其他测试预期 FAIL，原因是 `hoverState` 不再是 hook 关心的字段。下个 Task 会修。

- [ ] **Step 6: Commit**

```bash
git add plan-viewer-desktop/src/hooks/useWindowAutoShrink.js
git commit -m "refactor(useWindowAutoShrink): drive state machine off cursorPresent boolean"
```

---

## Task 4: 迁移 `useWindowAutoShrink.test.js`

**Files:**
- Modify: `plan-viewer-desktop/src/hooks/useWindowAutoShrink.test.js`

策略：参数名 `hoverState` → `cursorPresent`，值 `'active'` → `true`、`'idle'` → `false`。下面的步骤逐处替换。

- [ ] **Step 1: 替换基础初始状态测试**

旧：
```js
  it('should return initial state with savedSize null and isShrunk false', () => {
    const { result } = renderHook(() =>
      useWindowAutoShrink({ hoverState: 'active', enabled: true, initialSize })
    );
```

替换为：
```js
  it('should return initial state with savedSize null and isShrunk false', () => {
    const { result } = renderHook(() =>
      useWindowAutoShrink({ cursorPresent: true, enabled: true, initialSize })
    );
```

- [ ] **Step 2: 替换 "should shrink window on active → idle transition" 整段**

旧：
```js
  it('should shrink window on active → idle transition when enabled', async () => {
    const { result, rerender } = renderHook(
      ({ hoverState }) => useWindowAutoShrink({ hoverState, enabled: true, initialSize }),
      { initialProps: { hoverState: 'active' } }
    );

    // Transition to idle
    rerender({ hoverState: 'idle' });
```

替换为：
```js
  it('should shrink window on cursor leave (true → false) when enabled', async () => {
    const { result, rerender } = renderHook(
      ({ cursorPresent }) => useWindowAutoShrink({ cursorPresent, enabled: true, initialSize }),
      { initialProps: { cursorPresent: true } }
    );

    // Cursor leaves
    rerender({ cursorPresent: false });
```

- [ ] **Step 3: 全文替换剩余 `hoverState` 引用**

对该文件的所有剩余位置做同样替换：
- `({ hoverState }) =>` → `({ cursorPresent }) =>`
- `({ hoverState, enabled` → `({ cursorPresent, enabled`
- `initialProps: { hoverState: 'active' }` → `initialProps: { cursorPresent: true }`
- `initialProps: { hoverState: 'idle' }` → `initialProps: { cursorPresent: false }`
- `rerender({ hoverState: 'active' })` → `rerender({ cursorPresent: true })`
- `rerender({ hoverState: 'idle' })` → `rerender({ cursorPresent: false })`
- `useWindowAutoShrink({ hoverState: 'active'` → `useWindowAutoShrink({ cursorPresent: true`
- `useWindowAutoShrink({ hoverState: 'idle'` → `useWindowAutoShrink({ cursorPresent: false`

也更新描述里"active/idle"用语，例如：
- `'should NOT shrink on idle → idle (no transition)'` → `'should NOT shrink on cursor=false → cursor=false (no transition)'`
- `describe('restore behavior (idle → active)', ...)` → `describe('restore behavior (cursor enters)', ...)`
- `describe('manual resize tracking', ...)` 描述里 "in active state" → "while cursor is present"
- `'should register onResized listener when in active state'` → `'should register onResized listener while cursor is present'`
- `'should NOT register onResized listener when in idle state'` → `'should NOT register onResized listener when cursor is absent'`
- `'should call unlisten when hoverState changes from active to idle'` → `'should call unlisten when cursor leaves'`
- `'should cancel restore if mouse leaves before dwell delay elapses'` 内的 leave 测试一致；保留

- [ ] **Step 4: 运行整个测试文件**

Run: `cd plan-viewer-desktop && npx vitest --run src/hooks/useWindowAutoShrink.test.js`
Expected: 全部测试 PASS（约 20 条）。如有失败，定位是漏改的 `hoverState` 引用还是行为差异。Bug 修复本身不会改变这些测试断言的核心语义。

- [ ] **Step 5: Commit**

```bash
git add plan-viewer-desktop/src/hooks/useWindowAutoShrink.test.js
git commit -m "test(useWindowAutoShrink): migrate to cursorPresent param"
```

---

## Task 5: 迁移 `useWindowAutoShrink.property.test.js`

**Files:**
- Modify: `plan-viewer-desktop/src/hooks/useWindowAutoShrink.property.test.js`

- [ ] **Step 1: 替换 Property 1 测试中的参数**

旧：
```js
          // Render hook in active state
          const { result, rerender, unmount } = renderHook(
            ({ hoverState }) =>
              useWindowAutoShrink({ hoverState, enabled: true, initialSize }),
            { initialProps: { hoverState: 'active' } }
          );

          // Transition active → idle (shrink)
          rerender({ hoverState: 'idle' });
```

替换为：
```js
          // Render hook with cursor present
          const { result, rerender, unmount } = renderHook(
            ({ cursorPresent }) =>
              useWindowAutoShrink({ cursorPresent, enabled: true, initialSize }),
            { initialProps: { cursorPresent: true } }
          );

          // Cursor leaves (shrink)
          rerender({ cursorPresent: false });
```

文件末尾 restore 阶段：

旧：
```js
          rerender({ hoverState: 'active' });
```
替换为：
```js
          rerender({ cursorPresent: true });
```

- [ ] **Step 2: 全文替换其余位置**

按 Task 4 Step 3 的同样规则，对该文件其余每一处 `hoverState` 引用做替换。重点位置：

- Property 4 的 `useWindowAutoShrink({ hoverState: 'active', ... })` → `useWindowAutoShrink({ cursorPresent: true, ... })`
- Property 8 / 7 的 `initialProps: { hoverState: 'active' }`、`rerender({ hoverState: 'idle' })`、`rerender({ hoverState: 'active' })` 等位置全部替换

- [ ] **Step 3: 替换"Multiple rapid cycles"property 中的循环逻辑**

旧（约文件末尾）：
```js
          // Rapid enter-leave cycles
          for (let i = 0; i < numCycles; i++) {
            rerender({ hoverState: 'active' });
            vi.advanceTimersByTime(dwellTime);
            rerender({ hoverState: 'idle' });
            vi.advanceTimersByTime(100);
          }
```

替换为：
```js
          // Rapid enter-leave cycles
          for (let i = 0; i < numCycles; i++) {
            rerender({ cursorPresent: true });
            vi.advanceTimersByTime(dwellTime);
            rerender({ cursorPresent: false });
            vi.advanceTimersByTime(100);
          }
```

- [ ] **Step 4: 运行 property 测试**

Run: `cd plan-viewer-desktop && npx vitest --run src/hooks/useWindowAutoShrink.property.test.js`
Expected: 6 个 describe block 全部 PASS。

- [ ] **Step 5: Commit**

```bash
git add plan-viewer-desktop/src/hooks/useWindowAutoShrink.property.test.js
git commit -m "test(useWindowAutoShrink): migrate property tests to cursorPresent"
```

---

## Task 6: 迁移 `useWindowAutoShrink.property2.test.js`

**Files:**
- Modify: `plan-viewer-desktop/src/hooks/useWindowAutoShrink.property2.test.js`

- [ ] **Step 1: 替换 hook 调用部分**

旧：
```js
          const { result, rerender } = renderHook(
            ({ hoverState }) =>
              useWindowAutoShrink({ hoverState, enabled: true, initialSize }),
            { initialProps: { hoverState: 'active' } }
          );

          // Trigger active → idle transition (shrink trigger)
          rerender({ hoverState: 'idle' });
```

替换为：
```js
          const { result, rerender } = renderHook(
            ({ cursorPresent }) =>
              useWindowAutoShrink({ cursorPresent, enabled: true, initialSize }),
            { initialProps: { cursorPresent: true } }
          );

          // Cursor leaves (shrink trigger)
          rerender({ cursorPresent: false });
```

- [ ] **Step 2: 运行**

Run: `cd plan-viewer-desktop && npx vitest --run src/hooks/useWindowAutoShrink.property2.test.js`
Expected: PASS。

- [ ] **Step 3: Commit**

```bash
git add plan-viewer-desktop/src/hooks/useWindowAutoShrink.property2.test.js
git commit -m "test(property2): migrate to cursorPresent"
```

---

## Task 7: 迁移 `useWindowAutoShrink.property3.test.js`

**Files:**
- Modify: `plan-viewer-desktop/src/hooks/useWindowAutoShrink.property3.test.js`

- [ ] **Step 1: 替换 hook 调用部分**

旧：
```js
          const { result, rerender } = renderHook(
            ({ hoverState }) =>
              useWindowAutoShrink({ hoverState, enabled: false, initialSize }),
            { initialProps: { hoverState: 'active' } }
          );

          // Trigger active → idle transition (simulates mouse leave + delay elapsed)
          rerender({ hoverState: 'idle' });
```

替换为：
```js
          const { result, rerender } = renderHook(
            ({ cursorPresent }) =>
              useWindowAutoShrink({ cursorPresent, enabled: false, initialSize }),
            { initialProps: { cursorPresent: true } }
          );

          // Cursor leaves (simulates mouse leaving the window)
          rerender({ cursorPresent: false });
```

- [ ] **Step 2: 运行**

Run: `cd plan-viewer-desktop && npx vitest --run src/hooks/useWindowAutoShrink.property3.test.js`
Expected: PASS。

- [ ] **Step 3: Commit**

```bash
git add plan-viewer-desktop/src/hooks/useWindowAutoShrink.property3.test.js
git commit -m "test(property3): migrate to cursorPresent"
```

---

## Task 8: 迁移 `useWindowAutoShrink.property4.test.js`

**Files:**
- Modify: `plan-viewer-desktop/src/hooks/useWindowAutoShrink.property4.test.js`

注意：原文件含两个 `it(...)` 块。第一个块描述 "timer cancellation by re-entry"，旧含义依赖 useWindowHover 的 1500ms 防抖 — 新接口下 `cursorPresent` 没有防抖，这条 property 改为"cursor 一直 present 时 hook 不会 shrink"。第二个块测的 shrink → 立刻 re-enter → dwell 后 restore，迁移即可。

- [ ] **Step 1: 替换第一个 `it(...)` 块（"should not shrink when hoverState stays active"）**

旧：
```js
  it('should not shrink when hoverState stays active (timer cancelled by re-entry)', async () => {
    await fc.assert(
      fc.asyncProperty(
        // Generate random window dimensions (larger than initialSize)
        fc.integer({ min: 401, max: 3000 }),
        fc.integer({ min: 301, max: 2000 }),
        // Generate random re-entry time t ∈ (0, 1500ms) — simulates how long
        // the user was away before re-entering (timer gets cancelled)
        fc.integer({ min: 1, max: 1499 }),
        async (width, height, reentryTimeMs) => {
          // Configure mock to return the generated dimensions
          mockSetSize.mockClear();
          mockInnerSize.mockResolvedValue({ width, height });

          // Render hook in active state (mouse is inside window)
          const { result, rerender, unmount } = renderHook(
            ({ hoverState }) =>
              useWindowAutoShrink({ hoverState, enabled: true, initialSize }),
            { initialProps: { hoverState: 'active' } }
          );

          // Simulate the passage of time representing the re-entry delay.
          // The key insight: because the mouse re-entered before 1500ms,
          // useWindowHover cancels the timer and hoverState stays 'active'.
          // From useWindowAutoShrink's perspective, hoverState never changes.
          // We wait for the re-entry time to demonstrate that even after waiting,
          // no shrink occurs because hoverState remained 'active'.
          await new Promise((r) => setTimeout(r, Math.min(reentryTimeMs, 50)));

          // Assert: setSize was NOT called (no shrink operation executed)
          expect(mockSetSize).not.toHaveBeenCalled();

          // Assert: savedSize remains null (window size was not saved for restore)
          expect(result.current.savedSize).toBeNull();

          // Assert: isShrunk remains false (window is still at current size)
          expect(result.current.isShrunk).toBe(false);

          // Now simulate what happens if hoverState briefly flickers but returns
          // to 'active' before the hook can process a shrink. Re-render with
          // 'active' again (as if useWindowHover cancelled and re-set to active).
          rerender({ hoverState: 'active' });

          await new Promise((r) => setTimeout(r, 20));

          // Assert: still no shrink occurred
          expect(mockSetSize).not.toHaveBeenCalled();
          expect(result.current.savedSize).toBeNull();
          expect(result.current.isShrunk).toBe(false);

          unmount();
        }
      ),
      { numRuns: 100 }
    );
  }, 30000);
```

替换为：

```js
  it('should not shrink while cursorPresent stays true (no leave edge)', async () => {
    await fc.assert(
      fc.asyncProperty(
        // Generate random window dimensions (larger than initialSize)
        fc.integer({ min: 401, max: 3000 }),
        fc.integer({ min: 301, max: 2000 }),
        // Random elapsed wait time — proves time alone does not trigger shrink
        fc.integer({ min: 1, max: 1499 }),
        async (width, height, waitMs) => {
          mockSetSize.mockClear();
          mockInnerSize.mockResolvedValue({ width, height });

          // Cursor present, hook mounted
          const { result, rerender, unmount } = renderHook(
            ({ cursorPresent }) =>
              useWindowAutoShrink({ cursorPresent, enabled: true, initialSize }),
            { initialProps: { cursorPresent: true } }
          );

          // Wait an arbitrary amount of time. Since cursorPresent never goes
          // false, no leave edge ever fires, so the hook MUST NOT shrink
          // regardless of how long we wait.
          await new Promise((r) => setTimeout(r, Math.min(waitMs, 50)));

          expect(mockSetSize).not.toHaveBeenCalled();
          expect(result.current.savedSize).toBeNull();
          expect(result.current.isShrunk).toBe(false);

          // Re-render with cursorPresent still true (idempotent — no edge)
          rerender({ cursorPresent: true });
          await new Promise((r) => setTimeout(r, 20));

          expect(mockSetSize).not.toHaveBeenCalled();
          expect(result.current.savedSize).toBeNull();
          expect(result.current.isShrunk).toBe(false);

          unmount();
        }
      ),
      { numRuns: 100 }
    );
  }, 30000);
```

- [ ] **Step 2: 替换第二个 `it(...)` 块**

旧：
```js
  it('should not shrink when hoverState transitions active → idle → active quickly (re-entry restores after dwell)', async () => {
    await fc.assert(
      fc.asyncProperty(
        // Generate random window dimensions (larger than initialSize)
        fc.integer({ min: 401, max: 3000 }),
        fc.integer({ min: 301, max: 2000 }),
        // Generate random re-entry time t ∈ (0, 1500ms)
        fc.integer({ min: 1, max: 1499 }),
        async (width, height, _reentryTimeMs) => {
          // Configure mocks
          vi.clearAllMocks();
          mockSetSize.mockResolvedValue(undefined);
          mockInnerSize.mockResolvedValue({ width, height });
          mockOuterPosition.mockResolvedValue({ x: 0, y: 0 });
          mockCurrentMonitor.mockResolvedValue({ size: { width: 3840, height: 2160 } });
          mockOnResized.mockResolvedValue(() => {});

          // Render hook in active state
          const { result, rerender, unmount } = renderHook(
            ({ hoverState }) =>
              useWindowAutoShrink({ hoverState, enabled: true, initialSize }),
            { initialProps: { hoverState: 'active' } }
          );

          // Transition active → idle (shrink triggers)
          rerender({ hoverState: 'idle' });

          // Wait for shrink to complete
          await vi.waitFor(() => {
            expect(mockSetSize).toHaveBeenCalled();
          });

          // Immediately transition idle → active (re-entry, starts dwell timer)
          mockSetSize.mockClear();

          // Use fake timers to advance past dwell delay
          vi.useFakeTimers();
          rerender({ hoverState: 'active' });

          // Advance past dwell delay (2000ms)
          await act(async () => {
            vi.advanceTimersByTime(2000);
            await Promise.resolve();
            await Promise.resolve();
            await Promise.resolve();
          });
          vi.useRealTimers();

          // Wait for restore to complete
          await vi.waitFor(() => {
            expect(mockSetSize).toHaveBeenCalled();
          });

          // The window should be restored to its original size (not shrunk)
          const restoreArg = mockSetSize.mock.calls[0][0];
          expect(restoreArg.width).toBe(width);
          expect(restoreArg.height).toBe(height);

          // Final state: window is NOT shrunk (it was restored)
          expect(result.current.isShrunk).toBe(false);

          unmount();
        }
      ),
      { numRuns: 100 }
    );
  }, 30000);
```

替换为：

```js
  it('should restore after re-entry once dwell delay completes', async () => {
    await fc.assert(
      fc.asyncProperty(
        fc.integer({ min: 401, max: 3000 }),
        fc.integer({ min: 301, max: 2000 }),
        async (width, height) => {
          vi.clearAllMocks();
          mockSetSize.mockResolvedValue(undefined);
          mockInnerSize.mockResolvedValue({ width, height });
          mockOuterPosition.mockResolvedValue({ x: 0, y: 0 });
          mockCurrentMonitor.mockResolvedValue({ size: { width: 3840, height: 2160 } });
          mockOnResized.mockResolvedValue(() => {});

          const { result, rerender, unmount } = renderHook(
            ({ cursorPresent }) =>
              useWindowAutoShrink({ cursorPresent, enabled: true, initialSize }),
            { initialProps: { cursorPresent: true } }
          );

          // Cursor leaves → shrink
          rerender({ cursorPresent: false });
          await vi.waitFor(() => { expect(mockSetSize).toHaveBeenCalled(); });

          mockSetSize.mockClear();

          // Cursor returns → dwell timer starts
          vi.useFakeTimers();
          rerender({ cursorPresent: true });

          // Advance past dwell delay (2000ms)
          await act(async () => {
            vi.advanceTimersByTime(2000);
            await Promise.resolve();
            await Promise.resolve();
            await Promise.resolve();
          });
          vi.useRealTimers();

          await vi.waitFor(() => { expect(mockSetSize).toHaveBeenCalled(); });

          const restoreArg = mockSetSize.mock.calls[0][0];
          expect(restoreArg.width).toBe(width);
          expect(restoreArg.height).toBe(height);
          expect(result.current.isShrunk).toBe(false);

          unmount();
        }
      ),
      { numRuns: 100 }
    );
  }, 30000);
```

- [ ] **Step 3: 运行**

Run: `cd plan-viewer-desktop && npx vitest --run src/hooks/useWindowAutoShrink.property4.test.js`
Expected: 两条 property 都 PASS。

- [ ] **Step 4: Commit**

```bash
git add plan-viewer-desktop/src/hooks/useWindowAutoShrink.property4.test.js
git commit -m "test(property4): rewrite for cursorPresent semantics (no debounce)"
```

---

## Task 9: 新增 PBT — shrink 立即响应 cursor leave

**Files:**
- Modify: `plan-viewer-desktop/src/hooks/useWindowAutoShrink.property.test.js`

这是修复行为的关键 property：当 `cursorPresent` 从 true 变 false 时，shrink 必须立刻被触发，不依赖任何外部防抖。

- [ ] **Step 1: 在文件末尾追加新 describe block**

把以下整段追加到文件最后一个 `});` 之后（文件末尾）：

```js
describe('Feature: dwell-cancel-cursor-signal, Property: Shrink fires on cursor leave without debounce', () => {
  const initialSize = { width: 400, height: 300 };

  beforeEach(() => {
    vi.clearAllMocks();
    mockSetSize.mockResolvedValue(undefined);
    mockOuterPosition.mockResolvedValue({ x: 0, y: 0 });
    mockCurrentMonitor.mockResolvedValue({ size: { width: 3840, height: 2160 } });
    mockOnResized.mockResolvedValue(() => {});
  });

  /**
   * Property: For any window size larger than initialSize, the moment
   * cursorPresent flips from true to false, performShrink must be invoked
   * (i.e. setSize called with initialSize). No external debounce is allowed
   * to gate this — the orchestrator (useWindowHover) is responsible for
   * deciding when "leave" actually happened.
   */
  it('setSize(initialSize) is called immediately on cursorPresent true → false', async () => {
    await fc.assert(
      fc.asyncProperty(
        fc.integer({ min: 401, max: 3000 }),
        fc.integer({ min: 301, max: 2000 }),
        async (width, height) => {
          vi.clearAllMocks();
          mockSetSize.mockResolvedValue(undefined);
          mockInnerSize.mockResolvedValue({ width, height });
          mockOuterPosition.mockResolvedValue({ x: 0, y: 0 });
          mockCurrentMonitor.mockResolvedValue({ size: { width: 3840, height: 2160 } });
          mockOnResized.mockResolvedValue(() => {});

          const { rerender, unmount } = renderHook(
            ({ cursorPresent }) =>
              useWindowAutoShrink({ cursorPresent, enabled: true, initialSize }),
            { initialProps: { cursorPresent: true } }
          );

          rerender({ cursorPresent: false });

          // Shrink must fire — no time advance needed, no debounce in this hook
          await vi.waitFor(() => {
            expect(mockSetSize).toHaveBeenCalledTimes(1);
          });

          const arg = mockSetSize.mock.calls[0][0];
          expect(arg.width).toBe(initialSize.width);
          expect(arg.height).toBe(initialSize.height);

          unmount();
        }
      ),
      { numRuns: 50 }
    );
  }, 30000);
});
```

- [ ] **Step 2: 运行新 describe**

Run: `cd plan-viewer-desktop && npx vitest --run src/hooks/useWindowAutoShrink.property.test.js -t "Shrink fires on cursor leave"`
Expected: PASS。

- [ ] **Step 3: Commit**

```bash
git add plan-viewer-desktop/src/hooks/useWindowAutoShrink.property.test.js
git commit -m "test: add property — shrink fires immediately on cursor leave"
```

---

## Task 10: 接线 `App.jsx`

**Files:**
- Modify: `plan-viewer-desktop/src/App.jsx`

- [ ] **Step 1: 替换 hook 解构与传参（约文件第 12-19 行）**

旧：
```jsx
  const hoverState = useWindowHover();
  const [autoShrink, setAutoShrink] = useState(true);
  const { savedSize, isShrunk } = useWindowAutoShrink({
    hoverState,
    enabled: autoShrink,
    initialSize: { width: 400, height: 300 },
  });
```

替换为：
```jsx
  const { opacityState, cursorPresent } = useWindowHover();
  const [autoShrink, setAutoShrink] = useState(true);
  useWindowAutoShrink({
    cursorPresent,
    enabled: autoShrink,
    initialSize: { width: 400, height: 300 },
  });
```

注意：
- 删除了 `{ savedSize, isShrunk }` 解构（hook 返回值未被消费，移除消除 lint hint）。
- App 不需要 hook 的返回值；接线只是为了让副作用生效。

- [ ] **Step 2: 替换 CSS class 绑定**

旧（约第 56 行）：
```jsx
    <div class={`app-container ${hoverState}`}>
```

替换为：
```jsx
    <div class={`app-container ${opacityState}`}>
```

- [ ] **Step 3: 运行所有 hook 测试**

Run: `cd plan-viewer-desktop && npx vitest --run src/hooks/`
Expected: 全部 PASS（约 35-40 条测试，包括迁移后的旧测试和新增的 useWindowHover + 即时性 property）。

- [ ] **Step 4: Commit**

```bash
git add plan-viewer-desktop/src/App.jsx
git commit -m "refactor(App): consume opacityState + cursorPresent dual signals"
```

---

## Task 11: 全量测试 + 手测验证

**Files:** 无新建。运行验证命令。

- [ ] **Step 1: 跑完整测试套件**

Run: `cd plan-viewer-desktop && npx vitest --run`
Expected: 全部 PASS（含 TitleBar 既有测试不受影响）。

- [ ] **Step 2: 启动 Tauri dev（可选 — 取决于本地 Rust 工具链）**

如果本地有 Rust 工具链：
Run: `cd plan-viewer-desktop && npm run tauri dev`

如果没有，跳过此步骤，仅依靠测试通过即可。

- [ ] **Step 3: 手测三条路径（仅当 Step 2 成功启动）**

按设计文档"集成手测"条目逐项验证：

1. 缩小（鼠标离开） → 鼠标进入 → 1s 内离开 → 确认窗口未放大、约 3s 后透明化。
2. 缩小 → 鼠标进入 → 停留 > 2s → 确认窗口放大恢复。
3. 已放大 → 鼠标离开 → 确认窗口立即缩小、随后透明化。

把观察结果记录在 commit message 里。

- [ ] **Step 4: 最终 commit**

```bash
git commit --allow-empty -m "verify: dwell-cancel cursor-signal bugfix passes manual test"
```

如果手测有偏差，回到 Task 3 检查 hook 边沿条件。

---

## Self-Review Checklist

执行实现时不需要回看；这是 plan 作者完成后内审的备查项。

- [x] **Spec coverage:** 设计文档 Implementation Checklist 7 项全部映射到 task：1→T1, 2→T3, 3→T10, 4→T4-T8, 5→T2, 6→T9, 7→T11。
- [x] **Placeholder scan:** 无 TBD/TODO/`...`/"add proper error handling"。
- [x] **Type consistency:** `cursorPresent: boolean`, `opacityState: 'idle' | 'active'`, `prevCursorRef`, `restoreTimerRef` 在所有 task 中一致。`useWindowHover` 返回对象签名在 Task 1 与 Task 2 测试断言匹配。
- [x] **No drift:** 旧 `hoverState` 仅在 "before/after" 对比块中出现，所有运行代码已切到新名。
