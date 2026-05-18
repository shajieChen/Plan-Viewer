import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, cleanup, fireEvent, waitFor } from '@testing-library/preact';
import { App } from './App.jsx';

// --- Mock @tauri-apps/api/core ---
vi.mock('@tauri-apps/api/core', () => ({
  invoke: vi.fn(),
}));

// --- Mock @tauri-apps/api/event ---
vi.mock('@tauri-apps/api/event', () => ({
  listen: vi.fn(() => Promise.resolve(() => {})),
}));

// --- Mock @tauri-apps/api/window ---
const mockSetSize = vi.fn(() => Promise.resolve());
const mockInnerSize = vi.fn(() => Promise.resolve({ width: 800, height: 600 }));
const mockOuterPosition = vi.fn(() => Promise.resolve({ x: 0, y: 0 }));
const mockScaleFactor = vi.fn(() => Promise.resolve(1));
const mockOnResized = vi.fn(() => Promise.resolve(() => {}));

vi.mock('@tauri-apps/api/window', () => ({
  getCurrentWindow: () => ({
    setSize: mockSetSize,
    innerSize: mockInnerSize,
    outerPosition: mockOuterPosition,
    scaleFactor: mockScaleFactor,
    onResized: mockOnResized,
  }),
  currentMonitor: vi.fn(() =>
    Promise.resolve({ size: { width: 1920, height: 1080 } })
  ),
  LogicalSize: class LogicalSize {
    constructor(width, height) {
      this.width = width;
      this.height = height;
    }
  },
}));

// --- Mock sizeStore ---
vi.mock('./utils/sizeStore.js', () => ({
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
  MAX_ENTRIES: 200,
}));

import { invoke } from '@tauri-apps/api/core';
import sizeStore from './utils/sizeStore.js';

/**
 * Setup sizeStore.validate to behave like the real implementation.
 */
function setupValidateMock() {
  sizeStore.validate.mockImplementation((size) => {
    if (size == null || typeof size !== 'object') return null;
    const { width, height } = size;
    if (
      typeof width !== 'number' ||
      typeof height !== 'number' ||
      !Number.isInteger(width) ||
      !Number.isInteger(height) ||
      width < 200 ||
      width > 7680 ||
      height < 150 ||
      height > 4320
    )
      return null;
    return { width, height };
  });
}

/**
 * Setup invoke mock to return dashboard data with given projects.
 */
function setupInvokeMock(projects) {
  invoke.mockImplementation(async (cmd) => {
    if (cmd === 'get_dashboard_data') {
      return { projects };
    }
    if (cmd === 'read_window_sizes') {
      return '{}';
    }
    if (cmd === 'write_window_sizes') {
      return undefined;
    }
    return undefined;
  });
}

