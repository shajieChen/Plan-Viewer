import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, fireEvent } from '@testing-library/preact';
import { TitleBar } from './TitleBar.jsx';

// Mock Tauri APIs
vi.mock('@tauri-apps/api/core', () => ({
  invoke: vi.fn().mockResolvedValue(undefined),
}));

const mockHide = vi.fn().mockResolvedValue(undefined);
vi.mock('@tauri-apps/api/window', () => ({
  getCurrentWindow: () => ({
    hide: mockHide,
  }),
}));

describe('TitleBar Auto-Shrink toggle', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders toggle button with ⇲ icon when autoShrink is enabled', () => {
    const { container } = render(
      <TitleBar autoShrink={true} onToggleAutoShrink={() => {}} />
    );

    const toggle = container.querySelector('.auto-shrink-toggle');
    expect(toggle).not.toBeNull();
    expect(toggle.textContent).toBe('⇲');
  });

  it('renders toggle button with ⇱ icon when autoShrink is disabled', () => {
    const { container } = render(
      <TitleBar autoShrink={false} onToggleAutoShrink={() => {}} />
    );

    const toggle = container.querySelector('.auto-shrink-toggle');
    expect(toggle).not.toBeNull();
    expect(toggle.textContent).toBe('⇱');
  });

  it('calls onToggleAutoShrink callback when toggle button is clicked', () => {
    const onToggle = vi.fn();
    const { container } = render(
      <TitleBar autoShrink={true} onToggleAutoShrink={onToggle} />
    );

    const toggle = container.querySelector('.auto-shrink-toggle');
    fireEvent.click(toggle);

    expect(onToggle).toHaveBeenCalledTimes(1);
  });

  it('has "enabled" class when autoShrink is true', () => {
    const { container } = render(
      <TitleBar autoShrink={true} onToggleAutoShrink={() => {}} />
    );

    const toggle = container.querySelector('.auto-shrink-toggle');
    expect(toggle.classList.contains('enabled')).toBe(true);
    expect(toggle.classList.contains('disabled')).toBe(false);
  });

  it('has "disabled" class when autoShrink is false', () => {
    const { container } = render(
      <TitleBar autoShrink={false} onToggleAutoShrink={() => {}} />
    );

    const toggle = container.querySelector('.auto-shrink-toggle');
    expect(toggle.classList.contains('disabled')).toBe(true);
    expect(toggle.classList.contains('enabled')).toBe(false);
  });

  it('toggle button is positioned between pin and close buttons', () => {
    const { container } = render(
      <TitleBar autoShrink={true} onToggleAutoShrink={() => {}} />
    );

    const buttons = container.querySelectorAll('button');
    // Order: pin button, auto-shrink toggle, close button
    expect(buttons.length).toBe(3);
    expect(buttons[1].classList.contains('auto-shrink-toggle')).toBe(true);
  });
});
