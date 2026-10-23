import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowUpRight, FileText, Search, ShieldCheck } from "lucide-react";
import api from "../api/client";

export function DocumentCatalogue() {
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const { data: docs = [], isLoading } = useQuery({
    queryKey: ["documents"],
    queryFn: () => api.get("/p0/documents").then((r: any) => r.data),
  });

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
        <Link to="/documents/DOC-001/edit" className="app-btn-primary"><FileText size={16} /> Open editor <ArrowUpRight size={15} /></Link>
      </header>

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
                    <td className="px-4 py-4 text-right text-sm"><div className="flex justify-end gap-3"><Link to={`/documents/${d.document_id}/view`} className="font-semibold text-kfl-blue hover:text-kfl-blue-ink">View</Link><Link to={`/documents/${d.document_id}/edit`} className="font-semibold text-kfl-blue hover:text-kfl-blue-ink">Edit</Link></div></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}