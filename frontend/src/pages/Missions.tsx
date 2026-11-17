import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "../api/client";
import { Plus } from "lucide-react";
import { useToast } from "../components/ui/Toast";
import FormField from "../components/ui/FormField";
import { useValidation } from "../utils/validation";
import { useUnsavedChanges } from "../hooks/useUnsavedChanges";
import { useAuth } from "../auth/AuthContext";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";

const STATUS_ACTIONS: Record<string, { label: string; state: string; tone: "blue" | "green" | "red" }[]> = {
  planned: [
    { label: "Cancel", state: "cancelled", tone: "red" },
  ],
  released: [
    { label: "Start", state: "in_progress", tone: "green" },
    { label: "Abort", state: "aborted", tone: "red" },
  ],
  in_progress: [
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

function getErrorMessage(error: unknown, fallback: string): string {
  const detail = (error as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
  return typeof detail === "string" ? detail : fallback;
}

export function Missions() {
  const qc = useQueryClient();
  const { toast } = useToast();
  const { hasPermission } = useAuth();
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [page, setPage] = useState(0);
  const pageSize = 50;
  const trimmedSearch = search.trim();
  const { data: missions = [], isLoading, isError, refetch } = useQuery({
    queryKey: ["missions", trimmedSearch, statusFilter, page],
    queryFn: () => api.get("/p1/missions", {
      params: {
        ...(trimmedSearch ? { search: trimmedSearch } : {}),
        ...(statusFilter ? { status: statusFilter } : {}),
        limit: pageSize,
        offset: page * pageSize,
      },
    }).then((r: any) => r.data),
  });
  const { data: missionSummary, isLoading: summaryLoading, isError: summaryError, refetch: refetchSummary } = useQuery({
    queryKey: ["mission-summary"],
    queryFn: () => api.get("/p1/missions/summary").then((r: any) => r.data),
  });
  const [showForm, setShowForm] = useState(false);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [missionType, setMissionType] = useState("survey");
  const [priority, setPriority] = useState("normal");
  const [plannedDate, setPlannedDate] = useState("");
  const [location, setLocation] = useState("");
  const [missionError, setMissionError] = useState("");
  const [dirty, setDirty] = useState(false);

  const { errors: missionFieldErrors, isValid: missionIsValid } = useValidation(
    { title, mission_type: missionType, priority },
    {
      title: { required: true, minLength: 2 },
      mission_type: { required: true, minLength: 2 },
      priority: { required: true, minLength: 2 },
    }
  );

  useUnsavedChanges(showForm && dirty);

  const createMutation = useMutation({
    mutationFn: (data: any) => api.post("/p1/missions", data).then((r: any) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["missions"] });
      qc.invalidateQueries({ queryKey: ["mission-summary"] });
      setShowForm(false);
      setDirty(false);
      setTitle("");
      setDescription("");
      setMissionType("survey");
      setPriority("normal");
      setPlannedDate("");
      setLocation("");
      setMissionError("");
      toast({ title: "Mission created", message: "The new mission has been added to the register.", type: "success" });
    },
    onError: (error: unknown) => {
      setMissionError(getErrorMessage(error, "Failed to create mission. Please try again."));
    },
  });

  const transitionMutation = useMutation({
    mutationFn: ({ id, state }: { id: string; state: string }) =>
      api.patch(`/p1/missions/${id}/state?state=${state}`).then((r: any) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["missions"] });
      qc.invalidateQueries({ queryKey: ["mission-summary"] });
    },
    onError: (error: unknown) => {
      toast({ title: "Mission transition not recorded", message: getErrorMessage(error, "Reload the mission and retry."), type: "error" });
    },
  });

  return (
    <div className="app-page">
      <header className="app-page-header">
        <div>
          <div className="app-eyebrow">Flight Operations</div>
          <h1 className="app-title">Missions</h1>
          <p className="app-subtitle">Create planned mission records and track their lifecycle. Mission creation does not authorize flight.</p>
        </div>
        {hasPermission("safety:create") && <Button
          type="button"
          onClick={() => { setShowForm(!showForm); setMissionError(""); }}
          variant="default"
          size="sm"
        >
          <Plus size={16} /> {showForm ? "Cancel" : "New Mission"}
        </Button>}
      </header>

      {summaryError && <div role="alert" className="mb-4 rounded-md border border-kfl-status-danger-bg bg-kfl-status-danger-bg/20 text-kfl-status-danger p-3 text-sm">Unable to load mission metrics. <button type="button" className="font-semibold underline text-kfl-text" onClick={() => void refetchSummary()}>Retry mission metrics</button></div>}
      <section className="mb-5 grid grid-cols-1 gap-4 sm:grid-cols-4">
        <div className="app-surface p-4">
          <div className="app-label">Total Missions</div>
          <div className="mt-2 text-2xl font-bold text-kfl-text">{summaryLoading ? "…" : summaryError ? "—" : missionSummary?.total ?? "—"}</div>
        </div>
        <div className="app-surface p-4">
          <div className="app-label">Planned</div>
          <div className="mt-2 text-2xl font-bold text-kfl-blue">{summaryLoading ? "…" : summaryError ? "—" : missionSummary?.planned ?? "—"}</div>
        </div>
        <div className="app-surface p-4">
          <div className="app-label">In Progress</div>
          <div className="mt-2 text-2xl font-bold text-kfl-blue">{summaryLoading ? "…" : summaryError ? "—" : missionSummary?.in_progress ?? "—"}</div>
        </div>
        <div className="app-surface p-4">
          <div className="app-label">Completed</div>
          <div className="mt-2 text-2xl font-bold text-emerald-700">{summaryLoading ? "…" : summaryError ? "—" : missionSummary?.completed ?? "—"}</div>
        </div>
      </section>

      <section className="app-surface overflow-hidden">
        <div className="flex flex-col gap-3 border-b border-kfl-border p-4 md:flex-row md:items-center md:justify-between">
          <div className="relative min-w-0 flex-1 md:max-w-md">
            <Input id="search_missions_112" name="search_missions" type="search" aria-label="Search missions" value={search} onChange={(e) => { setPage(0); setSearch(e.target.value); }} placeholder="Search missions…" className="pl-9 relative z-10" />
          </div>
          <select id="select_field_114" name="status" aria-label="Filter missions by status" value={statusFilter} onChange={(e) => { setPage(0); setStatusFilter(e.target.value); }} className="w-full md:w-auto">
            <option value="">All statuses</option>
            <option value="planned">Planned</option>
            <option value="released">Released</option>
            <option value="in_progress">In Progress</option>
            <option value="completed">Completed</option>
            <option value="cancelled">Cancelled</option>
            <option value="aborted">Aborted</option>
          </select>
        </div>

        {showForm && (
          <div className="app-surface p-5 mb-5">
            <div className="mb-4 flex items-start justify-between gap-4">
              <div>
                <div className="app-label mb-1">New Mission</div>
                <p className="text-xs text-kfl-muted">Enter the planning context. Use values confirmed by the current operational procedure.</p>
              </div>
              <Button type="button" onClick={() => { setShowForm(false); setDirty(false); setMissionError(""); }} variant="outline" size="sm">
                Cancel
              </Button>
            </div>
            <div className="mb-3 rounded-md border border-kfl-status-warning-bg bg-kfl-status-warning-bg/20 text-kfl-status-warning p-3 text-sm">
              Creating a planned mission does not authorize flight. Release requires the separately approved flight plan, linked approved risk assessment, and release evidence.
            </div>
            {missionError && (
              <div role="alert" className="mb-3 p-3 rounded-md border border-kfl-status-danger-bg bg-kfl-status-danger-bg/20 text-kfl-status-danger text-sm">
                {missionError}
              </div>
            )}
            <FormField htmlFor="mission_title_137" label="Mission title" hint="Use the operational mission name or reference." required>
              <Input id="mission_title_137" name="mission_title" aria-describedby="mission_title_137-error" aria-invalid={!!missionFieldErrors.title} className={missionFieldErrors.title ? "border-rose-400" : ""} placeholder="Mission title" value={title} onChange={(e) => { setTitle(e.target.value); setDirty(true); }} />
              {missionFieldErrors.title && <p id="mission_title_137-error" className="text-[11px] text-rose-700 mt-1">{missionFieldErrors.title}</p>}
            </FormField>
            <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-2">
              <FormField htmlFor="mission_type" label="Mission type" hint="Use the exact type label in the applicable local procedure." required>
                <Input id="mission_type" name="mission_type" aria-invalid={!!missionFieldErrors.mission_type} className={missionFieldErrors.mission_type ? "border-rose-400" : ""} value={missionType} onChange={(e) => { setMissionType(e.target.value); setDirty(true); }} />
                {missionFieldErrors.mission_type && <p className="mt-1 text-[11px] text-rose-700">{missionFieldErrors.mission_type}</p>}
              </FormField>
              <FormField htmlFor="mission_priority" label="Priority" hint="Use the approved local priority scale." required>
                <Input id="mission_priority" name="priority" aria-invalid={!!missionFieldErrors.priority} className={missionFieldErrors.priority ? "border-rose-400" : ""} value={priority} onChange={(e) => { setPriority(e.target.value); setDirty(true); }} />
                {missionFieldErrors.priority && <p className="mt-1 text-[11px] text-rose-700">{missionFieldErrors.priority}</p>}
              </FormField>
              <FormField htmlFor="mission_planned_date" label="Planned date">
                <Input id="mission_planned_date" name="planned_date" type="date" value={plannedDate} onChange={(e) => { setPlannedDate(e.target.value); setDirty(true); }} />
              </FormField>
              <FormField htmlFor="mission_location" label="Location">
                <Input id="mission_location" name="location" value={location} onChange={(e) => { setLocation(e.target.value); setDirty(true); }} />
              </FormField>
              <FormField htmlFor="mission_description" label="Description" className="md:col-span-2">
                <textarea id="mission_description" name="description" rows={3} value={description} onChange={(e) => { setDescription(e.target.value); setDirty(true); }} className="flex-1 min-h-[80px]" />
              </FormField>
            </div>
            <Button
              type="button"
              disabled={!missionIsValid || createMutation.isPending}
              onClick={() => {
                setMissionError("");
                createMutation.mutate({
                  title: title.trim(),
                  description: description.trim() || null,
                  mission_type: missionType.trim(),
                  priority: priority.trim(),
                  planned_date: plannedDate || null,
                  location: location.trim() || null,
                });
              }}
              variant="default"
              size="sm"
              className="w-full disabled:opacity-60"
            >
              {createMutation.isPending ? "Creating…" : "Create Mission"}
            </Button>
          </div>
        )}

        {isLoading ? (
          <div className="p-10 text-center text-sm text-kfl-muted">Loading missions…</div>
        ) : isError ? (
          <div className="p-10 text-center" role="alert">
            <p className="text-sm font-semibold text-rose-800">Unable to load missions.</p>
            <Button variant="outline" size="sm" type="button" onClick={() => void refetch()} className="mt-3">
              Retry missions
            </Button>
          </div>
        ) : missions.length === 0 && page === 0 && !trimmedSearch && !statusFilter ? (
          <div className="app-surface border-dashed p-10 text-center">
            <Plus size={26} className="mx-auto mb-2 text-kfl-muted" />
            <p className="text-sm font-bold text-kfl-text">No missions found.</p>
            <p className="mt-1 text-xs text-kfl-muted">Create your first mission to begin tracking flight operations.</p>
          </div>
        ) : missions.length === 0 ? (
          <div className="p-10 text-center text-sm text-kfl-muted">
            <p>{page > 0 ? "No missions on this page." : "No missions match these filters."}</p>
            {page > 0 && <Button variant="outline" size="sm" type="button" disabled={isLoading} onClick={() => setPage((current) => current - 1)}>Previous page</Button>}
          </div>
        ) : (
          <>
          <div className="overflow-x-auto">
            <table className="min-w-full">
              <thead className="border-b border-kfl-border bg-kfl-surface-subtle">
                <tr>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">ID</th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Title</th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Type</th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Status</th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Priority</th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Risk assessment</th>
                  <th className="px-4 py-3 text-right text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-kfl-border">
                {missions.map((m: any) => (
                  <tr key={m.mission_id} className="transition hover:bg-kfl-surface-subtle group">
                    <td className="px-4 py-4 font-mono text-[12px] text-kfl-text">{m.mission_id}</td>
                    <td className="px-4 py-4">
                      <div className="font-semibold text-kfl-text">{m.title}</div>
                      <div className="mt-1 text-xs text-kfl-muted">{m.planned_date || "Date not set"}</div>
                    </td>
                    <td className="px-4 py-4 text-sm text-kfl-secondary">{m.mission_type}</td>
                    <td className="px-4 py-4"><Badge variant={m.status === "completed" ? "default" : m.status === "in_progress" || m.status === "released" ? "secondary" : m.status === "cancelled" || m.status === "aborted" ? "destructive" : "outline"} className={`badge ${m.status === "completed" ? "bg-kfl-status-info-bg text-kfl-status-info" : m.status === "in_progress" || m.status === "released" ? "bg-kfl-status-warning-bg text-kfl-status-warning" : m.status === "cancelled" || m.status === "aborted" ? "bg-kfl-status-danger-bg text-kfl-status-danger" : "bg-kfl-status-info-bg text-kfl-status-info"}`}>{m.status}</Badge></td>
                    <td className="px-4 py-4 text-sm text-kfl-secondary">{m.priority}</td>
                    <td className="px-4 py-4 text-sm text-kfl-secondary">{m.risk_assessment_id || "Not linked"}</td>
                    <td className="px-4 py-4 text-right text-sm">
                      {hasPermission("safety:update") && availableActions(m.status)
                        .filter((action) => action.state !== "aborted" || hasPermission("safety:close"))
                        .map((a) => (
                          <button
                            key={a.state}
                            type="button"
                            disabled={transitionMutation.isPending}
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
          <div className="flex items-center justify-between border-t border-kfl-border p-4">
            <span className="text-sm text-kfl-muted">Page {page + 1}</span>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" type="button" disabled={page === 0 || isLoading} onClick={() => setPage((current) => current - 1)}>
                Previous page
              </Button>
              <Button variant="outline" size="sm" type="button" disabled={missions.length < pageSize || isLoading} onClick={() => setPage((current) => current + 1)}>
                Next page
              </Button>
            </div>
          </div>
          </>
        )}
      </section>
    </div>
  );
}
