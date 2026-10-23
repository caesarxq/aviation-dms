import { useMemo } from "react";

export type OutlineItem = {
  anchorId: string;
  level: number;
  heading: string;
  sectionNumber?: string;
  blockIndex: number;
};

export function buildOutlineFromHtml(html: string): OutlineItem[] {
  if (typeof DOMParser === "undefined") return [];
  const document = new DOMParser().parseFromString(html || "", "text/html");
  const counts = new Map<string, number>();
  return Array.from(document.querySelectorAll("h1, h2, h3, h4, h5, h6")).map((heading, index) => {
    const text = (heading.textContent || "").replace(/\s+/g, " ").trim();
    const match = text.match(/^\s*(\d+(?:\.\d+)*)[\s.\-:]*(.*)$/);
    const sectionNumber = match?.[1];
    const label = (match?.[2] || text).trim();
    const key = `${sectionNumber || "heading"}-${label.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;
    const occurrence = (counts.get(key) || 0) + 1;
    counts.set(key, occurrence);
    return {
      anchorId: `outline-${key}-${occurrence}`,
      level: Number(heading.tagName.substring(1)),
      heading: label || text || `Heading ${index + 1}`,
      sectionNumber,
      blockIndex: index,
    };
  });
}

export function DocumentOutline({ items, activeAnchor, onSelect }: { items: OutlineItem[]; activeAnchor?: string; onSelect: (item: OutlineItem) => void }) {
  const visibleItems = useMemo(() => items, [items]);
  return (
    <nav aria-label="Document outline" className="h-full overflow-y-auto p-3">
      <div className="mb-2 px-2 text-[10px] font-bold uppercase tracking-wider text-kfl-muted">Document outline</div>
      {visibleItems.length === 0 ? (
        <p className="px-2 py-4 text-xs text-kfl-muted">No headings detected.</p>
      ) : (
        <div className="space-y-0.5">
          {visibleItems.map((item) => (
            <button
              key={item.anchorId}
              type="button"
              onClick={() => onSelect(item)}
              className={`block w-full rounded px-2 py-1.5 text-left text-xs transition ${activeAnchor === item.anchorId ? "bg-kfl-blue/10 font-semibold text-kfl-blue" : "text-kfl-secondary hover:bg-kfl-surface-subtle hover:text-kfl-text"}`}
              style={{ paddingLeft: `${Math.max(8, item.level * 10)}px` }}
            >
              {item.sectionNumber ? `${item.sectionNumber} ` : ""}{item.heading}
            </button>
          ))}
        </div>
      )}
    </nav>
  );
}
