import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { safetyApi } from "../api/safety";
import { CheckCircle, Plus } from "lucide-react";
import FormField from "../components/ui/FormField";
import { useValidation } from "../utils/validation";
import { useUnsavedChanges } from "../hooks/useUnsavedChanges";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select";

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
        <Button
          onClick={() => setShowForm(!showForm)}
          variant="default"
          size="sm"
        >
          <Plus size={16} /> {showForm ? "Cancel" : "New Action"}
        </Button>
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
            <Button variant="outline" size="sm" onClick={() => { setShowForm(false); setDirty(false); }}>
              Cancel
            </Button>
          </div>
          <div className="space-y-3 mb-4">
            <FormField htmlFor="sa_title" label="Action title" hint="Brief title for the safety action." required>
              <Input id="sa_title" name="title" aria-describedby="sa_title-error" aria-invalid={!!saErrors.title} className={saErrors.title ? "border-rose-400" : ""} placeholder="Action title" value={title} onChange={(e) => { setTitle(e.target.value); setDirty(true); }} />
              {saErrors.title && <p id="sa_title-error" className="text-[11px] text-rose-700 mt-1">{saErrors.title}</p>}
            </FormField>
            <FormField htmlFor="sa_description" label="Description" hint="Describe the action and its purpose." required>
              <textarea id="sa_description" name="description" aria-describedby="sa_description-error" aria-invalid={!!saErrors.description} className={saErrors.description ? "border-rose-400" : ""} placeholder="Describe the action" value={description} onChange={(e) => { setDescription(e.target.value); setDirty(true); }} rows={3} />
              {saErrors.description && <p id="sa_description-error" className="text-[11px] text-rose-700 mt-1">{saErrors.description}</p>}
            </FormField>
          </div>
          <div className="grid grid-cols-2 gap-4 mb-4">
            <div>
              <label className="app-label">Action Type</label>
              <Select onValueChange={(e) => { setActionType(e); setDirty(true); }}>
                <SelectTrigger id="sa_type" name="action_type">
                  <SelectValue placeholder={actionType} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="corrective">Corrective</SelectItem>
                  <SelectItem value="preventive">Preventive</SelectItem>
                  <SelectItem value="improvement">Improvement</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <FormField htmlFor="sa_owner" label="Owner ID" hint="Person responsible for completing this action." required>
              <Input id="sa_owner" name="owner_id" aria-describedby="sa_owner-error" aria-invalid={!!saErrors.owner_id} className={saErrors.owner_id ? "border-rose-400" : ""} placeholder="e.g. u-safety/security" value={ownerId} onChange={(e) => { setOwnerId(e.target.value); setDirty(true); }} />
              {saErrors.owner_id && <p id="sa_owner-error" className="text-[11px] text-rose-700 mt-1">{saErrors.owner_id}</p>}
            </FormField>
          </div>
          <div className="grid grid-cols-2 gap-4 mb-4">
            <FormField htmlFor="sa_due" label="Due date" hint="Target completion date.">
              <Input id="sa_due" name="due_date" type="date" value={dueDate} onChange={(e) => { setDueDate(e.target.value); setDirty(true); }} />
            </FormField>
            <FormField htmlFor="sa_occurrence" label="Occurrence ID" hint="Optional occurrence link.">
              <Input id="sa_occurrence" name="occurrence_id" placeholder="e.g. OCC-..." value={occurrenceId} onChange={(e) => { setOccurrenceId(e.target.value); setDirty(true); }} />
            </FormField>
          </div>
          <div className="grid grid-cols-2 gap-4 mb-4">
            <FormField htmlFor="sa_hazard" label="Hazard ID" hint="Optional hazard link.">
              <Input id="sa_hazard" name="hazard_id" placeholder="e.g. HAZ-..." value={hazardId} onChange={(e) => { setHazardId(e.target.value); setDirty(true); }} />
            </FormField>
            <FormField htmlFor="sa_investigation" label="Investigation ID" hint="Optional investigation link.">
              <Input id="sa_investigation" name="investigation_id" placeholder="e.g. INV-..." value={investigationId} onChange={(e) => { setInvestigationId(e.target.value); setDirty(true); }} />
            </FormField>
          </div>
          <Button
            disabled={!saIsValid || createMutation.isPending}
            onClick={() => createMutation.mutate({ title, description, action_type: actionType, owner_id: ownerId, due_date: dueDate || null, occurrence_id: occurrenceId || null, hazard_id: hazardId || null, investigation_id: investigationId || null })}
            variant="default"
            size="sm"
            className="w-full disabled:opacity-60"
          >
            {createMutation.isPending ? "Submitting…" : "Create Action"}
          </Button>
        </div>
      )}

      <section className="app-surface overflow-hidden">
        <div className="flex flex-col gap-3 border-b border-kfl-border p-4 md:flex-row md:items-center md:justify-between">
          <div className="text-sm font-semibold text-kfl-text">Safety Actions</div>
          <div className="flex gap-2">
            <Select onValueChange={(e) => {
              const val = e;
              qc.setQueryData(["safety-actions"], (old: any[]) => val ? old.filter((a: any) => a.status === val) : old);
            }}>
              <SelectTrigger id="sa_status_filter" name="status" aria-label="Filter by status">
                <SelectValue placeholder="All statuses" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="">All statuses</SelectItem>
                <SelectItem value="open">Open</SelectItem>
                <SelectItem value="in_progress">In Progress</SelectItem>
                <SelectItem value="completed">Completed</SelectItem>
                <SelectItem value="verified">Verified</SelectItem>
                <SelectItem value="closed">Closed</SelectItem>
              </SelectContent>
            </Select>
            <Select onValueChange={(e) => {
              const val = e;
              qc.setQueryData(["safety-actions"], (old: any[]) => val ? old.filter((a: any) => a.action_type === val) : old);
            }}>
              <SelectTrigger id="sa_type_filter" name="action_type" aria-label="Filter by action type">
                <SelectValue placeholder="All types" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="">All types</SelectItem>
                <SelectItem value="corrective">Corrective</SelectItem>
                <SelectItem value="preventive">Preventive</SelectItem>
                <SelectItem value="improvement">Improvement</SelectItem>
              </SelectContent>
            </Select>
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
                    <td className="px-4 py-4"><Badge variant={a.action_type === "improvement" ? "default" : a.action_type === "preventive" ? "secondary" : "outline"} className={`badge ${a.action_type === "improvement" ? "bg-kfl-status-info-bg text-kfl-status-info" : a.action_type === "preventive" ? "bg-kfl-status-warning-bg text-kfl-status-warning" : "bg-kfl-status-danger-bg text-kfl-status-danger"}`}>{a.action_type}</Badge></td>
                    <td className="px-4 py-4 text-sm text-kfl-secondary">{a.owner_id}</td>
                    <td className="px-4 py-4 text-sm text-kfl-secondary">{a.due_date || "—"}</td>
                    <td className="px-4 py-4"><Badge variant={a.status === "completed" || a.status === "verified" ? "default" : a.status === "in_progress" ? "secondary" : a.status === "closed" ? "destructive" : "outline"} className={`badge ${a.status === "completed" || a.status === "verified" ? "bg-kfl-status-info-bg text-kfl-status-info" : a.status === "in_progress" ? "bg-kfl-status-warning-bg text-kfl-status-warning" : a.status === "closed" ? "bg-kfl-status-danger-bg text-kfl-status-danger" : "bg-kfl-status-info-bg text-kfl-status-info"}`}>{a.status}</Badge></td>
                    <td className="px-4 py-4 text-right text-sm">
                      <Select onValueChange={(e) => updateMutation.mutate({ id: a.action_id, data: { status: e } })}>
                        <SelectTrigger aria-label={`Update status for ${a.action_id}`} className="w-auto text-xs">
                          <SelectValue placeholder={a.status} />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="open">Open</SelectItem>
                          <SelectItem value="in_progress">In Progress</SelectItem>
                          <SelectItem value="completed">Completed</SelectItem>
                          <SelectItem value="verified">Verified</SelectItem>
                          <SelectItem value="closed">Closed</SelectItem>
                        </SelectContent>
                      </Select>
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
