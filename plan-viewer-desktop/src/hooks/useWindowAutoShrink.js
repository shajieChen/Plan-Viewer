import { useState, useEffect, useRef, useCallback } from 'preact/hooks';
import { getCurrentWindow, currentMonitor } from '@tauri-apps/api/window';
import { LogicalSize } from '@tauri-apps/api/window';

/**
 * Auto-shrink the window after the cursor leaves and dwells outside for
 * `shrinkDelayMs` milliseconds, and restore it after the cursor enters and
 * dwells inside for `restoreDelayMs` milliseconds. Tracks manual resize
 * events to keep savedSize up-to-date.
 *
 * `cursorPresent` is the instantaneous mouse-in-window boolean from
 * `useWindowHover`. We deliberately do NOT consume the debounced `opacityState`,
 * because the dwell-timer cancellation must respond immediately when the cursor
 * leaves — debouncing would let the dwell timer fire before the leave signal arrives.
 *
 * Symmetric cancellation:
 * - Enter dwell (restoreTimer) IS cancelled by an immediate leave.
 * - Leave dwell (shrinkTimer) IS cancelled by an immediate re-entry. If the
 *   cursor returns to the window before `shrinkDelayMs` elapses, the pending
 *   shrink is cancelled and the window stays at its current (enlarged) size —
 *   no shrink-then-restore cycle.
 *
 * @param {{
 *   cursorPresent: boolean,
 *   enabled: boolean,
 *   initialSize: { width: number, height: number },
 *   restoreDelayMs?: number,
 *   shrinkDelayMs?: number,
 * }} options
 * @param {number} [options.restoreDelayMs=1500] - Cursor must dwell inside this long before restore triggers
 * @param {number} [options.shrinkDelayMs=1500] - Cursor must dwell outside this long before shrink triggers
 * @returns {{
 *   savedSize: { width: number, height: number } | null,
 *   isShrunk: boolean,
 *   isWaitingRestore: boolean,
 *   isWaitingShrink: boolean,
 * }}
 */
