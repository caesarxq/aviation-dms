import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { safetyApi } from "../api/safety";
import { Search, Plus } from "lucide-react";
import FormField from "../components/ui/FormField";
import { useValidation } from "../utils/validation";
import { useUnsavedChanges } from "../hooks/useUnsavedChanges";

function statusClass(status: string) {
  switch (status) {
    case "open": return "app-status app-status-info";
    case "in_progress": return "app-status app-status-warning";
    case "completed": return "app-status app-status-healthy";
    case "closed": return "app-status app-status-info";
    default: return "app-status app-status-info";
  }
}

export function Investigations() {
  const qc = useQueryClient();
  const { data: investigations = [], isLoading } = useQuery({
    queryKey: ["investigations"],
    queryFn: () => safetyApi.listInvestigations(),
  });
  const [showForm, setShowForm] = useState(false);
  const [occurrenceId, setOccurrenceId] = useState("");
  const [investigatorId, setInvestigatorId] = useState("");
  const [findings, setFindings] = useState("");
  const [rootCause, setRootCause] = useState("");
  const [recommendations, setRecommendations] = useState("");
  const [dirty, setDirty] = useState(false);

  const { errors: invErrors, isValid: invIsValid } = useValidation(
    { occurrence_id: occurrenceId, investigator_id: investigatorId },
    {
      occurrence_id: { required: true },
      investigator_id: { required: true, minLength: 2 },
    }
  );

  useUnsavedChanges(showForm && dirty);

  const createMutation = useMutation({
    mutationFn: (data: any) => safetyApi.createInvestigation(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["investigations"] });
      setShowForm(false);
      setDirty(false);
      setOccurrenceId("");
      setInvestigatorId("");
      setFindings("");
      setRootCause("");
      setRecommendations("");
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: any }) => safetyApi.updateInvestigation(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["investigations"] });
    },
  });

  return (
    <div className="app-page">
      <header className="app-page-header">
        <div>
          <div className="app-eyebrow">Safety Management</div>
          <h1 className="app-title">Investigations</h1>
          <p className="app-subtitle">Track occurrence investigations, findings, root causes, and recommendations.</p>
        </div>
        <button
          onClick={() => setShowForm(!showForm)}
          className="app-btn-primary"
        >
          <Plus size={16} /> {showForm ? "Cancel" : "New Investigation"}
        </button>
      </header>

      <section className="mb-5 grid grid-cols-1 gap-4 sm:grid-cols-4">
        <div className="app-surface p-4">
          <div className="app-label">Total Investigations</div>
          <div className="mt-2 text-2xl font-bold text-kfl-text">{investigations.length}</div>
        </div>
        <div className="app-surface p-4">
          <div className="app-label">Open</div>
          <div className="mt-2 text-2xl font-bold text-amber-700">{investigations.filter((i: any) => i.status === "open").length}</div>
        </div>
        <div className="app-surface p-4">
          <div className="app-label">In Progress</div>
          <div className="mt-2 text-2xl font-bold text-blue-700">{investigations.filter((i: any) => i.status === "in_progress").length}</div>
        </div>
        <div className="app-surface p-4">
          <div className="app-label">Completed</div>
          <div className="mt-2 text-2xl font-bold text-emerald-700">{investigations.filter((i: any) => i.status === "completed").length}</div>
        </div>
      </section>

      {showForm && (
        <div className="app-surface p-5 mb-5">
          <div className="mb-4 flex items-start justify-between gap-4">
            <div>
              <div className="app-label mb-1">New Investigation</div>
              <p className="text-xs text-kfl-muted">Open an investigation for an occurrence and assign an investigator.</p>
            </div>
            <button onClick={() => { setShowForm(false); setDirty(false); }} className="app-btn-secondary px-4 py-2 text-sm">Cancel</button>
          </div>
          <div className="space-y-3 mb-4">
            <FormField htmlFor="inv_occurrence" label="Occurrence ID" hint="The occurrence to investigate." required>
              <input id="inv_occurrence" name="occurrence_id" aria-describedby="inv_occurrence-error" aria-invalid={!!invErrors.occurrence_id} className={`app-input ${invErrors.occurrence_id ? "border-rose-400" : ""}`} placeholder="e.g. OCC-..." value={occurrenceId} onChange={(e) => { setOccurrenceId(e.target.value); setDirty(true); }} />
              {invErrors.occurrence_id && <p id="inv_occurrence-error" className="text-[11px] text-rose-700 mt-1">{invErrors.occurrence_id}</p>}
            </FormField>
            <FormField htmlFor="inv_investigator" label="Investigator ID" hint="Person responsible for this investigation." required>
              <input id="inv_investigator" name="investigator_id" aria-describedby="inv_investigator-error" aria-invalid={!!invErrors.investigator_id} className={`app-input ${invErrors.investigator_id ? "border-rose-400" : ""}`} placeholder="e.g. u-safety" value={investigatorId} onChange={(e) => { setInvestigatorId(e.target.value); setDirty(true); }} />
              {invErrors.investigator_id && <p id="inv_investigator-error" className="text-[11px] text-rose-700 mt-1">{invErrors.investigator_id}</p>}
            </FormField>
          </div>
          <div className="space-y-3 mb-4">
            <FormField htmlFor="inv_findings" label="Findings" hint="Initial findings from the investigation.">
              <textarea id="inv_findings" name="findings" className="app-input" placeholder="Investigation findings" value={findings} onChange={(e) => { setFindings(e.target.value); setDirty(true); }} rows={3} />
            </FormField>
            <FormField htmlFor="inv_root_cause" label="Root cause" hint="Identified root cause, if known.">
              <textarea id="inv_root_cause" name="root_cause" className="app-input" placeholder="Root cause analysis" value={rootCause} onChange={(e) => { setRootCause(e.target.value); setDirty(true); }} rows={2} />
            </FormField>
            <FormField htmlFor="inv_recommendations" label="Recommendations" hint="Corrective or preventive actions recommended.">
              <textarea id="inv_recommendations" name="recommendations" className="app-input" placeholder="Recommendations" value={recommendations} onChange={(e) => { setRecommendations(e.target.value); setDirty(true); }} rows={2} />
            </FormField>
          </div>
          <button
            disabled={!invIsValid || createMutation.isPending}
            onClick={() => createMutation.mutate({ occurrence_id: occurrenceId, investigator_id: investigatorId, findings: findings || null, root_cause: rootCause || null, recommendations: recommendations || null })}
            className="app-btn-primary w-full"
          >
            {createMutation.isPending ? "Submitting…" : "Open Investigation"}
          </button>
        </div>
      )}

      <section className="app-surface overflow-hidden">
        <div className="flex flex-col gap-3 border-b border-kfl-border p-4 md:flex-row md:items-center md:justify-between">
          <div className="relative min-w-0 flex-1 md:max-w-md">
            <Search size={16} className="pointer-events-none absolute left-3 top-3 text-kfl-muted" />
            <input id="investigations_search" name="search" placeholder="Search investigations…" className="app-input pl-9 relative z-10" onChange={(e) => {
              const q = e.target.value.toLowerCase();
              qc.setQueryData(["investigations"], (old: any[]) => q ? old.filter((i: any) => (i.occurrence_id + " " + (i.findings || "") + " " + (i.root_cause || "")).toLowerCase().includes(q)) : old);
            }} />
          </div>
          <select id="inv_status_filter" name="status" aria-label="Filter by status" className="app-input w-full md:w-auto" onChange={(e) => {
            const val = e.target.value;
            qc.setQueryData(["investigations"], (old: any[]) => val ? old.filter((i: any) => i.status === val) : old);
          }}>
            <option value="">All statuses</option>
            <option value="open">Open</option>
            <option value="in_progress">In Progress</option>
            <option value="completed">Completed</option>
            <option value="closed">Closed</option>
          </select>
        </div>

        {isLoading ? (
          <div className="p-10 text-center text-sm text-kfl-muted">Loading investigations…</div>
        ) : investigations.length === 0 ? (
          <div className="app-surface border-dashed p-10 text-center">
            <Search size={26} className="mx-auto mb-2 text-kfl-muted" />
            <p className="text-sm font-bold text-kfl-text">No investigations recorded.</p>
            <p className="mt-1 text-xs text-kfl-muted">Open an investigation from an occurrence to begin tracking.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full">
              <thead className="border-b border-kfl-border bg-kfl-surface-subtle">
                <tr>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Investigation ID</th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Occurrence</th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Investigator</th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Root Cause</th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Status</th>
                  <th className="px-4 py-3 text-right text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-kfl-border">
                {investigations.map((inv: any) => (
                  <tr key={inv.investigation_id} className="transition hover:bg-kfl-surface-subtle group">
                    <td className="px-4 py-4 font-mono text-[12px] text-kfl-text">{inv.investigation_id}</td>
                    <td className="px-4 py-4 text-sm text-kfl-secondary">{inv.occurrence_id}</td>
                    <td className="px-4 py-4 text-sm text-kfl-secondary">{inv.investigator_id}</td>
                    <td className="px-4 py-4 text-xs text-kfl-muted line-clamp-1">{inv.root_cause || "—"}</td>
                    <td className="px-4 py-4">
                      <span className={statusClass(inv.status)}>{inv.status}</span>
                    </td>
                    <td className="px-4 py-4 text-right text-sm">
                      <select
                        aria-label={`Update status for ${inv.investigation_id}`}
                        className="app-input w-auto text-xs"
                        value={inv.status}
                        onChange={(e) => updateMutation.mutate({ id: inv.investigation_id, data: { status: e.target.value } })}
                      >
                        <option value="open">Open</option>
                        <option value="in_progress">In Progress</option>
                        <option value="completed">Completed</option>
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
