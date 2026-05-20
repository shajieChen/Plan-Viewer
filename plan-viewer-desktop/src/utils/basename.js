/**
 * Extract the last path segment (basename) from a file path,
 * ignoring any trailing path separators.
 *
 * @param {string} path - The file path to extract the basename from
 * @returns {string} The last segment of the path
 */
export function getBasename(path) {
  return path.replace(/[\\/]+$/, '').split(/[\\/]/).pop();
}
