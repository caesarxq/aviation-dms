import { describe, expect, it } from "vitest";
import { sanitizeManualHtml } from "./DocumentEditor";
import sample from "../test/fixtures/pdf2htmlex-real-sample.html?raw";

// Real pdf2htmlEX output (CSS incl. @font-face + transform matrices, a .pf page) with
// injected XSS vectors. Sanitization must strip the vectors WITHOUT losing the layout.
const clean = sanitizeManualHtml(sample);

describe("sanitizeManualHtml on real pdf2htmlEX content", () => {
  it("preserves @font-face and transform-matrix CSS needed for exact layout", () => {
    expect(clean).toContain("@font-face");
    expect(clean).toContain("matrix(");
    expect(clean).toContain("<style");
  });

  it("preserves the page frame / text-layer structure, positioning, and images", () => {
    expect(clean).toContain('class="pf');
    expect(clean).toContain('class="t ');
    expect(clean).toContain("<img");
    expect(clean).toContain("position:absolute");
    expect(clean).toContain('id="page-container"');
    // The .t positioning rule must survive verbatim (DOMPurify's CSS sanitizer strips it).
    expect(clean).toMatch(/\.t\{[^}]*position:absolute/);
  });

  it("strips event handlers, script tags, and javascript: URLs", () => {
    expect(clean).not.toContain("onerror");
    expect(clean).not.toContain("onclick");
    expect(clean).not.toContain("<script");
    expect(clean.toLowerCase()).not.toContain("javascript:");
  });
});