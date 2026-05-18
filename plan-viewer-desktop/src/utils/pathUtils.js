/**
 * Path resolution and link classification utilities for README panel navigation.
 */

/**
 * Resolves a relative path against the directory of the current file.
 * Normalizes `.` and `..` segments and uses forward slashes.
 * The result never escapes above the project root.
 *
 * @param {string} currentFilePath - The path of the currently displayed file (relative to project root)
 * @param {string} relativePath - The relative path to resolve (may contain . and .. segments)
 * @returns {string} Resolved path relative to project root, normalized with forward slashes
 */
export function resolveRelativePath(currentFilePath, relativePath) {
  // Normalize separators to forward slashes
  const normalized = currentFilePath.replace(/\\/g, '/');
  const rel = relativePath.replace(/\\/g, '/');

  // Get the directory of the current file
  const lastSlash = normalized.lastIndexOf('/');
  const dir = lastSlash >= 0 ? normalized.substring(0, lastSlash) : '';

  // Combine directory with relative path
  const combined = dir ? `${dir}/${rel}` : rel;

  // Split into segments and resolve . and ..
  const segments = combined.split('/');
  const resolved = [];

  for (const segment of segments) {
    if (segment === '' || segment === '.') {
      // Skip empty segments and current-directory references
      continue;
    } else if (segment === '..') {
      // Go up one level, but never above project root
      if (resolved.length > 0) {
        resolved.pop();
      }
      // If resolved is empty, we're at root — silently clamp (don't escape)
    } else {
      resolved.push(segment);
    }
  }

  return resolved.join('/');
}

/**
 * Classifies a link href into one of three categories:
 * - 'absolute': starts with http:// or https://
 * - 'relative-md': relative path ending in .md (internal panel navigation)
 * - 'other-relative': all other relative paths (open via /api/file)
 *
 * @param {string} href - The href attribute value from a link
 * @returns {'absolute' | 'relative-md' | 'other-relative'} The link classification
 */
export function classifyLink(href) {
  if (href.startsWith('http://') || href.startsWith('https://')) {
    return 'absolute';
  }

  if (href.endsWith('.md')) {
    return 'relative-md';
  }

  return 'other-relative';
}
