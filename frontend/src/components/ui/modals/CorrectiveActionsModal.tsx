import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "../../../api/client";
import { Modal } from "../Modal";
import { useToast } from "../Toast";

export function CorrectiveActionsModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const qc = useQueryClient();
  const { toast } = useToast();
  const [title, setTitle] = useState("");
  const [error, setError] = useState("");

  const { data: cars = [] } = useQuery({
    queryKey: ["corrective-actions-modal"],
    queryFn: () => api.get("/p1/corrective-actions").then((r: any) => r.data),
  });

  const createMutation = useMutation({
    mutationFn: (data: any) => api.post("/p1/corrective-actions", data).then((r: any) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["corrective-actions-modal"] });
      setTitle("");
      setError("");
      toast({ title: "Corrective Action created", type: "success" });
    },
    onError: () => setError("Failed to create corrective action."),
  });

  return (
    <Modal open={open} onClose={onClose} title="Corrective Actions" className="max-w-2xl">
      {error && (
        <div className="mb-3 p-3 rounded bg-rose-50/60 border border-rose-200 text-rose-800 text-sm">{error}</div>
      )}
      <div className="flex justify-between items-center mb-3">
        <h3 className="font-medium text-white">Corrective Action Requests</h3>
        <button
          onClick={() => {
            setError("");
            setTitle("");
          }}
          className="text-xs text-white/70 hover:text-white underline"
        >
          Close
        </button>
      </div>

      <div className="mb-4">
        <label className="block text-xs font-medium text-white/70 mb-1">CAR Title</label>
        <input
          className="w-full border border-white/20 rounded p-2 text-sm bg-white/10 text-white focus:border-kfl-blue focus:outline-none"
          placeholder="Enter corrective action title"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
        />
      </div>
      <button
        disabled={!title.trim() || createMutation.isPending}
        onClick={() => {
          setError("");
          if (!title.trim()) {
            setError("Corrective action title is required.");
            return;
          }
          createMutation.mutate({ title });
        }}
        className="w-full bg-kfl-blue hover:bg-kfl-blue/90 text-white px-4 py-2 rounded disabled:opacity-50 transition"
      >
        {createMutation.isPending ? "Creating…" : "Create CAR"}
      </button>

      {cars.length > 0 && (
        <div className="mt-4 overflow-auto max-h-48">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="border-b border-white/10 text-white/60 text-[10px] uppercase">
                <th className="text-left px-2 py-1">ID</th>
                <th className="text-left px-2 py-1">Title</th>
                <th className="text-left px-2 py-1">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/10">
              {cars.map((c: any) => (
                <tr key={c.car_id}>
                  <td className="px-2 py-1 font-mono text-xs text-white/70">{c.car_id}</td>
                  <td className="px-2 py-1 text-xs text-white">{c.title}</td>
                  <td className="px-2 py-1 text-xs text-white">{c.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Modal>
  );
}
