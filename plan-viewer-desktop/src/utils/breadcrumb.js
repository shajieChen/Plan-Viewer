/**
 * Breadcrumb state logic for README panel navigation.
 * Pure functions — no side effects or hooks.
 */

const MAX_DEPTH = 10;

/**
 * Create the initial breadcrumb state.
 * @returns {Array<{path: string, label: string}>}
 */
export function createInitialBreadcrumb() {
  return [{ path: 'README.md', label: 'README.md' }];
}

/**
 * Push a new entry onto the breadcrumb trail.
 * Enforces a max depth of 10 — drops the oldest entries (from the front) if needed.
 * @param {Array<{path: string, label: string}>} breadcrumbs - Current breadcrumb array
 * @param {{path: string, label: string}} entry - New entry to append
 * @returns {Array<{path: string, label: string}>} New breadcrumb array
 */
export function pushBreadcrumb(breadcrumbs, entry) {
  const next = [...breadcrumbs, entry];
  if (next.length > MAX_DEPTH) {
    return next.slice(next.length - MAX_DEPTH);
  }
  return next;
}

/**
 * Truncate breadcrumbs at a given index (inclusive).
 * Keeps entries from index 0 through the given index.
 * @param {Array<{path: string, label: string}>} breadcrumbs - Current breadcrumb array
 * @param {number} index - The index to truncate at (inclusive)
 * @returns {Array<{path: string, label: string}>} New breadcrumb array
 */
export function truncateBreadcrumb(breadcrumbs, index) {
  return breadcrumbs.slice(0, index + 1);
}

/**
 * Reset breadcrumb to initial state.
 * @returns {Array<{path: string, label: string}>}
 */
export function resetBreadcrumb() {
  return createInitialBreadcrumb();
}
