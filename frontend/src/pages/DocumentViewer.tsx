import { useParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "../api/client";
import {
  ArrowLeft,
  Copy,
  Check,
  X,
  Maximize2,
  Minimize2,
  ListTree,
  Download,
} from "lucide-react";
import { useRef, useEffect, useState, useCallback } from "react";
import {
  DocumentOutline,
  buildOutlineFromHtml,
  type OutlineItem,
} from "../components/documents/DocumentOutline";

const DOCUMENT_CSP =
  '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; script-src \'none\'; img-src data: blob:; font-src data:; style-src \'unsafe-inline\' data:; media-src data: blob:; object-src \'none\'; connect-src \'none\'; frame-src \'none\'; form-action \'none\'; base-uri \'none\'>';

function addDocumentCsp(source: string): string {
  const isHtmlDocument = /<(?:!doctype\s+html|html\b|head\b|body\b|div\b|p\b|h[1-6]\b|table\b|span\b|section\b)/i.test(source);
  if (!isHtmlDocument) {
    const escapedText = source.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    return `<!doctype html><html><head><meta charset="utf-8"></head><body><pre>${escapedText}</pre></body></html>`;
  }
  const head = /<head\b[^>]*>/i.exec(source);
  if (head && head.index !== undefined) {
    const insertAt = head.index + head[0].length;
    return `${source.slice(0, insertAt)}${DOCUMENT_CSP}${source.slice(insertAt)}`;
  }
  const html = /<html\b[^>]*>/i.exec(source);
  if (html && html.index !== undefined) {
    const insertAt = html.index + html[0].length;
    return `${source.slice(0, insertAt)}<head>${DOCUMENT_CSP}</head>${source.slice(insertAt)}`;
  }
  return `<!doctype html><html><head>${DOCUMENT_CSP}</head><body>${source}</body></html>`;
}

function annotationText(annotation: any): string {
  const target = String(annotation.target_ref || "").trim();
  const marker = "Selected text:";
  const markerIndex = target.toLowerCase().lastIndexOf(marker.toLowerCase());
  if (markerIndex >= 0) return target.slice(markerIndex + marker.length).trim().slice(0, 500);
  if (target.startsWith("selection:")) {
    const start = target.indexOf('"');
    const end = target.lastIndexOf('"');
    if (start >= 0 && end > start) return target.slice(start + 1, end).slice(0, 500);
  }
  return target.slice(0, 500);
}

function applyAnnotationHighlights(doc: Document, annotations: any[]) {
  const highlights = annotations.filter((annotation) => annotation.status !== "dismissed");
  for (const annotation of highlights) {
    const target = annotationText(annotation);
    if (!target) continue;
    const walker = doc.createTreeWalker(doc.body, NodeFilter.SHOW_TEXT);
    let node: Node | null;
    while ((node = walker.nextNode())) {
      const parent = node.parentElement;
      if (!parent || parent.closest("[data-kfl-annotation]") || !node.textContent) continue;
      const text = node.textContent;
      const index = text.indexOf(target);
      if (index < 0 || !node.parentNode) continue;
      const before = doc.createTextNode(text.slice(0, index));
      const match = doc.createElement("mark");
      match.dataset.kflAnnotation = annotation.annotation_id;
      match.className = "kfl-document-annotation";
      match.textContent = target;
      const after = doc.createTextNode(text.slice(index + target.length));
      node.parentNode.insertBefore(before, node);
      node.parentNode.insertBefore(match, node);
      node.parentNode.insertBefore(after, node.nextSibling);
      node.parentNode.removeChild(node);
      break;
    }
  }
}

export function DocumentViewer() {
  const { docId } = useParams();
  const viewerShellRef = useRef<HTMLDivElement>(null);
  const qc = useQueryClient();
  const [isFullscreen, setIsFullscreen] = useState(false);

  const { data: content, isLoading } = useQuery({
    queryKey: ["doc-content", docId],
    queryFn: () => api.get(`/p0/documents/${docId}/content`).then((r: any) => r.data),
    enabled: !!docId,
  });
  const { data: attachedFiles = [] } = useQuery({
    queryKey: ["doc-files", docId],
    queryFn: () => api.get(`/p0/documents/${docId}/files`).then((r: any) => r.data),
    enabled: !!docId,
  });
  const downloadFileMutation = useMutation({
    mutationFn: async ({ fileId, originalFilename }: { fileId: string; originalFilename: string }) => {
      const response = await api.get(`/p0/documents/${docId}/file/${fileId}`, {
        responseType: "blob",
      });
      const contentType = response.headers["content-type"] as string;
      const blob = new Blob([response.data], { type: contentType });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = originalFilename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    },
  });
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const parentObservedDocumentRef = useRef<Document | null>(null);
  const selectionHandlerRef = useRef<EventListener | null>(null);
  const annotationCommentRef = useRef<HTMLTextAreaElement>(null);
  const selectionOpenerRef = useRef<HTMLElement | null>(null);
  const [iframeReady, setIframeReady] = useState(false);
  const [selection, setSelection] = useState<{ text: string; x: number; y: number } | null>(null);
  const [annotationType, setAnnotationType] = useState<"comment" | "highlight">("comment");
  const [annotationContent, setAnnotationContent] = useState("");
  const [annotationTarget, setAnnotationTarget] = useState("");
  const [showOutline, setShowOutline] = useState(false);
  const [activeOutlineAnchor, setActiveOutlineAnchor] = useState("");
  const outlineItems = buildOutlineFromHtml(content?.content || "");

  useEffect(() => {
    if (!iframeRef.current || !content) return;
    iframeRef.current.srcdoc = addDocumentCsp(content.content || "");
  }, [content?.content]);

  const closeAnnotationDialog = useCallback(() => {
    setSelection(null);
    selectionOpenerRef.current?.focus();
  }, []);

  const { data: annotations = [], isLoading: annLoading } = useQuery({
    queryKey: ["annotations", docId],
    queryFn: () => api.get(`/p2/documents/${docId}/annotations`).then((r: any) => r.data),
    enabled: !!docId,
  });

  useEffect(() => {
    const handleFullscreen = () => setIsFullscreen(document.fullscreenElement === viewerShellRef.current);
    document.addEventListener("fullscreenchange", handleFullscreen);
    return () => document.removeEventListener("fullscreenchange", handleFullscreen);
  }, []);

  const toggleFullscreen = async () => {
    const shell = viewerShellRef.current;
    if (!shell) return;
    try {
      if (document.fullscreenElement) {
        await document.exitFullscreen?.();
      } else if (shell.requestFullscreen) {
        await shell.requestFullscreen();
      } else {
        setIsFullscreen((value) => !value);
      }
    } catch {
      setIsFullscreen((value) => !value);
    }
  };

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: any }) => api.patch(`/p2/annotations/${id}`, data).then((r: any) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["annotations"] }),
  });

  const createMutation = useMutation({
    mutationFn: (data: any) => api.post(`/p2/documents/${docId}/annotations`, data).then((r: any) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["annotations", docId] });
      setAnnotationContent("");
      setAnnotationTarget("");
      closeAnnotationDialog();
    },
  });

  const handleFrameLoad = useCallback(() => {
    const frameDocument = iframeRef.current?.contentDocument;
    if (!frameDocument) return;
    if (parentObservedDocumentRef.current && selectionHandlerRef.current) {
      parentObservedDocumentRef.current.removeEventListener("mouseup", selectionHandlerRef.current);
      parentObservedDocumentRef.current.removeEventListener("keyup", selectionHandlerRef.current);
    }
    const onSelection: EventListener = () => {
      const frameWindow = frameDocument.defaultView;
      const selectedRange = frameWindow?.getSelection();
      const selected = selectedRange?.toString().trim() || "";
      if (!selected || !selectedRange?.rangeCount) return;
      selectionOpenerRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : iframeRef.current;
      const frameRect = iframeRef.current?.getBoundingClientRect();
      const range = selectedRange.getRangeAt(0);
      const rangeRect = typeof range.getBoundingClientRect === "function" ? range.getBoundingClientRect() : null;
      setSelection({
        text: selected.slice(0, 500),
        x: (frameRect?.left || 0) + (rangeRect?.left || 16),
        y: Math.max(8, (frameRect?.top || 0) + (rangeRect?.top || 16) - 12),
      });
    };
    frameDocument.addEventListener("mouseup", onSelection);
    frameDocument.addEventListener("keyup", onSelection);
    parentObservedDocumentRef.current = frameDocument;
    selectionHandlerRef.current = onSelection;
    setIframeReady(true);
  }, []);

  useEffect(() => {
    if (selection) annotationCommentRef.current?.focus();
  }, [selection]);

  useEffect(() => {
    if (parentObservedDocumentRef.current && selectionHandlerRef.current) {
      parentObservedDocumentRef.current.removeEventListener("mouseup", selectionHandlerRef.current);
      parentObservedDocumentRef.current.removeEventListener("keyup", selectionHandlerRef.current);
    }
  }, []);

  useEffect(() => {
    const frameDocument = iframeRef.current?.contentDocument;
    if (iframeReady && frameDocument && annotations.length) {
      applyAnnotationHighlights(frameDocument, annotations);
    }
  }, [annotations, iframeReady]);

  const submitAnnotation = () => {
    if (!selection) return;
    createMutation.mutate({
      annotation_type: annotationType,
      target_ref: `${annotationTarget.trim() ? `${annotationTarget.trim()} — ` : ""}Selected text: ${selection.text}`,
      content: annotationContent.trim(),
      status: "open",
    });
  };

  const selectOutlineItem = (item: OutlineItem) => {
    setActiveOutlineAnchor(item.anchorId);
    const frameDocument = iframeRef.current?.contentDocument;
    if (!frameDocument) return;
    const selector = item.anchorId.startsWith("page-") ? ".pf" : item.anchorId.startsWith("heading-") ? ".t" : "h1, h2, h3, h4, h5, h6, p, li, tr, figcaption, caption, blockquote, div";
    const target = frameDocument.querySelectorAll(selector)[item.blockIndex] as HTMLElement | undefined;
    if (!target) return;
    target.scrollIntoView?.({ behavior: "auto", block: "center" });
    target.classList.add("kfl-outline-target-highlight");
    window.setTimeout(() => target.classList.remove("kfl-outline-target-highlight"), 2500);
  };

  const handleResolve = (id: string) => {
    updateMutation.mutate({ id, data: { status: "resolved" } });
  };

  const handleDismiss = (id: string) => {
    updateMutation.mutate({ id, data: { status: "dismissed" } });
  };

  const getStatusColor = (status: string) => {
    if (status === "resolved") return "bg-green-100 text-green-800";
    if (status === "dismissed") return "bg-gray-100 text-gray-800";
    return "bg-blue-100 text-blue-800";
  };

  if (isLoading) return <div className="app-page"><div className="app-surface p-10 text-center text-sm text-kfl-muted">Loading document…</div></div>;
  if (!content) return <div className="app-page"><div className="app-surface p-10 text-center text-sm text-kfl-muted">Document not found</div></div>;

  return (
    <div ref={viewerShellRef} className={isFullscreen ? "fixed inset-0 z-50 overflow-auto bg-kfl-canvas p-4" : "app-page relative"}>
      <header className="app-page-header">
        <div>
          <div className="app-eyebrow">Document Control</div>
          <h1 className="app-title">{docId}</h1>
          <p className="app-subtitle">
            Version {content.version_number} • State: {content.state}
            {content.kcaa_approved ? " • KCAA Approved" : ""}
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setShowOutline((value) => !value)}
            className={`app-btn-secondary px-3 py-2 flex items-center gap-1 ${showOutline ? "bg-kfl-blue/10" : ""}`}
            aria-label={showOutline ? "Hide document outline" : "Show document outline"}
          >
            <ListTree size={16} /> {showOutline ? "Hide outline" : "Outline"}
          </button>
          <button
            onClick={toggleFullscreen}
            className="app-btn-secondary px-3 py-2 flex items-center gap-1"
            title={isFullscreen ? "Exit fullscreen" : "Enter fullscreen"}
          >
            {isFullscreen ? <Minimize2 size={16} /> : <Maximize2 size={16} />}
            {isFullscreen ? "Exit fullscreen" : "Fullscreen"}
          </button>
          <button
            onClick={() => navigator.clipboard.writeText(content.content || "")}
            className="app-btn-secondary px-3 py-2 flex items-center gap-1"
          >
            <Copy size={16} /> Copy Content
          </button>
          {attachedFiles.length > 0 && (
            <div className="flex items-center gap-2 border-l border-kfl-border pl-3">
              <div className="text-xs text-kfl-muted">Attached files:</div>
              {attachedFiles.map((f: any) => (
                <button
                  key={f.file_id}
                  onClick={() => downloadFileMutation.mutate({ fileId: f.file_id, originalFilename: f.original_filename })}
                  className="app-btn-secondary px-2 py-1 text-xs hover:bg-kfl-blue/10"
                  title={`Download ${f.original_filename} (${f.file_size} bytes)`}
                >
                  <Download size={12} /> {f.original_filename.length > 20 ? `${f.original_filename.slice(0, 17)}…` : f.original_filename}
                </button>
              ))}
            </div>
          )}
          <button
            onClick={() => window.history.back()}
            className="app-btn-secondary px-3 py-2 flex items-center gap-1"
          >
            <ArrowLeft size={16} /> Back
          </button>
        </div>
      </header>
      {selection && (
        <div
          className="fixed z-50 max-w-sm rounded border border-kfl-border bg-white p-3 shadow-lg"
          style={{ left: selection.x, top: selection.y }}
          role="dialog"
          aria-label="Add document annotation"
        >
          <p className="mb-2 text-xs text-kfl-muted">Selected: "{selection.text}"</p>
          <div className="mb-2 flex gap-2">
            <button type="button" onClick={() => setAnnotationType("comment")} className="app-btn-secondary px-2 py-1 text-xs">
              Comment
            </button>
            <button type="button" onClick={() => setAnnotationType("highlight")} className="app-btn-secondary px-2 py-1 text-xs">
              Highlight
            </button>
          </div>
          <label htmlFor="document-annotation-comment" className="mb-1 block text-xs font-semibold">
            Comment
          </label>
          <textarea ref={annotationCommentRef} id="document-annotation-comment" name="content" className="app-input mb-2 w-full" rows={2} value={annotationContent} onChange={(event) => setAnnotationContent(event.target.value)} />
          <label htmlFor="document-annotation-target" className="mb-1 block text-xs font-semibold">
            Target reference
          </label>
          <input id="document-annotation-target" name="target_ref" className="app-input mb-2 w-full" value={annotationTarget} onChange={(event) => setAnnotationTarget(event.target.value)} placeholder="Optional section reference" />
          <div className="flex justify-end gap-2">
            <button type="button" className="app-btn-secondary px-3 py-1 text-xs" onClick={closeAnnotationDialog}>
              Cancel
            </button>
            <button type="button" className="app-btn-primary px-3 py-1 text-xs" onClick={submitAnnotation} disabled={createMutation.isPending}>
              {createMutation.isPending ? "Saving…" : "Add Annotation"}
            </button>
          </div>
        </div>
      )}
      <section className="app-surface p-5">
        <div className={`flex gap-4 ${isFullscreen ? "h-[calc(100vh-170px)]" : "h-[calc(100vh-220px)]"}`}>
          {showOutline && (
            <aside className="w-72 shrink-0 overflow-y-auto rounded border border-kfl-border bg-kfl-surface-subtle">
              <DocumentOutline items={outlineItems} activeAnchor={activeOutlineAnchor} onSelect={selectOutlineItem} />
            </aside>
          )}
          <div className="relative min-w-0 flex-1 overflow-hidden rounded border border-kfl-border bg-white">
            <iframe
              ref={iframeRef}
              title={docId || "Document"}
              className="h-full w-full border-0"
              sandbox="allow-same-origin"
              onLoad={handleFrameLoad}
            />
          </div>
        </div>
      </section>

      {/* Annotation list */}
      <section className="app-surface p-5 mt-4">
        <div className="flex justify-between items-center mb-3">
          <h2 className="font-semibold text-kfl-text">Annotations ({annotations.length})</h2>
        </div>
        <p className="mb-3 text-sm text-kfl-muted">Select text in the document to create a comment or highlight. Rendering runs without document scripts or external network resources.</p>
        {annLoading ? (
          <div className="p-8 text-kfl-muted text-center">Loading annotations…</div>
        ) : annotations.length === 0 ? (
          <div className="p-8 text-center text-kfl-muted">No annotations yet.</div>
        ) : (
          <div className="space-y-3">
            {annotations.map((a: any) => (
              <div key={a.annotation_id} className="border border-kfl-border rounded p-3 bg-kfl-surface">
                <div className="flex justify-between items-start mb-2">
                  <div className="flex items-center gap-2">
                    <span className={`px-2 py-0.5 rounded text-xs font-semibold ${getStatusColor(a.status)}`}>{a.status}</span>
                    <span className={`text-xs ${a.annotation_type === "comment" ? "text-blue-600" : "text-yellow-600"}`}>{a.annotation_type}</span>
                    <span className="text-xs text-kfl-muted font-mono ml-2">{a.annotation_id}</span>
                  </div>
                  <div className="flex gap-1">
                    {a.status !== "resolved" && (
                      <button onClick={() => handleResolve(a.annotation_id)} className="text-xs text-green-600 hover:text-green-800 flex items-center gap-1">
                        <Check size={12} /> Resolve
                      </button>
                    )}
                    <button onClick={() => handleDismiss(a.annotation_id)} className="text-xs text-red-600 hover:text-red-800 flex items-center gap-1">
                      <X size={12} /> Dismiss
                    </button>
                  </div>
                </div>
                <div className="text-sm text-kfl-secondary mb-2">{a.target_ref || "No target reference"}</div>
                <div className="text-sm text-kfl-text whitespace-pre-wrap">{a.content || "No content"}</div>
                <div className="text-xs text-kfl-muted mt-2">Created: {a.created_at || "—"}</div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

export default DocumentViewer;
