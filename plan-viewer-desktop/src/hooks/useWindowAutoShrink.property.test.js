import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/preact';
import * as fc from 'fast-check';
import { useWindowAutoShrink } from './useWindowAutoShrink.js';

// Mock Tauri window API
const mockSetSize = vi.fn().mockResolvedValue(undefined);
const mockInnerSize = vi.fn().mockResolvedValue({ width: 800, height: 600 });
const mockOuterPosition = vi.fn().mockResolvedValue({ x: 0, y: 0 });
const mockOnResized = vi.fn().mockResolvedValue(() => {});
const mockScaleFactor = vi.fn().mockResolvedValue(1);
const mockCurrentMonitor = vi.fn().mockResolvedValue({
  size: { width: 3840, height: 2160 },
});

vi.mock('@tauri-apps/api/window', () => ({
  getCurrentWindow: () => ({
    setSize: mockSetSize,
    innerSize: mockInnerSize,
    outerPosition: mockOuterPosition,
    onResized: mockOnResized,
    scaleFactor: mockScaleFactor,
  }),
  currentMonitor: (...args) => mockCurrentMonitor(...args),
  LogicalSize: class LogicalSize {
    constructor(width, height) {
      this.width = width;
      this.height = height;
    }
  },
}));

describe('Feature: window-auto-shrink, Property 1: Shrink-then-restore round trip', () => {
  const initialSize = { width: 400, height: 300 };

  beforeEach(() => {
    vi.clearAllMocks();
    mockSetSize.mockResolvedValue(undefined);
    mockOuterPosition.mockResolvedValue({ x: 0, y: 0 });
    mockCurrentMonitor.mockResolvedValue({ size: { width: 3840, height: 2160 } });
    mockOnResized.mockResolvedValue(() => {});
  });

  /**
   * **Validates: Requirements 1.1, 2.1**
   *
   * For any window with dimensions larger than Initial_Size,
   * shrinking the window and then restoring it should produce
   * a window with the same dimensions as before the shrink.
   */
  it('should restore window to original dimensions after shrink-then-restore cycle', async () => {
    await fc.assert(
      fc.asyncProperty(
        fc.integer({ min: 401, max: 3000 }),
        fc.integer({ min: 301, max: 2000 }),
        async (width, height) => {
          // Reset mocks for each iteration
          vi.clearAllMocks();
          mockSetSize.mockResolvedValue(undefined);
          mockInnerSize.mockResolvedValue({ width, height });
          mockOuterPosition.mockResolvedValue({ x: 0, y: 0 });
          mockCurrentMonitor.mockResolvedValue({ size: { width: 3840, height: 2160 } });
          mockOnResized.mockResolvedValue(() => {});

          // Render hook with cursor present
          const { result, rerender, unmount } = renderHook(
            ({ cursorPresent }) =>
              useWindowAutoShrink({ cursorPresent, enabled: true, initialSize }),
            { initialProps: { cursorPresent: true } }
          );

          // Cursor leaves (shrink)
          rerender({ cursorPresent: false });

          // Wait for shrink to complete
          await vi.waitFor(() => {
            expect(mockSetSize).toHaveBeenCalledTimes(1);
          });

          // Verify shrink was called with initialSize
          const shrinkArg = mockSetSize.mock.calls[0][0];
          expect(shrinkArg.width).toBe(initialSize.width);
          expect(shrinkArg.height).toBe(initialSize.height);

          // Verify savedSize was stored
          expect(result.current.savedSize).toEqual({ width, height });
          expect(result.current.isShrunk).toBe(true);

          // Clear setSize mock for restore phase
          mockSetSize.mockClear();

          // Use fake timers to advance past dwell delay
          vi.useFakeTimers();
          rerender({ cursorPresent: true });
          await act(async () => {
            vi.advanceTimersByTime(2000);
            await Promise.resolve(); // flush microtasks from performRestore
            await Promise.resolve();
            await Promise.resolve();
          });
          vi.useRealTimers();

          // Then wait for async API calls to complete
          await vi.waitFor(() => {
            expect(mockSetSize).toHaveBeenCalledTimes(1);
          });

          // Verify restore was called with original dimensions
          const restoreArg = mockSetSize.mock.calls[0][0];
          expect(restoreArg.width).toBe(width);
          expect(restoreArg.height).toBe(height);
          expect(result.current.isShrunk).toBe(false);

          // Cleanup to avoid state leakage between iterations
          unmount();
        }
      ),
      { numRuns: 100 }
    );
  }, 30000); // Extended timeout for 100 async property iterations
});

