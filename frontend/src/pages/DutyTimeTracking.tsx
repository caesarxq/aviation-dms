import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { safetyApi } from "../api/safety";
import { DutyRecord, CrewMember } from "../types";
import { Clock, Plus, Trash2 } from "lucide-react";

function formatHours(hours: number | null | undefined) {
  if (hours === null || hours === undefined) return "—";
  return `${hours.toFixed(1)}h`;
}

export function DutyTimeTracking() {
  const qc = useQueryClient();
  const [crewFilter, setCrewFilter] = useState("");
  const [isCreating, setIsCreating] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState({
    crew_id: "",
    duty_start: "",
    duty_end: "",
    aircraft_reg: "",
    role: "",
    location: "",
    block_hours: "" as string | number,
    notes: "",
  });

  const { data: duties = [], isLoading } = useQuery({
    queryKey: ["duty-records", crewFilter],
    queryFn: () => safetyApi.listDutyRecords({ crew_id: crewFilter || undefined }),
  });

  const { data: crewList = [] } = useQuery({
    queryKey: ["crew-members"],
    queryFn: () => safetyApi.listCrewMembers(),
  });

  const createMutation = useMutation({
    mutationFn: (data: any) => safetyApi.createDutyRecord(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["duty-records"] });
      setIsCreating(false);
      setForm({ crew_id: "", duty_start: "", duty_end: "", aircraft_reg: "", role: "", location: "", block_hours: "", notes: "" });
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: any }) => safetyApi.updateDutyRecord(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["duty-records"] });
      setEditingId(null);
      setForm({ crew_id: "", duty_start: "", duty_end: "", aircraft_reg: "", role: "", location: "", block_hours: "", notes: "" });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => safetyApi.deleteDutyRecord(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["duty-records"] }),
  });

  return (
    <div className="app-page">
      <header className="app-page-header">
        <div>
          <div className="app-eyebrow">Personnel & Aircraft</div>
          <h1 className="app-title">Duty Time Tracking</h1>
          <p className="app-subtitle">Log duty periods, block hours, and FDTL compliance.</p>
        </div>
        <button className="app-btn" onClick={() => setIsCreating(true)}>
          <Plus size={16} /> New Duty
        </button>
      </header>

      <section className="app-surface overflow-hidden">
        <div className="flex flex-col gap-3 border-b border-kfl-border p-4 md:flex-row md:items-center md:justify-between">
          <div className="text-sm font-semibold text-kfl-text">Duty Records</div>
          <div className="flex gap-2">
            <select
              id="duty_crew_filter"
              name="crew_id"
              aria-label="Filter by crew"
              className="app-input w-full md:w-auto"
              value={crewFilter}
              onChange={(e) => setCrewFilter(e.target.value)}
            >
              <option value="">All crew</option>
              {crewList.map((c: CrewMember) => (
                <option key={c.crew_id} value={c.crew_id}>{c.full_name}</option>
              ))}
            </select>
          </div>
        </div>

        {isLoading ? (
          <div className="p-10 text-center text-sm text-kfl-muted">Loading duty records…</div>
        ) : duties.length === 0 ? (
          <div className="app-surface border-dashed p-10 text-center">
            <Clock size={26} className="mx-auto mb-2 text-kfl-muted" />
            <p className="text-sm font-bold text-kfl-text">No duty records found.</p>
            <p className="mt-1 text-xs text-kfl-muted">Create a new duty record to start tracking.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full">
              <thead className="border-b border-kfl-border bg-kfl-surface-subtle">
                <tr>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">ID</th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Crew</th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Duty Start</th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Duty End</th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Aircraft</th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Block</th>
                  <th className="px-4 py-3 text-right text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-kfl-border">
                {duties.map((duty: DutyRecord) => {
                  const crew = crewList.find((c: CrewMember) => c.crew_id === duty.crew_id);
                  return (
                    <tr key={duty.duty_id} className="transition hover:bg-kfl-surface-subtle">
                      <td className="px-4 py-4 font-mono text-[12px] text-kfl-text">{duty.duty_id}</td>
                      <td className="px-4 py-4 text-sm text-kfl-secondary">{crew?.full_name || duty.crew_id}</td>
                      <td className="px-4 py-4 text-sm text-kfl-secondary">{duty.duty_start}</td>
                      <td className="px-4 py-4 text-sm text-kfl-secondary">{duty.duty_end}</td>
                      <td className="px-4 py-4 text-sm text-kfl-secondary">{duty.aircraft_reg || "—"}</td>
                      <td className="px-4 py-4 text-sm text-kfl-secondary">{formatHours(duty.block_hours)}</td>
                      <td className="px-4 py-4 text-right">
                        <button
                          id={`edit_duty_${duty.duty_id}`}
                          className="app-btn app-btn-ghost"
                          onClick={() => {
                            setEditingId(duty.duty_id);
                            setForm({
                              crew_id: duty.crew_id,
                              duty_start: duty.duty_start,
                              duty_end: duty.duty_end,
                              aircraft_reg: duty.aircraft_reg || "",
                              role: duty.role,
                              location: duty.location || "",
                              block_hours: duty.block_hours ?? "",
                              notes: duty.notes || "",
                            });
                          }}
                        >
                          Edit
                        </button>
                        <button
                          id={`delete_duty_${duty.duty_id}`}
                          aria-label={`Delete duty record ${duty.duty_id}`}
                          className="app-btn app-btn-ghost"
                          onClick={() => {
                            if (confirm("Delete this duty record?")) deleteMutation.mutate(duty.duty_id);
                          }}
                        >
                          <Trash2 size={14} />
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {(isCreating || editingId) && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="app-surface w-full max-w-lg">
            <div className="border-b border-kfl-border px-5 py-4">
              <h2 className="app-modal-title">{editingId ? "Edit Duty Record" : "New Duty Record"}</h2>
              <p className="mt-1 text-xs text-kfl-muted">{editingId ? "Update duty details." : "Record a new duty period."}</p>
            </div>
            <div className="space-y-3 px-5 py-4">
              <label className="block text-sm text-kfl-secondary">
                <span className="mb-1 block text-xs font-semibold text-kfl-muted">Crew Member</span>
                <select
                  id="duty_crew_id"
                  name="crew_id"
                  className="app-input"
                  value={form.crew_id}
                  onChange={(e) => setForm({ ...form, crew_id: e.target.value })}
                >
                  <option value="">Select crew</option>
                  {crewList.map((c: CrewMember) => (
                    <option key={c.crew_id} value={c.crew_id}>{c.full_name}</option>
                  ))}
                </select>
              </label>
              <label className="block text-sm text-kfl-secondary">
                <span className="mb-1 block text-xs font-semibold text-kfl-muted">Role</span>
                <input
                  id="duty_role"
                  name="role"
                  className="app-input"
                  value={form.role}
                  onChange={(e) => setForm({ ...form, role: e.target.value })}
                />
              </label>
              <label className="block text-sm text-kfl-secondary">
                <span className="mb-1 block text-xs font-semibold text-kfl-muted">Duty Start</span>
                <input
                  id="duty_start"
                  name="duty_start"
                  type="datetime-local"
                  className="app-input"
                  value={form.duty_start}
                  onChange={(e) => setForm({ ...form, duty_start: e.target.value })}
                />
              </label>
              <label className="block text-sm text-kfl-secondary">
                <span className="mb-1 block text-xs font-semibold text-kfl-muted">Duty End</span>
                <input
                  id="duty_end"
                  name="duty_end"
                  type="datetime-local"
                  className="app-input"
                  value={form.duty_end}
                  onChange={(e) => setForm({ ...form, duty_end: e.target.value })}
                />
              </label>
              <label className="block text-sm text-kfl-secondary">
                <span className="mb-1 block text-xs font-semibold text-kfl-muted">Aircraft Registration</span>
                <input
                  id="duty_aircraft"
                  name="aircraft_reg"
                  className="app-input"
                  value={form.aircraft_reg}
                  onChange={(e) => setForm({ ...form, aircraft_reg: e.target.value })}
                />
              </label>
              <label className="block text-sm text-kfl-secondary">
                <span className="mb-1 block text-xs font-semibold text-kfl-muted">Location</span>
                <input
                  id="duty_location"
                  name="location"
                  className="app-input"
                  value={form.location}
                  onChange={(e) => setForm({ ...form, location: e.target.value })}
                />
              </label>
              <label className="block text-sm text-kfl-secondary">
                <span className="mb-1 block text-xs font-semibold text-kfl-muted">Block Hours</span>
                <input
                  id="duty_block_hours"
                  name="block_hours"
                  type="number"
                  step="0.1"
                  className="app-input"
                  value={form.block_hours}
                  onChange={(e) => setForm({ ...form, block_hours: e.target.value === "" ? "" : parseFloat(e.target.value) })}
                />
              </label>
              <label className="block text-sm text-kfl-secondary">
                <span className="mb-1 block text-xs font-semibold text-kfl-muted">Notes</span>
                <textarea
                  id="duty_notes"
                  name="notes"
                  className="app-input"
                  value={form.notes}
                  onChange={(e) => setForm({ ...form, notes: e.target.value })}
                />
              </label>
            </div>
            <div className="flex justify-end gap-2 border-t border-kfl-border px-5 py-4">
              <button className="app-btn app-btn-ghost" onClick={() => { setIsCreating(false); setEditingId(null); }}>Cancel</button>
              <button
                id="duty_submit"
                className="app-btn"
                disabled={!form.crew_id || !form.duty_start || !form.duty_end || !form.role}
                onClick={() => editingId ? updateMutation.mutate({ id: editingId, data: form }) : createMutation.mutate(form)}
              >
                {editingId ? (updateMutation.isPending ? "Saving…" : "Save") : (createMutation.isPending ? "Creating…" : "Create")}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
