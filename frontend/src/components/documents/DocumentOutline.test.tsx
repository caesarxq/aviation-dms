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
    const items = buildOutlineFromHtml("<div class=\"pf pf1\"></div><div class=\"pf pf2\"></div>");

    expect(items).toEqual([
      expect.objectContaining({ anchorId: "page-0", heading: "Page 1", blockIndex: 0 }),
      expect.objectContaining({ anchorId: "page-1", heading: "Page 2", blockIndex: 1 }),
    ]);
  });
});
