import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "../api/client";
import { Shield, Plus, AlertTriangle, Calendar, KeyRound } from "lucide-react";
import { Modal } from "../components/ui/Modal";
import { useToast } from "../components/ui/Toast";
import { RenewalProgressModal } from "../components/ui/modals/RenewalProgressModal";
import FormField from "../components/ui/FormField";

const INSURANCE_TYPES = ["hull", "liability", "war_risk", "passenger_liability", "cargo_liability"];
const AIRCRAFT_DOC_TYPES = ["airworthiness_cert", "registration", "arc", "noise_cert", "radio_license", "maintenance_release"];

export function AircraftInsurance() {
  const { toast } = useToast();
  const qc = useQueryClient();
  const [showInsForm, setShowInsForm] = useState(false);
  const [showDocForm, setShowDocForm] = useState(false);
  const [showRenewalModal, setShowRenewalModal] = useState(false);
  const [selectedAircraft, setSelectedAircraft] = useState("");

  const { data: aircraft = [] } = useQuery({
    queryKey: ["aircraft-list"],
    queryFn: () => api.get("/p1/aircraft").then((r: any) => r.data),
  });

  const { data: insurance = [] } = useQuery({
    queryKey: ["aircraft-insurance", selectedAircraft],
    queryFn: () => selectedAircraft
      ? api.get(`/p2/aircraft/${selectedAircraft}/insurance`).then((r: any) => r.data)
      : Promise.resolve([]),
    enabled: !!selectedAircraft,
  });

  const { data: aircraftDocs = [] } = useQuery({
    queryKey: ["aircraft-docs", selectedAircraft],
    queryFn: () => selectedAircraft
      ? api.get(`/p2/aircraft/${selectedAircraft}/documents`).then((r: any) => r.data)
      : Promise.resolve([]),
    enabled: !!selectedAircraft,
  });

  const { data: expiringIns = [] } = useQuery({
    queryKey: ["expiring-insurance"],
    queryFn: () => api.get("/p2/insurance/expiring?days=30").then((r: any) => r.data),
  });

  const { data: expiringDocs = [] } = useQuery({
    queryKey: ["expiring-aircraft-docs"],
    queryFn: () => api.get("/p2/aircraft-documents/expiring?days=30").then((r: any) => r.data),
  });

  const [insForm, setInsForm] = useState({
    insurance_type: "hull", insurer: "", policy_number: "", broker: "",
    coverage_amount: "", currency: "USD", premium_amount: "", start_date: "", expiry_date: "",
  });
  const [insError, setInsError] = useState("");

  const [docForm, setDocForm] = useState({
    document_type: "airworthiness_cert", document_number: "", issuing_authority: "KCAA",
    issue_date: "", expiry_date: "", notes: "",
  });
  const [docError, setDocError] = useState("");

  const createInsMutation = useMutation({
    mutationFn: (data: any) => api.post(`/p2/aircraft/${selectedAircraft}/insurance`, data).then((r: any) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["aircraft-insurance"] });
      qc.invalidateQueries({ queryKey: ["expiring-insurance"] });
      setShowInsForm(false);
      setInsError("");
      setInsForm({
        insurance_type: "hull", insurer: "", policy_number: "", broker: "",
        coverage_amount: "", currency: "USD", premium_amount: "", start_date: "", expiry_date: "",
      });
      toast({ title: "Insurance added", message: "Aircraft insurance policy recorded successfully.", type: "success" });
    },
    onError: () => {
      setInsError("Failed to add insurance policy. Please check your entries and try again.");
    },
  });

  const createDocMutation = useMutation({
    mutationFn: (data: any) => api.post(`/p2/aircraft/${selectedAircraft}/documents`, data).then((r: any) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["aircraft-docs"] });
      qc.invalidateQueries({ queryKey: ["expiring-aircraft-docs"] });
      setShowDocForm(false);
      setDocError("");
      setDocForm({
        document_type: "airworthiness_cert", document_number: "", issuing_authority: "KCAA",
        issue_date: "", expiry_date: "", notes: "",
      });
      toast({ title: "Document added", message: "Aircraft document recorded successfully.", type: "success" });
    },
    onError: () => {
      setDocError("Failed to add aircraft document. Please check your entries and try again.");
    },
  });

  const daysUntil = (date: string) => {
    if (!date) return null;
    const d = new Date(date);
    const now = new Date();
    return Math.ceil((d.getTime() - now.getTime()) / (1000 * 60 * 60 * 24));
  };

  const statusColor = (days: number | null) => {
    if (days === null) return "text-gray-600";
    if (days <= 0) return "text-red-600 font-bold";
    if (days <= 7) return "text-red-600 font-bold";
    if (days <= 30) return "text-yellow-600";
    return "text-green-600";
  };

  return (
    <div className="app-page">
      <header className="app-page-header">
        <div>
          <div className="app-eyebrow">Aircraft & Compliance</div>
          <h1 className="app-title">Aircraft Insurance & Documents</h1>
          <p className="app-subtitle">Track aircraft insurance policies and airworthiness documents.</p>
        </div>
        <button onClick={() => setShowRenewalModal(true)} className="app-btn-secondary">
          <KeyRound size={16} /> Renewal Progress
        </button>
      </header>

      {/* Expiry alerts */}
      {(expiringIns.length > 0 || expiringDocs.length > 0) && (
        <div className="app-surface p-4 mb-4 border-l-4 border-red-500">
          <h3 className="font-semibold text-red-700 flex items-center gap-2 mb-2">
            <AlertTriangle size={16} /> Expiring Soon
          </h3>
          {expiringIns.map((i: any) => (
            <div key={i.insurance_id} className="text-sm text-red-600">
              Insurance: {i.insurance_type} — {i.registration || i.aircraft_id} — expires {i.expiry_date} ({daysUntil(i.expiry_date)} days)
            </div>
          ))}
          {expiringDocs.map((d: any) => (
            <div key={d.doc_id} className="text-sm text-red-600">
              Document: {d.document_type} — {d.registration || d.aircraft_id} — expires {d.expiry_date} ({daysUntil(d.expiry_date)} days)
            </div>
          ))}
        </div>
      )}

      {/* Aircraft selector */}
      <div className="app-surface p-4 mb-4">
        <label className="text-sm font-semibold text-kfl-muted mb-2 block">Select Aircraft</label>
        <select id="selectedaircraft_149" name="selectedaircraft"
          className="border border-kfl-border rounded p-2 text-sm w-full max-w-md"
          value={selectedAircraft}
          onChange={e => setSelectedAircraft(e.target.value)}
        >
          <option value="">— Select an aircraft —</option>
          {aircraft.map((a: any) => (
            <option key={a.aircraft_id} value={a.aircraft_id}>{a.registration} — {a.model}</option>
          ))}
        </select>
      </div>

      {selectedAircraft && (
        <>
          {/* Insurance section */}
          <div className="app-surface p-5 mb-4">
            <div className="flex justify-between items-center mb-3">
              <h3 className="font-semibold text-kfl-text flex items-center gap-2"><Shield size={16} /> Insurance Policies</h3>
              <button onClick={() => setShowInsForm(true)} className="app-btn-secondary text-sm px-3 py-1 flex items-center gap-1">
                <Plus size={14} /> Add Policy
              </button>
            </div>

            {/* Insurance Modal */}
            <Modal open={showInsForm} onClose={() => setShowInsForm(false)} title="Add Insurance Policy" description="Record the policy for the selected aircraft. Enter the insurer and policy number exactly as issued, then provide coverage, premium, start, and expiry details for compliance tracking.">
              {insError && (
                <div className="mb-3 p-3 rounded bg-rose-50/60 border border-rose-200 text-rose-800 text-sm">
                  {insError}
                </div>
              )}
              <div className="grid grid-cols-2 gap-3">
                <FormField htmlFor="insurance_type_180" label="Insurance type" required>
                  <select id="insurance_type_180" name="insurance_type" className="border border-kfl-border rounded p-2 text-sm w-full" value={insForm.insurance_type} onChange={e => setInsForm({ ...insForm, insurance_type: e.target.value })}>
                    {INSURANCE_TYPES.map(t => <option key={t} value={t}>{t.replace(/_/g, " ")}</option>)}
                  </select>
                </FormField>
                <FormField htmlFor="insurer_183" label="Insurer" required><input id="insurer_183" name="insurer" className="border border-kfl-border rounded p-2 text-sm w-full" placeholder="Insurer" value={insForm.insurer} onChange={e => setInsForm({ ...insForm, insurer: e.target.value })} /></FormField>
                <FormField htmlFor="policy_number_184" label="Policy number" required><input id="policy_number_184" name="policy_number" className="border border-kfl-border rounded p-2 text-sm w-full" placeholder="Policy number" value={insForm.policy_number} onChange={e => setInsForm({ ...insForm, policy_number: e.target.value })} /></FormField>
                <FormField htmlFor="broker_185" label="Broker"><input id="broker_185" name="broker" className="border border-kfl-border rounded p-2 text-sm w-full" placeholder="Broker" value={insForm.broker} onChange={e => setInsForm({ ...insForm, broker: e.target.value })} /></FormField>
                <FormField htmlFor="start_date_186" label="Start date"><input id="start_date_186" name="start_date" type="date" className="border border-kfl-border rounded p-2 text-sm w-full" value={insForm.start_date} onChange={e => setInsForm({ ...insForm, start_date: e.target.value })} /></FormField>
                <FormField htmlFor="expiry_date_187" label="Expiry date" hint="Required for renewal tracking." required><input id="expiry_date_187" name="expiry_date" type="date" className="border border-kfl-border rounded p-2 text-sm w-full" value={insForm.expiry_date} onChange={e => setInsForm({ ...insForm, expiry_date: e.target.value })} /></FormField>
                <FormField htmlFor="coverage_amount_188" label="Coverage amount"><input id="coverage_amount_188" name="coverage_amount" type="number" className="border border-kfl-border rounded p-2 text-sm w-full" placeholder="Coverage amount" value={insForm.coverage_amount} onChange={e => setInsForm({ ...insForm, coverage_amount: e.target.value })} /></FormField>
                <FormField htmlFor="premium_amount_189" label="Premium amount"><input id="premium_amount_189" name="premium_amount" type="number" className="border border-kfl-border rounded p-2 text-sm w-full" placeholder="Premium amount" value={insForm.premium_amount} onChange={e => setInsForm({ ...insForm, premium_amount: e.target.value })} /></FormField>
              </div>
              <div className="mt-4 flex gap-2 justify-end">
                <button onClick={() => setShowInsForm(false)} className="app-btn-secondary px-4 py-2 text-sm">Cancel</button>
                <button onClick={() => {
                  setInsError("");
                  if (!insForm.expiry_date) {
                    setInsError("Expiry date is required.");
                    return;
                  }
                  createInsMutation.mutate(insForm);
                }} className="app-btn-primary px-4 py-2 text-sm" disabled={createInsMutation.isPending}>
                  {createInsMutation.isPending ? "Saving…" : "Save Policy"}
                </button>
              </div>
            </Modal>

            <table className="min-w-full">
              <thead className="border-b border-kfl-border bg-kfl-surface-subtle">
                <tr>
                  <th className="px-4 py-2 text-left text-[11px] font-bold uppercase text-kfl-muted">Type</th>
                  <th className="px-4 py-2 text-left text-[11px] font-bold uppercase text-kfl-muted">Insurer</th>
                  <th className="px-4 py-2 text-left text-[11px] font-bold uppercase text-kfl-muted">Policy #</th>
                  <th className="px-4 py-2 text-left text-[11px] font-bold uppercase text-kfl-muted">Expiry</th>
                  <th className="px-4 py-2 text-left text-[11px] font-bold uppercase text-kfl-muted">Days Left</th>
                  <th className="px-4 py-2 text-left text-[11px] font-bold uppercase text-kfl-muted">Status</th>
                  <th className="px-4 py-2 text-left text-[11px] font-bold uppercase text-kfl-muted">Renewal</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-kfl-border">
                {insurance.map((i: any) => (
                  <tr key={i.insurance_id} className="hover:bg-kfl-surface-subtle">
                    <td className="px-4 py-2 text-sm">{i.insurance_type.replace(/_/g, " ")}</td>
                    <td className="px-4 py-2 text-sm">{i.insurer}</td>
                    <td className="px-4 py-2 text-sm font-mono">{i.policy_number || "—"}</td>
                    <td className="px-4 py-2 text-sm">{i.expiry_date}</td>
                    <td className={`px-4 py-2 text-sm ${statusColor(daysUntil(i.expiry_date))}`}>{daysUntil(i.expiry_date)}</td>
                    <td className="px-4 py-2 text-sm">{i.status}</td>
                    <td className="px-4 py-2 text-sm">{i.renewal_status.replace(/_/g, " ")}</td>
                  </tr>
                ))}
                {insurance.length === 0 && <tr><td colSpan={7} className="px-4 py-6 text-center text-kfl-muted">No insurance policies found.</td></tr>}
              </tbody>
            </table>
          </div>

          {/* Aircraft Documents section */}
          <div className="app-surface p-5">
            <div className="flex justify-between items-center mb-3">
              <h3 className="font-semibold text-kfl-text flex items-center gap-2"><Calendar size={16} /> Aircraft Documents</h3>
              <button onClick={() => setShowDocForm(true)} className="app-btn-secondary text-sm px-3 py-1 flex items-center gap-1">
                <Plus size={14} /> Add Document
              </button>
            </div>

            {/* Aircraft Document Modal */}
            <Modal open={showDocForm} onClose={() => setShowDocForm(false)} title="Add Aircraft Document" description="Record an airworthiness, registration, or other aircraft document for the selected aircraft. Use the document number and issuing authority exactly as printed and include expiry details when applicable.">
              {docError && (
                <div className="mb-3 p-3 rounded bg-rose-50/60 border border-rose-200 text-rose-800 text-sm">
                  {docError}
                </div>
              )}
              <div className="grid grid-cols-2 gap-3">
                <FormField htmlFor="document_type_252" label="Document type" required>
                  <select id="document_type_252" name="document_type" className="border border-kfl-border rounded p-2 text-sm w-full" value={docForm.document_type} onChange={e => setDocForm({ ...docForm, document_type: e.target.value })}>
                    {AIRCRAFT_DOC_TYPES.map(t => <option key={t} value={t}>{t.replace(/_/g, " ")}</option>)}
                  </select>
                </FormField>
                <FormField htmlFor="document_number_255" label="Document number" required><input id="document_number_255" name="document_number" className="border border-kfl-border rounded p-2 text-sm w-full" placeholder="Document number" value={docForm.document_number} onChange={e => setDocForm({ ...docForm, document_number: e.target.value })} /></FormField>
                <FormField htmlFor="issuing_authority_256" label="Issuing authority" required><input id="issuing_authority_256" name="issuing_authority" className="border border-kfl-border rounded p-2 text-sm w-full" placeholder="Issuing authority" value={docForm.issuing_authority} onChange={e => setDocForm({ ...docForm, issuing_authority: e.target.value })} /></FormField>
                <FormField htmlFor="issue_date_257" label="Issue date"><input id="issue_date_257" name="issue_date" type="date" className="border border-kfl-border rounded p-2 text-sm w-full" value={docForm.issue_date} onChange={e => setDocForm({ ...docForm, issue_date: e.target.value })} /></FormField>
                <FormField htmlFor="expiry_date_258" label="Expiry date" hint="Enter the expiry date when the document is time-limited."><input id="expiry_date_258" name="expiry_date" type="date" className="border border-kfl-border rounded p-2 text-sm w-full" value={docForm.expiry_date} onChange={e => setDocForm({ ...docForm, expiry_date: e.target.value })} /></FormField>
                <FormField htmlFor="notes_259" label="Notes"><input id="notes_259" name="notes" className="border border-kfl-border rounded p-2 text-sm w-full" placeholder="Additional notes" value={docForm.notes} onChange={e => setDocForm({ ...docForm, notes: e.target.value })} /></FormField>
              </div>
              <div className="mt-4 flex gap-2 justify-end">
                <button onClick={() => setShowDocForm(false)} className="app-btn-secondary px-4 py-2 text-sm">Cancel</button>
                <button onClick={() => {
                  setDocError("");
                  createDocMutation.mutate(docForm);
                }} className="app-btn-primary px-4 py-2 text-sm" disabled={createDocMutation.isPending}>
                  {createDocMutation.isPending ? "Saving…" : "Save Document"}
                </button>
              </div>
            </Modal>

            <table className="min-w-full">
              <thead className="border-b border-kfl-border bg-kfl-surface-subtle">
                <tr>
                  <th className="px-4 py-2 text-left text-[11px] font-bold uppercase text-kfl-muted">Type</th>
                  <th className="px-4 py-2 text-left text-[11px] font-bold uppercase text-kfl-muted">Number</th>
                  <th className="px-4 py-2 text-left text-[11px] font-bold uppercase text-kfl-muted">Authority</th>
                  <th className="px-4 py-2 text-left text-[11px] font-bold uppercase text-kfl-muted">Issue Date</th>
                  <th className="px-4 py-2 text-left text-[11px] font-bold uppercase text-kfl-muted">Expiry</th>
                  <th className="px-4 py-2 text-left text-[11px] font-bold uppercase text-kfl-muted">Days Left</th>
                  <th className="px-4 py-2 text-left text-[11px] font-bold uppercase text-kfl-muted">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-kfl-border">
                {aircraftDocs.map((d: any) => (
                  <tr key={d.doc_id} className="hover:bg-kfl-surface-subtle">
                    <td className="px-4 py-2 text-sm">{d.document_type.replace(/_/g, " ")}</td>
                    <td className="px-4 py-2 text-sm font-mono">{d.document_number || "—"}</td>
                    <td className="px-4 py-2 text-sm">{d.issuing_authority || "—"}</td>
                    <td className="px-4 py-2 text-sm">{d.issue_date || "—"}</td>
                    <td className="px-4 py-2 text-sm">{d.expiry_date || "Permanent"}</td>
                    <td className={`px-4 py-2 text-sm ${d.expiry_date ? statusColor(daysUntil(d.expiry_date)) : "text-gray-600"}`}>
                      {d.expiry_date ? daysUntil(d.expiry_date) : "N/A"}
                    </td>
                    <td className="px-4 py-2 text-sm">{d.status}</td>
                  </tr>
                ))}
                {aircraftDocs.length === 0 && <tr><td colSpan={7} className="px-4 py-6 text-center text-kfl-muted">No documents found.</td></tr>}
              </tbody>
            </table>
          </div>
        </>
      )}
      <RenewalProgressModal open={showRenewalModal} onClose={() => setShowRenewalModal(false)} />
    </div>
  );
}

export default AircraftInsurance;
