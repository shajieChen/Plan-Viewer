import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook } from '@testing-library/preact';
import * as fc from 'fast-check';
import { useRememberedSize } from './useRememberedSize.js';

// Mock sizeStore module
vi.mock('../utils/sizeStore.js', async (importOriginal) => {
  const actual = await importOriginal();
  return {
    ...actual,
    default: {
      load: vi.fn().mockResolvedValue({}),
      save: vi.fn().mockResolvedValue(undefined),
      validate: actual.validate,
    },
    load: vi.fn().mockResolvedValue({}),
    save: vi.fn().mockResolvedValue(undefined),
  };
});

// Import the mocked module to control it
import sizeStore from '../utils/sizeStore.js';

describe('Feature: remember-window-size, Property 6: 显示器边界夹紧', () => {
  // Generators
  const largeSizeArb = fc.record({
    width: fc.integer({ min: 200, max: 7680 }),
    height: fc.integer({ min: 150, max: 4320 }),
  });

  const monitorArb = fc.record({
    availWidth: fc.integer({ min: 800, max: 3840 }),
    availHeight: fc.integer({ min: 600, max: 2160 }),
  });

  let originalScreen;

  beforeEach(() => {
    vi.clearAllMocks();
    // Save original screen descriptor
    originalScreen = Object.getOwnPropertyDescriptor(window, 'screen');
  });

  afterEach(() => {
    // Restore original screen
    if (originalScreen) {
      Object.defineProperty(window, 'screen', originalScreen);
    } else {
      delete window.screen;
    }
  });

  /**
   * **Validates: Requirements 2.2, 2.4, 2.6**
   *
   * For any Remembered_Size and monitor available area, if a dimension exceeds
   * the monitor boundary it should be clamped to that boundary.
   * After clamping: width ∈ [200, monitorWidth], height ∈ [150, monitorHeight].
   */
  it('returned initialSize is clamped within [200, monitorWidth] × [150, monitorHeight]', async () => {
    await fc.assert(
      fc.asyncProperty(
        largeSizeArb,
        monitorArb,
        fc.string({ minLength: 1, maxLength: 50 }),
        async (size, monitor, projectName) => {
          vi.clearAllMocks();

          // Mock window.screen with generated monitor values
          Object.defineProperty(window, 'screen', {
            value: {
              availWidth: monitor.availWidth,
              availHeight: monitor.availHeight,
            },
            writable: true,
            configurable: true,
          });

          // Mock sizeStore.load to return the generated size for the test project
          const sizeMap = { [projectName]: size };
          sizeStore.load.mockResolvedValue(sizeMap);

          // Render the hook
          const { result, unmount } = renderHook(() =>
            useRememberedSize({ selectedProject: projectName, savedSize: null })
          );

          // Wait for async load to complete
          await vi.waitFor(() => {
            expect(result.current.loading).toBe(false);
          });

          const { initialSize } = result.current;

          // Assert: width ∈ [200, monitorWidth]
          expect(initialSize.width).toBeGreaterThanOrEqual(200);
          expect(initialSize.width).toBeLessThanOrEqual(monitor.availWidth);

          // Assert: height ∈ [150, monitorHeight]
          expect(initialSize.height).toBeGreaterThanOrEqual(150);
          expect(initialSize.height).toBeLessThanOrEqual(monitor.availHeight);

          unmount();
        }
      ),
      { numRuns: 100 }
    );
  }, 30000);
});
