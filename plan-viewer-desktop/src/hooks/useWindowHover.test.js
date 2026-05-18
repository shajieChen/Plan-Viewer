import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/preact';
import { useWindowHover } from './useWindowHover.js';

function fireDocumentEvent(eventName) {
  document.dispatchEvent(new Event(eventName));
}

describe('useWindowHover', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('returns { opacityState: "idle", cursorPresent: false } initially', () => {
    const { result } = renderHook(() => useWindowHover());
    expect(result.current.opacityState).toBe('idle');
    expect(result.current.cursorPresent).toBe(false);
  });

  it('on mouseenter sets cursorPresent=true and opacityState="active" immediately', () => {
    const { result } = renderHook(() => useWindowHover());

    act(() => {
      fireDocumentEvent('mouseenter');
    });

    expect(result.current.cursorPresent).toBe(true);
    expect(result.current.opacityState).toBe('active');
  });

  it('on mouseleave sets cursorPresent=false immediately, opacityState stays "active" until 3s elapses', () => {
    const { result } = renderHook(() => useWindowHover());

    act(() => {
      fireDocumentEvent('mouseenter');
    });

    act(() => {
      fireDocumentEvent('mouseleave');
    });

    expect(result.current.cursorPresent).toBe(false);
    expect(result.current.opacityState).toBe('active');

    act(() => {
      vi.advanceTimersByTime(2999);
    });
    expect(result.current.opacityState).toBe('active');

    act(() => {
      vi.advanceTimersByTime(1);
    });
    expect(result.current.opacityState).toBe('idle');
  });

  it('mouseenter within 3s of mouseleave keeps opacityState="active" (no flicker)', () => {
    const { result } = renderHook(() => useWindowHover());

    act(() => {
      fireDocumentEvent('mouseenter');
    });
    act(() => {
      fireDocumentEvent('mouseleave');
    });

    act(() => {
      vi.advanceTimersByTime(1000);
    });

    act(() => {
      fireDocumentEvent('mouseenter');
    });

    expect(result.current.cursorPresent).toBe(true);
    expect(result.current.opacityState).toBe('active');

    act(() => {
      vi.advanceTimersByTime(5000);
    });
    expect(result.current.opacityState).toBe('active');
    expect(result.current.cursorPresent).toBe(true);
  });

  it('cleans up listeners and pending timer on unmount', () => {
    const removeSpy = vi.spyOn(document, 'removeEventListener');
    const { result, unmount } = renderHook(() => useWindowHover());

    act(() => {
      fireDocumentEvent('mouseenter');
    });
    act(() => {
      fireDocumentEvent('mouseleave');
    });

    unmount();

    expect(removeSpy).toHaveBeenCalledWith('mouseenter', expect.any(Function));
    expect(removeSpy).toHaveBeenCalledWith('mouseleave', expect.any(Function));

    expect(() => {
      vi.advanceTimersByTime(5000);
    }).not.toThrow();

    removeSpy.mockRestore();
  });
});
