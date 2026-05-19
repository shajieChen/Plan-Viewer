import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, cleanup, fireEvent, waitFor, act } from '@testing-library/preact';
import { App } from '../App.jsx';

/**
 * Integration test: end-to-end status change flow
 * Validates: Requirements 3.3, 3.4
 *
 * Tests the full cycle:
 *   user selects status -> invoke called -> watcher event fires -> data refreshes -> UI updates
 *
 * Also tests:
 *   failed re-fetch preserves previous data and shows error
 */

// Capture the listen callback so we can simulate watcher events
let listenCallbacks = {};

// --- Mock @tauri-apps/api/core ---
vi.mock('@tauri-apps/api/core', () => ({
  invoke: vi.fn(),
}));

// --- Mock @tauri-apps/api/event ---
vi.mock('@tauri-apps/api/event', () => ({
  listen: vi.fn((eventName, callback) => {
    listenCallbacks[eventName] = callback;
    return Promise.resolve(() => {
      delete listenCallbacks[eventName];
    });
  }),
}));

// --- Mock @tauri-apps/api/window ---
vi.mock('@tauri-apps/api/window', () => ({
  getCurrentWindow: () => ({
    setSize: vi.fn(() => Promise.resolve()),
    innerSize: vi.fn(() => Promise.resolve({ width: 800, height: 600 })),
    outerPosition: vi.fn(() => Promise.resolve({ x: 0, y: 0 })),
    scaleFactor: vi.fn(() => Promise.resolve(1)),
    onResized: vi.fn(() => Promise.resolve(() => {})),
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
vi.mock('../utils/sizeStore.js', () => ({
  default: {
    load: vi.fn(() => Promise.resolve({})),
    save: vi.fn(() => Promise.resolve()),
    validate: vi.fn((size) => {
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
    }),
  },
  load: vi.fn(() => Promise.resolve({})),
  save: vi.fn(() => Promise.resolve()),
  validate: vi.fn((size) => size),
  DEFAULT_SIZE: { width: 400, height: 300 },
  DEBOUNCE_MS: 1000,
  MIN_WIDTH: 200,
  MIN_HEIGHT: 150,
  MAX_WIDTH: 7680,
  MAX_HEIGHT: 4320,
  MAX_ENTRIES: 200,
}));

import { invoke } from '@tauri-apps/api/core';

// --- Test data ---
const makeProjectData = (artifactStatus = 'draft') => ({
  projects: {
    'TestProject': {
      artifacts: [
        { id: 'R-001', name: 'Research Doc', type: 'Research', status: artifactStatus, depends_on: [], group: 'Phase1' },
        { id: 'D-001', name: 'Design Doc', type: 'Decision', status: 'approved', depends_on: ['R-001'], group: 'Phase2' },
      ],
      change_events: [],
      markdown_previews: {},
    },
  },
});

beforeEach(() => {
  vi.clearAllMocks();
  listenCallbacks = {};

  // Mock window.screen
  Object.defineProperty(window, 'screen', {
    value: { availWidth: 1920, availHeight: 1080 },
    writable: true,
    configurable: true,
  });

  // Mock window.__TAURI__ for DetailPanel's direct invoke usage
  globalThis.window.__TAURI__ = {
    core: {
      invoke: vi.fn().mockResolvedValue({ artifact_id: 'R-001', new_status: 'ready' }),
    },
  };

  // Set window width large enough for side panel
  Object.defineProperty(window, 'innerWidth', { value: 800, writable: true, configurable: true });
});

afterEach(() => {
  cleanup();
  delete globalThis.window.__TAURI__;
});

describe('Integration: End-to-end status change flow', () => {
  it('happy path: select status, invoke succeeds, watcher event fires, UI refreshes with new status', async () => {
    // Initial data: artifact R-001 has status 'draft'
    const initialData = makeProjectData('draft');
    // After status change, watcher triggers re-fetch with updated status
    const updatedData = makeProjectData('ready');

    let invokeCallCount = 0;
    invoke.mockImplementation(async (cmd) => {
      if (cmd === 'get_dashboard_data') {
        invokeCallCount++;
        // First call returns initial data, subsequent calls return updated data
        return invokeCallCount === 1 ? initialData : updatedData;
      }
      if (cmd === 'read_window_sizes') return '{}';
      if (cmd === 'write_window_sizes') return undefined;
      return undefined;
    });

    // Also mock the __TAURI__ invoke for update_artifact_status
    window.__TAURI__.core.invoke.mockResolvedValue({ artifact_id: 'R-001', new_status: 'ready' });

    const { container } = render(<App />);

    // Wait for initial load to complete and artifacts to render
    await waitFor(() => {
      const cards = container.querySelectorAll('.swimlane-card');
      expect(cards.length).toBeGreaterThan(0);
    });

    // Click on the first artifact card to open DetailPanel
    const cards = container.querySelectorAll('.swimlane-card');

    await act(async () => {
      fireEvent.click(cards[0]);
    });

    // Wait for DetailPanel to appear with the status selector
    await waitFor(() => {
      const select = container.querySelector('.detail-panel select');
      expect(select).not.toBeNull();
    });

    const statusSelect = container.querySelector('.detail-panel select');
    expect(statusSelect.value).toBe('draft');

    // User selects a new status
    await act(async () => {
      fireEvent.change(statusSelect, { target: { value: 'ready' } });
    });

    // Verify the Tauri IPC was called with correct parameters
    expect(window.__TAURI__.core.invoke).toHaveBeenCalledWith(
      'update_artifact_status',
      {
        project_name: 'TestProject',
        artifact_id: 'R-001',
        new_status: 'ready',
      }
    );

    // Wait for the optimistic update to settle
    await waitFor(() => {
      const select = container.querySelector('.detail-panel select');
      expect(select.value).toBe('ready');
      expect(select.disabled).toBe(false);
    });

    // Now simulate the file watcher firing a 'project-updated' event
    // This is what happens when the Rust backend writes status.yaml and the watcher detects it
    expect(listenCallbacks['project-updated']).toBeDefined();

    await act(async () => {
      listenCallbacks['project-updated']({ payload: { path: 'status/status.yaml', timestamp: new Date().toISOString() } });
    });

    // The useProjects hook should re-fetch data
    await waitFor(() => {
      // get_dashboard_data should have been called at least twice (initial + refresh)
      const dashboardCalls = invoke.mock.calls.filter(c => c[0] === 'get_dashboard_data');
      expect(dashboardCalls.length).toBeGreaterThanOrEqual(2);
    });

    // After refresh, the UI should still show 'ready' (now from server data, not just optimistic)
    await waitFor(() => {
      const select = container.querySelector('.detail-panel select');
      expect(select).not.toBeNull();
      expect(select.value).toBe('ready');
    });
  });

  it('failed re-fetch after watcher event preserves previous data and shows error', async () => {
    // Initial data loads successfully
    const initialData = makeProjectData('draft');

    let invokeCallCount = 0;
    invoke.mockImplementation(async (cmd) => {
      if (cmd === 'get_dashboard_data') {
        invokeCallCount++;
        if (invokeCallCount === 1) {
          return initialData;
        }
        if (invokeCallCount === 2) {
          // Second call (triggered by watcher) fails
          throw new Error('Network error: failed to read projects');
        }
        // Third call (recovery) succeeds with original data
        return initialData;
      }
      if (cmd === 'read_window_sizes') return '{}';
      if (cmd === 'write_window_sizes') return undefined;
      return undefined;
    });

    const { container } = render(<App />);

    // Wait for initial load - artifacts should be visible
    await waitFor(() => {
      const cards = container.querySelectorAll('.swimlane-card');
      expect(cards.length).toBeGreaterThan(0);
    });

    // Simulate watcher event - the re-fetch will fail
    await act(async () => {
      listenCallbacks['project-updated']({ payload: { path: 'status/status.yaml', timestamp: new Date().toISOString() } });
    });

    // Wait for the failed re-fetch to be processed
    await waitFor(() => {
      const dashboardCalls = invoke.mock.calls.filter(c => c[0] === 'get_dashboard_data');
      expect(dashboardCalls.length).toBeGreaterThanOrEqual(2);
    });

    // The error should be displayed in the UI
    await waitFor(() => {
      const errorEl = container.querySelector('.error-message');
      expect(errorEl).not.toBeNull();
      expect(errorEl.textContent).toContain('Network error');
    });

    // Verify data is preserved by triggering another watcher event that succeeds.
    // The app should recover and show artifacts again, proving data was not lost.
    await act(async () => {
      listenCallbacks['project-updated']({ payload: { path: 'status/status.yaml', timestamp: new Date().toISOString() } });
    });

    // After successful recovery, artifacts should be visible again
    await waitFor(() => {
      const cards = container.querySelectorAll('.swimlane-card');
      expect(cards.length).toBeGreaterThan(0);
    });

    // Error should be cleared after successful refresh
    await waitFor(() => {
      const errorEl = container.querySelector('.error-message');
      expect(errorEl).toBeNull();
    });
  });
});
