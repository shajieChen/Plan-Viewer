import { useEffect, useRef } from 'preact/hooks';

/**
 * SwimLane view: CSS Grid layout with one column per Phase group.
 * Each artifact is a colored card in its phase column.
 */
export function SwimLane({ artifacts, onSelectArtifact, highlightedId }) {
  const cardRefs = useRef({});

  // Scroll to highlighted card
  useEffect(() => {
    if (highlightedId && cardRefs.current[highlightedId]) {
      cardRefs.current[highlightedId].scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  }, [highlightedId]);
  // Group artifacts by their derived group
  const groups = {};
  for (const artifact of artifacts) {
    const group = artifact.group || 'Other';
    if (!groups[group]) groups[group] = [];
    groups[group].push(artifact);
  }

  // Dynamically derive column order from data, sorted:
  // Phase1..N first (numeric), then alphabetical, "Other" last
  const allGroups = Object.keys(groups);
  const phaseRegex = /^Phase(\d+)$/i;
  const phases = [];
  const others = [];
  let hasOther = false;

  allGroups.forEach(g => {
    const match = g.match(phaseRegex);
    if (match) {
      phases.push({ name: g, num: parseInt(match[1]) });
    } else if (g === 'Other') {
      hasOther = true;
    } else {
      others.push(g);
    }
  });

  phases.sort((a, b) => a.num - b.num);
  others.sort((a, b) => a.localeCompare(b));

  const activeColumns = [
    ...phases.map(p => p.name),
    ...others,
  ];
  if (hasOther) activeColumns.push('Other');

  if (activeColumns.length === 0) {
    return <div class="swimlane-empty">No artifacts found</div>;
  }

  return (
    <div class="swimlane" style={{ gridTemplateColumns: `repeat(${activeColumns.length}, 1fr)` }}>
      {activeColumns.map((col) => (
        <div class="swimlane-column" key={col}>
          <div class="swimlane-header">{col}</div>
          <div class="swimlane-cards">
            {groups[col].map((artifact) => (
              <div
                class={`swimlane-card status-${artifact.status}${highlightedId === artifact.id ? ' swimlane-card--highlight' : ''}`}
                key={artifact.id}
                data-artifact-id={artifact.id}
                ref={(el) => { if (el) cardRefs.current[artifact.id] = el; }}
                onClick={() => onSelectArtifact(artifact)}
                title={`${artifact.id} (${artifact.status})`}
              >
                <span class="card-id">{artifact.id}</span>
                <span class="card-type">{artifact.type}</span>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
