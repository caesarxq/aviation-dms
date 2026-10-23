import { useParams } from "react-router-dom";
import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "../api/client";
import { Eye, Save, ArrowLeft } from "lucide-react";
import { sanitizeHtml } from "../utils/sanitizeHtml";

export function DocumentEditor() {
  const { docId: routeDocId } = useParams<{ docId: string }>();
  const [docId, setDocId] = useState(routeDocId || "");

  return (
    <div className="app-page">
      <header className="app-page-header">
        <div>
          <div className="app-eyebrow">Document Control</div>
          <h1 className="app-title">Document Editor</h1>
          <p className="app-subtitle">Edit controlled document versions and manage the KCAA approval gate.</p>
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
  const qc = useQueryClient();
  const { data: content, isLoading } = useQuery({
    queryKey: ["doc-content", docId],
    queryFn: () => api.get(`/p0/documents/${docId}/content`).then((r: any) => r.data),
    enabled: !!docId,
  });

  const [editContent, setEditContent] = useState("");
  useEffect(() => {
    if (content?.content !== undefined) {
      setEditContent(content.content || "");
    }
  }, [content?.content]);
  const [changeSummary, setChangeSummary] = useState("");
  const [showPreview, setShowPreview] = useState(false);
  const [saving, setSaving] = useState(false);

  const updateMutation = useMutation({
    mutationFn: async (data: { content: string; change_summary?: string }) => {
      const resp = await fetch(`/api/p0/documents/${docId}/content`, {
        method: "PUT",
        headers: { "Content-Type": "application/json", "X-Role": "system_admin", "X-Actor": "admin" },
        body: JSON.stringify(data),
      });
      if (!resp.ok) throw new Error("Failed to save");
      return resp.json();
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["doc-content", docId] });
      setSaving(false);
    },
  });

  const handleSave = () => {
    setSaving(true);
    updateMutation.mutate({ content: editContent, change_summary: changeSummary });
  };

  if (isLoading) return <div className="app-surface p-10 text-center text-sm text-kfl-muted">Loading document…</div>;

  return (
    <div className="flex flex-col h-full">
      <div className="flex justify-between items-center mb-4 border-b border-kfl-border px-5 py-4">
        <div>
          <h2 className="text-lg font-bold text-kfl-text">{docId}</h2>
          <p className="text-xs text-kfl-muted">Version content editor</p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setShowPreview(!showPreview)}
            className="app-btn-secondary px-3 py-2 flex items-center gap-1"
          >
            <Eye size={16} /> {showPreview ? "Edit" : "Preview"}
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="app-btn-primary px-4 py-2 flex items-center gap-1"
          >
            <Save size={16} /> {saving ? "Saving…" : "Save as Draft"}
          </button>
          <button
            onClick={() => setDocId("")}
            className="app-btn-secondary px-3 py-2 flex items-center gap-1"
          >
            <ArrowLeft size={16} /> Back
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-hidden">
        {showPreview ? (
          <div className="h-full overflow-auto p-6 bg-white">
            <div
              className="whitespace-pre-wrap font-sans text-sm"
              dangerouslySetInnerHTML={{ __html: sanitizeHtml(editContent || "No content.") }}
            />
          </div>
        ) : (
          <div className="h-full flex">
            <div className="flex-1 h-full border-r border-kfl-border p-4">
              <textarea
                className="w-full h-full p-3 font-mono text-sm resize-none focus:outline-none"
                value={editContent}
                onChange={(e) => setEditContent(e.target.value)}
                placeholder="Enter document content (HTML supported)..."
              />
            </div>
            <div className="w-1/4 h-full overflow-auto p-4 bg-kfl-surface-subtle">
              <h3 className="font-semibold mb-2 text-kfl-text">Change Summary</h3>
              <textarea
                className="w-full p-2 border border-kfl-border rounded resize-none focus:outline-none mb-4"
                value={changeSummary}
                onChange={(e) => setChangeSummary(e.target.value)}
                placeholder="Describe the changes..."
                rows={3}
              />
              <div className="text-xs text-kfl-muted space-y-2">
                <p><strong>Version:</strong> Auto-incremented</p>
                <p><strong>State:</strong> Draft</p>
                <p><strong>KCAA Gate:</strong> Required before publish</p>
              </div>
            </div>
          </div>
        )}
      </div>
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