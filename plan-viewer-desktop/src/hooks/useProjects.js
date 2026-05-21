import { useState, useEffect, useCallback, useRef } from 'preact/hooks';
import { invoke } from '@tauri-apps/api/core';
import { listen } from '@tauri-apps/api/event';

/**
 * Hook to fetch dashboard data and listen for file-change events.
 * Returns { data, loading, error, selectedProject, setSelectedProject, refresh }
 */
export function useProjects() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedProject, setSelectedProject] = useState(null);

  // Keep a ref to the latest selectedProject so refresh() never has a stale closure
  const selectedProjectRef = useRef(selectedProject);
  useEffect(() => {
    selectedProjectRef.current = selectedProject;
  }, [selectedProject]);

  const refresh = useCallback(async () => {
    try {
      setLoading(true);
      const result = await invoke('get_dashboard_data');
      setData(result);
      setError(null);

      // Auto-select first project if none selected or current selection is gone
      const current = selectedProjectRef.current;
      if (result && result.projects) {
        const keys = Object.keys(result.projects);
        if (keys.length > 0 && (!current || !result.projects[current])) {
          setSelectedProject(keys[0]);
        }
      }
    } catch (e) {
      setError(typeof e === 'string' ? e : e.message || 'Unknown error');
    } finally {
      setLoading(false);
    }
  }, []);

  // Initial load
  useEffect(() => {
    refresh();
  }, []);

  // Listen for file-change events from Rust watcher
  useEffect(() => {
    let unlisten;
    listen('project-updated', (_event) => {
      refresh();
    }).then((fn) => {
      unlisten = fn;
    });

    return () => {
      if (unlisten) unlisten();
    };
  }, [refresh]);

  return { data, loading, error, selectedProject, setSelectedProject, refresh };
}
