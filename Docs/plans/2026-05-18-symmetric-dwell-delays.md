# Symmetric Dwell Delays Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 Exe 的 hover dwell 行为对称化为 1.5s。鼠标进入应用 → 1.5s dwell 后放大；鼠标离开应用 → 1.5s dwell 后缩小。Per option B：leave dwell 期间 cursor 重新进入**不**取消 shrink；shrink 完成后若 cursor 仍在窗口里，自动衔接 1.5s restore dwell。

**Architecture:** 仅修改 `useWindowAutoShrink` hook。新增 `shrinkDelayMs = 1500` 参数与 `shrinkTimerRef`；`restoreDelayMs` 默认从 2000 改为 1500。状态机仍由 `cursorPresent` 边沿驱动：`true→false` 启动（或 reset）shrinkTimer；shrink 回调结尾根据 `prevCursorRef.current` 衔接 restoreTimer，实现 option B 的"先缩后放"。`useWindowHover` 与 `App.jsx` 不动。

**Tech Stack:** Preact 10 + `preact/hooks`、Tauri v2 (`@tauri-apps/api/window`)、Vitest + jsdom + `@testing-library/preact`、fast-check。

**Spec:** `Docs/specs/2026-05-18-symmetric-dwell-delays-design.md`

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `plan-viewer-desktop/src/hooks/useWindowAutoShrink.js` | Modify | 新参数 `shrinkDelayMs`、`shrinkTimerRef`、`isWaitingShrink`；leave 边沿启动 shrinkTimer；shrink 回调末尾衔接 restoreTimer；默认 `restoreDelayMs` 改 1500 |
| `plan-viewer-desktop/src/hooks/useWindowAutoShrink.test.js` | Modify | 适配 leave 不再立即 shrink；默认 dwell 由 2000 → 1500（保持 fake-timer 推进步长 = 默认） |
| `plan-viewer-desktop/src/hooks/useWindowAutoShrink.property.test.js` | Modify | 把 6 个 describe block 中假设"leave 立即 shrink"或"`vi.advanceTimersByTime(2000)` 用于 restore"的步骤改为先推进 shrinkDelay、再推进 restoreDelay |
| `plan-viewer-desktop/src/hooks/useWindowAutoShrink.property2.test.js` | Modify | leave 触发 shrink 处插入 fake timer 推进 |
| `plan-viewer-desktop/src/hooks/useWindowAutoShrink.property3.test.js` | Modify | 同上 |
| `plan-viewer-desktop/src/hooks/useWindowAutoShrink.property4.test.js` | Modify | 第二个 `it` 块的 shrink 路径插入 fake timer 推进 |
| `plan-viewer-desktop/src/hooks/useWindowAutoShrink.shrinkDwell.property.test.js` | Create | 5 条新 property 覆盖 leave dwell + chain restore |
| `.kiro/specs/window-auto-shrink/requirements.md` | Modify | 更新 Requirement 1 / 2 文案与 Glossary |

---

## Task 1: 修改 `useWindowAutoShrink` hook

**Files:**
- Modify: `plan-viewer-desktop/src/hooks/useWindowAutoShrink.js`

- [ ] **Step 1: 更新 JSDoc 与函数签名**

把顶部 JSDoc 替换为下面的版本（说明 leave dwell 与 chain restore 语义；同时更新默认值与新返回字段）：

```js
/**
 * Auto-shrink the window after the cursor leaves and dwells outside for
 * `shrinkDelayMs` milliseconds, and restore it after the cursor enters and
 * dwells inside for `restoreDelayMs` milliseconds. Tracks manual resize
 * events to keep savedSize up-to-date.
 *
 * `cursorPresent` is the instantaneous mouse-in-window boolean from
 * `useWindowHover`. We deliberately do NOT consume the debounced `opacityState`,
 * because the dwell-timer cancellation must respond immediately when the cursor
 * leaves — debouncing would let the dwell timer fire before the leave signal arrives.
 *
 * Asymmetry on cancellation:
 * - Enter dwell (restoreTimer) IS cancelled by an immediate leave.
 * - Leave dwell (shrinkTimer) is NOT cancelled by re-entry — option B. After
 *   shrink completes, if the cursor is still inside, a fresh restore dwell
 *   is started so the cycle ends at the user's intended size.
 *
 * @param {{
 *   cursorPresent: boolean,
 *   enabled: boolean,
 *   initialSize: { width: number, height: number },
 *   restoreDelayMs?: number,
 *   shrinkDelayMs?: number,
 * }} options
 * @param {number} [options.restoreDelayMs=1500] - Cursor must dwell inside this long before restore triggers
 * @param {number} [options.shrinkDelayMs=1500] - Cursor must dwell outside this long before shrink triggers
 * @returns {{
 *   savedSize: { width: number, height: number } | null,
 *   isShrunk: boolean,
 *   isWaitingRestore: boolean,
 *   isWaitingShrink: boolean,
 * }}
 */
```

更新函数签名：

旧：
```js
export function useWindowAutoShrink({ cursorPresent, enabled, initialSize, restoreDelayMs = 2000 }) {
```

新：
```js
export function useWindowAutoShrink({
  cursorPresent,
  enabled,
  initialSize,
  restoreDelayMs = 1500,
  shrinkDelayMs = 1500,
}) {
```

