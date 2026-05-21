import { useState, useEffect, useRef } from 'preact/hooks';

/**
 * Filter processes by search text (case-insensitive substring match on process_name or window_title).
 * @param {Array<{process_name: string, window_title: string}>} processes
 * @param {string} search
 * @returns {Array} filtered processes
 */
export function filterProcesses(processes, search) {
  const lower = search.toLowerCase();
  return (processes || []).filter(p =>
    p.process_name.toLowerCase().includes(lower) ||
    p.window_title.toLowerCase().includes(lower)
  );
}

/**
 * Compute popup position anchored to a button, with viewport boundary detection.
 * Pure function for testability.
 *
 * @param {{ anchorRect: { top: number, bottom: number, left: number, right: number }, panelWidth: number, panelHeight: number, viewportWidth: number, viewportHeight: number }} params
 * @returns {{ top: number, left: number }}
 */
export function computePopupPosition({ anchorRect, panelWidth, panelHeight, viewportWidth, viewportHeight }) {
  // Default: position below the anchor, aligned to right edge
  let top = anchorRect.bottom + 4;
  let left = anchorRect.right - panelWidth;

  // Viewport boundary detection: adjust if overflowing
  if (left < 0) left = 4;
  if (left + panelWidth > viewportWidth) left = viewportWidth - panelWidth - 4;
  if (left < 0) left = 4;
  if (top + panelHeight > viewportHeight) {
    // Position above the anchor if not enough space below
    top = anchorRect.top - panelHeight - 4;
  }
  if (top < 0) top = 4;
  // Final clamp: ensure popup bottom doesn't exceed viewport
  if (top + panelHeight > viewportHeight) top = viewportHeight - panelHeight - 4;
  if (top < 0) top = 4;

  return { top, left };
}

/**
 * ProcessSelector — popup overlay for selecting an external process to bind.
 * Anchored to Focus_Button with viewport boundary detection.
 */
export function ProcessSelector({
  processes,        // ProcessInfo[] from backend
  loading,          // boolean
  error,            // string | null
  terminatedName,   // string | null — name of previously bound process that died
  onSelect,         // (info: ProcessInfo) => void
  onDismiss,        // () => void
  anchorRef,        // ref to Focus_Button for positioning
}) {
  const [search, setSearch] = useState('');
  const panelRef = useRef(null);

  // Filter processes by search text (case-insensitive substring match on process_name or window_title)
  const filtered = filterProcesses(processes, search);

  // Dismiss on Escape key
  useEffect(() => {
    const handleKey = (e) => {
      if (e.key === 'Escape') onDismiss();
    };
    document.addEventListener('keydown', handleKey);
    return () => document.removeEventListener('keydown', handleKey);
  }, [onDismiss]);

  // Dismiss on click outside
  useEffect(() => {
    const handleClick = (e) => {
      if (panelRef.current && !panelRef.current.contains(e.target)) {
        onDismiss();
      }
    };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [onDismiss]);

  // Position overlay anchored to Focus_Button with viewport boundary detection
  useEffect(() => {
    if (!panelRef.current || !anchorRef?.current) return;

    const anchor = anchorRef.current.getBoundingClientRect();
    const panel = panelRef.current;
    const panelRect = panel.getBoundingClientRect();
    const vw = window.innerWidth;
    const vh = window.innerHeight;

    const { top, left } = computePopupPosition({
      anchorRect: anchor,
      panelWidth: panelRect.width,
      panelHeight: panelRect.height,
      viewportWidth: vw,
      viewportHeight: vh,
    });

    panel.style.position = 'absolute';
    panel.style.top = `${top}px`;
    panel.style.left = `${left}px`;
    panel.style.right = 'auto';
  }, [anchorRef, processes, loading]);

  return (
    <div class="process-selector-overlay" ref={panelRef}>
      {terminatedName && (
        <div class="process-selector-warning">
          进程 "{terminatedName}" 已终止，请重新选择
        </div>
      )}
      <div class="process-selector-header">
        <input
          type="text"
          placeholder="搜索进程..."
          value={search}
          onInput={(e) => setSearch(e.target.value)}
          autoFocus
        />
        <button onClick={onDismiss} class="process-selector-close">✕</button>
      </div>
      <div class="process-selector-list">
        {loading && <div class="process-selector-message">枚举进程中...</div>}
        {error && <div class="process-selector-message error">{error}</div>}
        {!loading && !error && filtered.length === 0 && (
          <div class="process-selector-message">
            {search ? '无匹配进程' : '未检测到可绑定进程'}
          </div>
        )}
        {filtered.map(p => (
          <button
            key={`${p.pid}-${p.hwnd}`}
            class="process-selector-item"
            onClick={() => onSelect(p)}
          >
            <span class="process-name">{p.process_name}</span>
            <span class="process-title">{p.window_title}</span>
            <span class="process-pid">PID: {p.pid}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
