import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { safetyApi } from "../api/safety";
import { FileText, Clock, ShieldCheck } from "lucide-react";

export function OccurrenceDetail() {
  const { occurrenceId } = useParams();
  const { data: occ, isLoading } = useQuery({
    queryKey: ["occurrence", occurrenceId],
    queryFn: () => safetyApi.getOccurrence(occurrenceId!),
    enabled: !!occurrenceId,
  });

  if (isLoading) return <div className="app-page"><div className="app-surface p-10 text-center text-sm text-kfl-muted">Loading occurrence…</div></div>;
  if (!occ) return <div className="app-page"><div className="app-surface p-10 text-center text-sm text-kfl-muted">Occurrence not found</div></div>;

  return (
    <div className="app-page">
      <header className="app-page-header">
        <div>
          <div className="app-eyebrow">Safety Management</div>
          <h1 className="app-title">{occ.title}</h1>
          <p className="app-subtitle">{occ.serial_number} — {occ.status}</p>
        </div>
        <div className="flex items-center gap-2">
          <span className={severityClass(occ.severity)}>{occ.severity}</span>
        </div>
      </header>

      <section className="mb-5 grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
        <div className="app-surface p-4">
          <div className="app-label">Type</div>
          <div className="mt-2 text-sm font-bold text-kfl-text">{occ.occurrence_type}</div>
        </div>
        <div className="app-surface p-4">
          <div className="app-label">Severity</div>
          <div className="mt-2 flex items-center gap-2">
            <span className={severityClass(occ.severity)}>{occ.severity}</span>
          </div>
        </div>
        <div className="app-surface p-4">
          <div className="app-label">Status</div>
          <div className="mt-2 flex items-center gap-2">
            <span className="app-status app-status-info">{occ.status}</span>
          </div>
        </div>
        <div className="app-surface p-4">
          <div className="app-label">MOR Required</div>
          <div className="mt-2 flex items-center gap-2">
            <ShieldCheck size={16} className="text-kfl-blue" />
            {occ.mor_required ? "Yes" : "No"}
          </div>
        </div>
        <div className="app-surface p-4">
          <div className="app-label">Location</div>
          <div className="mt-2 text-sm font-bold text-kfl-text">{occ.location || "—"}</div>
        </div>
        <div className="app-surface p-4">
          <div className="app-label">Reported</div>
          <div className="mt-2 text-sm font-bold text-kfl-text">{occ.reported_at || "—"}</div>
        </div>
      </section>

      <section className="app-surface overflow-hidden">
        <div className="flex items-start justify-between border-b border-kfl-border p-4">
          <div>
            <div className="flex items-center gap-2">
              <FileText size={18} className="text-kfl-blue" />
              <h2 className="text-base font-bold text-kfl-text">Description</h2>
            </div>
          </div>
        </div>
        <div className="p-5">
          <div className="prose prose-lg max-w-none whitespace-pre-wrap">{occ.description || "No description provided."}</div>
        </div>
      </section>

      <section className="app-surface p-5 overflow-hidden">
        <div className="flex items-start justify-between border-b border-kfl-border p-4 mb-4">
          <div>
            <div className="flex items-center gap-2">
              <Clock size={18} className="text-kfl-blue" />
              <h2 className="text-base font-bold text-kfl-text">Occurrence Details</h2>
            </div>
          </div>
        </div>
        <dl className="grid grid-cols-2 gap-4 text-sm">
          <dt className="font-medium text-kfl-muted">Occurrence ID</dt>
          <dd className="font-mono text-kfl-text">{occ.occurrence_id}</dd>
          <dt className="font-medium text-kfl-muted">Serial Number</dt>
          <dd className="font-mono text-kfl-text">{occ.serial_number}</dd>
          <dt className="font-medium text-kfl-muted">Occurred At</dt>
          <dd className="font-mono text-kfl-text">{occ.occurred_at || "—"}</dd>
          <dt className="font-medium text-kfl-muted">Reporter</dt>
          <dd className="font-mono text-kfl-text">
            {occ.reporter_id === "CONFIDENTIAL" ? (
              <span className="app-status app-status-info">Confidential Reporter</span>
            ) : (
              occ.reporter_id || "—"
            )}
          </dd>
          <dt className="font-medium text-kfl-muted">MOR Required</dt>
          <dd className="font-mono text-kfl-text">{occ.mor_required ? "Yes" : "No"}</dd>
          <dt className="font-medium text-kfl-muted">MOR Deadline</dt>
          <dd className="font-mono text-kfl-text">{occ.mor_deadline || "—"}</dd>
        </dl>
      </section>
    </div>
  );
}

function severityClass(severity: string) {
  switch (severity) {
    case "catastrophic": return "app-status app-status-critical";
    case "hazardous": return "app-status app-status-warning";
    case "major": return "app-status app-status-warning";
    case "minor": return "app-status app-status-info";
    case "negligible": return "app-status app-status-healthy";
    default: return "app-status app-status-info";
  }
}