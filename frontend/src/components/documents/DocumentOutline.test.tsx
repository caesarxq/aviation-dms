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
    expect(items[0].heading).toBe(items[1].heading);
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

  it("normalizes heading whitespace without trimming to empty", () => {
    const items = buildOutlineFromHtml("<h2>  Operations  </h2>");

    expect(items[0].heading).toBe("Operations");
  });

  it("falls back to Heading label for empty heading elements", () => {
    const items = buildOutlineFromHtml("<h2></h2>");

    expect(items).toEqual([
      expect.objectContaining({ heading: "Heading", sectionNumber: undefined }),
    ]);
  });

  it("parses section numbers with trailing dot", () => {
    const items = buildOutlineFromHtml("<h1>1.</h1><h2>1.1 Flight Planning</h2>");

    expect(items[0].sectionNumber).toBe("1");
    expect(items[1].sectionNumber).toBe("1.1");
  });

  it("parses section numbers with dash and colon separators", () => {
    const items = buildOutlineFromHtml("<h1>1-Operations</h1><h2>1:1 Flight Planning</h2>");

    expect(items[0].sectionNumber).toBe("1");
    expect(items[1].sectionNumber).toBe("1");
  });

  it("tracks duplicate heading counts for anchor generation", () => {
    const items = buildOutlineFromHtml("<h2>Safety</h2><p>one</p><h2>Safety</h2><p>two</p><h2>Safety</h2><p>three</p>");

    const safetyItems = items.filter((item) => item.heading === "Safety");
    expect(safetyItems).toHaveLength(3);
    expect(safetyItems.map((item) => item.anchorId)).toEqual(["block-0", "block-2", "block-4"]);
  });

  it("dedupes PDF headings case-insensitively on the same page", () => {
    const items = buildOutlineFromHtml(
      '<div class="pf"><div class="t">PART A</div><div class="t">Part a</div></div>',
    );

    expect(items).toHaveLength(1);
    expect(items[0].heading).toBe("PART A");
  });

  it("skips non-numbered non-PART text in PDF recovery", () => {
    const items = buildOutlineFromHtml('<div class="pf"><div class="t">Random text here</div></div>');

    expect(items).toEqual([
      expect.objectContaining({ anchorId: "page-0", heading: "Page 1" }),
    ]);
  });

  it("rejects ellipsis text in PDF recovery", () => {
    const items = buildOutlineFromHtml('<div class="pf"><div class="t">....</div></div>');

    expect(items).toEqual([
      expect.objectContaining({ anchorId: "page-0", heading: "Page 1" }),
    ]);
  });

  it("clamps heading level to 6 for deeply nested numbered sections", () => {
    const items = buildOutlineFromHtml(
      "<h1>1</h1><h2>1.1</h2><h3>1.1.1</h3><h4>1.1.1.1</h4><h5>1.1.1.1.1</h5><h6>1.1.1.1.1.1</h6><h6>1.1.1.1.1.1.1</h6>",
    );

    const levels = items.map((item) => item.level);
    expect(levels).toEqual([1, 2, 3, 4, 5, 6, 6]);
  });

  it("trims leading and trailing whitespace from PDF heading labels", () => {
    const items = buildOutlineFromHtml('<div class="pf"><div class="t">  1.1   The Company  </div></div>');

    expect(items[0].heading).toBe("The Company");
    expect(items[0].sectionNumber).toBe("1.1");
  });

  it("falls back to page index 0 when page element has no index map entry", () => {
    const items = buildOutlineFromHtml(
      '<div class="t">1.1 Title</div><div class="pf"><div class="t">inside pf</div></div>',
    );

    expect(items[0].anchorId).toBe("heading-0");
    expect(items[0].blockIndex).toBe(0);
  });

  it("skips text blocks at exactly 140 characters in PDF recovery", () => {
    const text140 = "a".repeat(140);
    const items = buildOutlineFromHtml(
      `<div class="pf"><div class="t">${text140}</div></div><div class="pf"><div class="t">1.1 Real</div></div>`,
    );

    expect(items).toEqual([
      expect.objectContaining({ anchorId: "heading-1", heading: "Real" }),
    ]);
  });

  it("rejects PART headings outside A-D range", () => {
    const items = buildOutlineFromHtml('<div class="pf"><div class="t">PART E</div></div>');

    expect(items).toEqual([
      expect.objectContaining({ anchorId: "page-0", heading: "Page 1" }),
    ]);
  });

  it("returns empty list when DOMParser input is null/undefined", () => {
    expect(buildOutlineFromHtml(null as unknown as string)).toEqual([]);
    expect(buildOutlineFromHtml(undefined as unknown as string)).toEqual([]);
  });

  it("collapses multiple spaces to single space in heading text", () => {
    const items = buildOutlineFromHtml("<h2>Operations    and   Safety</h2>");

    expect(items[0].heading).toBe("Operations and Safety");
  });

  it("collapses multiple spaces to single space in PDF text nodes", () => {
    const items = buildOutlineFromHtml('<div class="pf"><div class="t">1.1    Title    Here</div></div>');

    expect(items[0].heading).toBe("Title Here");
  });

  it("keeps whitespace-only headings with plain Heading label", () => {
    const items = buildOutlineFromHtml("<h2>   </h2><h2>Real Heading</h2>");

    expect(items).toEqual([
      expect.objectContaining({ heading: "Heading", anchorId: "block-0", sectionNumber: undefined }),
      expect.objectContaining({ heading: "Real Heading", anchorId: "block-1" }),
    ]);
  });

  it("parses section number with colon separator as best-effort split", () => {
    const items = buildOutlineFromHtml("<h2>1:1 Flight Planning</h2>");

    expect(items[0].sectionNumber).toBe("1");
  });

  it("rejects heading text with leading whitespace without section number", () => {
    const items = buildOutlineFromHtml("<h2>  Not a Number</h2>");

    expect(items[0].sectionNumber).toBeUndefined();
    expect(items[0].heading).toBe("Not a Number");
  });

  it("produces different anchor keys for different section numbers with same label", () => {
    const items = buildOutlineFromHtml("<h2>1 Introduction</h2><h2>2 Introduction</h2>");

    expect(items[0].anchorId).not.toBe(items[1].anchorId);
    expect(items[0].heading).toBe(items[1].heading);
  });

  it("handles trailing dot as separator rather than section number", () => {
    const items = buildOutlineFromHtml("<h2>3. Details</h2><h2>3.1 Details</h2>");

    expect(items[0].sectionNumber).toBe("3");
    expect(items[0].heading).toBe("Details");
    expect(items[1].sectionNumber).toBe("3.1");
    expect(items[1].heading).toBe("Details");
  });

  it("parses two-digit section numbers", () => {
    const items = buildOutlineFromHtml("<h2>10.1 Safety Management</h2>");

    expect(items[0].sectionNumber).toBe("10.1");
    expect(items[0].heading).toBe("Safety Management");
  });

  it("does not match leading text before section number", () => {
    const items = buildOutlineFromHtml("<h2>Some intro 1.1 Title</h2>");

    expect(items[0].sectionNumber).toBeUndefined();
  });

  it("does not require dot separators for section numbers", () => {
    const items = buildOutlineFromHtml("<h2>11 Title</h2>");

    expect(items[0].sectionNumber).toBe("11");
    expect(items[0].heading).toBe("Title");
  });

  it("produces block- prefixed anchors for semantic headings", () => {
    const items = buildOutlineFromHtml("<h2>Operations And Safety</h2>");

    expect(items[0].anchorId).toBe("block-0");
  });
});
