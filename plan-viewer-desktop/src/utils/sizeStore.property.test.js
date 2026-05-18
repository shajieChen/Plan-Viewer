import { describe, it, expect, vi, beforeEach } from 'vitest';
import fc from 'fast-check';

// Mock @tauri-apps/api/core
vi.mock('@tauri-apps/api/core', () => ({
  invoke: vi.fn(),
}));

import { invoke } from '@tauri-apps/api/core';
import { validate, save, MAX_ENTRIES, MIN_WIDTH, MIN_HEIGHT, MAX_WIDTH, MAX_HEIGHT } from './sizeStore.js';

// Arbitrary for valid WindowSize
const sizeArb = fc.record({
  width: fc.integer({ min: MIN_WIDTH, max: MAX_WIDTH }),
  height: fc.integer({ min: MIN_HEIGHT, max: MAX_HEIGHT }),
});

describe('Feature: remember-window-size, Property 2: 尺寸校验正确性', () => {
  /**
   * Validates: Requirements 5.1, 5.2, 5.3
   *
   * For ANY input, validate() returns either null OR a valid {width, height}
   * object where width ∈ [200, 7680] and height ∈ [150, 4320] (both positive integers).
   */
  it('validate() always returns null or a valid {width, height} within constraints', () => {
    fc.assert(
      fc.property(fc.anything(), (input) => {
        const result = validate(input);

        if (result === null) {
          // null is always a valid return
          return true;
        }

        // If not null, must be a valid object with width and height
        expect(result).toHaveProperty('width');
        expect(result).toHaveProperty('height');
        expect(Number.isInteger(result.width)).toBe(true);
        expect(Number.isInteger(result.height)).toBe(true);
        expect(result.width).toBeGreaterThanOrEqual(MIN_WIDTH);
        expect(result.width).toBeLessThanOrEqual(MAX_WIDTH);
        expect(result.height).toBeGreaterThanOrEqual(MIN_HEIGHT);
        expect(result.height).toBeLessThanOrEqual(MAX_HEIGHT);

        return true;
      }),
      { numRuns: 100 }
    );
  });

  it('validate() returns the size object for valid inputs', () => {
    fc.assert(
      fc.property(sizeArb, (size) => {
        const result = validate(size);
        expect(result).not.toBeNull();
        expect(result.width).toBe(size.width);
        expect(result.height).toBe(size.height);
      }),
      { numRuns: 100 }
    );
  });

  it('validate() returns null for invalid inputs (non-integer, out of range, missing fields)', () => {
    // Floats
    fc.assert(
      fc.property(
        fc.double({ min: 0.1, max: 10000, noNaN: true }).filter((n) => !Number.isInteger(n)),
        fc.double({ min: 0.1, max: 10000, noNaN: true }).filter((n) => !Number.isInteger(n)),
        (w, h) => {
          const result = validate({ width: w, height: h });
          expect(result).toBeNull();
        }
      ),
      { numRuns: 100 }
    );

    // Negative numbers
    fc.assert(
      fc.property(
        fc.integer({ min: -10000, max: -1 }),
        fc.integer({ min: -10000, max: -1 }),
        (w, h) => {
          const result = validate({ width: w, height: h });
          expect(result).toBeNull();
        }
      ),
      { numRuns: 100 }
    );

    // Out of range (too large)
    fc.assert(
      fc.property(
        fc.integer({ min: MAX_WIDTH + 1, max: MAX_WIDTH + 10000 }),
        fc.integer({ min: MAX_HEIGHT + 1, max: MAX_HEIGHT + 10000 }),
        (w, h) => {
          const result = validate({ width: w, height: h });
          expect(result).toBeNull();
        }
      ),
      { numRuns: 100 }
    );

    // Out of range (too small)
    fc.assert(
      fc.property(
        fc.integer({ min: 1, max: MIN_WIDTH - 1 }),
        fc.integer({ min: 1, max: MIN_HEIGHT - 1 }),
        (w, h) => {
          const result = validate({ width: w, height: h });
          expect(result).toBeNull();
        }
      ),
      { numRuns: 100 }
    );
  });
});

describe('Feature: remember-window-size, Property 3: 存储条目数量上限', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  /**
   * **Validates: Requirements 1.3**
   *
   * For any SizeMap with 201–500 entries, after save() the data written
   * to storage should have at most 200 entries (MAX_ENTRIES).
   */
  it('save() should enforce MAX_ENTRIES limit for oversized SizeMap', async () => {
    await fc.assert(
      fc.asyncProperty(
        fc.dictionary(
          fc.string({ minLength: 1, maxLength: 50 }),
          sizeArb,
          { minKeys: 201, maxKeys: 500 }
        ),
        async (oversizedMap) => {
          let writtenData = null;

          invoke.mockImplementation(async (cmd, args) => {
            if (cmd === 'write_window_sizes') {
              writtenData = args.data;
            }
          });

          await save(oversizedMap);

          expect(writtenData).not.toBeNull();
          const parsed = JSON.parse(writtenData);
          const entryCount = Object.keys(parsed).length;
          expect(entryCount).toBeLessThanOrEqual(MAX_ENTRIES);
        }
      ),
      { numRuns: 100 }
    );
  });
});
