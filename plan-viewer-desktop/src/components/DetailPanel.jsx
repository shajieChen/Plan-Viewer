import { useMemo, useState, useEffect } from 'preact/hooks';
import { marked } from 'marked';
import { STATUS_COLORS, VALID_STATUSES, getStatusColor } from '../utils/statusConstants.js';

/**
 * DetailPanel: shows artifact details when a swim-lane card is clicked.
 */
export function DetailPanel({ artifact, changeEvents, markdownPreview, onClose, onNavigateDep, projectName }) {
  // Status selector state
  const [localStatus, setLocalStatus] = useState(artifact ? artifact.status : 'draft');
  const [updating, setUpdating] = useState(false);
  const [error, setError] = useState(null);

  // Sync localStatus when the artifact prop changes (e.g. after watcher refresh)
  useEffect(() => {
    if (artifact) {
      setLocalStatus(artifact.status);
      setError(null);
    }
  }, [artifact && artifact.id, artifact && artifact.status]);

  // Status change handler with Tauri IPC invocation
  const handleStatusChange = async (e) => {
    const newStatus = e.target.value;
    const previousStatus = localStatus;

    // Optimistic update
    setLocalStatus(newStatus);
    setUpdating(true);
    setError(null);

    try {
      const timeoutPromise = new Promise((_, reject) =>
        setTimeout(() => reject(new Error('Request timed out')), 10000)
      );

      const invokePromise = window.__TAURI__.core.invoke('update_artifact_status', {
        project_name: projectName,
        artifact_id: artifact.id,
        new_status: newStatus,
      });

      await Promise.race([invokePromise, timeoutPromise]);
      // Success - localStatus already set optimistically
      setUpdating(false);
    } catch (err) {
      // Revert on failure
      setLocalStatus(previousStatus);
      setUpdating(false);
      const errorMsg = err instanceof Error ? err.message : String(err);
      setError(errorMsg);

      // Auto-clear error after 5 seconds
      setTimeout(() => setError(null), 5000);
    }
  };

  if (!artifact) return null;

  // Filter change events related to this artifact
  const relatedEvents = useMemo(() => {
    if (!changeEvents) return [];
    return changeEvents
      .filter((e) => e.affected && e.affected.includes(artifact.id))
      .slice(0, 5);
  }, [changeEvents, artifact.id]);

  // Render markdown excerpt
  const excerptHtml = useMemo(() => {
    if (!markdownPreview || !markdownPreview.excerpt) return '';
    return marked.parse(markdownPreview.excerpt, { breaks: true });
  }, [markdownPreview]);

  return (
    <div class="detail-panel">
      <div class="detail-header">
        <h3 class="detail-title">{artifact.id}</h3>
        <button class="detail-close" onClick={onClose}>✕</button>
      </div>

      <div class="detail-meta">
        <select
          value={localStatus}
          disabled={updating}
          style={{
            backgroundColor: getStatusColor(localStatus),
            color: '#ffffff',
            opacity: updating ? 0.5 : 1,
          }}
          class={`detail-badge status-${localStatus}`}
          onChange={handleStatusChange}
        >
          {VALID_STATUSES.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
        {error && <span class="status-error" style={{ color: '#ef4444', fontSize: '0.75rem', marginLeft: '0.5rem' }}>{error}</span>}
        <span class="detail-type">{artifact.type}</span>
      </div>

      {artifact.depends_on && artifact.depends_on.length > 0 && (
        <div class="detail-section">
          <h4>Dependencies</h4>
          <ul class="detail-deps">
            {artifact.depends_on.map((dep, i) => {
              const depId = typeof dep === 'string' ? dep : (dep && dep.id) || JSON.stringify(dep);
              return (
                <li key={i}>
                  <a
                    class="dep-link"
                    onClick={(e) => { e.preventDefault(); onNavigateDep && onNavigateDep(depId); }}
                  >
                    {depId}
                  </a>
                </li>
              );
            })}
          </ul>
        </div>
      )}

      {relatedEvents.length > 0 && (
        <div class="detail-section">
          <h4>Recent Changes</h4>
          <ul class="detail-events">
            {relatedEvents.map((ev) => (
              <li key={ev.id}>
                <span class="event-time">{ev.time}</span>
                <span class="event-summary">{ev.summary}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {markdownPreview && markdownPreview.excerpt && (
        <div class="detail-section">
          <h4>{markdownPreview.title}</h4>
          <div class="detail-markdown" dangerouslySetInnerHTML={{ __html: excerptHtml }} />
        </div>
      )}
    </div>
  );
}
