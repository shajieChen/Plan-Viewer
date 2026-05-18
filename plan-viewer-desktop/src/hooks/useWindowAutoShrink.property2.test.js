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

describe('Feature: window-auto-shrink, Property 2: No-op shrink when at or below Initial_Size', () => {
  /**
   * **Validates: Requirements 1.2**
   *
   * Property 2: For any window with dimensions where width ≤ 400 and height ≤ 300,
   * triggering a shrink operation should not change the window size and should not
   * update Saved_Size.
   */

  const initialSize = { width: 400, height: 300 };

  beforeEach(() => {
    vi.clearAllMocks();
    mockOuterPosition.mockResolvedValue({ x: 100, y: 100 });
    mockCurrentMonitor.mockResolvedValue({ size: { width: 1920, height: 1080 } });
    mockOnResized.mockResolvedValue(() => {});
  });

  it('should not shrink or update savedSize when window is at or below Initial_Size', async () => {
    await fc.assert(
      fc.asyncProperty(
        fc.integer({ min: 1, max: 400 }),
        fc.integer({ min: 1, max: 300 }),
        async (width, height) => {
          // Configure mock to return dimensions at or below initialSize
          mockSetSize.mockClear();
          mockInnerSize.mockResolvedValue({ width, height });

          const { result, rerender } = renderHook(
            ({ cursorPresent }) =>
              useWindowAutoShrink({ cursorPresent, enabled: true, initialSize }),
            { initialProps: { cursorPresent: true } }
          );

          // Cursor leaves (shrink trigger)
          rerender({ cursorPresent: false });

          // Wait for async operations to settle
          // The hook reads innerSize() then checks the condition and returns early
          await vi.waitFor(() => {
            // innerSize should have been called (hook reads current size)
            expect(mockInnerSize).toHaveBeenCalled();
          });

          // Assert: setSize was NOT called (no shrink performed)
          expect(mockSetSize).not.toHaveBeenCalled();

          // Assert: savedSize remains null (not updated)
          expect(result.current.savedSize).toBeNull();

          // Assert: isShrunk remains false
          expect(result.current.isShrunk).toBe(false);
        }
      ),
      { numRuns: 100 }
    );
  }, 30000);
});