- [ ] **Step 2: 添加新 state 与 ref**

在 `const [isWaitingRestore, setIsWaitingRestore] = useState(false);` 之后插入：

```js
  const [isWaitingShrink, setIsWaitingShrink] = useState(false);
```

在 `const restoreTimerRef = useRef(null);` 之后插入：

```js
  const shrinkTimerRef = useRef(null);
```

- [ ] **Step 3: 重写主 useEffect 主体**

旧（整段）：
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

新：
```js
    const prevCursor = prevCursorRef.current;
    prevCursorRef.current = cursorPresent;

    // Cursor entered: option B — do NOT cancel the shrinkTimer. Just start
    // a fresh restore dwell if we have a saved size to come back to.
    if (prevCursor === false && cursorPresent === true && savedSize && !restoreTimerRef.current) {
      restoreTimerRef.current = setTimeout(() => {
        restoreTimerRef.current = null;
        setIsWaitingRestore(false);
        performRestore();
      }, restoreDelayMs);
      setIsWaitingRestore(true);
    }

    // Cursor left: cancel any pending restore (immediate cancellation),
    // then start (or reset) the shrinkTimer if auto-shrink is enabled.
    if (prevCursor === true && cursorPresent === false) {
      if (restoreTimerRef.current) {
        clearTimeout(restoreTimerRef.current);
        restoreTimerRef.current = null;
        setIsWaitingRestore(false);
      }
      if (enabled) {
        // Reset semantics: a second leave during an in-flight shrink dwell
        // restarts the timer rather than stacking parallel timers.
        if (shrinkTimerRef.current) {
          clearTimeout(shrinkTimerRef.current);
        }
        shrinkTimerRef.current = setTimeout(shrinkTimerCallback, shrinkDelayMs);
        setIsWaitingShrink(true);
      }
    }
  }, [cursorPresent, enabled, initialSize, restoreDelayMs, shrinkDelayMs]);
```

- [ ] **Step 4: 添加 shrinkTimerCallback**

在 `performShrink` 函数声明之上（或之下，文件局部 hoist 都可以）添加：

```js
  async function shrinkTimerCallback() {
    shrinkTimerRef.current = null;
    setIsWaitingShrink(false);
    if (!enabled) return;
    await performShrink();
    // Option B chain: if the cursor is still inside after shrink completes
    // and we now have a savedSize, kick off the restore dwell so the user
    // ends up back at their intended size.
    if (prevCursorRef.current === true && !restoreTimerRef.current) {
      restoreTimerRef.current = setTimeout(() => {
        restoreTimerRef.current = null;
        setIsWaitingRestore(false);
        performRestore();
      }, restoreDelayMs);
      setIsWaitingRestore(true);
    }
  }
```

注意：`shrinkTimerCallback` 是普通函数声明，每次 render 重建，但 `setTimeout` 捕获的是创建时的闭包；闭包里读到的 `restoreDelayMs` / `enabled` 是 timer 启动那一刻的值。这与现有 `performShrink` / `performRestore` 闭包语义一致，不引入新风险。

- [ ] **Step 5: 更新 unmount cleanup 同时清两个 timer**

旧：
```js
  // Cleanup restore timer on unmount
  useEffect(() => {
    return () => {
      if (restoreTimerRef.current) {
        clearTimeout(restoreTimerRef.current);
      }
    };
  }, []);
```

新：
```js
  // Cleanup pending timers on unmount
  useEffect(() => {
    return () => {
      if (restoreTimerRef.current) {
        clearTimeout(restoreTimerRef.current);
      }
      if (shrinkTimerRef.current) {
        clearTimeout(shrinkTimerRef.current);
      }
    };
  }, []);
```

- [ ] **Step 6: 更新返回值**

旧：
```js
  return { savedSize, isShrunk, isWaitingRestore };
```

新：
```js
  return { savedSize, isShrunk, isWaitingRestore, isWaitingShrink };
```

- [ ] **Step 7: 通过编译加载验证文件无语法错误**

Run: `cd plan-viewer-desktop && npx vitest --run src/hooks/useWindowAutoShrink.test.js -t "should return initial state"`
Expected: 该测试 PASS（不依赖 dwell 时序）。如果出现 import / parse 错误，修正。其他测试此时预期会失败，下个 task 修。

- [ ] **Step 8: Commit**

```bash
git add plan-viewer-desktop/src/hooks/useWindowAutoShrink.js
git commit -m "feat(useWindowAutoShrink): symmetric 1.5s dwell delays for shrink and restore"
```

---

## Task 2: 迁移 `useWindowAutoShrink.test.js`

**Files:**
- Modify: `plan-viewer-desktop/src/hooks/useWindowAutoShrink.test.js`

策略：把"leave 立即 shrink"的所有断言改为"leave + 推进 1500ms 才 shrink"。`vi.advanceTimersByTime(2000)`（restore dwell）改为 `1500`（默认从 2000→1500）。

- [ ] **Step 1: 在文件顶部 describe 内添加 fake timer 控制 helper**

在 `describe('useWindowAutoShrink', () => {` 内、`beforeEach` 之后添加：

