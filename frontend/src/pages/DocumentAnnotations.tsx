import { useState } from "react";
import { useParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { List, Plus, Edit2, Trash2, Check } from "lucide-react";
import { listDocuments } from "../api/documents";
import { p2Api } from "../api/p2";
import { Modal } from "../components/ui/Modal";
import FormField from "../components/ui/FormField";
import { useValidation } from "../utils/validation";
import { useToast } from "../components/ui/Toast";
import { useUnsavedChanges } from "../hooks/useUnsavedChanges";
import { useAuth } from "../auth/AuthContext";
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

const ANNOTATION_TYPES = ["comment", "correction", "question", "observation"];
const ANNOTATION_STATUSES = ["open", "resolved", "dismissed"];

export function DocumentAnnotations() {
  const { toast } = useToast();
  const { hasPermission } = useAuth();
  const { docId: routeDocId } = useParams<{ docId: string }>();
  const qc = useQueryClient();
  const canAnnotate = hasPermission("document:annotate");
  const [docId, setDocId] = useState(routeDocId ?? "");
  const [showForm, setShowForm] = useState(false);
  const [editId, setEditId] = useState<string | null>(null);
  const [filterStatus, setFilterStatus] = useState("");
  const [form, setForm] = useState({
    annotation_type: "comment",
    target_ref: "",
    selected_text: "",
    content: "",
    status: "open",
  });
  const [formError, setFormError] = useState("");

  const { data: docs = [] } = useQuery({
    queryKey: ["documents"],
    queryFn: () => listDocuments().then((page) => page.data),
  });

  const currentDoc = docs.find((d) => d.document_id === docId);

  const { data: annotations = [], isLoading } = useQuery({
    queryKey: ["annotations", docId, filterStatus],
    queryFn: () => {
      if (!docId) return Promise.resolve([]);
      return p2Api.listAnnotations(docId, filterStatus || undefined);
    },
    enabled: !!docId && canAnnotate,
  });

  useUnsavedChanges(showForm || editId !== null);

  const setField = <K extends keyof typeof form>(key: K, value: (typeof form)[K]) => {
    setForm(prev => ({ ...prev, [key]: value }));
  };

  const createMutation = useMutation({
    mutationFn: (data: any) =>
      p2Api.createAnnotation(docId, data).then((r: any) => r.data),
    onMutate: async (variables) => {
      await qc.cancelQueries({ queryKey: ["annotations", docId, filterStatus] });
      const previous = qc.getQueryData<any[]>(["annotations", docId, filterStatus]) ?? [];
      const optimistic: any = {
        annotation_id: `opt-${Date.now()}`,
        annotation_type: variables.annotation_type,
        target_ref: variables.target_ref,
        selected_text: variables.selected_text,
        content: variables.content,
        status: "open",
        author_id: "(you)",
        created_by: "(you)",
        created_at: new Date().toISOString(),
      };
      qc.setQueryData(["annotations", docId, filterStatus], [...previous, optimistic]);
      return { previous };
    },
    onError: (_err, _variables, ctx) => {
      qc.setQueryData(["annotations", docId, filterStatus], ctx?.previous ?? []);
      setFormError("Failed to add annotation. Please check your entries and try again.");
    },
    onSuccess: () => {
      setShowForm(false);
      setFormError("");
      setForm({
        annotation_type: "comment",
        target_ref: "",
        selected_text: "",
        content: "",
        status: "open",
      });
      toast({ title: "Annotation added", type: "success" });
    },
    onSettled: () => {
      qc.invalidateQueries({ queryKey: ["annotations", docId] });
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: any }) =>
      p2Api.updateAnnotation(id, data).then((r: any) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["annotations", docId] });
      setEditId(null);
      toast({ title: "Annotation updated", type: "success" });
    },
    onError: () => {
      setFormError("Failed to update annotation.");
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => p2Api.deleteAnnotation(id).then((r: any) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["annotations", docId] });
      toast({ title: "Annotation deleted", type: "success" });
    },
    onError: () => {
      setFormError("Failed to delete annotation.");
    },
  });

  const formRules = {
    target_ref: { required: true, minLength: 2 },
    content: { required: true },
    annotation_type: { required: true },
  } as const;

  const { errors: formErrors, isValid: formIsValid } = useValidation(form, formRules);

  const handleCreate = () => {
    setFormError("");
    if (!formIsValid) {
      setFormError("Please complete all required fields.");
      return;
    }
    createMutation.mutate({
      annotation_type: form.annotation_type,
      target_ref: form.target_ref,
      selected_text: form.selected_text,
      content: form.content,
    });
  };

  const handleUpdate = () => {
    setFormError("");
    if (!editId) return;
    updateMutation.mutate({ id: editId, data: { ...form } });
  };

  const handleDelete = (id: string) => {
    if (!window.confirm("Delete this annotation? This cannot be undone.")) return;
    deleteMutation.mutate(id);
  };

  const handleResolve = (id: string) => {
    updateMutation.mutate({ id, data: { status: "resolved" } });
  };

  const statusColor = (s: string) => {
    if (s === "resolved") return "bg-kfl-status-success-bg text-kfl-status-success";
    if (s === "dismissed") return "bg-kfl-surface-subtle text-kfl-muted";
    return "bg-kfl-status-warning-bg text-kfl-status-warning";
  };

  const typeLabel = (t: string) => t.charAt(0).toUpperCase() + t.slice(1).replace(/_/g, " ");

  if (isLoading) return <div className="p-8 text-kfl-muted">Loading annotations…</div>;

  return (
    <div className="app-page">
      <header className="app-page-header">
        <div>
          <div className="app-eyebrow">Document Control</div>
          <h1 className="app-title">Document Annotations</h1>
          <p className="app-subtitle">
            Add, review, and manage annotations on controlled documents.
          </p>
        </div>
        <div className="flex gap-2">
          {canAnnotate && (
            <Button onClick={() => setShowForm(true)} variant="default" size="sm" className="flex items-center gap-1">
              <Plus size={14} /> New Annotation
            </Button>
          )}
        </div>
      </header>

      {/* Document selector */}
      <div className="app-surface p-4 mb-4 border-b border-kfl-border">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div className="flex items-center gap-2">
            <List size={14} className="shrink-0 text-kfl-muted" />
            <span className="text-sm font-medium text-kfl-text">Document</span>
          </div>
          <Select
            onValueChange={e => {
              setDocId(e);
              qc.invalidateQueries({ queryKey: ["annotations", e, filterStatus] });
            }}
            defaultValue={docId || ""}
          >
            <SelectTrigger className="w-full max-w-md text-sm">
              <SelectValue placeholder={currentDoc ? `${currentDoc.document_id} — ${currentDoc.title}` : "Select a document"} />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="">All documents</SelectItem>
              {docs.map((d) => (
                <SelectItem key={d.document_id} value={d.document_id}>
                  {d.document_id} — {d.title}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {docId && (
        <>
          <div className="flex gap-2 mb-4">
            {canAnnotate && (
              <Button onClick={() => setShowForm(true)} variant="default" size="sm" className="flex items-center gap-1 text-sm">
                <Plus size={14} /> New Annotation
              </Button>
            )}
            {[...ANNOTATION_STATUSES, ""].map((s) => (
              <Button
                key={s}
                variant={filterStatus === s ? "default" : "outline"}
                size="sm"
                onClick={() => setFilterStatus(s)}
              >
                {s || "All"}
              </Button>
            ))}
          </div>

          {/* Create Annotation Modal */}
          <Modal
            open={showForm && canAnnotate}
            onClose={() => setShowForm(false)}
            title="Create Annotation"
            description="Add a note against a specific reference in the document. Choose the annotation type, identify the target reference, and enter your comment."
          >
            {formError && (
              <div role="alert" className="mb-3 p-3 rounded-md border border-kfl-status-danger-bg bg-kfl-status-danger-bg/20 text-kfl-status-danger text-sm">
                {formError}
              </div>
            )}
            <div className="grid grid-cols-2 gap-3">
              <FormField htmlFor="ann_type" label="Annotation type" required>
                <Select
                  onValueChange={e => setField("annotation_type", e)}
                  defaultValue={form.annotation_type}
                >
                  <SelectTrigger id="ann_type">
                    <SelectValue placeholder="Select a type" />
                  </SelectTrigger>
                  <SelectContent>
                    {ANNOTATION_TYPES.map((t) => (
                      <SelectItem key={t} value={t}>
                        {typeLabel(t)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {formErrors.annotation_type && (
                  <p id="ann_type-error" className="text-[11px] text-kfl-status-danger mt-1">
                    {formErrors.annotation_type}
                  </p>
                )}
              </FormField>
              <FormField htmlFor="ann_status" label="Status">
                <Select
                  onValueChange={e => setField("status", e)}
                  defaultValue={form.status}
                >
                  <SelectTrigger id="ann_status">
                    <SelectValue placeholder="Select a status" />
                  </SelectTrigger>
                  <SelectContent>
                    {ANNOTATION_STATUSES.map((s) => (
                      <SelectItem key={s} value={s}>{typeLabel(s)}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </FormField>
              <FormField htmlFor="ann_target" label="Target reference" hint="Section, page, block, or line being annotated." required>
                <Input
                  id="ann_target"
                  name="target_ref"
                  aria-describedby="ann_target-error"
                  aria-invalid={!!formErrors.target_ref}
                  className={formErrors.target_ref ? "border-rose-400" : ""}
                  placeholder="Section 4.2 · line 12"
                  value={form.target_ref}
                  onChange={e => setField("target_ref", e.target.value)}
                />
                {formErrors.target_ref && (
                  <p id="ann_target-error" className="text-[11px] text-kfl-status-danger mt-1">
                    {formErrors.target_ref}
                  </p>
                )}
              </FormField>
              <FormField htmlFor="ann_selected" label="Selected text" hint="Exact quoted text being annotated (optional).">
                <Input
                  id="ann_selected"
                  name="selected_text"
                  placeholder="Quote the relevant text…"
                  value={form.selected_text}
                  onChange={e => setField("selected_text", e.target.value)}
                />
              </FormField>
              <FormField htmlFor="ann_content" label="Content" hint="Your annotation comment." required>
                <Input
                  id="ann_content"
                  name="content"
                  aria-describedby="ann_content-error"
                  aria-invalid={!!formErrors.content}
                  className={formErrors.content ? "border-rose-400" : ""}
                  placeholder="Enter your annotation…"
                  value={form.content}
                  onChange={e => setField("content", e.target.value)}
                />
                {formErrors.content && (
                  <p id="ann_content-error" className="text-[11px] text-kfl-status-danger mt-1">
                    {formErrors.content}
                  </p>
                )}
              </FormField>
            </div>
            <div className="mt-4 flex gap-2 justify-end">
              <Button
                variant="outline"
                size="sm"
                onClick={() => { setShowForm(false); }}
              >
                Cancel
              </Button>
              {canAnnotate && (
                <Button
                  onClick={handleCreate}
                  variant="default"
                  size="sm"
                  disabled={createMutation.isPending}
                >
                  {createMutation.isPending ? "Saving…" : "Create Annotation"}
                </Button>
              )}
            </div>
          </Modal>

          {/* Edit Annotation Modal */}
          <Modal
            open={editId !== null && canAnnotate}
            onClose={() => setEditId(null)}
            title="Edit Annotation"
            description="Update the annotation content, target reference, type, or status."
          >
            {formError && (
              <div role="alert" className="mb-3 p-3 rounded-md border border-kfl-status-danger-bg bg-kfl-status-danger-bg/20 text-kfl-status-danger text-sm">
                {formError}
              </div>
            )}
            <div className="grid grid-cols-2 gap-3">
              <FormField htmlFor="edit_ann_type" label="Annotation type" required>
                <Select
                  onValueChange={e => setField("annotation_type", e)}
                  defaultValue={form.annotation_type}
                >
                  <SelectTrigger id="edit_ann_type">
                    <SelectValue placeholder="Select a type" />
                  </SelectTrigger>
                  <SelectContent>
                    {ANNOTATION_TYPES.map((t) => (
                      <SelectItem key={t} value={t}>
                        {typeLabel(t)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {formErrors.annotation_type && (
                  <p id="edit_ann_type-error" className="text-[11px] text-kfl-status-danger mt-1">
                    {formErrors.annotation_type}
                  </p>
                )}
              </FormField>
              <FormField htmlFor="edit_ann_status" label="Status" required>
                <Select
                  onValueChange={e => setField("status", e)}
                  defaultValue={form.status}
                >
                  <SelectTrigger id="edit_ann_status">
                    <SelectValue placeholder="Select a status" />
                  </SelectTrigger>
                  <SelectContent>
                    {ANNOTATION_STATUSES.map((s) => (
                      <SelectItem key={s} value={s}>{typeLabel(s)}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {formErrors.status && (
                  <p id="edit_ann_status-error" className="text-[11px] text-kfl-status-danger mt-1">
                    {formErrors.status}
                  </p>
                )}
              </FormField>
              <FormField htmlFor="edit_ann_target" label="Target reference" required>
                <Input
                  id="edit_ann_target"
                  name="target_ref"
                  aria-invalid={!!formErrors.target_ref}
                  className={formErrors.target_ref ? "border-rose-400" : ""}
                  placeholder="Section 4.2 · line 12"
                  value={form.target_ref}
                  onChange={e => setField("target_ref", e.target.value)}
                />
                {formErrors.target_ref && (
                  <p id="edit_ann_target-error" className="text-[11px] text-kfl-status-danger mt-1">
                    {formErrors.target_ref}
                  </p>
                )}
              </FormField>
              <FormField htmlFor="edit_ann_selected" label="Selected text">
                <Input
                  id="edit_ann_selected"
                  name="selected_text"
                  placeholder="Quote the relevant text…"
                  value={form.selected_text}
                  onChange={e => setField("selected_text", e.target.value)}
                />
              </FormField>
              <FormField htmlFor="edit_ann_content" label="Content" required>
                <Input
                  id="edit_ann_content"
                  name="content"
                  aria-invalid={!!formErrors.content}
                  className={formErrors.content ? "border-rose-400" : ""}
                  placeholder="Enter your annotation…"
                  value={form.content}
                  onChange={e => setField("content", e.target.value)}
                />
                {formErrors.content && (
                  <p id="edit_ann_content-error" className="text-[11px] text-kfl-status-danger mt-1">
                    {formErrors.content}
                  </p>
                )}
              </FormField>
            </div>
            <div className="mt-4 flex gap-2 justify-end">
              <Button
                variant="outline"
                size="sm"
                onClick={() => { setEditId(null); }}
              >
                Cancel
              </Button>
              {canAnnotate && (
                <Button
                  onClick={handleUpdate}
                  variant="default"
                  size="sm"
                  disabled={updateMutation.isPending}
                >
                  {updateMutation.isPending ? "Saving…" : "Save Changes"}
                </Button>
              )}
            </div>
          </Modal>

          {/* Annotation list */}
          <div className="app-surface overflow-hidden">
            <div className="border-b border-kfl-border p-4">
              <div className="text-sm text-kfl-muted">
                {currentDoc ? `Annotations for “${currentDoc.title}” (${currentDoc.document_id})` : `No document selected`}
              </div>
            </div>
            {annotations.length === 0 ? (
              <div className="p-8 text-center text-kfl-muted">
                {docId ? "No annotations found for this document." : "Select a document to view annotations."}
              </div>
            ) : (
              <table className="min-w-full">
                <thead className="border-b border-kfl-border bg-kfl-surface-subtle">
                  <tr>
                    <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Type</th>
                    <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Target</th>
                    <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Selected Text</th>
                    <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Content</th>
                    <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Author</th>
                    <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Status</th>
                    <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Created</th>
                    <th className="px-4 py-3 text-right text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-kfl-border">
                  {annotations.map((a: any) => (
                    <tr key={a.annotation_id} className="transition hover:bg-kfl-surface-subtle">
                      <td className="px-4 py-3 text-sm text-kfl-secondary">{typeLabel(a.annotation_type)}</td>
                      <td className="px-4 py-3 text-sm font-mono text-kfl-text">{a.target_ref}</td>
                      <td className="px-4 py-3 text-sm">
                        {a.selected_text ? (
                          <span className="text-kfl-muted line-clamp-1">{a.selected_text}</span>
                        ) : (
                          <span className="text-kfl-muted italic">—</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-sm line-clamp-1">{a.content}</td>
                      <td className="px-4 py-3 text-sm text-kfl-secondary">{a.author_id || a.created_by || "—"}</td>
                      <td className="px-4 py-3">
                        <Badge variant={a.status === "resolved" ? "default" : a.status === "dismissed" ? "secondary" : "outline"} className={`badge ${statusColor(a.status)}`}>
                          {typeLabel(a.status)}
                        </Badge>
                      </td>
                      <td className="px-4 py-3 text-sm text-kfl-secondary">{a.created_at}</td>
                      <td className="px-4 py-3 text-right text-sm">
                        <div className="flex justify-end gap-1">
                          {a.status === "open" && canAnnotate && (
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleResolve(a.annotation_id)}
                              className="h-7 w-7 p-0 text-kfl-status-success hover:bg-kfl-status-success-bg/10"
                              title="Mark resolved"
                            >
                              <Check size={12} />
                            </Button>
                          )}
                          {canAnnotate && (
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => {
                                setForm({
                                  annotation_type: a.annotation_type || "comment",
                                  target_ref: a.target_ref || "",
                                  selected_text: a.selected_text || "",
                                  content: a.content || "",
                                  status: a.status || "open",
                                });
                                setEditId(a.annotation_id);
                              }}
                              className="h-7 w-7 p-0 text-kfl-blue hover:bg-kfl-blue/10"
                              title="Edit"
                            >
                              <Edit2 size={12} />
                            </Button>
                          )}
                          {canAnnotate && (
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleDelete(a.annotation_id)}
                              className="h-7 w-7 p-0 text-kfl-status-danger hover:bg-kfl-status-danger-bg/10"
                              title="Delete"
                            >
                              <Trash2 size={12} />
                            </Button>
                          )}
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

export default DocumentAnnotations;
