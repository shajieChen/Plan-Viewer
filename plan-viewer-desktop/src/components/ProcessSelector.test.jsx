import { describe, it, expect } from 'vitest';
import * as fc from 'fast-check';
import { computePopupPosition } from './ProcessSelector.jsx';

/**
 * Feature: process-focus-button, Property 7: Popup viewport containment
 * Validates: Requirements 7.3
 *
 * For any viewport dimensions (width, height) and any anchor button position,
 * the computed popup position SHALL ensure the popup rectangle is fully
 * contained within the viewport bounds (0,0)→(width, height).
 */
describe('Property 7: Popup viewport containment', () => {
  it('computed popup position keeps the popup rectangle fully within viewport bounds', () => {
    fc.assert(
      fc.property(
        // Generate random viewport dimensions (100–2000)
        fc.integer({ min: 100, max: 2000 }),
        fc.integer({ min: 100, max: 2000 }),
        // Generate random panel dimensions (smaller than viewport to be placeable)
        fc.integer({ min: 20, max: 400 }),
        fc.integer({ min: 20, max: 400 }),
        // Generate random anchor button rect within viewport
        fc.integer({ min: 0, max: 2000 }),
        fc.integer({ min: 0, max: 2000 }),
        fc.integer({ min: 1, max: 200 }),
        fc.integer({ min: 1, max: 200 }),
        (viewportWidth, viewportHeight, panelWidth, panelHeight, anchorX, anchorY, anchorW, anchorH) => {
          // Ensure panel can fit in viewport (skip if panel is larger than viewport)
          // The positioning logic assumes the panel can fit; if it can't, the property doesn't apply
          if (panelWidth > viewportWidth - 4 || panelHeight > viewportHeight - 4) return;

          const anchorRect = {
            top: anchorY,
            bottom: anchorY + anchorH,
            left: anchorX,
            right: anchorX + anchorW,
          };

          const { top, left } = computePopupPosition({
            anchorRect,
            panelWidth,
            panelHeight,
            viewportWidth,
            viewportHeight,
          });

          // Assert popup is fully within viewport bounds
          expect(left).toBeGreaterThanOrEqual(0);
          expect(top).toBeGreaterThanOrEqual(0);
          expect(left + panelWidth).toBeLessThanOrEqual(viewportWidth);
          expect(top + panelHeight).toBeLessThanOrEqual(viewportHeight);
        }
      ),
      { numRuns: 200 }
    );
  });
});


// ============================================================================
// Unit Tests for ProcessSelector component (Task 7.4)
// Validates: Requirements 3.1, 3.2, 3.3, 7.1, 7.2
// ============================================================================
import { render, fireEvent, cleanup } from '@testing-library/preact';
import { vi, afterEach } from 'vitest';
import { ProcessSelector } from './ProcessSelector.jsx';

const mockProcesses = [
  { process_name: 'devenv.exe', pid: 1234, hwnd: 100, window_title: 'MyProject - Visual Studio' },
  { process_name: 'code.exe', pid: 5678, hwnd: 200, window_title: 'index.ts - VSCode' },
  { process_name: 'notepad.exe', pid: 9012, hwnd: 300, window_title: 'Untitled - Notepad' },
];

