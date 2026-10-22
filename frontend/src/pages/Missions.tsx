import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "../api/client";

export function Missions() {
  const qc = useQueryClient();
  const { data: missions = [], isLoading } = useQuery({
    queryKey: ["missions"],
    queryFn: () => api.get("/p1/missions").then((r: any) => r.data),
  });
  const [showForm, setShowForm] = useState(false);
  const [title, setTitle] = useState("");

  const createMutation = useMutation({
    mutationFn: (data: any) => api.post("/p1/missions", data).then((r: any) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["missions"] });
      setShowForm(false);
      setTitle("");
    },
  });

  return (
    <div className="p-6">
      <div className="flex justify-between items-center mb-4">
        <h1 className="text-2xl font-bold">Missions</h1>
        <button onClick={() => setShowForm(!showForm)} className="bg-kfl-teal text-white px-4 py-2 rounded">
          {showForm ? "Cancel" : "New Mission"}
        </button>
      </div>
      {showForm && (
        <div className="bg-white p-4 rounded shadow mb-4">
          <input className="border p-2 w-full mb-2 rounded" placeholder="Mission title" value={title} onChange={(e) => setTitle(e.target.value)} />
          <button onClick={() => createMutation.mutate({ title })} className="bg-kfl-teal text-white px-4 py-2 rounded">Create</button>
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
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Priority</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {missions.map((m: any) => (
              <tr key={m.mission_id} className="hover:bg-gray-50">
                <td className="px-4 py-2 text-sm">{m.mission_id}</td>
                <td className="px-4 py-2 text-sm font-medium">{m.title}</td>
                <td className="px-4 py-2 text-sm">{m.mission_type}</td>
                <td className="px-4 py-2 text-sm">{m.status}</td>
                <td className="px-4 py-2 text-sm">{m.priority}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
