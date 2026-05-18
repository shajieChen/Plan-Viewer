import { useState, useEffect, useRef, useCallback } from 'preact/hooks';
import { getCurrentWindow, currentMonitor } from '@tauri-apps/api/window';
import { LogicalSize } from '@tauri-apps/api/window';

/**
 * Auto-shrink the window when hover state transitions from active → idle,
 * and restore it when transitioning from idle → active (after a dwell delay).
 * Tracks manual resize events to keep savedSize up-to-date.
 *
 * @param {{ hoverState: 'idle' | 'active', enabled: boolean, initialSize: { width: number, height: number }, restoreDelayMs?: number }} options
 * @param {number} [options.restoreDelayMs=2000] - Milliseconds the cursor must dwell before restore triggers
 * @returns {{ savedSize: { width: number, height: number } | null, isShrunk: boolean, isWaitingRestore: boolean }}
 */
export function useWindowAutoShrink({ hoverState, enabled, initialSize, restoreDelayMs = 2000 }) {
  const [savedSize, setSavedSize] = useState(null);
  const [isShrunk, setIsShrunk] = useState(false);
  const [isWaitingRestore, setIsWaitingRestore] = useState(false);
  const prevHoverStateRef = useRef(hoverState);
  // Flag to distinguish hook-triggered resizes from user-initiated resizes
  const isResizingRef = useRef(false);
  const restoreTimerRef = useRef(null);

  useEffect(() => {
    const prevState = prevHoverStateRef.current;
    prevHoverStateRef.current = hoverState;

    // Restore: idle → active transition when savedSize exists — start dwell timer
    if (prevState === 'idle' && hoverState === 'active' && savedSize) {
      restoreTimerRef.current = setTimeout(() => {
        restoreTimerRef.current = null;
        setIsWaitingRestore(false);
        performRestore();
      }, restoreDelayMs);
      setIsWaitingRestore(true);
    }

    // Shrink: active → idle transition
    if (prevState === 'active' && hoverState === 'idle') {
      // Cancel pending restore timer if still waiting
      if (restoreTimerRef.current) {
        clearTimeout(restoreTimerRef.current);
        restoreTimerRef.current = null;
        setIsWaitingRestore(false);
      }
      // Perform shrink if enabled
      if (enabled) {
        performShrink();
      }
    }
  }, [hoverState, enabled, initialSize, restoreDelayMs]);

  // Cleanup restore timer on unmount
  useEffect(() => {
    return () => {
      if (restoreTimerRef.current) {
        clearTimeout(restoreTimerRef.current);
      }
    };
  }, []);

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

      let clampedWidth = savedSize.width;
      let clampedHeight = savedSize.height;

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
    // Only track manual resizes when in active state
    if (hoverState !== 'active') {
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

    // Cleanup: remove listener on unmount or when hoverState changes
    return () => {
      if (unlisten) {
        unlisten();
      }
    };
  }, [hoverState]);

  return { savedSize, isShrunk, isWaitingRestore };
}
