import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { safetyApi } from "../api/safety";
import { TrainingRecord } from "../types";
import { GraduationCap, Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select";

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
        <Button onClick={() => setIsCreating(true)} variant="default" size="sm">
          <Plus size={16} /> New Record
        </Button>
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
            <Select onValueChange={(e) => setCategoryFilter(e)}>
              <SelectTrigger id="training_category_filter" name="category" aria-label="Filter by category">
                <SelectValue placeholder={categoryFilter || "All categories"} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="">All categories</SelectItem>
                <SelectItem value="general">General</SelectItem>
                <SelectItem value="dg">Dangerous Goods</SelectItem>
                <SelectItem value="security">Security</SelectItem>
                <SelectItem value="safety">Safety</SelectItem>
                <SelectItem value="maintenance">Maintenance</SelectItem>
              </SelectContent>
            </Select>
            <Input id="training_person_filter" name="person_id" placeholder="Person ID" value={personFilter} onChange={(e) => setPersonFilter(e.target.value)} className="w-full md:w-auto" />
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
                    <td className="px-4 py-4"><Badge variant={record.status === "valid" ? "default" : record.status === "expired" ? "destructive" : "secondary"} className={`badge ${record.status === "valid" ? "bg-kfl-status-info-bg text-kfl-status-info" : record.status === "expired" ? "bg-kfl-status-danger-bg text-kfl-status-danger" : "bg-kfl-status-warning-bg text-kfl-status-warning"}`}>{record.status}</Badge></td>
                    <td className="px-4 py-4 text-right">
                      <Button variant="outline" size="sm" id={`edit_training_${record.record_id}`} onClick={() => {
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
                      }}>
                        Edit
                      </Button>
                      <Button variant="destructive" size="sm" aria-label={`Delete training record ${record.record_id}`} id={`delete_training_${record.record_id}`} onClick={() => {
                        if (confirm("Delete this training record?")) deleteMutation.mutate(record.record_id);
                      }}>
                        <Trash2 size={14} />
                      </Button>
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
                <Input id="training_person_id" name="person_id" value={form.person_id} onChange={(e) => setForm({ ...form, person_id: e.target.value })} />
              </label>
              <label className="block text-sm text-kfl-secondary">
                <span className="mb-1 block text-xs font-semibold text-kfl-muted">Category</span>
                <Select onValueChange={(e) => setForm({ ...form, training_category: e })}>
                  <SelectTrigger id="training_category" name="training_category">
                    <SelectValue placeholder={form.training_category} />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="general">General</SelectItem>
                    <SelectItem value="dg">Dangerous Goods</SelectItem>
                    <SelectItem value="security">Security</SelectItem>
                    <SelectItem value="safety">Safety</SelectItem>
                    <SelectItem value="maintenance">Maintenance</SelectItem>
                  </SelectContent>
                </Select>
              </label>
              <label className="block text-sm text-kfl-secondary">
                <span className="mb-1 block text-xs font-semibold text-kfl-muted">Training Type</span>
                <Input id="training_type" name="training_type" value={form.training_type} onChange={(e) => setForm({ ...form, training_type: e.target.value })} />
              </label>
              <label className="block text-sm text-kfl-secondary">
                <span className="mb-1 block text-xs font-semibold text-kfl-muted">Training Date</span>
                <Input id="training_date" name="training_date" type="date" value={form.training_date} onChange={(e) => setForm({ ...form, training_date: e.target.value })} />
              </label>
              <label className="block text-sm text-kfl-secondary">
                <span className="mb-1 block text-xs font-semibold text-kfl-muted">Expiry Date</span>
                <Input id="training_expiry" name="expiry_date" type="date" value={form.expiry_date} onChange={(e) => setForm({ ...form, expiry_date: e.target.value })} />
              </label>
              <label className="block text-sm text-kfl-secondary">
                <span className="mb-1 block text-xs font-semibold text-kfl-muted">Certificate Number</span>
                <Input id="training_certificate" name="certificate_number" value={form.certificate_number} onChange={(e) => setForm({ ...form, certificate_number: e.target.value })} />
              </label>
              <label className="block text-sm text-kfl-secondary">
                <span className="mb-1 block text-xs font-semibold text-kfl-muted">Notes</span>
                <textarea id="training_notes" name="notes" value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} className="flex-1 min-h-[80px]" />
              </label>
            </div>
            <div className="flex justify-end gap-2 border-t border-kfl-border px-5 py-4">
              <Button variant="outline" size="sm" onClick={() => { setIsCreating(false); setEditingId(null); }}>
                Cancel
              </Button>
              <Button id="training_submit" variant="default" size="sm" disabled={!form.person_id || !form.training_type || !form.training_date} onClick={() => editingId ? updateMutation.mutate({ id: editingId, data: form }) : createMutation.mutate(form)}>
                {editingId ? (updateMutation.isPending ? "Saving…" : "Save") : (createMutation.isPending ? "Creating…" : "Create")}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
