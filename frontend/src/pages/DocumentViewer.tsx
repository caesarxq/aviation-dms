import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import api from "../api/client";
import { ArrowLeft, Copy } from "lucide-react";

export function DocumentViewer() {
  const { docId } = useParams();
  const { data: content, isLoading } = useQuery({
    queryKey: ["doc-content", docId],
    queryFn: () => api.get(`/p0/documents/${docId}/content`).then((r: any) => r.data),
    enabled: !!docId,
  });

  if (isLoading) return <div className="p-6">Loading document...</div>;
  if (!content) return <div className="p-6">Document not found</div>;

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <div className="flex justify-between items-center mb-6 border-b pb-2">
        <div>
          <h1 className="text-2xl font-bold">{docId}</h1>
          <p className="text-gray-600 text-sm">
            Version {content.version_number} • State: {content.state}
            {content.kcaa_approved ? " • KCAA Approved" : ""}
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => navigator.clipboard.writeText(content.content || "")}
            className="px-3 py-2 text-sm border rounded hover:bg-gray-100 flex items-center gap-1"
          >
            <Copy size={16} /> Copy Content
          </button>
          <button
            onClick={() => window.history.back()}
            className="px-3 py-2 text-sm border rounded hover:bg-gray-100 flex items-center gap-1"
          >
            <ArrowLeft size={16} /> Back
          </button>
        </div>
      </div>

      <div className="bg-white border rounded shadow p-6">
        <div className="prose prose-lg max-w-none">
          {content.content ? (
            <pre className="whitespace-pre-wrap font-sans text-sm">{content.content}</pre>
          ) : (
            <p className="text-gray-500 italic">No content available for this document.</p>
          )}
        </div>
      </div>

      <div className="mt-6 p-4 bg-gray-50 rounded border">
        <h3 className="font-semibold mb-2">Version Details</h3>
        <dl className="grid grid-cols-2 gap-4 text-sm">
          <dt className="font-medium text-gray-500">Document ID</dt>
          <dd className="font-mono">{content.document_id}</dd>
          <dt className="font-medium text-gray-500">Version ID</dt>
          <dd className="font-mono">{content.version_id}</dd>
          <dt className="font-medium text-gray-500">Version Number</dt>
          <dd>{content.version_number}</dd>
          <dt className="font-medium text-gray-500">State</dt>
          <dd>
            <span className={`px-2 py-1 rounded text-xs ${
              content.state === "published" ? "bg-green-100 text-green-800" :
              content.state === "draft" ? "bg-yellow-100 text-yellow-800" :
              content.state === "approved" ? "bg-blue-100 text-blue-800" :
              "bg-gray-100 text-gray-800"
            }`}>
              {content.state}
            </span>
          </dd>
          <dt className="font-medium text-gray-500">KCAA Approved</dt>
          <dd>
            <span className={`px-2 py-1 rounded text-xs ${
              content.kcaa_approved === 1 ? "bg-green-100 text-green-800" :
              "bg-gray-100 text-gray-800"
            }`}>
              {content.kcaa_approved === 1 ? "Yes" : "No"}
            </span>
          </dd>
          <dt className="font-medium text-gray-500">Created</dt>
          <dd>{content.created_at}</dd>
          <dt className="font-medium text-gray-500">Updated</dt>
          <dd>{content.updated_at}</dd>
        </dl>
      </div>
    </div>
  );
}

export default DocumentViewer;
