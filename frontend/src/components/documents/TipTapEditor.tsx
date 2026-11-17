/**
 * TipTap-based rich text editor for Aviation DMS document editing.
 *
 * Replaces contentEditable + document.execCommand + innerHTML pattern
 * with a controlled, type-safe editor that:
 * - Uses ProseMirror document model (no innerHTML injection)
 * - Sanitizes pasted content with DOMPurify
 * - Supports bold, italic, underline, lists, links
 * - Provides controlled value/onChange interface
 * - Handles both editable and read-only modes
 */
import { useEffect, useRef } from "react";
import { useEditor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import TextAlign from "@tiptap/extension-text-align";
import Link from "@tiptap/extension-link";
import Image from "@tiptap/extension-image";
import DOMPurify from "dompurify";
import type { Editor } from "@tiptap/core";

interface TipTapEditorProps {
  value: string;
  onChange: (html: string) => void;
  disabled?: boolean;
  className?: string;
  editorRef?: (editor: Editor | null) => void;
}

/**
 * Sanitizes HTML content using DOMPurify with the same allowed tags/attributes
 * as the rest of the application. This is defense-in-depth for pasted content.
 */
function sanitizeHtml(html: string): string {
  const ALLOWED_TAGS = [
    "a", "abbr", "address", "article", "b", "blockquote", "br", "caption", "cite",
    "code", "col", "colgroup", "dd", "del", "details", "div", "dl", "dt", "em",
    "figcaption", "figure", "font", "h1", "h2", "h3", "h4", "h5", "h6", "head",
    "hr", "html", "i", "img", "ins", "kbd", "li", "main", "mark", "ol", "p", "pre",
    "q", "s", "samp", "section", "small", "span", "strong", "style", "sub",
    "summary", "sup", "table", "tbody", "td", "tfoot", "th", "thead", "tr", "u",
    "ul", "var", "body",
  ];
  const ALLOWED_ATTR = [
    "alt", "class", "colspan", "height", "href", "id", "scope", "src", "start",
    "style", "title", "type", "width", "rowspan",
  ];

  return DOMPurify.sanitize(html, {
    ALLOWED_TAGS,
    ALLOWED_ATTR,
    ALLOW_DATA_ATTR: true,
    ALLOW_ARIA_ATTR: false,
    RETURN_TRUSTED_TYPE: false,
  });
}

/**
 * TipTapEditor - Controlled rich text editor using TipTap (ProseMirror-based).
 *
 * Replaces contentEditable + document.execCommand pattern with:
 * - ProseMirror document model (no innerHTML injection)
 * - DOMPurify sanitization on paste
 * - Controlled value/onChange interface
 * - Bold, italic, underline, lists, links, text alignment
 */
export function TipTapEditor({
  value,
  onChange,
  disabled = false,
  className = "",
  editorRef: editorRefCallback,
}: TipTapEditorProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const editorRef = useRef<Editor | null>(null);

  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        heading: {
          levels: [1, 2, 3, 4, 5, 6],
        },
        link: false,
        blockquote: false,
        code: false,
        horizontalRule: false,
        dropcursor: false,
        gapcursor: false,
      }),
      Link.extend({
        inclusive: false,
      }).configure({
        HTMLAttributes: {
          class: "text-kfl-blue underline underline-offset-2 hover:text-kfl-blue/80",
          target: "_blank",
          rel: "noopener noreferrer",
        },
      }),
      TextAlign.configure({
        types: ["heading", "paragraph"],
      }),
      Image.configure({
        HTMLAttributes: {
          class: "rounded-lg border border-kfl-border",
        },
      }),
    ],
    content: value || "",
    editable: !disabled,
    onUpdate: ({ editor: tipTapEditor }) => {
      const html = tipTapEditor.getHTML();
      const sanitized = sanitizeHtml(html);
      onChange(sanitized);
    },
    onPaste: (event) => {
      event.preventDefault();
      const clipboardData = (event as ClipboardEvent).clipboardData;
      const html = clipboardData?.getData("text/html") || "";
      const text = clipboardData?.getData("text/plain") || "";
      const tipTapEditor = editorRef.current;
      if (!tipTapEditor) return;

      if (html) {
        const sanitized = sanitizeHtml(html);
        tipTapEditor.commands.insertContent(sanitized);
      } else if (text) {
        tipTapEditor.commands.insertContent(text);
      }
    },
  });

  editorRef.current = editor;
  if (editorRefCallback) editorRefCallback(editor);

  // Mount the editor's ProseMirror DOM element into our container ref
  useEffect(() => {
    if (editor?.view?.dom && containerRef.current && !containerRef.current.contains(editor.view.dom)) {
      containerRef.current.innerHTML = "";
      containerRef.current.appendChild(editor.view.dom);
    }
  }, [editor]);

  // Sync editor content when external value changes (e.g., revert changes)
  useEffect(() => {
    if (editor && editor.getHTML() !== value) {
      editor.commands.setContent(value || "");
    }
  }, [value, editor]);

  return (
    <div ref={containerRef} className={className} data-testid="tappeditor" />
  );
}

export default TipTapEditor;
