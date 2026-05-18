import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act, cleanup, waitFor } from '@testing-library/preact';
import { useRememberedSize } from './useRememberedSize.js';

// Mock the sizeStore module
vi.mock('../utils/sizeStore.js', () => ({
  default: {
    load: vi.fn(),
    save: vi.fn(),
    validate: vi.fn(),
  },
  load: vi.fn(),
  save: vi.fn(),
  validate: vi.fn(),
  DEFAULT_SIZE: { width: 400, height: 300 },
  DEBOUNCE_MS: 1000,
  MIN_WIDTH: 200,
  MIN_HEIGHT: 150,
  MAX_WIDTH: 7680,
  MAX_HEIGHT: 4320,
}));

import sizeStore, { DEFAULT_SIZE } from '../utils/sizeStore.js';

/**
 * Helper to flush all pending microtasks/promises.
 */
async function flushPromises() {
  for (let i = 0; i < 10; i++) {
    await new Promise((resolve) => resolve(undefined));
  }
}

/**
 * Helper to flush both microtasks and any pending timers (for Preact effect scheduling).
 */
async function flushAll() {
  await act(async () => {
    await flushPromises();
    vi.runAllTimers();
    await flushPromises();
  });
}

function setupValidateMock() {
  sizeStore.validate.mockImplementation((size) => {
    if (size == null || typeof size !== 'object') return null;
    const { width, height } = size;
    if (
      typeof width !== 'number' ||
      typeof height !== 'number' ||
      !Number.isInteger(width) ||
      !Number.isInteger(height) ||
      width < 200 || width > 7680 ||
      height < 150 || height > 4320
    ) return null;
    return { width, height };
  });
}

