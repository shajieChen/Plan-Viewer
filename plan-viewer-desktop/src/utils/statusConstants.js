/**
 * Status color mapping and validation constants.
 * Shared across components that display or interact with artifact statuses.
 */

/**
 * Background color hex values for each valid artifact status.
 * @type {Record<string, string>}
 */
export const STATUS_COLORS = {
  draft: '#6b7280',
  reviewed: '#3b82f6',
  approved: '#6366f1',
  ready: '#10b981',
  blocked: '#ef4444',
  needs_update: '#f59e0b',
  invalidated: '#991b1b',
  deprecated: '#78716c',
  archived: '#d1d5db',
};

/**
 * All 9 valid artifact status strings.
 * @type {string[]}
 */
export const VALID_STATUSES = [
  'draft',
  'reviewed',
  'approved',
  'ready',
  'blocked',
  'needs_update',
  'invalidated',
  'deprecated',
  'archived',
];

/**
 * Default color used when a status value is unknown or invalid.
 * @type {string}
 */
const DEFAULT_STATUS_COLOR = '#6b7280';

/**
 * Get the background color for a given status value.
 * Returns the draft color (#6b7280) for unknown or invalid statuses.
 * @param {string} status - The status value to look up
 * @returns {string} Hex color string
 */
export function getStatusColor(status) {
  if (status && Object.hasOwn(STATUS_COLORS, status)) {
    return STATUS_COLORS[status];
  }
  return DEFAULT_STATUS_COLOR;
}
