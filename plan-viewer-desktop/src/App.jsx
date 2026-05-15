import { useState, useEffect } from 'preact/hooks';
import { TitleBar } from './components/TitleBar.jsx';
import { SwimLane } from './components/SwimLane.jsx';
import { CompactView } from './components/CompactView.jsx';
import { DetailPanel } from './components/DetailPanel.jsx';
import { useProjects } from './hooks/useProjects.js';
import { useWindowHover } from './hooks/useWindowHover.js';
import { useWindowAutoShrink } from './hooks/useWindowAutoShrink.js';

export function App() {
  const hoverState = useWindowHover();
  const [autoShrink, setAutoShrink] = useState(true);
  const { savedSize, isShrunk } = useWindowAutoShrink({
    hoverState,
    enabled: autoShrink,
    initialSize: { width: 400, height: 300 },
  });
  const { data, loading, error, selectedProject, setSelectedProject } = useProjects();
  const [selectedArtifact, setSelectedArtifact] = useState(null);
  const [windowWidth, setWindowWidth] = useState(window.innerWidth);

  useEffect(() => {
    const handleResize = () => setWindowWidth(window.innerWidth);
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  // Determine layout mode
  const isCompact = windowWidth < 400;
  const hasSidePanel = windowWidth >= 600;

  // Get current project data
  const projectData = data && selectedProject ? data.projects[selectedProject] : null;
  const artifacts = projectData ? projectData.artifacts : [];
  const changeEvents = projectData ? projectData.change_events : [];
  const markdownPreviews = projectData ? projectData.markdown_previews : {};

  const projectNames = data ? Object.keys(data.projects) : [];

  return (
    <div class={`app-container ${hoverState}`}>
      <TitleBar autoShrink={autoShrink} onToggleAutoShrink={() => setAutoShrink(prev => !prev)} />

      {/* Project selector */}
      {projectNames.length > 1 && (
        <div class="project-selector">
          <select
            value={selectedProject || ''}
            onChange={(e) => {
              setSelectedProject(e.target.value);
              setSelectedArtifact(null);
            }}
          >
            {projectNames.map((name) => (
              <option key={name} value={name}>{name}</option>
            ))}
          </select>
        </div>
      )}

      <div class={`content ${hasSidePanel && selectedArtifact ? 'with-side-panel' : ''}`}>
        {loading && <div class="center-message">Loading...</div>}
        {error && <div class="center-message error-message">{error}</div>}

        {!loading && !error && artifacts.length === 0 && (
          <div class="center-message">
            <p>No projects configured.</p>
            <p style={{ fontSize: '11px', opacity: 0.6, marginTop: '4px' }}>
              Add projects via the browser dashboard or edit projects.json
            </p>
          </div>
        )}

        {!loading && !error && artifacts.length > 0 && (
          <>
            <div class="main-view">
              {isCompact ? (
                <CompactView artifacts={artifacts} />
              ) : (
                <SwimLane
                  artifacts={artifacts}
                  onSelectArtifact={setSelectedArtifact}
                />
              )}
            </div>

            {selectedArtifact && !isCompact && (
              <div class={`detail-container ${hasSidePanel ? 'side' : 'bottom'}`}>
                <DetailPanel
                  artifact={selectedArtifact}
                  changeEvents={changeEvents}
                  markdownPreview={markdownPreviews[selectedArtifact.id]}
                  onClose={() => setSelectedArtifact(null)}
                />
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
