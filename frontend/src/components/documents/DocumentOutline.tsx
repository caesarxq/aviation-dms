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
  try {
    const document = new DOMParser().parseFromString(html || "", "text/html");
    const counts = new Map<string, number>();

    // All blocks in document order — same selector the editor uses for scrolling.
    const allBlocks = Array.from(
      document.querySelectorAll("h1, h2, h3, h4, h5, h6, p, li, tr, figcaption, caption, blockquote, div"),
    );
    const blockIndexMap = new Map<Node, number>();
    allBlocks.forEach((node, idx) => blockIndexMap.set(node, idx));

    const headings = Array.from(document.querySelectorAll("h1, h2, h3, h4, h5, h6")).map((heading) => {
      const text = (heading.textContent || "").replace(/\s+/g, " ").trim();
      const match = text.match(/^\s*(\d+(?:\.\d+)*)[\s.\-:]*(.*)$/);
      const sectionNumber = match?.[1];
      const label = (match?.[2] || text).trim();
      const key = `${sectionNumber || "heading"}-${label.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;
      const occurrence = (counts.get(key) || 0) + 1;
      counts.set(key, occurrence);
      const blockIndex = blockIndexMap.get(heading);
      return {
        anchorId: `block-${blockIndex}`,
        level: Number(heading.tagName.substring(1)),
        heading: label || text || `Heading`,
        sectionNumber,
        blockIndex: blockIndex ?? 0,
      };
    });

    if (headings.length > 0) return headings;

    // --- PDF-converted heading detection (pdf2htmlEX .t / pdftohtml p) ---
    // Text lives in positioned .t divs (pdf2htmlEX) or <p> elements (pdftohtml).
    // Detect numbered sections, PART titles, and short uppercase/large-font titles,
    // then drop header/footer noise that repeats across many pages.
    const fontSizes = new Map<string, number>();
    document.querySelectorAll("style").forEach((styleEl) => {
      const css = styleEl.textContent || "";
      for (const m of css.matchAll(/\.(fs\d+|ft\d+)\s*\{[^}]*font-size:\s*(\d+(?:\.\d+)?)(?:pt|px)/g)) {
        fontSizes.set(m[1], parseFloat(m[2]));
      }
    });

    const textBlocks = Array.from(document.querySelectorAll(".t, p"));
    const pages = Array.from(document.querySelectorAll('.pf, div[id^="page"][id$="-div"]'));
    const pageIndexMap = new Map<Element, number>();
    pages.forEach((pg, i) => pageIndexMap.set(pg, i));
    const totalPages = pages.length || 1;

    // Body text size = most common font size among text blocks.
    const sizeCounts = new Map<number, number>();
    textBlocks.forEach((b) => {
      const cls = Array.from(b.classList).find((c) => fontSizes.has(c));
      if (cls) { const sz = fontSizes.get(cls)!; sizeCounts.set(sz, (sizeCounts.get(sz) || 0) + 1); }
    });
    let bodySize = 0, maxCount = 0;
    sizeCounts.forEach((count, size) => { if (count > maxCount) { maxCount = count; bodySize = size; } });

    // First pass: collect heading candidates and track how many pages each appears on.
    const candidates: Array<{ b: Element; label: string; sectionNumber?: string; fontSize: number; isPart: boolean }> = [];
    const pageFrequency = new Map<string, Set<number>>();
    textBlocks.forEach((b) => {
      const text = (b.textContent || "").replace(/\s+/g, " ").trim();
      if (!text || text.length > 140 || text.length < 3) return;
      if (/^[\d\s.\-–—:]+$/.test(text)) return;
      if (/\.{3,}/.test(text)) return; // table-of-contents dot leaders

      const cls = Array.from(b.classList).find((c) => fontSizes.has(c));
      const fontSize = cls ? fontSizes.get(cls)! : 0;
      const numbered = text.match(/^(\d+(?:\.\d+)*)\.?\s+([A-Za-z].*)$/);
      const part = text.match(/^(PART\s+[A-Z](?:\s*\([^)]*\))?)$/i);
      const isUppercase = /^[A-Z][A-Z\s\-&/()]+$/.test(text) && text.length >= 4 && text.length <= 60;
      const isLargeFont = bodySize > 0 && fontSize > bodySize * 1.15 && text.length <= 60;
      if (!numbered && !part && !isUppercase && !isLargeFont) return;

      const sectionNumber = numbered?.[1];
      const label = (numbered?.[2] || part?.[1] || text).trim();
      if (!label || label.length < 3) return;

      const page = b.closest('.pf, div[id^="page"][id$="-div"]');
      const pageIndex = page ? (pageIndexMap.get(page) ?? 0) : 0;
      const freqKey = label.toLowerCase();
      if (!pageFrequency.has(freqKey)) pageFrequency.set(freqKey, new Set());
      pageFrequency.get(freqKey)!.add(pageIndex);
      candidates.push({ b, label, sectionNumber, fontSize, isPart: !!part });
    });

    // Second pass: drop header/footer noise (repeated across many pages), dedupe.
    const recoveredHeadings: OutlineItem[] = [];
    const seen = new Set<string>();
    const noiseThreshold = Math.max(3, totalPages * 0.3);
    candidates.forEach(({ b, label, sectionNumber, fontSize, isPart }) => {
      const pagesSeen = pageFrequency.get(label.toLowerCase())?.size || 1;
      if (pagesSeen > noiseThreshold) return;
      const dedupeKey = `${sectionNumber || label}|${label}`.toLowerCase();
      if (seen.has(dedupeKey)) return;
      seen.add(dedupeKey);
      const blockIndex = blockIndexMap.get(b) ?? 0;
      const level = isPart ? 1
        : sectionNumber ? Math.min(6, sectionNumber.split(".").length + 1)
        : (bodySize > 0 && fontSize >= bodySize * 1.5) ? 2 : 3;
      recoveredHeadings.push({
        anchorId: `block-${blockIndex}`,
        level,
        heading: label,
        sectionNumber,
        blockIndex,
      });
    });
    if (recoveredHeadings.length > 0) return recoveredHeadings;

    // Converted manuals may contain page wrappers without recoverable titles.
    const pageFallback = document.querySelectorAll('.pf, div[id^="page"][id$="-div"]');
    return Array.from(pageFallback).map((_, index) => ({
      anchorId: `page-${index}`,
      level: 1,
      heading: `Page ${index + 1}`,
      blockIndex: index,
    }));
  } catch (err) {
    console.error("Failed to build document outline:", err);
    return [];
  }
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