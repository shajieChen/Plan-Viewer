# Restore Dwell Delay Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a 2-second hover dwell delay before the window restores from its shrunk state, preventing accidental enlargement when the cursor briefly passes over the window.

**Architecture:** Modify the existing `useWindowAutoShrink` hook to defer `performRestore()` behind a 2000ms timer. On `idle → active` transition, start the timer instead of restoring immediately. On `active → idle` transition, cancel the timer if it's still pending. Transparency (CSS class) continues to toggle immediately on enter/leave as before — only the size restore is deferred.

**Tech Stack:** Preact hooks, Tauri window API, Vitest, fast-check (PBT)

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `src/hooks/useWindowAutoShrink.js` | Add `restoreDelayMs` param, `restoreTimerRef`, `isWaitingRestore` state, deferred restore logic |
| Modify | `src/hooks/useWindowAutoShrink.test.js` | Update existing restore tests to account for 2s delay |
| Modify | `src/hooks/useWindowAutoShrink.property.test.js` | Update Property 1 round-trip test, add new dwell properties |

No changes needed to `App.jsx`, `useWindowHover.js`, `TitleBar.jsx`, or `styles.css`. The hook interface is backward-compatible (new param has a default).

---

### Task 1: Update `useWindowAutoShrink` hook — add restore delay logic

**Files:**
- Modify: `src/hooks/useWindowAutoShrink.js`

- [ ] **Step 1: Add restoreDelayMs parameter and new state**

Open `src/hooks/useWindowAutoShrink.js`. Add `restoreDelayMs = 2000` to the destructured options. Add `isWaitingRestore` state and `restoreTimerRef` ref:

```js
export function useWindowAutoShrink({ hoverState, enabled, initialSize, restoreDelayMs = 2000 }) {
  const [savedSize, setSavedSize] = useState(null);
  const [isShrunk, setIsShrunk] = useState(false);
  const [isWaitingRestore, setIsWaitingRestore] = useState(false);
  const prevHoverStateRef = useRef(hoverState);
  const isResizingRef = useRef(false);
  const restoreTimerRef = useRef(null);
```

- [ ] **Step 2: Replace immediate restore with deferred restore**

In the main `useEffect`, replace the direct `performRestore()` call with a timer-based approach:

```js
  useEffect(() => {
    const prevState = prevHoverStateRef.current;
    prevHoverStateRef.current = hoverState;

    // Shrink: active → idle transition when enabled
    if (prevState === 'active' && hoverState === 'idle' && enabled) {
      // Cancel any pending restore timer
      if (restoreTimerRef.current) {
        clearTimeout(restoreTimerRef.current);
        restoreTimerRef.current = null;
        setIsWaitingRestore(false);
      }
      performShrink();
    }

    // Restore: idle → active transition when savedSize exists
    if (prevState === 'idle' && hoverState === 'active' && savedSize) {
      // Start dwell timer instead of restoring immediately
      restoreTimerRef.current = setTimeout(() => {
        restoreTimerRef.current = null;
        setIsWaitingRestore(false);
        performRestore();
      }, restoreDelayMs);
      setIsWaitingRestore(true);
    }

    // Cancel restore timer if leaving while waiting (active → idle while isWaitingRestore)
    if (prevState === 'active' && hoverState === 'idle' && !enabled) {
      if (restoreTimerRef.current) {
        clearTimeout(restoreTimerRef.current);
        restoreTimerRef.current = null;
        setIsWaitingRestore(false);
      }
    }
  }, [hoverState, enabled, initialSize, restoreDelayMs]);
```

- [ ] **Step 3: Add cleanup for restoreTimer on unmount**

Add a separate effect to clean up the restore timer when the component unmounts:

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

- [ ] **Step 4: Update return value**

Update the return statement to include `isWaitingRestore`:

```js
  return { savedSize, isShrunk, isWaitingRestore };
```

- [ ] **Step 5: Run existing tests to see which ones break**

Run: `npm test` (in `plan-viewer-desktop/`)

