import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowUpRight, FileText, ShieldCheck, Plus, Shuffle } from "lucide-react";
import api from "../api/client";
import { listDocuments } from "../api/documents";
import { Modal } from "../components/ui/Modal";
import FormField from "../components/ui/FormField";
import { useValidation } from "../utils/validation";
import { useToast } from "../components/ui/Toast";
import { VersionDiffModal } from "../components/ui/modals/VersionDiffModal";
import { useUnsavedChanges } from "../hooks/useUnsavedChanges";
import { useAuth } from "../auth/AuthContext";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";

const DOCUMENT_PAGE_SIZE = 50;

export function DocumentCatalogue() {
  const { toast } = useToast();
  const { hasPermission } = useAuth();
  const canCreate = hasPermission("document:create");
  const canUpdate = hasPermission("document:update");
  const canEdit = canUpdate || hasPermission("document:propose");
  const [showNewDoc, setShowNewDoc] = useState(false);
  const [documentOffset, setDocumentOffset] = useState(0);
  const [showVersionDiffModal, setShowVersionDiffModal] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [newDocForm, setNewDocForm] = useState({
    document_id: "", title: "", doc_class: "manual", classification: "S2",
    kcaa_approval_required: false, review_due_date: "", status: "draft",
  });
  const [newDocError, setNewDocError] = useState("");
  const qc = useQueryClient();
  const { data: documentPage, isLoading } = useQuery({
    queryKey: ["documents", { limit: DOCUMENT_PAGE_SIZE, offset: documentOffset }],
    queryFn: () => listDocuments({ limit: DOCUMENT_PAGE_SIZE, offset: documentOffset }),
  });
  const docs = documentPage?.data ?? [];

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

  return (
    <div className="app-page">
      <header className="app-page-header">
        <div>
          <div className="app-eyebrow">Controlled information</div>
          <h1 className="app-title">Document Catalogue</h1>
          <p className="app-subtitle">Find, review, and open the controlled documents that support safe operations.</p>
        </div>
        <div className="flex gap-2">
          {canCreate && (
            <Button onClick={() => setShowNewDoc(true)} variant="outline" size="sm">
              <Plus size={16} /> New Document
            </Button>
          )}
          <Button onClick={() => setShowVersionDiffModal(true)} variant="outline" size="sm">
            <Shuffle size={16} /> Version Diff
          </Button>
          {canEdit && (
            <Button asChild variant="default" size="sm" className="flex items-center gap-1">
              <Link to="/documents/DOC-001/edit">
                <FileText size={16} /> Open editor <ArrowUpRight size={15} />
              </Link>
            </Button>
          )}
        </div>
      </header>

      {/* New Document Modal */}
      <Modal open={showNewDoc} onClose={() => setShowNewDoc(false)} title="Create New Document" description="Create the controlled-document record first. Use the official document identifier, choose the document class and classification, and mark KCAA approval when regulatory approval is required.">
        {newDocError && (
          <div className="mb-3 p-3 rounded-md border border-kfl-status-danger-bg bg-kfl-status-danger-bg/20 text-kfl-status-danger text-sm">
            {newDocError}
          </div>
        )}
        <div className="grid grid-cols-2 gap-3">
          <FormField htmlFor="document_id_89" label="Document ID" hint="Use the controlled identifier, for example DOC-016." required>
            <Input id="document_id_89" name="document_id" aria-describedby="document_id_89-error" aria-invalid={!!docErrors.document_id} placeholder="DOC-016" value={newDocForm.document_id} onChange={e => setField("document_id", e.target.value)} />
            {docErrors.document_id && <p id="document_id_89-error" className="text-[11px] text-kfl-status-danger mt-1">{docErrors.document_id}</p>}
          </FormField>
          <FormField htmlFor="title_95" label="Document title" required>
            <Input id="title_95" name="title" aria-describedby="title_95-error" aria-invalid={!!docErrors.title} placeholder="Title" value={newDocForm.title} onChange={e => setField("title", e.target.value)} />
            {docErrors.title && <p id="title_95-error" className="text-[11px] text-kfl-status-danger mt-1">{docErrors.title}</p>}
          </FormField>
          <FormField htmlFor="doc_class_101" label="Document class" hint="Choose the controlled-document category.">
            <Select onValueChange={e => setField("doc_class", e)}>
              <SelectTrigger id="doc_class_101" name="doc_class" aria-describedby="doc_class_101-hint">
                <SelectValue placeholder="Select a class" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="manual">Manual</SelectItem>
                <SelectItem value="procedure">Procedure</SelectItem>
                <SelectItem value="form">Form</SelectItem>
                <SelectItem value="checklist">Checklist</SelectItem>
                <SelectItem value="report">Report</SelectItem>
              </SelectContent>
            </Select>
          </FormField>
          <FormField htmlFor="classification_104" label="Classification" hint="Select the highest applicable handling restriction.">
            <Select onValueChange={e => setField("classification", e)}>
              <SelectTrigger id="classification_104" name="classification" aria-describedby="classification_104-hint">
                <SelectValue placeholder="Select classification" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="S0">S0 Public</SelectItem>
                <SelectItem value="S1">S1 Internal</SelectItem>
                <SelectItem value="S2">S2 Confidential</SelectItem>
                <SelectItem value="S3">S3 Restricted</SelectItem>
                <SelectItem value="S4">S4 Highly Restricted</SelectItem>
              </SelectContent>
            </Select>
          </FormField>
          <div className="flex items-center gap-2 text-sm self-end pb-2">
            <Checkbox id="kcaa_approval_required_108" name="kcaa_approval_required" checked={Boolean(newDocForm.kcaa_approval_required)} onCheckedChange={(checked) => setField("kcaa_approval_required", Boolean(checked))} />
            <Label htmlFor="kcaa_approval_required_108">KCAA approval required</Label>
          </div>
          <FormField htmlFor="review_due_date_111" label="Review due date" hint="Set the next controlled-document review date.">
            <Input type="date" id="review_due_date_111" name="review_due_date" aria-describedby="review_due_date_111-hint" placeholder="YYYY-MM-DD" value={newDocForm.review_due_date} onChange={e => setField("review_due_date", e.target.value)} />
          </FormField>
        </div>
        <div className="mt-4 flex gap-2 justify-end">
          <Button onClick={() => { setShowNewDoc(false); setDirty(false); }} variant="outline" size="sm">Cancel</Button>
          <Button onClick={handleCreate} variant="default" size="sm" disabled={createMutation.isPending}>
            {createMutation.isPending ? "Creating…" : "Create Document"}
          </Button>
        </div>
      </Modal>

      <section className="mb-5 grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="app-surface p-4"><div className="app-label">Total documents</div><div className="mt-2 text-2xl font-bold text-kfl-text">{documentPage?.total ?? 0}</div></div>
        <div className="app-surface p-4"><div className="app-label">Published on this page</div><div className="mt-2 text-2xl font-bold text-kfl-status-success">{docs.filter((d: any) => d.status === "published").length}</div></div>
        <div className="app-surface p-4"><div className="app-label">KCAA-controlled on this page</div><div className="mt-2 flex items-center gap-2 text-2xl font-bold text-kfl-status-info"><ShieldCheck size={21} />{docs.filter((d: any) => d.kcaa_approval_required).length}</div></div>
      </section>

      <section className="app-surface overflow-hidden">
        <div className="flex flex-col gap-3 border-b border-kfl-border p-4 md:flex-row md:items-center md:justify-between">
          <div className="text-sm text-kfl-muted">Use the global search bar for cross-resource filtering, including documents.</div>
        </div>
        {isLoading ? <div className="p-10 text-center text-sm text-kfl-muted">Loading controlled documents…</div> : docs.length === 0 ? <div className="p-10 text-center text-sm text-kfl-muted">No documents in the catalogue.</div> : (
          <div className="overflow-x-auto">
            <table className="min-w-full">
              <thead className="border-b border-kfl-border bg-kfl-surface-subtle">
                <tr>{["Title", "Class", "Status", "Classification", "KCAA", "Review Due", "Actions"].map((heading) => <th key={heading} className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">{heading}</th>)}</tr>
              </thead>
              <tbody className="divide-y divide-kfl-border">
                {docs.map((d: any) => (
                  <tr key={d.document_id} className="transition hover:bg-kfl-surface-subtle">
                    <td className="px-4 py-4"><div className="font-semibold text-kfl-text">{d.title}</div><div className="mt-1 font-mono text-[11px] text-kfl-muted">{d.document_id}</div></td>
                    <td className="px-4 py-4 text-sm text-kfl-secondary">{d.doc_class}</td>
                    <td className="px-4 py-4">
                      <Badge variant={d.status === "published" ? "default" : "outline"} className={d.status === "published" ? "bg-kfl-status-success-bg text-kfl-status-success" : "bg-kfl-status-warning-bg text-kfl-status-warning"}>
                        {d.status}
                      </Badge>
                    </td>
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
        {documentPage && (
          <div className="flex items-center justify-between border-t border-kfl-border px-4 py-3">
            <span className="text-xs text-kfl-muted">
              {documentPage.total === 0 ? "0 documents" : `${documentOffset + 1}–${documentOffset + docs.length} of ${documentPage.total}`}
            </span>
            <div className="flex items-center gap-2">
              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={documentOffset === 0 || isLoading}
                onClick={() => setDocumentOffset((offset) => Math.max(0, offset - DOCUMENT_PAGE_SIZE))}
              >
                Previous
              </Button>
              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={documentOffset + DOCUMENT_PAGE_SIZE >= documentPage.total || isLoading}
                onClick={() => setDocumentOffset((offset) => offset + DOCUMENT_PAGE_SIZE)}
              >
                Next
              </Button>
            </div>
          </div>
        )}
      </section>
      <VersionDiffModal open={showVersionDiffModal} onClose={() => setShowVersionDiffModal(false)} />
    </div>
  );
}

export default DocumentCatalogue;
