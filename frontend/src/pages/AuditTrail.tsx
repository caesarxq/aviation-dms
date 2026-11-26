import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { safetyApi } from "../api/safety";
import { ScrollText, Monitor, List } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

export function AuditTrail() {
  const [entityType, setEntityType] = useState("");
  const [entityId, setEntityId] = useState("");
  const [activeTab, setActiveTab] = useState<"system" | "aviation">("system");
  const [limit] = useState(100);

  const { data: events = [], isLoading } = useQuery({
    queryKey: ["audit-events", activeTab, entityType, entityId, limit],
    queryFn: () => safetyApi.listAuditEvents({
      ...(entityType ? { entity_type: entityType } : {}),
      ...(entityId ? { entity_id: entityId } : {}),
      limit,
    }),
  });

  const isSystemTab = activeTab === "system";

  return (
    <div className="app-page">
      <header className="app-page-header">
        <div>
          <div className="app-eyebrow">Compliance & Governance</div>
          <h1 className="app-title">Audit Trail</h1>
          <p className="app-subtitle">System change log and aviation audit events serve different personnel.</p>
        </div>
      </header>

      <div className="flex gap-2 mb-5">
        <Button
          variant={isSystemTab ? "default" : "outline"}
          size="sm"
          onClick={() => setActiveTab("system")}
        >
          <Monitor className="mr-2 h-4 w-4" /> System Audit
        </Button>
        <Button
          variant={!isSystemTab ? "default" : "outline"}
          size="sm"
          onClick={() => setActiveTab("aviation")}
        >
          <List className="mr-2 h-4 w-4" /> Aviation Audits
        </Button>
      </div>

      {isSystemTab && (
        <section className="app-surface overflow-hidden">
          <p className="text-xs text-kfl-muted p-4 border-b border-kfl-border">System administrator only. Database change log — all entity types.</p>
          <div className="flex flex-col gap-3 border-b border-kfl-border p-4 md:flex-row md:items-center md:justify-between">
            <div className="text-sm font-semibold text-kfl-text">System Audit Events</div>
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
                        <Badge variant={ev.action === "deleted" || ev.action === "rejected" ? "destructive" : ev.action === "created" || ev.action === "approved" || ev.action === "published" ? "default" : "secondary"} className={`badge ${ev.action === "deleted" || ev.action === "rejected" ? "bg-kfl-status-danger-bg text-kfl-status-danger" : ev.action === "created" || ev.action === "approved" || ev.action === "published" ? "bg-kfl-status-info-bg text-kfl-status-info" : "bg-kfl-status-warning-bg text-kfl-status-warning"}`}>
                          {ev.action}
                        </Badge>
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
      )}

      {!isSystemTab && (
        <section className="app-surface overflow-hidden">
          <p className="text-xs text-kfl-muted p-4 border-b border-kfl-border">Department heads only. Aviation audit events: findings, corrective actions, risk assessments, missions, occurrences, hazards, safety actions.</p>
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
            <div className="p-10 text-center text-sm text-kfl-muted">Loading audit trail…</div>
          ) : events.length === 0 ? (
            <div className="app-surface border-dashed p-10 text-center">
              <ScrollText size={26} className="mx-auto mb-2 text-kfl-muted" />
              <p className="text-sm font-bold text-kfl-text">No aviation audit events found.</p>
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
                        <Badge variant={ev.action === "deleted" || ev.action === "rejected" ? "destructive" : ev.action === "created" || ev.action === "approved" || ev.action === "published" ? "default" : "secondary"} className={`badge ${ev.action === "deleted" || ev.action === "rejected" ? "bg-kfl-status-danger-bg text-kfl-status-danger" : ev.action === "created" || ev.action === "approved" || ev.action === "published" ? "bg-kfl-status-info-bg text-kfl-status-info" : "bg-kfl-status-warning-bg text-kfl-status-warning"}`}>
                          {ev.action}
                        </Badge>
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
      )}
    </div>
  );
}