Expected: Some restore-related tests will fail because they expect immediate restore behavior. This confirms the behavior change is effective.

- [ ] **Step 6: Commit the hook change**

```bash
git add src/hooks/useWindowAutoShrink.js
git commit -m "feat: add restore dwell delay to useWindowAutoShrink hook"
```

---

### Task 2: Update unit tests for deferred restore behavior

**Files:**
- Modify: `src/hooks/useWindowAutoShrink.test.js`

- [ ] **Step 1: Enable fake timers in restore tests**

Add `vi.useFakeTimers()` and `vi.useRealTimers()` around the restore describe block:

```js
  describe('restore behavior (idle → active)', () => {
    beforeEach(() => {
      vi.useFakeTimers();
    });

    afterEach(() => {
      vi.useRealTimers();
    });
```

- [ ] **Step 2: Update "should restore window to savedSize on idle → active transition" test**

The restore now requires advancing timers by 2000ms:

```js
    it('should restore window to savedSize on idle → active transition after dwell delay', async () => {
      vi.useRealTimers(); // shrink uses real async
      const { result, rerender } = renderHook(
        ({ hoverState }) => useWindowAutoShrink({ hoverState, enabled: true, initialSize }),
        { initialProps: { hoverState: 'active' } }
      );

      // First: shrink (active → idle)
      rerender({ hoverState: 'idle' });

      await vi.waitFor(() => {
        expect(mockSetSize).toHaveBeenCalledTimes(1);
      });

      expect(result.current.savedSize).toEqual({ width: 800, height: 600 });
      expect(result.current.isShrunk).toBe(true);

      mockSetSize.mockClear();

      // Switch to fake timers for the restore delay
      vi.useFakeTimers();

      // Then: restore (idle → active) — starts dwell timer
      rerender({ hoverState: 'active' });

      // Should NOT restore immediately
      expect(mockSetSize).not.toHaveBeenCalled();
      expect(result.current.isWaitingRestore).toBe(true);

      // Advance timer by 2000ms
      await act(async () => {
        vi.advanceTimersByTime(2000);
      });

      // Now it should restore
      await vi.waitFor(() => {
        expect(mockSetSize).toHaveBeenCalledTimes(1);
      });

      const restoreArg = mockSetSize.mock.calls[0][0];
      expect(restoreArg.width).toBe(800);
      expect(restoreArg.height).toBe(600);
      expect(result.current.isShrunk).toBe(false);
      expect(result.current.isWaitingRestore).toBe(false);
    });
```

- [ ] **Step 3: Add test for dwell cancellation on early leave**

```js
    it('should cancel restore if mouse leaves before dwell delay elapses', async () => {
      vi.useRealTimers();
      const { result, rerender } = renderHook(
        ({ hoverState }) => useWindowAutoShrink({ hoverState, enabled: true, initialSize }),
        { initialProps: { hoverState: 'active' } }
      );

      // Shrink first
      rerender({ hoverState: 'idle' });

      await vi.waitFor(() => {
        expect(mockSetSize).toHaveBeenCalledTimes(1);
      });

      mockSetSize.mockClear();
      vi.useFakeTimers();

      // Enter (starts dwell timer)
      rerender({ hoverState: 'active' });
      expect(result.current.isWaitingRestore).toBe(true);

      // Leave before 2000ms (at 1000ms)
      vi.advanceTimersByTime(1000);
      rerender({ hoverState: 'idle' });

      // Advance past the original 2000ms mark
      vi.advanceTimersByTime(2000);

      // Should NOT have restored — timer was cancelled
      expect(mockSetSize).not.toHaveBeenCalled();
      expect(result.current.isShrunk).toBe(true);
      expect(result.current.isWaitingRestore).toBe(false);
    });
```

- [ ] **Step 4: Add test for isWaitingRestore state**

