import { useState, useEffect, useRef } from 'preact/hooks';

/**
 * Track mouse enter/leave on the document and produce two signals:
 *
 * - `cursorPresent`: instantaneous boolean — `true` on mouseenter, `false` on mouseleave.
 *   Use this to drive logic that must respond immediately to the cursor leaving
 *   (e.g. cancelling a dwell timer).
 * - `opacityState`: debounced `'idle' | 'active'` — turns `'active'` immediately on
 *   mouseenter, returns to `'idle'` 3s after mouseleave. Use this to drive transparency
 *   so the window does not flicker when the user briefly grazes the edge.
 *
 * @returns {{ opacityState: 'idle' | 'active', cursorPresent: boolean }}
 */
export function useWindowHover() {
  const [opacityState, setOpacityState] = useState('idle');
  const [cursorPresent, setCursorPresent] = useState(false);
  const idleTimeoutRef = useRef(null);

  useEffect(() => {
    const handleEnter = () => {
      if (idleTimeoutRef.current) {
        clearTimeout(idleTimeoutRef.current);
        idleTimeoutRef.current = null;
      }
      setCursorPresent(true);
      setOpacityState('active');
    };

    const handleLeave = () => {
      setCursorPresent(false);
      idleTimeoutRef.current = setTimeout(() => {
        setOpacityState('idle');
        idleTimeoutRef.current = null;
      }, 3000);
    };

    document.addEventListener('mouseenter', handleEnter);
    document.addEventListener('mouseleave', handleLeave);

    return () => {
      document.removeEventListener('mouseenter', handleEnter);
      document.removeEventListener('mouseleave', handleLeave);
      if (idleTimeoutRef.current) clearTimeout(idleTimeoutRef.current);
    };
  }, []);

  return { opacityState, cursorPresent };
}
