import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "../../../api/client";
import { Modal } from "../Modal";
import { useToast } from "../Toast";

export function SafetyKPIsModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const qc = useQueryClient();
  const { toast } = useToast();
  const [name, setName] = useState("");
  const [target, setTarget] = useState("");
  const [error, setError] = useState("");

  const { data: items = [] } = useQuery({
    queryKey: ["safety-kpis-modal"],
    queryFn: () => api.get("/p1/safety-kpis").then((r: any) => r.data),
  });

  const createMutation = useMutation({
    mutationFn: (data: any) => api.post("/p1/safety-kpis", data).then((r: any) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["safety-kpis-modal"] });
      setName("");
      setTarget("");
      setError("");
      toast({ title: "Safety KPI created", type: "success" });
    },
    onError: () => setError("Failed to create safety KPI."),
  });

  return (
    <Modal open={open} onClose={onClose} title="Safety KPIs" className="max-w-2xl">
      {error && (
        <div className="mb-3 p-3 rounded bg-rose-50/60 border border-rose-200 text-rose-800 text-sm">{error}</div>
      )}
      <div className="flex justify-between items-center mb-3">
        <h3 className="font-medium text-white">Safety Performance Indicators</h3>
        <button
          onClick={() => onClose()}
          className="text-xs text-white/70 hover:text-white underline"
        >
          Close
        </button>
      </div>

      <div className="grid grid-cols-2 gap-3 mb-4">
        <div>
          <label className="block text-xs font-medium text-white/70 mb-1">KPI Name</label>
          <input id="kpi_name_49" name="kpi_name"
            className="w-full border border-white/20 rounded p-2 text-sm bg-white/10 text-white focus:border-kfl-blue focus:outline-none"
            placeholder="KPI name"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-white/70 mb-1">Target</label>
          <input id="target_value_58" name="target_value"
            className="w-full border border-white/20 rounded p-2 text-sm bg-white/10 text-white focus:border-kfl-blue focus:outline-none"
            placeholder="Target value"
            value={target}
            onChange={(e) => setTarget(e.target.value)}
          />
        </div>
      </div>
      <button
        disabled={!name.trim() || createMutation.isPending}
        onClick={() => {
          setError("");
          if (!name.trim()) {
            setError("KPI name is required.");
            return;
          }
          createMutation.mutate({ kpi_name: name, target });
        }}
        className="w-full bg-kfl-blue hover:bg-kfl-blue/90 text-white px-4 py-2 rounded disabled:opacity-50 transition"
      >
        {createMutation.isPending ? "Creating…" : "Create KPI"}
      </button>

      {items.length > 0 && (
        <div className="mt-4 overflow-auto max-h-48">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="border-b border-white/10 text-white/60 text-[10px] uppercase">
                <th className="text-left px-2 py-1">KPI</th>
                <th className="text-left px-2 py-1">Target</th>
                <th className="text-left px-2 py-1">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/10">
              {items.map((i: any) => (
                <tr key={i.kpi_id}>
                  <td className="px-2 py-1 text-xs text-white">{i.kpi_name}</td>
                  <td className="px-2 py-1 text-xs text-white/70">{i.target}</td>
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
