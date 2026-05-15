import { useState, useEffect, useRef } from 'preact/hooks';

/**
 * Track mouse enter/leave on the document to toggle transparency state.
 * Returns "idle" or "active". Transitions back to idle after 1.5s delay.
 */
export function useWindowHover() {
  const [state, setState] = useState('idle');
  const timeoutRef = useRef(null);

  useEffect(() => {
    const handleEnter = () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
        timeoutRef.current = null;
      }
      setState('active');
    };

    const handleLeave = () => {
      timeoutRef.current = setTimeout(() => {
        setState('idle');
      }, 3000);
    };

    document.addEventListener('mouseenter', handleEnter);
    document.addEventListener('mouseleave', handleLeave);

    return () => {
      document.removeEventListener('mouseenter', handleEnter);
      document.removeEventListener('mouseleave', handleLeave);
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    };
  }, []);

  return state;
}
