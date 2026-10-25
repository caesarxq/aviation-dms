import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { safetyApi } from "../api/safety";
import { CrewMember } from "../types";
import { UserPlus, Trash2 } from "lucide-react";

function statusClass(status: string) {
  switch (status.toLowerCase()) {
    case "active": return "app-status app-status-healthy";
    case "inactive": return "app-status app-status-critical";
    default: return "app-status app-status-info";
  }
}

export function CrewManagement() {
  const qc = useQueryClient();
  const [roleFilter, setRoleFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [isCreating, setIsCreating] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState({
    full_name: "",
    role: "",
    base: "Nairobi",
    status: "active",
  });

  const { data: crew = [], isLoading } = useQuery({
    queryKey: ["crew-members", roleFilter, statusFilter],
    queryFn: () => safetyApi.listCrewMembers({ role: roleFilter || undefined, status: statusFilter || undefined }),
  });

  const createMutation = useMutation({
    mutationFn: (data: any) => safetyApi.createCrewMember(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["crew-members"] });
      setIsCreating(false);
      setForm({ full_name: "", role: "", base: "Nairobi", status: "active" });
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: any }) => safetyApi.updateCrewMember(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["crew-members"] });
      setEditingId(null);
      setForm({ full_name: "", role: "", base: "Nairobi", status: "active" });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => safetyApi.deleteCrewMember(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["crew-members"] }),
  });

  return (
    <div className="app-page">
      <header className="app-page-header">
        <div>
          <div className="app-eyebrow">Personnel & Aircraft</div>
          <h1 className="app-title">Crew Management</h1>
          <p className="app-subtitle">Manage crew directory, duty time logs, and qualification currency.</p>
        </div>
        <button className="app-btn" onClick={() => setIsCreating(true)}>
          <UserPlus size={16} /> Add Crew
        </button>
      </header>

      <section className="app-surface overflow-hidden">
        <div className="flex flex-col gap-3 border-b border-kfl-border p-4 md:flex-row md:items-center md:justify-between">
          <div className="text-sm font-semibold text-kfl-text">Crew Directory</div>
          <div className="flex gap-2">
            <input
              id="crew_role_filter"
              name="role"
              placeholder="Filter by role"
              className="app-input w-full md:w-auto"
              value={roleFilter}
              onChange={(e) => setRoleFilter(e.target.value)}
            />
            <select
              id="crew_status_filter"
              name="status"
              aria-label="Filter by status"
              className="app-input w-full md:w-auto"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
            >
              <option value="">All statuses</option>
              <option value="active">Active</option>
              <option value="inactive">Inactive</option>
            </select>
          </div>
        </div>

        {isLoading ? (
          <div className="p-10 text-center text-sm text-kfl-muted">Loading crew…</div>
        ) : crew.length === 0 ? (
          <div className="app-surface border-dashed p-10 text-center">
            <p className="text-sm font-bold text-kfl-text">No crew members found.</p>
            <p className="mt-1 text-xs text-kfl-muted">Add crew to begin duty and qualification tracking.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full">
              <thead className="border-b border-kfl-border bg-kfl-surface-subtle">
                <tr>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">ID</th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Name</th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Role</th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Base</th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Status</th>
                  <th className="px-4 py-3 text-right text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-kfl-border">
                {crew.map((c: CrewMember) => (
                  <tr key={c.crew_id} className="transition hover:bg-kfl-surface-subtle">
                    <td className="px-4 py-4 font-mono text-[12px] text-kfl-text">{c.crew_id}</td>
                    <td className="px-4 py-4 text-sm text-kfl-secondary">{c.full_name}</td>
                    <td className="px-4 py-4 text-sm text-kfl-secondary">{c.role}</td>
                    <td className="px-4 py-4 text-sm text-kfl-secondary">{c.base}</td>
                    <td className="px-4 py-4"><span className={statusClass(c.status)}>{c.status}</span></td>
                    <td className="px-4 py-4 text-right">
                      <button
                        id={`edit_crew_${c.crew_id}`}
                        className="app-btn app-btn-ghost"
                        onClick={() => {
                          setEditingId(c.crew_id);
                          setForm({ full_name: c.full_name, role: c.role, base: c.base, status: c.status });
                        }}
                      >
                        Edit
                      </button>
                      <button
                        id={`delete_crew_${c.crew_id}`}
                        aria-label={`Delete crew member ${c.crew_id}`}
                        className="app-btn app-btn-ghost"
                        onClick={() => {
                          if (confirm("Delete this crew member?")) deleteMutation.mutate(c.crew_id);
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
              <h2 className="app-modal-title">{editingId ? "Edit Crew Member" : "New Crew Member"}</h2>
              <p className="mt-1 text-xs text-kfl-muted">{editingId ? "Update crew details." : "Add a new crew member to the directory."}</p>
            </div>
            <div className="space-y-3 px-5 py-4">
              <label className="block text-sm text-kfl-secondary">
                <span className="mb-1 block text-xs font-semibold text-kfl-muted">Full Name</span>
                <input
                  id="crew_full_name"
                  name="full_name"
                  className="app-input"
                  value={form.full_name}
                  onChange={(e) => setForm({ ...form, full_name: e.target.value })}
                />
              </label>
              <label className="block text-sm text-kfl-secondary">
                <span className="mb-1 block text-xs font-semibold text-kfl-muted">Role</span>
                <input
                  id="crew_role"
                  name="role"
                  className="app-input"
                  value={form.role}
                  onChange={(e) => setForm({ ...form, role: e.target.value })}
                />
              </label>
              <label className="block text-sm text-kfl-secondary">
                <span className="mb-1 block text-xs font-semibold text-kfl-muted">Base</span>
                <input
                  id="crew_base"
                  name="base"
                  className="app-input"
                  value={form.base}
                  onChange={(e) => setForm({ ...form, base: e.target.value })}
                />
              </label>
              <label className="block text-sm text-kfl-secondary">
                <span className="mb-1 block text-xs font-semibold text-kfl-muted">Status</span>
                <select
                  id="crew_status"
                  name="status"
                  className="app-input"
                  value={form.status}
                  onChange={(e) => setForm({ ...form, status: e.target.value })}
                >
                  <option value="active">Active</option>
                  <option value="inactive">Inactive</option>
                </select>
              </label>
            </div>
            <div className="flex justify-end gap-2 border-t border-kfl-border px-5 py-4">
              <button className="app-btn app-btn-ghost" onClick={() => { setIsCreating(false); setEditingId(null); }}>Cancel</button>
              <button
                id="crew_submit"
                className="app-btn"
                disabled={!form.full_name || !form.role}
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