export function useWindowAutoShrink({
  cursorPresent,
  enabled,
  initialSize,
  restoreDelayMs = 1500,
  shrinkDelayMs = 1500,
}) {
  const [savedSize, setSavedSize] = useState(null);
  const [isShrunk, setIsShrunk] = useState(false);
  const [isWaitingRestore, setIsWaitingRestore] = useState(false);
  const [isWaitingShrink, setIsWaitingShrink] = useState(false);
  const prevCursorRef = useRef(cursorPresent);
  // Flag to distinguish hook-triggered resizes from user-initiated resizes
  const isResizingRef = useRef(false);
  const restoreTimerRef = useRef(null);
  const shrinkTimerRef = useRef(null);
  // Mirror savedSize into a ref so async closures (e.g. the option B chain
  // inside shrinkTimerCallback that schedules performRestore) always read
  // the latest value rather than a stale capture from the render that
  // scheduled the timer.
  const savedSizeRef = useRef(null);

  useEffect(() => {
    savedSizeRef.current = savedSize;
  }, [savedSize]);

  useEffect(() => {
    const prevCursor = prevCursorRef.current;
    prevCursorRef.current = cursorPresent;

    // Cursor entered: cancel any pending leave dwell (symmetric to leave
    // cancelling enter dwell). Then start a fresh restore dwell if we have a
    // saved size to come back to.
    if (prevCursor === false && cursorPresent === true) {
      if (shrinkTimerRef.current) {
        clearTimeout(shrinkTimerRef.current);
        shrinkTimerRef.current = null;
        setIsWaitingShrink(false);
      }
      if (savedSize && !restoreTimerRef.current) {
        restoreTimerRef.current = setTimeout(() => {
          restoreTimerRef.current = null;
          setIsWaitingRestore(false);
          performRestore();
        }, restoreDelayMs);
        setIsWaitingRestore(true);
      }
    }

    // Cursor left: cancel any pending restore (immediate cancellation),
    // then start (or reset) the shrinkTimer if auto-shrink is enabled.
    if (prevCursor === true && cursorPresent === false) {
      if (restoreTimerRef.current) {
        clearTimeout(restoreTimerRef.current);
        restoreTimerRef.current = null;
        setIsWaitingRestore(false);
      }
      if (enabled) {
        // Reset semantics: a second leave during an in-flight shrink dwell
        // restarts the timer rather than stacking parallel timers.
        if (shrinkTimerRef.current) {
          clearTimeout(shrinkTimerRef.current);
        }
        shrinkTimerRef.current = setTimeout(shrinkTimerCallback, shrinkDelayMs);
        setIsWaitingShrink(true);
      }
    }
  }, [cursorPresent, enabled, initialSize, restoreDelayMs, shrinkDelayMs]);

  // Cleanup pending timers on unmount
  useEffect(() => {
    return () => {
      if (restoreTimerRef.current) {
        clearTimeout(restoreTimerRef.current);
      }
      if (shrinkTimerRef.current) {
        clearTimeout(shrinkTimerRef.current);
      }
    };
  }, []);

  async function shrinkTimerCallback() {
    shrinkTimerRef.current = null;
    setIsWaitingShrink(false);
    if (!enabled) return;
    await performShrink();
    // Symmetric cancel: with the enter edge clearing shrinkTimer, control flow
    // can only reach here when the cursor is still outside. No chain hookup.
  }

  async function performShrink() {
    try {
      const win = getCurrentWindow();
      const physicalSize = await win.innerSize();
      const scaleFactor = await win.scaleFactor();

      // Convert physical pixels to logical pixels for comparison
      const currentSize = {
        width: Math.round(physicalSize.width / scaleFactor),
        height: Math.round(physicalSize.height / scaleFactor),
      };

      // No-op if already at or below initialSize (Req 1.2)
      if (currentSize.width <= initialSize.width && currentSize.height <= initialSize.height) {
        return;
      }

      // Save current size in logical pixels before shrinking
      setSavedSize({ width: currentSize.width, height: currentSize.height });

      // Mark as hook-triggered resize so the resize listener ignores it
      isResizingRef.current = true;
      try {
        await win.setSize(new LogicalSize(initialSize.width, initialSize.height));
        setIsShrunk(true);
        // Delay reset to ensure the async resize event from setSize is also ignored
        await new Promise((r) => setTimeout(r, 100));
      } finally {
        isResizingRef.current = false;
      }
    } catch (err) {
      isResizingRef.current = false;
      console.warn('[useWindowAutoShrink] shrink failed:', err);
    }
  }

  async function performRestore() {
    try {
      const win = getCurrentWindow();
      const position = await win.outerPosition();

      const currentSaved = savedSizeRef.current;
      // Guard against null after manual state changes — without a saved
      // size there is nothing to restore to.
      if (!currentSaved) return;
      let clampedWidth = currentSaved.width;
      let clampedHeight = currentSaved.height;

      // Read screen bounds for clamping (Req 7.3)
      try {
        const monitor = await currentMonitor();
        if (monitor) {
          const screenWidth = monitor.size.width;
          const screenHeight = monitor.size.height;

          // Clamp so window fits within screen boundary (Req 7.3)
          // position.x + width ≤ screenWidth, position.y + height ≤ screenHeight
          const maxWidth = screenWidth - position.x;
          const maxHeight = screenHeight - position.y;

          if (clampedWidth > maxWidth) {
            clampedWidth = maxWidth;
          }
          if (clampedHeight > maxHeight) {
            clampedHeight = maxHeight;
          }

          // Ensure we don't go below minimum reasonable size
          if (clampedWidth < initialSize.width) {
            clampedWidth = initialSize.width;
          }
          if (clampedHeight < initialSize.height) {
            clampedHeight = initialSize.height;
          }
        }
      } catch (monitorErr) {
        // If monitor info unavailable, skip clamping and use savedSize directly
        console.warn('[useWindowAutoShrink] monitor info unavailable, skipping clamping:', monitorErr);
      }

      // Mark as hook-triggered resize so the resize listener ignores it
      isResizingRef.current = true;
      try {
        await win.setSize(new LogicalSize(clampedWidth, clampedHeight));
        setIsShrunk(false);
        // Delay reset to ensure the async resize event from setSize is also ignored
        await new Promise((r) => setTimeout(r, 100));
      } finally {
        isResizingRef.current = false;
      }
    } catch (err) {
      // On failure, keep current state unchanged (error handling per design)
      isResizingRef.current = false;
      console.warn('[useWindowAutoShrink] restore failed:', err);
    }
  }

  // Listen for window resize events while in active state to track manual resizes (Req 4.1)
  useEffect(() => {
    // Only track manual resizes while the cursor is inside the window
    if (!cursorPresent) {
      return;
    }

    let unlisten = null;

    const setupListener = async () => {
      const win = getCurrentWindow();
      unlisten = await win.onResized(async ({ payload: size }) => {
        // Ignore resize events triggered by the hook itself
        if (isResizingRef.current) {
          return;
        }

        // Convert physical pixels to logical pixels
        try {
          const scaleFactor = await win.scaleFactor();
          const logicalWidth = Math.round(size.width / scaleFactor);
          const logicalHeight = Math.round(size.height / scaleFactor);
          // Update savedSize with the user-initiated resize dimensions (Req 4.1)
          setSavedSize({ width: logicalWidth, height: logicalHeight });
        } catch (e) {
          // Fallback: use physical size directly
          setSavedSize({ width: size.width, height: size.height });
        }
      });
    };

    setupListener();

    // Cleanup: remove listener on unmount or when cursorPresent changes
    return () => {
      if (unlisten) {
        unlisten();
      }
    };
  }, [cursorPresent]);

  return { savedSize, isShrunk, isWaitingRestore, isWaitingShrink };
}
