import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/preact';
import { useReadmeLoader } from './useReadmeLoader.js';

describe('useReadmeLoader', () => {
  beforeEach(() => {
    globalThis.fetch = vi.fn();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('returns initial state with null content, false loading, null error', () => {
    const { result } = renderHook(() => useReadmeLoader());
    expect(result.current.content).toBe(null);
    expect(result.current.loading).toBe(false);
    expect(result.current.error).toBe(null);
    expect(typeof result.current.loadFile).toBe('function');
  });

  it('sets loading=true while fetching and false after completion', async () => {
    let resolveResponse;
    globalThis.fetch.mockImplementation(() => new Promise((resolve) => { resolveResponse = resolve; }));

    const { result } = renderHook(() => useReadmeLoader());

    // Capture loadFile reference before calling it
    const loadFile = result.current.loadFile;

    let loadPromise;
    act(() => {
      loadPromise = loadFile('README.md');
    });

    // loading should be true while fetch is pending
    expect(result.current.loading).toBe(true);

    // Now resolve the fetch
    await act(async () => {
      resolveResponse({ ok: true, status: 200, text: () => Promise.resolve('# Hello') });
      await loadPromise;
    });

    expect(result.current.loading).toBe(false);
    expect(result.current.content).toBe('# Hello');
  });

  it('sets content on successful fetch', async () => {
    globalThis.fetch.mockResolvedValue({
      ok: true,
      status: 200,
      text: () => Promise.resolve('# Project README'),
    });

    const { result } = renderHook(() => useReadmeLoader());
    const loadFile = result.current.loadFile;

    await act(async () => {
      await loadFile('README.md');
    });

    expect(result.current.content).toBe('# Project README');
    expect(result.current.error).toBe(null);
    expect(result.current.loading).toBe(false);
  });

  it('sets error to "未找到 README.md" on 404 response', async () => {
    globalThis.fetch.mockResolvedValue({
      ok: false,
      status: 404,
      text: () => Promise.resolve('{"error":"File not found"}'),
    });

    const { result } = renderHook(() => useReadmeLoader());
    const loadFile = result.current.loadFile;

    await act(async () => {
      await loadFile('README.md');
    });

    expect(result.current.error).toBe('未找到 README.md');
    expect(result.current.content).toBe(null);
    expect(result.current.loading).toBe(false);
  });

  it('sets error to "加载失败，请确认服务器运行中" on network error', async () => {
    globalThis.fetch.mockRejectedValue(new TypeError('Failed to fetch'));

    const { result } = renderHook(() => useReadmeLoader());
    const loadFile = result.current.loadFile;

    await act(async () => {
      await loadFile('README.md');
    });

    expect(result.current.error).toBe('加载失败，请确认服务器运行中');
    expect(result.current.content).toBe(null);
    expect(result.current.loading).toBe(false);
  });

  it('sets error to "加载失败，请确认服务器运行中" on timeout (abort)', async () => {
    vi.useFakeTimers();

    // Simulate a fetch that never resolves until aborted
    globalThis.fetch.mockImplementation((_url, options) => {
      return new Promise((_, reject) => {
        options.signal.addEventListener('abort', () => {
          reject(new DOMException('The operation was aborted.', 'AbortError'));
        });
      });
    });

    const { result } = renderHook(() => useReadmeLoader());
    const loadFile = result.current.loadFile;

    let loadPromise;
    act(() => {
      loadPromise = loadFile('README.md');
    });

    expect(result.current.loading).toBe(true);

    // Advance past the 10 second timeout
    await act(async () => {
      vi.advanceTimersByTime(10000);
      await loadPromise;
    });

    expect(result.current.error).toBe('加载失败，请确认服务器运行中');
    expect(result.current.content).toBe(null);
    expect(result.current.loading).toBe(false);

    vi.useRealTimers();
  });

  it('sets content to empty string when file exists but is empty (no error)', async () => {
    globalThis.fetch.mockResolvedValue({
      ok: true,
      status: 200,
      text: () => Promise.resolve(''),
    });

    const { result } = renderHook(() => useReadmeLoader());
    const loadFile = result.current.loadFile;

    await act(async () => {
      await loadFile('README.md');
    });

    expect(result.current.content).toBe('');
    expect(result.current.error).toBe(null);
    expect(result.current.loading).toBe(false);
  });

  it('fetches from correct URL with encoded path', async () => {
    globalThis.fetch.mockResolvedValue({
      ok: true,
      status: 200,
      text: () => Promise.resolve('content'),
    });

    const { result } = renderHook(() => useReadmeLoader());
    const loadFile = result.current.loadFile;

    await act(async () => {
      await loadFile('docs/getting started.md');
    });

    expect(globalThis.fetch).toHaveBeenCalledWith(
      'http://localhost:8000/api/file?path=docs%2Fgetting%20started.md',
      expect.objectContaining({ signal: expect.any(AbortSignal) })
    );
  });

  it('aborts previous request when loadFile is called again', async () => {
    let callCount = 0;

    globalThis.fetch.mockImplementation((_url, options) => {
      callCount++;
      const currentCall = callCount;
      return new Promise((resolve, reject) => {
        options.signal.addEventListener('abort', () => {
          reject(new DOMException('The operation was aborted.', 'AbortError'));
        });
        // Only second call resolves
        if (currentCall === 2) {
          resolve({ ok: true, status: 200, text: () => Promise.resolve('second content') });
        }
      });
    });

    const { result } = renderHook(() => useReadmeLoader());
    const loadFile = result.current.loadFile;

    // Start first request (will never resolve on its own, will be aborted)
    act(() => {
      loadFile('first.md');
    });

    // Start second request — this aborts the first and resolves
    await act(async () => {
      await loadFile('second.md');
    });

    expect(result.current.content).toBe('second content');
    expect(result.current.error).toBe(null);
  });
});
