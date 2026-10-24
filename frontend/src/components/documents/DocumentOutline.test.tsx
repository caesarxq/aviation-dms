import { describe, expect, it } from "vitest";
import { buildOutlineFromHtml } from "./DocumentOutline";

describe("buildOutlineFromHtml", () => {
  it("uses document block positions so headings navigate to the matching block", () => {
    const items = buildOutlineFromHtml(
      "<h1>1. Operations</h1><p>Introductory text</p><h2>1.1 Flight Planning</h2><p>Planning text</p>",
    );

    expect(items).toHaveLength(2);
    expect(items[0]).toMatchObject({ anchorId: "block-0", blockIndex: 0, sectionNumber: "1" });
    expect(items[1]).toMatchObject({ anchorId: "block-2", blockIndex: 2, sectionNumber: "1.1" });
  });

  it("returns stable block anchors for duplicate headings", () => {
    const items = buildOutlineFromHtml("<h2>Repeated</h2><p>one</p><h2>Repeated</h2>");

    expect(items.map((item) => item.anchorId)).toEqual(["block-0", "block-2"]);
  });

  it("recovers numbered headings from PDF-converted text blocks", () => {
    const items = buildOutlineFromHtml(
      '<div class="pf"><div class="t">1.1 The Company</div></div><div class="pf"><div class="t">1.1.1 Remote Aircraft Operators Certificate</div></div>',
    );

    expect(items).toEqual([
      expect.objectContaining({ anchorId: "heading-0", sectionNumber: "1.1", heading: "The Company", blockIndex: 0 }),
      expect.objectContaining({ anchorId: "heading-1", sectionNumber: "1.1.1", heading: "Remote Aircraft Operators Certificate", blockIndex: 1 }),
    ]);
  });

  it("falls back to page navigation for converted manuals without headings", () => {
    const items = buildOutlineFromHtml('<div class="pf pf1"></div><div class="pf pf2"></div>');

    expect(items).toEqual([
      expect.objectContaining({ anchorId: "page-0", heading: "Page 1", blockIndex: 0 }),
      expect.objectContaining({ anchorId: "page-1", heading: "Page 2", blockIndex: 1 }),
    ]);
  });

  it("returns empty list for empty or non-HTML input", () => {
    expect(buildOutlineFromHtml("")).toEqual([]);
    expect(buildOutlineFromHtml("<p>No headings here</p>")).toEqual([]);
  });

  it("handles headings without section numbers", () => {
    const items = buildOutlineFromHtml("<h2>Introduction</h2><p>text</p>");

    expect(items).toEqual([
      expect.objectContaining({ heading: "Introduction", sectionNumber: undefined, anchorId: "block-0" }),
    ]);
  });

  it("skips long text blocks and ellipsis-only text in PDF-converted pages", () => {
    const longText = "a".repeat(141);
    const ellipsisText = "....";
    const items = buildOutlineFromHtml(
      `<div class="pf"><div class="t">${longText}</div></div><div class="pf"><div class="t">${ellipsisText}</div></div>`,
    );

    // Falls back to page navigation because no headings were recovered
    expect(items).toEqual([
      expect.objectContaining({ anchorId: "page-0", heading: "Page 1" }),
      expect.objectContaining({ anchorId: "page-1", heading: "Page 2" }),
    ]);
  });

  it("recognizes PART headings in PDF-converted text", () => {
    const items = buildOutlineFromHtml('<div class="pf"><div class="t">PART A</div></div>');

    expect(items).toEqual([
      expect.objectContaining({ heading: "PART A", anchorId: "heading-0", sectionNumber: undefined }),
    ]);
  });

  it("produces stable dedupe keys for duplicate headings with same block position", () => {
    const items = buildOutlineFromHtml("<h2>Same</h2><p>one</p><h2>Same</h2><p>two</p>");

    expect(items.map((item) => item.anchorId)).toEqual(["block-0", "block-2"]);
    // Same text but different positions, so blockIndex differs
    expect(items[0].heading).toBe(items[1].heading);
  });

  it("handles deeply nested numbered headings", () => {
    const items = buildOutlineFromHtml("<h1>1</h1><h2>1.1</h2><h3>1.1.1</h3><h4>1.1.1.1</h4>");

    expect(items.map((item) => item.level)).toEqual([1, 2, 3, 4]);
  });

  it("generates lowercase block anchors for headings without section numbers", () => {
    const items = buildOutlineFromHtml("<h1>Heading With Spaces & Special!</h1>");

    expect(items[0].anchorId).toBe("block-0");
    expect(items[0].heading).toBe("Heading With Spaces & Special!");
  });
});