```js
    it('should set isWaitingRestore during dwell wait period', async () => {
      vi.useRealTimers();
      const { result, rerender } = renderHook(
        ({ hoverState }) => useWindowAutoShrink({ hoverState, enabled: true, initialSize }),
        { initialProps: { hoverState: 'active' } }
      );

      // Shrink
      rerender({ hoverState: 'idle' });
      await vi.waitFor(() => {
        expect(mockSetSize).toHaveBeenCalledTimes(1);
      });

      mockSetSize.mockClear();
      vi.useFakeTimers();

      // Enter — isWaitingRestore should become true
      rerender({ hoverState: 'active' });
      expect(result.current.isWaitingRestore).toBe(true);

      // After delay — isWaitingRestore should become false
      await act(async () => {
        vi.advanceTimersByTime(2000);
      });

      await vi.waitFor(() => {
        expect(result.current.isWaitingRestore).toBe(false);
      });
    });
```

- [ ] **Step 5: Update remaining restore tests (clamping, error handling) to use timer advance**

For each existing restore test that checks the restored size, insert the timer advance pattern after transitioning to `active`:

```js
// After rerender({ hoverState: 'active' }):
await act(async () => {
  vi.advanceTimersByTime(2000);
});
```

Apply this pattern to:
- "should clamp restored size to fit within screen boundary"
- "should clamp width only when it exceeds screen boundary"
- "should use savedSize directly when monitor info is unavailable"
- "should use savedSize directly when currentMonitor returns null"
- "should handle restore API errors gracefully"

- [ ] **Step 6: Run all unit tests**

Run: `npm test -- src/hooks/useWindowAutoShrink.test.js`

Expected: All tests PASS.

- [ ] **Step 7: Commit updated unit tests**

```bash
git add src/hooks/useWindowAutoShrink.test.js
git commit -m "test: update unit tests for restore dwell delay behavior"
```

---

### Task 3: Update Property 1 (round-trip) to account for dwell delay

**Files:**
- Modify: `src/hooks/useWindowAutoShrink.property.test.js`

- [ ] **Step 1: Update Property 1 shrink-then-restore round trip**

The round trip now requires a timer advance between `idle → active` and the actual restore. Update the property test:

```js
describe('Feature: window-auto-shrink, Property 1: Shrink-then-restore round trip', () => {
  const initialSize = { width: 400, height: 300 };

  beforeEach(() => {
    vi.clearAllMocks();
    mockSetSize.mockResolvedValue(undefined);
    mockOuterPosition.mockResolvedValue({ x: 0, y: 0 });
    mockCurrentMonitor.mockResolvedValue({ size: { width: 3840, height: 2160 } });
    mockOnResized.mockResolvedValue(() => {});
  });

  it('should restore window to original dimensions after shrink-then-restore cycle', async () => {
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
            ({ hoverState }) =>
              useWindowAutoShrink({ hoverState, enabled: true, initialSize }),
            { initialProps: { hoverState: 'active' } }
          );

          // Shrink: active → idle
          rerender({ hoverState: 'idle' });

          await vi.waitFor(() => {
            expect(mockSetSize).toHaveBeenCalledTimes(1);
          });

          const shrinkArg = mockSetSize.mock.calls[0][0];
          expect(shrinkArg.width).toBe(initialSize.width);
          expect(shrinkArg.height).toBe(initialSize.height);
          expect(result.current.savedSize).toEqual({ width, height });
          expect(result.current.isShrunk).toBe(true);

          mockSetSize.mockClear();

          // Use fake timers for dwell delay
          vi.useFakeTimers();

          // Restore: idle → active (starts 2s dwell timer)
          rerender({ hoverState: 'active' });

          // Advance past dwell delay
          await act(async () => {
            vi.advanceTimersByTime(2000);
          });

          vi.useRealTimers();

          await vi.waitFor(() => {
            expect(mockSetSize).toHaveBeenCalledTimes(1);
          });

          const restoreArg = mockSetSize.mock.calls[0][0];
          expect(restoreArg.width).toBe(width);
          expect(restoreArg.height).toBe(height);
          expect(result.current.isShrunk).toBe(false);

          unmount();
        }
      ),
      { numRuns: 50 }
    );
  }, 60000);
});
```

- [ ] **Step 2: Run Property 1 test**