describe('Feature: window-auto-shrink, Property 4: Manual resize updates Saved_Size', () => {
  const initialSize = { width: 400, height: 300 };

  beforeEach(() => {
    vi.clearAllMocks();
    mockInnerSize.mockResolvedValue({ width: 800, height: 600 });
    mockOuterPosition.mockResolvedValue({ x: 100, y: 100 });
    mockCurrentMonitor.mockResolvedValue({ size: { width: 1920, height: 1080 } });
    mockOnResized.mockResolvedValue(() => {});
  });

  /**
   * **Validates: Requirements 4.1**
   *
   * Property 4: For any sequence of manual resize events while in Active_State,
   * the Saved_Size should always equal the dimensions from the most recent resize event.
   */
  it('savedSize always equals the most recent resize dimensions after a sequence of resize events', async () => {
    await fc.assert(
      fc.asyncProperty(
        // Generate an array of 1-20 resize events with random dimensions
        fc.array(
          fc.record({
            width: fc.integer({ min: 200, max: 3000 }),
            height: fc.integer({ min: 150, max: 2000 }),
          }),
          { minLength: 1, maxLength: 20 }
        ),
        async (resizeEvents) => {
          // Capture the onResized callback
          let resizeCallback = null;
          mockOnResized.mockImplementation((cb) => {
            resizeCallback = cb;
            return Promise.resolve(() => {});
          });

          // Render hook with cursor present
          const { result, unmount } = renderHook(() =>
            useWindowAutoShrink({ cursorPresent: true, enabled: true, initialSize })
          );

          // Wait for the async setupListener to complete and capture the callback
          await vi.waitFor(() => {
            expect(resizeCallback).not.toBeNull();
          });

          // Simulate each resize event in the sequence
          for (const event of resizeEvents) {
            await act(async () => {
              resizeCallback({ payload: { width: event.width, height: event.height } });
              await Promise.resolve(); // flush scaleFactor() promise in callback
            });
          }

          // The savedSize should equal the last resize event's dimensions
          const lastEvent = resizeEvents[resizeEvents.length - 1];
          expect(result.current.savedSize).toEqual({
            width: lastEvent.width,
            height: lastEvent.height,
          });

          unmount();
        }
      ),
      { numRuns: 100 }
    );
  }, 30000);
});

describe('Feature: window-auto-shrink, Property 8: Screen boundary clamping on restore', () => {
  /**
   * **Validates: Requirements 7.3**
   *
   * For any window position near a screen edge and a Saved_Size that would extend
   * beyond the screen boundary, the restored window size should be clamped so that
   * the window fits entirely within the visible screen area.
   */

  const initialSize = { width: 400, height: 300 };

  beforeEach(() => {
    vi.clearAllMocks();
    mockOnResized.mockResolvedValue(() => {});
  });

  it('restored window fits entirely within visible screen area', async () => {
    await fc.assert(
      fc.asyncProperty(
        // Generate screen dimensions
        fc.integer({ min: 1920, max: 3840 }),
        fc.integer({ min: 1080, max: 2160 }),
        // Generate position near screen edge (will be derived from screen dims)
        fc.integer({ min: 0, max: 700 }),
        fc.integer({ min: 0, max: 500 }),
        // Generate savedSize (large enough to potentially overflow)
        fc.integer({ min: 401, max: 2000 }),
        fc.integer({ min: 301, max: 1500 }),
        async (screenWidth, screenHeight, xOffset, yOffset, savedWidth, savedHeight) => {
          // Position near screen edge: x ∈ [screenWidth - 800, screenWidth - 100]
          const posX = screenWidth - 800 + Math.round(xOffset * (700 / 700));
          // Position near screen edge: y ∈ [screenHeight - 600, screenHeight - 100]
          const posY = screenHeight - 600 + Math.round(yOffset * (500 / 500));

          // Configure mocks for this iteration
          vi.clearAllMocks();
          mockSetSize.mockResolvedValue(undefined);
          mockInnerSize.mockResolvedValue({ width: savedWidth, height: savedHeight });
          mockOuterPosition.mockResolvedValue({ x: posX, y: posY });
          mockCurrentMonitor.mockResolvedValue({
            size: { width: screenWidth, height: screenHeight },
          });
          mockOnResized.mockResolvedValue(() => {});

          // Render hook with cursor present
          const { rerender, unmount } = renderHook(
            ({ cursorPresent }) =>
              useWindowAutoShrink({ cursorPresent, enabled: true, initialSize }),
            { initialProps: { cursorPresent: true } }
          );

          // Shrink: cursor leaves (saves the current size)
          rerender({ cursorPresent: false });
          await vi.waitFor(() => {
            expect(mockSetSize).toHaveBeenCalled();
          });

          mockSetSize.mockClear();

          // Use fake timers to advance past dwell delay
          vi.useFakeTimers();
          rerender({ cursorPresent: true });
          await act(async () => {
            vi.advanceTimersByTime(2000);
            await Promise.resolve();
            await Promise.resolve();
            await Promise.resolve();
          });
          vi.useRealTimers();

          // Then wait for async API calls
          await vi.waitFor(() => {
            expect(mockSetSize).toHaveBeenCalled();
          });

          // Get the restored size from the setSize call
          const restoreCall = mockSetSize.mock.calls[0][0];
          const restoredWidth = restoreCall.width;
          const restoredHeight = restoreCall.height;

          // Assert: position.x + restoredWidth ≤ screenWidth OR restoredWidth === initialSize.width (minimum)
          const fitsWidth =
            posX + restoredWidth <= screenWidth || restoredWidth === initialSize.width;
          expect(fitsWidth).toBe(true);

          // Assert: position.y + restoredHeight ≤ screenHeight OR restoredHeight === initialSize.height (minimum)
          const fitsHeight =
            posY + restoredHeight <= screenHeight || restoredHeight === initialSize.height;
          expect(fitsHeight).toBe(true);

          unmount();
        }
      ),
      { numRuns: 100 }
    );
  }, 30000);
});

