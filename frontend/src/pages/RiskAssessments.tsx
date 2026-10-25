import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { safetyApi } from "../api/safety";
import { ShieldCheck, Plus } from "lucide-react";
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
    case "draft": return "app-status app-status-info";
    case "under_review": return "app-status app-status-warning";
    case "approved": return "app-status app-status-healthy";
    case "rejected": return "app-status app-status-critical";
    case "implemented": return "app-status app-status-healthy";
    default: return "app-status app-status-info";
  }
}

export function RiskAssessments() {
  const qc = useQueryClient();
  const { data: assessments = [], isLoading } = useQuery({
    queryKey: ["risk-assessments"],
    queryFn: () => safetyApi.listRiskAssessments(),
  });
  const [showForm, setShowForm] = useState(false);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [hazardId, setHazardId] = useState("");
  const [occurrenceId, setOccurrenceId] = useState("");
  const [missionId, setMissionId] = useState("");
  const [likelihood, setLikelihood] = useState("possible");
  const [severity, setSeverity] = useState("minor");
  const [riskLevel, setRiskLevel] = useState("medium");
  const [mitigationMeasures, setMitigationMeasures] = useState("");
  const [residualRisk, setResidualRisk] = useState("");
  const [dirty, setDirty] = useState(false);

  const { errors: raErrors, isValid: raIsValid } = useValidation(
    { title, description, likelihood, severity, risk_level: riskLevel },
    {
      title: { required: true, minLength: 2 },
      description: { required: true, minLength: 5 },
      likelihood: { required: true },
      severity: { required: true },
      risk_level: { required: true },
    }
  );

  useUnsavedChanges(showForm && dirty);

  const createMutation = useMutation({
    mutationFn: (data: any) => safetyApi.createRiskAssessment(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["risk-assessments"] });
      setShowForm(false);
      setDirty(false);
      setTitle("");
      setDescription("");
      setHazardId("");
      setOccurrenceId("");
      setMissionId("");
      setLikelihood("possible");
      setSeverity("minor");
      setRiskLevel("medium");
      setMitigationMeasures("");
      setResidualRisk("");
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: any }) => safetyApi.updateRiskAssessment(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["risk-assessments"] });
    },
  });

  return (
    <div className="app-page">
      <header className="app-page-header">
        <div>
          <div className="app-eyebrow">Safety Management</div>
          <h1 className="app-title">Risk Assessments</h1>
          <p className="app-subtitle">Assess hazards and occurrences, define mitigations, and track residual risk.</p>
        </div>
        <button
          onClick={() => setShowForm(!showForm)}
          className="app-btn-primary"
        >
          <Plus size={16} /> {showForm ? "Cancel" : "New Assessment"}
        </button>
      </header>

      <section className="mb-5 grid grid-cols-1 gap-4 sm:grid-cols-4">
        <div className="app-surface p-4">
          <div className="app-label">Total Assessments</div>
          <div className="mt-2 text-2xl font-bold text-kfl-text">{assessments.length}</div>
        </div>
        <div className="app-surface p-4">
          <div className="app-label">Draft</div>
          <div className="mt-2 text-2xl font-bold text-amber-700">{assessments.filter((r: any) => r.status === "draft").length}</div>
        </div>
        <div className="app-surface p-4">
          <div className="app-label">High / Critical</div>
          <div className="mt-2 text-2xl font-bold text-red-700">{assessments.filter((r: any) => r.risk_level === "high" || r.risk_level === "critical").length}</div>
        </div>
        <div className="app-surface p-4">
          <div className="app-label">Implemented</div>
          <div className="mt-2 text-2xl font-bold text-emerald-700">{assessments.filter((r: any) => r.status === "implemented").length}</div>
        </div>
      </section>

      {showForm && (
        <div className="app-surface p-5 mb-5">
          <div className="mb-4 flex items-start justify-between gap-4">
            <div>
              <div className="app-label mb-1">New Risk Assessment</div>
              <p className="text-xs text-kfl-muted">Assess a hazard, occurrence, or mission for likelihood, severity, and mitigation.</p>
            </div>
            <button onClick={() => { setShowForm(false); setDirty(false); }} className="app-btn-secondary px-4 py-2 text-sm">Cancel</button>
          </div>
          <div className="space-y-3 mb-4">
            <FormField htmlFor="ra_title" label="Assessment title" hint="Summarize the risk being assessed." required>
              <input id="ra_title" name="title" aria-describedby="ra_title-error" aria-invalid={!!raErrors.title} className={`app-input ${raErrors.title ? "border-rose-400" : ""}`} placeholder="Assessment title" value={title} onChange={(e) => { setTitle(e.target.value); setDirty(true); }} />
              {raErrors.title && <p id="ra_title-error" className="text-[11px] text-rose-700 mt-1">{raErrors.title}</p>}
            </FormField>
            <FormField htmlFor="ra_description" label="Description" hint="Describe the scenario, exposure, and potential consequences." required>
              <textarea id="ra_description" name="description" aria-describedby="ra_description-error" aria-invalid={!!raErrors.description} className={`app-input ${raErrors.description ? "border-rose-400" : ""}`} placeholder="Describe the risk scenario" value={description} onChange={(e) => { setDescription(e.target.value); setDirty(true); }} rows={3} />
              {raErrors.description && <p id="ra_description-error" className="text-[11px] text-rose-700 mt-1">{raErrors.description}</p>}
            </FormField>
          </div>
          <div className="grid grid-cols-2 gap-4 mb-4">
            <FormField htmlFor="ra_hazard" label="Hazard ID" hint="Link to an existing hazard record.">
              <input id="ra_hazard" name="hazard_id" className="app-input" placeholder="e.g. HAZ-..." value={hazardId} onChange={(e) => { setHazardId(e.target.value); setDirty(true); }} />
            </FormField>
            <FormField htmlFor="ra_occurrence" label="Occurrence ID" hint="Link to an existing occurrence.">
              <input id="ra_occurrence" name="occurrence_id" className="app-input" placeholder="e.g. OCC-..." value={occurrenceId} onChange={(e) => { setOccurrenceId(e.target.value); setDirty(true); }} />
            </FormField>
          </div>
          <div className="grid grid-cols-2 gap-4 mb-4">
            <div>
              <label className="app-label">Likelihood</label>
              <select id="ra_likelihood" name="likelihood" value={likelihood} onChange={(e) => { setLikelihood(e.target.value); setDirty(true); }} className="app-input">
                <option value="rare">Rare</option>
                <option value="unlikely">Unlikely</option>
                <option value="possible">Possible</option>
                <option value="likely">Likely</option>
                <option value="certain">Certain</option>
              </select>
            </div>
            <div>
              <label className="app-label">Severity</label>
              <select id="ra_severity" name="severity" value={severity} onChange={(e) => { setSeverity(e.target.value); setDirty(true); }} className="app-input">
                <option value="negligible">Negligible</option>
                <option value="minor">Minor</option>
                <option value="major">Major</option>
                <option value="hazardous">Hazardous</option>
                <option value="catastrophic">Catastrophic</option>
              </select>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4 mb-4">
            <div>
              <label className="app-label">Risk Level</label>
              <select id="ra_risk" name="risk_level" value={riskLevel} onChange={(e) => { setRiskLevel(e.target.value); setDirty(true); }} className="app-input">
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
                <option value="critical">Critical</option>
              </select>
            </div>
            <FormField htmlFor="ra_mission" label="Mission ID" hint="Optional mission link.">
              <input id="ra_mission" name="mission_id" className="app-input" placeholder="e.g. MSN-..." value={missionId} onChange={(e) => { setMissionId(e.target.value); setDirty(true); }} />
            </FormField>
          </div>
          <div className="space-y-3 mb-4">
            <FormField htmlFor="ra_mitigation" label="Mitigation measures" hint="Controls or actions to reduce likelihood or severity.">
              <textarea id="ra_mitigation" name="mitigation_measures" className="app-input" placeholder="Mitigation measures" value={mitigationMeasures} onChange={(e) => { setMitigationMeasures(e.target.value); setDirty(true); }} rows={2} />
            </FormField>
            <FormField htmlFor="ra_residual" label="Residual risk" hint="Remaining risk after mitigations are applied.">
              <input id="ra_residual" name="residual_risk" className="app-input" placeholder="Residual risk statement" value={residualRisk} onChange={(e) => { setResidualRisk(e.target.value); setDirty(true); }} />
            </FormField>
          </div>
          <button
            disabled={!raIsValid || createMutation.isPending}
            onClick={() => createMutation.mutate({ title, description, hazard_id: hazardId || null, occurrence_id: occurrenceId || null, mission_id: missionId || null, likelihood, severity, risk_level: riskLevel, mitigation_measures: mitigationMeasures || null, residual_risk: residualRisk || null })}
            className="app-btn-primary w-full"
          >
            {createMutation.isPending ? "Submitting…" : "Submit Assessment"}
          </button>
        </div>
      )}

      <section className="app-surface overflow-hidden">
        <div className="flex flex-col gap-3 border-b border-kfl-border p-4 md:flex-row md:items-center md:justify-between">
          <div className="text-sm font-semibold text-kfl-text">Risk Assessments</div>
          <div className="flex gap-2">
            <select id="ra_status_filter" name="status" aria-label="Filter by status" className="app-input w-full md:w-auto" onChange={(e) => {
              const val = e.target.value;
              qc.setQueryData(["risk-assessments"], (old: any[]) => val ? old.filter((r: any) => r.status === val) : old);
            }}>
              <option value="">All statuses</option>
              <option value="draft">Draft</option>
              <option value="under_review">Under Review</option>
              <option value="approved">Approved</option>
              <option value="rejected">Rejected</option>
              <option value="implemented">Implemented</option>
            </select>
            <select id="ra_risk_filter" name="risk_level" aria-label="Filter by risk level" className="app-input w-full md:w-auto" onChange={(e) => {
              const val = e.target.value;
              qc.setQueryData(["risk-assessments"], (old: any[]) => val ? old.filter((r: any) => r.risk_level === val) : old);
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
          <div className="p-10 text-center text-sm text-kfl-muted">Loading risk assessments…</div>
        ) : assessments.length === 0 ? (
          <div className="app-surface border-dashed p-10 text-center">
            <ShieldCheck size={26} className="mx-auto mb-2 text-kfl-muted" />
            <p className="text-sm font-bold text-kfl-text">No risk assessments recorded.</p>
            <p className="mt-1 text-xs text-kfl-muted">Create your first assessment to begin risk tracking.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full">
              <thead className="border-b border-kfl-border bg-kfl-surface-subtle">
                <tr>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Assessment ID</th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Title</th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Linked To</th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Risk</th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Status</th>
                  <th className="px-4 py-3 text-right text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-kfl-border">
                {assessments.map((r: any) => (
                  <tr key={r.assessment_id} className="transition hover:bg-kfl-surface-subtle group">
                    <td className="px-4 py-4 font-mono text-[12px] text-kfl-text">{r.assessment_id}</td>
                    <td className="px-4 py-4">
                      <div className="font-semibold text-kfl-text">{r.title}</div>
                      <div className="mt-1 text-xs text-kfl-muted line-clamp-1">{r.description}</div>
                    </td>
                    <td className="px-4 py-4 text-sm text-kfl-secondary">
                      {r.hazard_id ? `Hazard ${r.hazard_id}` : r.occurrence_id ? `Occurrence ${r.occurrence_id}` : r.mission_id ? `Mission ${r.mission_id}` : "—"}
                    </td>
                    <td className="px-4 py-4">
                      <span className={riskClass(r.risk_level)}>{r.risk_level}</span>
                    </td>
                    <td className="px-4 py-4">
                      <span className={statusClass(r.status)}>{r.status}</span>
                    </td>
                    <td className="px-4 py-4 text-right text-sm">
                      <select
                        aria-label={`Update status for ${r.assessment_id}`}
                        className="app-input w-auto text-xs"
                        value={r.status}
                        onChange={(e) => updateMutation.mutate({ id: r.assessment_id, data: { status: e.target.value } })}
                      >
                        <option value="draft">Draft</option>
                        <option value="under_review">Under Review</option>
                        <option value="approved">Approved</option>
                        <option value="rejected">Rejected</option>
                        <option value="implemented">Implemented</option>
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