Run: `npm test -- src/hooks/useWindowAutoShrink.property.test.js`

Expected: Property 1 passes (may need to adjust timer strategy if vitest fake timers interact poorly with `vi.waitFor`).

- [ ] **Step 3: Commit**

```bash
git add src/hooks/useWindowAutoShrink.property.test.js
git commit -m "test: update Property 1 round-trip for dwell delay"
```

---

### Task 4: Add new property tests for dwell behavior

**Files:**
- Modify: `src/hooks/useWindowAutoShrink.property.test.js`

- [ ] **Step 1: Add Property — Restore dwell cancellation**

Append to the property test file:

```js
describe('Feature: restore-dwell-delay, Property: Dwell cancellation on early leave', () => {
  const initialSize = { width: 400, height: 300 };

  beforeEach(() => {
    vi.clearAllMocks();
    mockSetSize.mockResolvedValue(undefined);
    mockOuterPosition.mockResolvedValue({ x: 0, y: 0 });
    mockCurrentMonitor.mockResolvedValue({ size: { width: 3840, height: 2160 } });
    mockOnResized.mockResolvedValue(() => {});
  });

  /**
   * **Validates: Restore Dwell Delay spec — cancellation behavior**
   *
   * For any random dwell time t ∈ (0, 2000ms), if the mouse leaves
   * the window before t reaches 2000ms, the window should NOT restore.
   */
  it('window remains shrunk when mouse leaves before dwell delay completes', async () => {
    await fc.assert(
      fc.asyncProperty(
        fc.integer({ min: 401, max: 2000 }),  // savedSize width
        fc.integer({ min: 301, max: 1500 }),  // savedSize height
        fc.integer({ min: 1, max: 1999 }),     // dwell time before leave (< 2000)
        async (width, height, dwellTime) => {
          vi.clearAllMocks();
          mockSetSize.mockResolvedValue(undefined);
          mockInnerSize.mockResolvedValue({ width, height });
          mockOuterPosition.mockResolvedValue({ x: 0, y: 0 });
          mockCurrentMonitor.mockResolvedValue({ size: { width: 3840, height: 2160 } });
          mockOnResized.mockResolvedValue(() => {});

          const { result, rerender, unmount } = renderHook(
            ({ hoverState }) =>
              useWindowAutoShrink({ hoverState, enabled: true, initialSize }),
            { initialProps: { hoverState: 'active' } }
          );

          // Shrink first: active → idle
          rerender({ hoverState: 'idle' });

          await vi.waitFor(() => {
            expect(mockSetSize).toHaveBeenCalledTimes(1);
          });

          expect(result.current.isShrunk).toBe(true);
          mockSetSize.mockClear();

          // Switch to fake timers for dwell measurement
          vi.useFakeTimers();

          // Enter window (starts dwell timer)
          rerender({ hoverState: 'active' });
          expect(result.current.isWaitingRestore).toBe(true);

          // Advance by dwellTime (< 2000ms)
          vi.advanceTimersByTime(dwellTime);

          // Leave before dwell completes
          rerender({ hoverState: 'idle' });

          // Advance well past 2000ms to prove timer was cancelled
          vi.advanceTimersByTime(5000);

          vi.useRealTimers();

          // Window should NOT have been restored
          expect(mockSetSize).not.toHaveBeenCalled();
          expect(result.current.isShrunk).toBe(true);
          expect(result.current.isWaitingRestore).toBe(false);

          unmount();
        }
      ),
      { numRuns: 100 }
    );
  }, 30000);
});
```

- [ ] **Step 2: Add Property — Restore after dwell completes**

