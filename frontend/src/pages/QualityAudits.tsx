import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "../api/client";

export function QualityAudits() {
  const qc = useQueryClient();
  const { data: audits = [], isLoading } = useQuery({
    queryKey: ["quality-audits"],
    queryFn: () => api.get("/p1/quality-audits").then((r: any) => r.data),
  });
  const [showForm, setShowForm] = useState(false);
  const [title, setTitle] = useState("");

  const createMutation = useMutation({
    mutationFn: (data: any) => api.post("/p1/quality-audits", data).then((r: any) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["quality-audits"] });
      setShowForm(false);
      setTitle("");
    },
  });

  return (
    <div className="p-6">
      <div className="flex justify-between items-center mb-4">
        <h1 className="text-2xl font-bold">Quality Audits</h1>
        <button onClick={() => setShowForm(!showForm)} className="bg-kfl-teal text-white px-4 py-2 rounded">
          {showForm ? "Cancel" : "New Audit"}
        </button>
      </div>
      {showForm && (
        <div className="bg-white p-4 rounded shadow mb-4">
          <input className="border p-2 w-full mb-2 rounded" placeholder="Audit title" value={title} onChange={(e) => setTitle(e.target.value)} />
          <button onClick={() => createMutation.mutate({ title, auditor_id: "u-quality" })} className="bg-kfl-teal text-white px-4 py-2 rounded">Create</button>
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
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Findings</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {audits.map((a: any) => (
              <tr key={a.audit_id} className="hover:bg-gray-50">
                <td className="px-4 py-2 text-sm">{a.audit_id}</td>
                <td className="px-4 py-2 text-sm font-medium">{a.title}</td>
                <td className="px-4 py-2 text-sm">{a.audit_type}</td>
                <td className="px-4 py-2 text-sm">{a.status}</td>
                <td className="px-4 py-2 text-sm">{a.findings_count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

export function CorrectiveActions() {
  const { data: cars = [], isLoading } = useQuery({
    queryKey: ["corrective-actions"],
    queryFn: () => api.get("/p1/corrective-actions").then((r: any) => r.data),
  });

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-4">Corrective Action Requests</h1>
      {isLoading ? (
        <p>Loading...</p>
      ) : (
        <table className="min-w-full bg-white border rounded shadow">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">ID</th>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Title</th>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Owner</th>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Due Date</th>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {cars.map((c: any) => (
              <tr key={c.car_id} className="hover:bg-gray-50">
                <td className="px-4 py-2 text-sm">{c.car_id}</td>
                <td className="px-4 py-2 text-sm font-medium">{c.title}</td>
                <td className="px-4 py-2 text-sm">{c.owner_id}</td>
                <td className="px-4 py-2 text-sm">{c.due_date || "—"}</td>
                <td className="px-4 py-2 text-sm">{c.status}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