```js
  // Helper: advance fake timers and flush microtasks so async performShrink/Restore can resolve.
  async function advanceAndFlush(ms) {
    await act(async () => {
      vi.advanceTimersByTime(ms);
      // Flush a couple of microtask rounds for the awaited promises in performShrink/Restore
      await Promise.resolve();
      await Promise.resolve();
    });
  }
```

- [ ] **Step 2: 更新 "should shrink window on cursor leave" 测试**

旧：
```js
  it('should shrink window on cursor leave (true → false) when enabled', async () => {
    const { result, rerender } = renderHook(
      ({ cursorPresent }) => useWindowAutoShrink({ cursorPresent, enabled: true, initialSize }),
      { initialProps: { cursorPresent: true } }
    );

    // Cursor leaves
    rerender({ cursorPresent: false });

    // Wait for async operations
    await vi.waitFor(() => {
      expect(mockSetSize).toHaveBeenCalledTimes(1);
    });
```

新：
```js
  it('should shrink window after shrink dwell delay when cursor leaves', async () => {
    vi.useFakeTimers();
    const { result, rerender } = renderHook(
      ({ cursorPresent }) => useWindowAutoShrink({ cursorPresent, enabled: true, initialSize }),
      { initialProps: { cursorPresent: true } }
    );

    // Cursor leaves — shrink does NOT fire yet
    rerender({ cursorPresent: false });
    expect(mockSetSize).not.toHaveBeenCalled();
    expect(result.current.isWaitingShrink).toBe(true);

    // Advance past shrink dwell
    await advanceAndFlush(1500);
    vi.useRealTimers();

    await vi.waitFor(() => {
      expect(mockSetSize).toHaveBeenCalledTimes(1);
    });
```

后续断言（`sizeArg`、`savedSize`、`isShrunk`）保持不变。在该 it 块末尾，文件其余测试一致使用 `vi.useRealTimers()` 收尾。

- [ ] **Step 3: 更新所有依赖"leave 立即 shrink"的剩余测试**

下面这些测试都需要在 `rerender({ cursorPresent: false })` 之后、`await vi.waitFor` 之前插入 fake-timer 推进 1500ms：

| Test name | 修改 |
|---|---|
| `should NOT shrink when enabled is false` | 不变（enabled=false 时 shrinkTimer 不启动）|
| `should NOT shrink when window is already at or below initialSize` | 在 leave 之前 `vi.useFakeTimers()`；leave 后 `await advanceAndFlush(1500)`；保留 50ms real wait 同样可以；最后 `vi.useRealTimers()` |
| `should NOT shrink when window is below initialSize` | 同上 |
| `should NOT shrink on cursor=false → cursor=false (no transition)` | 不变（无边沿）|
| `should handle API errors gracefully` | leave 后 fake timer 推进 1500ms；`mockInnerSize.mockRejectedValue` 等保留 |
| `should call unlisten when cursor leaves` | 不变（unlisten 由 effect cleanup 触发，不依赖 shrinkTimer）|
| `restore behavior` 整组 | 把所有 `vi.advanceTimersByTime(2000)` 改为 `1500`；shrink 触发处加 fake timer 推进 1500ms（详见 Step 4）|

具体替换示例 — `should handle API errors gracefully`：

旧：
```js
    rerender({ cursorPresent: false });

    await new Promise((r) => setTimeout(r, 50));

    // Should not crash, state should remain unchanged
    expect(result.current.savedSize).toBeNull();
```

新：
```js
    vi.useFakeTimers();
    rerender({ cursorPresent: false });
    await advanceAndFlush(1500);
    vi.useRealTimers();

    await new Promise((r) => setTimeout(r, 50));

    // Should not crash, state should remain unchanged
    expect(result.current.savedSize).toBeNull();
```

- [ ] **Step 4: 更新 `restore behavior` 组**

每个 restore 测试当前结构是：先 shrink → 等 setSize 调用 → 清 mock → 进入 → 推进 2000ms → 等 restore。修改为：

a) shrink 阶段统一改为 `vi.useFakeTimers()` + `rerender({ cursorPresent: false })` + `await advanceAndFlush(1500)` + `vi.useRealTimers()` + `await vi.waitFor(...)`。

b) restore 阶段把 `vi.advanceTimersByTime(2000)` 改为 `vi.advanceTimersByTime(1500)`（默认对齐）。

需要按上述模式更新的 it 块：
- `should restore window to savedSize when cursor enters (false → true)`
- `should clamp restored size to fit within screen boundary`
- `should clamp width only when it exceeds screen boundary`
- `should use savedSize directly when monitor info is unavailable`
- `should use savedSize directly when currentMonitor returns null`
- `should handle restore API errors gracefully`
- `should cancel restore if mouse leaves before dwell delay elapses`（也需把 `cursor=false` 之后的 `vi.advanceTimersByTime(5000)` 留着，但断言变为 isShrunk=true 仍成立的同时 isWaitingShrink=true → 推进过 1500ms 后 mockSetSize 会被 shrink 第二次调用，所以这个测试需要小心：在断言阶段把 `enabled: false` 用于该测试，或在 leave 后立刻 `vi.advanceTimersByTime(5000)` 之前断言完毕，且仅推进到不超过 1499ms）— 详见下一步
- `should set isWaitingRestore during dwell wait period`

- [ ] **Step 5: 修复 `should cancel restore if mouse leaves before dwell delay elapses` 与新行为的交互**