```js
describe('Feature: restore-dwell-delay, Property: Restore triggers after full dwell', () => {
  const initialSize = { width: 400, height: 300 };

  beforeEach(() => {
    vi.clearAllMocks();
    mockSetSize.mockResolvedValue(undefined);
    mockOuterPosition.mockResolvedValue({ x: 0, y: 0 });
    mockCurrentMonitor.mockResolvedValue({ size: { width: 3840, height: 2160 } });
    mockOnResized.mockResolvedValue(() => {});
  });

  /**
   * **Validates: Restore Dwell Delay spec — successful restore after dwell**
   *
   * For any window dimensions, if the mouse stays in the window
   * for at least 2000ms, the window should restore to savedSize.
   */
  it('window restores to savedSize after dwell delay completes', async () => {
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
            ({ hoverState }) =>
              useWindowAutoShrink({ hoverState, enabled: true, initialSize }),
            { initialProps: { hoverState: 'active' } }
          );

          // Shrink: active → idle
          rerender({ hoverState: 'idle' });

          await vi.waitFor(() => {
            expect(mockSetSize).toHaveBeenCalledTimes(1);
          });

          expect(result.current.isShrunk).toBe(true);
          expect(result.current.savedSize).toEqual({ width, height });
          mockSetSize.mockClear();

          // Switch to fake timers
          vi.useFakeTimers();

          // Enter window (starts dwell timer)
          rerender({ hoverState: 'active' });
          expect(result.current.isWaitingRestore).toBe(true);

          // Advance full 2000ms
          await act(async () => {
            vi.advanceTimersByTime(2000);
          });

          vi.useRealTimers();

          // Restore should have been called
          await vi.waitFor(() => {
            expect(mockSetSize).toHaveBeenCalledTimes(1);
          });

          const restoreArg = mockSetSize.mock.calls[0][0];
          expect(restoreArg.width).toBe(width);
          expect(restoreArg.height).toBe(height);
          expect(result.current.isShrunk).toBe(false);
          expect(result.current.isWaitingRestore).toBe(false);

          unmount();
        }
      ),
      { numRuns: 100 }
    );
  }, 30000);
});
```

- [ ] **Step 3: Add Property — Multiple rapid enter-leave cycles**

```js
describe('Feature: restore-dwell-delay, Property: Multiple rapid cycles never trigger restore', () => {
  const initialSize = { width: 400, height: 300 };

  beforeEach(() => {
    vi.clearAllMocks();
    mockSetSize.mockResolvedValue(undefined);
    mockOuterPosition.mockResolvedValue({ x: 0, y: 0 });
    mockCurrentMonitor.mockResolvedValue({ size: { width: 3840, height: 2160 } });
    mockOnResized.mockResolvedValue(() => {});
  });

  /**
   * **Validates: Restore Dwell Delay spec — rapid cycle edge case**
   *
   * For any number of rapid enter-leave cycles (each < 2s),
   * the window should never restore to savedSize.
   */
  it('N rapid enter-leave cycles (each < 2s) never trigger restore', async () => {
    await fc.assert(
      fc.asyncProperty(
        fc.integer({ min: 2, max: 10 }),         // number of cycles
        fc.integer({ min: 1, max: 1999 }),        // dwell time per cycle
        async (numCycles, dwellTime) => {
          vi.clearAllMocks();
          mockSetSize.mockResolvedValue(undefined);
          mockInnerSize.mockResolvedValue({ width: 800, height: 600 });
          mockOuterPosition.mockResolvedValue({ x: 0, y: 0 });
          mockCurrentMonitor.mockResolvedValue({ size: { width: 3840, height: 2160 } });
          mockOnResized.mockResolvedValue(() => {});

          const { result, rerender, unmount } = renderHook(
            ({ hoverState }) =>
              useWindowAutoShrink({ hoverState, enabled: true, initialSize }),
            { initialProps: { hoverState: 'active' } }
          );

          // Shrink first
          rerender({ hoverState: 'idle' });

          await vi.waitFor(() => {
            expect(mockSetSize).toHaveBeenCalledTimes(1);
          });

          expect(result.current.isShrunk).toBe(true);
          mockSetSize.mockClear();

          vi.useFakeTimers();

          // Rapid enter-leave cycles
          for (let i = 0; i < numCycles; i++) {
            rerender({ hoverState: 'active' });
            vi.advanceTimersByTime(dwellTime);
            rerender({ hoverState: 'idle' });
            vi.advanceTimersByTime(100); // small gap between cycles
          }

          // Advance well past any possible pending timer
          vi.advanceTimersByTime(10000);

          vi.useRealTimers();

          // No restore should have been called
          expect(mockSetSize).not.toHaveBeenCalled();
          expect(result.current.isShrunk).toBe(true);

          unmount();
        }
      ),
      { numRuns: 50 }
    );
  }, 30000);
});
```

