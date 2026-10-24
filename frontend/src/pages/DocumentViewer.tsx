import { useParams, useSearchParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "../api/client";
import { ArrowLeft, Copy, Check, X, ListTree, Maximize2, Minimize2 } from "lucide-react";
import { useRef, useEffect, useState } from "react";
import { DocumentOutline, buildOutlineFromHtml } from "../components/documents/DocumentOutline";

export function DocumentViewer() {
  const { docId } = useParams();
  const [searchParams] = useSearchParams();
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const viewerShellRef = useRef<HTMLDivElement>(null);
  const qc = useQueryClient();
  const [annotationToolbar, setAnnotationToolbar] = useState<{ show: boolean; x: number; y: number; selectedText: string }>({ show: false, x: 0, y: 0, selectedText: "" });
  const [newAnnotationType, setNewAnnotationType] = useState<"comment" | "highlight">("comment");
  const [annotationContent, setAnnotationContent] = useState("");
  const [annotationTargetRef, setAnnotationTargetRef] = useState("");
  const [iframeReady, setIframeReady] = useState(false);
  const [showOutline, setShowOutline] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [activeOutlineAnchor, setActiveOutlineAnchor] = useState(searchParams.get("section") || "");

  const { data: content, isLoading } = useQuery({
    queryKey: ["doc-content", docId],
    queryFn: () => api.get(`/p0/documents/${docId}/content`).then((r: any) => r.data),
    enabled: !!docId,
  });

  const { data: annotations = [], isLoading: annLoading } = useQuery({
    queryKey: ["annotations", docId],
    queryFn: () => api.get(`/p2/documents/${docId}/annotations`).then((r: any) => r.data),
    enabled: !!docId,
  });

  const outlineItems = buildOutlineFromHtml(content?.content || "");

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

  const selectOutlineItem = (item: { anchorId: string; blockIndex: number }) => {
    setActiveOutlineAnchor(item.anchorId);
    const iframeDocument = iframeRef.current?.contentDocument;
    if (!iframeDocument) return;
    const selector = item.anchorId.startsWith("page-")
      ? ".pf"
      : item.anchorId.startsWith("heading-")
        ? ".t"
        : "h1, h2, h3, h4, h5, h6, p, li, tr, figcaption, caption, blockquote, div";
    const blocks = iframeDocument.querySelectorAll(selector);
    const target = blocks[item.blockIndex] as HTMLElement | undefined;
    if (!target) return;
    const pageFrame = target.closest(".pf") as HTMLElement | null;
    const container = iframeDocument.querySelector("#page-container") as HTMLElement | null;
    if ((item.anchorId.startsWith("page-") || item.anchorId.startsWith("heading-")) && container && pageFrame) {
      container.scrollTop = pageFrame.offsetTop;
      container.dispatchEvent(new Event("scroll"));
    } else {
      target.scrollIntoView?.({ behavior: "auto", block: "center" });
    }
    target.classList.add("kfl-outline-target-highlight");
    window.setTimeout(() => target.classList.remove("kfl-outline-target-highlight"), 2500);
  };

  const createMutation = useMutation({
    mutationFn: (data: any) => api.post(`/p2/documents/${docId}/annotations`, data).then((r: any) => r.data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["annotations"] }); closeToolbar(); },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: any }) => api.patch(`/p2/annotations/${id}`, data).then((r: any) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["annotations"] }),
  });

  const closeToolbar = () => setAnnotationToolbar({ show: false, x: 0, y: 0, selectedText: "" });

  // Listen for postMessage from iframe (text selection events)
  useEffect(() => {
    const handleMessage = (event: MessageEvent) => {
      if (event.origin !== window.location.origin) return;
      const { type, payload } = event.data || {};
      if (type === "TEXT_SELECTED") {
        setAnnotationToolbar({ show: true, x: payload.x, y: payload.y, selectedText: payload.text });
      }
    };
    window.addEventListener("message", handleMessage);
    return () => window.removeEventListener("message", handleMessage);
  }, []);

  // Render the source document once, then attach the annotation bridge without rewriting the iframe on load.
  useEffect(() => {
    const iframe = iframeRef.current;
    const html = content?.content;
    if (!iframe || !html) return;
    const doc = iframe.contentDocument || iframe.contentWindow?.document;
    if (!doc) return;

    setIframeReady(false);
    doc.open();
    doc.write(html);
    doc.close();

    const script = doc.createElement("script");
    script.textContent = `
      (function() {
        document.addEventListener('mouseup', function() {
          var sel = window.getSelection();
          var text = sel ? sel.toString().trim() : '';
          if (!text || !sel || sel.rangeCount === 0) return;
          var rect = sel.getRangeAt(0).getBoundingClientRect();
          window.parent.postMessage({
            type: 'TEXT_SELECTED',
            payload: {
              text: text,
              x: rect.left + window.scrollX + 10,
              y: rect.top + window.scrollY - 40
            }
          }, window.location.origin);
        });

        window.addEventListener('message', function(event) {
          if (event.origin !== window.location.origin || !event.data || event.data.type !== 'RENDER_HIGHLIGHTS') return;
          var highlights = event.data.payload.highlights || [];
          highlights.forEach(function(h) {
            var walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null, false);
            var node;
            var nodesToWrap = [];
            while (node = walker.nextNode()) {
              if (node.parentElement && !node.parentElement.classList.contains('kfl-annotation') && node.textContent.indexOf(h.text) >= 0) {
                nodesToWrap.push({node: node, text: h.text, id: h.id, type: h.type, status: h.status});
              }
            }
            nodesToWrap.forEach(function(item) {
              var text = item.node.textContent;
              var idx = text.indexOf(item.text);
              if (idx < 0 || !item.node.parentNode) return;
              var before = document.createTextNode(text.substring(0, idx));
              var matchText = text.substring(idx, idx + item.text.length);
              var after = document.createTextNode(text.substring(idx + item.text.length));
              var span = document.createElement('span');
              span.className = 'kfl-annotation kfl-' + item.type + ' kfl-status-' + item.status;
              span.title = 'Annotation #' + item.id + ' (' + item.status + ')';
              span.style.backgroundColor = item.type === 'comment' ? '#dbeafe' : '#fef3c7';
              span.style.borderBottom = '2px solid';
              span.style.borderBottomColor = item.type === 'comment' ? '#3b82f6' : '#d97706';
              span.style.cursor = 'pointer';
              span.textContent = matchText;
              var parent = item.node.parentNode;
              parent.insertBefore(before, item.node);
              parent.insertBefore(span, item.node);
              parent.insertBefore(after, item.node.nextSibling);
              parent.removeChild(item.node);
            });
          });
        });
      })();
    `;
    (doc.body || doc.documentElement).appendChild(script);
    setIframeReady(true);
  }, [content]);

  // Inject annotations into iframe as highlights
  useEffect(() => {
    const iframe = iframeRef.current;
    if (!iframe || !annotations) return;
    const doc = iframe.contentDocument || iframe.contentWindow?.document;
    if (!doc) return;

    const highlights = annotations.map((a: any) => ({
      id: a.annotation_id,
      text: a.target_ref || a.content?.substring(0, 50) || "annotation",
      type: a.annotation_type || "comment",
      status: a.status || "open",
    }));

    iframe.contentWindow?.postMessage(
      { type: "RENDER_HIGHLIGHTS", payload: { highlights } },
      window.location.origin
    );
  }, [annotations, iframeReady]);

  useEffect(() => {
    const match = searchParams.get("section")?.match(/^block-(\d+)$/);
    if (!match || !iframeReady) return;
    selectOutlineItem({ anchorId: `block-${Number(match[1])}`, blockIndex: Number(match[1]) });
  }, [iframeReady, searchParams]);

  const handleSubmitAnnotation = () => {
    createMutation.mutate({
      annotation_type: newAnnotationType,
      target_ref: annotationTargetRef || `selection: "${annotationToolbar.selectedText.substring(0, 60)}"`,
      content: annotationContent,
      status: "open",
    });
    setAnnotationContent("");
    setAnnotationTargetRef("");
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
            title={showOutline ? "Hide document outline" : "Show document outline"}
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
          <button
            onClick={() => window.history.back()}
            className="app-btn-secondary px-3 py-2 flex items-center gap-1"
          >
            <ArrowLeft size={16} /> Back
          </button>
        </div>
      </header>

      {/* Annotation toolbar (floating, positioned by iframe postMessage) */}
      {annotationToolbar.show && (
        <div className="fixed z-50 bg-white border border-kfl-border rounded shadow-lg p-3" style={{ left: annotationToolbar.x, top: annotationToolbar.y }}>
          <div className="text-xs font-semibold text-kfl-muted mb-2">Selected: "{annotationToolbar.selectedText.substring(0, 50)}{annotationToolbar.selectedText.length > 50 ? "…" : ""}"</div>
          <div className="flex gap-2 mb-2">
            <button onClick={() => setNewAnnotationType("comment")} className={`px-2 py-1 text-xs rounded ${newAnnotationType === "comment" ? "bg-kfl-primary text-white" : "bg-kfl-surface text-kfl-muted"}`}>Comment</button>
            <button onClick={() => setNewAnnotationType("highlight")} className={`px-2 py-1 text-xs rounded ${newAnnotationType === "highlight" ? "bg-kfl-primary text-white" : "bg-kfl-surface text-kfl-muted"}`}>Highlight</button>
          </div>
          <textarea id="add_a_comment_284" name="add_a_comment"
            className="w-full h-16 p-2 border border-kfl-border rounded text-sm resize-none focus:outline-none mb-2"
            value={annotationContent}
            onChange={e => setAnnotationContent(e.target.value)}
            placeholder="Add a comment…"
          />
          <input id="target_reference_290" name="target_reference"
            className="w-full p-2 border border-kfl-border rounded text-sm focus:outline-none mb-2"
            value={annotationTargetRef}
            onChange={e => setAnnotationTargetRef(e.target.value)}
            placeholder="Target reference (e.g., section 3.2, line 15)"
          />
          <div className="flex justify-end gap-2">
            <button onClick={closeToolbar} className="app-btn-secondary text-xs px-3 py-1.5">Cancel</button>
            <button onClick={handleSubmitAnnotation} className="app-btn-primary text-xs px-3 py-1.5" disabled={createMutation.isPending}>
              {createMutation.isPending ? "Saving…" : "Add Annotation"}
            </button>
          </div>
        </div>
      )}

      <section className="app-surface p-5">
        <div className={`flex gap-4 ${isFullscreen ? "h-[calc(100vh-170px)]" : "h-[calc(100vh-220px)]"}`}>
          {showOutline && (
            <aside className="relative z-20 w-72 shrink-0 overflow-y-auto rounded border border-kfl-border bg-kfl-surface-subtle pointer-events-auto">
              <DocumentOutline
                items={outlineItems}
                activeAnchor={activeOutlineAnchor}
                onSelect={selectOutlineItem}
              />
            </aside>
          )}
          <div className="relative min-w-0 flex-1 overflow-hidden rounded border border-kfl-border bg-white">
            <iframe
              ref={iframeRef}
              title={docId || "Document"}
              className="h-full w-full border-0"
              sandbox="allow-same-origin allow-scripts allow-popups"
            />
          </div>
        </div>
      </section>

      {/* Annotation list */}
      <section className="app-surface p-5 mt-4">
        <div className="flex justify-between items-center mb-3">
          <h2 className="font-semibold text-kfl-text">Annotations ({annotations.length})</h2>
          <button onClick={() => setAnnotationToolbar({ show: false, x: 0, y: 0, selectedText: "" })} className="text-xs text-kfl-muted hover:text-kfl-text underline">Close</button>
        </div>
        {annLoading ? (
          <div className="p-8 text-kfl-muted text-center">Loading annotations…</div>
        ) : annotations.length === 0 ? (
          <div className="p-8 text-center text-kfl-muted">No annotations yet. Select text in the document to add one.</div>
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
                      <button onClick={() => handleResolve(a.annotation_id)} className="text-xs text-green-600 hover:text-green-800 flex items-center gap-1"><Check size={12} /> Resolve</button>
                    )}
                    <button onClick={() => handleDismiss(a.annotation_id)} className="text-xs text-red-600 hover:text-red-800 flex items-center gap-1"><X size={12} /> Dismiss</button>
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

      <style>{`
        .kfl-annotation { position: relative; }
        .kfl-annotation:hover { z-index: 10; }
        .kfl-outline-target-highlight { outline: 3px solid #1B7ABF; outline-offset: 4px; transition: outline-color 200ms ease; }
      `}</style>
    </div>
  );
}

export default DocumentViewer;