旧测试在 enter dwell 中途 `rerender({ cursorPresent: false })`，然后 `vi.advanceTimersByTime(5000)` 验证 restore 没触发。新行为下，cursor=false 会启动 shrinkTimer，1500ms 后会调用 `setSize(initialSize)`。原断言 `expect(mockSetSize).not.toHaveBeenCalled()` 会失败。

修复：把测试改为只推进到 `< 1500ms`，并把"shrink 不该触发"换成"shrink dwell 启动了"：

旧：
```js
      // Cursor leaves at 1000ms (before 2s)
      vi.advanceTimersByTime(1000);
      rerender({ cursorPresent: false });

      // Advance well past 2000ms
      vi.advanceTimersByTime(5000);
      vi.useRealTimers();

      // Restore should NOT have fired
      expect(mockSetSize).not.toHaveBeenCalled();
      expect(result.current.isShrunk).toBe(true);
      expect(result.current.isWaitingRestore).toBe(false);
```

新：
```js
      // Cursor leaves at 800ms (before 1.5s restore dwell)
      vi.advanceTimersByTime(800);
      rerender({ cursorPresent: false });

      // Restore was cancelled immediately
      expect(result.current.isWaitingRestore).toBe(false);
      // Shrink dwell is now active
      expect(result.current.isWaitingShrink).toBe(true);

      // Advance to just before shrink dwell completes (total elapsed since leave: 1499ms)
      vi.advanceTimersByTime(1499);
      vi.useRealTimers();

      // Restore should NOT have fired (it was cancelled)
      // Shrink also has not fired yet (still inside dwell)
      expect(mockSetSize).not.toHaveBeenCalled();
      expect(result.current.isShrunk).toBe(true);
```

- [ ] **Step 6: 运行整个测试文件**

Run: `cd plan-viewer-desktop && npx vitest --run src/hooks/useWindowAutoShrink.test.js`
Expected: 全部测试 PASS。如果失败，定位是漏改的 timer 推进还是 cleanup 顺序。

- [ ] **Step 7: Commit**

```bash
git add plan-viewer-desktop/src/hooks/useWindowAutoShrink.test.js
git commit -m "test(useWindowAutoShrink): adapt unit tests to symmetric 1.5s dwell"
```

---

## Task 3: 迁移 `useWindowAutoShrink.property.test.js`

**Files:**
- Modify: `plan-viewer-desktop/src/hooks/useWindowAutoShrink.property.test.js`

该文件含 6 个 describe / property block。所有 shrink 触发点都需要在 `rerender({ cursorPresent: false })` 之后插入 fake-timer 推进 1500ms。所有现有的 `vi.advanceTimersByTime(2000)` 改为 `1500`。

- [ ] **Step 1: 在文件顶部添加 helper**

在最外层 describe 之外或最先的 describe 内添加：

```js
async function advanceAndFlush(ms) {
  await act(async () => {
    vi.advanceTimersByTime(ms);
    await Promise.resolve();
    await Promise.resolve();
    await Promise.resolve();
  });
}
```

- [ ] **Step 2: Property 1（round trip）— 给 shrink 阶段加 fake-timer 推进**

在 `rerender({ cursorPresent: false })` 之后、`await vi.waitFor(() => { expect(mockSetSize).toHaveBeenCalledTimes(1); });` 之前插入：

```js
          vi.useFakeTimers();
          await advanceAndFlush(1500);
          vi.useRealTimers();
```

随后把 restore 阶段的 `vi.advanceTimersByTime(2000)` 改为 `1500`：

旧：
```js
          rerender({ cursorPresent: true });
          await act(async () => {
            vi.advanceTimersByTime(2000);
            ...
```

新：
```js
          rerender({ cursorPresent: true });
          await act(async () => {
            vi.advanceTimersByTime(1500);
            ...
```

- [ ] **Step 3: Property 2（list of resizes）和 Property 3（screen overflow clamping）**

按 grep 结果，这两个 property 也有 shrink + restore 流程。同样：
- shrink 处插入 `vi.useFakeTimers()` + `advanceAndFlush(1500)` + `vi.useRealTimers()`。
- restore 阶段 `vi.advanceTimersByTime(2000)` → `1500`。

具体行号参考 grep 输出（254、353 等位置的 `vi.advanceTimersByTime(2000)`）。每个 property 内通常只有一个 restore advance；shrink advance 需要新增。

- [ ] **Step 4: Property 4（dwell cancellation property）**

旧测试 `it('window remains shrunk when mouse leaves before dwell delay completes', ...)` 中：

旧：
```js
        fc.integer({ min: 1, max: 1999 }),
```

应改为针对新默认（1499ms 上限）：

新：
```js
        fc.integer({ min: 1, max: 1499 }),
```

且测试内的 `vi.advanceTimersByTime(5000)` 可保留，但断言需补上"shrink 也尚未触发"。要在 leave 之后只推进到 `< shrinkDelayMs` 才能保持原来的"未调用 setSize"语义。改为：

旧：
```js
          // Leave before dwell completes
          rerender({ cursorPresent: false });

          // Advance well past 2000ms
          vi.advanceTimersByTime(5000);

          vi.useRealTimers();

          expect(mockSetSize).not.toHaveBeenCalled();
          expect(result.current.isShrunk).toBe(true);
          expect(result.current.isWaitingRestore).toBe(false);
```

