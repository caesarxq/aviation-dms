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

    // --- pdftohtml heading detection ---
    // pdftohtml -c -s outputs <p class="ftNN"><span class="ftMM">text</span></p>
    // with font sizes defined in <style> blocks. Detect heading-sized text.
    const fontSizes = new Map<string, number>();
    const styleBlocks = document.querySelectorAll("style");
    styleBlocks.forEach((styleEl) => {
      const css = styleEl.textContent || "";
      const matches = css.matchAll(/\.(ft\d+)\s*\{[^}]*font-size:\s*(\d+(?:\.\d+)?)px/g);
      for (const m of matches) {
        fontSizes.set(m[1], parseFloat(m[2]));
      }
    });

    if (fontSizes.size > 0) {
      // Find body text size (most common font size)
      const sizeCounts = new Map<number, number>();
      fontSizes.forEach((size) => sizeCounts.set(size, (sizeCounts.get(size) || 0) + 1));
      let bodySize = 12;
      let maxCount = 0;
      sizeCounts.forEach((count, size) => {
        if (count > maxCount) { maxCount = count; bodySize = size; }
      });

      // Heading classes: font size > body size + 2px threshold
      const headingClasses = new Set<string>();
      fontSizes.forEach((size, cls) => {
        if (size > bodySize + 2) headingClasses.add(cls);
      });

      if (headingClasses.size > 0) {
        const recoveredHeadings: OutlineItem[] = [];
        const seen = new Set<string>();
        const pageDivs = Array.from(document.querySelectorAll('div[id^="page"][id$="-div"]'));
        const pageIndexMap = new Map<Element, number>();
        pageDivs.forEach((page, index) => pageIndexMap.set(page, index));

        // Find <p> elements containing heading-class spans
        const paragraphs = Array.from(document.querySelectorAll("p"));
        paragraphs.forEach((p) => {
          const spans = Array.from(p.querySelectorAll("span"));
          const headingSpans = spans.filter((s) =>
            Array.from(s.classList).some((c) => headingClasses.has(c))
          );
          if (headingSpans.length === 0) return;

          const text = (p.textContent || "").replace(/\s+/g, " ").trim();
          if (!text || text.length > 140 || text.length < 3) return;
          // Skip lines that are mostly numbers/symbols (page headers/footers)
          if (/^[\d\s.\-–—:]+$/.test(text)) return;

          const numbered = text.match(/^(\d+(?:\.\d+)*)\s+(.+)$/);
          const part = text.match(/^(PART\s+[A-D](?:\s*\([^)]*\))?)$/i);
          const sectionNumber = numbered?.[1];
          const label = (numbered?.[2] || part?.[1] || text).trim();

          const page = p.closest('div[id^="page"][id$="-div"]');
          const pageIndex = page ? (pageIndexMap.get(page) ?? 0) : 0;
          const dedupeKey = `${sectionNumber || label}|${label}|${pageIndex}`.toLowerCase();
          if (seen.has(dedupeKey)) return;
          seen.add(dedupeKey);

          const blockIndex = blockIndexMap.get(p) ?? 0;
          // Determine level from font size relative to body
          const spanSize = headingSpans.reduce((max, s) => {
            const cls = Array.from(s.classList).find((c) => fontSizes.has(c));
            return cls ? Math.max(max, fontSizes.get(cls) || 0) : max;
          }, 0);
          const level = spanSize >= bodySize * 2 ? 1 : spanSize >= bodySize * 1.5 ? 2 : 3;

          recoveredHeadings.push({
            anchorId: `block-${blockIndex}`,
            level: sectionNumber ? Math.min(6, sectionNumber.split(".").length) : level,
            heading: label,
            sectionNumber,
            blockIndex,
          });
        });

        if (recoveredHeadings.length > 0) return recoveredHeadings;
      }
    }

    // PDF-converted manuals often preserve section titles as `.t` text blocks
    // instead of semantic h1-h6 elements. Recover numbered headings from those
    // blocks and keep their exact text-node index for navigation.
    const textNodes = Array.from(document.querySelectorAll(".t"));
    const pageIndexMap = new Map<Element, number>();
    Array.from(document.querySelectorAll(".pf")).forEach((page, index) => pageIndexMap.set(page, index));
    const recoveredHeadings: OutlineItem[] = [];
    const seen = new Set<string>();

    textNodes.forEach((node, textIndex) => {
      const text = (node.textContent || "").replace(/\s+/g, " ").trim();
      if (!text || text.length > 140 || /\.{3,}/.test(text)) return;
      const numbered = text.match(/^(\d+(?:\.\d+)*)\s+(.+)$/);
      const part = text.match(/^(PART\s+[A-D])$/i);
      if (!numbered && !part) return;
      const sectionNumber = numbered?.[1];
      const label = (numbered?.[2] || part?.[1] || text).trim();
      const page = node.closest(".pf");
      const pageIndex = page ? (pageIndexMap.get(page) ?? 0) : 0;
      const dedupeKey = `${sectionNumber || label}|${label}|${pageIndex}`.toLowerCase();
      if (seen.has(dedupeKey)) return;
      seen.add(dedupeKey);
      recoveredHeadings.push({
        anchorId: `heading-${textIndex}`,
        level: sectionNumber ? Math.min(6, sectionNumber.split(".").length) : 1,
        heading: label,
        sectionNumber,
        blockIndex: textIndex,
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
