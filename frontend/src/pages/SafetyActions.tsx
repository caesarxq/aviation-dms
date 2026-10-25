import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { safetyApi } from "../api/safety";
import { CheckCircle, Plus } from "lucide-react";
import FormField from "../components/ui/FormField";
import { useValidation } from "../utils/validation";
import { useUnsavedChanges } from "../hooks/useUnsavedChanges";

function statusClass(status: string) {
  switch (status) {
    case "open": return "app-status app-status-info";
    case "in_progress": return "app-status app-status-warning";
    case "completed": return "app-status app-status-healthy";
    case "verified": return "app-status app-status-healthy";
    case "closed": return "app-status app-status-info";
    default: return "app-status app-status-info";
  }
}

function actionTypeClass(type: string) {
  switch (type) {
    case "corrective": return "app-status app-status-warning";
    case "preventive": return "app-status app-status-info";
    case "improvement": return "app-status app-status-healthy";
    default: return "app-status app-status-info";
  }
}

export function SafetyActions() {
  const qc = useQueryClient();
  const { data: actions = [], isLoading } = useQuery({
    queryKey: ["safety-actions"],
    queryFn: () => safetyApi.listSafetyActions(),
  });
  const [showForm, setShowForm] = useState(false);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [actionType, setActionType] = useState("corrective");
  const [ownerId, setOwnerId] = useState("");
  const [dueDate, setDueDate] = useState("");
  const [occurrenceId, setOccurrenceId] = useState("");
  const [hazardId, setHazardId] = useState("");
  const [investigationId, setInvestigationId] = useState("");
  const [dirty, setDirty] = useState(false);

  const { errors: saErrors, isValid: saIsValid } = useValidation(
    { title, description, owner_id: ownerId },
    {
      title: { required: true, minLength: 2 },
      description: { required: true, minLength: 5 },
      owner_id: { required: true, minLength: 2 },
    }
  );

  useUnsavedChanges(showForm && dirty);

  const createMutation = useMutation({
    mutationFn: (data: any) => safetyApi.createSafetyAction(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["safety-actions"] });
      setShowForm(false);
      setDirty(false);
      setTitle("");
      setDescription("");
      setActionType("corrective");
      setOwnerId("");
      setDueDate("");
      setOccurrenceId("");
      setHazardId("");
      setInvestigationId("");
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: any }) => safetyApi.updateSafetyAction(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["safety-actions"] });
    },
  });

  return (
    <div className="app-page">
      <header className="app-page-header">
        <div>
          <div className="app-eyebrow">Safety Management</div>
          <h1 className="app-title">Safety Actions</h1>
          <p className="app-subtitle">Track corrective, preventive, and improvement actions from occurrences, hazards, and investigations.</p>
        </div>
        <button
          onClick={() => setShowForm(!showForm)}
          className="app-btn-primary"
        >
          <Plus size={16} /> {showForm ? "Cancel" : "New Action"}
        </button>
      </header>

      <section className="mb-5 grid grid-cols-1 gap-4 sm:grid-cols-4">
        <div className="app-surface p-4">
          <div className="app-label">Total Actions</div>
          <div className="mt-2 text-2xl font-bold text-kfl-text">{actions.length}</div>
        </div>
        <div className="app-surface p-4">
          <div className="app-label">Open</div>
          <div className="mt-2 text-2xl font-bold text-amber-700">{actions.filter((a: any) => a.status === "open").length}</div>
        </div>
        <div className="app-surface p-4">
          <div className="app-label">In Progress</div>
          <div className="mt-2 text-2xl font-bold text-blue-700">{actions.filter((a: any) => a.status === "in_progress").length}</div>
        </div>
        <div className="app-surface p-4">
          <div className="app-label">Completed / Verified</div>
          <div className="mt-2 text-2xl font-bold text-emerald-700">{actions.filter((a: any) => a.status === "completed" || a.status === "verified").length}</div>
        </div>
      </section>

      {showForm && (
        <div className="app-surface p-5 mb-5">
          <div className="mb-4 flex items-start justify-between gap-4">
            <div>
              <div className="app-label mb-1">New Safety Action</div>
              <p className="text-xs text-kfl-muted">Create a corrective or preventive action linked to an occurrence, hazard, or investigation.</p>
            </div>
            <button onClick={() => { setShowForm(false); setDirty(false); }} className="app-btn-secondary px-4 py-2 text-sm">Cancel</button>
          </div>
          <div className="space-y-3 mb-4">
            <FormField htmlFor="sa_title" label="Action title" hint="Brief title for the safety action." required>
              <input id="sa_title" name="title" aria-describedby="sa_title-error" aria-invalid={!!saErrors.title} className={`app-input ${saErrors.title ? "border-rose-400" : ""}`} placeholder="Action title" value={title} onChange={(e) => { setTitle(e.target.value); setDirty(true); }} />
              {saErrors.title && <p id="sa_title-error" className="text-[11px] text-rose-700 mt-1">{saErrors.title}</p>}
            </FormField>
            <FormField htmlFor="sa_description" label="Description" hint="Describe the action and its purpose." required>
              <textarea id="sa_description" name="description" aria-describedby="sa_description-error" aria-invalid={!!saErrors.description} className={`app-input ${saErrors.description ? "border-rose-400" : ""}`} placeholder="Describe the action" value={description} onChange={(e) => { setDescription(e.target.value); setDirty(true); }} rows={3} />
              {saErrors.description && <p id="sa_description-error" className="text-[11px] text-rose-700 mt-1">{saErrors.description}</p>}
            </FormField>
          </div>
          <div className="grid grid-cols-2 gap-4 mb-4">
            <div>
              <label className="app-label">Action Type</label>
              <select id="sa_type" name="action_type" value={actionType} onChange={(e) => { setActionType(e.target.value); setDirty(true); }} className="app-input">
                <option value="corrective">Corrective</option>
                <option value="preventive">Preventive</option>
                <option value="improvement">Improvement</option>
              </select>
            </div>
            <FormField htmlFor="sa_owner" label="Owner ID" hint="Person responsible for completing this action." required>
              <input id="sa_owner" name="owner_id" aria-describedby="sa_owner-error" aria-invalid={!!saErrors.owner_id} className={`app-input ${saErrors.owner_id ? "border-rose-400" : ""}`} placeholder="e.g. u-safety" value={ownerId} onChange={(e) => { setOwnerId(e.target.value); setDirty(true); }} />
              {saErrors.owner_id && <p id="sa_owner-error" className="text-[11px] text-rose-700 mt-1">{saErrors.owner_id}</p>}
            </FormField>
          </div>
          <div className="grid grid-cols-2 gap-4 mb-4">
            <FormField htmlFor="sa_due" label="Due date" hint="Target completion date.">
              <input id="sa_due" name="due_date" type="date" className="app-input" value={dueDate} onChange={(e) => { setDueDate(e.target.value); setDirty(true); }} />
            </FormField>
            <FormField htmlFor="sa_occurrence" label="Occurrence ID" hint="Optional occurrence link.">
              <input id="sa_occurrence" name="occurrence_id" className="app-input" placeholder="e.g. OCC-..." value={occurrenceId} onChange={(e) => { setOccurrenceId(e.target.value); setDirty(true); }} />
            </FormField>
          </div>
          <div className="grid grid-cols-2 gap-4 mb-4">
            <FormField htmlFor="sa_hazard" label="Hazard ID" hint="Optional hazard link.">
              <input id="sa_hazard" name="hazard_id" className="app-input" placeholder="e.g. HAZ-..." value={hazardId} onChange={(e) => { setHazardId(e.target.value); setDirty(true); }} />
            </FormField>
            <FormField htmlFor="sa_investigation" label="Investigation ID" hint="Optional investigation link.">
              <input id="sa_investigation" name="investigation_id" className="app-input" placeholder="e.g. INV-..." value={investigationId} onChange={(e) => { setInvestigationId(e.target.value); setDirty(true); }} />
            </FormField>
          </div>
          <button
            disabled={!saIsValid || createMutation.isPending}
            onClick={() => createMutation.mutate({ title, description, action_type: actionType, owner_id: ownerId, due_date: dueDate || null, occurrence_id: occurrenceId || null, hazard_id: hazardId || null, investigation_id: investigationId || null })}
            className="app-btn-primary w-full"
          >
            {createMutation.isPending ? "Submitting…" : "Create Action"}
          </button>
        </div>
      )}

      <section className="app-surface overflow-hidden">
        <div className="flex flex-col gap-3 border-b border-kfl-border p-4 md:flex-row md:items-center md:justify-between">
          <div className="text-sm font-semibold text-kfl-text">Safety Actions</div>
          <div className="flex gap-2">
            <select id="sa_status_filter" name="status" aria-label="Filter by status" className="app-input w-full md:w-auto" onChange={(e) => {
              const val = e.target.value;
              qc.setQueryData(["safety-actions"], (old: any[]) => val ? old.filter((a: any) => a.status === val) : old);
            }}>
              <option value="">All statuses</option>
              <option value="open">Open</option>
              <option value="in_progress">In Progress</option>
              <option value="completed">Completed</option>
              <option value="verified">Verified</option>
              <option value="closed">Closed</option>
            </select>
            <select id="sa_type_filter" name="action_type" aria-label="Filter by action type" className="app-input w-full md:w-auto" onChange={(e) => {
              const val = e.target.value;
              qc.setQueryData(["safety-actions"], (old: any[]) => val ? old.filter((a: any) => a.action_type === val) : old);
            }}>
              <option value="">All types</option>
              <option value="corrective">Corrective</option>
              <option value="preventive">Preventive</option>
              <option value="improvement">Improvement</option>
            </select>
          </div>
        </div>

        {isLoading ? (
          <div className="p-10 text-center text-sm text-kfl-muted">Loading safety actions…</div>
        ) : actions.length === 0 ? (
          <div className="app-surface border-dashed p-10 text-center">
            <CheckCircle size={26} className="mx-auto mb-2 text-kfl-muted" />
            <p className="text-sm font-bold text-kfl-text">No safety actions recorded.</p>
            <p className="mt-1 text-xs text-kfl-muted">Create actions from occurrences, hazards, or investigations.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full">
              <thead className="border-b border-kfl-border bg-kfl-surface-subtle">
                <tr>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Action ID</th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Title</th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Type</th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Owner</th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Due Date</th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Status</th>
                  <th className="px-4 py-3 text-right text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-kfl-border">
                {actions.map((a: any) => (
                  <tr key={a.action_id} className="transition hover:bg-kfl-surface-subtle group">
                    <td className="px-4 py-4 font-mono text-[12px] text-kfl-text">{a.action_id}</td>
                    <td className="px-4 py-4">
                      <div className="font-semibold text-kfl-text">{a.title}</div>
                      <div className="mt-1 text-xs text-kfl-muted line-clamp-1">{a.description}</div>
                    </td>
                    <td className="px-4 py-4">
                      <span className={actionTypeClass(a.action_type)}>{a.action_type}</span>
                    </td>
                    <td className="px-4 py-4 text-sm text-kfl-secondary">{a.owner_id}</td>
                    <td className="px-4 py-4 text-sm text-kfl-secondary">{a.due_date || "—"}</td>
                    <td className="px-4 py-4">
                      <span className={statusClass(a.status)}>{a.status}</span>
                    </td>
                    <td className="px-4 py-4 text-right text-sm">
                      <select
                        aria-label={`Update status for ${a.action_id}`}
                        className="app-input w-auto text-xs"
                        value={a.status}
                        onChange={(e) => updateMutation.mutate({ id: a.action_id, data: { status: e.target.value } })}
                      >
                        <option value="open">Open</option>
                        <option value="in_progress">In Progress</option>
                        <option value="completed">Completed</option>
                        <option value="verified">Verified</option>
                        <option value="closed">Closed</option>
                      </select>
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