新：
```js
          // Leave before restore dwell completes
          rerender({ cursorPresent: false });

          // Advance to just before shrink dwell completes (1499ms after leave)
          vi.advanceTimersByTime(1499);

          vi.useRealTimers();

          // Restore was cancelled, shrink is still pending
          expect(mockSetSize).not.toHaveBeenCalled();
          expect(result.current.isShrunk).toBe(true);
          expect(result.current.isWaitingRestore).toBe(false);
```

- [ ] **Step 5: Property 5（restore after full dwell）**

把 `vi.advanceTimersByTime(2000)` 改为 `1500`（两处）。该 property 内 shrink 阶段使用 `vi.waitFor` 直接断言 `setSize` 调用——shrink 现在不再立即触发，需要插入 fake-timer 推进：

旧（在 `await vi.waitFor(() => { expect(mockSetSize).toHaveBeenCalledTimes(1); });` 之前）：

新：在第一次 `rerender({ cursorPresent: false })` 之后、第一次 `vi.waitFor` 之前插入：
```js
          vi.useFakeTimers();
          await advanceAndFlush(1500);
          vi.useRealTimers();
```

- [ ] **Step 6: Property 6（rapid cycles never trigger restore）**

该 property 在 fake timer 模式下做 N 次 enter/leave 循环。新行为下需要确认：每次 leave 都会启动 shrinkTimer，循环之间 `vi.advanceTimersByTime(100)` 远短于 1500ms，所以前一个 shrinkTimer 不会触发；但**最后一次 leave 之后**的 `vi.advanceTimersByTime(10000)` 会让 shrinkTimer 到期、调用 `setSize(initialSize)`。

由于该 property 已经在 shrunk 状态开始（shrink 在 cycles 之前已发生一次），最后一次 shrink 调用 `performShrink` 时检查 `currentSize <= initialSize`，会 no-op 短路 — `setSize` 不会被调用。所以原断言 `expect(mockSetSize).not.toHaveBeenCalled()` 仍成立。**但只有当 mockInnerSize 在最后一次 shrink 时返回 ≤ initialSize 时**才成立。需要在循环之前重置 `mockInnerSize.mockResolvedValue({ width: initialSize.width, height: initialSize.height })`，或确认现有测试 setup 已经使 `mockInnerSize` 在 shrink 之后返回缩小后的尺寸。

最稳妥：在循环开始前插入：
```js
          // After the prior shrink the window is at initialSize. Make innerSize
          // reflect that so any shrinkTimer that fires during the rapid cycles
          // hits the "already small" no-op path.
          mockInnerSize.mockResolvedValue({ width: initialSize.width, height: initialSize.height });
```

并在循环内每次 `rerender({ cursorPresent: false })` 之后增加一次 `await Promise.resolve()` 让 microtask 排空（如果原代码已有则无需重复）。

把循环内的 advance 调整到不会触发 shrink：把每个 cycle 末尾的 `vi.advanceTimersByTime(100)` 换为：
```js
            // Stay just under shrinkDelayMs to avoid the shrinkTimer firing mid-loop
            vi.advanceTimersByTime(Math.min(100, 1499));
```
（实质等价于 100ms，但意图明确。）

- [ ] **Step 7: 运行 property 测试**

Run: `cd plan-viewer-desktop && npx vitest --run src/hooks/useWindowAutoShrink.property.test.js`
Expected: 全部 6 个 describe 块 PASS。

- [ ] **Step 8: Commit**

```bash
git add plan-viewer-desktop/src/hooks/useWindowAutoShrink.property.test.js
git commit -m "test(property): adapt main property tests to 1.5s symmetric dwell"
```

---

## Task 4: 迁移 `useWindowAutoShrink.property2.test.js`、`property3.test.js`

**Files:**
- Modify: `plan-viewer-desktop/src/hooks/useWindowAutoShrink.property2.test.js`
- Modify: `plan-viewer-desktop/src/hooks/useWindowAutoShrink.property3.test.js`

这两个文件结构类似：cursor leave → 立即 `await vi.waitFor` 验证 setSize。

- [ ] **Step 1: 在每个文件最外层 describe 顶部加 helper**

```js
async function advanceAndFlush(ms) {
  await act(async () => {
    vi.advanceTimersByTime(ms);
    await Promise.resolve();
    await Promise.resolve();
    await Promise.resolve();
  });
}
```

如果 `act` 没有 import，需要在文件顶部 `import { renderHook, act } from '@testing-library/preact';`。

- [ ] **Step 2: 在 leave 处插入 fake-timer 推进**

每个 `rerender({ cursorPresent: false })` 之后、`await vi.waitFor` 之前插入：

```js
          vi.useFakeTimers();
          await advanceAndFlush(1500);
          vi.useRealTimers();
```

- [ ] **Step 3: 运行**

Run: `cd plan-viewer-desktop && npx vitest --run src/hooks/useWindowAutoShrink.property2.test.js src/hooks/useWindowAutoShrink.property3.test.js`
Expected: PASS。

- [ ] **Step 4: Commit**

```bash
git add plan-viewer-desktop/src/hooks/useWindowAutoShrink.property2.test.js plan-viewer-desktop/src/hooks/useWindowAutoShrink.property3.test.js
git commit -m "test(property2,property3): inject 1.5s shrink dwell advance"
```

