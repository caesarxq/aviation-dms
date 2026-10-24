import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "../api/client";
import { AlertTriangle, Plus, KeyRound } from "lucide-react";
import { Modal } from "../components/ui/Modal";
import FormField from "../components/ui/FormField";
import { useValidation } from "../utils/validation";
import { useToast } from "../components/ui/Toast";
import { RenewalProgressModal } from "../components/ui/modals/RenewalProgressModal";
import { useUnsavedChanges } from "../hooks/useUnsavedChanges";

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
  const [dirty, setDirty] = useState(false);

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
      setDirty(false);
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

  useUnsavedChanges(showForm && dirty);

  const setField = <K extends keyof typeof form>(key: K, value: (typeof form)[K]) => {
    setForm(prev => ({ ...prev, [key]: value }));
    setDirty(true);
  };

  const licenseRules = {
    person_id: { required: true },
    license_type: { required: true },
    license_number: { required: true },
    issuing_authority: { required: true },
    expiry_date: { required: "Expiry date is required for renewal tracking." },
  } as const;

  const { errors: licenseFieldErrors, isValid: licenseIsValid } = useValidation(form, licenseRules);

  const handleCreate = () => {
    setLicenseError("");
    if (!licenseIsValid) {
      setLicenseError("Please correct the fields marked below.");
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
          <FormField htmlFor="person_id_129" label="Person ID" hint="Use the ID from the personnel register, for example u-safety." required>
            <input id="person_id_129" name="person_id" aria-describedby="person_id_129-error" aria-invalid={!!licenseFieldErrors.person_id} className={`border border-kfl-border rounded p-2 text-sm w-full ${licenseFieldErrors.person_id ? "border-rose-400" : ""}`} placeholder="u-safety" value={form.person_id} onChange={e => setField("person_id", e.target.value)} />
            {licenseFieldErrors.person_id && <p id="person_id_129-error" className="text-[11px] text-rose-700 mt-1">{licenseFieldErrors.person_id}</p>}
          </FormField>
          <FormField htmlFor="license_type_135" label="License type" required>
            <select id="license_type_135" name="license_type" className="border border-kfl-border rounded p-2 text-sm w-full" value={form.license_type} onChange={e => setField("license_type", e.target.value)}>
              {LICENSE_TYPES.map(t => <option key={t} value={t}>{t.replace(/_/g, " ")}</option>)}
            </select>
          </FormField>
          <FormField htmlFor="license_number_138" label="License number" required>
            <input id="license_number_138" name="license_number" aria-describedby="license_number_138-error" aria-invalid={!!licenseFieldErrors.license_number} className={`border border-kfl-border rounded p-2 text-sm w-full ${licenseFieldErrors.license_number ? "border-rose-400" : ""}`} placeholder="License number" value={form.license_number} onChange={e => setField("license_number", e.target.value)} />
            {licenseFieldErrors.license_number && <p id="license_number_138-error" className="text-[11px] text-rose-700 mt-1">{licenseFieldErrors.license_number}</p>}
          </FormField>
          <FormField htmlFor="issuing_authority_144" label="Issuing authority" required>
            <input id="issuing_authority_144" name="issuing_authority" aria-describedby="issuing_authority_144-error" aria-invalid={!!licenseFieldErrors.issuing_authority} className={`border border-kfl-border rounded p-2 text-sm w-full ${licenseFieldErrors.issuing_authority ? "border-rose-400" : ""}`} placeholder="Issuing authority" value={form.issuing_authority} onChange={e => setField("issuing_authority", e.target.value)} />
            {licenseFieldErrors.issuing_authority && <p id="issuing_authority_144-error" className="text-[11px] text-rose-700 mt-1">{licenseFieldErrors.issuing_authority}</p>}
          </FormField>
          <FormField htmlFor="issued_date_150" label="Issued date">
            <input id="issued_date_150" name="issued_date" type="date" className="border border-kfl-border rounded p-2 text-sm w-full" value={form.issued_date} onChange={e => setField("issued_date", e.target.value)} />
          </FormField>
          <FormField htmlFor="expiry_date_151" label="Expiry date" hint="Required for renewal tracking." required>
            <input id="expiry_date_151" name="expiry_date" type="date" aria-describedby="expiry_date_151-error" aria-invalid={!!licenseFieldErrors.expiry_date} className={`border border-kfl-border rounded p-2 text-sm w-full ${licenseFieldErrors.expiry_date ? "border-rose-400" : ""}`} value={form.expiry_date} onChange={e => setField("expiry_date", e.target.value)} />
            {licenseFieldErrors.expiry_date && <p id="expiry_date_151-error" className="text-[11px] text-rose-700 mt-1">{licenseFieldErrors.expiry_date}</p>}
          </FormField>
          <FormField htmlFor="aircraft_type_152" label="Aircraft type" hint="Complete this for type ratings; otherwise leave blank.">
            <input id="aircraft_type_152" name="aircraft_type" className="border border-kfl-border rounded p-2 text-sm w-full" placeholder="Aircraft type" value={form.aircraft_type} onChange={e => setField("aircraft_type", e.target.value)} />
          </FormField>
          <FormField htmlFor="notes_158" label="Notes">
            <input id="notes_158" name="notes" className="border border-kfl-border rounded p-2 text-sm w-full" placeholder="Additional notes" value={form.notes} onChange={e => setField("notes", e.target.value)} />
          </FormField>
        </div>
        <div className="mt-4 flex gap-2 justify-end">
          <button onClick={() => { setShowForm(false); setDirty(false); }} className="app-btn-secondary px-4 py-2 text-sm">Cancel</button>
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
