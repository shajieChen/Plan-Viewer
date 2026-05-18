import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/preact';
import { useWindowAutoShrink } from './useWindowAutoShrink.js';

// Mock Tauri window API
const mockSetSize = vi.fn().mockResolvedValue(undefined);
const mockInnerSize = vi.fn().mockResolvedValue({ width: 800, height: 600 });
const mockScaleFactor = vi.fn().mockResolvedValue(1);
const mockOuterPosition = vi.fn().mockResolvedValue({ x: 100, y: 100 });
const mockOnResized = vi.fn().mockResolvedValue(() => {});
const mockCurrentMonitor = vi.fn().mockResolvedValue({
  size: { width: 1920, height: 1080 },
});

vi.mock('@tauri-apps/api/window', () => ({
  getCurrentWindow: () => ({
    setSize: mockSetSize,
    innerSize: mockInnerSize,
    scaleFactor: mockScaleFactor,
    outerPosition: mockOuterPosition,
    onResized: mockOnResized,
  }),
  currentMonitor: (...args) => mockCurrentMonitor(...args),
  LogicalSize: class LogicalSize {
    constructor(width, height) {
      this.width = width;
      this.height = height;
    }
  },
}));

describe('useWindowAutoShrink', () => {
  const initialSize = { width: 400, height: 300 };

  beforeEach(() => {
    vi.clearAllMocks();
    mockInnerSize.mockResolvedValue({ width: 800, height: 600 });
    mockOuterPosition.mockResolvedValue({ x: 100, y: 100 });
    mockCurrentMonitor.mockResolvedValue({ size: { width: 1920, height: 1080 } });
    mockOnResized.mockResolvedValue(() => {});
  });

  // Helper: advance fake timers and flush microtasks so async performShrink/Restore can resolve.
  async function advanceAndFlush(ms) {
    await act(async () => {
      vi.advanceTimersByTime(ms);
      // Flush a couple of microtask rounds for the awaited promises in performShrink/Restore
      await Promise.resolve();
      await Promise.resolve();
    });
  }

  it('should return initial state with savedSize null and isShrunk false', () => {
    const { result } = renderHook(() =>
      useWindowAutoShrink({ cursorPresent: true, enabled: true, initialSize })
    );

    expect(result.current.savedSize).toBeNull();
    expect(result.current.isShrunk).toBe(false);
    expect(result.current.isWaitingRestore).toBe(false);
  });

  it('should shrink window after shrink dwell delay when cursor leaves', async () => {
    vi.useFakeTimers();
    const { result, rerender } = renderHook(
      ({ cursorPresent }) => useWindowAutoShrink({ cursorPresent, enabled: true, initialSize }),
      { initialProps: { cursorPresent: true } }
    );

    // Cursor leaves — shrink does NOT fire yet
    rerender({ cursorPresent: false });
    expect(mockSetSize).not.toHaveBeenCalled();
    expect(result.current.isWaitingShrink).toBe(true);

    // Advance past shrink dwell
    await advanceAndFlush(1500);
    vi.useRealTimers();

    await vi.waitFor(() => {
      expect(mockSetSize).toHaveBeenCalledTimes(1);
    });

    const sizeArg = mockSetSize.mock.calls[0][0];
    expect(sizeArg.width).toBe(400);
    expect(sizeArg.height).toBe(300);
    expect(result.current.savedSize).toEqual({ width: 800, height: 600 });
    expect(result.current.isShrunk).toBe(true);
  });

  it('should NOT shrink when enabled is false', async () => {
    const { rerender } = renderHook(
      ({ cursorPresent }) => useWindowAutoShrink({ cursorPresent, enabled: false, initialSize }),
      { initialProps: { cursorPresent: true } }
    );

    rerender({ cursorPresent: false });

    // Give time for any async operations
    await new Promise((r) => setTimeout(r, 50));

    expect(mockSetSize).not.toHaveBeenCalled();
  });

  it('should NOT shrink when window is already at or below initialSize', async () => {
    mockInnerSize.mockResolvedValue({ width: 400, height: 300 });

    const { result, rerender } = renderHook(
      ({ cursorPresent }) => useWindowAutoShrink({ cursorPresent, enabled: true, initialSize }),
      { initialProps: { cursorPresent: true } }
    );

    vi.useFakeTimers();
    rerender({ cursorPresent: false });
    await advanceAndFlush(1500);
    vi.useRealTimers();

    // Give time for async operations
    await new Promise((r) => setTimeout(r, 50));

    expect(mockSetSize).not.toHaveBeenCalled();
    expect(result.current.savedSize).toBeNull();
    expect(result.current.isShrunk).toBe(false);
  });

  it('should NOT shrink when window is below initialSize', async () => {
    mockInnerSize.mockResolvedValue({ width: 350, height: 250 });

    const { result, rerender } = renderHook(
      ({ cursorPresent }) => useWindowAutoShrink({ cursorPresent, enabled: true, initialSize }),
      { initialProps: { cursorPresent: true } }
    );

    vi.useFakeTimers();
    rerender({ cursorPresent: false });
    await advanceAndFlush(1500);
    vi.useRealTimers();

    await new Promise((r) => setTimeout(r, 50));

    expect(mockSetSize).not.toHaveBeenCalled();
    expect(result.current.savedSize).toBeNull();
  });

  it('should NOT shrink on cursor=false → cursor=false (no transition)', async () => {
    const { rerender } = renderHook(
      ({ cursorPresent }) => useWindowAutoShrink({ cursorPresent, enabled: true, initialSize }),
      { initialProps: { cursorPresent: false } }
    );

    rerender({ cursorPresent: false });

    await new Promise((r) => setTimeout(r, 50));

    expect(mockSetSize).not.toHaveBeenCalled();
  });

  it('should handle API errors gracefully', async () => {
    const consoleSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
    mockInnerSize.mockRejectedValue(new Error('API unavailable'));

    const { result, rerender } = renderHook(
      ({ cursorPresent }) => useWindowAutoShrink({ cursorPresent, enabled: true, initialSize }),
      { initialProps: { cursorPresent: true } }
    );

    vi.useFakeTimers();
    rerender({ cursorPresent: false });
    await advanceAndFlush(1500);
    vi.useRealTimers();

    await new Promise((r) => setTimeout(r, 50));

    // Should not crash, state should remain unchanged
    expect(result.current.savedSize).toBeNull();
    expect(result.current.isShrunk).toBe(false);
    expect(consoleSpy).toHaveBeenCalled();

    consoleSpy.mockRestore();
  });

  describe('manual resize tracking', () => {
    it('should register onResized listener while cursor is present', async () => {
      renderHook(() =>
        useWindowAutoShrink({ cursorPresent: true, enabled: true, initialSize })
      );

      await new Promise((r) => setTimeout(r, 50));

      expect(mockOnResized).toHaveBeenCalledTimes(1);
      expect(typeof mockOnResized.mock.calls[0][0]).toBe('function');
    });

    it('should NOT register onResized listener when cursor is absent', async () => {
      renderHook(() =>
        useWindowAutoShrink({ cursorPresent: false, enabled: true, initialSize })
      );

      await new Promise((r) => setTimeout(r, 50));

      expect(mockOnResized).not.toHaveBeenCalled();
    });

    it('should update savedSize on user-initiated resize while cursor is present', async () => {
      let resizeCallback = null;
      mockOnResized.mockImplementation((cb) => {
        resizeCallback = cb;
        return Promise.resolve(() => {});
      });

      const { result } = renderHook(() =>
        useWindowAutoShrink({ cursorPresent: true, enabled: true, initialSize })
      );

      await new Promise((r) => setTimeout(r, 50));

      // Simulate user resize event
      act(() => {
        resizeCallback({ payload: { width: 900, height: 700 } });
      });

      await vi.waitFor(() => {
        expect(result.current.savedSize).toEqual({ width: 900, height: 700 });
      });
    });

    it('should call unlisten when cursor leaves', async () => {
      const mockUnlisten = vi.fn();
      mockOnResized.mockResolvedValue(mockUnlisten);

      const { rerender } = renderHook(
        ({ cursorPresent }) => useWindowAutoShrink({ cursorPresent, enabled: true, initialSize }),
        { initialProps: { cursorPresent: true } }
      );

      await new Promise((r) => setTimeout(r, 50));

      // Cursor leaves should trigger cleanup
      rerender({ cursorPresent: false });

      await new Promise((r) => setTimeout(r, 50));

      expect(mockUnlisten).toHaveBeenCalled();
    });

    it('should update savedSize to most recent user resize', async () => {
      let resizeCallback = null;
      mockOnResized.mockImplementation((cb) => {
        resizeCallback = cb;
        return Promise.resolve(() => {});
      });

      const { result } = renderHook(() =>
        useWindowAutoShrink({ cursorPresent: true, enabled: true, initialSize })
      );

      await new Promise((r) => setTimeout(r, 50));

      // Simulate multiple user resize events
      act(() => {
        resizeCallback({ payload: { width: 600, height: 400 } });
      });
      act(() => {
        resizeCallback({ payload: { width: 1000, height: 800 } });
      });

      // savedSize should reflect the most recent resize
      await vi.waitFor(() => {
        expect(result.current.savedSize).toEqual({ width: 1000, height: 800 });
      });
    });
  });

  describe('restore behavior (cursor enters)', () => {
    afterEach(() => {
      vi.useRealTimers();
    });

    it('should restore window to savedSize when cursor enters (false → true)', async () => {
      const { result, rerender } = renderHook(
        ({ cursorPresent }) => useWindowAutoShrink({ cursorPresent, enabled: true, initialSize }),
        { initialProps: { cursorPresent: true } }
      );

      // First: shrink (cursor leaves)
      vi.useFakeTimers();
      rerender({ cursorPresent: false });
      await advanceAndFlush(1500);
      vi.useRealTimers();

      await vi.waitFor(() => {
        expect(mockSetSize).toHaveBeenCalledTimes(1);
      });

      expect(result.current.savedSize).toEqual({ width: 800, height: 600 });
      expect(result.current.isShrunk).toBe(true);

      mockSetSize.mockClear();

      // Switch to fake timers for restore dwell
      vi.useFakeTimers();

      // Then: restore (cursor enters)
      rerender({ cursorPresent: true });

      // Advance past dwell delay
      await act(async () => {
        vi.advanceTimersByTime(1500);
      });

      // Switch back for async assertions
      vi.useRealTimers();

      await vi.waitFor(() => {
        expect(mockSetSize).toHaveBeenCalledTimes(1);
      });

      const restoreArg = mockSetSize.mock.calls[0][0];
      expect(restoreArg.width).toBe(800);
      expect(restoreArg.height).toBe(600);

      await vi.waitFor(() => {
        expect(result.current.isShrunk).toBe(false);
      });
    });

    it('should do nothing on cursor enter when no savedSize exists', async () => {
      const { result, rerender } = renderHook(
        ({ cursorPresent }) => useWindowAutoShrink({ cursorPresent, enabled: true, initialSize }),
        { initialProps: { cursorPresent: false } }
      );

      // cursor enters without any prior shrink (no savedSize)
      rerender({ cursorPresent: true });

      await new Promise((r) => setTimeout(r, 50));

      expect(mockSetSize).not.toHaveBeenCalled();
      expect(result.current.isShrunk).toBe(false);
    });

    it('should clamp restored size to fit within screen boundary', async () => {
      // Window positioned near bottom-right edge
      mockOuterPosition.mockResolvedValue({ x: 1700, y: 900 });
      // Screen is 1920×1080, so max available: 220×180
      mockCurrentMonitor.mockResolvedValue({ size: { width: 1920, height: 1080 } });

      const { result, rerender } = renderHook(
        ({ cursorPresent }) => useWindowAutoShrink({ cursorPresent, enabled: true, initialSize }),
        { initialProps: { cursorPresent: true } }
      );

      // Shrink first
      vi.useFakeTimers();
      rerender({ cursorPresent: false });
      await advanceAndFlush(1500);
      vi.useRealTimers();

      await vi.waitFor(() => {
        expect(mockSetSize).toHaveBeenCalledTimes(1);
      });

      // savedSize = 800×600, but position is near edge
      expect(result.current.savedSize).toEqual({ width: 800, height: 600 });
      mockSetSize.mockClear();

      // Switch to fake timers for restore dwell
      vi.useFakeTimers();

      // Restore
      rerender({ cursorPresent: true });

      // Advance past dwell delay
      await act(async () => {
        vi.advanceTimersByTime(1500);
      });

      // Switch back for async assertions
      vi.useRealTimers();

      await vi.waitFor(() => {
        expect(mockSetSize).toHaveBeenCalledTimes(1);
      });

      const restoreArg = mockSetSize.mock.calls[0][0];
      // maxWidth = 1920 - 1700 = 220, but min is initialSize.width (400)
      // So clamped to initialSize.width since 220 < 400
      expect(restoreArg.width).toBe(400);
      // maxHeight = 1080 - 900 = 180, but min is initialSize.height (300)
      // So clamped to initialSize.height since 180 < 300
      expect(restoreArg.height).toBe(300);
    });

    it('should clamp width only when it exceeds screen boundary', async () => {
      // Window positioned where only width overflows
      mockOuterPosition.mockResolvedValue({ x: 1400, y: 100 });
      mockCurrentMonitor.mockResolvedValue({ size: { width: 1920, height: 1080 } });

      const { result, rerender } = renderHook(
        ({ cursorPresent }) => useWindowAutoShrink({ cursorPresent, enabled: true, initialSize }),
        { initialProps: { cursorPresent: true } }
      );

      // Shrink
      vi.useFakeTimers();
      rerender({ cursorPresent: false });
      await advanceAndFlush(1500);
      vi.useRealTimers();

      await vi.waitFor(() => {
        expect(mockSetSize).toHaveBeenCalledTimes(1);
      });

      mockSetSize.mockClear();

      // Switch to fake timers for restore dwell
      vi.useFakeTimers();

      // Restore — maxWidth = 1920 - 1400 = 520 (less than 800), maxHeight = 1080 - 100 = 980 (enough)
      rerender({ cursorPresent: true });

      // Advance past dwell delay
      await act(async () => {
        vi.advanceTimersByTime(1500);
      });

      // Switch back for async assertions
      vi.useRealTimers();

      await vi.waitFor(() => {
        expect(mockSetSize).toHaveBeenCalledTimes(1);
      });

      const restoreArg = mockSetSize.mock.calls[0][0];
      expect(restoreArg.width).toBe(520);   // Clamped
      expect(restoreArg.height).toBe(600);  // Not clamped (600 < 980)
    });

    it('should use savedSize directly when monitor info is unavailable', async () => {
      mockCurrentMonitor.mockRejectedValue(new Error('Monitor unavailable'));

      const consoleSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});

      const { result, rerender } = renderHook(
        ({ cursorPresent }) => useWindowAutoShrink({ cursorPresent, enabled: true, initialSize }),
        { initialProps: { cursorPresent: true } }
      );

      // Shrink
      vi.useFakeTimers();
      rerender({ cursorPresent: false });
      await advanceAndFlush(1500);
      vi.useRealTimers();

      await vi.waitFor(() => {
        expect(mockSetSize).toHaveBeenCalledTimes(1);
      });

      mockSetSize.mockClear();

      // Switch to fake timers for restore dwell
      vi.useFakeTimers();

      // Restore — monitor call fails, should use savedSize without clamping
      rerender({ cursorPresent: true });

      // Advance past dwell delay
      await act(async () => {
        vi.advanceTimersByTime(1500);
      });

      // Switch back for async assertions
      vi.useRealTimers();

      await vi.waitFor(() => {
        expect(mockSetSize).toHaveBeenCalledTimes(1);
      });

      const restoreArg = mockSetSize.mock.calls[0][0];
      expect(restoreArg.width).toBe(800);
      expect(restoreArg.height).toBe(600);

      await vi.waitFor(() => {
        expect(result.current.isShrunk).toBe(false);
      });

      consoleSpy.mockRestore();
    });

    it('should use savedSize directly when currentMonitor returns null', async () => {
      mockCurrentMonitor.mockResolvedValue(null);

      const { result, rerender } = renderHook(
        ({ cursorPresent }) => useWindowAutoShrink({ cursorPresent, enabled: true, initialSize }),
        { initialProps: { cursorPresent: true } }
      );

      // Shrink
      vi.useFakeTimers();
      rerender({ cursorPresent: false });
      await advanceAndFlush(1500);
      vi.useRealTimers();

      await vi.waitFor(() => {
        expect(mockSetSize).toHaveBeenCalledTimes(1);
      });

      mockSetSize.mockClear();

      // Switch to fake timers for restore dwell
      vi.useFakeTimers();

      // Restore — monitor is null, should use savedSize directly
      rerender({ cursorPresent: true });

      // Advance past dwell delay
      await act(async () => {
        vi.advanceTimersByTime(1500);
      });

      // Switch back for async assertions
      vi.useRealTimers();

      await vi.waitFor(() => {
        expect(mockSetSize).toHaveBeenCalledTimes(1);
      });

      const restoreArg = mockSetSize.mock.calls[0][0];
      expect(restoreArg.width).toBe(800);
      expect(restoreArg.height).toBe(600);

      await vi.waitFor(() => {
        expect(result.current.isShrunk).toBe(false);
      });
    });

    it('should handle restore API errors gracefully', async () => {
      const consoleSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
      mockOuterPosition.mockRejectedValue(new Error('Position unavailable'));

      const { result, rerender } = renderHook(
        ({ cursorPresent }) => useWindowAutoShrink({ cursorPresent, enabled: true, initialSize }),
        { initialProps: { cursorPresent: true } }
      );

      // Shrink first
      vi.useFakeTimers();
      rerender({ cursorPresent: false });
      await advanceAndFlush(1500);
      vi.useRealTimers();

      await vi.waitFor(() => {
        expect(mockSetSize).toHaveBeenCalledTimes(1);
      });

      mockSetSize.mockClear();

      // Switch to fake timers for restore dwell
      vi.useFakeTimers();

      // Restore — outerPosition fails
      rerender({ cursorPresent: true });

      // Advance past dwell delay
      await act(async () => {
        vi.advanceTimersByTime(1500);
      });

      // Switch back for async assertions
      vi.useRealTimers();

      await new Promise((r) => setTimeout(r, 50));

      // setSize should not have been called for restore since outerPosition failed
      expect(mockSetSize).not.toHaveBeenCalled();
      // isShrunk remains true since restore failed
      expect(result.current.isShrunk).toBe(true);
      expect(consoleSpy).toHaveBeenCalled();

      consoleSpy.mockRestore();
    });

    it('should cancel restore if mouse leaves before dwell delay elapses', async () => {
      const { result, rerender } = renderHook(
        ({ cursorPresent }) => useWindowAutoShrink({ cursorPresent, enabled: true, initialSize }),
        { initialProps: { cursorPresent: true } }
      );

      // Shrink
      vi.useFakeTimers();
      rerender({ cursorPresent: false });
      await advanceAndFlush(1500);
      vi.useRealTimers();
      await vi.waitFor(() => { expect(mockSetSize).toHaveBeenCalledTimes(1); });
      mockSetSize.mockClear();

      vi.useFakeTimers();

      // Cursor enters (starts 1.5s restore dwell timer)
      rerender({ cursorPresent: true });
      expect(result.current.isWaitingRestore).toBe(true);

      // Cursor leaves at 800ms (before 1.5s restore dwell)
      vi.advanceTimersByTime(800);
      rerender({ cursorPresent: false });

      // Restore was cancelled immediately
      expect(result.current.isWaitingRestore).toBe(false);
      // Shrink dwell is now active
      expect(result.current.isWaitingShrink).toBe(true);

      // Advance to just before shrink dwell completes (total elapsed since leave: 1499ms)
      vi.advanceTimersByTime(1499);
      vi.useRealTimers();

      // Restore should NOT have fired (it was cancelled)
      // Shrink also has not fired yet (still inside dwell)
      expect(mockSetSize).not.toHaveBeenCalled();
      expect(result.current.isShrunk).toBe(true);
    });

    it('should set isWaitingRestore during dwell wait period', async () => {
      const { result, rerender } = renderHook(
        ({ cursorPresent }) => useWindowAutoShrink({ cursorPresent, enabled: true, initialSize }),
        { initialProps: { cursorPresent: true } }
      );

      // Shrink
      vi.useFakeTimers();
      rerender({ cursorPresent: false });
      await advanceAndFlush(1500);
      vi.useRealTimers();
      await vi.waitFor(() => { expect(mockSetSize).toHaveBeenCalledTimes(1); });
      mockSetSize.mockClear();

      vi.useFakeTimers();

      // Cursor enters — waiting starts
      rerender({ cursorPresent: true });
      expect(result.current.isWaitingRestore).toBe(true);

      // After dwell completes
      await act(async () => { vi.advanceTimersByTime(1500); });
      vi.useRealTimers();

      await vi.waitFor(() => {
        expect(result.current.isWaitingRestore).toBe(false);
      });
    });
  });
});
