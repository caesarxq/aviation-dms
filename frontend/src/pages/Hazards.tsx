import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { safetyApi } from "../api/safety";
import { AlertTriangle, Plus } from "lucide-react";
import FormField from "../components/ui/FormField";
import { useValidation } from "../utils/validation";
import { useUnsavedChanges } from "../hooks/useUnsavedChanges";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select";

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
        <Button
          onClick={() => setShowForm(!showForm)}
          variant="default"
          size="sm"
        >
          <Plus size={16} /> {showForm ? "Cancel" : "New Hazard"}
        </Button>
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
            <Button variant="outline" size="sm" onClick={() => { setShowForm(false); setDirty(false); }}>
              Cancel
            </Button>
          </div>
          <div className="space-y-3 mb-4">
            <FormField htmlFor="hazard_title" label="Hazard title" hint="Brief title describing the hazard." required>
              <Input id="hazard_title" name="title" aria-describedby="hazard_title-error" aria-invalid={!!hazardErrors.title} className={hazardErrors.title ? "border-rose-400" : ""} placeholder="Hazard title" value={title} onChange={(e) => { setTitle(e.target.value); setDirty(true); }} />
              {hazardErrors.title && <p id="hazard_title-error" className="text-[11px] text-rose-700 mt-1">{hazardErrors.title}</p>}
            </FormField>
            <FormField htmlFor="hazard_description" label="Description" hint="Describe the hazard, conditions, and potential consequences." required>
              <textarea id="hazard_description" name="description" aria-describedby="hazard_description-error" aria-invalid={!!hazardErrors.description} className={hazardErrors.description ? "border-rose-400" : ""} placeholder="Describe the hazard" value={description} onChange={(e) => { setDescription(e.target.value); setDirty(true); }} rows={3} />
              {hazardErrors.description && <p id="hazard_description-error" className="text-[11px] text-rose-700 mt-1">{hazardErrors.description}</p>}
            </FormField>
          </div>
          <div className="grid grid-cols-2 gap-4 mb-4">
            <div>
              <label className="app-label">Category</label>
              <Select onValueChange={(e) => { setCategory(e); setDirty(true); }}>
                <SelectTrigger id="hazard_category" name="category">
                  <SelectValue placeholder={category} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="operational">Operational</SelectItem>
                  <SelectItem value="technical">Technical</SelectItem>
                  <SelectItem value="environmental">Environmental</SelectItem>
                  <SelectItem value="human">Human Factors</SelectItem>
                  <SelectItem value="organizational">Organizational</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <label className="app-label">Risk Level</label>
              <Select onValueChange={(e) => { setRiskLevel(e); setDirty(true); }}>
                <SelectTrigger id="hazard_risk" name="risk_level">
                  <SelectValue placeholder={riskLevel} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="low">Low</SelectItem>
                  <SelectItem value="medium">Medium</SelectItem>
                  <SelectItem value="high">High</SelectItem>
                  <SelectItem value="critical">Critical</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4 mb-4">
            <div>
              <label className="app-label">Likelihood</label>
              <Select onValueChange={(e) => { setLikelihood(e); setDirty(true); }}>
                <SelectTrigger id="hazard_likelihood" name="likelihood">
                  <SelectValue placeholder={likelihood || "—"} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="">—</SelectItem>
                  <SelectItem value="rare">Rare</SelectItem>
                  <SelectItem value="unlikely">Unlikely</SelectItem>
                  <SelectItem value="possible">Possible</SelectItem>
                  <SelectItem value="likely">Likely</SelectItem>
                  <SelectItem value="certain">Certain</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <label className="app-label">Severity</label>
              <Select onValueChange={(e) => { setSeverity(e); setDirty(true); }}>
                <SelectTrigger id="hazard_severity" name="severity">
                  <SelectValue placeholder={severity || "—"} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="">—</SelectItem>
                  <SelectItem value="negligible">Negligible</SelectItem>
                  <SelectItem value="minor">Minor</SelectItem>
                  <SelectItem value="major">Major</SelectItem>
                  <SelectItem value="hazardous">Hazardous</SelectItem>
                  <SelectItem value="catastrophic">Catastrophic</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="space-y-3 mb-4">
            <FormField htmlFor="hazard_mitigation" label="Initial mitigation" hint="Planned controls or immediate actions.">
              <textarea id="hazard_mitigation" name="mitigation" placeholder="Initial mitigation measures" value={mitigation} onChange={(e) => { setMitigation(e.target.value); setDirty(true); }} rows={2} />
            </FormField>
            <FormField htmlFor="hazard_owner" label="Owner ID" hint="Person responsible for tracking this hazard.">
              <Input id="hazard_owner" name="owner_id" placeholder="e.g. u-safety/security" value={ownerId} onChange={(e) => { setOwnerId(e.target.value); setDirty(true); }} />
            </FormField>
          </div>
          <Button
            disabled={!hazardIsValid || createMutation.isPending}
            onClick={() => createMutation.mutate({ title, description, category, risk_level: riskLevel, likelihood: likelihood || null, severity: severity || null, mitigation: mitigation || null, owner_id: ownerId || null })}
            variant="default"
            size="sm"
            className="w-full disabled:opacity-60"
          >
            {createMutation.isPending ? "Submitting…" : "Submit Hazard"}
          </Button>
        </div>
      )}

      <section className="app-surface overflow-hidden">
        <div className="flex flex-col gap-3 border-b border-kfl-border p-4 md:flex-row md:items-center md:justify-between">
          <div className="text-sm font-semibold text-kfl-text">Hazard Register</div>
          <div className="flex gap-2">
            <Select onValueChange={(e) => {
              const val = e;
              qc.setQueryData(["hazards"], (old: any[]) => val ? old.filter((h: any) => h.status === val) : old);
            }}>
              <SelectTrigger id="hazard_status_filter" name="status" aria-label="Filter by status">
                <SelectValue placeholder="All statuses" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="">All statuses</SelectItem>
                <SelectItem value="identified">Identified</SelectItem>
                <SelectItem value="assessed">Assessed</SelectItem>
                <SelectItem value="mitigated">Mitigated</SelectItem>
                <SelectItem value="closed">Closed</SelectItem>
              </SelectContent>
            </Select>
            <Select onValueChange={(e) => {
              const val = e;
              qc.setQueryData(["hazards"], (old: any[]) => val ? old.filter((h: any) => h.risk_level === val) : old);
            }}>
              <SelectTrigger id="hazard_risk_filter" name="risk_level" aria-label="Filter by risk level">
                <SelectValue placeholder="All risk levels" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="">All risk levels</SelectItem>
                <SelectItem value="low">Low</SelectItem>
                <SelectItem value="medium">Medium</SelectItem>
                <SelectItem value="high">High</SelectItem>
                <SelectItem value="critical">Critical</SelectItem>
              </SelectContent>
            </Select>
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
                    <td className="px-4 py-4"><Badge variant={h.risk_level === "critical" || h.risk_level === "high" ? "destructive" : h.risk_level === "medium" ? "secondary" : "default"} className={`badge ${h.risk_level === "critical" || h.risk_level === "high" ? "bg-kfl-status-danger-bg text-kfl-status-danger" : h.risk_level === "medium" ? "bg-kfl-status-warning-bg text-kfl-status-warning" : "bg-kfl-status-info-bg text-kfl-status-info"}`}>{h.risk_level}</Badge></td>
                    <td className="px-4 py-4"><Badge variant={h.status === "mitigated" || h.status === "closed" ? "default" : h.status === "assessed" ? "secondary" : "outline"} className={`badge ${h.status === "mitigated" || h.status === "closed" ? "bg-kfl-status-info-bg text-kfl-status-info" : h.status === "assessed" ? "bg-kfl-status-warning-bg text-kfl-status-warning" : "bg-kfl-status-info-bg text-kfl-status-info"}`}>{h.status}</Badge></td>
                    <td className="px-4 py-4 text-sm text-kfl-secondary">{h.owner_id || "—"}</td>
                    <td className="px-4 py-4 text-right text-sm">
                      <Select onValueChange={(e) => updateMutation.mutate({ id: h.hazard_id, data: { status: e } })}>
                        <SelectTrigger aria-label={`Update status for ${h.hazard_id}`} className="w-auto text-xs">
                          <SelectValue placeholder={h.status} />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="identified">Identified</SelectItem>
                          <SelectItem value="assessed">Assessed</SelectItem>
                          <SelectItem value="mitigated">Mitigated</SelectItem>
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