---

## Task 5: 迁移 `useWindowAutoShrink.property4.test.js`

**Files:**
- Modify: `plan-viewer-desktop/src/hooks/useWindowAutoShrink.property4.test.js`

第一个 it 块（"should not shrink while cursorPresent stays true"）不依赖 leave dwell — 不动。第二个 it 块包含 shrink → restore，需要更新。

- [ ] **Step 1: 第二个 it 块的 shrink 阶段**

在 `rerender({ cursorPresent: false })`（约第 116 行附近，参考 grep 结果）之后、第一次 `await vi.waitFor` 之前插入：

```js
          vi.useFakeTimers();
          await act(async () => {
            vi.advanceTimersByTime(1500);
            await Promise.resolve();
            await Promise.resolve();
          });
          vi.useRealTimers();
```

- [ ] **Step 2: restore 阶段把 `vi.advanceTimersByTime(2000)` 改为 `1500`**

旧（grep 结果显示在第 121 行）：
```js
            vi.advanceTimersByTime(2000);
```
新：
```js
            vi.advanceTimersByTime(1500);
```

- [ ] **Step 3: 运行**

Run: `cd plan-viewer-desktop && npx vitest --run src/hooks/useWindowAutoShrink.property4.test.js`
Expected: PASS。

- [ ] **Step 4: Commit**

```bash
git add plan-viewer-desktop/src/hooks/useWindowAutoShrink.property4.test.js
git commit -m "test(property4): adapt restore-after-reentry test to 1.5s dwell"
```

---

## Task 6: 新增 `useWindowAutoShrink.shrinkDwell.property.test.js`

**Files:**
- Create: `plan-viewer-desktop/src/hooks/useWindowAutoShrink.shrinkDwell.property.test.js`

5 条新 property 覆盖 leave dwell + chain restore 不变量。沿用现有 mock setup pattern（参考 `property.test.js` 的 mock 块）。

- [ ] **Step 1: 创建文件骨架与 mock**

```js
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/preact';
import * as fc from 'fast-check';
import { useWindowAutoShrink } from './useWindowAutoShrink.js';

const mockSetSize = vi.fn().mockResolvedValue(undefined);
const mockInnerSize = vi.fn().mockResolvedValue({ width: 800, height: 600 });
const mockScaleFactor = vi.fn().mockResolvedValue(1);
const mockOuterPosition = vi.fn().mockResolvedValue({ x: 100, y: 100 });
const mockOnResized = vi.fn().mockResolvedValue(() => {});
const mockCurrentMonitor = vi.fn().mockResolvedValue({
  size: { width: 3840, height: 2160 },
});

vi.mock('@tauri-apps/api/window', () => ({
  getCurrentWindow: () => ({
    setSize: mockSetSize,
    innerSize: mockInnerSize,
    scaleFactor: mockScaleFactor,
    outerPosition: mockOuterPosition,
    onResized: mockOnResized,
  }),
  currentMonitor: (...args) => mockCurrentMonitor(...args),
  LogicalSize: class LogicalSize {
    constructor(width, height) {
      this.width = width;
      this.height = height;
    }
  },
}));

const initialSize = { width: 400, height: 300 };

async function advanceAndFlush(ms) {
  await act(async () => {
    vi.advanceTimersByTime(ms);
    await Promise.resolve();
    await Promise.resolve();
    await Promise.resolve();
  });
}

beforeEach(() => {
  vi.clearAllMocks();
  mockSetSize.mockResolvedValue(undefined);
  mockInnerSize.mockResolvedValue({ width: 800, height: 600 });
  mockOuterPosition.mockResolvedValue({ x: 100, y: 100 });
  mockCurrentMonitor.mockResolvedValue({ size: { width: 3840, height: 2160 } });
  mockOnResized.mockResolvedValue(() => {});
});
```

- [ ] **Step 2: Property — leave dwell delays shrink**

```js
describe('Feature: symmetric-dwell-delays, Property: leave dwell delays shrink', () => {
  it('shrink does not fire before shrinkDelayMs has elapsed since cursor leave', async () => {
    await fc.assert(
      fc.asyncProperty(
        fc.integer({ min: 401, max: 3000 }),
        fc.integer({ min: 301, max: 2000 }),
        fc.integer({ min: 1, max: 1499 }),
        async (width, height, dwellTime) => {
          vi.clearAllMocks();
          mockSetSize.mockResolvedValue(undefined);
          mockInnerSize.mockResolvedValue({ width, height });

          const { result, rerender, unmount } = renderHook(
            ({ cursorPresent }) =>
              useWindowAutoShrink({ cursorPresent, enabled: true, initialSize }),
            { initialProps: { cursorPresent: true } }
          );

          vi.useFakeTimers();
          rerender({ cursorPresent: false });
          expect(result.current.isWaitingShrink).toBe(true);

          // Stay below the shrink dwell threshold
          vi.advanceTimersByTime(dwellTime);
          vi.useRealTimers();

          expect(mockSetSize).not.toHaveBeenCalled();
          expect(result.current.isShrunk).toBe(false);
          expect(result.current.isWaitingShrink).toBe(true);

          unmount();
        }
      ),
      { numRuns: 50 }
    );
  }, 30000);
});
```

