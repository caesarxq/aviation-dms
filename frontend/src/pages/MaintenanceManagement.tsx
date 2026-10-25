import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { safetyApi } from "../api/safety";
import { MaintenanceRecord } from "../types";
import { Wrench, Plus, Trash2 } from "lucide-react";

function statusClass(status: string) {
  switch (status.toLowerCase()) {
    case "completed": return "app-status app-status-healthy";
    case "pending": return "app-status app-status-warning";
    case "overdue": return "app-status app-status-critical";
    default: return "app-status app-status-info";
  }
}

export function MaintenanceManagement() {
  const qc = useQueryClient();
  const [aircraftFilter, setAircraftFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [isCreating, setIsCreating] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState({
    aircraft_registration: "5Y-1353A",
    maintenance_type: "",
    description: "",
    performed_by: "",
    performed_at: "",
    next_due: "",
    notes: "",
  });

  const { data: records = [], isLoading } = useQuery({
    queryKey: ["maintenance-records", aircraftFilter, statusFilter],
    queryFn: () => safetyApi.listMaintenanceRecords({ aircraft_registration: aircraftFilter || undefined, status: statusFilter || undefined }),
  });

  const createMutation = useMutation({
    mutationFn: (data: any) => safetyApi.createMaintenanceRecord(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["maintenance-records"] });
      setIsCreating(false);
      setForm({ aircraft_registration: "5Y-1353A", maintenance_type: "", description: "", performed_by: "", performed_at: "", next_due: "", notes: "" });
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: any }) => safetyApi.updateMaintenanceRecord(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["maintenance-records"] });
      setEditingId(null);
      setForm({ aircraft_registration: "5Y-1353A", maintenance_type: "", description: "", performed_by: "", performed_at: "", next_due: "", notes: "" });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => safetyApi.deleteMaintenanceRecord(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["maintenance-records"] }),
  });

  const stats = {
    total: records.length,
    completed: records.filter((r: MaintenanceRecord) => r.status === "completed").length,
    pending: records.filter((r: MaintenanceRecord) => r.status === "pending").length,
    overdue: records.filter((r: MaintenanceRecord) => r.status === "overdue").length,
  };

  return (
    <div className="app-page">
      <header className="app-page-header">
        <div>
          <div className="app-eyebrow">Aircraft Operations</div>
          <h1 className="app-title">Maintenance Management</h1>
          <p className="app-subtitle">Track aircraft maintenance, inspections, and work orders.</p>
        </div>
        <button className="app-btn" onClick={() => setIsCreating(true)}>
          <Plus size={16} /> New Record
        </button>
      </header>

      <section className="mb-5 grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="app-surface p-4">
          <div className="app-label">Total Records</div>
          <div className="mt-2 text-2xl font-bold text-kfl-text">{stats.total}</div>
        </div>
        <div className="app-surface p-4">
          <div className="app-label">Completed</div>
          <div className="mt-2 text-2xl font-bold text-kfl-text">{stats.completed}</div>
        </div>
        <div className="app-surface p-4">
          <div className="app-label">Pending / Overdue</div>
          <div className="mt-2 text-2xl font-bold text-kfl-text">{stats.pending + stats.overdue}</div>
        </div>
      </section>

      <section className="app-surface overflow-hidden">
        <div className="flex flex-col gap-3 border-b border-kfl-border p-4 md:flex-row md:items-center md:justify-between">
          <div className="text-sm font-semibold text-kfl-text">Maintenance Records</div>
          <div className="flex gap-2">
            <input
              id="maintenance_aircraft_filter"
              name="aircraft_registration"
              placeholder="Aircraft registration"
              className="app-input w-full md:w-auto"
              value={aircraftFilter}
              onChange={(e) => setAircraftFilter(e.target.value)}
            />
            <select
              id="maintenance_status_filter"
              name="status"
              aria-label="Filter by status"
              className="app-input w-full md:w-auto"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
            >
              <option value="">All statuses</option>
              <option value="completed">Completed</option>
              <option value="pending">Pending</option>
              <option value="overdue">Overdue</option>
            </select>
          </div>
        </div>

        {isLoading ? (
          <div className="p-10 text-center text-sm text-kfl-muted">Loading maintenance records…</div>
        ) : records.length === 0 ? (
          <div className="app-surface border-dashed p-10 text-center">
            <Wrench size={26} className="mx-auto mb-2 text-kfl-muted" />
            <p className="text-sm font-bold text-kfl-text">No maintenance records found.</p>
            <p className="mt-1 text-xs text-kfl-muted">Create a new record to track aircraft maintenance.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full">
              <thead className="border-b border-kfl-border bg-kfl-surface-subtle">
                <tr>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">ID</th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Aircraft</th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Type</th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Description</th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Performed At</th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Next Due</th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Status</th>
                  <th className="px-4 py-3 text-right text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-kfl-border">
                {records.map((record: MaintenanceRecord) => (
                  <tr key={record.record_id} className="transition hover:bg-kfl-surface-subtle">
                    <td className="px-4 py-4 font-mono text-[12px] text-kfl-text">{record.record_id}</td>
                    <td className="px-4 py-4 text-sm text-kfl-secondary">{record.aircraft_registration}</td>
                    <td className="px-4 py-4 text-sm text-kfl-secondary">{record.maintenance_type}</td>
                    <td className="px-4 py-4 text-sm text-kfl-secondary max-w-xs truncate">{record.description}</td>
                    <td className="px-4 py-4 text-sm text-kfl-secondary">{record.performed_at}</td>
                    <td className="px-4 py-4 text-sm text-kfl-secondary">{record.next_due || "—"}</td>
                    <td className="px-4 py-4"><span className={statusClass(record.status)}>{record.status}</span></td>
                    <td className="px-4 py-4 text-right">
                      <button
                        id={`edit_maintenance_${record.record_id}`}
                        className="app-btn app-btn-ghost"
                        onClick={() => {
                          setEditingId(record.record_id);
                          setForm({
                            aircraft_registration: record.aircraft_registration,
                            maintenance_type: record.maintenance_type,
                            description: record.description,
                            performed_by: record.performed_by,
                            performed_at: record.performed_at,
                            next_due: record.next_due || "",
                            notes: record.notes || "",
                          });
                        }}
                      >
                        Edit
                      </button>
                      <button
                        id={`delete_maintenance_${record.record_id}`}
                        aria-label={`Delete maintenance record ${record.record_id}`}
                        className="app-btn app-btn-ghost"
                        onClick={() => {
                          if (confirm("Delete this maintenance record?")) deleteMutation.mutate(record.record_id);
                        }}
                      >
                        <Trash2 size={14} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {(isCreating || editingId) && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="app-surface w-full max-w-lg">
            <div className="border-b border-kfl-border px-5 py-4">
              <h2 className="app-modal-title">{editingId ? "Edit Maintenance Record" : "New Maintenance Record"}</h2>
              <p className="mt-1 text-xs text-kfl-muted">{editingId ? "Update maintenance details." : "Record a new maintenance action for an aircraft."}</p>
            </div>
            <div className="space-y-3 px-5 py-4">
              <label className="block text-sm text-kfl-secondary">
                <span className="mb-1 block text-xs font-semibold text-kfl-muted">Aircraft Registration</span>
                <input
                  id="maintenance_aircraft"
                  name="aircraft_registration"
                  className="app-input"
                  value={form.aircraft_registration}
                  onChange={(e) => setForm({ ...form, aircraft_registration: e.target.value })}
                />
              </label>
              <label className="block text-sm text-kfl-secondary">
                <span className="mb-1 block text-xs font-semibold text-kfl-muted">Maintenance Type</span>
                <input
                  id="maintenance_type"
                  name="maintenance_type"
                  className="app-input"
                  value={form.maintenance_type}
                  onChange={(e) => setForm({ ...form, maintenance_type: e.target.value })}
                />
              </label>
              <label className="block text-sm text-kfl-secondary">
                <span className="mb-1 block text-xs font-semibold text-kfl-muted">Description</span>
                <textarea
                  id="maintenance_description"
                  name="description"
                  className="app-input"
                  value={form.description}
                  onChange={(e) => setForm({ ...form, description: e.target.value })}
                />
              </label>
              <label className="block text-sm text-kfl-secondary">
                <span className="mb-1 block text-xs font-semibold text-kfl-muted">Performed By</span>
                <input
                  id="maintenance_performed_by"
                  name="performed_by"
                  className="app-input"
                  value={form.performed_by}
                  onChange={(e) => setForm({ ...form, performed_by: e.target.value })}
                />
              </label>
              <label className="block text-sm text-kfl-secondary">
                <span className="mb-1 block text-xs font-semibold text-kfl-muted">Performed At</span>
                <input
                  id="maintenance_performed_at"
                  name="performed_at"
                  type="date"
                  className="app-input"
                  value={form.performed_at}
                  onChange={(e) => setForm({ ...form, performed_at: e.target.value })}
                />
              </label>
              <label className="block text-sm text-kfl-secondary">
                <span className="mb-1 block text-xs font-semibold text-kfl-muted">Next Due</span>
                <input
                  id="maintenance_next_due"
                  name="next_due"
                  type="date"
                  className="app-input"
                  value={form.next_due}
                  onChange={(e) => setForm({ ...form, next_due: e.target.value })}
                />
              </label>
              <label className="block text-sm text-kfl-secondary">
                <span className="mb-1 block text-xs font-semibold text-kfl-muted">Notes</span>
                <textarea
                  id="maintenance_notes"
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
                id="maintenance_submit"
                className="app-btn"
                disabled={!form.aircraft_registration || !form.maintenance_type || !form.description || !form.performed_by || !form.performed_at}
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