beforeEach(() => {
  vi.useFakeTimers();
  vi.clearAllMocks();

  // Default: load resolves to empty, validate passes through
  sizeStore.load.mockResolvedValue({});
  sizeStore.save.mockResolvedValue(undefined);
  setupValidateMock();

  // Mock window.screen for clampToMonitor
  Object.defineProperty(window, 'screen', {
    value: { availWidth: 1920, availHeight: 1080 },
    writable: true,
    configurable: true,
  });
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

describe('useRememberedSize', () => {
  describe('启动加载成功时返回正确的 initialSize', () => {
    it('returns stored size for the selected project on mount', async () => {
      sizeStore.load.mockResolvedValue({
        'C:/Projects/app': { width: 800, height: 600 },
      });

      const { result } = renderHook(() =>
        useRememberedSize({ selectedProject: 'C:/Projects/app', savedSize: null })
      );

      // Initially loading
      expect(result.current.loading).toBe(true);

      // Wait for async load to complete
      await flushAll();

      expect(result.current.loading).toBe(false);
      expect(result.current.initialSize).toEqual({ width: 800, height: 600 });
    });

    it('returns DEFAULT_SIZE when project has no stored size', async () => {
      sizeStore.load.mockResolvedValue({
        'C:/Other/project': { width: 500, height: 400 },
      });

      const { result } = renderHook(() =>
        useRememberedSize({ selectedProject: 'C:/Projects/app', savedSize: null })
      );

      await flushAll();

      expect(result.current.loading).toBe(false);
      expect(result.current.initialSize).toEqual(DEFAULT_SIZE);
    });
  });

  describe('启动加载失败时返回 DEFAULT_SIZE', () => {
    it('returns DEFAULT_SIZE when load returns empty (simulating failure)', async () => {
      // sizeStore.load() internally catches errors and returns {}
      sizeStore.load.mockResolvedValue({});

      const { result } = renderHook(() =>
        useRememberedSize({ selectedProject: 'C:/Projects/app', savedSize: null })
      );

      await flushAll();

      expect(result.current.initialSize).toEqual(DEFAULT_SIZE);
    });

    it('returns DEFAULT_SIZE when selectedProject is null', async () => {
      sizeStore.load.mockResolvedValue({
        'C:/Projects/app': { width: 800, height: 600 },
      });

      const { result } = renderHook(() =>
        useRememberedSize({ selectedProject: null, savedSize: null })
      );

      await flushAll();

      expect(result.current.initialSize).toEqual(DEFAULT_SIZE);
    });
  });

  describe('项目切换时正确保存旧项目并加载新项目尺寸', () => {
    it('saves old project size and loads new project size on switch', async () => {
      // Use real timers for async effect completion
      vi.useRealTimers();

      // Return fresh copies each time to avoid mutation issues
      sizeStore.load.mockImplementation(async () => ({
        'C:/Projects/app-a': { width: 600, height: 450 },
        'C:/Projects/app-b': { width: 900, height: 700 },
      }));
      sizeStore.save.mockResolvedValue(undefined);

      const { result, rerender } = renderHook(
        ({ selectedProject, savedSize }) =>
          useRememberedSize({ selectedProject, savedSize }),
        { initialProps: { selectedProject: 'C:/Projects/app-a', savedSize: null } }
      );

      // Wait for initial load
      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });
      expect(result.current.initialSize).toEqual({ width: 600, height: 450 });

      // Set a savedSize for the current project (simulating a window resize)
      // This ensures savedSizeRef.current is set before the switch
      rerender({ selectedProject: 'C:/Projects/app-a', savedSize: { width: 650, height: 480 } });

      // Small delay to let the savedSize effect register
      await new Promise((r) => setTimeout(r, 10));

      // Now switch project — the hook should save old project's size before loading new
      rerender({ selectedProject: 'C:/Projects/app-b', savedSize: { width: 650, height: 480 } });

      // Wait for the async switchProject to complete and state to update
      await waitFor(() => {
        expect(result.current.initialSize).toEqual({ width: 900, height: 700 });
      });

      // Should have saved old project's size (via the switchProject logic)
      expect(sizeStore.save).toHaveBeenCalled();
    });

    it('returns DEFAULT_SIZE for new project with no stored size', async () => {
      vi.useRealTimers();

      sizeStore.load.mockImplementation(async () => ({
        'C:/Projects/app-a': { width: 600, height: 450 },
      }));
      sizeStore.save.mockResolvedValue(undefined);

      const { result, rerender } = renderHook(
        ({ selectedProject, savedSize }) =>
          useRememberedSize({ selectedProject, savedSize }),
        { initialProps: { selectedProject: 'C:/Projects/app-a', savedSize: null } }
      );

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });

      // Switch to project with no stored size
      rerender({ selectedProject: 'C:/Projects/new-project', savedSize: null });

      await waitFor(() => {
        expect(result.current.initialSize).toEqual(DEFAULT_SIZE);
      });
    });
  });

  describe('校验失败时返回 DEFAULT_SIZE', () => {
    it('returns DEFAULT_SIZE when stored size fails validation', async () => {
      sizeStore.load.mockResolvedValue({
        'C:/Projects/app': { width: 50, height: 50 }, // Below minimums
      });

      const { result } = renderHook(() =>
        useRememberedSize({ selectedProject: 'C:/Projects/app', savedSize: null })
      );

      await flushAll();

      // validate returns null for invalid sizes, so DEFAULT_SIZE is used
      expect(result.current.initialSize).toEqual(DEFAULT_SIZE);
    });

    it('returns DEFAULT_SIZE when stored size has non-integer values', async () => {
      sizeStore.load.mockResolvedValue({
        'C:/Projects/app': { width: 400.5, height: 300.7 },
      });

      const { result } = renderHook(() =>
        useRememberedSize({ selectedProject: 'C:/Projects/app', savedSize: null })
      );

      await flushAll();

      expect(result.current.initialSize).toEqual(DEFAULT_SIZE);
    });
  });

  describe('组件卸载时 flush 防抖', () => {
    it('flushes pending debounced save on unmount', async () => {
      sizeStore.load.mockResolvedValue({});

      const { rerender, unmount } = renderHook(
        ({ selectedProject, savedSize }) =>
          useRememberedSize({ selectedProject, savedSize }),
        { initialProps: { selectedProject: 'C:/Projects/app', savedSize: null } }
      );

      // Wait for initial load
      await flushAll();

      // Trigger a savedSize change to schedule a debounced save
      rerender({ selectedProject: 'C:/Projects/app', savedSize: { width: 700, height: 500 } });

      // Let the effect run but don't advance past debounce time (1000ms)
      await act(async () => {
        vi.advanceTimersByTime(100);
        await flushPromises();
      });

      // The debounce timer is pending (not yet flushed) — save should NOT have been called
      expect(sizeStore.save).not.toHaveBeenCalled();

      // Unmount should flush the pending save
      unmount();

      // save should have been called with the pending size
      expect(sizeStore.save).toHaveBeenCalled();
      const savedArg = sizeStore.save.mock.calls[0][0];
      expect(savedArg['C:/Projects/app']).toEqual({ width: 700, height: 500 });
    });

    it('does not call save on unmount when no pending debounce', async () => {
      sizeStore.load.mockResolvedValue({});

      const { unmount } = renderHook(() =>
        useRememberedSize({ selectedProject: 'C:/Projects/app', savedSize: null })
      );

      await flushAll();

      unmount();

      // No savedSize change was made, so save should not be called
      expect(sizeStore.save).not.toHaveBeenCalled();
    });
  });
});
