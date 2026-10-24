import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "../api/client";
import { AlertTriangle, Plus, KeyRound } from "lucide-react";
import { Modal } from "../components/ui/Modal";
import { useToast } from "../components/ui/Toast";
import { RenewalProgressModal } from "../components/ui/modals/RenewalProgressModal";

const LICENSE_TYPES = [
  "pilot_license", "medical", "type_rating", "proficiency_check",
  "dg_training", "security_training", "sms_awareness", "crm",
  "indoctrination", "background_check", "avsec", "english_proficiency",
];

export function PersonnelLicenses() {
  const { toast } = useToast();
  const qc = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [showRenewalModal, setShowRenewalModal] = useState(false);
  const [filter, setFilter] = useState("");

  const { data: licenses = [], isLoading } = useQuery({
    queryKey: ["personnel-licenses", filter],
    queryFn: () => {
      const params = filter ? `?status=${filter}` : "";
      return api.get(`/p2/personnel/licenses${params}`).then((r: any) => r.data);
    },
  });

  const { data: expiring = [] } = useQuery({
    queryKey: ["expiring-licenses"],
    queryFn: () => api.get("/p2/personnel/expiring-licenses?days=30").then((r: any) => r.data),
  });

  const [form, setForm] = useState({
    person_id: "", license_type: "pilot_license", license_number: "",
    issuing_authority: "KCAA", issued_date: "", expiry_date: "", status: "valid",
    aircraft_type: "", notes: "",
  });
  const [licenseError, setLicenseError] = useState("");

  const createMutation = useMutation({
    mutationFn: (data: any) => api.post("/p2/personnel/licenses", data).then((r: any) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["personnel-licenses"] });
      qc.invalidateQueries({ queryKey: ["expiring-licenses"] });
      setShowForm(false);
      setLicenseError("");
      setForm({
        person_id: "", license_type: "pilot_license", license_number: "",
        issuing_authority: "KCAA", issued_date: "", expiry_date: "", status: "valid",
        aircraft_type: "", notes: "",
      });
      toast({ title: "License added", message: "Personnel license recorded successfully.", type: "success" });
    },
    onError: () => {
      setLicenseError("Failed to add license. Please check your entries and try again.");
    },
  });

  const handleCreate = () => {
    setLicenseError("");
    if (!form.person_id.trim()) {
      setLicenseError("Person ID is required.");
      return;
    }
    if (!form.expiry_date) {
      setLicenseError("Expiry date is required.");
      return;
    }
    createMutation.mutate(form);
  };

  const statusColor = (s: string) => {
    if (s === "valid") return "bg-green-100 text-green-800";
    if (s === "expiring_soon") return "bg-yellow-100 text-yellow-800";
    if (s === "expired") return "bg-red-100 text-red-800";
    return "bg-gray-100 text-gray-800";
  };

  const daysUntil = (date: string) => {
    const d = new Date(date);
    const now = new Date();
    return Math.ceil((d.getTime() - now.getTime()) / (1000 * 60 * 60 * 24));
  };

  if (isLoading) return <div className="p-8 text-kfl-muted">Loading licenses…</div>;

  return (
    <div className="app-page">
      <header className="app-page-header">
        <div>
          <div className="app-eyebrow">Personnel & Compliance</div>
          <h1 className="app-title">Personnel Licenses</h1>
          <p className="app-subtitle">Track crew qualifications, ratings, and credential currency.</p>
        </div>
        <button onClick={() => setShowForm(true)} className="app-btn-primary flex items-center gap-1">
          <Plus size={16} /> Add License
        </button>
        <button onClick={() => setShowRenewalModal(true)} className="app-btn-secondary">
          <KeyRound size={16} /> View Renewal Progress
        </button>
      </header>

      {/* Expiry alerts */}
      {expiring.length > 0 && (
        <div className="app-surface p-4 mb-4 border-l-4 border-red-500">
          <h3 className="font-semibold text-red-700 flex items-center gap-2 mb-2">
            <AlertTriangle size={16} /> {expiring.length} License(s) Expiring Soon
          </h3>
          <div className="space-y-1">
            {expiring.map((l: any) => (
              <div key={l.license_id} className="text-sm text-red-600">
                {l.license_type} — {l.person_id} — expires {l.expiry_date} ({daysUntil(l.expiry_date)} days)
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Add License Modal */}
      <Modal open={showForm} onClose={() => setShowForm(false)} title="Add Personnel License" description="Record one current personnel credential. Use the person ID from the personnel register, enter the issuing authority and dates exactly as shown on the credential, and provide the expiry date for renewal tracking.">
        {licenseError && (
          <div className="mb-3 p-3 rounded bg-rose-50/60 border border-rose-200 text-rose-800 text-sm">
            {licenseError}
          </div>
        )}
        <div className="grid grid-cols-2 gap-3">
          <input
            className="border border-kfl-border rounded p-2 text-sm"
            placeholder="Person ID"
            value={form.person_id}
            onChange={e => setForm({ ...form, person_id: e.target.value })}
          />
          <select className="border border-kfl-border rounded p-2 text-sm" value={form.license_type} onChange={e => setForm({ ...form, license_type: e.target.value })}>
            {LICENSE_TYPES.map(t => <option key={t} value={t}>{t.replace(/_/g, " ")}</option>)}
          </select>
          <input
            className="border border-kfl-border rounded p-2 text-sm"
            placeholder="License Number"
            value={form.license_number}
            onChange={e => setForm({ ...form, license_number: e.target.value })}
          />
          <input
            className="border border-kfl-border rounded p-2 text-sm"
            placeholder="Issuing Authority"
            value={form.issuing_authority}
            onChange={e => setForm({ ...form, issuing_authority: e.target.value })}
          />
          <input type="date" className="border border-kfl-border rounded p-2 text-sm" placeholder="Issued Date" value={form.issued_date} onChange={e => setForm({ ...form, issued_date: e.target.value })} />
          <input type="date" className="border border-kfl-border rounded p-2 text-sm" placeholder="Expiry Date" value={form.expiry_date} onChange={e => setForm({ ...form, expiry_date: e.target.value })} />
          <input
            className="border border-kfl-border rounded p-2 text-sm"
            placeholder="Aircraft Type (for type ratings)"
            value={form.aircraft_type}
            onChange={e => setForm({ ...form, aircraft_type: e.target.value })}
          />
          <input
            className="border border-kfl-border rounded p-2 text-sm"
            placeholder="Notes"
            value={form.notes}
            onChange={e => setForm({ ...form, notes: e.target.value })}
          />
        </div>
        <div className="mt-4 flex gap-2 justify-end">
          <button onClick={() => setShowForm(false)} className="app-btn-secondary px-4 py-2 text-sm">Cancel</button>
          <button onClick={handleCreate} className="app-btn-primary px-4 py-2 text-sm" disabled={createMutation.isPending}>
            {createMutation.isPending ? "Saving…" : "Save"}
          </button>
        </div>
      </Modal>

      {/* Filter */}
      <div className="flex gap-2 mb-4">
        {["", "valid", "expiring_soon", "expired"].map(s => (
          <button key={s} onClick={() => setFilter(s)} className={`px-3 py-1 text-sm rounded ${filter === s ? "bg-kfl-primary text-white" : "bg-kfl-surface text-kfl-muted"}`}>
            {s || "All"}
          </button>
        ))}
      </div>

      {/* License list */}
      <div className="app-surface overflow-auto">
        <table className="min-w-full">
          <thead className="border-b border-kfl-border bg-kfl-surface-subtle">
            <tr>
              <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Person</th>
              <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Type</th>
              <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Number</th>
              <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Authority</th>
              <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Expiry</th>
              <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Days Left</th>
              <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-kfl-border">
            {licenses.map((l: any) => (
              <tr key={l.license_id} className="hover:bg-kfl-surface-subtle">
                <td className="px-4 py-3 text-sm font-medium">{l.person_id}</td>
                <td className="px-4 py-3 text-sm">{l.license_type.replace(/_/g, " ")}</td>
                <td className="px-4 py-3 text-sm font-mono">{l.license_number || "—"}</td>
                <td className="px-4 py-3 text-sm">{l.issuing_authority}</td>
                <td className="px-4 py-3 text-sm">{l.expiry_date}</td>
                <td className="px-4 py-3 text-sm">
                  <span className={daysUntil(l.expiry_date) <= 30 ? "text-red-600 font-bold" : daysUntil(l.expiry_date) <= 90 ? "text-yellow-600" : "text-green-600"}>
                    {daysUntil(l.expiry_date)}
                  </span>
                </td>
                <td className="px-4 py-3 text-sm">
                  <span className={`px-2 py-0.5 rounded text-xs font-semibold ${statusColor(l.status)}`}>{l.status}</span>
                </td>
              </tr>
            ))}
            {licenses.length === 0 && (
              <tr><td colSpan={7} className="px-4 py-8 text-center text-kfl-muted">No licenses found.</td></tr>
            )}
          </tbody>
        </table>
      </div>
      <RenewalProgressModal open={showRenewalModal} onClose={() => setShowRenewalModal(false)} />
    </div>
  );
}

export default PersonnelLicenses;
