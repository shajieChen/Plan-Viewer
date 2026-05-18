/**
 * Window size persistence store.
 * Reads/writes per-project window sizes via Tauri invoke commands.
 *
 * @typedef {{ width: number, height: number }} WindowSize
 * @typedef {Record<string, WindowSize>} SizeMap
 */

import { invoke } from '@tauri-apps/api/core';

export const DEFAULT_SIZE = { width: 400, height: 300 };
export const MIN_WIDTH = 200;
export const MIN_HEIGHT = 150;
export const MAX_WIDTH = 7680;
export const MAX_HEIGHT = 4320;
export const MAX_ENTRIES = 200;
export const DEBOUNCE_MS = 1000;

/**
 * Validates a single size record.
 * Returns a valid { width, height } object or null if invalid.
 *
 * @param {unknown} size
 * @returns {WindowSize | null}
 */
export function validate(size) {
  if (size == null || typeof size !== 'object') {
    return null;
  }

  const { width, height } = /** @type {any} */ (size);

  if (
    typeof width !== 'number' ||
    typeof height !== 'number' ||
    !Number.isInteger(width) ||
    !Number.isInteger(height) ||
    width < MIN_WIDTH ||
    width > MAX_WIDTH ||
    height < MIN_HEIGHT ||
    height > MAX_HEIGHT
  ) {
    return null;
  }

  return { width, height };
}

/**
 * Loads the full size map from persistent storage.
 * Returns an empty object on any failure.
 *
 * @returns {Promise<SizeMap>}
 */
export async function load() {
  try {
    const raw = await invoke('read_window_sizes');
    const parsed = JSON.parse(raw);
    if (parsed == null || typeof parsed !== 'object' || Array.isArray(parsed)) {
      console.warn('[sizeStore] Invalid data format in storage, returning empty map');
      return {};
    }
    return parsed;
  } catch (err) {
    console.warn('[sizeStore] Failed to load window sizes:', err);
    return {};
  }
}

/**
 * Saves the full size map to persistent storage.
 * Enforces the MAX_ENTRIES capacity limit by removing the earliest entries.
 * Never throws — logs a warning on failure.
 *
 * @param {SizeMap} data
 * @returns {Promise<void>}
 */
export async function save(data) {
  try {
    let toSave = data;

    // Enforce capacity limit
    const keys = Object.keys(toSave);
    if (keys.length > MAX_ENTRIES) {
      // Keep only the last MAX_ENTRIES entries (delete earliest)
      const excess = keys.length - MAX_ENTRIES;
      const trimmed = { ...toSave };
      for (let i = 0; i < excess; i++) {
        delete trimmed[keys[i]];
      }
      toSave = trimmed;
    }

    const json = JSON.stringify(toSave);
    await invoke('write_window_sizes', { data: json });
  } catch (err) {
    console.warn('[sizeStore] Failed to save window sizes:', err);
  }
}

export const sizeStore = { load, save, validate };
export default sizeStore;
