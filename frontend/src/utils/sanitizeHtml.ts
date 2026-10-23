import DOMPurify from "dompurify";

/**
 * Sanitize HTML content to prevent XSS while preserving safe formatting.
 * Removes script tags, event handlers, and dangerous attributes.
 */
export function sanitizeHtml(html: string | null | undefined): string {
  if (!html) return "";
  return DOMPurify.sanitize(html, {
    ADD_ATTR: ["target", "rel"],
    ADD_TAGS: [],
    FORCE_BODY: false,
  });
}

export default { sanitizeHtml };