- [ ] **Step 4: Run all property tests**

Run: `npm test -- src/hooks/useWindowAutoShrink.property.test.js`

Expected: All property tests PASS.

- [ ] **Step 5: Commit new property tests**

```bash
git add src/hooks/useWindowAutoShrink.property.test.js
git commit -m "test: add dwell delay property tests (cancellation, restore, rapid cycles)"
```

---

### Task 5: Run full test suite and fix any remaining issues

**Files:**
- Possibly modify any of the above test files if issues arise

- [ ] **Step 1: Run the entire test suite**

Run: `npm test` (in `plan-viewer-desktop/`)

Expected: All tests PASS. If any test fails, fix it before proceeding.

- [ ] **Step 2: Verify the hook still handles edge cases**

Specifically verify these scenarios work:
- Hook with `restoreDelayMs` not provided uses default 2000ms
- Hook with `enabled: false` never triggers restore timer
- Manual resize during dwell wait properly updates savedSize

- [ ] **Step 3: Final commit if any fixes were needed**

```bash
git add -A
git commit -m "fix: resolve test issues from dwell delay integration"
```

---

### Task 6: Update requirements document

**Files:**
- Modify: `.kiro/specs/window-auto-shrink/requirements.md`

- [ ] **Step 1: Add Requirement 8 to the requirements doc**

Append after Requirement 7:

```markdown
### Requirement 8: 恢复放大停留延迟

**User Story:** As a 用户, I want 鼠标需要在缩小窗口内停留一段时间才触发放大, so that 鼠标快速划过窗口时不会触发意外的放大抖动。

#### Acceptance Criteria

1. WHEN the mouse enters the window area while the window is in shrunk state, THE Window_Manager SHALL start a 2000ms dwell timer before performing the restore operation.
2. WHEN the mouse leaves the window area before the 2000ms dwell timer elapses, THE Window_Manager SHALL cancel the pending restore and keep the window at Initial_Size.
3. WHEN the mouse enters the window area while the window is in shrunk state, THE Window_Manager SHALL immediately restore opacity (via CSS class transition to Active_State) without waiting for the dwell timer.
4. THE Window_Manager SHALL reset the dwell timer on each new mouse-enter event (no accumulation from previous partial dwells).
```

- [ ] **Step 2: Update Requirement 2, AC 1 to reference the new dwell delay**

Change Requirement 2, AC 1 from:
```
1. WHEN the mouse enters the window area, THE Window_Manager SHALL resize the window to the Saved_Size.
```
To:
```
1. WHEN the mouse enters the window area and remains for the duration of the Restore_Dwell_Delay (2000ms), THE Window_Manager SHALL resize the window to the Saved_Size.
```

- [ ] **Step 3: Add Restore_Dwell_Delay to Glossary**

Add to the Glossary section:
```markdown
- **Restore_Dwell_Delay**: 鼠标进入缩小窗口后，需持续停留的时间（2000ms），超过此时间才触发窗口放大恢复
```

- [ ] **Step 4: Commit requirements update**

```bash
git add .kiro/specs/window-auto-shrink/requirements.md
git commit -m "docs: add Requirement 8 (restore dwell delay) to window-auto-shrink spec"
```

---

## Summary

| Task | Description | Est. |
|------|-------------|------|
| 1 | Modify hook: add dwell timer logic | 5 min |
| 2 | Update existing unit tests | 5 min |
| 3 | Update Property 1 round-trip test | 3 min |
| 4 | Add 3 new dwell property tests | 5 min |
| 5 | Run full suite, fix issues | 3 min |
| 6 | Update requirements doc | 2 min |

Total estimated: ~23 minutes
