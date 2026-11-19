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

// Radix UI Select uses setPointerCapture/hasPointerCapture which jsdom lacks
if (typeof HTMLElement !== 'undefined') {
  const proto = HTMLElement.prototype;
  if (typeof proto.setPointerCapture !== 'function') {
    proto.setPointerCapture = () => {};
  }
  if (typeof proto.hasPointerCapture !== 'function') {
    proto.hasPointerCapture = () => true;
  }
  if (typeof proto.releasePointerCapture !== 'function') {
    proto.releasePointerCapture = () => {};
  }
  if (typeof proto.scrollIntoView !== 'function') {
    proto.scrollIntoView = () => {};
  }
}

// Radix UI Select/Popover observe element size; jsdom has no ResizeObserver.
if (typeof globalThis.ResizeObserver === 'undefined') {
  globalThis.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  } as unknown as typeof ResizeObserver;
}

// matchMedia polyfill for jsdom (used by ThemeToggle)
if (typeof window !== 'undefined' && typeof window.matchMedia !== 'function') {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    configurable: true,
    value: () => ({
      matches: false,
      media: '',
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false,
    }),
  });
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
