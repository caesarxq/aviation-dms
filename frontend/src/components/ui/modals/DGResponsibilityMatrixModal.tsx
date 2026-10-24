import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "../../../api/client";
import { Modal } from "../Modal";
import { useToast } from "../Toast";

export function DGResponsibilityMatrixModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const qc = useQueryClient();
  const { toast } = useToast();
  const [project, setProject] = useState("");
  const [stage, setStage] = useState("");
  const [role, setRole] = useState("");
  const [error, setError] = useState("");

  const { data: items = [] } = useQuery({
    queryKey: ["dg-matrix-modal"],
    queryFn: () => api.get("/p1/dg-responsibility-matrix").then((r: any) => r.data),
  });

  const createMutation = useMutation({
    mutationFn: (data: any) => api.post("/p1/dg-responsibility-matrix", data).then((r: any) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["dg-matrix-modal"] });
      setProject("");
      setStage("");
      setRole("");
      setError("");
      toast({ title: "DG Responsibility entry added", type: "success" });
    },
    onError: () => setError("Failed to add DG responsibility entry."),
  });

  return (
    <Modal open={open} onClose={onClose} title="DG Responsibility Matrix" className="max-w-2xl">
      {error && (
        <div className="mb-3 p-3 rounded bg-rose-50/60 border border-rose-200 text-rose-800 text-sm">{error}</div>
      )}
      <div className="flex justify-between items-center mb-3">
        <h3 className="font-medium text-white">DG Responsibility Matrix</h3>
        <button onClick={() => onClose()} className="text-xs text-white/70 hover:text-white underline">
          Close
        </button>
      </div>

      <div className="grid grid-cols-3 gap-3 mb-4">
        <div>
          <label className="block text-xs font-medium text-white/70 mb-1">Project / Route</label>
          <input id="project_or_route_48" name="project_or_route"
            className="w-full border border-white/20 rounded p-2 text-sm bg-white/10 text-white focus:border-kfl-blue focus:outline-none"
            placeholder="Project or route"
            value={project}
            onChange={(e) => setProject(e.target.value)}
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-white/70 mb-1">Process Stage</label>
          <input id="process_stage_57" name="process_stage"
            className="w-full border border-white/20 rounded p-2 text-sm bg-white/10 text-white focus:border-kfl-blue focus:outline-none"
            placeholder="Process stage"
            value={stage}
            onChange={(e) => setStage(e.target.value)}
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-white/70 mb-1">Responsible Role</label>
          <input id="responsible_role_66" name="responsible_role"
            className="w-full border border-white/20 rounded p-2 text-sm bg-white/10 text-white focus:border-kfl-blue focus:outline-none"
            placeholder="Responsible role"
            value={role}
            onChange={(e) => setRole(e.target.value)}
          />
        </div>
      </div>
      <button
        disabled={!project.trim() || createMutation.isPending}
        onClick={() => {
          setError("");
          if (!project.trim()) {
            setError("Project / Route is required.");
            return;
          }
          createMutation.mutate({ project_or_route: project, process_stage: stage, responsible_role: role });
        }}
        className="w-full bg-kfl-blue hover:bg-kfl-blue/90 text-white px-4 py-2 rounded disabled:opacity-50 transition"
      >
        {createMutation.isPending ? "Creating…" : "Create Entry"}
      </button>

      {items.length > 0 && (
        <div className="mt-4 overflow-auto max-h-48">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="border-b border-white/10 text-white/60 text-[10px] uppercase">
                <th className="text-left px-2 py-1">Project / Route</th>
                <th className="text-left px-2 py-1">Process Stage</th>
                <th className="text-left px-2 py-1">Responsible Role</th>
                <th className="text-left px-2 py-1">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/10">
              {items.map((i: any) => (
                <tr key={i.matrix_id}>
                  <td className="px-2 py-1 text-xs text-white">{i.project_or_route}</td>
                  <td className="px-2 py-1 text-xs text-white/70">{i.process_stage}</td>
                  <td className="px-2 py-1 text-xs text-white">{i.responsible_role}</td>
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
