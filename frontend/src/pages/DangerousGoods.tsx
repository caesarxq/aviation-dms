import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "../api/client";

export function DangerousGoods() {
  const qc = useQueryClient();
  const { data: shipments = [], isLoading } = useQuery({
    queryKey: ["dg-shipments"],
    queryFn: () => api.get("/p1/dg-shipments").then((r: any) => r.data),
  });
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [dgClass, setDgClass] = useState("3");

  const createMutation = useMutation({
    mutationFn: (data: any) => api.post("/p1/dg-shipments", data).then((r: any) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["dg-shipments"] });
      setShowForm(false);
      setName("");
    },
  });

  return (
    <div className="p-6">
      <div className="flex justify-between items-center mb-4">
        <h1 className="text-2xl font-bold">Dangerous Goods</h1>
        <button onClick={() => setShowForm(!showForm)} className="bg-kfl-teal text-white px-4 py-2 rounded">
          {showForm ? "Cancel" : "New Shipment"}
        </button>
      </div>
      {showForm && (
        <div className="bg-white p-4 rounded shadow mb-4">
          <input className="border p-2 w-full mb-2 rounded" placeholder="Proper shipping name" value={name} onChange={(e) => setName(e.target.value)} />
          <input className="border p-2 w-full mb-2 rounded" placeholder="DG Class" value={dgClass} onChange={(e) => setDgClass(e.target.value)} />
          <button onClick={() => createMutation.mutate({ proper_shipping_name: name, dg_class: dgClass })} className="bg-kfl-teal text-white px-4 py-2 rounded">Create</button>
        </div>
      )}
      {isLoading ? (
        <p>Loading...</p>
      ) : (
        <table className="min-w-full bg-white border rounded shadow">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">ID</th>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Shipping Name</th>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">DG Class</th>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">UN Number</th>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {shipments.map((s: any) => (
              <tr key={s.shipment_id} className="hover:bg-gray-50">
                <td className="px-4 py-2 text-sm">{s.shipment_id}</td>
                <td className="px-4 py-2 text-sm font-medium">{s.proper_shipping_name}</td>
                <td className="px-4 py-2 text-sm">{s.dg_class}</td>
                <td className="px-4 py-2 text-sm">{s.un_number || "—"}</td>
                <td className="px-4 py-2 text-sm">{s.status}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
