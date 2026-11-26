import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { safetyApi } from "../api/safety";
import { List } from "lucide-react";
import { Badge } from "@/components/ui/badge";

export function AuditTrail() {
  const [entityType, setEntityType] = useState("");
  const [entityId, setEntityId] = useState("");
  const [limit] = useState(100);

  const { data: events = [], isLoading } = useQuery({
    queryKey: ["audit-events-aviation", entityType, entityId, limit],
    queryFn: () =>
      safetyApi.listAuditEvents({
        ...(entityType ? { entity_type: entityType } : {}),
        ...(entityId ? { entity_id: entityId } : {}),
        limit,
      }),
  });

  const ACTION_BADGES: Record<string, string> = {
    created: "bg-kfl-status-info-bg text-kfl-status-info",
    updated: "bg-kfl-status-info-bg text-kfl-status-info",
    approved: "bg-kfl-status-info-bg text-kfl-status-info",
    published: "bg-kfl-status-info-bg text-kfl-status-info",
    closed: "bg-kfl-status-success-bg text-kfl-status-success",
    deleted: "bg-kfl-status-danger-bg text-kfl-status-danger",
    rejected: "bg-kfl-status-danger-bg text-kfl-status-danger",
    submitted: "bg-kfl-status-warning-bg text-kfl-status-warning",
    linked: "bg-kfl-status-warning-bg text-kfl-status-warning",
  };

  return (
    <div className="app-page">
      <header className="app-page-header">
        <div>
          <div className="app-eyebrow">Audit Management</div>
          <h1 className="app-title">Aviation Audit Trail</h1>
          <p className="app-subtitle">
            Aviation audit events: findings, corrective actions, risk assessments,
            missions, occurrences, hazards, and safety actions. Department heads see
            events for their aviation entity types only.
          </p>
        </div>
      </header>

      <section className="app-surface overflow-hidden">
        <div className="flex flex-col gap-3 border-b border-kfl-border p-4 md:flex-row md:items-center md:justify-between">
          <div className="text-sm font-semibold text-kfl-text">Aviation Audit Events</div>
          <div className="flex gap-2">
            <input
              id="audit_entity_type"
              name="entity_type"
              placeholder="Entity type (e.g. audit_finding)"
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
          <div className="p-10 text-center text-sm text-kfl-muted">Loading audit trail</div>
        ) : events.length === 0 ? (
          <div className="app-surface border-dashed p-10 text-center">
            <List size={26} className="mx-auto mb-2 text-kfl-muted" />
            <p className="text-sm font-bold text-kfl-text">No aviation audit events found.</p>
            <p className="mt-1 text-xs text-kfl-muted">
              Adjust filters or perform actions to generate audit records.
            </p>
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
                      <Badge
                        variant="default"
                        className={`badge ${ACTION_BADGES[ev.action] ?? "bg-kfl-surface-subtle text-kfl-muted"}`}
                      >
                        {ev.action}
                      </Badge>
                    </td>
                    <td className="px-4 py-4 text-sm text-kfl-secondary">{ev.actor_id}</td>
                    <td className="px-4 py-4 text-xs text-kfl-muted max-w-xs truncate">{ev.details || "N/A"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
      }
      </section>
    </div>
  );
}
