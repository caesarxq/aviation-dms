import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { safetyApi } from "../api/safety";
import { ScrollText } from "lucide-react";

function actionClass(action: string) {
  switch (action.toLowerCase()) {
    case "created": return "app-status app-status-healthy";
    case "updated": return "app-status app-status-warning";
    case "deleted": return "app-status app-status-critical";
    case "approved": return "app-status app-status-healthy";
    case "rejected": return "app-status app-status-critical";
    case "published": return "app-status app-status-healthy";
    default: return "app-status app-status-info";
  }
}

export function AuditTrail() {
  const [entityType, setEntityType] = useState("");
  const [entityId, setEntityId] = useState("");
  const [limit] = useState(100);

  const { data: events = [], isLoading } = useQuery({
    queryKey: ["audit-events", entityType, entityId, limit],
    queryFn: () => safetyApi.listAuditEvents({ entity_type: entityType || undefined, entity_id: entityId || undefined, limit }),
  });

  return (
    <div className="app-page">
      <header className="app-page-header">
        <div>
          <div className="app-eyebrow">Compliance & Governance</div>
          <h1 className="app-title">Audit Trail</h1>
          <p className="app-subtitle">Immutable record of all system actions and state changes for compliance review.</p>
        </div>
      </header>

      <section className="mb-5 grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="app-surface p-4">
          <div className="app-label">Total Events</div>
          <div className="mt-2 text-2xl font-bold text-kfl-text">{events.length}</div>
        </div>
        <div className="app-surface p-4">
          <div className="app-label">Entity Types</div>
          <div className="mt-2 text-2xl font-bold text-kfl-text">{new Set(events.map((e: any) => e.entity_type)).size}</div>
        </div>
        <div className="app-surface p-4">
          <div className="app-label">Recent Actions</div>
          <div className="mt-2 text-2xl font-bold text-kfl-text">{events.filter((e: any) => new Date(e.timestamp).getTime() > Date.now() - 86400000).length}</div>
        </div>
      </section>

      <section className="app-surface overflow-hidden">
        <div className="flex flex-col gap-3 border-b border-kfl-border p-4 md:flex-row md:items-center md:justify-between">
          <div className="text-sm font-semibold text-kfl-text">Audit Events</div>
          <div className="flex gap-2">
            <input
              id="audit_entity_type"
              name="entity_type"
              placeholder="Entity type (e.g. document)"
              className="app-input w-full md:w-auto"
              value={entityType}
              onChange={(e) => setEntityType(e.target.value)}
            />
            <input
              id="audit_entity_id"
              name="entity_id"
              placeholder="Entity ID"
              className="app-input w-full md:w-auto"
              value={entityId}
              onChange={(e) => setEntityId(e.target.value)}
            />
          </div>
        </div>

        {isLoading ? (
          <div className="p-10 text-center text-sm text-kfl-muted">Loading audit trail…</div>
        ) : events.length === 0 ? (
          <div className="app-surface border-dashed p-10 text-center">
            <ScrollText size={26} className="mx-auto mb-2 text-kfl-muted" />
            <p className="text-sm font-bold text-kfl-text">No audit events found.</p>
            <p className="mt-1 text-xs text-kfl-muted">Adjust filters or perform actions to generate audit records.</p>
          </div>
        ) : (
          <div className="overflow-x-auto" tabIndex={0}>
            <table className="min-w-full">
              <thead className="border-b border-kfl-border bg-kfl-surface-subtle">
                <tr>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Event ID</th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Timestamp</th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Entity</th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Action</th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Actor</th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Details</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-kfl-border">
                {events.map((ev: any) => (
                  <tr key={ev.event_id} className="transition hover:bg-kfl-surface-subtle">
                    <td className="px-4 py-4 font-mono text-[12px] text-kfl-text">{ev.event_id}</td>
                    <td className="px-4 py-4 text-sm text-kfl-secondary whitespace-nowrap">{new Date(ev.timestamp).toLocaleString()}</td>
                    <td className="px-4 py-4 text-sm text-kfl-secondary">
                      <span className="font-medium">{ev.entity_type}</span>
                      <span className="text-kfl-muted ml-1">{ev.entity_id}</span>
                    </td>
                    <td className="px-4 py-4">
                      <span className={actionClass(ev.action)}>{ev.action}</span>
                    </td>
                    <td className="px-4 py-4 text-sm text-kfl-secondary">{ev.actor_id}</td>
                    <td className="px-4 py-4 text-xs text-kfl-muted max-w-xs truncate">{ev.details || "—"}</td>
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
