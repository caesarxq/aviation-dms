import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "../api/client";

export function SecurityManagement() {
  const qc = useQueryClient();
  const { data: incidents = [], isLoading } = useQuery({
    queryKey: ["security-incidents"],
    queryFn: () => api.get("/p1/security-incidents").then((r: any) => r.data),
  });
  const [showForm, setShowForm] = useState(false);
  const [title, setTitle] = useState("");

  const createMutation = useMutation({
    mutationFn: (data: any) => api.post("/p1/security-incidents", data).then((r: any) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["security-incidents"] });
      setShowForm(false);
      setTitle("");
    },
  });

  return (
    <div className="p-6">
      <div className="flex justify-between items-center mb-4">
        <h1 className="text-2xl font-bold">Security Management</h1>
        <button onClick={() => setShowForm(!showForm)} className="bg-kfl-teal text-white px-4 py-2 rounded">
          {showForm ? "Cancel" : "Report Incident"}
        </button>
      </div>
      {showForm && (
        <div className="bg-white p-4 rounded shadow mb-4">
          <input className="border p-2 w-full mb-2 rounded" placeholder="Incident title" value={title} onChange={(e) => setTitle(e.target.value)} />
          <button onClick={() => createMutation.mutate({ title, description: "Security incident", incident_type: "unauthorized_access" })} className="bg-kfl-teal text-white px-4 py-2 rounded">Report</button>
        </div>
      )}
      {isLoading ? (
        <p>Loading...</p>
      ) : (
        <table className="min-w-full bg-white border rounded shadow">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">ID</th>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Title</th>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Type</th>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Severity</th>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {incidents.map((i: any) => (
              <tr key={i.incident_id} className="hover:bg-gray-50">
                <td className="px-4 py-2 text-sm">{i.incident_id}</td>
                <td className="px-4 py-2 text-sm font-medium">{i.title}</td>
                <td className="px-4 py-2 text-sm">{i.incident_type}</td>
                <td className="px-4 py-2 text-sm">{i.severity}</td>
                <td className="px-4 py-2 text-sm">{i.status}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
