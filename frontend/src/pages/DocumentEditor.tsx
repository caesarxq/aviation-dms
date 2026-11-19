import { useParams, useSearchParams } from "react-router-dom";
import { useState, useEffect, useRef, useCallback, useMemo } from "react";
import type { PointerEvent as ReactPointerEvent } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "../api/client";
import { Eye, Save, ArrowLeft, Bold, Italic, Underline, ListOrdered, Link, Image as ImageIcon, UserCheck, X, GripVertical, Maximize2, Minimize2, ListTree } from "lucide-react";
import { useToast } from "../components/ui/Toast";
import { DocumentOutline, buildOutlineFromHtml } from "../components/documents/DocumentOutline";
import { InlineSuggestionView } from "../components/documents/InlineSuggestionView";
import { TipTapEditor } from "../components/documents/TipTapEditor";
import { htmlToText } from "../utils/diff";
import DOMPurify from "dompurify";
import { useAuth } from "../auth/AuthContext";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogClose } from "@/components/ui/dialog";

const DOCUMENT_ALLOWED_TAGS = [
  "a", "abbr", "address", "article", "b", "blockquote", "br", "caption", "cite", "code", "col", "colgroup",
  "dd", "del", "details", "div", "dl", "dt", "em", "figcaption", "figure", "font", "h1", "h2", "h3", "h4", "h5", "h6",
  "head", "hr", "html", "i", "img", "ins", "kbd", "li", "main", "mark", "ol", "p", "pre", "q", "s", "samp", "section", "small",
  "span", "strong", "style", "sub", "summary", "sup", "table", "tbody", "td", "tfoot", "th", "thead", "tr", "u", "ul", "var", "body",
];
const DOCUMENT_ALLOWED_ATTRIBUTES = ["alt", "class", "colspan", "height", "href", "id", "scope", "src", "start", "style", "title", "type", "width", "rowspan"];

function sanitizeDocumentHtml(html: string) {
  return DOMPurify.sanitize(html, {
    ALLOWED_TAGS: DOCUMENT_ALLOWED_TAGS,
    ALLOWED_ATTR: DOCUMENT_ALLOWED_ATTRIBUTES,
    ALLOW_DATA_ATTR: true,
    ALLOW_ARIA_ATTR: false,
    RETURN_TRUSTED_TYPE: false,
  });
}

export function DocumentEditor() {
  const { docId: routeDocId } = useParams<{ docId: string }>();
  const [docId, setDocId] = useState(routeDocId || "");

  return (
    <div className="app-page">
      <header className="app-page-header">
        <div>
          <div className="app-eyebrow">Document Control</div>
          <h1 className="app-title">Document Editor</h1>
          <p className="app-subtitle">Propose changes to controlled documents. All suggestions undergo manual review before adoption or rejection.</p>
        </div>
        <Button
          onClick={() => setDocId("")}
          disabled={!docId}
          variant="outline"
          size="sm"
          aria-label="Back to list"
        >
          <ArrowLeft size={16} /> Back to List
        </Button>
      </header>

      {!docId && <DocumentSelector setDocId={setDocId} />}

      {docId && <DocumentEditorContent docId={docId} setDocId={setDocId} />}
    </div>
  );
}