- [ ] **Step 3: Property — shrink fires after leave dwell**

```js
describe('Feature: symmetric-dwell-delays, Property: shrink fires after leave dwell completes', () => {
  it('shrink fires exactly once when cursor stays away for shrinkDelayMs', async () => {
    await fc.assert(
      fc.asyncProperty(
        fc.integer({ min: 401, max: 3000 }),
        fc.integer({ min: 301, max: 2000 }),
        async (width, height) => {
          vi.clearAllMocks();
          mockSetSize.mockResolvedValue(undefined);
          mockInnerSize.mockResolvedValue({ width, height });

          const { result, rerender, unmount } = renderHook(
            ({ cursorPresent }) =>
              useWindowAutoShrink({ cursorPresent, enabled: true, initialSize }),
            { initialProps: { cursorPresent: true } }
          );

          vi.useFakeTimers();
          rerender({ cursorPresent: false });
          await advanceAndFlush(1500);
          vi.useRealTimers();

          await vi.waitFor(() => {
            expect(mockSetSize).toHaveBeenCalledTimes(1);
          });

          const sizeArg = mockSetSize.mock.calls[0][0];
          expect(sizeArg.width).toBe(initialSize.width);
          expect(sizeArg.height).toBe(initialSize.height);
          expect(result.current.isShrunk).toBe(true);
          expect(result.current.savedSize).toEqual({ width, height });

          unmount();
        }
      ),
      { numRuns: 50 }
    );
  }, 30000);
});
```

- [ ] **Step 4: Property — re-entry during leave dwell does NOT cancel shrink**

```js
describe('Feature: symmetric-dwell-delays, Property: re-entry does not cancel shrink (option B)', () => {
  it('cursor returning during leave dwell still results in shrink', async () => {
    await fc.assert(
      fc.asyncProperty(
        fc.integer({ min: 401, max: 3000 }),
        fc.integer({ min: 301, max: 2000 }),
        fc.integer({ min: 1, max: 1499 }),
        async (width, height, reentryAt) => {
          vi.clearAllMocks();
          mockSetSize.mockResolvedValue(undefined);
          mockInnerSize.mockResolvedValue({ width, height });

          const { result, rerender, unmount } = renderHook(
            ({ cursorPresent }) =>
              useWindowAutoShrink({ cursorPresent, enabled: true, initialSize }),
            { initialProps: { cursorPresent: true } }
          );

          vi.useFakeTimers();
          rerender({ cursorPresent: false });

          // Re-enter at some point inside the leave dwell window
          vi.advanceTimersByTime(reentryAt);
          rerender({ cursorPresent: true });

          // Continue advancing until shrink dwell would have fired
          await advanceAndFlush(1500 - reentryAt);
          vi.useRealTimers();

          // Shrink fired despite the re-entry
          await vi.waitFor(() => {
            expect(mockSetSize).toHaveBeenCalledTimes(1);
          });
          const sizeArg = mockSetSize.mock.calls[0][0];
          expect(sizeArg.width).toBe(initialSize.width);
          expect(sizeArg.height).toBe(initialSize.height);
          expect(result.current.savedSize).toEqual({ width, height });

          unmount();
        }
      ),
      { numRuns: 50 }
    );
  }, 30000);
});
```

- [ ] **Step 5: Property — shrink-then-restore chain when cursor stays inside**

```js
describe('Feature: symmetric-dwell-delays, Property: shrink chains into restore when cursor stays inside', () => {
  it('after shrink fires with cursor still inside, restore fires shrinkDelayMs+restoreDelayMs later', async () => {
    await fc.assert(
      fc.asyncProperty(
        fc.integer({ min: 401, max: 3000 }),
        fc.integer({ min: 301, max: 2000 }),
        fc.integer({ min: 1, max: 1499 }),
        async (width, height, reentryAt) => {
          vi.clearAllMocks();
          mockSetSize.mockResolvedValue(undefined);
          mockInnerSize.mockResolvedValue({ width, height });

          const { result, rerender, unmount } = renderHook(
            ({ cursorPresent }) =>
              useWindowAutoShrink({ cursorPresent, enabled: true, initialSize }),
            { initialProps: { cursorPresent: true } }
          );

          vi.useFakeTimers();
          rerender({ cursorPresent: false });
          vi.advanceTimersByTime(reentryAt);
          rerender({ cursorPresent: true });

          // Run leave dwell to completion → triggers shrinkTimerCallback
          await advanceAndFlush(1500 - reentryAt);
          // performShrink internally awaits a 100ms timeout before resetting
          // isResizingRef. Flush that, plus a few microtasks, so the chained
          // restore-timer setup at the end of shrinkTimerCallback runs.
          await advanceAndFlush(150);
          // Now run the chained restore dwell
          await advanceAndFlush(1500);
          vi.useRealTimers();

          await vi.waitFor(() => {
            // shrink + restore = 2 calls
            expect(mockSetSize).toHaveBeenCalledTimes(2);
          });

          const shrinkArg = mockSetSize.mock.calls[0][0];
          const restoreArg = mockSetSize.mock.calls[1][0];
          expect(shrinkArg.width).toBe(initialSize.width);
          expect(restoreArg.width).toBe(width);
          expect(restoreArg.height).toBe(height);
          expect(result.current.isShrunk).toBe(false);

          unmount();
        }
      ),
      { numRuns: 30 }
    );
  }, 60000);
});
```

