import { useState, useEffect, useRef } from 'preact/hooks';
import { marked } from 'marked';
import { useReadmeLoader } from '../hooks/useReadmeLoader.js';
import { resolveRelativePath, classifyLink } from '../utils/pathUtils.js';
import {
  createInitialBreadcrumb,
  pushBreadcrumb,
  truncateBreadcrumb,
} from '../utils/breadcrumb.js';

/**
 * ReadmePanel — renders project README.md with markdown formatting,
 * breadcrumb navigation for internal .md links, and glassmorphism styling.
 *
 * @param {{ projectName: string, onClose: () => void }} props
 */
export function ReadmePanel({ projectName, onClose }) {
  const { content, loading, error, loadFile } = useReadmeLoader();
  const [breadcrumbs, setBreadcrumbs] = useState(createInitialBreadcrumb);
  const [navError, setNavError] = useState(null);
  const containerRef = useRef(null);

  // Load README.md on mount
  useEffect(() => {
    loadFile('README.md');
  }, []);

  // Current file path is the last breadcrumb entry
  const currentPath = breadcrumbs[breadcrumbs.length - 1].path;

  // Render markdown to HTML
  const htmlContent = content != null
    ? marked.parse(content, { breaks: true, gfm: true })
    : '';

  // Handle link clicks via event delegation
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const handleClick = async (event) => {
      const anchor = event.target.closest('a');
      if (!anchor) return;

      event.preventDefault();
      const href = anchor.getAttribute('href');
      if (!href) return;

      const linkType = classifyLink(href);

      if (linkType === 'absolute') {
        // Open in system browser
        window.open(href, '_blank');
      } else if (linkType === 'relative-md') {
        // Internal .md navigation
        const resolved = resolveRelativePath(currentPath, href);
        const success = await loadFile(resolved);
        if (success) {
          const label = resolved.split('/').pop() || resolved;
          const newBreadcrumbs = pushBreadcrumb(breadcrumbs, { path: resolved, label });
          setBreadcrumbs(newBreadcrumbs);
          setNavError(null);
        } else {
          // Failed .md navigation: show error, retain current breadcrumb
          setNavError(`无法加载: ${resolved}`);
        }
      } else {
        // Other relative links — open via /api/file endpoint
        const resolved = resolveRelativePath(currentPath, href);
        const url = `http://localhost:8000/api/file?path=${encodeURIComponent(resolved)}`;
        window.open(url, '_blank');
      }
    };

    container.addEventListener('click', handleClick);
    return () => container.removeEventListener('click', handleClick);
  }, [currentPath, breadcrumbs, loadFile]);

  // Handle breadcrumb click — navigate to that entry and truncate history
  const handleBreadcrumbClick = (index) => {
    if (index === breadcrumbs.length - 1) return; // Already there
    const entry = breadcrumbs[index];
    const truncated = truncateBreadcrumb(breadcrumbs, index);
    setBreadcrumbs(truncated);
    setNavError(null);
    loadFile(entry.path);
  };

  return (
    <div class="readme-panel" ref={containerRef}>
      {/* Breadcrumb bar */}
      <div class="readme-breadcrumb">
        {breadcrumbs.map((entry, i) => (
          <span key={`${entry.path}-${i}`} class="readme-breadcrumb-item">
            {i > 0 && <span class="readme-breadcrumb-sep">{' > '}</span>}
            {i < breadcrumbs.length - 1 ? (
              <span
                class="readme-breadcrumb-link"
                onClick={() => handleBreadcrumbClick(i)}
              >
                {entry.label}
              </span>
            ) : (
              <span class="readme-breadcrumb-current">{entry.label}</span>
            )}
          </span>
        ))}
      </div>

      {/* Content area */}
      <div class="readme-content">
        {loading && (
          <div class="readme-loading">加载中...</div>
        )}

        {!loading && (error || navError) && (
          <div class="readme-error">{navError || error}</div>
        )}

        {!loading && !error && content != null && (
          <div
            class="readme-markdown"
            dangerouslySetInnerHTML={{ __html: htmlContent }}
          />
        )}
      </div>
    </div>
  );
}
