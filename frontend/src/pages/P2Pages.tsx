import { useMemo, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { p2Api } from "../api/p2";
import { Users, BarChart3, Calendar, Share2, Plus } from "lucide-react";
import { useToast } from "../components/ui/Toast";
import FormField from "../components/ui/FormField";
import { useValidation } from "../utils/validation";
import { useUnsavedChanges } from "../hooks/useUnsavedChanges";
import { useAuth } from "../auth/AuthContext";

function outsourcedStatusClass(status: string) {
  switch (status) {
    case "active": return "app-status app-status-healthy";
    case "inactive": return "app-status app-status-critical";
    case "pending": return "app-status app-status-info";
    default: return "app-status app-status-info";
  }
}

export function OutsourcedFunctions() {
  const qc = useQueryClient();
  const { toast } = useToast();
  const { hasPermission } = useAuth();
  const { data: items = [], isLoading } = useQuery({
    queryKey: ["outsourced-functions"],
    queryFn: () => p2Api.listOutsourcedFunctions(),
  });
  const [showForm, setShowForm] = useState(false);
  const [provider, setProvider] = useState("");
  const [scope, setScope] = useState("");
  const [ofError, setOfError] = useState("");
  const [dirty, setDirty] = useState(false);
  const [search, setSearch] = useState("");
  const filteredItems = useMemo(() => items.filter((item: any) => {
    const query = search.trim().toLowerCase();
    return !query || [item.provider_name, item.scope, item.status].some((value) => String(value ?? "").toLowerCase().includes(query));
  }), [items, search]);

  const { errors: ofFieldErrors, isValid: ofIsValid } = useValidation(
    { provider_name: provider, scope_of_work: scope },
    {
      provider_name: { required: true, minLength: 2 },
      scope_of_work: { required: true, minLength: 2 },
    }
  );

  useUnsavedChanges(showForm && dirty);

  const createMutation = useMutation({
    mutationFn: (data: any) => p2Api.createOutsourcedFunction(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["outsourced-functions"] });
      setShowForm(false);
      setDirty(false);
      setProvider("");
      setScope("");
      setOfError("");
      toast({ title: "Provider added", message: "Outsourced function recorded successfully.", type: "success" });
    },
    onError: () => {
      setOfError("Failed to add outsourced function. Please try again.");
    },
  });

  return (
    <div className="app-page">
      <header className="app-page-header">
        <div>
          <div className="app-eyebrow">P2 – Supporting Requirements</div>
          <h1 className="app-title">Outsourced Functions</h1>
          <p className="app-subtitle">Manage outsourced service providers and their scope of work.</p>
        </div>
        {hasPermission("safety:create") && <button
          onClick={() => setShowForm(!showForm)}
          className="app-btn-primary"
        >
          <Plus size={16} /> {showForm ? "Cancel" : "Add Provider"}
        </button>}
      </header>

      <section className="mb-5 grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="app-surface p-4">
          <div className="app-label">Total Providers</div>
          <div className="mt-2 text-2xl font-bold text-kfl-text">{items.length}</div>
        </div>
        <div className="app-surface p-4">
          <div className="app-label">Active</div>
          <div className="mt-2 text-2xl font-bold text-emerald-700">{items.filter((i: any) => i.status === "active").length}</div>
        </div>
      </section>

      <section className="app-surface overflow-hidden">
        <div className="flex flex-col gap-3 border-b border-kfl-border p-4 md:flex-row md:items-center md:justify-between">
          <div className="relative min-w-0 flex-1 md:max-w-md">
            <input id="search_providers_73" name="search_providers" type="search" aria-label="Search providers" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search providers…" className="app-input pl-9 relative z-10" />
          </div>
        </div>

        {showForm && (
          <div className="app-surface p-5 mb-5">
            <div className="mb-4 flex items-start justify-between gap-4">
              <div>
                <div className="app-label mb-1">New Outsourced Function</div>
                <p className="text-xs text-kfl-muted">Register an external service provider.</p>
              </div>
              <button onClick={() => { setShowForm(false); setDirty(false); }} className="app-btn-secondary px-3 py-2">Cancel</button>
            </div>
            {ofError && (
              <div className="mb-3 p-3 rounded bg-rose-50/60 border border-rose-200 text-rose-800 text-sm">
                {ofError}
              </div>
            )}
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <FormField htmlFor="provider_name_94" label="Provider name" hint="Use the legal or trading name of the external provider." required>
                <input id="provider_name_94" name="provider_name" aria-describedby="provider_name_94-error" aria-invalid={!!ofFieldErrors.provider_name} className={`app-input ${ofFieldErrors.provider_name ? "border-rose-400" : ""}`} placeholder="Provider name" value={provider} onChange={(e) => { setProvider(e.target.value); setDirty(true); }} />
                {ofFieldErrors.provider_name && <p id="provider_name_94-error" className="text-[11px] text-rose-700 mt-1">{ofFieldErrors.provider_name}</p>}
              </FormField>
              <FormField htmlFor="scope_of_work_98" label="Scope of work" hint="Describe the service being outsourced." required>
                <input id="scope_of_work_98" name="scope_of_work" aria-describedby="scope_of_work_98-error" aria-invalid={!!ofFieldErrors.scope_of_work} className={`app-input ${ofFieldErrors.scope_of_work ? "border-rose-400" : ""}`} placeholder="Scope of work" value={scope} onChange={(e) => { setScope(e.target.value); setDirty(true); }} />
                {ofFieldErrors.scope_of_work && <p id="scope_of_work_98-error" className="text-[11px] text-rose-700 mt-1">{ofFieldErrors.scope_of_work}</p>}
              </FormField>
            </div>
            <button
              disabled={!ofIsValid || createMutation.isPending}
              onClick={() => {
                setOfError("");
                if (!provider.trim() || !scope.trim()) {
                  setOfError("Please complete all required fields.");
                  return;
                }
                createMutation.mutate({ provider_name: provider, scope });
              }}
              className="app-btn-primary w-full"
            >
              {createMutation.isPending ? "Creating…" : "Create Provider"}
            </button>
          </div>
        )}

        {isLoading ? (
          <div className="p-10 text-center text-sm text-kfl-muted">Loading providers…</div>
        ) : items.length === 0 ? (
          <div className="app-surface border-dashed p-10 text-center">
            <Users size={26} className="mx-auto mb-2 text-kfl-muted" />
            <p className="text-sm font-bold text-kfl-text">No outsourced functions.</p>
            <p className="mt-1 text-xs text-kfl-muted">Register your first service provider.</p>
          </div>
        ) : filteredItems.length === 0 ? (
          <div className="p-10 text-center text-sm text-kfl-muted">No outsourced functions match these filters.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full">
              <thead className="border-b border-kfl-border bg-kfl-surface-subtle">
                <tr>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Provider</th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Scope</th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-kfl-border">
                {filteredItems.map((i: any) => (
                  <tr key={i.function_id} className="transition hover:bg-kfl-surface-subtle">
                    <td className="px-4 py-4 text-sm font-medium text-kfl-text">{i.provider_name}</td>
                    <td className="px-4 py-4 text-sm text-kfl-secondary">{i.scope}</td>
                    <td className="px-4 py-4">
                      <span className={outsourcedStatusClass(i.status)}>{i.status}</span>
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

export function SafetyKPIs() {
  const qc = useQueryClient();
  const { toast } = useToast();
  const { hasPermission } = useAuth();
  const { data: items = [], isLoading } = useQuery({
    queryKey: ["safety-kpis"],
    queryFn: () => p2Api.listSafetyKPIs(),
  });
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [target, setTarget] = useState("");
  const [kpiError, setKpiError] = useState("");
  const [dirty, setDirty] = useState(false);
  const [search, setSearch] = useState("");
  const filteredItems = useMemo(() => items.filter((item: any) => {
    const query = search.trim().toLowerCase();
    return !query || [item.kpi_name, item.target, item.status].some((value) => String(value ?? "").toLowerCase().includes(query));
  }), [items, search]);

  const { errors: kpiFieldErrors, isValid: kpiIsValid } = useValidation(
    { kpi_name: name },
    {
      kpi_name: { required: true, minLength: 2 },
    }
  );

  useUnsavedChanges(showForm && dirty);

  const createMutation = useMutation({
    mutationFn: (data: any) => p2Api.createSafetyKPI(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["safety-kpis"] });
      setShowForm(false);
      setDirty(false);
      setName("");
      setTarget("");
      setKpiError("");
      toast({ title: "KPI added", message: "Safety KPI recorded successfully.", type: "success" });
    },
    onError: () => {
      setKpiError("Failed to add KPI. Please try again.");
    },
  });

  return (
    <div className="app-page">
      <header className="app-page-header">
        <div>
          <div className="app-eyebrow">P2 – Supporting Requirements</div>
          <h1 className="app-title">Safety KPIs</h1>
          <p className="app-subtitle">Monitor key safety performance indicators and targets.</p>
        </div>
        {hasPermission("safety:create") && <button
          onClick={() => setShowForm(!showForm)}
          className="app-btn-primary"
        >
          <BarChart3 size={16} /> {showForm ? "Cancel" : "Add KPI"}
        </button>}
      </header>

      <section className="mb-5 grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="app-surface p-4">
          <div className="app-label">Total KPIs</div>
          <div className="mt-2 text-2xl font-bold text-kfl-text">{items.length}</div>
        </div>
      </section>

      <section className="app-surface overflow-hidden">
        <div className="flex flex-col gap-3 border-b border-kfl-border p-4 md:flex-row md:items-center md:justify-between">
          <div className="relative min-w-0 flex-1 md:max-w-md">
            <input id="search_kpis_208" name="search_kpis" type="search" aria-label="Search KPIs" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search KPIs…" className="app-input pl-9 relative z-10" />
          </div>
        </div>

        {showForm && (
          <div className="app-surface p-5 mb-5">
            <div className="mb-4 flex items-start justify-between gap-4">
              <div>
                <div className="app-label mb-1">New Safety KPI</div>
                <p className="text-xs text-kfl-muted">Define a safety performance indicator.</p>
              </div>
              <button onClick={() => { setShowForm(false); setDirty(false); }} className="app-btn-secondary px-3 py-2">Cancel</button>
            </div>
            {kpiError && (
              <div className="mb-3 p-3 rounded bg-rose-50/60 border border-rose-200 text-rose-800 text-sm">
                {kpiError}
              </div>
            )}
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <FormField htmlFor="kpi_name_229" label="KPI name" hint="Name the safety performance measure." required>
                <input id="kpi_name_229" name="kpi_name" aria-describedby="kpi_name_229-error" aria-invalid={!!kpiFieldErrors.kpi_name} className={`app-input ${kpiFieldErrors.kpi_name ? "border-rose-400" : ""}`} placeholder="KPI name" value={name} onChange={(e) => { setName(e.target.value); setDirty(true); }} />
                {kpiFieldErrors.kpi_name && <p id="kpi_name_229-error" className="text-[11px] text-rose-700 mt-1">{kpiFieldErrors.kpi_name}</p>}
              </FormField>
              <FormField htmlFor="target_value_233" label="Target value" hint="Include the unit or threshold in the target description.">
                <input id="target_value_233" name="target_value" className="app-input" placeholder="Target value" value={target} onChange={(e) => { setTarget(e.target.value); setDirty(true); }} />
              </FormField>
            </div>
            <button
              disabled={!kpiIsValid || createMutation.isPending}
              onClick={() => {
                setKpiError("");
                if (!name.trim()) {
                  setKpiError("KPI name is required.");
                  return;
                }
                createMutation.mutate({ kpi_name: name, target });
              }}
              className="app-btn-primary w-full"
            >
              {createMutation.isPending ? "Creating…" : "Create KPI"}
            </button>
          </div>
        )}

        {isLoading ? (
          <div className="p-10 text-center text-sm text-kfl-muted">Loading KPIs…</div>
        ) : items.length === 0 ? (
          <div className="app-surface border-dashed p-10 text-center">
            <BarChart3 size={26} className="mx-auto mb-2 text-kfl-muted" />
            <p className="text-sm font-bold text-kfl-text">No safety KPIs.</p>
            <p className="mt-1 text-xs text-kfl-muted">Create your first KPI to monitor safety performance.</p>
          </div>
        ) : filteredItems.length === 0 ? (
          <div className="p-10 text-center text-sm text-kfl-muted">No safety KPIs match these filters.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full">
              <thead className="border-b border-kfl-border bg-kfl-surface-subtle">
                <tr>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">KPI</th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Target</th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-kfl-border">
                {filteredItems.map((i: any) => (
                  <tr key={i.kpi_id} className="transition hover:bg-kfl-surface-subtle">
                    <td className="px-4 py-4 text-sm font-medium text-kfl-text">{i.kpi_name}</td>
                    <td className="px-4 py-4 text-sm text-kfl-secondary">{i.target}</td>
                    <td className="px-4 py-4 text-sm text-kfl-secondary">{i.status}</td>
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

export function SecurityReviews() {
  const qc = useQueryClient();
  const { toast } = useToast();
  const { hasPermission } = useAuth();
  const { data: items = [], isLoading } = useQuery({
    queryKey: ["security-reviews"],
    queryFn: () => p2Api.listSecurityReviews(),
  });
  const [showForm, setShowForm] = useState(false);
  const [date, setDate] = useState("");
  const [srError, setSrError] = useState("");
  const [dirty, setDirty] = useState(false);
  const [search, setSearch] = useState("");
  const filteredItems = useMemo(() => items.filter((item: any) => {
    const query = search.trim().toLowerCase();
    return !query || [item.meeting_date, item.attendees, item.minutes, item.status].some((value) => String(value ?? "").toLowerCase().includes(query));
  }), [items, search]);

  const { errors: srFieldErrors, isValid: srIsValid } = useValidation(
    { meeting_date: date },
    {
      meeting_date: { required: true },
    }
  );

  useUnsavedChanges(showForm && dirty);

  const createMutation = useMutation({
    mutationFn: (data: any) => p2Api.createSecurityReview(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["security-reviews"] });
      setShowForm(false);
      setDirty(false);
      setDate("");
      setSrError("");
      toast({ title: "Review scheduled", message: "Security review meeting recorded successfully.", type: "success" });
    },
    onError: () => {
      setSrError("Failed to schedule review. Please try again.");
    },
  });

  return (
    <div className="app-page">
      <header className="app-page-header">
        <div>
          <div className="app-eyebrow">P2 – Supporting Requirements</div>
          <h1 className="app-title">Security Review Meetings</h1>
          <p className="app-subtitle">Schedule and track security review meetings.</p>
        </div>
        {hasPermission("safety:create") && <button
          onClick={() => setShowForm(!showForm)}
          className="app-btn-primary"
        >
          <Calendar size={16} /> {showForm ? "Cancel" : "Schedule Review"}
        </button>}
      </header>

      <section className="mb-5 grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="app-surface p-4">
          <div className="app-label">Total Reviews</div>
          <div className="mt-2 text-2xl font-bold text-kfl-text">{items.length}</div>
        </div>
      </section>

      <section className="app-surface overflow-hidden">
        <div className="flex flex-col gap-3 border-b border-kfl-border p-4 md:flex-row md:items-center md:justify-between">
          <div className="relative min-w-0 flex-1 md:max-w-md">
            <input id="search_reviews_339" name="search_reviews" type="search" aria-label="Search reviews" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search reviews…" className="app-input pl-9 relative z-10" />
          </div>
        </div>

        {showForm && (
          <div className="app-surface p-5 mb-5">
            <div className="mb-4 flex items-start justify-between gap-4">
              <div>
                <div className="app-label mb-1">Schedule Security Review</div>
                <p className="text-xs text-kfl-muted">Create a security review meeting record.</p>
              </div>
              <button onClick={() => { setShowForm(false); setDirty(false); }} className="app-btn-secondary px-3 py-2">Cancel</button>
            </div>
            {srError && (
              <div className="mb-3 p-3 rounded bg-rose-50/60 border border-rose-200 text-rose-800 text-sm">
                {srError}
              </div>
            )}
            <FormField htmlFor="date_357" label="Meeting date" required>
              <input id="date_357" name="date" aria-describedby="date_357-error" aria-invalid={!!srFieldErrors.meeting_date} type="date" className={`app-input mb-3 ${srFieldErrors.meeting_date ? "border-rose-400" : ""}`} value={date} onChange={(e) => { setDate(e.target.value); setDirty(true); }} />
              {srFieldErrors.meeting_date && <p id="date_357-error" className="text-[11px] text-rose-700 mt-1">{srFieldErrors.meeting_date}</p>}
            </FormField>
            <button
              disabled={!srIsValid || createMutation.isPending}
              onClick={() => {
                setSrError("");
                if (!date) {
                  setSrError("Meeting date is required.");
                  return;
                }
                createMutation.mutate({ meeting_date: date });
              }}
              className="app-btn-primary w-full"
            >
              {createMutation.isPending ? "Scheduling…" : "Schedule Review"}
            </button>
          </div>
        )}

        {isLoading ? (
          <div className="p-10 text-center text-sm text-kfl-muted">Loading reviews…</div>
        ) : items.length === 0 ? (
          <div className="app-surface border-dashed p-10 text-center">
            <Calendar size={26} className="mx-auto mb-2 text-kfl-muted" />
            <p className="text-sm font-bold text-kfl-text">No security reviews.</p>
            <p className="mt-1 text-xs text-kfl-muted">Schedule your first security review meeting.</p>
          </div>
        ) : filteredItems.length === 0 ? (
          <div className="p-10 text-center text-sm text-kfl-muted">No security reviews match these filters.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full">
              <thead className="border-b border-kfl-border bg-kfl-surface-subtle">
                <tr>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Meeting Date</th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Status</th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Attendees</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-kfl-border">
                {filteredItems.map((i: any) => (
                  <tr key={i.review_id} className="transition hover:bg-kfl-surface-subtle">
                    <td className="px-4 py-4 text-sm font-medium text-kfl-text">{i.meeting_date}</td>
                    <td className="px-4 py-4 text-sm text-kfl-secondary">{i.status}</td>
                    <td className="px-4 py-4 text-sm text-kfl-secondary">{i.attendees || "—"}</td>
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

export function DGResponsibilityMatrix() {
  const qc = useQueryClient();
  const { toast } = useToast();
  const { hasPermission } = useAuth();
  const { data: items = [], isLoading } = useQuery({
    queryKey: ["dg-matrix"],
    queryFn: () => p2Api.listDGMatrix(),
  });
  const [showForm, setShowForm] = useState(false);
  const [project, setProject] = useState("");
  const [stage, setStage] = useState("");
  const [role, setRole] = useState("");
  const [dgError, setDgError] = useState("");
  const [dirty, setDirty] = useState(false);
  const [search, setSearch] = useState("");
  const filteredItems = useMemo(() => items.filter((item: any) => {
    const query = search.trim().toLowerCase();
    return !query || [item.project_or_route, item.process_stage, item.responsible_role, item.operation_type, item.status].some((value) => String(value ?? "").toLowerCase().includes(query));
  }), [items, search]);

  const { errors: dgFieldErrors, isValid: dgIsValid } = useValidation(
    { project_or_route: project, process_stage: stage, responsible_role: role },
    {
      project_or_route: { required: true, minLength: 2 },
    }
  );

  useUnsavedChanges(showForm && dirty);

  const createMutation = useMutation({
    mutationFn: (data: any) => p2Api.createDGMatrix(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["dg-matrix"] });
      setShowForm(false);
      setDirty(false);
      setProject("");
      setStage("");
      setRole("");
      setDgError("");
      toast({ title: "Entry added", message: "DG responsibility entry recorded successfully.", type: "success" });
    },
    onError: () => {
      setDgError("Failed to add entry. Please try again.");
    },
  });

  return (
    <div className="app-page">
      <header className="app-page-header">
        <div>
          <div className="app-eyebrow">P2 – Supporting Requirements</div>
          <h1 className="app-title">DG Responsibility Matrix</h1>
          <p className="app-subtitle">Assign DG responsibilities across projects and routes.</p>
        </div>
        {hasPermission("safety:create") && <button
          onClick={() => setShowForm(!showForm)}
          className="app-btn-primary"
        >
          <Share2 size={16} /> {showForm ? "Cancel" : "Add Entry"}
        </button>}
      </header>

      <section className="mb-5 grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="app-surface p-4">
          <div className="app-label">Total Entries</div>
          <div className="mt-2 text-2xl font-bold text-kfl-text">{items.length}</div>
        </div>
      </section>

      <section className="app-surface overflow-hidden">
        <div className="flex flex-col gap-3 border-b border-kfl-border p-4 md:flex-row md:items-center md:justify-between">
          <div className="relative min-w-0 flex-1 md:max-w-md">
            <input id="search_matrix_entries_465" name="search_matrix_entries" type="search" aria-label="Search matrix entries" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search matrix entries…" className="app-input pl-9 relative z-10" />
          </div>
        </div>

        {showForm && (
          <div className="app-surface p-5 mb-5">
            <div className="mb-4 flex items-start justify-between gap-4">
              <div>
                <div className="app-label mb-1">New DG Responsibility Entry</div>
                <p className="text-xs text-kfl-muted">Assign DG responsibility for a project or route.</p>
              </div>
              <button onClick={() => { setShowForm(false); setDirty(false); }} className="app-btn-secondary px-3 py-2">Cancel</button>
            </div>
            {dgError && (
              <div className="mb-3 p-3 rounded bg-rose-50/60 border border-rose-200 text-rose-800 text-sm">
                {dgError}
              </div>
            )}
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              <FormField htmlFor="project_or_route_486" label="Project or route" hint="Identify the operation or route covered." required>
                <input id="project_or_route_486" name="project_or_route" aria-describedby="project_or_route_486-error" aria-invalid={!!dgFieldErrors.project_or_route} className={`app-input ${dgFieldErrors.project_or_route ? "border-rose-400" : ""}`} placeholder="Project or route" value={project} onChange={(e) => { setProject(e.target.value); setDirty(true); }} />
                {dgFieldErrors.project_or_route && <p id="project_or_route_486-error" className="text-[11px] text-rose-700 mt-1">{dgFieldErrors.project_or_route}</p>}
              </FormField>
              <FormField htmlFor="process_stage_490" label="Process stage" hint="Name the stage where DG responsibility applies.">
                <input id="process_stage_490" name="process_stage" className="app-input" placeholder="Process stage" value={stage} onChange={(e) => { setStage(e.target.value); setDirty(true); }} />
              </FormField>
              <FormField htmlFor="responsible_role_494" label="Responsible role" hint="Use the accountable post or role, not a password or secret.">
                <input id="responsible_role_494" name="responsible_role" className="app-input" placeholder="Responsible role" value={role} onChange={(e) => { setRole(e.target.value); setDirty(true); }} />
              </FormField>
            </div>
            <button
              disabled={!dgIsValid || createMutation.isPending}
              onClick={() => {
                setDgError("");
                if (!project.trim()) {
                  setDgError("Project / Route is required.");
                  return;
                }
                createMutation.mutate({ project_or_route: project, process_stage: stage, responsible_role: role });
              }}
              className="app-btn-primary w-full"
            >
              {createMutation.isPending ? "Creating…" : "Create Entry"}
            </button>
          </div>
        )}

        {isLoading ? (
          <div className="p-10 text-center text-sm text-kfl-muted">Loading matrix entries…</div>
        ) : items.length === 0 ? (
          <div className="app-surface border-dashed p-10 text-center">
            <Share2 size={26} className="mx-auto mb-2 text-kfl-muted" />
            <p className="text-sm font-bold text-kfl-text">No DG responsibility entries.</p>
            <p className="mt-1 text-xs text-kfl-muted">Add a matrix entry to assign operational responsibilities.</p>
          </div>
        ) : filteredItems.length === 0 ? (
          <div className="p-10 text-center text-sm text-kfl-muted">No matrix entries match these filters.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full">
              <thead className="border-b border-kfl-border bg-kfl-surface-subtle">
                <tr>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Project / Route</th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Process Stage</th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Responsible Role</th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-kfl-border">
                {filteredItems.map((i: any) => (
                  <tr key={i.matrix_id} className="transition hover:bg-kfl-surface-subtle">
                    <td className="px-4 py-4 text-sm font-medium text-kfl-text">{i.project_or_route}</td>
                    <td className="px-4 py-4 text-sm text-kfl-secondary">{i.process_stage}</td>
                    <td className="px-4 py-4 text-sm text-kfl-secondary">{i.responsible_role}</td>
                    <td className="px-4 py-4 text-sm text-kfl-secondary">{i.status}</td>
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