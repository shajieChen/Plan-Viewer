/**
 * CompactView: shown when window width < 400px.
 * Displays each phase as a single row with a progress bar.
 */
export function CompactView({ artifacts }) {
  const groups = {};
  for (const artifact of artifacts) {
    const group = artifact.group || 'Other';
    if (!groups[group]) groups[group] = [];
    groups[group].push(artifact);
  }

  const columnOrder = ['Phase1', 'Phase2', 'Phase3', 'Phase4', 'Phase5', 'CodeGen', 'Other'];
  const activeColumns = columnOrder.filter((col) => groups[col] && groups[col].length > 0);

  const completedStatuses = new Set(['ready', 'approved', 'archived']);

  return (
    <div class="compact-view">
      {activeColumns.map((col) => {
        const items = groups[col];
        const done = items.filter((a) => completedStatuses.has(a.status)).length;
        const total = items.length;
        const pct = total > 0 ? Math.round((done / total) * 100) : 0;

        return (
          <div class="compact-row" key={col}>
            <span class="compact-label">{col}</span>
            <div class="compact-bar">
              <div class="compact-bar-fill" style={{ width: `${pct}%` }} />
            </div>
            <span class="compact-count">{done}/{total}</span>
          </div>
        );
      })}
    </div>
  );
}
