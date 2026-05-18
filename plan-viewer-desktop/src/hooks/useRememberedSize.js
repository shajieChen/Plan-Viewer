import { useState, useEffect, useRef, useCallback } from 'preact/hooks';
import sizeStore, { DEFAULT_SIZE, DEBOUNCE_MS, MIN_WIDTH, MIN_HEIGHT } from '../utils/sizeStore.js';

/**
 * Clamp a size to the current monitor's available area and enforce minimums.
 * Falls back to the original size if screen info is unavailable.
 *
 * @param {{ width: number, height: number }} size
 * @returns {{ width: number, height: number }}
 */
function clampToMonitor(size) {
  let { width, height } = size;

  try {
    const availW = window.screen.availWidth;
    const availH = window.screen.availHeight;

    if (typeof availW === 'number' && availW > 0) {
      if (width > availW) width = availW;
    }
    if (typeof availH === 'number' && availH > 0) {
      if (height > availH) height = availH;
    }
  } catch {
    // Screen info unavailable — skip clamping
  }

  // Enforce minimums
  if (width < MIN_WIDTH) width = MIN_WIDTH;
  if (height < MIN_HEIGHT) height = MIN_HEIGHT;

  return { width, height };
}

/**
 * Hook that coordinates window size persistence with sizeStore.
 *
 * - On mount: loads stored sizes and extracts the current project's size
 * - On savedSize change: debounces (1000ms) and persists to sizeStore
 * - On selectedProject change: flushes pending save → loads new project size → updates initialSize
 * - On unmount: flushes any pending debounced write
 *
 * @param {{ selectedProject: string | null, savedSize: { width: number, height: number } | null }} options
 * @returns {{ initialSize: { width: number, height: number }, loading: boolean }}
 */
export function useRememberedSize({ selectedProject, savedSize }) {
  const [initialSize, setInitialSize] = useState(DEFAULT_SIZE);
  const [loading, setLoading] = useState(true);

  // Mutable refs for debounce management
  const sizeMapRef = useRef({});
  const debounceTimerRef = useRef(null);
  const pendingSaveRef = useRef(null); // { project, size } awaiting flush
  const selectedProjectRef = useRef(selectedProject);
  const savedSizeRef = useRef(savedSize);
  const mountedRef = useRef(true);

  // Keep refs in sync
  selectedProjectRef.current = selectedProject;
  savedSizeRef.current = savedSize;

  /**
   * Immediately flush any pending debounced save.
   */
  const flushDebounce = useCallback(async () => {
    if (debounceTimerRef.current !== null) {
      clearTimeout(debounceTimerRef.current);
      debounceTimerRef.current = null;
    }
    const pending = pendingSaveRef.current;
    if (pending) {
      pendingSaveRef.current = null;
      const { project, size } = pending;
      if (project && size) {
        sizeMapRef.current[project] = size;
        await sizeStore.save(sizeMapRef.current);
      }
    }
  }, []);

  /**
   * Schedule a debounced save for the given project/size.
   */
  const scheduleSave = useCallback((project, size) => {
    if (!project || !size) return;

    pendingSaveRef.current = { project, size };

    if (debounceTimerRef.current !== null) {
      clearTimeout(debounceTimerRef.current);
    }

    debounceTimerRef.current = setTimeout(async () => {
      debounceTimerRef.current = null;
      const pending = pendingSaveRef.current;
      if (pending) {
        pendingSaveRef.current = null;
        const { project: p, size: s } = pending;
        if (p && s) {
          sizeMapRef.current[p] = s;
          await sizeStore.save(sizeMapRef.current);
        }
      }
    }, DEBOUNCE_MS);
  }, []);

  /**
   * Load size for a given project from the cached sizeMap.
   * Validates and clamps to monitor bounds.
   */
  const resolveSizeForProject = useCallback((project) => {
    if (!project) return DEFAULT_SIZE;

    const raw = sizeMapRef.current[project];
    const validated = sizeStore.validate(raw);

    if (!validated) return DEFAULT_SIZE;

    return clampToMonitor(validated);
  }, []);

  // --- Mount: load full size map and resolve initial size ---
  useEffect(() => {
    let cancelled = false;

    async function init() {
      const data = await sizeStore.load();
      if (cancelled) return;

      sizeMapRef.current = data;
      const size = resolveSizeForProject(selectedProject);
      setInitialSize(size);
      setLoading(false);
    }

    init();

    return () => {
      cancelled = true;
    };
  }, []); // Only on mount

  // --- Watch savedSize changes: debounce persist ---
  const prevSavedSizeRef = useRef(savedSize);
  useEffect(() => {
    // Skip if savedSize hasn't actually changed or is null
    if (savedSize === prevSavedSizeRef.current) return;
    prevSavedSizeRef.current = savedSize;

    if (!savedSize || !selectedProject) return;

    scheduleSave(selectedProject, savedSize);
  }, [savedSize, selectedProject, scheduleSave]);

  // --- Watch selectedProject changes: flush → load new → update initialSize ---
  const prevProjectRef = useRef(selectedProject);
  useEffect(() => {
    if (selectedProject === prevProjectRef.current) return;
    const prevProject = prevProjectRef.current;
    prevProjectRef.current = selectedProject;

    async function switchProject() {
      // 1. Flush pending debounce (saves current/old project size)
      await flushDebounce();

      // 2. If there's a current savedSize for the old project that wasn't yet persisted,
      //    save it now (the flush above handles the debounced one)
      if (prevProject && savedSizeRef.current) {
        sizeMapRef.current[prevProject] = savedSizeRef.current;
        await sizeStore.save(sizeMapRef.current);
      }

      // 3. Load new project size
      // Re-load from disk in case another process updated it
      const freshData = await sizeStore.load();
      if (!mountedRef.current) return;
      sizeMapRef.current = freshData;

      const newSize = resolveSizeForProject(selectedProject);
      setInitialSize(newSize);
    }

    switchProject();
  }, [selectedProject, flushDebounce, resolveSizeForProject]);

  // --- Unmount: flush pending debounce ---
  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      // Synchronously clear timer and attempt flush
      if (debounceTimerRef.current !== null) {
        clearTimeout(debounceTimerRef.current);
        debounceTimerRef.current = null;
      }
      const pending = pendingSaveRef.current;
      if (pending) {
        pendingSaveRef.current = null;
        const { project, size } = pending;
        if (project && size) {
          sizeMapRef.current[project] = size;
          // Fire-and-forget save on unmount
          sizeStore.save(sizeMapRef.current);
        }
      }
    };
  }, []);

  return { initialSize, loading };
}

export default useRememberedSize;
