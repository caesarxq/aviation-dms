import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { safetyApi } from "../api/safety";
import { AlertTriangle, Plus } from "lucide-react";
import FormField from "../components/ui/FormField";
import { useValidation } from "../utils/validation";
import { useUnsavedChanges } from "../hooks/useUnsavedChanges";

function riskClass(risk: string) {
  switch (risk) {
    case "critical": return "app-status app-status-critical";
    case "high": return "app-status app-status-warning";
    case "medium": return "app-status app-status-info";
    case "low": return "app-status app-status-healthy";
    default: return "app-status app-status-info";
  }
}

function statusClass(status: string) {
  switch (status) {
    case "identified": return "app-status app-status-info";
    case "assessed": return "app-status app-status-warning";
    case "mitigated": return "app-status app-status-healthy";
    case "closed": return "app-status app-status-info";
    default: return "app-status app-status-info";
  }
}

export function Hazards() {
  const qc = useQueryClient();
  const { data: hazards = [], isLoading } = useQuery({
    queryKey: ["hazards"],
    queryFn: () => safetyApi.listHazards(),
  });
  const [showForm, setShowForm] = useState(false);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [category, setCategory] = useState("operational");
  const [riskLevel, setRiskLevel] = useState("medium");
  const [likelihood, setLikelihood] = useState("");
  const [severity, setSeverity] = useState("");
  const [mitigation, setMitigation] = useState("");
  const [ownerId, setOwnerId] = useState("");
  const [dirty, setDirty] = useState(false);

  const { errors: hazardErrors, isValid: hazardIsValid } = useValidation(
    { title, description, category, risk_level: riskLevel },
    {
      title: { required: true, minLength: 2 },
      description: { required: true, minLength: 5 },
      category: { required: true },
      risk_level: { required: true },
    }
  );

  useUnsavedChanges(showForm && dirty);

  const createMutation = useMutation({
    mutationFn: (data: any) => safetyApi.createHazard(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["hazards"] });
      setShowForm(false);
      setDirty(false);
      setTitle("");
      setDescription("");
      setCategory("operational");
      setRiskLevel("medium");
      setLikelihood("");
      setSeverity("");
      setMitigation("");
      setOwnerId("");
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: any }) => safetyApi.updateHazard(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["hazards"] });
    },
  });

  return (
    <div className="app-page">
      <header className="app-page-header">
        <div>
          <div className="app-eyebrow">Safety Management</div>
          <h1 className="app-title">Hazard Register</h1>
          <p className="app-subtitle">Identify, assess, and mitigate operational hazards.</p>
        </div>
        <button
          onClick={() => setShowForm(!showForm)}
          className="app-btn-primary"
        >
          <Plus size={16} /> {showForm ? "Cancel" : "New Hazard"}
        </button>
      </header>

      <section className="mb-5 grid grid-cols-1 gap-4 sm:grid-cols-4">
        <div className="app-surface p-4">
          <div className="app-label">Total Hazards</div>
          <div className="mt-2 text-2xl font-bold text-kfl-text">{hazards.length}</div>
        </div>
        <div className="app-surface p-4">
          <div className="app-label">Open / Identified</div>
          <div className="mt-2 text-2xl font-bold text-amber-700">{hazards.filter((h: any) => h.status === "identified").length}</div>
        </div>
        <div className="app-surface p-4">
          <div className="app-label">High / Critical Risk</div>
          <div className="mt-2 text-2xl font-bold text-red-700">{hazards.filter((h: any) => h.risk_level === "high" || h.risk_level === "critical").length}</div>
        </div>
        <div className="app-surface p-4">
          <div className="app-label">Mitigated / Closed</div>
          <div className="mt-2 text-2xl font-bold text-emerald-700">{hazards.filter((h: any) => h.status === "mitigated" || h.status === "closed").length}</div>
        </div>
      </section>

      {showForm && (
        <div className="app-surface p-5 mb-5">
          <div className="mb-4 flex items-start justify-between gap-4">
            <div>
              <div className="app-label mb-1">New Hazard</div>
              <p className="text-xs text-kfl-muted">Record a newly identified hazard for assessment and mitigation.</p>
            </div>
            <button onClick={() => { setShowForm(false); setDirty(false); }} className="app-btn-secondary px-4 py-2 text-sm">Cancel</button>
          </div>
          <div className="space-y-3 mb-4">
            <FormField htmlFor="hazard_title" label="Hazard title" hint="Brief title describing the hazard." required>
              <input id="hazard_title" name="title" aria-describedby="hazard_title-error" aria-invalid={!!hazardErrors.title} className={`app-input ${hazardErrors.title ? "border-rose-400" : ""}`} placeholder="Hazard title" value={title} onChange={(e) => { setTitle(e.target.value); setDirty(true); }} />
              {hazardErrors.title && <p id="hazard_title-error" className="text-[11px] text-rose-700 mt-1">{hazardErrors.title}</p>}
            </FormField>
            <FormField htmlFor="hazard_description" label="Description" hint="Describe the hazard, conditions, and potential consequences." required>
              <textarea id="hazard_description" name="description" aria-describedby="hazard_description-error" aria-invalid={!!hazardErrors.description} className={`app-input ${hazardErrors.description ? "border-rose-400" : ""}`} placeholder="Describe the hazard" value={description} onChange={(e) => { setDescription(e.target.value); setDirty(true); }} rows={3} />
              {hazardErrors.description && <p id="hazard_description-error" className="text-[11px] text-rose-700 mt-1">{hazardErrors.description}</p>}
            </FormField>
          </div>
          <div className="grid grid-cols-2 gap-4 mb-4">
            <div>
              <label className="app-label">Category</label>
              <select id="hazard_category" name="category" value={category} onChange={(e) => { setCategory(e.target.value); setDirty(true); }} className="app-input">
                <option value="operational">Operational</option>
                <option value="technical">Technical</option>
                <option value="environmental">Environmental</option>
                <option value="human">Human Factors</option>
                <option value="organizational">Organizational</option>
              </select>
            </div>
            <div>
              <label className="app-label">Risk Level</label>
              <select id="hazard_risk" name="risk_level" value={riskLevel} onChange={(e) => { setRiskLevel(e.target.value); setDirty(true); }} className="app-input">
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
                <option value="critical">Critical</option>
              </select>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4 mb-4">
            <div>
              <label className="app-label">Likelihood</label>
              <select id="hazard_likelihood" name="likelihood" value={likelihood} onChange={(e) => { setLikelihood(e.target.value); setDirty(true); }} className="app-input">
                <option value="">—</option>
                <option value="rare">Rare</option>
                <option value="unlikely">Unlikely</option>
                <option value="possible">Possible</option>
                <option value="likely">Likely</option>
                <option value="certain">Certain</option>
              </select>
            </div>
            <div>
              <label className="app-label">Severity</label>
              <select id="hazard_severity" name="severity" value={severity} onChange={(e) => { setSeverity(e.target.value); setDirty(true); }} className="app-input">
                <option value="">—</option>
                <option value="negligible">Negligible</option>
                <option value="minor">Minor</option>
                <option value="major">Major</option>
                <option value="hazardous">Hazardous</option>
                <option value="catastrophic">Catastrophic</option>
              </select>
            </div>
          </div>
          <div className="space-y-3 mb-4">
            <FormField htmlFor="hazard_mitigation" label="Initial mitigation" hint="Planned controls or immediate actions.">
              <textarea id="hazard_mitigation" name="mitigation" className="app-input" placeholder="Initial mitigation measures" value={mitigation} onChange={(e) => { setMitigation(e.target.value); setDirty(true); }} rows={2} />
            </FormField>
            <FormField htmlFor="hazard_owner" label="Owner ID" hint="Person responsible for tracking this hazard.">
              <input id="hazard_owner" name="owner_id" className="app-input" placeholder="e.g. u-safety" value={ownerId} onChange={(e) => { setOwnerId(e.target.value); setDirty(true); }} />
            </FormField>
          </div>
          <button
            disabled={!hazardIsValid || createMutation.isPending}
            onClick={() => createMutation.mutate({ title, description, category, risk_level: riskLevel, likelihood: likelihood || null, severity: severity || null, mitigation: mitigation || null, owner_id: ownerId || null })}
            className="app-btn-primary w-full"
          >
            {createMutation.isPending ? "Submitting…" : "Submit Hazard"}
          </button>
        </div>
      )}

      <section className="app-surface overflow-hidden">
        <div className="flex flex-col gap-3 border-b border-kfl-border p-4 md:flex-row md:items-center md:justify-between">
          <div className="text-sm font-semibold text-kfl-text">Hazard Register</div>
          <div className="flex gap-2">
            <select id="hazard_status_filter" name="status" aria-label="Filter by status" className="app-input w-full md:w-auto" onChange={(e) => {
              const val = e.target.value;
              qc.setQueryData(["hazards"], (old: any[]) => val ? old.filter((h: any) => h.status === val) : old);
            }}>
              <option value="">All statuses</option>
              <option value="identified">Identified</option>
              <option value="assessed">Assessed</option>
              <option value="mitigated">Mitigated</option>
              <option value="closed">Closed</option>
            </select>
            <select id="hazard_risk_filter" name="risk_level" aria-label="Filter by risk level" className="app-input w-full md:w-auto" onChange={(e) => {
              const val = e.target.value;
              qc.setQueryData(["hazards"], (old: any[]) => val ? old.filter((h: any) => h.risk_level === val) : old);
            }}>
              <option value="">All risk levels</option>
              <option value="low">Low</option>
              <option value="medium">Medium</option>
              <option value="high">High</option>
              <option value="critical">Critical</option>
            </select>
          </div>
        </div>

        {isLoading ? (
          <div className="p-10 text-center text-sm text-kfl-muted">Loading hazards…</div>
        ) : hazards.length === 0 ? (
          <div className="app-surface border-dashed p-10 text-center">
            <AlertTriangle size={26} className="mx-auto mb-2 text-kfl-muted" />
            <p className="text-sm font-bold text-kfl-text">No hazards recorded.</p>
            <p className="mt-1 text-xs text-kfl-muted">Report your first hazard to begin risk tracking.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full">
              <thead className="border-b border-kfl-border bg-kfl-surface-subtle">
                <tr>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Hazard ID</th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Title</th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Category</th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Risk</th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Status</th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Owner</th>
                  <th className="px-4 py-3 text-right text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-kfl-border">
                {hazards.map((h: any) => (
                  <tr key={h.hazard_id} className="transition hover:bg-kfl-surface-subtle group">
                    <td className="px-4 py-4 font-mono text-[12px] text-kfl-text">{h.hazard_id}</td>
                    <td className="px-4 py-4">
                      <div className="font-semibold text-kfl-text">{h.title}</div>
                      <div className="mt-1 text-xs text-kfl-muted line-clamp-1">{h.description}</div>
                    </td>
                    <td className="px-4 py-4 text-sm text-kfl-secondary">{h.category}</td>
                    <td className="px-4 py-4">
                      <span className={riskClass(h.risk_level)}>{h.risk_level}</span>
                    </td>
                    <td className="px-4 py-4">
                      <span className={statusClass(h.status)}>{h.status}</span>
                    </td>
                    <td className="px-4 py-4 text-sm text-kfl-secondary">{h.owner_id || "—"}</td>
                    <td className="px-4 py-4 text-right text-sm">
                      <select
                        aria-label={`Update status for ${h.hazard_id}`}
                        className="app-input w-auto text-xs"
                        value={h.status}
                        onChange={(e) => updateMutation.mutate({ id: h.hazard_id, data: { status: e.target.value } })}
                      >
                        <option value="identified">Identified</option>
                        <option value="assessed">Assessed</option>
                        <option value="mitigated">Mitigated</option>
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
