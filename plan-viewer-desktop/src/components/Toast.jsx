import { useEffect } from 'preact/hooks';

export function Toast({ message, type = 'error', onDismiss }) {
  useEffect(() => {
    const timer = setTimeout(onDismiss, 3000);
    return () => clearTimeout(timer);
  }, [message]);

  return (
    <div class={`toast toast-${type}`}>
      <span class="toast-message">{message}</span>
      <button class="toast-close" onClick={onDismiss} aria-label="Dismiss notification">✕</button>
    </div>
  );
}
