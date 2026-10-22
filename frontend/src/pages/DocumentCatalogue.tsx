import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import api from "../api/client";

export function DocumentCatalogue() {
  const { data: docs = [], isLoading } = useQuery({
    queryKey: ["documents"],
    queryFn: () => api.get("/p0/documents").then((r: any) => r.data),
  });

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-4">Document Catalogue</h1>
      {isLoading ? (
        <p>Loading...</p>
      ) : (
        <table className="min-w-full bg-white border rounded shadow">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Title</th>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Class</th>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Classification</th>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">KCAA</th>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Review Due</th>
              <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {docs.map((d: any) => (
              <tr key={d.document_id} className="hover:bg-gray-50">
                <td className="px-4 py-2 text-sm font-medium">{d.title}</td>
                <td className="px-4 py-2 text-sm">{d.doc_class}</td>
                <td className="px-4 py-2 text-sm">{d.status}</td>
                <td className="px-4 py-2 text-sm">{d.classification}</td>
                <td className="px-4 py-2 text-sm">{d.kcaa_approval_required ? "Yes" : "No"}</td>
                <td className="px-4 py-2 text-sm">{d.review_due_date || "—"}</td>
                <td className="px-4 py-2 text-right text-sm">
                  <Link to={`/documents/${d.document_id}/view`} className="text-kfl-teal hover:underline mr-2">
                    View
                  </Link>
                  <Link to={`/documents/${d.document_id}/edit`} className="text-kfl-teal hover:underline">
                    Edit
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
