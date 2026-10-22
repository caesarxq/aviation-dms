import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "../api/client";
import { Eye, Save, ArrowLeft } from "lucide-react";

export function DocumentEditor() {
  const [docId, setDocId] = useState("");

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">Document Editor</h1>
        <button
          onClick={() => setDocId("")}
          disabled={!docId}
          className="px-3 py-2 text-sm border rounded hover:bg-gray-100 disabled:opacity-50"
        >
          <ArrowLeft size={16} /> Back to List
        </button>
      </div>

      {/* Document selector */}
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

  if (isLoading) return <div className="p-6">Loading document...</div>;

  return (
    <div className="flex flex-col h-full">
      <div className="flex justify-between items-center mb-4 border-b pb-2">
        <div>
          <h2 className="text-xl font-bold">{docId}</h2>
          <p className="text-gray-600 text-sm">Version content editor</p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setShowPreview(!showPreview)}
            className="px-3 py-2 text-sm border rounded hover:bg-gray-100 flex items-center gap-1"
          >
            <Eye size={16} /> {showPreview ? "Edit" : "Preview"}
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-4 py-2 text-sm bg-kfl-teal text-white rounded hover:bg-kfl-teal-dark disabled:opacity-50 flex items-center gap-1"
          >
            <Save size={16} /> {saving ? "Saving..." : "Save as Draft"}
          </button>
          <button
            onClick={() => setDocId("")}
            className="px-3 py-2 text-sm border rounded hover:bg-gray-100 flex items-center gap-1"
          >
            <ArrowLeft size={16} /> Back
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-hidden">
        {showPreview ? (
          <div className="h-full overflow-auto p-6 bg-gray-50">
            <pre className="whitespace-pre-wrap font-mono text-sm bg-white p-4 rounded border">{editContent || "No content."}</pre>
          </div>
        ) : (
          <div className="h-full flex">
            <div className="flex-1 h-full border-r p-4">
              <textarea
                className="w-full h-full p-3 font-mono text-sm resize-none focus:outline-none"
                value={editContent}
                onChange={(e) => setEditContent(e.target.value)}
                placeholder="Enter document content (Markdown supported)..."
              />
            </div>
            <div className="w-1/4 h-full overflow-auto p-4 bg-gray-50">
              <h3 className="font-semibold mb-2">Change Summary</h3>
              <textarea
                className="w-full p-2 border rounded resize-none focus:outline-none mb-4"
                value={changeSummary}
                onChange={(e) => setChangeSummary(e.target.value)}
                placeholder="Describe the changes..."
                rows={3}
              />
              <div className="text-xs text-gray-500 space-y-2">
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

export default DocumentEditor;

function DocumentSelector({ setDocId }: { setDocId: (id: string) => void }) {
  const { data: docs = [], isLoading } = useQuery({
    queryKey: ["documents"],
    queryFn: () => api.get("/p0/documents").then((r: any) => r.data),
  });

  if (isLoading) return <div className="p-6">Loading documents...</div>;

  return (
    <div className="bg-white border rounded shadow p-4 mb-6">
      <h2 className="font-semibold mb-3">Select Document to Edit</h2>
      <div className="overflow-x-auto">
        <table className="min-w-full bg-white divide-y">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">ID</th>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Title</th>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Class</th>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">KCAA</th>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Review Due</th>
              <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {docs.map((d: any) => (
              <tr key={d.document_id} className="hover:bg-gray-50 cursor-pointer" onClick={() => setDocId(d.document_id)}>
                <td className="px-4 py-2 text-sm font-mono">{d.document_id}</td>
                <td className="px-4 py-2 text-sm">{d.title}</td>
                <td className="px-4 py-2 text-sm">{d.doc_class}</td>
                <td className="px-4 py-2 text-sm">
                  <span className={`px-2 py-1 rounded text-xs ${
                    d.status === "published" ? "bg-green-100 text-green-800" :
                    d.status === "draft" ? "bg-yellow-100 text-yellow-800" :
                    "bg-gray-100 text-gray-800"
                  }`}>
                    {d.status}
                  </span>
                </td>
                <td className="px-4 py-2 text-sm">{d.kcaa_approval_required ? "Yes" : "No"}</td>
                <td className="px-4 py-2 text-sm">{d.review_due_date || "—"}</td>
                <td className="px-4 py-2 text-right">
                  <button className="text-xs text-kfl-teal hover:underline">Edit</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
