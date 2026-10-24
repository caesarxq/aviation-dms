import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "../api/client";
import { Plus } from "lucide-react";
import { useToast } from "../components/ui/Toast";
import FormField from "../components/ui/FormField";
import { useValidation } from "../utils/validation";

function missionStatusClass(status: string) {
  switch (status) {
    case "completed": return "app-status app-status-healthy";
    case "in_progress": return "app-status app-status-info";
    case "planned": return "app-status app-status-info";
    case "cancelled": return "app-status app-status-critical";
    case "aborted": return "app-status app-status-critical";
    default: return "app-status app-status-info";
  }
}

const STATUS_ACTIONS: Record<string, { label: string; state: string; tone: "blue" | "green" | "red" }[]> = {
  planned: [
    { label: "Start", state: "in_progress", tone: "green" },
    { label: "Cancel", state: "cancelled", tone: "red" },
  ],
  in_progress: [
    { label: "Complete", state: "completed", tone: "blue" },
    { label: "Abort", state: "aborted", tone: "red" },
  ],
};

function availableActions(status: string) {
  return STATUS_ACTIONS[status] || [];
}

function toneColor(tone: string) {
  switch (tone) {
    case "green": return "#0f6b4c";
    case "red": return "#c53030";
    default: return "#1b7abf";
  }
}

