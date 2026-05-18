import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook } from '@testing-library/preact';
import * as fc from 'fast-check';
import { useWindowAutoShrink } from './useWindowAutoShrink.js';

// Mock Tauri window API
const mockSetSize = vi.fn().mockResolvedValue(undefined);
const mockInnerSize = vi.fn().mockResolvedValue({ width: 800, height: 600 });
const mockOuterPosition = vi.fn().mockResolvedValue({ x: 100, y: 100 });
const mockOnResized = vi.fn().mockResolvedValue(() => {});
const mockCurrentMonitor = vi.fn().mockResolvedValue({
  size: { width: 1920, height: 1080 },
});

vi.mock('@tauri-apps/api/window', () => ({
  getCurrentWindow: () => ({
    setSize: mockSetSize,
    innerSize: mockInnerSize,
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

describe('Feature: window-auto-shrink, Property 6: Disabled auto-shrink prevents shrink', () => {
  /**
   * **Validates: Requirements 6.3**
   *
   * Property 6: For any window size with auto-shrink disabled, when the mouse leaves
   * and the delay elapses (active → idle transition), the window size should remain
   * unchanged (no shrink operation performed).
   */

  const initialSize = { width: 400, height: 300 };

  beforeEach(() => {
    vi.clearAllMocks();
    mockOuterPosition.mockResolvedValue({ x: 100, y: 100 });
    mockCurrentMonitor.mockResolvedValue({ size: { width: 1920, height: 1080 } });
    mockOnResized.mockResolvedValue(() => {});
  });

  it('should not shrink window when auto-shrink is disabled, for any window size', async () => {
    await fc.assert(
      fc.asyncProperty(
        fc.integer({ min: 401, max: 3000 }),
        fc.integer({ min: 301, max: 2000 }),
        async (width, height) => {
          // Configure mock to return the generated dimensions (larger than initialSize)
          mockSetSize.mockClear();
          mockInnerSize.mockResolvedValue({ width, height });

          const { result, rerender } = renderHook(
            ({ cursorPresent }) =>
              useWindowAutoShrink({ cursorPresent, enabled: false, initialSize }),
            { initialProps: { cursorPresent: true } }
          );

          // Cursor leaves (simulates mouse leaving the window)
          rerender({ cursorPresent: false });

          // Give time for any async operations to settle
          await new Promise((r) => setTimeout(r, 50));

          // Assert: setSize was NOT called (no shrink operation performed)
          expect(mockSetSize).not.toHaveBeenCalled();

          // Assert: savedSize remains null (no size was saved)
          expect(result.current.savedSize).toBeNull();

          // Assert: isShrunk remains false
          expect(result.current.isShrunk).toBe(false);
        }
      ),
      { numRuns: 100 }
    );
  }, 30000);
});
