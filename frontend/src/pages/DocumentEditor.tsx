import { useParams, useSearchParams } from "react-router-dom";
import { useState, useEffect, useRef, useCallback, useMemo } from "react";
import type { PointerEvent as ReactPointerEvent } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "../api/client";
import { Eye, Save, ArrowLeft, Bold, Italic, Underline, ListOrdered, Link, Image as ImageIcon, UserCheck, X, GripVertical, Maximize2, Minimize2, ListTree } from "lucide-react";
import { useToast } from "../components/ui/Toast";
import { DocumentOutline, buildOutlineFromHtml } from "../components/documents/DocumentOutline";
import { InlineSuggestionView } from "../components/documents/InlineSuggestionView";
import { htmlToText } from "../utils/diff";
import DOMPurify from "dompurify";
import { useAuth } from "../auth/AuthContext";

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
        <button
          onClick={() => setDocId("")}
          disabled={!docId}
          className="app-btn-secondary"
          aria-label="Back to list"
        >
          <ArrowLeft size={16} /> Back to List
        </button>
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

  useEffect(() => {
    if (content?.content !== undefined) {
      const base = content.content || "";
      setOriginalContent(base);
      setCurrentContent(base);
    }
  }, [content?.content]);

  const [liveSuggestionContent, setLiveSuggestionContent] = useState("");

  useEffect(() => {
    const timer = window.setTimeout(() => setLiveSuggestionContent(currentContent), 250);
    return () => window.clearTimeout(timer);
  }, [currentContent]);

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

  const selectOutlineItem = useCallback((item: { anchorId: string; blockIndex: number }) => {
    setActiveOutlineAnchor(item.anchorId);
    const editor = editorRef.current;
    if (!editor) return;
    const selector = item.anchorId.startsWith("page-")
      ? ".pf"
      : item.anchorId.startsWith("heading-")
        ? ".t"
        : "h1, h2, h3, h4, h5, h6, p, li, tr, figcaption, caption, blockquote, div";
    const blocks = editor.querySelectorAll(selector);
    const target = blocks[item.blockIndex] as HTMLElement | undefined;
    if (!target) return;
    const pageFrame = target.closest(".pf") as HTMLElement | null;
    if ((item.anchorId.startsWith("page-") || item.anchorId.startsWith("heading-")) && pageFrame?.parentElement) {
      pageFrame.parentElement.scrollTop = pageFrame.offsetTop;
    } else {
      const navigationTarget = target;
      navigationTarget.scrollIntoView?.({ behavior: "auto", block: "center" });
    }
    if (target) {
      target.classList.add("proposal-target-highlight");
      window.setTimeout(() => target.classList.remove("proposal-target-highlight"), 2500);
    }
  }, []);

  useEffect(() => {
    const el = editorRef.current;
    if (!el) return;
    el.innerHTML = sanitizeDocumentHtml(originalContent);
  }, [originalContent]);

  useEffect(() => {
    const match = targetSection?.match(/^(block|page)-(\d+)$/);
    const editor = editorRef.current;
    if (!match || !editor) return;
    const timer = window.setTimeout(() => {
      const selector = match[1] === "page"
        ? ".pf"
        : "h1, h2, h3, h4, h5, h6, p, li, tr, figcaption, caption, blockquote, div";
      const blocks = editor.querySelectorAll(selector);
      const target = blocks[Number(match[2])] as HTMLElement | undefined;
      if (!target) return;
      target.scrollIntoView?.({ behavior: "auto", block: "center" });
      target.classList.add("proposal-target-highlight");
      window.setTimeout(() => target.classList.remove("proposal-target-highlight"), 2500);
    }, 50);
    return () => window.clearTimeout(timer);
  }, [originalContent, targetSection]);

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

  const handleEditorInput = useCallback(() => {
    const el = editorRef.current;
    if (!el) return;
    const html = sanitizeDocumentHtml(el.innerHTML);
    if (html !== el.innerHTML) el.innerHTML = html;
    setCurrentContent(html);
    setDirty(true);
  }, []);

  const handleEditorPaste = useCallback((event: React.ClipboardEvent<HTMLDivElement>) => {
    event.preventDefault();
    const html = event.clipboardData.getData("text/html");
    const text = event.clipboardData.getData("text/plain");
    if (html) {
      document.execCommand("insertHTML", false, sanitizeDocumentHtml(html));
    } else {
      document.execCommand("insertText", false, text);
    }
    handleEditorInput();
  }, [handleEditorInput]);


  const revertChanges = useCallback(() => {
    if (!window.confirm("Discard all unsuggested changes and revert to original?")) return;
    setCurrentContent(originalContent);
    setDirty(false);
    if (editorRef.current) editorRef.current.innerHTML = sanitizeDocumentHtml(originalContent);
  }, [originalContent]);

  const toggleFormat = useCallback((command: string, value?: string) => {
    const el = editorRef.current;
    if (!el) return;
    document.execCommand(command, false, value || undefined);
    const html = sanitizeDocumentHtml(el.innerHTML);
    if (html !== el.innerHTML) el.innerHTML = html;
    setCurrentContent(html);
    setDirty(true);
  }, []);

  const hasChanges = currentContent !== originalContent;
  const highFidelityManual = /<(?:style|link|svg)\b|@import\b/i.test(originalContent) || /\sstyle\s*=/i.test(originalContent) || /class=["'][^"']*\b(?:pf|pc|t)\b/i.test(originalContent);

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
      setLiveSuggestionContent("");
      setDirty(false);
      setEditError("");
      // Reset the editor to the original content so the submitted changes
      // no longer appear as pending edits in the editor or diff preview.
      setCurrentContent(originalContent);
      if (editorRef.current) editorRef.current.innerHTML = sanitizeDocumentHtml(originalContent);
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
      setEditError("Proposal submission is disabled for this formatted manual because secure sanitization can alter its embedded layout. No edited content will be submitted.");
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
      setEditError("Direct draft saving is disabled for this formatted manual because secure sanitization can alter its embedded layout. Proposal submission is also disabled; no edited content will be submitted.");
      return;
    }
    setSaving(true);
    updateMutation.mutate({ content: sanitizeDocumentHtml(currentContent), change_summary: changeSummary });
  };

  const primaryDetectedChange = proposalPreview?.changes?.find((change: any) => selectedChangeSequences.includes(change.change_sequence)) || proposalPreview?.changes?.[0];

  if (isLoading) return <div className="app-surface p-10 text-center text-sm text-kfl-muted">Loading document…</div>;

  return (
    <div ref={editorShellRef} className={`flex flex-col h-full relative ${isFullscreen ? "bg-kfl-canvas p-4" : ""}`}>
      {/* Moveable suggesting toolbar. Drag the grip to reposition; position is remembered locally. */}
      <div
        ref={toolbarRef}
        className={`fixed z-50 rounded-xl border border-kfl-border bg-white/95 p-2 shadow-xl backdrop-blur-md ${toolbarDragging ? "cursor-grabbing select-none" : ""} ${toolbarPosition ? "" : "bottom-4 left-4"}`}
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
            <span className="text-[10px] font-semibold text-kfl-text" title="Mode">✎ Suggest</span>
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
          <div className="flex gap-1 px-1">
            <button onClick={() => toggleFormat("bold")} className="p-1.5 hover:bg-kfl-blue/10 rounded transition" title="Bold"><Bold size={14} className="text-kfl-blue font-bold" /></button>
            <button onClick={() => toggleFormat("italic")} className="p-1.5 hover:bg-kfl-blue/10 rounded transition" title="Italic"><Italic size={14} className="text-kfl-blue font-bold" /></button>
            <button onClick={() => toggleFormat("underline")} className="p-1.5 hover:bg-kfl-blue/10 rounded transition" title="Underline"><Underline size={14} className="text-kfl-blue font-bold" /></button>
            <button onClick={() => toggleFormat("insertOrderedList")} className="p-1.5 hover:bg-kfl-blue/10 rounded transition" title="Ordered List"><ListOrdered size={14} className="text-kfl-blue font-bold" /></button>
            <button onClick={() => toggleFormat("insertLink")} className="p-1.5 hover:bg-kfl-blue/10 rounded transition" title="Insert Link"><Link size={14} className="text-kfl-blue font-bold" /></button>
            <button onClick={() => {
              const url = window.prompt("Image URL:");
              if (url) toggleFormat("insertImage", url);
            }} className="p-1.5 hover:bg-kfl-blue/10 rounded transition" title="Insert Image"><ImageIcon size={14} className="text-kfl-blue font-bold" /></button>
          </div>
          <div className="flex gap-1 px-1 border-t border-kfl-border pt-1">
            <button
              onClick={() => setShowPreview(!showPreview)}
              className={`p-1.5 hover:bg-kfl-blue/10 rounded transition ${showPreview ? "bg-kfl-blue/10" : ""}`}
              title={showPreview ? "Hide live suggestions" : "Show live suggestions"}
            >
              <Eye size={14} className="text-kfl-blue font-bold" />
            </button>
            {canPropose && (
              <button
                onClick={() => setShowSubmit(true)}
                disabled={highFidelityManual}
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
            Mode: <span className="font-semibold text-emerald-600">Suggesting</span>{hasChanges ? ` · unsaved changes` : ""}
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setShowPreview(!showPreview)}
            className="app-btn-secondary px-3 py-2 flex items-center gap-1 text-sm"
          >
            <Eye size={16} /> {showPreview ? "Hide suggestions" : "Show suggestions"}
          </button>
          {canUpdate && (
            <button
              onClick={handleSave}
              disabled={saving || !dirty || highFidelityManual}
              className="app-btn-primary px-4 py-2 flex items-center gap-1 text-sm"
            >
              <Save size={16} /> {saving ? "Saving…" : "Save as Draft"}
            </button>
          )}
          <button
            onClick={() => setDocId("")}
            className="app-btn-secondary px-3 py-2 flex items-center gap-1 text-sm"
          >
            <ArrowLeft size={16} /> Back
          </button>
        </div>
      </div>
      {editError && (
        <div className="px-5 py-2">
          <div className="p-3 rounded bg-rose-50/60 border border-rose-200 text-rose-800 text-sm">{editError}</div>
        </div>
      )}
      {highFidelityManual && (
        <div className="px-5 py-2">
          <div className="rounded border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">Direct draft saving is disabled for this formatted manual because secure sanitization can alter its embedded layout. Proposal submission is also disabled; no edited content will be submitted.</div>
        </div>
      )}
      <div className={`flex-1 min-h-[600px] overflow-y-auto relative ${showOutline ? "flex" : ""}`}>
        {showOutline && (
          <aside className="relative z-20 w-80 border-r border-kfl-border bg-kfl-surface-subtle shrink-0 pointer-events-auto">
            <DocumentOutline
              items={outlineItems}
              activeAnchor={activeOutlineAnchor}
              onSelect={selectOutlineItem}
            />
          </aside>
        )}
        <div className="flex-1 flex flex-col gap-4">
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
          <div ref={editorRef}
            className="min-h-[500px] overflow-y-auto bg-white p-4 text-kfl-text"
            contentEditable={true}
            onInput={handleEditorInput}
            onPaste={handleEditorPaste}
            onDrop={(event) => event.preventDefault()}
            suppressContentEditableWarning={true}
            spellCheck={true}
          />

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
      {canPropose && showSubmit && (
        <div className="fixed inset-0 z-[60] bg-black/50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl p-6 max-w-md w-full shadow-2xl border border-white">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-bold text-kfl-text">Submit Change Proposal</h3>
              <button onClick={() => setShowSubmit(false)} className="text-kfl-muted hover:text-kfl-text"><X size={20} /></button>
            </div>
            <p className="text-sm text-kfl-muted mb-4">
              Your suggested changes will be recorded as a proposal and undergo the prescribed manual change process before being adopted or rejected.
            </p>
            <div className="space-y-3">
              <div>
                <label htmlFor="proposal-target-ref" className="block text-xs font-semibold text-kfl-muted mb-1">Auto-detected Target Reference</label>
                <input
                  id="proposal-target-ref"
                  name="target_ref"
                  readOnly
                  className="w-full border border-kfl-border rounded p-2 text-sm bg-kfl-surface-subtle text-kfl-text"
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
                        <label key={change.change_sequence} className="flex cursor-pointer gap-2 rounded border border-kfl-border bg-white p-2 text-xs">
                          <input id="checked_526" name="checked"
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
              <div>
                <label htmlFor="proposal-rationale" className="block text-xs font-semibold text-kfl-muted mb-1">Rationale</label>
                <textarea
                  id="proposal-rationale"
                  name="rationale"
                  className="w-full border border-kfl-border rounded p-2 text-sm focus:border-kfl-blue focus:outline-none"
                  placeholder="Why is this change needed?"
                  value={submitRationale}
                  onChange={(e) => setSubmitRationale(e.target.value)}
                  rows={3}
                />
              </div>
              <div>
                <label htmlFor="proposal-severity" className="block text-xs font-semibold text-kfl-muted mb-1">Severity</label>
                <select
                  id="proposal-severity"
                  name="severity"
                  className="w-full border border-kfl-border rounded p-2 text-sm focus:border-kfl-blue focus:outline-none"
                  value={submitSeverity}
                  onChange={(e) => setSubmitSeverity(e.target.value)}
                >
                  <option value="minor">Minor</option>
                  <option value="major">Major</option>
                  <option value="critical">Critical</option>
                </select>
              </div>
              <div className="pt-3 border-t border-kfl-border text-xs text-kfl-muted">
                <p><strong>Original text:</strong> {originalContent.length} chars</p>
                <p><strong>Proposed text:</strong> {currentContent.length} chars</p>
              </div>
            </div>
            <div className="mt-6 flex gap-2 justify-end">
              <button onClick={() => setShowSubmit(false)} className="app-btn-secondary px-4 py-2 text-sm">Cancel</button>
              <button
                onClick={handleSubmitProposal}
                disabled={submitting || previewLoading || !proposalPreview?.changes?.length || !selectedChangeSequences.length || !hasChanges}
                className="app-btn-primary px-4 py-2 text-sm disabled:opacity-50"
              >
                {submitting ? "Submitting…" : "Submit Proposal"}
              </button>
            </div>
          </div>
        </div>
      )}
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
                  <span className={`app-status ${d.status === "published" ? "app-status-healthy" : d.status === "draft" ? "app-status-warning" : "app-status-info"}`}>{d.status}</span>
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