- [ ] **Step 6: Property — repeated leave resets shrink dwell**

```js
describe('Feature: symmetric-dwell-delays, Property: repeated leave resets shrink dwell', () => {
  it('a second leave restarts the shrink dwell timer', async () => {
    await fc.assert(
      fc.asyncProperty(
        fc.integer({ min: 401, max: 3000 }),
        fc.integer({ min: 301, max: 2000 }),
        fc.integer({ min: 100, max: 700 }),  // first leave waits this long
        fc.integer({ min: 100, max: 700 }),  // re-enter delay before second leave
        async (width, height, firstLeaveWait, reEnterPause) => {
          vi.clearAllMocks();
          mockSetSize.mockResolvedValue(undefined);
          mockInnerSize.mockResolvedValue({ width, height });

          const { result, rerender, unmount } = renderHook(
            ({ cursorPresent }) =>
              useWindowAutoShrink({ cursorPresent, enabled: true, initialSize }),
            { initialProps: { cursorPresent: true } }
          );

          vi.useFakeTimers();

          // First leave
          rerender({ cursorPresent: false });
          vi.advanceTimersByTime(firstLeaveWait);

          // Re-enter (does NOT cancel shrink, but re-arms restore)
          rerender({ cursorPresent: true });
          vi.advanceTimersByTime(reEnterPause);

          // Second leave — must reset the shrink dwell timer
          rerender({ cursorPresent: false });

          // Just before the reset 1500ms elapses
          vi.advanceTimersByTime(1499);
          expect(mockSetSize).not.toHaveBeenCalled();

          // One more ms — shrink fires
          await advanceAndFlush(1);
          vi.useRealTimers();

          await vi.waitFor(() => {
            expect(mockSetSize).toHaveBeenCalledTimes(1);
          });

          unmount();
        }
      ),
      { numRuns: 30 }
    );
  }, 30000);
});
```

- [ ] **Step 7: 运行新文件**

Run: `cd plan-viewer-desktop && npx vitest --run src/hooks/useWindowAutoShrink.shrinkDwell.property.test.js`
Expected: 全部 5 个 property 块 PASS。

- [ ] **Step 8: Commit**

```bash
git add plan-viewer-desktop/src/hooks/useWindowAutoShrink.shrinkDwell.property.test.js
git commit -m "test(property): symmetric dwell + option B chain invariants"
```

---

## Task 7: 全量回归 + 集成手测

**Files:** none (validation only)

- [ ] **Step 1: 跑整个测试套件**

Run: `cd plan-viewer-desktop && npm test`
Expected: 全部 PASS。如有失败，定位是漏改的 timer 推进、cleanup 或 `enabled` 判断。

- [ ] **Step 2: 启动 Tauri dev 模式手测**

Run（用户手动跑）: `cd plan-viewer-desktop && npm run tauri dev`

按下面四条路径手测：
1. 进入 → 默念 1.5s → 看到放大。
2. 离开 → 默念 1.5s → 看到缩小。
3. 进入 → < 1.5s 离开 → 不放大。
4. 离开 → < 1.5s 进入 → 仍缩小，再 1.5s 后又放大（option B 表现）。

- [ ] **Step 3: 如有发现的回归，修复后再 commit**

```bash
git add -A
git commit -m "fix: regression found during integration test"
```

---

## Task 8: 更新 requirements 文档

**Files:**
- Modify: `.kiro/specs/window-auto-shrink/requirements.md`

- [ ] **Step 1: 更新 Requirement 1 触发延迟**

把 Requirement 1 中"鼠标离开 → 立即缩小"的 AC 改为"鼠标离开并停留 Shrink_Dwell_Delay (1500ms) 后缩小"。具体行号取决于现有文档（按需 grep）。

- [ ] **Step 2: 更新 Requirement 2 AC 1**

把 dwell 时长从 2000ms 改为 1500ms。同时记录 option B 行为：leave dwell 期间 cursor re-entry 不取消缩小。

- [ ] **Step 3: 更新 Glossary**

在 `Restore_Dwell_Delay` 之外添加：

```markdown
- **Shrink_Dwell_Delay**: 鼠标离开窗口后，需持续在窗口外停留的时间（1500ms），超过此时间才触发窗口缩小
```

把 `Restore_Dwell_Delay` 的 2000ms 改为 1500ms。

- [ ] **Step 4: Commit**

```bash
git add .kiro/specs/window-auto-shrink/requirements.md
git commit -m "docs(window-auto-shrink): symmetric 1.5s dwell + Shrink_Dwell_Delay glossary"
```

---

## Summary

| Task | Description | Est. |
|------|-------------|------|
| 1 | 修改 hook：加 shrinkTimer + chain restore | 8 min |
| 2 | 适配 useWindowAutoShrink.test.js | 10 min |
| 3 | 适配 property.test.js（6 blocks）| 10 min |
| 4 | 适配 property2 + property3 | 4 min |
| 5 | 适配 property4 | 3 min |
| 6 | 新增 shrinkDwell property tests | 10 min |
| 7 | 全量回归 + 手测 | 5 min |
| 8 | 更新 requirements 文档 | 3 min |

Total estimated: ~53 minutes
