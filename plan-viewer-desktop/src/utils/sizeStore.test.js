import { describe, it, expect, vi, beforeEach } from 'vitest';
import { load, save, validate } from './sizeStore.js';

// Mock @tauri-apps/api/core invoke function
vi.mock('@tauri-apps/api/core', () => ({
  invoke: vi.fn(),
}));

import { invoke } from '@tauri-apps/api/core';

beforeEach(() => {
  vi.clearAllMocks();
  vi.spyOn(console, 'warn').mockImplementation(() => {});
});

describe('sizeStore.load', () => {
  it('returns {} when invoke rejects (I/O error)', async () => {
    invoke.mockRejectedValue(new Error('I/O error'));
    const result = await load();
    expect(result).toEqual({});
  });

  it('returns {} when invoke returns invalid JSON (parse error)', async () => {
    invoke.mockResolvedValue('not valid json {{{');
    const result = await load();
    expect(result).toEqual({});
  });

  it('returns {} when invoke returns "{}" (file not found case)', async () => {
    invoke.mockResolvedValue('{}');
    const result = await load();
    expect(result).toEqual({});
  });

  it('returns parsed data when invoke returns valid JSON', async () => {
    const data = { 'C:/Projects/app': { width: 600, height: 450 } };
    invoke.mockResolvedValue(JSON.stringify(data));
    const result = await load();
    expect(result).toEqual(data);
  });

  it('returns {} when invoke returns a JSON array', async () => {
    invoke.mockResolvedValue('[1, 2, 3]');
    const result = await load();
    expect(result).toEqual({});
  });

  it('returns {} when invoke returns JSON null', async () => {
    invoke.mockResolvedValue('null');
    const result = await load();
    expect(result).toEqual({});
  });
});

describe('sizeStore.save', () => {
  it('does not throw when invoke rejects (write failure)', async () => {
    invoke.mockRejectedValue(new Error('disk full'));
    await expect(save({ 'C:/app': { width: 400, height: 300 } })).resolves.toBeUndefined();
  });

  it('correctly serializes and calls invoke with JSON string', async () => {
    invoke.mockResolvedValue(undefined);
    const data = { 'C:/Projects/app': { width: 600, height: 450 } };
    await save(data);
    expect(invoke).toHaveBeenCalledWith('write_window_sizes', {
      data: JSON.stringify(data),
    });
  });
});

describe('sizeStore.validate', () => {
  it('returns null for null input', () => {
    expect(validate(null)).toBeNull();
  });

  it('returns null for undefined input', () => {
    expect(validate(undefined)).toBeNull();
  });

  it('returns null for string input', () => {
    expect(validate('400x300')).toBeNull();
  });

  it('returns null for float width', () => {
    expect(validate({ width: 400.5, height: 300 })).toBeNull();
  });

  it('returns null for float height', () => {
    expect(validate({ width: 400, height: 300.7 })).toBeNull();
  });

  it('returns null for width below minimum (200)', () => {
    expect(validate({ width: 199, height: 300 })).toBeNull();
  });

  it('returns null for height below minimum (150)', () => {
    expect(validate({ width: 400, height: 149 })).toBeNull();
  });

  it('returns null for width above maximum (7680)', () => {
    expect(validate({ width: 7681, height: 300 })).toBeNull();
  });

  it('returns null for height above maximum (4320)', () => {
    expect(validate({ width: 400, height: 4321 })).toBeNull();
  });

  it('returns null for negative width', () => {
    expect(validate({ width: -1, height: 300 })).toBeNull();
  });

  it('returns null for zero width', () => {
    expect(validate({ width: 0, height: 300 })).toBeNull();
  });

  it('returns valid object for minimum boundary values (200x150)', () => {
    expect(validate({ width: 200, height: 150 })).toEqual({ width: 200, height: 150 });
  });

  it('returns valid object for maximum boundary values (7680x4320)', () => {
    expect(validate({ width: 7680, height: 4320 })).toEqual({ width: 7680, height: 4320 });
  });

  it('returns valid object for typical values', () => {
    expect(validate({ width: 800, height: 600 })).toEqual({ width: 800, height: 600 });
  });
});
