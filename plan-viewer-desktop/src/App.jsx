import { useState, useEffect } from 'preact/hooks';
import { TitleBar } from './components/TitleBar.jsx';
import { SwimLane } from './components/SwimLane.jsx';
import { CompactView } from './components/CompactView.jsx';
import { DetailPanel } from './components/DetailPanel.jsx';
import { ReadmePanel } from './components/ReadmePanel.jsx';
import { useProjects } from './hooks/useProjects.js';
import { useWindowHover } from './hooks/useWindowHover.js';
import { useWindowAutoShrink } from './hooks/useWindowAutoShrink.js';
import { useRememberedSize } from './hooks/useRememberedSize.js';

export function App() {
  const { opacityState, cursorPresent } = useWindowHover();
  const [autoShrink, setAutoShrink] = useState(true);
  const { data, loading, error, selectedProject, setSelectedProject } = useProjects();

  // Circular dependency resolution between useRememberedSize and useWindowAutoShrink:
  // - useRememberedSize needs savedSize for persistence
  // - useWindowAutoShrink needs a SHRINK TARGET (small size, ~400×300)
  // The two hooks share `savedSize` so user resize gets remembered, but the
  // shrink target must NOT be the remembered (potentially large) size or
  // performShrink's `currentSize <= initialSize` short-circuit kills shrink
  // entirely. Hardcode the small target here.
  const SHRINK_TARGET = { width: 400, height: 300 };
  const [currentSavedSize, setCurrentSavedSize] = useState(null);
  const { initialSize: rememberedInitialSize } = useRememberedSize({ selectedProject, savedSize: currentSavedSize });
  // rememberedInitialSize is read for size persistence/startup but is NOT
  // passed as the shrink target.
  void rememberedInitialSize;
  const { savedSize } = useWindowAutoShrink({
    cursorPresent,
    enabled: autoShrink,
    initialSize: SHRINK_TARGET,
  });

  // Feed savedSize from useWindowAutoShrink back to useRememberedSize
  useEffect(() => {
    setCurrentSavedSize(savedSize);
  }, [savedSize]);
  const [showReadme, setShowReadme] = useState(false);
  const [selectedArtifact, setSelectedArtifact] = useState(null);
  const [highlightedId, setHighlightedId] = useState(null);
  const [notFoundToast, setNotFoundToast] = useState(null);
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

  // Handle dependency navigation
  const handleNavigateDep = (depId) => {
    if (isCompact) return; // SwimLane not rendered in compact mode
    const found = artifacts.find((a) => a.id === depId);
    if (found) {
      setHighlightedId(depId);
      setTimeout(() => setHighlightedId(null), 1000);
    } else {
      setNotFoundToast(`未找到: ${depId}`);
      setTimeout(() => setNotFoundToast(null), 1500);
    }
  };

  return (
    <div class={`app-container ${opacityState}`}>
      <TitleBar
        autoShrink={autoShrink}
        onToggleAutoShrink={() => setAutoShrink(prev => !prev)}
        showReadme={showReadme}
        onToggleReadme={() => setShowReadme(prev => !prev)}
      />

      {/* Project selector */}
      {projectNames.length > 1 && (
        <div class="project-selector">
          <select
            value={selectedProject || ''}
            onChange={(e) => {
              setSelectedProject(e.target.value);
              setSelectedArtifact(null);
              setShowReadme(false);
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
            {showReadme ? (
              <ReadmePanel projectName={selectedProject} onClose={() => setShowReadme(false)} />
            ) : (
              <>
                <div class="main-view">
                  {isCompact ? (
                    <CompactView artifacts={artifacts} />
                  ) : (
                    <SwimLane
                      artifacts={artifacts}
                      onSelectArtifact={setSelectedArtifact}
                      highlightedId={highlightedId}
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
                      onNavigateDep={handleNavigateDep}
                      projectName={selectedProject}
                    />
                    {notFoundToast && <span class="nav-toast">{notFoundToast}</span>}
                  </div>
                )}
              </>
            )}
          </>
        )}
      </div>
    </div>
  );
}