function DocumentEditorContent({ docId, setDocId }: { docId: string; setDocId: (id: string) => void }) {
  const { hasPermission } = useAuth();
  const canUpdate = hasPermission("document:update");
  const canPropose = hasPermission("document:propose");
  const [searchParams] = useSearchParams();
  const targetSection = searchParams.get("section") ?? undefined;
  const qc = useQueryClient();
  const { toast } = useToast();
  const editorRef = useRef<HTMLDivElement>(null);
  const tipTapEditorRef = useRef<InstanceType<typeof import("@tiptap/core").Editor> | null>(null);
  const editorShellRef = useRef<HTMLDivElement>(null);
  const toolbarRef = useRef<HTMLDivElement>(null);
  const dragRef = useRef({ offsetX: 0, offsetY: 0 });
  const [showOutline, setShowOutline] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [activeOutlineAnchor, setActiveOutlineAnchor] = useState(targetSection || "");
  const [toolbarPosition, setToolbarPosition] = useState<{ left: number; top: number } | null>(() => {
    try {
      const stored = window.localStorage.getItem("kfl-document-editor-toolbar-position");
      return stored ? JSON.parse(stored) : null;
    } catch {
      return null;
    }
  });
  const [toolbarDragging, setToolbarDragging] = useState(false);

  const { data: content, isLoading } = useQuery({
    queryKey: ["doc-content", docId],
    queryFn: () => api.get(`/p0/documents/${docId}/content`).then((r: any) => r.data),
    enabled: !!docId,
  });

  const [originalContent, setOriginalContent] = useState("");
  const [currentContent, setCurrentContent] = useState("");
  const [changeSummary, setChangeSummary] = useState("");
  const [showPreview, setShowPreview] = useState(true);
  const [saving, setSaving] = useState(false);
  const [editError, setEditError] = useState("");
  const [dirty, setDirty] = useState(false);
  const [showSubmit, setShowSubmit] = useState(false);
  const [selectedChangeSequences, setSelectedChangeSequences] = useState<number[]>([]);
  const [submitRationale, setSubmitRationale] = useState("");
  const [submitSeverity, setSubmitSeverity] = useState("minor");
  const [submitting, setSubmitting] = useState(false);

  // --- High-fidelity manual mode: read-only formatted display with proposal overlay ---
  // Detected when the source contains embedded CSS, page-break classes, or PDF-conversion markers.
  const highFidelityManual = /<(?:style|link|svg)\b|@import\b/i.test(originalContent) || /\sstyle\s*=/i.test(originalContent) || /class=[\"'][^\"']*\b(?:pf|pc|t)\b/i.test(originalContent);

  // Proposed changes for high-fidelity manuals: text selection -> proposed replacement
  const [proposedChangeRanges, setProposedChangeRanges] = useState<Array<{
    id: string;
    originalText: string;
    proposedText: string;
    startOffset: number;
    endOffset: number;
  }>>([]);
  const [selectionPending, setSelectionPending] = useState<{ text: string; start: number; end: number } | null>(null);
  const [proposeDialogOpen, setProposeDialogOpen] = useState(false);
  const [proposedReplacement, setProposedReplacement] = useState("");

  useEffect(() => {
    if (content?.content !== undefined) {
      const base = content.content || "";
      setOriginalContent(base);
      setCurrentContent(base);
    }
  }, [content?.content]);

  const liveSuggestionContent = currentContent;

  const liveOriginalText = useMemo(() => htmlToText(originalContent), [originalContent]);
  const liveProposedText = useMemo(() => htmlToText(liveSuggestionContent), [liveSuggestionContent]);
  const outlineItems = useMemo(() => buildOutlineFromHtml(originalContent), [originalContent]);

  useEffect(() => {
    const handleFullscreen = () => setIsFullscreen(document.fullscreenElement === editorShellRef.current);
    document.addEventListener("fullscreenchange", handleFullscreen);
    return () => document.removeEventListener("fullscreenchange", handleFullscreen);
  }, []);

  const toggleFullscreen = useCallback(async () => {
    const shell = editorShellRef.current;
    if (!shell) return;
    if (document.fullscreenElement) {
      await document.exitFullscreen?.();
    } else if (shell.requestFullscreen) {
      await shell.requestFullscreen();
    } else {
      setIsFullscreen((value) => !value);
    }
  }, []);

  const selectOutlineItem = useCallback((item: { anchorId: string; blockIndex: number; heading: string }) => {
    setActiveOutlineAnchor(item.anchorId);
    const editor = editorRef.current;
    if (!editor) return;

    try {
      // Find the target element by matching heading text content.
      // This is more robust than index-based lookup, which breaks between
      // DOMParser parsing (used by buildOutlineFromHtml) and browser rendering
      // (used when content is set via innerHTML).
      const blocks = editor.querySelectorAll("h1, h2, h3, h4, h5, h6, p, li, tr, figcaption, caption, blockquote");
      let target: HTMLElement | undefined;
      for (const block of Array.from(blocks)) {
        if ((block.textContent || "").trim() === item.heading) {
          target = block as HTMLElement;
          break;
        }
      }

      // Fall back to index-based lookup if text matching fails
      if (!target) {
        const selector = item.anchorId.startsWith("page-")
          ? '.pf, div[id^="page"][id$="-div"]'
          : item.anchorId.startsWith("heading-")
            ? ".t"
            : "h1, h2, h3, h4, h5, h6, p, li, tr, figcaption, caption, blockquote, div";
        const fallbackBlocks = editor.querySelectorAll(selector);
        target = fallbackBlocks[item.blockIndex] as HTMLElement | undefined;
      }

      if (!target) return;

      const pageFrame = (target.closest('.pf') || target.closest('div[id^="page"][id$="-div"]')) as HTMLElement | null;
      if ((item.anchorId.startsWith("page-") || item.anchorId.startsWith("heading-")) && pageFrame?.parentElement) {
        pageFrame.parentElement.scrollTop = pageFrame.offsetTop;
      } else {
        target.scrollIntoView?.({ behavior: "auto", block: "center" });
      }
      target.classList.add("proposal-target-highlight");
      window.setTimeout(() => target.classList.remove("proposal-target-highlight"), 2500);
    } catch (err) {
      console.error("Outline navigation failed:", err);
    }
  }, []);

  // For high-fidelity manuals: render exact source HTML without sanitization, read-only.
  useEffect(() => {
    if (!highFidelityManual) return;
    const el = editorRef.current;
    if (!el) return;
    el.innerHTML = originalContent;
    el.style.overflow = "auto";
    el.style.background = "#f3f4f6";
    el.style.padding = "20px 0";

    const pageContainer = el.querySelector("#page-container") as HTMLElement | null;
    if (pageContainer) {
      // pdf2htmlEX: reveal every .pc content box (display:none until its JS opens
      // it), flow the page container, hide the built-in sidebar, center .pf pages,
      // and scale to fit the editor width. The .t text layer is the visible,
      // editable content; the .bi background carries graphics.
      el.style.display = "block";
      pageContainer.style.position = "static";
      pageContainer.style.width = "100%";
      pageContainer.style.height = "auto";
      el.querySelectorAll(".pc").forEach((pc) => { (pc as HTMLElement).style.display = "block"; });
      const sidebar = el.querySelector("#sidebar") as HTMLElement | null;
      if (sidebar) sidebar.style.display = "none";
      const pfs = Array.from(el.querySelectorAll(".pf")) as HTMLElement[];
      pfs.forEach((pf) => {
        pf.style.margin = "16px auto";
        pf.style.boxShadow = "0 2px 8px rgba(0,0,0,0.12)";
        pf.style.display = "block";
      });
      if (pfs.length && el.clientWidth > 0) {
        const natural = pfs[0].getBoundingClientRect().width || 918;
        const scale = Math.min(1, (el.clientWidth - 32) / natural);
        pageContainer.style.zoom = scale.toFixed(4);
      }
    } else {
      // pdftohtml/pdftoppm: center fixed-size page divs with paper styling.
      el.style.display = "flex";
      el.style.flexDirection = "column";
      el.style.alignItems = "center";
      el.style.gap = "16px";
      el.querySelectorAll('div[id^="page"][id$="-div"]').forEach((page) => {
        (page as HTMLElement).style.margin = "0 auto";
        (page as HTMLElement).style.boxShadow = "0 2px 8px rgba(0,0,0,0.12)";
        (page as HTMLElement).style.background = "#ffffff";
        (page as HTMLElement).style.position = "relative";
        (page as HTMLElement).style.overflow = "hidden";
        (page as HTMLElement).style.flexShrink = "0";
      });
      el.querySelectorAll("img.page-bg").forEach((img) => {
        (img as HTMLElement).style.display = "none";
      });
    }
  }, [originalContent, highFidelityManual]);

  useEffect(() => {
    const match = targetSection?.match(/^(block|page)-(\d+)$/);
    const editor = editorRef.current;
    if (!match || !editor) return;
    const timer = window.setTimeout(() => {
      const selector = match[1] === "page"
        ? '.pf, div[id^="page"][id$="-div"]'
        : "h1, h2, h3, h4, h5, h6, p, li, tr, figcaption, caption, blockquote, div";
      const blocks = editor.querySelectorAll(selector);
      const target = blocks[Number(match[2])] as HTMLElement | undefined;
      if (!target) return;
      target.scrollIntoView?.({ behavior: "auto", block: "center" });
      target.classList.add("proposal-target-highlight");
      window.setTimeout(() => target.classList.remove("proposal-target-highlight"), 2500);
    }, 50);
    return () => window.clearTimeout(timer);
  }, [originalContent, targetSection, highFidelityManual]);

  useEffect(() => {
    if (!toolbarDragging) return;
    const handleMove = (event: PointerEvent) => {
      const toolbar = toolbarRef.current;
      if (!toolbar) return;
      const rect = toolbar.getBoundingClientRect();
      const left = Math.max(8, Math.min(window.innerWidth - rect.width - 8, event.clientX - dragRef.current.offsetX));
      const top = Math.max(8, Math.min(window.innerHeight - rect.height - 8, event.clientY - dragRef.current.offsetY));
      setToolbarPosition({ left, top });
    };
    const handleUp = () => setToolbarDragging(false);
    window.addEventListener("pointermove", handleMove);
    window.addEventListener("pointerup", handleUp, { once: true });
    return () => {
      window.removeEventListener("pointermove", handleMove);
      window.removeEventListener("pointerup", handleUp);
    };
  }, [toolbarDragging]);

  useEffect(() => {
    if (toolbarPosition) window.localStorage.setItem("kfl-document-editor-toolbar-position", JSON.stringify(toolbarPosition));
  }, [toolbarPosition]);

  const startToolbarDrag = (event: ReactPointerEvent<HTMLButtonElement>) => {
    const toolbar = toolbarRef.current;
    if (!toolbar) return;
    const rect = toolbar.getBoundingClientRect();
    if (!toolbarPosition) setToolbarPosition({ left: rect.left, top: rect.top });
    dragRef.current = { offsetX: event.clientX - rect.left, offsetY: event.clientY - rect.top };
    setToolbarDragging(true);
    event.preventDefault();
  };

  // --- Regular document editing ---

  const revertChanges = useCallback(() => {
    if (!window.confirm("Discard all unsuggested changes and revert to original?")) return;
    setCurrentContent(originalContent);
    setProposedChangeRanges([]);
    setDirty(false);
    // TipTapEditor syncs value prop changes automatically via internal useEffect
  }, [originalContent, highFidelityManual]);

  const toggleFormat = useCallback((command: string, value?: string) => {
    if (highFidelityManual) return;
    if (!tipTapEditorRef.current) return;
    if (command === "bold") tipTapEditorRef.current.commands.toggleBold();
    else if (command === "italic") tipTapEditorRef.current.commands.toggleItalic();
    else if (command === "underline") tipTapEditorRef.current.commands.toggleUnderline();
    else if (command === "insertOrderedList") tipTapEditorRef.current.commands.toggleOrderedList();
    else if (command === "bulletList") tipTapEditorRef.current.commands.toggleBulletList();
    else if (command === "insertLink" && value) tipTapEditorRef.current.commands.extendMarkRange("link", { href: value });
    else if (command === "insertImage" && value) tipTapEditorRef.current.commands.setImage({ src: value });
    setDirty(true);
  }, [highFidelityManual]);

  const hasChanges = currentContent !== originalContent;

  // --- High-fidelity manual: text selection for proposing changes ---

  const handleEditorMouseUp = useCallback(() => {
    if (!highFidelityManual) return;
    const el = editorRef.current;
    if (!el) return;
    const selection = window.getSelection();
    if (!selection || selection.isCollapsed) return;
    const text = selection.toString().trim();
    if (!text || text.length < 2) return;

    const range = selection.getRangeAt(0);
    // Compute offsets within the editor's text content for reference
    const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
    let startOffset = 0;
    let endOffset = 0;
    let current = 0;
    let foundStart = false;
    let foundEnd = false;

    let node: Node | null;
    while ((node = walker.nextNode()) && (!foundEnd)) {
      const len = node.textContent?.length || 0;
      if (!foundStart && range.startContainer === node.parentNode || range.startContainer === node) {
        startOffset = current + (range.startContainer === node ? range.startOffset : 0);
        foundStart = true;
      }
      if (foundStart && range.endContainer === node.parentNode || range.endContainer === node) {
        endOffset = current + (range.endContainer === node ? range.endOffset : 0);
        foundEnd = true;
      }
      current += len;
    }

    setSelectionPending({ text, start: Math.max(0, startOffset), end: Math.max(0, endOffset) });
    setProposeDialogOpen(true);
  }, [highFidelityManual]);

  const handleProposeChange = useCallback(() => {
    if (!selectionPending) return;
    const newRange = {
      id: `${Date.now()}`,
      originalText: selectionPending.text,
      proposedText: proposedReplacement.trim() || selectionPending.text,
      startOffset: selectionPending.start,
      endOffset: selectionPending.end,
    };
    setProposedChangeRanges((prev) => [...prev, newRange]);
    setSelectionPending(null);
    setProposedReplacement("");
    setProposeDialogOpen(false);
    setDirty(true);
  }, [selectionPending, proposedReplacement]);

  const removeProposedChange = useCallback((id: string) => {
    setProposedChangeRanges((prev) => prev.filter((r) => r.id !== id));
    setDirty(true);
  }, []);

  const { data: proposalPreview, isLoading: previewLoading } = useQuery({
    queryKey: ["proposal-preview", docId, currentContent],
    queryFn: () => api.post(`/p2/documents/${docId}/proposals/preview`, { proposed_content: sanitizeDocumentHtml(currentContent) }).then((r: any) => r.data),
    enabled: showSubmit && hasChanges && !highFidelityManual,
    staleTime: 1000,
  });

  useEffect(() => {
    if (proposalPreview?.changes) {
      setSelectedChangeSequences(proposalPreview.changes.map((change: any) => change.change_sequence));
    }
  }, [proposalPreview]);

  /* ---------- proposal submission ---------- */
  const createProposalMutation = useMutation({
    mutationFn: (data: {
      proposed_content: string;
      base_version_id?: string;
      selected_change_sequences: number[];
      rationale?: string;
      severity?: string;
    }) => api.post(`/p2/documents/${docId}/proposals/batch`, data).then((r: any) => r.data),
    onSuccess: () => {
      setSubmitting(false);
      setShowSubmit(false);
      setSelectedChangeSequences([]);
      setSubmitRationale("");
      setSubmitSeverity("minor");
      setProposedChangeRanges([]);
      setDirty(false);
      setEditError("");
      setCurrentContent(originalContent);
      // TipTapEditor syncs value prop changes automatically via internal useEffect
      qc.invalidateQueries({ queryKey: ["doc-content", docId] });
      toast({ title: "Proposal submitted", message: "Your change proposal has been submitted for manual review.", type: "success" });
    },
    onError: () => {
      setSubmitting(false);
      setEditError("Failed to submit proposal. Please try again.");
    },
  });

  const handleSubmitProposal = () => {
    setEditError("");
    if (highFidelityManual) {
      if (proposedChangeRanges.length === 0) {
        setEditError("No changes were proposed for submission.");
        return;
      }
      // Build proposed content by applying replacements to original text for preview
      let proposedText = originalContent;
      for (const change of proposedChangeRanges) {
        proposedText = proposedText.split(change.originalText).join(change.proposedText);
      }
      createProposalMutation.mutate({
        proposed_content: sanitizeDocumentHtml(proposedText),
        selected_change_sequences: proposedChangeRanges.map((_, i) => i),
        rationale: submitRationale.trim() || undefined,
        severity: submitSeverity || "minor",
      });
      return;
    }
    if (!proposalPreview?.changes?.length) {
      setEditError("No changes were detected for submission.");
      return;
    }
    if (!selectedChangeSequences.length) {
      setEditError("Select at least one detected change.");
      return;
    }
    setSubmitting(true);
    createProposalMutation.mutate({
      proposed_content: sanitizeDocumentHtml(currentContent),
      base_version_id: proposalPreview.base_version_id,
      selected_change_sequences: selectedChangeSequences,
      rationale: submitRationale.trim() || undefined,
      severity: submitSeverity || "minor",
    });
  };

  const updateMutation = useMutation({
    mutationFn: (data: { content: string; change_summary?: string }) => api.put(`/p0/documents/${docId}/content`, data).then((r: any) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["doc-content", docId] });
      setSaving(false);
      setDirty(false);
      setEditError("");
      toast({ title: "Draft saved", message: "Document version saved as draft.", type: "success" });
    },
    onError: () => {
      setSaving(false);
      setEditError("Failed to save draft. Please try again.");
    },
  });

  const handleSave = () => {
    setEditError("");
    if (highFidelityManual) {
      setEditError("Direct draft saving is disabled for this formatted manual because secure sanitization can alter its embedded layout. Propose changes instead; they undergo manual review before adoption.");
      return;
    }
    setSaving(true);
    updateMutation.mutate({ content: currentContent, change_summary: changeSummary });
  };

  const primaryDetectedChange = proposalPreview?.changes?.find((change: any) => selectedChangeSequences.includes(change.change_sequence)) || proposalPreview?.changes?.[0];

  if (isLoading) return <div className="app-surface p-10 text-center text-sm text-kfl-muted">Loading document…</div>;

  return (
    <div ref={editorShellRef} className={`flex flex-col h-full relative ${isFullscreen ? "bg-kfl-canvas p-4" : ""}`}>
      {/* Moveable suggesting toolbar */}
      <div
        ref={toolbarRef}
        className={`fixed z-50 rounded-xl border border-kfl-border bg-kfl-surface p-2 shadow-xl backdrop-blur-md ${toolbarDragging ? "cursor-grabbing select-none" : ""} ${toolbarPosition ? "" : "bottom-4 left-4"}`}
        style={toolbarPosition ? { left: toolbarPosition.left, top: toolbarPosition.top } : undefined}
      >
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-2 px-1">
            <button
              type="button"
              onPointerDown={startToolbarDrag}
              className="cursor-grab rounded p-1 text-kfl-muted hover:bg-kfl-blue/10 hover:text-kfl-blue active:cursor-grabbing"
              title="Drag toolbar"
              aria-label="Drag toolbar"
            >
              <GripVertical size={14} />
            </button>
            <span className="text-[10px] font-semibold text-kfl-text" title="Mode">
              {highFidelityManual ? "Read-Only (Formatted)" : "Suggesting"}
            </span>
            {toolbarPosition && (
              <button
                type="button"
                onClick={() => setToolbarPosition(null)}
                className="ml-auto text-[10px] text-kfl-muted underline hover:text-kfl-blue"
                title="Reset toolbar position"
              >
                Reset
              </button>
            )}
          </div>
          {!highFidelityManual && (
            <div className="flex gap-1 px-1">
              <button onClick={() => toggleFormat("bold")} className="p-1.5 hover:bg-kfl-blue/10 rounded transition" title="Bold"><Bold size={14} className="text-kfl-blue font-bold" /></button>
              <button onClick={() => toggleFormat("italic")} className="p-1.5 hover:bg-kfl-blue/10 rounded transition" title="Italic"><Italic size={14} className="text-kfl-blue font-bold" /></button>
              <button onClick={() => toggleFormat("underline")} className="p-1.5 hover:bg-kfl-blue/10 rounded transition" title="Underline"><Underline size={14} className="text-kfl-blue font-bold" /></button>
              <button onClick={() => toggleFormat("insertOrderedList")} className="p-1.5 hover:bg-kfl-blue/10 rounded transition" title="Ordered List"><ListOrdered size={14} className="text-kfl-blue font-bold" /></button>
              <button onClick={() => { const url = window.prompt("Link URL:"); if (url) toggleFormat("insertLink", url); }} className="p-1.5 hover:bg-kfl-blue/10 rounded transition" title="Insert Link"><Link size={14} className="text-kfl-blue font-bold" /></button>
              <button onClick={() => {
                const url = window.prompt("Image URL:");
                if (url) toggleFormat("insertImage", url);
              }} className="p-1.5 hover:bg-kfl-blue/10 rounded transition" title="Insert Image"><ImageIcon size={14} className="text-kfl-blue font-bold" /></button>
            </div>
          )}
          <div className="flex gap-1 px-1 border-t border-kfl-border pt-1">
            <button
              onClick={() => setShowPreview(!showPreview)}
              className={`p-1.5 hover:bg-kfl-blue/10 rounded transition ${showPreview ? "bg-kfl-blue/10" : ""}`}
              title={showPreview ? "Hide live suggestions" : "Show suggestions"}
            >
              <Eye size={14} className="text-kfl-blue font-bold" />
            </button>
            {canPropose && (
              <button
                onClick={() => setShowSubmit(true)}
                disabled={highFidelityManual ? proposedChangeRanges.length === 0 : false}
                className="p-1.5 hover:bg-emerald-500/10 rounded transition text-emerald-600 font-bold disabled:cursor-not-allowed disabled:opacity-50"
                aria-label="Submit proposal for review"
                title="Submit proposal for review"
              >
                <UserCheck size={14} />
              </button>
            )}
            <button
              onClick={() => setShowOutline(!showOutline)}
              className={`p-1.5 hover:bg-kfl-blue/10 rounded transition ${showOutline ? "bg-kfl-blue/10" : ""}`}
              title={showOutline ? "Hide document outline" : "Show document outline"}
            >
              <ListTree size={14} className="text-kfl-blue font-bold" />
            </button>
            <button
              onClick={toggleFullscreen}
              className="p-1.5 hover:bg-kfl-blue/10 rounded transition"
              title={isFullscreen ? "Exit fullscreen" : "Enter fullscreen"}
            >
              {isFullscreen ? <Minimize2 size={14} className="text-kfl-blue font-bold" /> : <Maximize2 size={14} className="text-kfl-blue font-bold" />}
            </button>
            <button
              onClick={revertChanges}
              className="p-1.5 hover:bg-rose-500/10 rounded transition text-rose-600 font-bold"
              title="Revert to original"
            >
              <X size={14} />
            </button>
          </div>
        </div>
      </div>

      <div className="flex justify-between items-center mb-4 border-b border-kfl-border px-5 py-4">
        <div>
          <h2 className="text-lg font-bold text-kfl-text">{docId}</h2>
          <p className="text-xs text-kfl-muted">
            Mode:{" "}
            {highFidelityManual ? (
              <span className="font-semibold text-blue-600">Read-Only (Formatted Manual)</span>
            ) : (
              <span className="font-semibold text-emerald-600">Suggesting</span>
            )}
            {hasChanges ? ` · unsaved changes` : ""}
          </p>
          {highFidelityManual && proposedChangeRanges.length > 0 && (
            <p className="text-xs text-kfl-muted mt-1">
              {proposedChangeRanges.length} proposed change{proposedChangeRanges.length !== 1 ? "s" : ""} highlighted in the document.
            </p>
          )}
        </div>
        <div className="flex gap-2">
          <Button
            onClick={() => setShowPreview(!showPreview)}
            variant="outline"
            size="sm"
          >
            <Eye size={16} /> {showPreview ? "Hide suggestions" : "Show suggestions"}
          </Button>
          {canUpdate && (
            <Button
              onClick={handleSave}
              disabled={saving || !dirty || highFidelityManual}
              size="sm"
            >
              <Save size={16} /> {saving ? "Saving…" : "Save as Draft"}
            </Button>
          )}
          <Button
            onClick={() => setDocId("")}
            variant="outline"
            size="sm"
          >
            <ArrowLeft size={16} /> Back
          </Button>
        </div>
      </div>
      {editError && (
        <div className="px-5 py-2">
          <div className="p-3 rounded-md border border-kfl-status-danger-bg bg-kfl-status-danger-bg/20 text-kfl-status-danger text-sm">{editError}</div>
        </div>
      )}
      {highFidelityManual && (
      <div className="px-5 py-2">
      <div className="rounded-md border border-kfl-status-warning-bg bg-kfl-status-warning-bg/20 p-3 text-sm text-kfl-status-warning">
        Direct draft saving is disabled for this formatted manual because secure sanitization can alter its embedded layout. Proposal submission is also disabled; propose changes instead, they undergo manual review before adoption.
      </div>
      </div>
      )}
      <div className={`flex-1 min-h-[600px] overflow-y-auto relative ${showOutline ? "flex" : ""}`}>
        {showOutline && (
          <aside className="relative w-80 border-r border-kfl-border bg-kfl-surface-subtle shrink-0 pr-2 pointer-events-auto">
            <DocumentOutline
              items={outlineItems}
              activeAnchor={activeOutlineAnchor}
              onSelect={selectOutlineItem}
            />
          </aside>
        )}
        <div className={`flex-1 flex flex-col gap-4 ${showOutline ? "pl-2" : ""}`}>
          {!highFidelityManual && (
            <>
              {/* Suggesting-mode banner */}
              <div className="border-b border-kfl-border bg-emerald-50 p-2 flex flex-wrap gap-2 items-center">
                <span className="text-xs font-semibold text-emerald-700 bg-emerald-100 px-2 py-1 rounded">Suggesting mode — changes are tracked live below while you edit.</span>
                <button
                  onClick={revertChanges}
                  className="text-xs text-rose-600 hover:text-rose-800 underline"
                >
                  Revert all suggestions
                </button>
              </div>

              {/* Editable rich-text area — current proposed content */}
              <TipTapEditor
                value={currentContent}
                onChange={setCurrentContent}
                editorRef={(editor) => { tipTapEditorRef.current = editor; }}
                className="min-h-[500px] overflow-y-auto bg-kfl-surface p-4 text-kfl-text"
              />
            </>
          )}
          {highFidelityManual && (
            <>
              {/* Read-only formatted manual — exact layout preserved */}
              <div ref={editorRef}
                className="min-h-[500px] overflow-y-auto bg-white p-4 text-kfl-text leading-relaxed"
                contentEditable={false}
                onMouseUp={handleEditorMouseUp}
                onContextMenu={() => {
                  // Allow native context menu for copy; selection handled by onMouseUp
                }}
                onInput={(e) => e.preventDefault()}
                onPaste={(e) => e.preventDefault()}
                suppressContentEditableWarning={true}
              >
                {/* Content injected via useEffect into innerHTML to preserve formatting */}
              </div>
              {proposedChangeRanges.length > 0 && (
                <div className="border-t border-kfl-border bg-kfl-surface-subtle p-3">
                  <h4 className="text-xs font-semibold text-kfl-text mb-2">Proposed Changes</h4>
                  <ul className="space-y-1 text-xs">
                    {proposedChangeRanges.map((change) => (
                      <li key={change.id} className="flex items-start gap-2 p-1.5 rounded border border-kfl-border bg-kfl-surface">
                        <button
                          onClick={() => removeProposedChange(change.id)}
                          className="text-rose-600 hover:text-rose-800 underline text-[10px] ml-auto"
                          title="Remove proposed change"
                        >
                          Remove
                        </button>
                        <div>
                          <div className="text-[10px] text-kfl-muted">Original:</div>
                          <div className="text-xs line-through text-red-600">{change.originalText}</div>
                          <div className="text-[10px] text-kfl-muted mt-0.5">Proposed:</div>
                          <div className="text-xs underline text-emerald-700">{change.proposedText}</div>
                        </div>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </>
          )}

          <div className="border-t border-kfl-border bg-kfl-surface-subtle px-4 py-3 flex gap-4 items-start">
            <div className="flex-1">
              <label htmlFor="change-summary" className="text-xs font-semibold text-kfl-muted mb-1 block">Change Summary</label>
              <textarea
                id="change-summary"
                name="change_summary"
                className="w-full p-2 border border-kfl-border rounded resize-none focus:outline-none text-sm"
                value={changeSummary}
                onChange={(e) => setChangeSummary(e.target.value)}
                placeholder="Describe the changes..."
                rows={2}
              />
            </div>
            <div className="text-xs text-kfl-muted space-y-1 pt-5">
              <p><strong>Version:</strong> Auto-incremented</p>
              <p><strong>State:</strong> Draft</p>
              <p><strong>KCAA Gate:</strong> Required before publish</p>
            </div>
          </div>

          {showPreview && (
            <InlineSuggestionView
              originalText={liveOriginalText}
              proposedText={liveProposedText}
            />
          )}
        </div>
      </div>

      {/* Submit Proposal Dialog */}
      <Dialog open={showSubmit && canPropose} onOpenChange={open => { if (!open) setShowSubmit(false); }}>
        <DialogContent className="max-w-md w-full">
          <DialogHeader>
            <DialogTitle>Submit Change Proposal</DialogTitle>
            <DialogDescription>
              Your suggested changes will be recorded as a proposal and undergo the prescribed manual change process before being adopted or rejected.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 mt-4">
            {highFidelityManual ? (
              <div className="rounded-lg border border-kfl-border bg-kfl-surface-subtle p-3">
                <div className="mb-2 flex items-center justify-between">
                  <span className="text-xs font-semibold text-kfl-text">Proposed changes</span>
                  <span className="text-xs text-kfl-muted">{proposedChangeRanges.length} proposed</span>
                </div>
                <div className="max-h-48 space-y-1 overflow-y-auto text-xs">
                  {proposedChangeRanges.map((change) => (
                    <div key={change.id} className="p-1 rounded border border-kfl-border bg-kfl-surface">
                      <div className="text-[10px] text-kfl-muted line-through">{change.originalText}</div>
                      <div className="text-[10px] underline text-emerald-700">{change.proposedText}</div>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <>
                <div>
                  <Label htmlFor="proposal-target-ref">Auto-detected Target Reference</Label>
                  <Input
                    id="proposal-target-ref"
                    name="target_ref"
                    readOnly
                    value={primaryDetectedChange?.target_ref || (previewLoading ? "Detecting changed sections…" : "No detected change")}
                  />
                </div>
                <div className="rounded-lg border border-kfl-border bg-kfl-surface-subtle p-3">
                  <div className="mb-2 flex items-center justify-between">
                    <span className="text-xs font-semibold text-kfl-text">Detected changes</span>
                    <span className="text-xs text-kfl-muted">{proposalPreview?.change_count ?? 0} total · {selectedChangeSequences.length} selected</span>
                  </div>
                  {previewLoading ? (
                    <p className="text-xs text-kfl-muted">Detecting sections and atomic changes…</p>
                  ) : proposalPreview?.changes?.length ? (
                    <div className="max-h-56 space-y-2 overflow-y-auto">
                      {proposalPreview.changes.map((change: any) => {
                        const checked = selectedChangeSequences.includes(change.change_sequence);
                        return (
                          <label key={change.change_sequence} className="flex cursor-pointer gap-2 rounded border border-kfl-border bg-kfl-surface p-2 text-xs">
                            <input id={`checked_${change.change_sequence}`} name="checked"
                              type="checkbox"
                              checked={checked}
                              onChange={(event) => setSelectedChangeSequences((current) => event.target.checked ? [...current, change.change_sequence] : current.filter((sequence) => sequence !== change.change_sequence))}
                            />
                            <span>
                              <span className="block font-semibold text-kfl-text">{change.target_ref}</span>
                              <span className="block text-[11px] text-kfl-muted">{change.proposal_type} · {change.grouping_reason}</span>
                              <span className="block text-red-700">{change.original_text || "(new text)"}</span>
                              <span className="block text-emerald-700">→ {change.proposed_text || "(removed)"}</span>
                            </span>
                          </label>
                        );
                      })}
                    </div>
                  ) : (
                    <p className="text-xs text-kfl-muted">No atomic changes detected.</p>
                  )}
                </div>
              </>
            )}
            <div>
              <Label htmlFor="proposal-rationale">Rationale</Label>
              <Textarea
                id="proposal-rationale"
                name="rationale"
                placeholder="Why is this change needed?"
                value={submitRationale}
                onChange={(e) => setSubmitRationale(e.target.value)}
                rows={3}
              />
            </div>
            <div>
              <Label htmlFor="proposal-severity">Severity</Label>
              <Select onValueChange={(value) => setSubmitSeverity(value)}>
                <SelectTrigger id="proposal-severity" name="severity">
                  <SelectValue placeholder={submitSeverity} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="minor">Minor</SelectItem>
                  <SelectItem value="major">Major</SelectItem>
                  <SelectItem value="critical">Critical</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="pt-3 border-t border-kfl-border text-xs text-kfl-muted">
              <p><strong>Original text:</strong> {originalContent.length} chars</p>
              <p><strong>Proposed text:</strong> {currentContent.length} chars</p>
            </div>
            <div className="mt-6 flex gap-2 justify-end">
              <Button onClick={() => setShowSubmit(false)} variant="outline">Cancel</Button>
              <Button
                onClick={handleSubmitProposal}
                disabled={submitting || previewLoading || !hasChanges || (highFidelityManual && proposedChangeRanges.length === 0) || (!highFidelityManual && (!proposalPreview?.changes?.length || !selectedChangeSequences.length))}
              >
                {submitting ? "Submitting…" : "Submit Proposal"}
              </Button>
            </div>
          </div>
        </DialogContent>
        <DialogClose>
          <X size={20} />
        </DialogClose>
      </Dialog>

      {/* Propose Change dialog (high-fidelity manual text selection) */}
      <Dialog open={proposeDialogOpen} onOpenChange={setProposeDialogOpen}>
        <DialogContent className="max-w-sm w-full">
          <DialogHeader>
            <DialogTitle>Propose Change</DialogTitle>
            <DialogDescription>
              Select the replacement text for the selected passage. The original formatting of the manual is preserved; only your proposed text is recorded for review.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div>
              <Label htmlFor="propose-original">Original (read-only)</Label>
              <Textarea
                id="propose-original"
                value={selectionPending?.text || ""}
                readOnly
                rows={3}
                className="bg-kfl-surface-subtle"
              />
            </div>
            <div>
              <Label htmlFor="propose-replacement">Proposed replacement</Label>
              <Textarea
                id="propose-replacement"
                value={proposedReplacement}
                onChange={(e) => setProposedReplacement(e.target.value)}
                placeholder="Type the replacement text…"
                rows={3}
              />
            </div>
          </div>
          <div className="mt-4 flex gap-2 justify-end">
            <Button onClick={() => { setProposeDialogOpen(false); setSelectionPending(null); setProposedReplacement(""); }} variant="outline">Cancel</Button>
            <Button
              onClick={handleProposeChange}
              disabled={!selectionPending || !proposedReplacement.trim()}
            >
              Propose Change
            </Button>
          </div>
        </DialogContent>
        <DialogClose>
          <X size={20} />
        </DialogClose>
      </Dialog>
    </div>
  );
}

function DocumentSelector({ setDocId }: { setDocId: (id: string) => void }) {
  const { data: docs = [], isLoading } = useQuery({
    queryKey: ["documents"],
    queryFn: () => api.get("/p0/documents").then((r: any) => r.data),
  });

  if (isLoading) return <div className="app-surface p-10 text-center text-sm text-kfl-muted">Loading documents…</div>;

  return (
    <div className="app-surface mb-5 p-5">
      <h2 className="font-semibold mb-3 text-kfl-text">Select Document to Edit</h2>
      <div className="overflow-x-auto">
        <table className="min-w-full">
          <thead className="border-b border-kfl-border bg-kfl-surface-subtle">
            <tr>
              <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">ID</th>
              <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Title</th>
              <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Class</th>
              <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Status</th>
              <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">KCAA</th>
              <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Review Due</th>
              <th className="px-4 py-3 text-right text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-kfl-border">
            {docs.map((d: any) => (
              <tr key={d.document_id} className="transition hover:bg-kfl-surface-subtle group cursor-pointer" onClick={() => setDocId(d.document_id)}>
                <td className="px-4 py-4 font-mono text-[12px] text-kfl-text">{d.document_id}</td>
                <td className="px-4 py-4 text-sm font-medium text-kfl-text">{d.title}</td>
                <td className="px-4 py-4 text-sm text-kfl-secondary">{d.doc_class}</td>
                <td className="px-4 py-4 text-sm">
                  <Badge variant={d.status === "published" ? "default" : d.status === "draft" ? "outline" : "secondary"} className={d.status === "published" ? "bg-kfl-status-success-bg text-kfl-status-success" : d.status === "draft" ? "bg-kfl-status-warning-bg text-kfl-status-warning" : "bg-kfl-status-info-bg text-kfl-status-info"}>
                    {d.status}
                  </Badge>
                </td>
                <td className="px-4 py-4 text-sm text-kfl-secondary">{d.kcaa_approval_required ? "Required" : "No"}</td>
                <td className="px-4 py-4 text-sm text-kfl-secondary">{d.review_due_date || "—"}</td>
                <td className="px-4 py-4 text-right text-sm">
                  <span className="font-semibold text-kfl-blue hover:underline">Edit</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default DocumentEditor;
