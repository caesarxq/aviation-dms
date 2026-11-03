import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowUpRight, FileText, Search, ShieldCheck, Plus, Shuffle } from "lucide-react";
import api from "../api/client";
import { Modal } from "../components/ui/Modal";
import FormField from "../components/ui/FormField";
import { useValidation } from "../utils/validation";
import { useToast } from "../components/ui/Toast";
import { VersionDiffModal } from "../components/ui/modals/VersionDiffModal";
import { useUnsavedChanges } from "../hooks/useUnsavedChanges";
import { useAuth } from "../auth/AuthContext";

export function DocumentCatalogue() {
  const { toast } = useToast();
  const { hasPermission } = useAuth();
  const canCreate = hasPermission("document:create");
  const canUpdate = hasPermission("document:update");
  const canEdit = canUpdate || hasPermission("document:propose");
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [showNewDoc, setShowNewDoc] = useState(false);
  const [showVersionDiffModal, setShowVersionDiffModal] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [newDocForm, setNewDocForm] = useState({
    document_id: "", title: "", doc_class: "manual", classification: "S2",
    kcaa_approval_required: false, review_due_date: "", status: "draft",
  });
  const [newDocError, setNewDocError] = useState("");
  const qc = useQueryClient();
  const { data: docs = [], isLoading } = useQuery({
    queryKey: ["documents"],
    queryFn: () => api.get("/p0/documents").then((r: any) => r.data),
  });

  useUnsavedChanges(showNewDoc && dirty);

  const setField = <K extends keyof typeof newDocForm>(key: K, value: (typeof newDocForm)[K]) => {
    setNewDocForm(prev => ({ ...prev, [key]: value }));
    setDirty(true);
  };

  const createMutation = useMutation({
    mutationFn: (data: any) => api.post("/p0/documents", data).then((r: any) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["documents"] });
      setShowNewDoc(false);
      setDirty(false);
      setNewDocForm({
        document_id: "", title: "", doc_class: "manual", classification: "S2",
        kcaa_approval_required: false, review_due_date: "", status: "draft",
      });
      setNewDocError("");
      toast({ title: "Document created", message: "The new document has been added to the catalogue.", type: "success" });
    },
    onError: () => {
      setNewDocError("Failed to create document. Please check your entries and try again.");
    },
  });

  const newDocRules = {
    document_id: { required: true },
    title: { required: true },
  } as const;

  const { errors: docErrors, isValid: docIsValid } = useValidation(newDocForm, newDocRules);

  const handleCreate = () => {
    setNewDocError("");
    if (!docIsValid) {
      setNewDocError("Please correct the fields marked below.");
      return;
    }
    createMutation.mutate(newDocForm);
  };

  const filteredDocs = useMemo(() => docs.filter((d: any) => {
    const haystack = `${d.title} ${d.document_id} ${d.doc_class}`.toLowerCase();
    return haystack.includes(search.toLowerCase()) && (!status || d.status === status);
  }), [docs, search, status]);

  return (
    <div className="app-page">
      <header className="app-page-header">
        <div>
          <div className="app-eyebrow">Controlled information</div>
          <h1 className="app-title">Document Catalogue</h1>
          <p className="app-subtitle">Find, review, and open the controlled documents that support safe operations.</p>
        </div>
        <div className="flex gap-2">
          {canCreate && <button onClick={() => setShowNewDoc(true)} className="app-btn-secondary flex items-center gap-1">
            <Plus size={16} /> New Document
          </button>}
          <button onClick={() => setShowVersionDiffModal(true)} className="app-btn-secondary">
            <Shuffle size={16} /> Version Diff
          </button>
          {canEdit && <Link to="/documents/DOC-001/edit" className="app-btn-primary"><FileText size={16} /> Open editor <ArrowUpRight size={15} /></Link>}
        </div>
      </header>

      {/* New Document Modal */}
      <Modal open={showNewDoc} onClose={() => setShowNewDoc(false)} title="Create New Document" description="Create the controlled-document record first. Use the official document identifier, choose the document class and classification, and mark KCAA approval when regulatory approval is required.">
        {newDocError && (
          <div className="mb-3 p-3 rounded bg-rose-50/60 border border-rose-200 text-rose-800 text-sm">
            {newDocError}
          </div>
        )}
        <div className="grid grid-cols-2 gap-3">
          <FormField htmlFor="document_id_89" label="Document ID" hint="Use the controlled identifier, for example DOC-016." required>
            <input id="document_id_89" name="document_id" aria-describedby="document_id_89-error" aria-invalid={!!docErrors.document_id} className={`border border-kfl-border rounded p-2 text-sm w-full ${docErrors.document_id ? "border-rose-400" : ""}`} placeholder="DOC-016" value={newDocForm.document_id} onChange={e => setField("document_id", e.target.value)} />
            {docErrors.document_id && <p id="document_id_89-error" className="text-[11px] text-rose-700 mt-1">{docErrors.document_id}</p>}
          </FormField>
          <FormField htmlFor="title_95" label="Document title" required>
            <input id="title_95" name="title" aria-describedby="title_95-error" aria-invalid={!!docErrors.title} className={`border border-kfl-border rounded p-2 text-sm w-full ${docErrors.title ? "border-rose-400" : ""}`} placeholder="Title" value={newDocForm.title} onChange={e => setField("title", e.target.value)} />
            {docErrors.title && <p id="title_95-error" className="text-[11px] text-rose-700 mt-1">{docErrors.title}</p>}
          </FormField>
          <FormField htmlFor="doc_class_101" label="Document class" hint="Choose the controlled-document category.">
            <select id="doc_class_101" name="doc_class" className="border border-kfl-border rounded p-2 text-sm w-full" value={newDocForm.doc_class} onChange={e => setField("doc_class", e.target.value)}>
              <option value="manual">Manual</option><option value="procedure">Procedure</option><option value="form">Form</option><option value="checklist">Checklist</option><option value="report">Report</option>
            </select>
          </FormField>
          <FormField htmlFor="classification_104" label="Classification" hint="Select the highest applicable handling restriction.">
            <select id="classification_104" name="classification" className="border border-kfl-border rounded p-2 text-sm w-full" value={newDocForm.classification} onChange={e => setField("classification", e.target.value)}>
              <option value="S0">S0 Public</option><option value="S1">S1 Internal</option><option value="S2">S2 Confidential</option><option value="S3">S3 Restricted</option><option value="S4">S4 Highly Restricted</option>
            </select>
          </FormField>
          <label className="flex items-center gap-2 text-sm self-end pb-2">
            <input id="kcaa_approval_required_108" name="kcaa_approval_required" type="checkbox" checked={newDocForm.kcaa_approval_required} onChange={e => setField("kcaa_approval_required", e.target.checked)} />
            KCAA approval required
          </label>
          <FormField htmlFor="review_due_date_111" label="Review due date" hint="Set the next controlled-document review date.">
            <input id="review_due_date_111" name="review_due_date" type="date" className="border border-kfl-border rounded p-2 text-sm w-full" value={newDocForm.review_due_date} onChange={e => setField("review_due_date", e.target.value)} />
          </FormField>
        </div>
        <div className="mt-4 flex gap-2 justify-end">
          <button onClick={() => { setShowNewDoc(false); setDirty(false); }} className="app-btn-secondary px-4 py-2 text-sm">Cancel</button>
          <button onClick={handleCreate} className="app-btn-primary px-4 py-2 text-sm" disabled={createMutation.isPending}>
            {createMutation.isPending ? "Creating…" : "Create Document"}
          </button>
        </div>
      </Modal>

      <section className="mb-5 grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="app-surface p-4"><div className="app-label">Total documents</div><div className="mt-2 text-2xl font-bold text-kfl-text">{docs.length}</div></div>
        <div className="app-surface p-4"><div className="app-label">Published baseline</div><div className="mt-2 text-2xl font-bold text-emerald-700">{docs.filter((d: any) => d.status === "published").length}</div></div>
        <div className="app-surface p-4"><div className="app-label">KCAA-controlled</div><div className="mt-2 flex items-center gap-2 text-2xl font-bold text-kfl-blue"><ShieldCheck size={21} />{docs.filter((d: any) => d.kcaa_approval_required).length}</div></div>
      </section>

      <section className="app-surface overflow-hidden">
        <div className="flex flex-col gap-3 border-b border-kfl-border p-4 md:flex-row md:items-center md:justify-between">
          <div className="relative min-w-0 flex-1 md:max-w-md">
            <Search size={16} className="pointer-events-none absolute left-3 top-3 text-kfl-muted" />
            <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search title, ID, or class" className="app-input pl-9" aria-label="Search documents" />
          </div>
          <select value={status} onChange={(e) => setStatus(e.target.value)} className="app-input w-full md:w-auto" aria-label="Filter document status">
            <option value="">All statuses</option><option value="published">Published</option><option value="draft">Draft</option><option value="in_review">In review</option>
          </select>
        </div>
        {isLoading ? <div className="p-10 text-center text-sm text-kfl-muted">Loading controlled documents…</div> : filteredDocs.length === 0 ? <div className="p-10 text-center text-sm text-kfl-muted">No documents match this view.</div> : (
          <div className="overflow-x-auto">
            <table className="min-w-full">
              <thead className="border-b border-kfl-border bg-kfl-surface-subtle">
                <tr>{["Title", "Class", "Status", "Classification", "KCAA", "Review Due", "Actions"].map((heading) => <th key={heading} className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">{heading}</th>)}</tr>
              </thead>
              <tbody className="divide-y divide-kfl-border">
                {filteredDocs.map((d: any) => (
                  <tr key={d.document_id} className="transition hover:bg-kfl-surface-subtle">
                    <td className="px-4 py-4"><div className="font-semibold text-kfl-text">{d.title}</div><div className="mt-1 font-mono text-[11px] text-kfl-muted">{d.document_id}</div></td>
                    <td className="px-4 py-4 text-sm text-kfl-secondary">{d.doc_class}</td>
                    <td className="px-4 py-4"><span className={`app-status ${d.status === "published" ? "app-status-healthy" : "app-status-warning"}`}>{d.status}</span></td>
                    <td className="px-4 py-4 text-sm text-kfl-secondary">{d.classification}</td>
                    <td className="px-4 py-4 text-sm text-kfl-secondary">{d.kcaa_approval_required ? "Required" : "No"}</td>
                    <td className="px-4 py-4 text-sm text-kfl-secondary">{d.review_due_date || "—"}</td>
                    <td className="px-4 py-4 text-right text-sm"><div className="flex justify-end gap-3"><Link to={`/documents/${d.document_id}/view`} className="font-semibold text-kfl-blue hover:text-kfl-blue-ink">View</Link>{canEdit && <Link to={`/documents/${d.document_id}/edit`} className="font-semibold text-kfl-blue hover:text-kfl-blue-ink">Edit</Link>}</div></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
      <VersionDiffModal open={showVersionDiffModal} onClose={() => setShowVersionDiffModal(false)} />
    </div>
  );
}

export default DocumentCatalogue;
