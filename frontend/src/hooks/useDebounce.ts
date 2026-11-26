import { useEffect, useState } from "react";

/**
 * Debounce a value by `delay` milliseconds.
 *
 * Useful for search inputs where each keystroke should not trigger a network
 * request; the returned value only updates after the user stops typing.
 */
export function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value);

  useEffect(() => {
    const handler = setTimeout(() => setDebouncedValue(value), delay);
    return () => clearTimeout(handler);
  }, [value, delay]);

  return debouncedValue;
}

export default useDebounce;
