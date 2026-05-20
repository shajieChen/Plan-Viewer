import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, fireEvent, cleanup } from '@testing-library/preact';
import { Toast } from './Toast.jsx';

describe('Toast', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    cleanup();
    vi.useRealTimers();
  });

  describe('auto-dismiss after 3 seconds', () => {
    it('calls onDismiss after 3000ms', () => {
      const onDismiss = vi.fn();
      render(<Toast message="Something went wrong" onDismiss={onDismiss} />);

      expect(onDismiss).not.toHaveBeenCalled();

      vi.advanceTimersByTime(2999);
      expect(onDismiss).not.toHaveBeenCalled();

      vi.advanceTimersByTime(1);
      expect(onDismiss).toHaveBeenCalledTimes(1);
    });
  });

  describe('manual dismiss via close button', () => {
    it('calls onDismiss when close button is clicked', () => {
      const onDismiss = vi.fn();
      const { getByLabelText } = render(
        <Toast message="Error occurred" onDismiss={onDismiss} />
      );

      fireEvent.click(getByLabelText('Dismiss notification'));
      expect(onDismiss).toHaveBeenCalledTimes(1);
    });
  });

  describe('new message replaces previous and resets timer', () => {
    it('resets the 3-second timer when message changes', () => {
      const onDismiss = vi.fn();
      const { rerender } = render(
        <Toast message="First error" onDismiss={onDismiss} />
      );

      // Advance 2 seconds into the first timer
      vi.advanceTimersByTime(2000);
      expect(onDismiss).not.toHaveBeenCalled();

      // Re-render with a new message — timer should reset
      rerender(<Toast message="Second error" onDismiss={onDismiss} />);

      // Advance another 2 seconds (total 4s from start, but only 2s from new message)
      vi.advanceTimersByTime(2000);
      expect(onDismiss).not.toHaveBeenCalled();

      // Advance the remaining 1 second to hit 3s from the new message
      vi.advanceTimersByTime(1000);
      expect(onDismiss).toHaveBeenCalledTimes(1);
    });
  });

  describe('error and info type rendering', () => {
    it('renders with toast-error class for error type', () => {
      const { container } = render(
        <Toast message="Error!" type="error" onDismiss={() => {}} />
      );
      const toastEl = container.querySelector('.toast');
      expect(toastEl.classList.contains('toast-error')).toBe(true);
    });

    it('renders with toast-info class for info type', () => {
      const { container } = render(
        <Toast message="Info!" type="info" onDismiss={() => {}} />
      );
      const toastEl = container.querySelector('.toast');
      expect(toastEl.classList.contains('toast-info')).toBe(true);
    });

    it('defaults to toast-error class when no type is specified', () => {
      const { container } = render(
        <Toast message="Default" onDismiss={() => {}} />
      );
      const toastEl = container.querySelector('.toast');
      expect(toastEl.classList.contains('toast-error')).toBe(true);
    });

    it('displays the message text', () => {
      const { getByText } = render(
        <Toast message="Something happened" onDismiss={() => {}} />
      );
      expect(getByText('Something happened')).toBeTruthy();
    });
  });
});