describe('Feature: window-auto-shrink, Property 7: Position preservation during resize', () => {
  /**
   * **Validates: Requirements 7.1, 7.2**
   *
   * For any window position and size, both shrink and restore operations
   * should preserve the window's top-left corner coordinates exactly.
   * Since the hook only calls setSize and never setPosition, the window's
   * top-left corner is preserved by the OS/Tauri.
   */

  const initialSize = { width: 400, height: 300 };

  beforeEach(() => {
    vi.clearAllMocks();
    mockSetSize.mockResolvedValue(undefined);
    mockOnResized.mockResolvedValue(() => {});
  });

  it('should never call setPosition during shrink and restore operations', async () => {
    await fc.assert(
      fc.asyncProperty(
        fc.integer({ min: 0, max: 1500 }),   // x position
        fc.integer({ min: 0, max: 800 }),    // y position
        fc.integer({ min: 401, max: 2000 }), // width (larger than initialSize)
        fc.integer({ min: 301, max: 1500 }), // height (larger than initialSize)
        async (x, y, width, height) => {
          // Reset mocks for each iteration
          vi.clearAllMocks();
          mockSetSize.mockResolvedValue(undefined);
          mockInnerSize.mockResolvedValue({ width, height });
          mockOuterPosition.mockResolvedValue({ x, y });
          // Use a large screen so clamping doesn't interfere
          mockCurrentMonitor.mockResolvedValue({ size: { width: 3840, height: 2160 } });
          mockOnResized.mockResolvedValue(() => {});

          // Render hook with cursor present
          const { rerender, unmount } = renderHook(
            ({ cursorPresent }) =>
              useWindowAutoShrink({ cursorPresent, enabled: true, initialSize }),
            { initialProps: { cursorPresent: true } }
          );

          // Cursor leaves (shrink)
          rerender({ cursorPresent: false });

          // Wait for shrink to complete
          await vi.waitFor(() => {
            expect(mockSetSize).toHaveBeenCalledTimes(1);
          });

          // Verify only setSize was called during shrink (Req 7.1)
          // The hook never calls setPosition - position is preserved by the OS
          const shrinkArg = mockSetSize.mock.calls[0][0];
          expect(shrinkArg.width).toBe(initialSize.width);
          expect(shrinkArg.height).toBe(initialSize.height);

          // Clear setSize mock for restore phase
          mockSetSize.mockClear();

          // Use fake timers to advance past dwell delay
          vi.useFakeTimers();
          rerender({ cursorPresent: true });
          await act(async () => {
            vi.advanceTimersByTime(2000);
            await Promise.resolve();
            await Promise.resolve();
            await Promise.resolve();
          });
          vi.useRealTimers();

          // Then wait for async API calls
          await vi.waitFor(() => {
            expect(mockSetSize).toHaveBeenCalledTimes(1);
          });

          // Verify only setSize was called during restore (Req 7.2)
          // outerPosition is READ (for clamping calculations) but never WRITTEN
          expect(mockOuterPosition).toHaveBeenCalled();

          // The critical assertion: the mock object provided by vi.mock does NOT
          // include setPosition. If the hook ever tried to call setPosition,
          // it would throw an error. Since the test passes, position is preserved.
          // Additionally, verify that setSize was the ONLY window mutation method called.
          const restoreArg = mockSetSize.mock.calls[0][0];
          expect(restoreArg).toBeDefined();
          expect(restoreArg.width).toBeGreaterThan(0);
          expect(restoreArg.height).toBeGreaterThan(0);

          unmount();
        }
      ),
      { numRuns: 100 }
    );
  }, 30000);
});

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
   * For any random dwell time t ∈ (0, 2000ms), if the mouse leaves
   * before t reaches 2000ms, the window should NOT restore.
   */
  it('window remains shrunk when mouse leaves before dwell delay completes', async () => {
    await fc.assert(
      fc.asyncProperty(
        fc.integer({ min: 401, max: 2000 }),
        fc.integer({ min: 301, max: 1500 }),
        fc.integer({ min: 1, max: 1999 }),
        async (width, height, dwellTime) => {
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

          // Shrink first
          rerender({ cursorPresent: false });
          await vi.waitFor(() => { expect(mockSetSize).toHaveBeenCalledTimes(1); });
          await vi.waitFor(() => { expect(result.current.isShrunk).toBe(true); });
          mockSetSize.mockClear();

          // Use fake timers for dwell
          vi.useFakeTimers();
          rerender({ cursorPresent: true });
          expect(result.current.isWaitingRestore).toBe(true);

          // Advance by dwellTime (< 2000ms)
          vi.advanceTimersByTime(dwellTime);

          // Leave before dwell completes
          rerender({ cursorPresent: false });

          // Advance well past 2000ms
          vi.advanceTimersByTime(5000);
          vi.useRealTimers();

          // Should NOT have restored
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

describe('Feature: restore-dwell-delay, Property: Restore triggers after full dwell', () => {
  const initialSize = { width: 400, height: 300 };

  beforeEach(() => {
    vi.clearAllMocks();
    mockSetSize.mockResolvedValue(undefined);
    mockOuterPosition.mockResolvedValue({ x: 0, y: 0 });
    mockCurrentMonitor.mockResolvedValue({ size: { width: 3840, height: 2160 } });
    mockOnResized.mockResolvedValue(() => {});
  });

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
            ({ cursorPresent }) =>
              useWindowAutoShrink({ cursorPresent, enabled: true, initialSize }),
            { initialProps: { cursorPresent: true } }
          );

          // Shrink
          rerender({ cursorPresent: false });
          await vi.waitFor(() => { expect(mockSetSize).toHaveBeenCalledTimes(1); });
          expect(result.current.isShrunk).toBe(true);
          expect(result.current.savedSize).toEqual({ width, height });
          mockSetSize.mockClear();

          // Use fake timers for dwell
          vi.useFakeTimers();
          rerender({ cursorPresent: true });
          expect(result.current.isWaitingRestore).toBe(true);

          // Advance full 2000ms
          await act(async () => {
            vi.advanceTimersByTime(2000);
            await Promise.resolve();
            await Promise.resolve();
            await Promise.resolve();
          });
          vi.useRealTimers();

          // Restore should fire
          await vi.waitFor(() => { expect(mockSetSize).toHaveBeenCalledTimes(1); });

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

describe('Feature: restore-dwell-delay, Property: Multiple rapid cycles never trigger restore', () => {
  const initialSize = { width: 400, height: 300 };

  beforeEach(() => {
    vi.clearAllMocks();
    mockSetSize.mockResolvedValue(undefined);
    mockOuterPosition.mockResolvedValue({ x: 0, y: 0 });
    mockCurrentMonitor.mockResolvedValue({ size: { width: 3840, height: 2160 } });
    mockOnResized.mockResolvedValue(() => {});
  });

  it('N rapid enter-leave cycles (each < 2s) never trigger restore', async () => {
    await fc.assert(
      fc.asyncProperty(
        fc.integer({ min: 2, max: 10 }),
        fc.integer({ min: 1, max: 1999 }),
        async (numCycles, dwellTime) => {
          vi.clearAllMocks();
          mockSetSize.mockResolvedValue(undefined);
          mockInnerSize.mockResolvedValue({ width: 800, height: 600 });
          mockOuterPosition.mockResolvedValue({ x: 0, y: 0 });
          mockCurrentMonitor.mockResolvedValue({ size: { width: 3840, height: 2160 } });
          mockOnResized.mockResolvedValue(() => {});

          const { result, rerender, unmount } = renderHook(
            ({ cursorPresent }) =>
              useWindowAutoShrink({ cursorPresent, enabled: true, initialSize }),
            { initialProps: { cursorPresent: true } }
          );

          // Shrink first
          rerender({ cursorPresent: false });
          await vi.waitFor(() => { expect(mockSetSize).toHaveBeenCalledTimes(1); });
          expect(result.current.isShrunk).toBe(true);
          mockSetSize.mockClear();

          vi.useFakeTimers();

          // Rapid enter-leave cycles
          for (let i = 0; i < numCycles; i++) {
            rerender({ cursorPresent: true });
            vi.advanceTimersByTime(dwellTime);
            rerender({ cursorPresent: false });
            vi.advanceTimersByTime(100);
          }

          // Advance well past any pending timer
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