export function Missions() {
  const qc = useQueryClient();
  const { toast } = useToast();
  const { data: missions = [], isLoading } = useQuery({
    queryKey: ["missions"],
    queryFn: () => api.get("/p1/missions").then((r: any) => r.data),
  });
  const [showForm, setShowForm] = useState(false);
  const [title, setTitle] = useState("");
  const [missionError, setMissionError] = useState("");

  const { errors: missionFieldErrors, isValid: missionIsValid } = useValidation(
    { title },
    {
      title: { required: true, minLength: 2 },
    }
  );

  const createMutation = useMutation({
    mutationFn: (data: any) => api.post("/p1/missions", data).then((r: any) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["missions"] });
      setShowForm(false);
      setTitle("");
      setMissionError("");
      toast({ title: "Mission created", message: "The new mission has been added to the register.", type: "success" });
    },
    onError: () => {
      setMissionError("Failed to create mission. Please try again.");
    },
  });

  const transitionMutation = useMutation({
    mutationFn: ({ id, state }: { id: string; state: string }) =>
      api.patch(`/p1/missions/${id}/state?state=${state}`).then((r: any) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["missions"] });
    },
  });

  return (
    <div className="app-page">
      <header className="app-page-header">
        <div>
          <div className="app-eyebrow">Flight Operations</div>
          <h1 className="app-title">Missions</h1>
          <p className="app-subtitle">Plan, track, and transition flight missions through their operational lifecycle.</p>
        </div>
        <button
          onClick={() => setShowForm(!showForm)}
          className="app-btn-primary"
        >
          <Plus size={16} /> {showForm ? "Cancel" : "New Mission"}
        </button>
      </header>

      <section className="mb-5 grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="app-surface p-4">
          <div className="app-label">Total Missions</div>
          <div className="mt-2 text-2xl font-bold text-kfl-text">{missions.length}</div>
        </div>
        <div className="app-surface p-4">
          <div className="app-label">Planned</div>
          <div className="mt-2 text-2xl font-bold text-kfl-blue">{missions.filter((m: any) => m.status === "planned").length}</div>
        </div>
        <div className="app-surface p-4">
          <div className="app-label">In Progress</div>
          <div className="mt-2 text-2xl font-bold text-kfl-blue">{missions.filter((m: any) => m.status === "in_progress").length}</div>
        </div>
        <div className="app-surface p-4">
          <div className="app-label">Completed</div>
          <div className="mt-2 text-2xl font-bold text-emerald-700">{missions.filter((m: any) => m.status === "completed").length}</div>
        </div>
      </section>

      <section className="app-surface overflow-hidden">
        <div className="flex flex-col gap-3 border-b border-kfl-border p-4 md:flex-row md:items-center md:justify-between">
          <div className="relative min-w-0 flex-1 md:max-w-md">
            <input id="search_missions_112" name="search_missions" value={showForm ? title : ""} onChange={(e) => setTitle(e.target.value)} placeholder="Search missions…" className="app-input pl-9 relative z-10" />
          </div>
          <select id="select_field_114" name="select_field" className="app-input w-full md:w-auto">
            <option value="">All statuses</option>
            <option value="planned">Planned</option>
            <option value="in_progress">In Progress</option>
            <option value="completed">Completed</option>
            <option value="cancelled">Cancelled</option>
          </select>
        </div>

        {showForm && (
          <div className="app-surface p-5 mb-5">
            <div className="mb-4 flex items-start justify-between gap-4">
              <div>
                <div className="app-label mb-1">New Mission</div>
                <p className="text-xs text-kfl-muted">Create a new mission plan.</p>
              </div>
              <button onClick={() => setShowForm(false)} className="app-btn-secondary px-3 py-2">Cancel</button>
            </div>
            {missionError && (
              <div className="mb-3 p-3 rounded bg-rose-50/60 border border-rose-200 text-rose-800 text-sm">
                {missionError}
              </div>
            )}
            <FormField htmlFor="mission_title_137" label="Mission title" hint="Use the operational mission name or reference." required>
              <input id="mission_title_137" name="mission_title" aria-describedby="mission_title_137-error" aria-invalid={!!missionFieldErrors.title} className={`app-input ${missionFieldErrors.title ? "border-rose-400" : ""}`} placeholder="Mission title" value={title} onChange={(e) => setTitle(e.target.value)} />
              {missionFieldErrors.title && <p id="mission_title_137-error" className="text-[11px] text-rose-700 mt-1">{missionFieldErrors.title}</p>}
            </FormField>
            <button
              disabled={!missionIsValid || createMutation.isPending}
              onClick={() => {
                setMissionError("");
                createMutation.mutate({ title });
              }}
              className="app-btn-primary w-full"
            >
              {createMutation.isPending ? "Creating…" : "Create Mission"}
            </button>
          </div>
        )}

        {isLoading ? (
          <div className="p-10 text-center text-sm text-kfl-muted">Loading missions…</div>
        ) : missions.length === 0 ? (
          <div className="app-surface border-dashed p-10 text-center">
            <Plus size={26} className="mx-auto mb-2 text-kfl-muted" />
            <p className="text-sm font-bold text-kfl-text">No missions found.</p>
            <p className="mt-1 text-xs text-kfl-muted">Create your first mission to begin tracking flight operations.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full">
              <thead className="border-b border-kfl-border bg-kfl-surface-subtle">
                <tr>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">ID</th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Title</th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Type</th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Status</th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Priority</th>
                  <th className="px-4 py-3 text-right text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-kfl-border">
                {missions.map((m: any) => (
                  <tr key={m.mission_id} className="transition hover:bg-kfl-surface-subtle group">
                    <td className="px-4 py-4 font-mono text-[12px] text-kfl-text">{m.mission_id}</td>
                    <td className="px-4 py-4">
                      <div className="font-semibold text-kfl-text">{m.title}</div>
                      <div className="mt-1 text-xs text-kfl-muted">{m.planned_date}</div>
                    </td>
                    <td className="px-4 py-4 text-sm text-kfl-secondary">{m.mission_type}</td>
                    <td className="px-4 py-4">
                      <span className={missionStatusClass(m.status)}>{m.status}</span>
                    </td>
                    <td className="px-4 py-4 text-sm text-kfl-secondary">{m.priority}</td>
                    <td className="px-4 py-4 text-right text-sm">
                      {availableActions(m.status).map((a) => (
                        <button
                          key={a.state}
                          onClick={() => transitionMutation.mutate({ id: m.mission_id, state: a.state })}
                          className="text-xs font-medium px-2 py-1.5 rounded border transition hover:bg-kfl-surface-subtle"
                          style={{ borderColor: toneColor(a.tone), color: toneColor(a.tone) }}
                        >
                          {a.label}
                        </button>
                      ))}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}