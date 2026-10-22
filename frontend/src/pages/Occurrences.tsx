import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { safetyApi } from "../api/safety";

export function Occurrences() {
  const qc = useQueryClient();
  const { data: occurrences = [], isLoading } = useQuery({
    queryKey: ["occurrences"],
    queryFn: () => safetyApi.listOccurrences(),
  });
  const [showForm, setShowForm] = useState(false);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [severity, setSeverity] = useState("minor");

  const createMutation = useMutation({
    mutationFn: (data: any) => safetyApi.createOccurrence(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["occurrences"] });
      setShowForm(false);
      setTitle("");
      setDescription("");
    },
  });

  return (
    <div className="p-6">
      <div className="flex justify-between items-center mb-4">
        <h1 className="text-2xl font-bold">Safety Occurrences</h1>
        <button onClick={() => setShowForm(!showForm)} className="bg-kfl-teal text-white px-4 py-2 rounded">
          {showForm ? "Cancel" : "Report Occurrence"}
        </button>
      </div>
      {showForm && (
        <div className="bg-white p-4 rounded shadow mb-4">
          <input className="border p-2 w-full mb-2 rounded" placeholder="Title" value={title} onChange={(e) => setTitle(e.target.value)} />
          <textarea className="border p-2 w-full mb-2 rounded" placeholder="Description" value={description} onChange={(e) => setDescription(e.target.value)} />
          <select className="border p-2 mb-2 rounded" value={severity} onChange={(e) => setSeverity(e.target.value)}>
            <option value="negligible">Negligible</option>
            <option value="minor">Minor</option>
            <option value="major">Major</option>
            <option value="hazardous">Hazardous</option>
            <option value="catastrophic">Catastrophic</option>
          </select>
          <button onClick={() => createMutation.mutate({ title, description, severity })} className="bg-kfl-teal text-white px-4 py-2 rounded">
            Submit
          </button>
        </div>
      )}
      {isLoading ? (
        <p>Loading...</p>
      ) : (
        <table className="min-w-full bg-white border rounded shadow">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Serial</th>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Title</th>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Type</th>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Severity</th>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {occurrences.map((o: any) => (
              <tr key={o.occurrence_id} className="hover:bg-gray-50">
                <td className="px-4 py-2 text-sm">{o.serial_number}</td>
                <td className="px-4 py-2 text-sm font-medium">{o.title}</td>
                <td className="px-4 py-2 text-sm">{o.occurrence_type}</td>
                <td className="px-4 py-2 text-sm">{o.severity}</td>
                <td className="px-4 py-2 text-sm">{o.status}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