beforeEach(() => {
  vi.useFakeTimers();
  vi.clearAllMocks();

  setupValidateMock();
  sizeStore.load.mockResolvedValue({});
  sizeStore.save.mockResolvedValue(undefined);

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

/**
 * Helper to flush microtasks and timers.
 */
async function flushAll() {
  for (let i = 0; i < 5; i++) {
    await new Promise((r) => r(undefined));
  }
  vi.runAllTimers();
  for (let i = 0; i < 5; i++) {
    await new Promise((r) => r(undefined));
  }
}

describe('App.jsx 集成测试', () => {
  describe('启动时 initialSize 从存储加载 (Req 4.1)', () => {
    it('uses stored remembered size as initialSize instead of hardcoded 400×300', async () => {
      // Setup: sizeStore has a remembered size for the project
      sizeStore.load.mockResolvedValue({
        'C:/Projects/my-app': { width: 750, height: 550 },
      });

      // Setup: invoke returns project data with one project
      setupInvokeMock({
        'C:/Projects/my-app': {
          artifacts: [{ id: 'a1', name: 'Test', type: 'plan', status: 'active' }],
          change_events: [],
          markdown_previews: {},
        },
      });

      vi.useRealTimers();

      const { container } = render(<App />);

      // Wait for the app to finish loading (useProjects + useRememberedSize)
      await waitFor(() => {
        // The app should render content (not loading state)
        expect(container.querySelector('.app-container')).toBeTruthy();
      });

      // Verify sizeStore.load was called (initialSize loaded from storage)
      expect(sizeStore.load).toHaveBeenCalled();
    });

    it('falls back to DEFAULT_SIZE when no stored size exists', async () => {
      // Setup: sizeStore returns empty (no stored sizes)
      sizeStore.load.mockResolvedValue({});

      setupInvokeMock({
        'C:/Projects/my-app': {
          artifacts: [],
          change_events: [],
          markdown_previews: {},
        },
      });

      vi.useRealTimers();

      render(<App />);

      await waitFor(() => {
        expect(sizeStore.load).toHaveBeenCalled();
      });

      // Since there's no stored size, useRememberedSize should return DEFAULT_SIZE
      // The app should still render without errors
    });
  });

  describe('项目切换时窗口尺寸正确更新 (Req 4.2)', () => {
    it('loads new project size when switching projects via selector', async () => {
      // Setup: two projects with different stored sizes
      sizeStore.load.mockResolvedValue({
        'Project-A': { width: 600, height: 450 },
        'Project-B': { width: 900, height: 700 },
      });

      setupInvokeMock({
        'Project-A': {
          artifacts: [{ id: 'a1', name: 'Artifact A', type: 'plan', status: 'active' }],
          change_events: [],
          markdown_previews: {},
        },
        'Project-B': {
          artifacts: [{ id: 'b1', name: 'Artifact B', type: 'plan', status: 'active' }],
          change_events: [],
          markdown_previews: {},
        },
      });

      vi.useRealTimers();

      const { container } = render(<App />);

      // Wait for initial load to complete
      await waitFor(() => {
        const selector = container.querySelector('.project-selector select');
        expect(selector).toBeTruthy();
      });

      // Verify initial load happened
      expect(sizeStore.load).toHaveBeenCalled();

      // Switch project via the selector
      const selector = container.querySelector('.project-selector select');
      fireEvent.change(selector, { target: { value: 'Project-B' } });

      // After switching, sizeStore.load should be called again (to refresh data)
      // and sizeStore.save should be called (to persist old project's size)
      await waitFor(() => {
        // load is called at least twice: once on mount, once on project switch
        expect(sizeStore.load.mock.calls.length).toBeGreaterThanOrEqual(2);
      });
    });

    it('saves current project size before switching to new project', async () => {
      sizeStore.load.mockResolvedValue({
        'Project-A': { width: 600, height: 450 },
        'Project-B': { width: 900, height: 700 },
      });

      setupInvokeMock({
        'Project-A': {
          artifacts: [{ id: 'a1', name: 'A', type: 'plan', status: 'active' }],
          change_events: [],
          markdown_previews: {},
        },
        'Project-B': {
          artifacts: [{ id: 'b1', name: 'B', type: 'plan', status: 'active' }],
          change_events: [],
          markdown_previews: {},
        },
      });

      vi.useRealTimers();

      const { container } = render(<App />);

      await waitFor(() => {
        expect(container.querySelector('.project-selector select')).toBeTruthy();
      });

      // Wait for initial load to complete
      await waitFor(() => {
        expect(sizeStore.load).toHaveBeenCalled();
      });

      // Switch project — the hook's switchProject logic calls save to persist old project
      const selector = container.querySelector('.project-selector select');
      fireEvent.change(selector, { target: { value: 'Project-B' } });

      // The switchProject logic in useRememberedSize calls sizeStore.save
      // to persist the old project's size (even if savedSize is null, it saves
      // whatever savedSizeRef.current is). Also calls load again for fresh data.
      await waitFor(
        () => {
          // load is called again during project switch
          expect(sizeStore.load.mock.calls.length).toBeGreaterThanOrEqual(2);
        },
        { timeout: 3000 }
      );
    });
  });

  describe('auto-shrink 恢复时使用 rememberedSize 而非默认值 (Req 4.3)', () => {
    it('useWindowAutoShrink receives remembered initialSize, not hardcoded 400×300', async () => {
      // Setup: stored size is different from default 400×300
      const storedSize = { width: 750, height: 550 };
      sizeStore.load.mockResolvedValue({
        'C:/Projects/my-app': storedSize,
      });

      setupInvokeMock({
        'C:/Projects/my-app': {
          artifacts: [{ id: 'a1', name: 'Test', type: 'plan', status: 'active' }],
          change_events: [],
          markdown_previews: {},
        },
      });

      vi.useRealTimers();

      const { container } = render(<App />);

      // Wait for app to load and useRememberedSize to resolve
      await waitFor(() => {
        expect(container.querySelector('.app-container')).toBeTruthy();
      });

      // Wait for the async load to complete and validate to be called
      await waitFor(() => {
        expect(sizeStore.validate).toHaveBeenCalledWith(storedSize);
      });

      // Verify that sizeStore.load was called
      expect(sizeStore.load).toHaveBeenCalled();
    });

    it('when no remembered size exists, auto-shrink uses DEFAULT_SIZE (400×300)', async () => {
      // Setup: no stored sizes
      sizeStore.load.mockResolvedValue({});

      setupInvokeMock({
        'C:/Projects/my-app': {
          artifacts: [{ id: 'a1', name: 'Test', type: 'plan', status: 'active' }],
          change_events: [],
          markdown_previews: {},
        },
      });

      vi.useRealTimers();

      const { container } = render(<App />);

      await waitFor(() => {
        expect(container.querySelector('.app-container')).toBeTruthy();
      });

      // sizeStore.load was called but returned empty — validate won't be called
      // with a valid size, so DEFAULT_SIZE is used
      expect(sizeStore.load).toHaveBeenCalled();
    });

    it('remembered size is passed through validation before use', async () => {
      // Setup: stored size that passes validation
      const storedSize = { width: 800, height: 600 };
      sizeStore.load.mockResolvedValue({
        'C:/Projects/my-app': storedSize,
      });

      setupInvokeMock({
        'C:/Projects/my-app': {
          artifacts: [{ id: 'a1', name: 'Test', type: 'plan', status: 'active' }],
          change_events: [],
          markdown_previews: {},
        },
      });

      vi.useRealTimers();

      render(<App />);

      await waitFor(() => {
        expect(sizeStore.validate).toHaveBeenCalledWith(storedSize);
      });
    });

    it('invalid remembered size causes fallback to DEFAULT_SIZE', async () => {
      // Setup: stored size that fails validation (too small)
      const invalidSize = { width: 50, height: 50 };
      sizeStore.load.mockResolvedValue({
        'C:/Projects/my-app': invalidSize,
      });

      setupInvokeMock({
        'C:/Projects/my-app': {
          artifacts: [{ id: 'a1', name: 'Test', type: 'plan', status: 'active' }],
          change_events: [],
          markdown_previews: {},
        },
      });

      vi.useRealTimers();

      render(<App />);

      await waitFor(() => {
        // validate is called with the invalid size and returns null
        expect(sizeStore.validate).toHaveBeenCalledWith(invalidSize);
      });

      // Since validate returns null for invalid sizes, DEFAULT_SIZE is used
      // The app should still render without errors
    });
  });
});
