import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { safetyApi } from "../api/safety";
import { CrewQualification, CrewMember } from "../types";
import { Award, Plus, Trash2 } from "lucide-react";

function statusClass(status: string) {
  switch (status.toLowerCase()) {
    case "valid": return "app-status app-status-healthy";
    case "expired": return "app-status app-status-critical";
    case "suspended": return "app-status app-status-warning";
    default: return "app-status app-status-info";
  }
}

export function CrewQualifications() {
  const qc = useQueryClient();
  const [crewFilter, setCrewFilter] = useState("");
  const [isCreating, setIsCreating] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState({
    crew_id: "",
    qual_type: "",
    rating: "",
    issue_date: "",
    expiry_date: "",
    notes: "",
  });

  const { data: qualifications = [], isLoading } = useQuery({
    queryKey: ["crew-qualifications", crewFilter],
    queryFn: () => safetyApi.listCrewQualifications({ crew_id: crewFilter || undefined }),
  });

  const { data: crewList = [] } = useQuery({
    queryKey: ["crew-members"],
    queryFn: () => safetyApi.listCrewMembers(),
  });

  const createMutation = useMutation({
    mutationFn: (data: any) => safetyApi.createCrewQualification(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["crew-qualifications"] });
      setIsCreating(false);
      setForm({ crew_id: "", qual_type: "", rating: "", issue_date: "", expiry_date: "", notes: "" });
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: any }) => safetyApi.updateCrewQualification(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["crew-qualifications"] });
      setEditingId(null);
      setForm({ crew_id: "", qual_type: "", rating: "", issue_date: "", expiry_date: "", notes: "" });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => safetyApi.deleteCrewQualification(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["crew-qualifications"] }),
  });

  return (
    <div className="app-page">
      <header className="app-page-header">
        <div>
          <div className="app-eyebrow">Personnel & Aircraft</div>
          <h1 className="app-title">Crew Qualifications</h1>
          <p className="app-subtitle">Track licenses, type ratings, medicals, and expiry alerts.</p>
        </div>
        <button className="app-btn" onClick={() => setIsCreating(true)}>
          <Plus size={16} /> Add Qualification
        </button>
      </header>

      <section className="app-surface overflow-hidden">
        <div className="flex flex-col gap-3 border-b border-kfl-border p-4 md:flex-row md:items-center md:justify-between">
          <div className="text-sm font-semibold text-kfl-text">Qualifications</div>
          <div className="flex gap-2">
            <select
              id="qual_crew_filter"
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
          <div className="p-10 text-center text-sm text-kfl-muted">Loading qualifications…</div>
        ) : qualifications.length === 0 ? (
          <div className="app-surface border-dashed p-10 text-center">
            <Award size={26} className="mx-auto mb-2 text-kfl-muted" />
            <p className="text-sm font-bold text-kfl-text">No qualifications found.</p>
            <p className="mt-1 text-xs text-kfl-muted">Add qualifications to track expiry and currency.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full">
              <thead className="border-b border-kfl-border bg-kfl-surface-subtle">
                <tr>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">ID</th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Crew</th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Type</th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Rating</th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Expiry</th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Status</th>
                  <th className="px-4 py-3 text-right text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-kfl-border">
                {qualifications.map((q: CrewQualification) => {
                  const crew = crewList.find((c: CrewMember) => c.crew_id === q.crew_id);
                  return (
                    <tr key={q.qual_id} className="transition hover:bg-kfl-surface-subtle">
                      <td className="px-4 py-4 font-mono text-[12px] text-kfl-text">{q.qual_id}</td>
                      <td className="px-4 py-4 text-sm text-kfl-secondary">{crew?.full_name || q.crew_id}</td>
                      <td className="px-4 py-4 text-sm text-kfl-secondary">{q.qual_type}</td>
                      <td className="px-4 py-4 text-sm text-kfl-secondary">{q.rating || "—"}</td>
                      <td className="px-4 py-4 text-sm text-kfl-secondary">{q.expiry_date}</td>
                      <td className="px-4 py-4"><span className={statusClass(q.status)}>{q.status}</span></td>
                      <td className="px-4 py-4 text-right">
                        <button
                          id={`edit_qual_${q.qual_id}`}
                          className="app-btn app-btn-ghost"
                          onClick={() => {
                            setEditingId(q.qual_id);
                            setForm({
                              crew_id: q.crew_id,
                              qual_type: q.qual_type,
                              rating: q.rating || "",
                              issue_date: q.issue_date,
                              expiry_date: q.expiry_date,
                              notes: q.notes || "",
                            });
                          }}
                        >
                          Edit
                        </button>
                        <button
                          id={`delete_qual_${q.qual_id}`}
                          aria-label={`Delete qualification ${q.qual_id}`}
                          className="app-btn app-btn-ghost"
                          onClick={() => {
                            if (confirm("Delete this qualification?")) deleteMutation.mutate(q.qual_id);
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
              <h2 className="app-modal-title">{editingId ? "Edit Qualification" : "New Qualification"}</h2>
              <p className="mt-1 text-xs text-kfl-muted">{editingId ? "Update qualification details." : "Add a new qualification record."}</p>
            </div>
            <div className="space-y-3 px-5 py-4">
              <label className="block text-sm text-kfl-secondary">
                <span className="mb-1 block text-xs font-semibold text-kfl-muted">Crew Member</span>
                <select
                  id="qual_crew_id"
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
                <span className="mb-1 block text-xs font-semibold text-kfl-muted">Qualification Type</span>
                <input
                  id="qual_type"
                  name="qual_type"
                  className="app-input"
                  value={form.qual_type}
                  onChange={(e) => setForm({ ...form, qual_type: e.target.value })}
                />
              </label>
              <label className="block text-sm text-kfl-secondary">
                <span className="mb-1 block text-xs font-semibold text-kfl-muted">Rating</span>
                <input
                  id="qual_rating"
                  name="rating"
                  className="app-input"
                  value={form.rating}
                  onChange={(e) => setForm({ ...form, rating: e.target.value })}
                />
              </label>
              <label className="block text-sm text-kfl-secondary">
                <span className="mb-1 block text-xs font-semibold text-kfl-muted">Issue Date</span>
                <input
                  id="qual_issue_date"
                  name="issue_date"
                  type="date"
                  className="app-input"
                  value={form.issue_date}
                  onChange={(e) => setForm({ ...form, issue_date: e.target.value })}
                />
              </label>
              <label className="block text-sm text-kfl-secondary">
                <span className="mb-1 block text-xs font-semibold text-kfl-muted">Expiry Date</span>
                <input
                  id="qual_expiry_date"
                  name="expiry_date"
                  type="date"
                  className="app-input"
                  value={form.expiry_date}
                  onChange={(e) => setForm({ ...form, expiry_date: e.target.value })}
                />
              </label>
              <label className="block text-sm text-kfl-secondary">
                <span className="mb-1 block text-xs font-semibold text-kfl-muted">Notes</span>
                <textarea
                  id="qual_notes"
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
                id="qual_submit"
                className="app-btn"
                disabled={!form.crew_id || !form.qual_type || !form.issue_date || !form.expiry_date}
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
