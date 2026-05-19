import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, act, cleanup, waitFor } from '@testing-library/preact';
import { DetailPanel } from './DetailPanel.jsx';
import { STATUS_COLORS, VALID_STATUSES, getStatusColor } from '../utils/statusConstants.js';

/**
 * Convert hex color (#rrggbb) to rgb() format as returned by jsdom style.
 */
function hexToRgb(hex) {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgb(${r}, ${g}, ${b})`;
}

/**
 * Feature: status-change-interaction, Property 5: Status selector renders current state correctly
 * Validates: Requirements 2.2, 2.3, 4.1
 */

// Mock Tauri IPC
beforeEach(() => {
  globalThis.window.__TAURI__ = {
    core: {
      invoke: vi.fn().mockResolvedValue({ artifact_id: 'test-artifact', new_status: 'ready' }),
    },
  };
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  delete globalThis.window.__TAURI__;
});

const baseArtifact = {
  id: 'R-001',
  status: 'draft',
  type: 'Research',
  depends_on: [],
};

describe('DetailPanel StatusSelector - rendering', () => {
  it('renders all 9 status options in the select element', () => {
    const { container } = render(
      <DetailPanel artifact={baseArtifact} projectName="test-project" onClose={() => {}} />
    );

    const select = container.querySelector('select');
    expect(select).not.toBeNull();

    const options = select.querySelectorAll('option');
    expect(options.length).toBe(9);

    const optionValues = Array.from(options).map((o) => o.value);
    expect(optionValues).toEqual(VALID_STATUSES);
  });

  it('shows the correct selected value matching artifact status', () => {
    const artifact = { ...baseArtifact, status: 'approved' };
    const { container } = render(
      <DetailPanel artifact={artifact} projectName="test-project" onClose={() => {}} />
    );

    const select = container.querySelector('select');
    expect(select.value).toBe('approved');
  });

  it('applies correct background color from STATUS_COLORS for the current status', () => {
    const artifact = { ...baseArtifact, status: 'blocked' };
    const { container } = render(
      <DetailPanel artifact={artifact} projectName="test-project" onClose={() => {}} />
    );

    const select = container.querySelector('select');
    expect(select.style.backgroundColor).toBe(hexToRgb(STATUS_COLORS.blocked));
  });

  it('applies correct background color for each valid status', () => {
    for (const status of VALID_STATUSES) {
      cleanup();
      const artifact = { ...baseArtifact, status };
      const { container } = render(
        <DetailPanel artifact={artifact} projectName="test-project" onClose={() => {}} />
      );

      const select = container.querySelector('select');
      expect(select.style.backgroundColor).toBe(hexToRgb(STATUS_COLORS[status]));
    }
  });
});

describe('DetailPanel StatusSelector - pending state', () => {
  it('disables select and applies opacity 0.5 during update', async () => {
    // Make invoke hang (never resolve) to keep pending state
    window.__TAURI__.core.invoke.mockImplementation(() => new Promise(() => {}));

    const artifact = { ...baseArtifact, status: 'draft' };
    const { container } = render(
      <DetailPanel artifact={artifact} projectName="test-project" onClose={() => {}} />
    );

    const select = container.querySelector('select');
    expect(select.disabled).toBe(false);
    expect(select.style.opacity).toBe('1');

    // Trigger status change
    await act(async () => {
      fireEvent.change(select, { target: { value: 'ready' } });
    });

    // Now it should be disabled with reduced opacity
    expect(select.disabled).toBe(true);
    expect(select.style.opacity).toBe('0.5');
  });

  it('re-enables select after successful update', async () => {
    window.__TAURI__.core.invoke.mockResolvedValue({ artifact_id: 'R-001', new_status: 'ready' });

    const artifact = { ...baseArtifact, status: 'draft' };
    const { container } = render(
      <DetailPanel artifact={artifact} projectName="test-project" onClose={() => {}} />
    );

    const select = container.querySelector('select');

    await act(async () => {
      fireEvent.change(select, { target: { value: 'ready' } });
    });

    // Wait for the promise to resolve and state to update
    await waitFor(() => {
      expect(select.disabled).toBe(false);
    });

    expect(select.style.opacity).toBe('1');
    expect(select.value).toBe('ready');
  });
});

describe('DetailPanel StatusSelector - error handling', () => {
  it('reverts status and displays error message on invoke failure', async () => {
    window.__TAURI__.core.invoke.mockRejectedValue(new Error('Artifact not found'));

    const artifact = { ...baseArtifact, status: 'draft' };
    const { container } = render(
      <DetailPanel artifact={artifact} projectName="test-project" onClose={() => {}} />
    );

    const select = container.querySelector('select');

    await act(async () => {
      fireEvent.change(select, { target: { value: 'blocked' } });
    });

    // Wait for the rejection to be handled and state to revert
    await waitFor(() => {
      expect(select.value).toBe('draft');
    });

    expect(select.disabled).toBe(false);

    // Error message should be displayed
    const errorSpan = container.querySelector('.status-error');
    expect(errorSpan).not.toBeNull();
    expect(errorSpan.textContent).toBe('Artifact not found');
  });

  it('handles timeout at 10 seconds and reverts status', async () => {
    vi.useFakeTimers();

    // Mock invoke that never resolves (simulates slow request)
    window.__TAURI__.core.invoke.mockImplementation(() => new Promise(() => {}));

    const artifact = { ...baseArtifact, status: 'draft' };
    const { container } = render(
      <DetailPanel artifact={artifact} projectName="test-project" onClose={() => {}} />
    );

    const select = container.querySelector('select');

    // Trigger status change
    act(() => {
      fireEvent.change(select, { target: { value: 'approved' } });
    });

    // Select should be disabled during pending
    expect(select.disabled).toBe(true);

    // Advance time past the 10-second timeout
    await act(async () => {
      vi.advanceTimersByTime(10001);
    });

    // Wait for state to settle after timeout rejection
    await waitFor(() => {
      expect(select.value).toBe('draft');
    });

    expect(select.disabled).toBe(false);

    const errorSpan = container.querySelector('.status-error');
    expect(errorSpan).not.toBeNull();
    expect(errorSpan.textContent).toBe('Request timed out');

    vi.useRealTimers();
  });
});
