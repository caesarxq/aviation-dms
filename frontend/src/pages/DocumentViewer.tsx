import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import api from "../api/client";
import { ArrowLeft, Copy } from "lucide-react";
import { sanitizeHtml } from "../utils/sanitizeHtml";

export function DocumentViewer() {
  const { docId } = useParams();
  const { data: content, isLoading } = useQuery({
    queryKey: ["doc-content", docId],
    queryFn: () => api.get(`/p0/documents/${docId}/content`).then((r: any) => r.data),
    enabled: !!docId,
  });

  if (isLoading) return <div className="app-page"><div className="app-surface p-10 text-center text-sm text-kfl-muted">Loading document…</div></div>;
  if (!content) return <div className="app-page"><div className="app-surface p-10 text-center text-sm text-kfl-muted">Document not found</div></div>;

  return (
    <div className="app-page">
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

      <section className="app-surface p-5">
        {/* PDF2HTML EX output uses absolute positioning for text elements.
            Wrap in a fixed page-sized container and scale to fit viewport. */}
        <div className="relative w-full h-[calc(100vh-220px)] overflow-auto bg-white">
          <div className="transform origin-[0_0] scale-[0.5] w-[850px] h-[1100px]">
            <div className="prose prose-lg max-w-none whitespace-pre-wrap bg-white p-4 rounded border border-kfl-border">
              {content.content ? (
                <div dangerouslySetInnerHTML={{ __html: sanitizeHtml(content.content) }} />
              ) : (
                <p className="text-kfl-muted italic">No content available for this document.</p>
              )}
            </div>
          </div>
        </div>
      </section>

      <section className="app-surface p-5">
        <h2 className="font-semibold mb-2 text-kfl-text">Version Details</h2>
        <dl className="grid grid-cols-2 gap-4 text-sm">
          <dt className="font-medium text-kfl-muted">Document ID</dt>
          <dd className="font-mono text-kfl-text">{content.document_id}</dd>
          <dt className="font-medium text-kfl-muted">Version ID</dt>
          <dd className="font-mono text-kfl-text">{content.version_id}</dd>
          <dt className="font-medium text-kfl-muted">Version Number</dt>
          <dd className="font-kfl-text">{content.version_number}</dd>
          <dt className="font-medium text-kfl-muted">State</dt>
          <dd>
            <span className={`app-status ${content.state === "published" ? "app-status-healthy" : content.state === "draft" ? "app-status-warning" : content.state === "approved" ? "app-status-info" : "app-status-info"}`}>{content.state}</span>
          </dd>
          <dt className="font-medium text-kfl-muted">KCAA Approved</dt>
          <dd>
            <span className={`app-status ${content.kcaa_approved === 1 ? "app-status-healthy" : "app-status-critical"}`}>
              {content.kcaa_approved === 1 ? "Yes" : "No"}
            </span>
          </dd>
          <dt className="font-medium text-kfl-muted">Created</dt>
          <dd className="font-mono text-kfl-text">{content.created_at}</dd>
          <dt className="font-medium text-kfl-muted">Updated</dt>
          <dd className="font-mono text-kfl-text">{content.updated_at}</dd>
        </dl>
      </section>
    </div>
  );
}