import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, fireEvent, waitFor } from '@testing-library/preact';
import { TitleBar } from './TitleBar.jsx';
import { open } from '@tauri-apps/plugin-dialog';

// Mock Tauri APIs
vi.mock('@tauri-apps/api/core', () => ({
  invoke: vi.fn().mockResolvedValue(undefined),
}));

vi.mock('@tauri-apps/plugin-dialog', () => ({
  open: vi.fn().mockResolvedValue(null),
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

  it('toggle button is positioned between pin and readme buttons', () => {
    const { container } = render(
      <TitleBar autoShrink={true} onToggleAutoShrink={() => {}} />
    );

    const buttons = container.querySelectorAll('button');
    // Order: pin button, auto-shrink toggle, readme toggle, add-project, close button
    expect(buttons.length).toBe(5);
    expect(buttons[1].classList.contains('auto-shrink-toggle')).toBe(true);
  });
});

describe('TitleBar README button', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders 📖 button with tooltip "项目导读"', () => {
    const { container } = render(
      <TitleBar autoShrink={true} onToggleAutoShrink={() => {}} showReadme={false} onToggleReadme={() => {}} />
    );

    const readmeBtn = container.querySelector('.readme-toggle');
    expect(readmeBtn).not.toBeNull();
    expect(readmeBtn.textContent).toBe('📖');
    expect(readmeBtn.getAttribute('title')).toBe('项目导读');
  });

  it('is positioned between the auto-shrink button and the close button (index 2 of 4)', () => {
    const { container } = render(
      <TitleBar autoShrink={true} onToggleAutoShrink={() => {}} showReadme={false} onToggleReadme={() => {}} />
    );

    const buttons = container.querySelectorAll('button');
    // Order: pin (0), auto-shrink (1), readme (2), add-project (3), close (4)
    expect(buttons.length).toBe(5);
    expect(buttons[1].classList.contains('auto-shrink-toggle')).toBe(true);
    expect(buttons[2].classList.contains('readme-toggle')).toBe(true);
    expect(buttons[4].getAttribute('title')).toBe('最小化到托盘');
  });

  it('calls onToggleReadme when clicked', () => {
    const onToggleReadme = vi.fn();
    const { container } = render(
      <TitleBar autoShrink={true} onToggleAutoShrink={() => {}} showReadme={false} onToggleReadme={onToggleReadme} />
    );

    const readmeBtn = container.querySelector('.readme-toggle');
    fireEvent.click(readmeBtn);

    expect(onToggleReadme).toHaveBeenCalledTimes(1);
  });

  it('has "active" class when showReadme is true', () => {
    const { container } = render(
      <TitleBar autoShrink={true} onToggleAutoShrink={() => {}} showReadme={true} onToggleReadme={() => {}} />
    );

    const readmeBtn = container.querySelector('.readme-toggle');
    expect(readmeBtn.classList.contains('active')).toBe(true);
  });

  it('does not have "active" class when showReadme is false', () => {
    const { container } = render(
      <TitleBar autoShrink={true} onToggleAutoShrink={() => {}} showReadme={false} onToggleReadme={() => {}} />
    );

    const readmeBtn = container.querySelector('.readme-toggle');
    expect(readmeBtn.classList.contains('active')).toBe(false);
  });
});


describe('TitleBar Add Project button', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders 📂 button with tooltip "添加工程"', () => {
    const { container } = render(
      <TitleBar autoShrink={true} onToggleAutoShrink={() => {}} onAddProject={() => {}} />
    );

    const buttons = container.querySelectorAll('button');
    const addBtn = Array.from(buttons).find(b => b.getAttribute('title') === '添加工程');
    expect(addBtn).not.toBeNull();
    expect(addBtn.textContent).toBe('📂');
  });

  it('is positioned after 📖 (readme) and before ✕ (close)', () => {
    const { container } = render(
      <TitleBar autoShrink={true} onToggleAutoShrink={() => {}} showReadme={false} onToggleReadme={() => {}} onAddProject={() => {}} />
    );

    const buttons = container.querySelectorAll('button');
    // Order: pin (0), auto-shrink (1), readme (2), add-project (3), close (4)
    expect(buttons.length).toBe(5);
    expect(buttons[2].classList.contains('readme-toggle')).toBe(true);
    expect(buttons[3].getAttribute('title')).toBe('添加工程');
    expect(buttons[4].getAttribute('title')).toBe('最小化到托盘');
  });

  it('clicking calls open({ directory: true })', async () => {
    open.mockResolvedValue(null);

    const { container } = render(
      <TitleBar autoShrink={true} onToggleAutoShrink={() => {}} onAddProject={() => {}} />
    );

    const addBtn = Array.from(container.querySelectorAll('button')).find(
      b => b.getAttribute('title') === '添加工程'
    );
    fireEvent.click(addBtn);

    await waitFor(() => {
      expect(open).toHaveBeenCalledTimes(1);
      expect(open).toHaveBeenCalledWith(expect.objectContaining({ directory: true }));
    });
  });

  it('dialog cancel (null) does not call onAddProject', async () => {
    open.mockResolvedValue(null);
    const onAddProject = vi.fn();

    const { container } = render(
      <TitleBar autoShrink={true} onToggleAutoShrink={() => {}} onAddProject={onAddProject} />
    );

    const addBtn = Array.from(container.querySelectorAll('button')).find(
      b => b.getAttribute('title') === '添加工程'
    );
    fireEvent.click(addBtn);

    await waitFor(() => {
      expect(open).toHaveBeenCalledTimes(1);
    });

    expect(onAddProject).not.toHaveBeenCalled();
  });

  it('successful selection calls onAddProject with path', async () => {
    const selectedPath = 'C:\\Projects\\my-project';
    open.mockResolvedValue(selectedPath);
    const onAddProject = vi.fn();

    const { container } = render(
      <TitleBar autoShrink={true} onToggleAutoShrink={() => {}} onAddProject={onAddProject} />
    );

    const addBtn = Array.from(container.querySelectorAll('button')).find(
      b => b.getAttribute('title') === '添加工程'
    );
    fireEvent.click(addBtn);

    await waitFor(() => {
      expect(onAddProject).toHaveBeenCalledTimes(1);
      expect(onAddProject).toHaveBeenCalledWith(selectedPath);
    });
  });
});
