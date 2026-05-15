import { useMemo } from 'preact/hooks';
import { marked } from 'marked';

/**
 * DetailPanel: shows artifact details when a swim-lane card is clicked.
 */
export function DetailPanel({ artifact, changeEvents, markdownPreview, onClose }) {
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
        <span class={`detail-badge status-${artifact.status}`}>{artifact.status}</span>
        <span class="detail-type">{artifact.type}</span>
      </div>

      {artifact.depends_on && artifact.depends_on.length > 0 && (
        <div class="detail-section">
          <h4>Dependencies</h4>
          <ul class="detail-deps">
            {artifact.depends_on.map((dep, i) => (
              <li key={i}>{typeof dep === 'string' ? dep : (dep && dep.id) || JSON.stringify(dep)}</li>
            ))}
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
