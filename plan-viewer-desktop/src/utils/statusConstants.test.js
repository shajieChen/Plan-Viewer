import { describe, it, expect } from 'vitest';
import fc from 'fast-check';
import { STATUS_COLORS, VALID_STATUSES, getStatusColor } from './statusConstants.js';

describe('statusConstants', () => {
  describe('STATUS_COLORS', () => {
    it('contains exactly 9 status entries', () => {
      expect(Object.keys(STATUS_COLORS).length).toBe(9);
    });

    it('maps each valid status to the correct hex color', () => {
      expect(STATUS_COLORS.draft).toBe('#6b7280');
      expect(STATUS_COLORS.reviewed).toBe('#3b82f6');
      expect(STATUS_COLORS.approved).toBe('#6366f1');
      expect(STATUS_COLORS.ready).toBe('#10b981');
      expect(STATUS_COLORS.blocked).toBe('#ef4444');
      expect(STATUS_COLORS.needs_update).toBe('#f59e0b');
      expect(STATUS_COLORS.invalidated).toBe('#991b1b');
      expect(STATUS_COLORS.deprecated).toBe('#78716c');
      expect(STATUS_COLORS.archived).toBe('#d1d5db');
    });

    it('all color values are valid hex color strings', () => {
      for (const color of Object.values(STATUS_COLORS)) {
        expect(color).toMatch(/^#[0-9a-f]{6}$/);
      }
    });
  });

  describe('VALID_STATUSES', () => {
    it('contains exactly 9 status strings', () => {
      expect(VALID_STATUSES.length).toBe(9);
    });

    it('contains all expected statuses', () => {
      const expected = [
        'draft', 'reviewed', 'approved', 'ready', 'blocked',
        'needs_update', 'invalidated', 'deprecated', 'archived',
      ];
      expect(VALID_STATUSES).toEqual(expected);
    });

    it('every entry in VALID_STATUSES has a corresponding STATUS_COLORS entry', () => {
      for (const status of VALID_STATUSES) {
        expect(STATUS_COLORS[status]).toBeDefined();
      }
    });
  });

  describe('getStatusColor', () => {
    it('returns the correct color for each valid status', () => {
      for (const status of VALID_STATUSES) {
        expect(getStatusColor(status)).toBe(STATUS_COLORS[status]);
      }
    });

    it('returns draft color for undefined/null/empty input', () => {
      expect(getStatusColor(undefined)).toBe('#6b7280');
      expect(getStatusColor(null)).toBe('#6b7280');
      expect(getStatusColor('')).toBe('#6b7280');
    });

    /**
     * Feature: status-change-interaction, Property 6: Unknown status color defaults to draft
     *
     * For any status string that is not one of the 9 defined valid status values,
     * the color lookup function SHALL return the draft color (#6b7280).
     *
     * Validates: Requirements 4.3
     */
    it('returns draft color (#6b7280) for any unknown status string', () => {
      fc.assert(
        fc.property(
          fc.string({ minLength: 1, maxLength: 30 }).filter(
            (s) => !VALID_STATUSES.includes(s)
          ),
          (unknownStatus) => {
            expect(getStatusColor(unknownStatus)).toBe('#6b7280');
          }
        ),
        { numRuns: 100 }
      );
    });
  });
});
