import { describe, it, expect } from 'vitest';
import fc from 'fast-check';
import { getBasename } from './basename.js';

describe('Feature: delete-project-button, Property 6: Basename extraction ignores trailing separators', () => {
  /**
   * Validates: Requirements 2.2
   *
   * For any file path string, extracting the basename by splitting on path
   * separators and taking the last non-empty segment produces the same result
   * regardless of trailing separator presence (0–5 trailing `/` or `\`).
   */
  it('getBasename produces the same result regardless of trailing separator count', () => {
    // Generate a random alphanumeric segment (the "basename" part)
    const segmentArb = fc.string({ minLength: 1, maxLength: 20, unit: fc.constantFrom(
      ...'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-.'
    ) });

    // Generate a base path prefix (e.g., "C:\Users\test" or "/home/user")
    const prefixArb = fc.constantFrom(
      'C:\\Users\\test',
      '/home/user/projects',
      'D:\\Work',
      '/var/data',
      'relative/path'
    );

    // Generate a separator to join prefix and segment
    const sepArb = fc.constantFrom('/', '\\');

    // Generate 0–5 trailing separators (each randomly `/` or `\`)
    const trailingSepsArb = fc.array(fc.constantFrom('/', '\\'), { minLength: 0, maxLength: 5 });

    fc.assert(
      fc.property(prefixArb, sepArb, segmentArb, trailingSepsArb, (prefix, sep, segment, trailingSeps) => {
        const basePath = prefix + sep + segment;
        const pathWithTrailing = basePath + trailingSeps.join('');
        const pathWithoutTrailing = basePath;

        const resultWithTrailing = getBasename(pathWithTrailing);
        const resultWithoutTrailing = getBasename(pathWithoutTrailing);

        expect(resultWithTrailing).toBe(resultWithoutTrailing);
        expect(resultWithTrailing).toBe(segment);
      }),
      { numRuns: 100 }
    );
  });
});
