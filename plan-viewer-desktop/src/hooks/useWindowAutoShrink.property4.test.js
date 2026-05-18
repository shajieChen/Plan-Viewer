import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/preact';
import * as fc from 'fast-check';
import { useWindowAutoShrink } from './useWindowAutoShrink.js';

// Helper: advance fake timers and flush microtasks so the async
// shrinkTimerCallback / performShrink chain can resolve.
async function advanceAndFlush(ms) {
  await act(async () => {
    vi.advanceTimersByTime(ms);
    await Promise.resolve();
    await Promise.resolve();
    await Promise.resolve();
  });
}

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
   * Property 3: While cursorPresent stays true (no leave edge fires),
   * no shrink should ever occur regardless of window size or elapsed time.
   */

  const initialSize = { width: 400, height: 300 };

  beforeEach(() => {
    vi.clearAllMocks();
    mockOuterPosition.mockResolvedValue({ x: 100, y: 100 });
    mockCurrentMonitor.mockResolvedValue({ size: { width: 1920, height: 1080 } });
    mockOnResized.mockResolvedValue(() => {});
  });

  it('should not shrink while cursorPresent stays true (no leave edge)', async () => {
    await fc.assert(
      fc.asyncProperty(
        fc.integer({ min: 401, max: 3000 }),
        fc.integer({ min: 301, max: 2000 }),
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
          // false, no leave edge ever fires, so the hook MUST NOT shrink.
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

          // Cursor leaves → shrink (after 1.5s dwell)
          vi.useFakeTimers();
          rerender({ cursorPresent: false });
          await advanceAndFlush(1500);
          vi.useRealTimers();
          await vi.waitFor(() => { expect(mockSetSize).toHaveBeenCalled(); });

          mockSetSize.mockClear();

          // Cursor returns → dwell timer starts
          vi.useFakeTimers();
          rerender({ cursorPresent: true });

          // Advance past dwell delay (1500ms)
          await act(async () => {
            vi.advanceTimersByTime(1500);
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
});
