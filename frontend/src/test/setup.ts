import '@testing-library/jest-dom';
import { cleanup } from '@testing-library/react';
import { afterEach, expect as vitestExpect } from 'vitest';

class MemoryStorage implements Storage {
  private data = new Map<string, string>();
  get length() { return this.data.size; }
  clear() { this.data.clear(); }
  getItem(key: string) { return this.data.get(key) ?? null; }
  key(index: number) { return Array.from(this.data.keys())[index] ?? null; }
  removeItem(key: string) { this.data.delete(key); }
  setItem(key: string, value: string) { this.data.set(key, String(value)); }
}

if (typeof globalThis.localStorage?.clear !== 'function') {
  Object.defineProperty(globalThis, 'localStorage', { value: new MemoryStorage(), configurable: true });
}
if (typeof window !== 'undefined' && typeof window.localStorage?.clear !== 'function') {
  Object.defineProperty(window, 'localStorage', { value: globalThis.localStorage, configurable: true });
}

afterEach(() => {
  cleanup();
});

if (typeof (globalThis as any).expect === 'undefined') {
  Object.defineProperty(globalThis, 'expect', { value: vitestExpect, writable: true, configurable: true });
}

if (typeof (globalThis as any).jest === 'undefined') {
  Object.defineProperty(globalThis, 'jest', {
    value: {
      mock: () => {},
      spyOn: () => ({ mockImplementation: () => ({}) }),
      fn: () => ({ mockImplementation: () => ({}) }),
      restoreAllMocks: () => {},
    },
    writable: true,
    configurable: true,
  });
}
