/**
 * Shared filter utilities for Aviation DMS frontend.
 *
 * Eliminates duplicated .filter()/.map() logic across 15+ pages.
 */

export function filterByStatus<T extends { status?: string }>(
  items: T[],
  status: string
): T[] {
  if (!status) return items;
  return items.filter((item) => item.status === status);
}

export function filterBySearch<T>(
  items: T[],
  search: string,
  keys: string[]
): T[] {
  if (!search) return items;
  const lower = search.toLowerCase();
  return items.filter((item) =>
    keys.some((key) =>
      String(item[key as keyof T] ?? "").toLowerCase().includes(lower)
    )
  );
}

export function countByStatus<T extends { status: string }>(
  items: T[]
): Record<string, number> {
  return items.reduce((acc, item) => {
    acc[item.status] = (acc[item.status] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);
}

export function filterByDateRange<T extends { date_field?: string }>(
  items: T[],
  startDate: string | null,
  endDate: string | null,
  dateKey: keyof T = "date_field" as keyof T
): T[] {
  if (!startDate && !endDate) return items;
  return items.filter((item) => {
    const itemDate = item[dateKey];
    if (!itemDate) return false;
    if (startDate && itemDate < startDate) return false;
    if (endDate && itemDate > endDate) return false;
    return true;
  });
}

export function sortByField<T>(
  items: T[],
  key: keyof T,
  direction: "asc" | "desc" = "asc"
): T[] {
  return [...items].sort((a, b) => {
    const aVal = a[key];
    const bVal = b[key];
    if (aVal < bVal) return direction === "asc" ? -1 : 1;
    if (aVal > bVal) return direction === "asc" ? 1 : -1;
    return 0;
  });
}

export function groupByField<T>(items: T[], key: keyof T): Record<string, T[]> {
  return items.reduce((acc, item) => {
    const groupKey = String(item[key]);
    if (!acc[groupKey]) acc[groupKey] = [];
    acc[groupKey]!.push(item);
    return acc;
  }, {} as Record<string, T[]>);
}
