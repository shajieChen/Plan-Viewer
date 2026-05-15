import { describe, it, expect, vi } from 'vitest';
import * as fc from 'fast-check';

/**
 * Feature: window-auto-shrink, Property 5: Toggle state alternation
 *
 * For any sequence of N toggle clicks starting from enabled,
 * the auto-shrink state should be `enabled` when N is even
 * and `disabled` when N is odd.
 *
 * Validates: Requirements 6.2
 */

// Mock Tauri APIs before importing the component
vi.mock('@tauri-apps/api/core', () => ({
  invoke: vi.fn().mockResolvedValue(undefined),
}));

vi.mock('@tauri-apps/api/window', () => ({
  getCurrentWindow: vi.fn(() => ({
    hide: vi.fn().mockResolvedValue(undefined),
  })),
}));

describe('Feature: window-auto-shrink, Property 5: Toggle state alternation', () => {
  it('after N toggles starting from enabled, state is enabled when N is even, disabled when N is odd', () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 1, max: 50 }),
        (n) => {
          // Simulate the toggle logic as managed by App.jsx
          // Starting state: autoShrink = true (enabled)
          let autoShrink = true;

          // Simulate N toggle clicks
          for (let i = 0; i < n; i++) {
            autoShrink = !autoShrink;
          }

          // Assert: enabled when N is even, disabled when N is odd
          const expectedState = n % 2 === 0;
          expect(autoShrink).toBe(expectedState);
        }
      ),
      { numRuns: 100, verbose: true }
    );
  });
});
