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

// Helper: advance fake timers and flush microtasks so async performShrink/performRestore
// callbacks resolve. Pattern: fake timers must be active BEFORE the rerender that
// schedules a setTimeout, so the timer is captured by vi's fake clock.
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

describe('Feature: symmetric-dwell-delays, Property: leave dwell delays shrink', () => {
  /**
   * **Validates: leave dwell semantics**
   *
   * For any dwellTime strictly less than shrinkDelayMs (1500ms), the
   * window must NOT be shrunk yet — the shrinkTimer is still pending.
   */
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

describe('Feature: symmetric-dwell-delays, Property: shrink fires after leave dwell completes', () => {
  /**
   * **Validates: leave dwell completion → shrink**
   *
   * After cursor stays away for shrinkDelayMs, shrink fires exactly
   * once and savedSize captures the pre-shrink dimensions.
   */
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

describe('Feature: symmetric-dwell-delays, Property: re-entry cancels shrink (option A)', () => {
  /**
   * **Validates: option A — re-entry CANCELS shrinkTimer**
   *
   * If the cursor returns inside the window before the leave dwell elapses,
   * the in-flight shrinkTimer is cancelled. The window stays at its current
   * (enlarged) size — no shrink-then-restore cycle.
   */
  it('cursor returning during leave dwell cancels the pending shrink', async () => {
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
          expect(result.current.isWaitingShrink).toBe(true);

          // Re-enter at some point inside the leave dwell window
          vi.advanceTimersByTime(reentryAt);
          rerender({ cursorPresent: true });

          // shrinkTimer is now cancelled
          expect(result.current.isWaitingShrink).toBe(false);

          // Continue advancing well past when shrinkTimer would have fired
          await advanceAndFlush(5000);
          vi.useRealTimers();

          // Shrink did NOT fire — window stays enlarged
          expect(mockSetSize).not.toHaveBeenCalled();
          expect(result.current.savedSize).toBeNull();
          expect(result.current.isShrunk).toBe(false);

          unmount();
        }
      ),
      { numRuns: 50 }
    );
  }, 30000);
});

describe('Feature: symmetric-dwell-delays, Property: repeated leave resets shrink dwell', () => {
  /**
   * **Validates: shrinkTimer reset semantics on a second leave**
   *
   * When the cursor leaves, briefly re-enters, then leaves again, the
   * shrinkTimer is restarted from the second leave — not stacked.
   */
  it('a second leave restarts the shrink dwell timer', async () => {
    await fc.assert(
      fc.asyncProperty(
        fc.integer({ min: 401, max: 3000 }),
        fc.integer({ min: 301, max: 2000 }),
        fc.integer({ min: 100, max: 700 }), // first leave waits this long
        fc.integer({ min: 100, max: 700 }), // re-enter delay before second leave
        async (width, height, firstLeaveWait, reEnterPause) => {
          vi.clearAllMocks();
          mockSetSize.mockResolvedValue(undefined);
          mockInnerSize.mockResolvedValue({ width, height });

          const { rerender, unmount } = renderHook(
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
