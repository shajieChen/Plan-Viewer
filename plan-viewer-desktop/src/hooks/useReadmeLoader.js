import { useState, useCallback, useRef } from 'preact/hooks';

/**
 * Hook to load file content from the dashboard server's /api/file endpoint.
 * Returns { content, loading, error, loadFile }
 *
 * - loadFile(relativePath) fetches from http://localhost:8000/api/file?path=<relativePath>
 * - Uses AbortController with 10-second timeout
 * - Sets error to "未找到 README.md" on 404
 * - Sets error to "加载失败，请确认服务器运行中" on network error or timeout
 * - Sets content to empty string (no error) when file exists but is empty
 */
export function useReadmeLoader() {
  const [content, setContent] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const abortControllerRef = useRef(null);

  const loadFile = useCallback(async (relativePath) => {
    // Abort any previous in-flight request
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }

    const controller = new AbortController();
    abortControllerRef.current = controller;

    // Set up 10-second timeout
    const timeoutId = setTimeout(() => {
      controller.abort();
    }, 10000);

    setLoading(true);
    setError(null);

    try {
      const url = `http://localhost:8000/api/file?path=${encodeURIComponent(relativePath)}`;
      const response = await fetch(url, { signal: controller.signal });

      if (response.status === 404) {
        setContent(null);
        setError('未找到 README.md');
        return false;
      }

      if (!response.ok) {
        setContent(null);
        setError('加载失败，请确认服务器运行中');
        return false;
      }

      const text = await response.text();
      setContent(text);
      setError(null);
      return true;
    } catch (err) {
      // Network error or abort (timeout)
      setContent(null);
      setError('加载失败，请确认服务器运行中');
      return false;
    } finally {
      clearTimeout(timeoutId);
      setLoading(false);
    }
  }, []);

  return { content, loading, error, loadFile };
}
