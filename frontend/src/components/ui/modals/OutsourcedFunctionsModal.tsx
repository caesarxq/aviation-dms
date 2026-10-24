import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "../../../api/client";
import { Modal } from "../Modal";
import { useToast } from "../Toast";

export function OutsourcedFunctionsModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const qc = useQueryClient();
  const { toast } = useToast();
  const [provider, setProvider] = useState("");
  const [scope, setScope] = useState("");
  const [error, setError] = useState("");

  const { data: items = [] } = useQuery({
    queryKey: ["outsourced-functions-modal"],
    queryFn: () => api.get("/p1/outsourced-functions").then((r: any) => r.data),
  });

  const createMutation = useMutation({
    mutationFn: (data: any) => api.post("/p1/outsourced-functions", data).then((r: any) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["outsourced-functions-modal"] });
      setProvider("");
      setScope("");
      setError("");
      toast({ title: "Outsourced function added", type: "success" });
    },
    onError: () => setError("Failed to add outsourced function."),
  });

  return (
    <Modal open={open} onClose={onClose} title="Outsourced Functions" className="max-w-2xl">
      {error && (
        <div className="mb-3 p-3 rounded bg-rose-50/60 border border-rose-200 text-rose-800 text-sm">{error}</div>
      )}
      <div className="flex justify-between items-center mb-3">
        <h3 className="font-medium text-white">Outsourced Service Providers</h3>
        <button onClick={() => onClose()} className="text-xs text-white/70 hover:text-white underline">
          Close
        </button>
      </div>

      <div className="grid grid-cols-2 gap-3 mb-4">
        <div>
          <label className="block text-xs font-medium text-white/70 mb-1">Provider Name</label>
          <input id="provider_name_46" name="provider_name"
            className="w-full border border-white/20 rounded p-2 text-sm bg-white/10 text-white focus:border-kfl-blue focus:outline-none"
            placeholder="Provider name"
            value={provider}
            onChange={(e) => setProvider(e.target.value)}
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-white/70 mb-1">Scope</label>
          <input id="scope_of_work_55" name="scope_of_work"
            className="w-full border border-white/20 rounded p-2 text-sm bg-white/10 text-white focus:border-kfl-blue focus:outline-none"
            placeholder="Scope of work"
            value={scope}
            onChange={(e) => setScope(e.target.value)}
          />
        </div>
      </div>
      <button
        disabled={!provider.trim() || createMutation.isPending}
        onClick={() => {
          setError("");
          if (!provider.trim()) {
            setError("Provider name is required.");
            return;
          }
          createMutation.mutate({ provider_name: provider, scope });
        }}
        className="w-full bg-kfl-blue hover:bg-kfl-blue/90 text-white px-4 py-2 rounded disabled:opacity-50 transition"
      >
        {createMutation.isPending ? "Creating…" : "Create Provider"}
      </button>

      {items.length > 0 && (
        <div className="mt-4 overflow-auto max-h-48">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="border-b border-white/10 text-white/60 text-[10px] uppercase">
                <th className="text-left px-2 py-1">Provider</th>
                <th className="text-left px-2 py-1">Scope</th>
                <th className="text-left px-2 py-1">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/10">
              {items.map((i: any) => (
                <tr key={i.function_id}>
                  <td className="px-2 py-1 text-xs text-white">{i.provider_name}</td>
                  <td className="px-2 py-1 text-xs text-white/70">{i.scope}</td>
                  <td className="px-2 py-1 text-xs text-white">{i.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Modal>
  );
}
