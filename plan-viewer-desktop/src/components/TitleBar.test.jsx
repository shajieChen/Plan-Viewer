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
    // Order: pin button, auto-shrink toggle, readme toggle, add-project, focus, close button
    expect(buttons.length).toBe(6);
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
    // Order: pin (0), auto-shrink (1), readme (2), add-project (3), focus (4), close (5)
    expect(buttons.length).toBe(6);
    expect(buttons[1].classList.contains('auto-shrink-toggle')).toBe(true);
    expect(buttons[2].classList.contains('readme-toggle')).toBe(true);
    expect(buttons[5].getAttribute('title')).toBe('最小化到托盘');
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
    // Order: pin (0), auto-shrink (1), readme (2), add-project (3), focus (4), close (5)
    expect(buttons.length).toBe(6);
    expect(buttons[2].classList.contains('readme-toggle')).toBe(true);
    expect(buttons[3].getAttribute('title')).toBe('添加工程');
    expect(buttons[5].getAttribute('title')).toBe('最小化到托盘');
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


describe('TitleBar Focus/Unbind buttons', () => {
  const defaultProps = {
    autoShrink: true,
    onToggleAutoShrink: () => {},
    showReadme: false,
    onToggleReadme: () => {},
    onAddProject: () => {},
    boundProcess: null,
    onFocusClick: () => {},
    onUnbind: () => {},
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders 🎯 button with class "unbound" and tooltip "未绑定进程" when no boundProcess', () => {
    const { container } = render(<TitleBar {...defaultProps} boundProcess={null} />);

    const focusBtn = container.querySelector('.focus-btn');
    expect(focusBtn).not.toBeNull();
    expect(focusBtn.textContent).toBe('🎯');
    expect(focusBtn.classList.contains('unbound')).toBe(true);
    expect(focusBtn.getAttribute('title')).toBe('未绑定进程');
  });

  it('renders 🎯 button with class "bound" and tooltip containing process name when boundProcess set', () => {
    const boundProcess = { pid: 1234, hwnd: 5678, processName: 'devenv.exe', windowTitle: 'MyProject' };
    const { container } = render(<TitleBar {...defaultProps} boundProcess={boundProcess} />);

    const focusBtn = container.querySelector('.focus-btn');
    expect(focusBtn).not.toBeNull();
    expect(focusBtn.classList.contains('bound')).toBe(true);
    expect(focusBtn.getAttribute('title')).toContain('devenv.exe');
  });

  it('renders ✖ button only when boundProcess is set', () => {
    const boundProcess = { pid: 1234, hwnd: 5678, processName: 'notepad.exe', windowTitle: 'Untitled' };
    const { container } = render(<TitleBar {...defaultProps} boundProcess={boundProcess} />);

    const unbindBtn = container.querySelector('.unbind-btn');
    expect(unbindBtn).not.toBeNull();
    expect(unbindBtn.textContent).toBe('✖');
  });

  it('does not render ✖ button when boundProcess is null', () => {
    const { container } = render(<TitleBar {...defaultProps} boundProcess={null} />);

    const unbindBtn = container.querySelector('.unbind-btn');
    expect(unbindBtn).toBeNull();
  });

  it('🎯 button is positioned before close button (✕)', () => {
    const { container } = render(<TitleBar {...defaultProps} boundProcess={null} />);

    const buttons = container.querySelectorAll('button');
    const buttonTexts = Array.from(buttons).map(b => b.getAttribute('title'));
    const focusIndex = buttonTexts.indexOf('未绑定进程');
    const closeIndex = buttonTexts.indexOf('最小化到托盘');

    expect(focusIndex).toBeGreaterThan(-1);
    expect(closeIndex).toBeGreaterThan(-1);
    expect(focusIndex).toBeLessThan(closeIndex);
  });

  it('clicking 🎯 calls onFocusClick', () => {
    const onFocusClick = vi.fn();
    const { container } = render(<TitleBar {...defaultProps} onFocusClick={onFocusClick} />);

    const focusBtn = container.querySelector('.focus-btn');
    fireEvent.click(focusBtn);

    expect(onFocusClick).toHaveBeenCalledTimes(1);
  });

  it('clicking ✖ calls onUnbind', () => {
    const onUnbind = vi.fn();
    const boundProcess = { pid: 1234, hwnd: 5678, processName: 'code.exe', windowTitle: 'VS Code' };
    const { container } = render(<TitleBar {...defaultProps} boundProcess={boundProcess} onUnbind={onUnbind} />);

    const unbindBtn = container.querySelector('.unbind-btn');
    fireEvent.click(unbindBtn);

    expect(onUnbind).toHaveBeenCalledTimes(1);
  });
});
