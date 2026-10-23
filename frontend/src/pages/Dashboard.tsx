import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, ArrowUpRight, CalendarClock, CheckCircle2, FileCheck2, ShieldCheck } from "lucide-react";
import { safetyApi } from "../api/safety";

function MetricCard({ label, value, context, icon: Icon, tone = "blue" }: any) {
  const tones: Record<string, string> = {
    blue: "bg-sky-50 text-kfl-blue",
    green: "bg-emerald-50 text-emerald-700",
    amber: "bg-amber-50 text-amber-700",
    red: "bg-red-50 text-red-700",
  };
  return (
    <div className="app-surface p-5 transition hover:-translate-y-0.5 hover:shadow-card">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="app-label">{label}</div>
          <div className="mt-3 text-3xl font-bold tracking-tight text-kfl-text">{value}</div>
          {context && <div className="mt-1 text-xs text-kfl-muted">{context}</div>}
        </div>
        <div className={`rounded-lg p-2.5 ${tones[tone] || tones.blue}`}>
          <Icon size={19} strokeWidth={1.8} />
        </div>
      </div>
    </div>
  );
}

function priorityClass(priority: string) {
  if (priority === "critical") return "app-status app-status-critical";
  if (priority === "high") return "app-status app-status-warning";
  return "app-status app-status-info";
}

export function Dashboard() {
  const { data: trends, isLoading: trendsLoading } = useQuery({
    queryKey: ["trends"],
    queryFn: () => safetyApi.getTrends(),
  });
  const { data: deadlines, isLoading: deadlinesLoading } = useQuery({
    queryKey: ["deadlines"],
    queryFn: () => safetyApi.getDeadlines(30),
  });

  const hazardTotal = Object.values(trends?.hazards_by_risk_level ?? {}).reduce((a: number, b: any) => a + Number(b || 0), 0);
  const isLoading = trendsLoading || deadlinesLoading;

  return (
    <div className="app-page">
      <header className="app-page-header">
        <div>
          <div className="app-eyebrow">Operations control centre</div>
          <h1 className="app-title">Dashboard</h1>
          <p className="app-subtitle">Good morning, Mohamed. A clear view of safety, compliance, and operational commitments.</p>
        </div>
        <div className="flex items-center gap-2">
          <span className="app-status app-status-healthy">System healthy</span>
          <Link to="/notifications" className="app-btn-secondary">
            View notifications <ArrowUpRight size={15} />
          </Link>
        </div>
      </header>

      <section className="mb-7 grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4" aria-label="Key metrics">
        <MetricCard label="Occurrences (30 days)" value={isLoading ? "—" : trends?.occurrences_last_30_days ?? 0} context="Reported safety events" icon={AlertTriangle} tone="amber" />
        <MetricCard label="Total Hazards" value={isLoading ? "—" : hazardTotal} context="Across active risk registers" icon={ShieldCheck} tone="blue" />
        <MetricCard label="Open Safety Actions" value={isLoading ? "—" : trends?.safety_actions_by_status?.open ?? 0} context="Awaiting completion" icon={CheckCircle2} tone="green" />
        <MetricCard label="Deadlines requiring attention" value={isLoading ? "—" : deadlines?.overdue_count ?? 0} context="Overdue items" icon={CalendarClock} tone={deadlines?.overdue_count ? "red" : "green"} />
      </section>

      <section className="grid grid-cols-1 gap-5 xl:grid-cols-[1.45fr_0.85fr]">
        <div className="app-surface overflow-hidden">
          <div className="flex items-start justify-between gap-4 border-b border-kfl-border px-5 py-4">
            <div>
              <div className="flex items-center gap-2">
                <CalendarClock size={18} className="text-kfl-blue" />
                <h2 className="text-base font-bold text-kfl-text">Upcoming & overdue deadlines</h2>
              </div>
              <p className="mt-1 text-xs text-kfl-muted">The next 30 days across the control system.</p>
            </div>
            <Link to="/notifications" className="text-xs font-bold text-kfl-blue hover:text-kfl-blue-ink">Open centre</Link>
          </div>

          <div className="p-5">
            {deadlines?.overdue?.length > 0 && (
              <div className="mb-5">
                <div className="mb-2 flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-red-700">
                  <AlertTriangle size={14} /> Overdue
                </div>
                <ul className="space-y-2">
                  {deadlines.overdue.slice(0, 5).map((d: any, i: number) => (
                    <li key={`${d.entity_id}-${i}`} className="flex flex-col gap-2 rounded-lg border border-red-100 bg-red-50/70 p-3 sm:flex-row sm:items-center sm:justify-between">
                      <span className="text-sm font-semibold text-kfl-text">{d.title}</span>
                      <span className={priorityClass(d.priority)}>{d.due_date} · {d.priority}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {deadlines?.upcoming?.length > 0 && (
              <div>
                <div className="mb-2 flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-kfl-muted">
                  <FileCheck2 size={14} /> Upcoming
                </div>
                <ul className="divide-y divide-kfl-border rounded-lg border border-kfl-border">
                  {deadlines.upcoming.slice(0, 7).map((d: any, i: number) => (
                    <li key={`${d.entity_id}-${i}`} className="flex flex-col gap-2 p-3 sm:flex-row sm:items-center sm:justify-between">
                      <span className="text-sm text-kfl-text">{d.title}</span>
                      <span className={priorityClass(d.priority)}>{d.due_date}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {!deadlines?.overdue?.length && !deadlines?.upcoming?.length && (
              <div className="rounded-lg border border-dashed border-kfl-border bg-kfl-surface-subtle p-8 text-center">
                <CheckCircle2 className="mx-auto mb-2 text-emerald-600" size={24} />
                <p className="text-sm font-semibold text-kfl-text">No deadlines require attention.</p>
                <p className="mt-1 text-xs text-kfl-muted">The next 30 days are clear.</p>
              </div>
            )}
          </div>
        </div>

        <div className="app-surface p-5">
          <div className="mb-5 flex items-start justify-between">
            <div>
              <div className="app-label">Control posture</div>
              <h2 className="mt-1 text-base font-bold text-kfl-text">Operational readiness</h2>
            </div>
            <ShieldCheck size={21} className="text-emerald-600" />
          </div>
          <div className="space-y-4">
            {[
              ["Document control", "Published baseline available", "healthy"],
              ["Safety reporting", "Occurrence workflow active", "healthy"],
              ["Deadline monitoring", deadlines?.overdue_count ? `${deadlines.overdue_count} overdue item(s)` : "No overdue items", deadlines?.overdue_count ? "critical" : "healthy"],
              ["Notification service", "Scheduler connected", "healthy"],
            ].map(([label, value, tone]) => (
              <div key={label} className="flex items-center justify-between gap-3 border-b border-kfl-border pb-3 last:border-0 last:pb-0">
                <div>
                  <p className="text-sm font-semibold text-kfl-text">{label}</p>
                  <p className="mt-0.5 text-xs text-kfl-muted">{value}</p>
                </div>
                <span className={`app-status ${tone === "critical" ? "app-status-critical" : "app-status-healthy"}`}>{tone === "critical" ? "Action" : "Ready"}</span>
              </div>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}