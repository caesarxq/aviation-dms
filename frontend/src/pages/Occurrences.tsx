import { useMemo, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { safetyApi } from "../api/safety";
import { AlertTriangle, FileText } from "lucide-react";
import FormField from "../components/ui/FormField";
import { useValidation } from "../utils/validation";
import { useUnsavedChanges } from "../hooks/useUnsavedChanges";
import { useAuth } from "../auth/AuthContext";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select";

export function Occurrences() {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const { hasPermission } = useAuth();
  const { data: occurrences = [], isLoading, isError, refetch } = useQuery({
    queryKey: ["occurrences"],
    queryFn: () => safetyApi.listOccurrences(),
  });
  const [showForm, setShowForm] = useState(false);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [severity, setSeverity] = useState("minor");
  const [occurrenceType, setOccurrenceType] = useState("incident");
  const [dirty, setDirty] = useState(false);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [mutationError, setMutationError] = useState("");

  const filteredOccurrences = useMemo(() => occurrences.filter((occurrence: any) => {
    const query = search.trim().toLowerCase();
    const matchesSearch = !query || [occurrence.serial_number, occurrence.title, occurrence.location, occurrence.occurrence_type]
      .some((value) => String(value ?? "").toLowerCase().includes(query));
    return matchesSearch && (!statusFilter || occurrence.status === statusFilter);
  }), [occurrences, search, statusFilter]);

  const { errors: occFieldErrors, isValid: occIsValid } = useValidation(
    { title, description, severity, occurrence_type: occurrenceType },
    {
      title: { required: true, minLength: 2 },
      description: { required: true, minLength: 5 },
    }
  );

  useUnsavedChanges(showForm && dirty);

  const createMutation = useMutation({
    mutationFn: (data: any) => safetyApi.createOccurrence(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["occurrences"] });
      setShowForm(false);
      setDirty(false);
      setTitle("");
      setDescription("");
      setSeverity("minor");
      setOccurrenceType("incident");
      setMutationError("");
    },
    onError: () => setMutationError("Unable to submit the occurrence. Please try again."),
  });

  return (
    <div className="app-page">
      <header className="app-page-header">
        <div>
          <div className="app-eyebrow">Safety Management</div>
          <h1 className="app-title">Safety Occurrences</h1>
          <p className="app-subtitle">Report, track, and manage aviation safety occurrences.</p>
        </div>
        {hasPermission("safety:create") && <Button
          onClick={() => setShowForm(!showForm)}
          variant="default"
          size="sm"
        >
          <AlertTriangle size={16} /> {showForm ? "Cancel" : "Report Occurrence"}
        </Button>}
      </header>

      <section className="mb-5 grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="app-surface p-4">
          <div className="app-label">Total Occurrences</div>
          <div className="mt-2 text-2xl font-bold text-kfl-text">{occurrences.length}</div>
        </div>
        <div className="app-surface p-4">
          <div className="app-label">Critical / Hazardous</div>
          <div className="mt-2 text-2xl font-bold text-red-700">{occurrences.filter((o: any) => o.severity === "catastrophic" || o.severity === "hazardous").length}</div>
        </div>
        <div className="app-surface p-4">
          <div className="app-label">Open / Reported</div>
          <div className="mt-2 text-2xl font-bold text-amber-700">{occurrences.filter((o: any) => o.status === "reported").length}</div>
        </div>
      </section>

      <section className="app-surface overflow-hidden">
        <div className="flex flex-col gap-3 border-b border-kfl-border p-4 md:flex-row md:items-center md:justify-between">
          <div className="relative min-w-0 flex-1 md:max-w-md">
            <FileText size={16} className="pointer-events-none absolute left-3 top-3 text-kfl-muted" />
            <Input id="search_occurrences_74" name="search_occurrences" type="search" aria-label="Search occurrences" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search occurrences…" className="pl-9 relative z-10" />
          </div>
          <select id="select_field_76" name="status" aria-label="Filter occurrences by status" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="w-full md:w-auto">
            <option value="">All statuses</option>
            <option value="reported">Reported</option>
            <option value="acknowledged">Acknowledged</option>
            <option value="investigating">Investigating</option>
            <option value="closed">Closed</option>
          </select>
        </div>

        {showForm && (
          <div className="app-surface p-5 mb-5">
            <div className="mb-4 flex items-start justify-between gap-4">
              <div>
                <div className="app-label mb-1">New Safety Occurrence</div>
                <p className="text-xs text-kfl-muted">Report a safety occurrence for investigation.</p>
              </div>
              <Button variant="outline" size="sm" onClick={() => { setShowForm(false); setDirty(false); }}>
                Cancel
              </Button>
            </div>
            <div className="space-y-3 mb-4">
              <FormField htmlFor="title_94" label="Occurrence title" hint="Summarize the event clearly and concisely." required>
                <Input id="title_94" name="title" aria-describedby="title_94-error" aria-invalid={!!occFieldErrors.title} className={occFieldErrors.title ? "border-rose-400" : ""} placeholder="Occurrence title" value={title} onChange={(e) => { setTitle(e.target.value); setDirty(true); }} />
                {occFieldErrors.title && <p id="title_94-error" className="text-[11px] text-rose-700 mt-1">{occFieldErrors.title}</p>}
              </FormField>
              <FormField htmlFor="description_95" label="Description" hint="Include what happened, where, and any immediate action taken." required>
                <textarea id="description_95" name="description" aria-describedby="description_95-error" aria-invalid={!!occFieldErrors.description} className={occFieldErrors.description ? "border-rose-400" : ""} placeholder="Describe the occurrence" value={description} onChange={(e) => { setDescription(e.target.value); setDirty(true); }} rows={3} />
                {occFieldErrors.description && <p id="description_95-error" className="text-[11px] text-rose-700 mt-1">{occFieldErrors.description}</p>}
              </FormField>
            </div>
            {mutationError && <p role="alert" className="mb-3 rounded-md border border-kfl-status-danger-bg bg-kfl-status-danger-bg/20 text-kfl-status-danger p-3 text-sm">{mutationError}</p>}
            <div className="grid grid-cols-2 gap-4 mb-4">
              <div>
                <label className="app-label">Occurrence Type</label>
                <Select onValueChange={(e) => { setOccurrenceType(e); setDirty(true); }}>
                  <SelectTrigger id="occurrencetype_99" name="occurrencetype">
                    <SelectValue placeholder={occurrenceType} />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="incident">Incident</SelectItem>
                    <SelectItem value="accident">Accident</SelectItem>
                    <SelectItem value="serious_incident">Serious Incident</SelectItem>
                    <SelectItem value="near_miss">Near Miss</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div>
                <label className="app-label">Severity</label>
                <Select onValueChange={(e) => { setSeverity(e); setDirty(true); }}>
                  <SelectTrigger id="severity_108" name="severity">
                    <SelectValue placeholder={severity} />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="negligible">Negligible</SelectItem>
                    <SelectItem value="minor">Minor</SelectItem>
                    <SelectItem value="major">Major</SelectItem>
                    <SelectItem value="hazardous">Hazardous</SelectItem>
                    <SelectItem value="catastrophic">Catastrophic</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            <Button
              disabled={!occIsValid || createMutation.isPending}
              onClick={() => createMutation.mutate({ title, description, occurrence_type: occurrenceType, severity })}
              variant="default"
              size="sm"
              className="w-full disabled:opacity-60"
            >
              {createMutation.isPending ? "Submitting…" : "Submit Report"}
            </Button>
          </div>
        )}

        {isError ? (
          <div className="p-10 text-center" role="alert">
            <p className="text-sm font-semibold text-rose-800">Unable to load occurrences.</p>
            <Button variant="outline" size="sm" type="button" onClick={() => void refetch()} className="mt-3" aria-label="Retry loading occurrences">
              Retry
            </Button>
          </div>
        ) : isLoading ? (
          <div className="p-10 text-center text-sm text-kfl-muted">Loading occurrences…</div>
        ) : occurrences.length === 0 ? (
          <div className="app-surface border-dashed p-10 text-center">
            <AlertTriangle size={26} className="mx-auto mb-2 text-kfl-muted" />
            <p className="text-sm font-bold text-kfl-text">No occurrences reported.</p>
            <p className="mt-1 text-xs text-kfl-muted">Report your first occurrence to begin safety tracking.</p>
          </div>
        ) : filteredOccurrences.length === 0 ? (
          <div className="p-10 text-center text-sm text-kfl-muted">No occurrences match these filters.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full">
              <thead className="border-b border-kfl-border bg-kfl-surface-subtle">
                <tr>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Serial</th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Title</th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Type</th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Severity</th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Status</th>
                  <th className="px-4 py-3 text-right text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Open</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-kfl-border">
                {filteredOccurrences.map((o: any) => (
                  <tr key={o.occurrence_id} className="transition hover:bg-kfl-surface-subtle group">
                    <td className="px-4 py-4 font-mono text-[12px] text-kfl-text">{o.serial_number}</td>
                    <td className="px-4 py-4">
                      <div className="font-semibold text-kfl-text">{o.title}</div>
                      <div className="mt-1 text-xs text-kfl-muted">{o.location || "—"}</div>
                    </td>
                    <td className="px-4 py-4 text-sm text-kfl-secondary">{o.occurrence_type}</td>
                    <td className="px-4 py-4"><Badge variant={o.severity === "catastrophic" || o.severity === "hazardous" || o.severity === "major" ? "destructive" : o.severity === "minor" || o.severity === "negligible" ? "default" : "secondary"} className={`badge ${o.severity === "catastrophic" || o.severity === "hazardous" || o.severity === "major" ? "bg-kfl-status-danger-bg text-kfl-status-danger" : o.severity === "minor" || o.severity === "negligible" ? "bg-kfl-status-info-bg text-kfl-status-info" : "bg-kfl-status-warning-bg text-kfl-status-warning"}`}>{o.severity}</Badge></td>
                    <td className="px-4 py-4"><Badge variant="outline" className="badge">{o.status}</Badge></td>
                    <td className="px-4 py-4 text-right text-sm">
                      <button type="button" onClick={() => navigate(`/occurrences/${encodeURIComponent(o.occurrence_id)}`)} aria-label={`Open ${o.serial_number}`} className="text-xs font-medium text-kfl-blue hover:underline">Open</button>
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
