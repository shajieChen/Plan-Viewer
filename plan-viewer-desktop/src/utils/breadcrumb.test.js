import { describe, it, expect } from 'vitest';
import fc from 'fast-check';
import {
  createInitialBreadcrumb,
  pushBreadcrumb,
  truncateBreadcrumb,
  resetBreadcrumb
} from './breadcrumb.js';

/**
 * Feature: readme-guide-button, Property 6: Breadcrumb depth invariant
 *
 * For any sequence of internal .md link navigations of arbitrary length,
 * the breadcrumb array length SHALL never exceed 10 entries.
 *
 * Validates: Requirements 4.5
 */
describe('Property 6: Breadcrumb depth invariant', () => {
  it('breadcrumb length never exceeds 10 after any sequence of push operations', () => {
    fc.assert(
      fc.property(
        fc.array(
          fc.record({
            path: fc.stringMatching(/^[a-z][a-z0-9/]*\.md$/),
            label: fc.stringMatching(/^[a-z][a-z0-9/]*\.md$/)
          }),
          { minLength: 1, maxLength: 50 }
        ),
        (entries) => {
          let breadcrumbs = createInitialBreadcrumb();

          for (const entry of entries) {
            breadcrumbs = pushBreadcrumb(breadcrumbs, entry);
            expect(breadcrumbs.length).toBeLessThanOrEqual(10);
          }
        }
      ),
      { numRuns: 100 }
    );
  });
});

/**
 * Feature: readme-guide-button, Property 7: Breadcrumb truncation on click
 *
 * For any breadcrumb array of length N and any valid click index I (where 0 ≤ I < N),
 * clicking the breadcrumb at index I SHALL produce a new breadcrumb array of length I + 1,
 * containing exactly the same entries from index 0 through I (inclusive) in the same order.
 *
 * Validates: Requirements 4.6
 */
describe('Property 7: Breadcrumb truncation on click', () => {
  it('truncating at index I produces array of length I+1 with same entries 0..I', () => {
    fc.assert(
      fc.property(
        fc.array(
          fc.record({
            path: fc.stringMatching(/^[a-z][a-z0-9/]*\.md$/),
            label: fc.stringMatching(/^[a-z][a-z0-9/]*\.md$/)
          }),
          { minLength: 1, maxLength: 10 }
        ),
        (entries) => {
          // Build a breadcrumb array from the generated entries
          const breadcrumbs = [createInitialBreadcrumb()[0], ...entries].slice(0, 10);

          // Pick a random valid index
          fc.assert(
            fc.property(
              fc.integer({ min: 0, max: breadcrumbs.length - 1 }),
              (clickIndex) => {
                const result = truncateBreadcrumb(breadcrumbs, clickIndex);

                // Length must be clickIndex + 1
                expect(result.length).toBe(clickIndex + 1);

                // Each entry 0..clickIndex must match exactly
                for (let i = 0; i <= clickIndex; i++) {
                  expect(result[i]).toEqual(breadcrumbs[i]);
                }
              }
            ),
            { numRuns: 20 }
          );
        }
      ),
      { numRuns: 100 }
    );
  });
});

/**
 * Feature: readme-guide-button, Property 8: Panel close resets navigation state
 *
 * For any sequence of navigations that produces a non-empty breadcrumb array,
 * closing the README panel (resetBreadcrumb) SHALL reset the breadcrumb array
 * to its initial state (single entry: root README.md).
 *
 * Validates: Requirements 5.4
 */
describe('Property 8: Panel close resets navigation state', () => {
  it('resetBreadcrumb always returns initial state after any navigation sequence', () => {
    fc.assert(
      fc.property(
        fc.array(
          fc.record({
            path: fc.stringMatching(/^[a-z][a-z0-9/]*\.md$/),
            label: fc.stringMatching(/^[a-z][a-z0-9/]*\.md$/)
          }),
          { minLength: 1, maxLength: 50 }
        ),
        (entries) => {
          // Simulate a navigation sequence
          let breadcrumbs = createInitialBreadcrumb();
          for (const entry of entries) {
            breadcrumbs = pushBreadcrumb(breadcrumbs, entry);
          }

          // After any sequence of navigations, reset should return initial state
          const resetResult = resetBreadcrumb();
          const initialState = createInitialBreadcrumb();

          expect(resetResult).toEqual(initialState);
          expect(resetResult.length).toBe(1);
          expect(resetResult[0]).toEqual({ path: 'README.md', label: 'README.md' });
        }
      ),
      { numRuns: 100 }
    );
  });
});
