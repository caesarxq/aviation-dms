import { useState } from "react";
import { useParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { List, Plus, Edit2, Trash2, AlertTriangle } from "lucide-react";
import api from "../api/client";
import { p2Api } from "../api/p2";
import { Modal } from "../components/ui/Modal";
import FormField from "../components/ui/FormField";
import { useValidation } from "../utils/validation";
import { useToast } from "../components/ui/Toast";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/ui/select";

const AIRCRAFT_DOCUMENT_TYPES = [
  "certificate_of_registration",
  "airworthiness_certificate",
  "radio_license",
  "noise_certificate",
  "insurance_certificate",
  "maintenance_release",
  "weight_and_balance",
  "flight_manual",
  "minimum_equipment_list",
  "other",
];

const DOCUMENT_STATUSES = ["valid", "expiring_soon", "expired", "revoked"];

export function AircraftDocuments() {
  const { toast } = useToast();
  const qc = useQueryClient();
  const { aircraftId: routeAircraftId } = useParams<{ aircraftId: string }>();
  const [aircraftId, setAircraftId] = useState(routeAircraftId ?? "");
  const [showForm, setShowForm] = useState(false);
  const [editId, setEditId] = useState<string | null>(null);
  const [filterType, setFilterType] = useState("");
  const [form, setForm] = useState({
    document_type: "",
    document_number: "",
    issuing_authority: "",
    issue_date: "",
    expiry_date: "",
    status: "valid",
    document_ref: "",
    notes: "",
  });
  const [formError, setFormError] = useState("");

  const { data: aircraft = [] } = useQuery({
    queryKey: ["aircraft"],
    queryFn: () => api.get("/p1/aircraft?limit=100").then((r: any) => r.data),
  });

  const currentAircraft = aircraft.find((a: any) => a.aircraft_id === aircraftId);

  const { data: documents = [], isLoading } = useQuery({
    queryKey: ["aircraft-documents", aircraftId, filterType],
    queryFn: () => {
      if (!aircraftId) return Promise.resolve([]);
      return p2Api.listAircraftDocuments(aircraftId, filterType || undefined);
    },
    enabled: !!aircraftId,
  });

  const { data: expiring = [] } = useQuery({
    queryKey: ["expiring-aircraft-documents"],
    queryFn: () =>
      p2Api.listExpiringAircraftDocuments().then((r: any) => r.data),
  });

  const setField = <K extends keyof typeof form>(key: K, value: (typeof form)[K]) => {
    setForm(prev => ({ ...prev, [key]: value }));
  };

  const createMutation = useMutation({
    mutationFn: (data: any) =>
      p2Api.createAircraftDocument(aircraftId, data).then((r: any) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["aircraft-documents", aircraftId] });
      qc.invalidateQueries({ queryKey: ["expiring-aircraft-documents"] });
      setShowForm(false);
      setFormError("");
      setForm({
        document_type: "",
        document_number: "",
        issuing_authority: "",
        issue_date: "",
        expiry_date: "",
        status: "valid",
        document_ref: "",
        notes: "",
      });
      toast({ title: "Aircraft document added", type: "success" });
    },
    onError: () => {
      setFormError("Failed to add aircraft document. Please check your entries and try again.");
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: any }) =>
      p2Api.updateAircraftDocument(id, data).then((r: any) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["aircraft-documents", aircraftId] });
      qc.invalidateQueries({ queryKey: ["expiring-aircraft-documents"] });
      setEditId(null);
      toast({ title: "Aircraft document updated", type: "success" });
    },
    onError: () => {
      setFormError("Failed to update aircraft document.");
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => p2Api.deleteAircraftDocument(id).then((r: any) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["aircraft-documents", aircraftId] });
      qc.invalidateQueries({ queryKey: ["expiring-aircraft-documents"] });
      toast({ title: "Aircraft document deleted", type: "success" });
    },
    onError: () => {
      setFormError("Failed to delete aircraft document.");
    },
  });

  const formRules = {
    document_type: { required: true },
    document_number: { required: true },
    issuing_authority: { required: true },
    expiry_date: { required: true },
  } as const;

  const { errors: formErrors, isValid: formIsValid } = useValidation(form, formRules);

  const handleCreate = () => {
    setFormError("");
    if (!formIsValid) {
      setFormError("Please complete all required fields.");
      return;
    }
    createMutation.mutate({
      document_type: form.document_type,
      document_number: form.document_number,
      issuing_authority: form.issuing_authority,
      issue_date: form.issue_date,
      expiry_date: form.expiry_date,
      status: form.status,
      document_ref: form.document_ref,
      notes: form.notes,
    });
  };

  const handleUpdate = () => {
    setFormError("");
    if (!editId) return;
    updateMutation.mutate({ id: editId, data: { ...form } });
  };

  const handleDelete = (id: string) => {
    if (!window.confirm("Delete this aircraft document? This cannot be undone.")) return;
    deleteMutation.mutate(id);
  };

  const typeLabel = (t: string) => t.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

  const daysUntil = (date: string) => {
    const d = new Date(date);
    const now = new Date();
    return Math.ceil((d.getTime() - now.getTime()) / (1000 * 60 * 60 * 24));
  };

  const statusColor = (s: string) => {
    if (s === "valid") return "bg-kfl-status-info-bg text-kfl-status-info";
    if (s === "expiring_soon") return "bg-kfl-status-warning-bg text-kfl-status-warning";
    if (s === "expired") return "bg-kfl-status-danger-bg text-kfl-status-danger";
    return "bg-kfl-surface-subtle text-kfl-muted";
  };

  if (isLoading) return <div className="p-8 text-kfl-muted">Loading aircraft documents…</div>;

  return (
    <div className="app-page">
      <header className="app-page-header">
        <div>
          <div className="app-eyebrow">Aircraft</div>
          <h1 className="app-title">Aircraft Documents</h1>
          <p className="app-subtitle">
            Track aircraft documentation, certifications, and expiry dates.
          </p>
        </div>
        <Button onClick={() => setShowForm(true)} variant="default" size="sm" className="flex items-center gap-1">
          <Plus size={14} /> Add Document
        </Button>
      </header>

      {/* Expiry alerts */}
      {expiring.length > 0 && (
        <div className="app-surface p-4 mb-4 border-l-4 border-kfl-status-danger-bg">
          <h3 className="font-semibold text-kfl-status-danger flex items-center gap-2 mb-2">
            <AlertTriangle size={16} /> {expiring.length} Aircraft Document(s) Expiring Soon
          </h3>
          <div className="space-y-1">
            {expiring.map((d: any) => (
              <div key={d.doc_id} className="text-sm text-kfl-status-danger">
                {d.document_type} — {d.registration || d.aircraft_id} — expires {d.expiry_date} ({daysUntil(d.expiry_date)} days)
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Aircraft selector */}
      <div className="app-surface p-4 mb-4 border-b border-kfl-border">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <List size={14} className="shrink-0 text-kfl-muted" />
            <span className="text-sm font-medium text-kfl-text">Aircraft</span>
          </div>
          <Select
            onValueChange={e => setAircraftId(e)}
            defaultValue={aircraftId || ""}
          >
            <SelectTrigger className="w-full max-w-md text-sm">
              <SelectValue
                placeholder={
                  currentAircraft
                    ? `${currentAircraft.registration} — ${currentAircraft.model}`
                    : "Select an aircraft"
                }
              />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="">All aircraft</SelectItem>
              {aircraft.map((a: any) => (
                <SelectItem key={a.aircraft_id} value={a.aircraft_id}>
                  {a.registration} — {a.model}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {aircraftId && (
        <>
          <div className="flex gap-2 mb-4">
            <Button onClick={() => setShowForm(true)} variant="default" size="sm" className="flex items-center gap-1 text-sm">
              <Plus size={14} /> Add Document
            </Button>
            {["", ...AIRCRAFT_DOCUMENT_TYPES].map((t) => (
              <Button
                key={t}
                variant={filterType === t ? "default" : "outline"}
                size="sm"
                onClick={() => setFilterType(t)}
              >
                {t || "All types"}
              </Button>
            ))}
          </div>

          {/* Create Aircraft Document Modal */}
          <Modal
            open={showForm}
            onClose={() => setShowForm(false)}
            title="Add Aircraft Document"
            description="Record one aircraft document. Enter the document type, number, issuing authority, and dates exactly as shown on the document."
          >
            {formError && (
              <div role="alert" className="mb-3 p-3 rounded-md border border-kfl-status-danger-bg bg-kfl-status-danger-bg/20 text-kfl-status-danger text-sm">
                {formError}
              </div>
            )}
            <form onSubmit={handleCreate} className="space-y-2">
              <div className="grid grid-cols-2 gap-3">
              <FormField htmlFor="adoc_type" label="Document type" required>
                <Select
                  onValueChange={e => setField("document_type", e)}
                  defaultValue={form.document_type}
                >
                  <SelectTrigger id="adoc_type">
                    <SelectValue placeholder="Select a type" />
                  </SelectTrigger>
                  <SelectContent>
                    {AIRCRAFT_DOCUMENT_TYPES.map((t) => (
                      <SelectItem key={t} value={t}>
                        {typeLabel(t)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {formErrors.document_type && (
                  <p id="adoc_type-error" className="text-[11px] text-kfl-status-danger mt-1">
                    {formErrors.document_type}
                  </p>
                )}
              </FormField>
              <FormField htmlFor="adoc_status" label="Status" required>
                <Select
                  onValueChange={e => setField("status", e)}
                  defaultValue={form.status}
                >
                  <SelectTrigger id="adoc_status">
                    <SelectValue placeholder="Select a status" />
                  </SelectTrigger>
                  <SelectContent>
                    {DOCUMENT_STATUSES.map((s) => (
                      <SelectItem key={s} value={s}>
                        {typeLabel(s)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {formErrors.status && (
                  <p id="adoc_status-error" className="text-[11px] text-kfl-status-danger mt-1">
                    {formErrors.status}
                  </p>
                )}
              </FormField>
              <FormField htmlFor="adoc_number" label="Document number" hint="The document identifier as printed on the document." required>
                <Input
                  id="adoc_number"
                  name="document_number"
                  aria-describedby="adoc_number-error"
                  aria-invalid={!!formErrors.document_number}
                  className={formErrors.document_number ? "border-rose-400" : ""}
                  placeholder="Document number"
                  value={form.document_number}
                  onChange={e => setField("document_number", e.target.value)}
                />
                {formErrors.document_number && (
                  <p id="adoc_number-error" className="text-[11px] text-kfl-status-danger mt-1">
                    {formErrors.document_number}
                  </p>
                )}
              </FormField>
              <FormField htmlFor="adoc_authority" label="Issuing authority" required>
                <Input
                  id="adoc_authority"
                  name="issuing_authority"
                  aria-describedby="adoc_authority-error"
                  aria-invalid={!!formErrors.issuing_authority}
                  className={formErrors.issuing_authority ? "border-rose-400" : ""}
                  placeholder="Issuing authority"
                  value={form.issuing_authority}
                  onChange={e => setField("issuing_authority", e.target.value)}
                />
                {formErrors.issuing_authority && (
                  <p id="adoc_authority-error" className="text-[11px] text-kfl-status-danger mt-1">
                    {formErrors.issuing_authority}
                  </p>
                )}
              </FormField>
              <FormField htmlFor="adoc_issue" label="Issue date">
                <Input
                  id="adoc_issue"
                  name="issue_date"
                  type="date"
                  value={form.issue_date}
                  onChange={e => setField("issue_date", e.target.value)}
                />
              </FormField>
              <FormField htmlFor="adoc_expiry" label="Expiry date" hint="Required for expiry tracking." required>
                <Input
                  id="adoc_expiry"
                  name="expiry_date"
                  type="date"
                  aria-describedby="adoc_expiry-error"
                  aria-invalid={!!formErrors.expiry_date}
                  className={formErrors.expiry_date ? "border-rose-400" : ""}
                  value={form.expiry_date}
                  onChange={e => setField("expiry_date", e.target.value)}
                />
                {formErrors.expiry_date && (
                  <p id="adoc_expiry-error" className="text-[11px] text-kfl-status-danger mt-1">
                    {formErrors.expiry_date}
                  </p>
                )}
              </FormField>
              <FormField htmlFor="adoc_ref" label="Document reference" hint="Internal reference or file number (optional).">
                <Input
                  id="adoc_ref"
                  name="document_ref"
                  placeholder="Internal reference…"
                  value={form.document_ref}
                  onChange={e => setField("document_ref", e.target.value)}
                />
              </FormField>
              <FormField htmlFor="adoc_notes" label="Notes" hint="Additional notes about this document.">
                <Input
                  id="adoc_notes"
                  name="notes"
                  placeholder="Notes…"
                  value={form.notes}
                  onChange={e => setField("notes", e.target.value)}
                />
              </FormField>
            </div>
            <div className="mt-4 flex gap-2 justify-end">
              <Button type="button" variant="outline" size="sm" onClick={() => { setShowForm(false); }}>
                Cancel
              </Button>
              <Button type="submit" variant="default" size="sm" disabled={createMutation.isPending}>
                {createMutation.isPending ? "Saving…" : "Save"}
              </Button>
            </div>
            </form>
          </Modal>

          {/* Edit Aircraft Document Modal */}
          <Modal
            open={editId !== null}
            onClose={() => setEditId(null)}
            title="Edit Aircraft Document"
            description="Update the document details, dates, or status."
          >
            {formError && (
              <div role="alert" className="mb-3 p-3 rounded-md border border-kfl-status-danger-bg bg-kfl-status-danger-bg/20 text-kfl-status-danger text-sm">
                {formError}
              </div>
            )}
            <form onSubmit={handleUpdate} className="space-y-2">
              <div className="grid grid-cols-2 gap-3">
              <FormField htmlFor="edit_adoc_type" label="Document type" required>
                <Select
                  onValueChange={e => setField("document_type", e)}
                  defaultValue={form.document_type}
                >
                  <SelectTrigger id="edit_adoc_type">
                    <SelectValue placeholder="Select a type" />
                  </SelectTrigger>
                  <SelectContent>
                    {AIRCRAFT_DOCUMENT_TYPES.map((t) => (
                      <SelectItem key={t} value={t}>
                        {typeLabel(t)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {formErrors.document_type && (
                  <p id="edit_adoc_type-error" className="text-[11px] text-kfl-status-danger mt-1">
                    {formErrors.document_type}
                  </p>
                )}
              </FormField>
              <FormField htmlFor="edit_adoc_status" label="Status" required>
                <Select
                  onValueChange={e => setField("status", e)}
                  defaultValue={form.status}
                >
                  <SelectTrigger id="edit_adoc_status">
                    <SelectValue placeholder="Select a status" />
                  </SelectTrigger>
                  <SelectContent>
                    {DOCUMENT_STATUSES.map((s) => (
                      <SelectItem key={s} value={s}>
                        {typeLabel(s)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {formErrors.status && (
                  <p id="edit_adoc_status-error" className="text-[11px] text-kfl-status-danger mt-1">
                    {formErrors.status}
                  </p>
                )}
              </FormField>
              <FormField htmlFor="edit_adoc_number" label="Document number" required>
                <Input
                  id="edit_adoc_number"
                  name="document_number"
                  aria-invalid={!!formErrors.document_number}
                  className={formErrors.document_number ? "border-rose-400" : ""}
                  placeholder="Document number"
                  value={form.document_number}
                  onChange={e => setField("document_number", e.target.value)}
                />
                {formErrors.document_number && (
                  <p id="edit_adoc_number-error" className="text-[11px] text-kfl-status-danger mt-1">
                    {formErrors.document_number}
                  </p>
                )}
              </FormField>
              <FormField htmlFor="edit_adoc_authority" label="Issuing authority" required>
                <Input
                  id="edit_adoc_authority"
                  name="issuing_authority"
                  aria-invalid={!!formErrors.issuing_authority}
                  className={formErrors.issuing_authority ? "border-rose-400" : ""}
                  placeholder="Issuing authority"
                  value={form.issuing_authority}
                  onChange={e => setField("issuing_authority", e.target.value)}
                />
                {formErrors.issuing_authority && (
                  <p id="edit_adoc_authority-error" className="text-[11px] text-kfl-status-danger mt-1">
                    {formErrors.issuing_authority}
                  </p>
                )}
              </FormField>
              <FormField htmlFor="edit_adoc_issue" label="Issue date">
                <Input
                  id="edit_adoc_issue"
                  name="issue_date"
                  type="date"
                  value={form.issue_date}
                  onChange={e => setField("issue_date", e.target.value)}
                />
              </FormField>
              <FormField htmlFor="edit_adoc_expiry" label="Expiry date" required>
                <Input
                  id="edit_adoc_expiry"
                  name="expiry_date"
                  type="date"
                  aria-invalid={!!formErrors.expiry_date}
                  className={formErrors.expiry_date ? "border-rose-400" : ""}
                  value={form.expiry_date}
                  onChange={e => setField("expiry_date", e.target.value)}
                />
                {formErrors.expiry_date && (
                  <p id="edit_adoc_expiry-error" className="text-[11px] text-kfl-status-danger mt-1">
                    {formErrors.expiry_date}
                  </p>
                )}
              </FormField>
              <FormField htmlFor="edit_adoc_ref" label="Document reference">
                <Input
                  id="edit_adoc_ref"
                  name="document_ref"
                  placeholder="Internal reference…"
                  value={form.document_ref}
                  onChange={e => setField("document_ref", e.target.value)}
                />
              </FormField>
              <FormField htmlFor="edit_adoc_notes" label="Notes">
                <Input
                  id="edit_adoc_notes"
                  name="notes"
                  placeholder="Notes…"
                  value={form.notes}
                  onChange={e => setField("notes", e.target.value)}
                />
              </FormField>
            </div>
            <div className="mt-4 flex gap-2 justify-end">
              <Button type="button" variant="outline" size="sm" onClick={() => setEditId(null)}>
                Cancel
              </Button>
              <Button type="submit" variant="default" size="sm" disabled={updateMutation.isPending}>
                {updateMutation.isPending ? "Saving…" : "Save Changes"}
              </Button>
            </div>
            </form>
          </Modal>

          {/* Document list */}
          <div className="app-surface overflow-hidden">
            <div className="border-b border-kfl-border p-4">
              <div className="text-sm text-kfl-muted">
                {currentAircraft ? `Documents for ${currentAircraft.registration} — ${currentAircraft.model} (${currentAircraft.aircraft_id})` : `No aircraft selected`}
              </div>
            </div>
            {documents.length === 0 ? (
              <div className="p-8 text-center text-kfl-muted">
                {aircraftId ? "No aircraft documents found." : "Select an aircraft to view documents."}
              </div>
            ) : (
              <table className="min-w-full">
                <thead className="border-b border-kfl-border bg-kfl-surface-subtle">
                  <tr>
                    <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Type</th>
                    <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Number</th>
                    <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Authority</th>
                    <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Issue Date</th>
                    <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Expiry Date</th>
                    <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Status</th>
                    <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Days Left</th>
                    <th className="px-4 py-3 text-right text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-kfl-border">
                  {documents.map((d: any) => (
                    <tr key={d.doc_id} className="transition hover:bg-kfl-surface-subtle">
                      <td className="px-4 py-3 text-sm text-kfl-secondary">{typeLabel(d.document_type)}</td>
                      <td className="px-4 py-3 text-sm font-mono text-kfl-text">{d.document_number || "—"}</td>
                      <td className="px-4 py-3 text-sm text-kfl-secondary">{d.issuing_authority || "—"}</td>
                      <td className="px-4 py-3 text-sm text-kfl-secondary">{d.issue_date || "—"}</td>
                      <td className="px-4 py-3 text-sm text-kfl-secondary">{d.expiry_date || "—"}</td>
                      <td className="px-4 py-3">
                        <Badge variant={d.status === "valid" ? "default" : d.status === "expiring_soon" ? "secondary" : "destructive"} className={`badge ${statusColor(d.status)}`}>
                          {typeLabel(d.status)}
                        </Badge>
                      </td>
                      <td className="px-4 py-3 text-sm">
                        {d.expiry_date ? (
                          <span className={`text-sm ${daysUntil(d.expiry_date) <= 30 ? "text-kfl-status-danger font-bold" : daysUntil(d.expiry_date) <= 90 ? "text-kfl-status-warning" : "text-kfl-status-info"}`}>
                            {daysUntil(d.expiry_date)}
                          </span>
                        ) : (
                          <span className="text-sm text-kfl-muted">—</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-right text-sm">
                        <div className="flex justify-end gap-1">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => {
                              setForm({
                                document_type: d.document_type || "",
                                document_number: d.document_number || "",
                                issuing_authority: d.issuing_authority || "",
                                issue_date: d.issue_date || "",
                                expiry_date: d.expiry_date || "",
                                status: d.status || "valid",
                                document_ref: d.document_ref || "",
                                notes: d.notes || "",
                              });
                              setEditId(d.doc_id);
                            }}
                            className="h-7 w-7 p-0 text-kfl-blue hover:bg-kfl-blue/10"
                            title="Edit"
                          >
                            <Edit2 size={12} />
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleDelete(d.doc_id)}
                            className="h-7 w-7 p-0 text-kfl-status-danger hover:bg-kfl-status-danger-bg/10"
                            title="Delete"
                          >
                            <Trash2 size={12} />
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </>
      )}
    </div>
  );
}

export default AircraftDocuments;
