import { useState, useEffect, useRef } from 'preact/hooks';
import { invoke } from '@tauri-apps/api/core';
import { TitleBar } from './components/TitleBar.jsx';
import { Toast } from './components/Toast.jsx';
import { SwimLane } from './components/SwimLane.jsx';
import { CompactView } from './components/CompactView.jsx';
import { DetailPanel } from './components/DetailPanel.jsx';
import { ReadmePanel } from './components/ReadmePanel.jsx';
import { ProcessSelector } from './components/ProcessSelector.jsx';
import { useProjects } from './hooks/useProjects.js';
import { useWindowHover } from './hooks/useWindowHover.js';
import { useWindowAutoShrink } from './hooks/useWindowAutoShrink.js';
import { useRememberedSize } from './hooks/useRememberedSize.js';

export function App() {
  const { opacityState, cursorPresent } = useWindowHover();
  const [autoShrink, setAutoShrink] = useState(true);
  const { data, loading, error, selectedProject, setSelectedProject, refresh } = useProjects();

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
  const [toast, setToast] = useState(null); // { message, type } | null
  const [pendingProjectPath, setPendingProjectPath] = useState(null);
  const [notFoundToast, setNotFoundToast] = useState(null);
  const [windowWidth, setWindowWidth] = useState(window.innerWidth);

  // Process focus binding state — per-project map
  const [processBindings, setProcessBindings] = useState({});
  const currentBinding = processBindings[selectedProject] || null;
  const [showProcessSelector, setShowProcessSelector] = useState(false);
  const [processList, setProcessList] = useState([]);
  const [processListLoading, setProcessListLoading] = useState(false);
  const [processListError, setProcessListError] = useState(null);
  const [terminatedProcessName, setTerminatedProcessName] = useState(null);
  const focusBtnRef = useRef(null);

  // Load persisted process bindings on mount
  useEffect(() => {
    invoke('read_process_bindings').then(bindings => {
      setProcessBindings(bindings || {});
    }).catch(() => {});
  }, []);

  useEffect(() => {
    const handleResize = () => setWindowWidth(window.innerWidth);
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  // --- Process focus handlers ---

  const loadProcessList = async () => {
    setProcessListLoading(true);
    setProcessListError(null);
    try {
      const list = await invoke('enumerate_processes');
      setProcessList(list);
    } catch (e) {
      setProcessListError(typeof e === 'string' ? e : '枚举进程失败');
      setProcessList([]);
    } finally {
      setProcessListLoading(false);
    }
  };

  const handleFocusClick = async () => {
    if (!currentBinding) {
      // Unbound: open selector and enumerate processes
      setTerminatedProcessName(null);
      setShowProcessSelector(true);
      await loadProcessList();
    } else {
      // Bound: try to focus the window
      try {
        await invoke('focus_bound_window', {
          pid: currentBinding.pid,
          hwnd: currentBinding.hwnd,
        });
      } catch (e) {
        if (e === 'process_terminated' || (e && e.code === 'process_terminated')) {
          const name = currentBinding.processName;
          setProcessBindings(prev => {
            const next = { ...prev };
            delete next[selectedProject];
            return next;
          });
          invoke('remove_process_binding', { projectName: selectedProject }).catch(() => {});
          setTerminatedProcessName(name);
          setShowProcessSelector(true);
          await loadProcessList();
        }
      }
    }
  };

  const handleUnbind = () => {
    setProcessBindings(prev => {
      const next = { ...prev };
      delete next[selectedProject];
      return next;
    });
    invoke('remove_process_binding', { projectName: selectedProject }).catch(() => {});
  };

  const handleProcessSelect = async (info) => {
    try {
      await invoke('bind_process', { pid: info.pid, hwnd: info.hwnd });
      setProcessBindings(prev => ({
        ...prev,
        [selectedProject]: {
          pid: info.pid,
          hwnd: info.hwnd,
          processName: info.process_name,
          windowTitle: info.window_title,
        },
      }));
      invoke('write_process_binding', { projectName: selectedProject, binding: { pid: info.pid, hwnd: info.hwnd, process_name: info.process_name, window_title: info.window_title } }).catch(() => {});
      setShowProcessSelector(false);
      setTerminatedProcessName(null);
    } catch (e) {
      setProcessListError('进程已不可用，请重新选择');
      await loadProcessList();
    }
  };

  const handleDismissSelector = () => {
    setShowProcessSelector(false);
    setTerminatedProcessName(null);
  };

  // Determine layout mode
  const isCompact = windowWidth < 400;
  const hasSidePanel = windowWidth >= 600;

  // Get current project data
  const projectData = data && selectedProject ? data.projects[selectedProject] : null;
  const artifacts = projectData ? projectData.artifacts : [];
  const changeEvents = projectData ? projectData.change_events : [];
  const markdownPreviews = projectData ? projectData.markdown_previews : {};

  const projectNames = data ? Object.keys(data.projects) : [];

  // Handle deleting the currently selected project
  const handleDeleteProject = async () => {
    if (!selectedProject || !data) return;

    // Resolve the full path for the selected project via backend
    let fullPath;
    try {
      fullPath = await invoke('resolve_project_path', { projectName: selectedProject });
    } catch (_) {
      return;
    }

    // Confirmation dialog with project name
    const confirmed = window.confirm(`确认删除工程 "${selectedProject}"？\n（仅从列表移除，不删除磁盘文件）`);
    if (!confirmed) return;

    try {
      await invoke('delete_project', { path: fullPath });
      setToast({ message: '工程已删除', type: 'info' });
      setSelectedArtifact(null);
      setShowReadme(false);
      // Explicitly refresh project list to remove deleted project from UI
      await refresh();
    } catch (e) {
      const msg = typeof e === 'string' ? e : (e && e.message ? e.message : JSON.stringify(e));
      setToast({ message: msg, type: 'error' });
    }
  };

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

  // Handle adding a new project via the backend command
  const handleAddProject = async (path) => {
    try {
      const result = await invoke('add_project', { path });
      setPendingProjectPath(result.path);
      if (result.not_initialized) {
        setToast({ message: '该目录不是合规项目，需要先初始化', type: 'info' });
      }
    } catch (e) {
      const msg = typeof e === 'string' ? e : (e && e.message ? e.message : JSON.stringify(e));
      setToast({ message: msg, type: 'error' });
    }
  };

  // Auto-select newly added project after refresh
  useEffect(() => {
    if (pendingProjectPath && data) {
      // Extract the last path segment (directory name) from the pending path
      const normalized = pendingProjectPath.replace(/[\\/]+$/, '');
      const basename = normalized.split(/[\\/]/).pop();
      const match = Object.keys(data.projects).find(
        (name) => name === basename
      );
      if (match) {
        setSelectedProject(match);
        setPendingProjectPath(null);
      }
    }
  }, [data, pendingProjectPath]);

  return (
    <div class={`app-container ${opacityState}`}>
      <TitleBar
        autoShrink={autoShrink}
        onToggleAutoShrink={() => setAutoShrink(prev => !prev)}
        showReadme={showReadme}
        onToggleReadme={() => setShowReadme(prev => !prev)}
        onAddProject={handleAddProject}
        boundProcess={currentBinding}
        onFocusClick={handleFocusClick}
        onUnbind={handleUnbind}
        focusBtnRef={focusBtnRef}
      />
      {showProcessSelector && (
        <ProcessSelector
          processes={processList}
          loading={processListLoading}
          error={processListError}
          terminatedName={terminatedProcessName}
          onSelect={handleProcessSelect}
          onDismiss={handleDismissSelector}
          anchorRef={focusBtnRef}
        />
      )}
      {toast && <Toast message={toast.message} type={toast.type} onDismiss={() => setToast(null)} />}

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
          <button
            className="delete-project-btn"
            onClick={handleDeleteProject}
            title="删除工程"
            aria-label="删除工程"
          >
            🗑️
          </button>
        </div>
      )}

      {projectNames.length === 1 && (
        <div class="project-selector single-project">
          <span className="single-project-name">{projectNames[0]}</span>
          <button
            className="delete-project-btn"
            onClick={handleDeleteProject}
            title="删除工程"
            aria-label="删除工程"
          >
            🗑️
          </button>
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
