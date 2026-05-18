import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/preact';
import * as fc from 'fast-check';
import { useWindowAutoShrink } from './useWindowAutoShrink.js';

// Mock Tauri window API
const mockSetSize = vi.fn().mockResolvedValue(undefined);
const mockInnerSize = vi.fn().mockResolvedValue({ width: 800, height: 600 });
const mockScaleFactor = vi.fn().mockResolvedValue(1);
const mockOuterPosition = vi.fn().mockResolvedValue({ x: 100, y: 100 });
const mockOnResized = vi.fn().mockResolvedValue(() => {});
const mockCurrentMonitor = vi.fn().mockResolvedValue({
  size: { width: 1920, height: 1080 },
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

describe('Feature: window-auto-shrink, Property 3: Timer cancellation on re-entry', () => {
  /**
   * **Validates: Requirements 3.2**
   *
   * Property 3: For any re-entry time t where 0 < t < 1500ms after mouse-leave,
   * the shrink operation should not execute and the window should remain at its
   * current size.
   *
   * Since the 1500ms delay is managed by useWindowHover (which provides hoverState),
   * timer cancellation means hoverState never transitions to 'idle' — it stays 'active'.
   * From useWindowAutoShrink's perspective, no active → idle transition occurs,
   * so no shrink should happen regardless of window size or re-entry timing.
   */

  const initialSize = { width: 400, height: 300 };

  beforeEach(() => {
    vi.clearAllMocks();
    mockOuterPosition.mockResolvedValue({ x: 100, y: 100 });
    mockCurrentMonitor.mockResolvedValue({ size: { width: 1920, height: 1080 } });
    mockOnResized.mockResolvedValue(() => {});
  });

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
});