describe('ProcessSelector unit tests', () => {
  afterEach(() => {
    cleanup();
  });

  describe('renders process list with name, PID, and window title', () => {
    it('displays all process entries with correct info', () => {
      const { container } = render(
        <ProcessSelector
          processes={mockProcesses}
          loading={false}
          error={null}
          terminatedName={null}
          onSelect={() => {}}
          onDismiss={() => {}}
          anchorRef={null}
        />
      );

      const items = container.querySelectorAll('.process-selector-item');
      expect(items.length).toBe(3);

      // First process
      expect(items[0].querySelector('.process-name').textContent).toBe('devenv.exe');
      expect(items[0].querySelector('.process-title').textContent).toBe('MyProject - Visual Studio');
      expect(items[0].querySelector('.process-pid').textContent).toBe('PID: 1234');

      // Second process
      expect(items[1].querySelector('.process-name').textContent).toBe('code.exe');
      expect(items[1].querySelector('.process-title').textContent).toBe('index.ts - VSCode');
      expect(items[1].querySelector('.process-pid').textContent).toBe('PID: 5678');

      // Third process
      expect(items[2].querySelector('.process-name').textContent).toBe('notepad.exe');
      expect(items[2].querySelector('.process-title').textContent).toBe('Untitled - Notepad');
      expect(items[2].querySelector('.process-pid').textContent).toBe('PID: 9012');
    });
  });

  describe('search input filters list in real-time', () => {
    it('filters by process name (case-insensitive)', () => {
      const { container } = render(
        <ProcessSelector
          processes={mockProcesses}
          loading={false}
          error={null}
          terminatedName={null}
          onSelect={() => {}}
          onDismiss={() => {}}
          anchorRef={null}
        />
      );

      const input = container.querySelector('input[type="text"]');
      fireEvent.input(input, { target: { value: 'code' } });

      const items = container.querySelectorAll('.process-selector-item');
      expect(items.length).toBe(1);
      expect(items[0].querySelector('.process-name').textContent).toBe('code.exe');
    });

    it('filters by window title (case-insensitive)', () => {
      const { container } = render(
        <ProcessSelector
          processes={mockProcesses}
          loading={false}
          error={null}
          terminatedName={null}
          onSelect={() => {}}
          onDismiss={() => {}}
          anchorRef={null}
        />
      );

      const input = container.querySelector('input[type="text"]');
      fireEvent.input(input, { target: { value: 'Visual Studio' } });

      const items = container.querySelectorAll('.process-selector-item');
      expect(items.length).toBe(1);
      expect(items[0].querySelector('.process-name').textContent).toBe('devenv.exe');
    });

    it('shows multiple matches when search matches several entries', () => {
      const { container } = render(
        <ProcessSelector
          processes={mockProcesses}
          loading={false}
          error={null}
          terminatedName={null}
          onSelect={() => {}}
          onDismiss={() => {}}
          anchorRef={null}
        />
      );

      const input = container.querySelector('input[type="text"]');
      fireEvent.input(input, { target: { value: '.exe' } });

      const items = container.querySelectorAll('.process-selector-item');
      expect(items.length).toBe(3);
    });
  });

  describe('empty search with no processes shows "未检测到可绑定进程"', () => {
    it('shows empty message when process list is empty and no search text', () => {
      const { container } = render(
        <ProcessSelector
          processes={[]}
          loading={false}
          error={null}
          terminatedName={null}
          onSelect={() => {}}
          onDismiss={() => {}}
          anchorRef={null}
        />
      );

      const message = container.querySelector('.process-selector-message');
      expect(message).not.toBeNull();
      expect(message.textContent).toBe('未检测到可绑定进程');
    });
  });

  describe('search with no matches shows "无匹配进程"', () => {
    it('shows no-match message when search yields zero results', () => {
      const { container } = render(
        <ProcessSelector
          processes={mockProcesses}
          loading={false}
          error={null}
          terminatedName={null}
          onSelect={() => {}}
          onDismiss={() => {}}
          anchorRef={null}
        />
      );

      const input = container.querySelector('input[type="text"]');
      fireEvent.input(input, { target: { value: 'nonexistent_process' } });

      const message = container.querySelector('.process-selector-message');
      expect(message).not.toBeNull();
      expect(message.textContent).toBe('无匹配进程');
    });
  });

  describe('loading state shows "枚举进程中..."', () => {
    it('displays loading message when loading is true', () => {
      const { container } = render(
        <ProcessSelector
          processes={[]}
          loading={true}
          error={null}
          terminatedName={null}
          onSelect={() => {}}
          onDismiss={() => {}}
          anchorRef={null}
        />
      );

      const message = container.querySelector('.process-selector-message');
      expect(message).not.toBeNull();
      expect(message.textContent).toBe('枚举进程中...');
    });
  });

  describe('error state shows error message', () => {
    it('displays error message when error prop is set', () => {
      const errorMsg = '枚举进程失败: 权限不足';
      const { container } = render(
        <ProcessSelector
          processes={[]}
          loading={false}
          error={errorMsg}
          terminatedName={null}
          onSelect={() => {}}
          onDismiss={() => {}}
          anchorRef={null}
        />
      );

      const message = container.querySelector('.process-selector-message.error');
      expect(message).not.toBeNull();
      expect(message.textContent).toBe(errorMsg);
    });
  });

  describe('terminated name warning message', () => {
    it('shows warning with terminated process name', () => {
      const { container } = render(
        <ProcessSelector
          processes={mockProcesses}
          loading={false}
          error={null}
          terminatedName="devenv.exe"
          onSelect={() => {}}
          onDismiss={() => {}}
          anchorRef={null}
        />
      );

      const warning = container.querySelector('.process-selector-warning');
      expect(warning).not.toBeNull();
      expect(warning.textContent).toContain('devenv.exe');
      expect(warning.textContent).toContain('已终止');
    });

    it('does not show warning when terminatedName is null', () => {
      const { container } = render(
        <ProcessSelector
          processes={mockProcesses}
          loading={false}
          error={null}
          terminatedName={null}
          onSelect={() => {}}
          onDismiss={() => {}}
          anchorRef={null}
        />
      );

      const warning = container.querySelector('.process-selector-warning');
      expect(warning).toBeNull();
    });
  });

  describe('dismiss via Escape key', () => {
    it('calls onDismiss when Escape key is pressed', () => {
      const onDismiss = vi.fn();
      render(
        <ProcessSelector
          processes={mockProcesses}
          loading={false}
          error={null}
          terminatedName={null}
          onSelect={() => {}}
          onDismiss={onDismiss}
          anchorRef={null}
        />
      );

      fireEvent.keyDown(document, { key: 'Escape' });
      expect(onDismiss).toHaveBeenCalledTimes(1);
    });
  });

  describe('dismiss via click outside', () => {
    it('calls onDismiss when clicking outside the panel', () => {
      const onDismiss = vi.fn();
      render(
        <ProcessSelector
          processes={mockProcesses}
          loading={false}
          error={null}
          terminatedName={null}
          onSelect={() => {}}
          onDismiss={onDismiss}
          anchorRef={null}
        />
      );

      fireEvent.mouseDown(document.body);
      expect(onDismiss).toHaveBeenCalledTimes(1);
    });

    it('does not call onDismiss when clicking inside the panel', () => {
      const onDismiss = vi.fn();
      const { container } = render(
        <ProcessSelector
          processes={mockProcesses}
          loading={false}
          error={null}
          terminatedName={null}
          onSelect={() => {}}
          onDismiss={onDismiss}
          anchorRef={null}
        />
      );

      const panel = container.querySelector('.process-selector-overlay');
      fireEvent.mouseDown(panel);
      expect(onDismiss).not.toHaveBeenCalled();
    });
  });

  describe('dismiss via close button', () => {
    it('calls onDismiss when close button is clicked', () => {
      const onDismiss = vi.fn();
      const { container } = render(
        <ProcessSelector
          processes={mockProcesses}
          loading={false}
          error={null}
          terminatedName={null}
          onSelect={() => {}}
          onDismiss={onDismiss}
          anchorRef={null}
        />
      );

      const closeBtn = container.querySelector('.process-selector-close');
      fireEvent.click(closeBtn);
      expect(onDismiss).toHaveBeenCalledTimes(1);
    });
  });

  describe('selecting a process calls onSelect with correct ProcessInfo', () => {
    it('calls onSelect with the clicked process info', () => {
      const onSelect = vi.fn();
      const { container } = render(
        <ProcessSelector
          processes={mockProcesses}
          loading={false}
          error={null}
          terminatedName={null}
          onSelect={onSelect}
          onDismiss={() => {}}
          anchorRef={null}
        />
      );

      const items = container.querySelectorAll('.process-selector-item');
      fireEvent.click(items[1]); // Click the second process (code.exe)

      expect(onSelect).toHaveBeenCalledTimes(1);
      expect(onSelect).toHaveBeenCalledWith(mockProcesses[1]);
    });

    it('passes the correct process when selecting after filtering', () => {
      const onSelect = vi.fn();
      const { container } = render(
        <ProcessSelector
          processes={mockProcesses}
          loading={false}
          error={null}
          terminatedName={null}
          onSelect={onSelect}
          onDismiss={() => {}}
          anchorRef={null}
        />
      );

      const input = container.querySelector('input[type="text"]');
      fireEvent.input(input, { target: { value: 'notepad' } });

      const items = container.querySelectorAll('.process-selector-item');
      expect(items.length).toBe(1);
      fireEvent.click(items[0]);

      expect(onSelect).toHaveBeenCalledTimes(1);
      expect(onSelect).toHaveBeenCalledWith(mockProcesses[2]);
    });
  });
});
