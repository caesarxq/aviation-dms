import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { safetyApi } from "../api/safety";
import { TrainingRecord } from "../types";
import { GraduationCap, Plus, Trash2 } from "lucide-react";

function statusClass(status: string) {
  switch (status.toLowerCase()) {
    case "valid": return "app-status app-status-healthy";
    case "expired": return "app-status app-status-critical";
    case "pending": return "app-status app-status-warning";
    default: return "app-status app-status-info";
  }
}

export function TrainingManagement() {
  const qc = useQueryClient();
  const [categoryFilter, setCategoryFilter] = useState("");
  const [personFilter, setPersonFilter] = useState("");
  const [isCreating, setIsCreating] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState({
    person_id: "",
    training_category: "general",
    training_type: "",
    training_date: "",
    expiry_date: "",
    certificate_number: "",
    notes: "",
  });

  const { data: records = [], isLoading } = useQuery({
    queryKey: ["training-records", categoryFilter, personFilter],
    queryFn: () => safetyApi.listTrainingRecords({ category: categoryFilter || undefined, person_id: personFilter || undefined }),
  });

  const createMutation = useMutation({
    mutationFn: (data: any) => safetyApi.createTrainingRecord(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["training-records"] });
      setIsCreating(false);
      setForm({ person_id: "", training_category: "general", training_type: "", training_date: "", expiry_date: "", certificate_number: "", notes: "" });
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: any }) => safetyApi.updateTrainingRecord(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["training-records"] });
      setEditingId(null);
      setForm({ person_id: "", training_category: "general", training_type: "", training_date: "", expiry_date: "", certificate_number: "", notes: "" });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => safetyApi.deleteTrainingRecord(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["training-records"] }),
  });

  const stats = {
    total: records.length,
    valid: records.filter((r: TrainingRecord) => r.status === "valid").length,
    expired: records.filter((r: TrainingRecord) => r.status === "expired").length,
  };

  return (
    <div className="app-page">
      <header className="app-page-header">
        <div>
          <div className="app-eyebrow">Training & Competency</div>
          <h1 className="app-title">Training Management</h1>
          <p className="app-subtitle">Track personnel training, certifications, and expiry.</p>
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
          <div className="app-label">Valid</div>
          <div className="mt-2 text-2xl font-bold text-kfl-text">{stats.valid}</div>
        </div>
        <div className="app-surface p-4">
          <div className="app-label">Expired</div>
          <div className="mt-2 text-2xl font-bold text-kfl-text">{stats.expired}</div>
        </div>
      </section>

      <section className="app-surface overflow-hidden">
        <div className="flex flex-col gap-3 border-b border-kfl-border p-4 md:flex-row md:items-center md:justify-between">
          <div className="text-sm font-semibold text-kfl-text">Training Records</div>
          <div className="flex gap-2">
            <select
              id="training_category_filter"
              name="category"
              aria-label="Filter by category"
              className="app-input w-full md:w-auto"
              value={categoryFilter}
              onChange={(e) => setCategoryFilter(e.target.value)}
            >
              <option value="">All categories</option>
              <option value="general">General</option>
              <option value="dg">Dangerous Goods</option>
              <option value="security">Security</option>
              <option value="safety">Safety</option>
              <option value="maintenance">Maintenance</option>
            </select>
            <input
              id="training_person_filter"
              name="person_id"
              placeholder="Person ID"
              className="app-input w-full md:w-auto"
              value={personFilter}
              onChange={(e) => setPersonFilter(e.target.value)}
            />
          </div>
        </div>

        {isLoading ? (
          <div className="p-10 text-center text-sm text-kfl-muted">Loading training records…</div>
        ) : records.length === 0 ? (
          <div className="app-surface border-dashed p-10 text-center">
            <GraduationCap size={26} className="mx-auto mb-2 text-kfl-muted" />
            <p className="text-sm font-bold text-kfl-text">No training records found.</p>
            <p className="mt-1 text-xs text-kfl-muted">Create a new record to begin tracking.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full">
              <thead className="border-b border-kfl-border bg-kfl-surface-subtle">
                <tr>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">ID</th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Person</th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Category</th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Type</th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Date</th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Expiry</th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Status</th>
                  <th className="px-4 py-3 text-right text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-kfl-border">
                {records.map((record: TrainingRecord) => (
                  <tr key={record.record_id} className="transition hover:bg-kfl-surface-subtle">
                    <td className="px-4 py-4 font-mono text-[12px] text-kfl-text">{record.record_id}</td>
                    <td className="px-4 py-4 text-sm text-kfl-secondary">{record.person_id}</td>
                    <td className="px-4 py-4 text-sm text-kfl-secondary">{record.training_category}</td>
                    <td className="px-4 py-4 text-sm text-kfl-secondary">{record.training_type}</td>
                    <td className="px-4 py-4 text-sm text-kfl-secondary">{record.training_date}</td>
                    <td className="px-4 py-4 text-sm text-kfl-secondary">{record.expiry_date || "—"}</td>
                    <td className="px-4 py-4"><span className={statusClass(record.status)}>{record.status}</span></td>
                    <td className="px-4 py-4 text-right">
                      <button
                        id={`edit_training_${record.record_id}`}
                        className="app-btn app-btn-ghost"
                        onClick={() => {
                          setEditingId(record.record_id);
                          setForm({
                            person_id: record.person_id,
                            training_category: record.training_category,
                            training_type: record.training_type,
                            training_date: record.training_date,
                            expiry_date: record.expiry_date || "",
                            certificate_number: record.certificate_number || "",
                            notes: record.notes || "",
                          });
                        }}
                      >
                        Edit
                      </button>
                      <button
                        id={`delete_training_${record.record_id}`}
                        aria-label={`Delete training record ${record.record_id}`}
                        className="app-btn app-btn-ghost"
                        onClick={() => {
                          if (confirm("Delete this training record?")) deleteMutation.mutate(record.record_id);
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
              <h2 className="app-modal-title">{editingId ? "Edit Training Record" : "New Training Record"}</h2>
              <p className="mt-1 text-xs text-kfl-muted">{editingId ? "Update training details." : "Add a new training record for a person."}</p>
            </div>
            <div className="space-y-3 px-5 py-4">
              <label className="block text-sm text-kfl-secondary">
                <span className="mb-1 block text-xs font-semibold text-kfl-muted">Person ID</span>
                <input
                  id="training_person_id"
                  name="person_id"
                  className="app-input"
                  value={form.person_id}
                  onChange={(e) => setForm({ ...form, person_id: e.target.value })}
                />
              </label>
              <label className="block text-sm text-kfl-secondary">
                <span className="mb-1 block text-xs font-semibold text-kfl-muted">Category</span>
                <select
                  id="training_category"
                  name="training_category"
                  className="app-input"
                  value={form.training_category}
                  onChange={(e) => setForm({ ...form, training_category: e.target.value })}
                >
                  <option value="general">General</option>
                  <option value="dg">Dangerous Goods</option>
                  <option value="security">Security</option>
                  <option value="safety">Safety</option>
                  <option value="maintenance">Maintenance</option>
                </select>
              </label>
              <label className="block text-sm text-kfl-secondary">
                <span className="mb-1 block text-xs font-semibold text-kfl-muted">Training Type</span>
                <input
                  id="training_type"
                  name="training_type"
                  className="app-input"
                  value={form.training_type}
                  onChange={(e) => setForm({ ...form, training_type: e.target.value })}
                />
              </label>
              <label className="block text-sm text-kfl-secondary">
                <span className="mb-1 block text-xs font-semibold text-kfl-muted">Training Date</span>
                <input
                  id="training_date"
                  name="training_date"
                  type="date"
                  className="app-input"
                  value={form.training_date}
                  onChange={(e) => setForm({ ...form, training_date: e.target.value })}
                />
              </label>
              <label className="block text-sm text-kfl-secondary">
                <span className="mb-1 block text-xs font-semibold text-kfl-muted">Expiry Date</span>
                <input
                  id="training_expiry"
                  name="expiry_date"
                  type="date"
                  className="app-input"
                  value={form.expiry_date}
                  onChange={(e) => setForm({ ...form, expiry_date: e.target.value })}
                />
              </label>
              <label className="block text-sm text-kfl-secondary">
                <span className="mb-1 block text-xs font-semibold text-kfl-muted">Certificate Number</span>
                <input
                  id="training_certificate"
                  name="certificate_number"
                  className="app-input"
                  value={form.certificate_number}
                  onChange={(e) => setForm({ ...form, certificate_number: e.target.value })}
                />
              </label>
              <label className="block text-sm text-kfl-secondary">
                <span className="mb-1 block text-xs font-semibold text-kfl-muted">Notes</span>
                <textarea
                  id="training_notes"
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
                id="training_submit"
                className="app-btn"
                disabled={!form.person_id || !form.training_type || !form.training_date}
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
