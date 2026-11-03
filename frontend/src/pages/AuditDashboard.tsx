import { useQuery } from "@tanstack/react-query";
import { auditApi } from "../api/audit";
import { AlertTriangle, BarChart3, ShieldAlert } from "lucide-react";

function MetricCard({ label, value, sublabel, icon: Icon, tone = "blue" }: any) {
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
          <div className="mt-3 text-3xl font-bold tracking-tight text-kfl-text">
            {value}
          </div>
          {sublabel && <div className="mt-1 text-xs text-kfl-muted">{sublabel}</div>}
        </div>
        <div className={`rounded-lg p-2.5 ${tones[tone] || tones.blue}`}>
          <Icon size={19} strokeWidth={1.8} />
        </div>
      </div>
    </div>
  );
}

export function AuditDashboard() {
  const { data: summary, isLoading, isError, refetch, isSuccess } = useQuery({
    queryKey: ["audit-findings-summary"],
    queryFn: () => auditApi.getAuditFindingsSummary(),
  });

  const data = summary as {
    total?: number;
    open?: number;
    closed?: number;
    by_level?: Record<string, number>;
    by_status?: Record<string, number>;
    by_area?: Record<string, number>;
  } | null;

  const total = data?.total ?? 0;
  const open = data?.open ?? 0;
  const closed = data?.closed ?? 0;
  const byLevel = data?.by_level ?? {};
  const byStatus = data?.by_status ?? {};
  const byArea = data?.by_area ?? {};
  const metricValue = (value: number) => isSuccess ? value : "—";

  return (
    <div className="app-page">
      <header className="app-page-header">
        <div>
          <div className="app-eyebrow">Audit Management</div>
          <h1 className="app-title">Audit Dashboard</h1>
          <p className="app-subtitle">
            Overview of audit findings and corrective action status.
          </p>
        </div>
      </header>

      {isLoading && <div className="mb-4 text-sm text-kfl-muted">Loading audit summary…</div>}
      {isError && <div role="alert" className="mb-4 text-sm text-rose-800">Unable to load audit summary. <button type="button" onClick={() => void refetch()} className="font-semibold underline">Retry</button></div>}

      <section className="mb-7 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          label="Total Findings"
          value={metricValue(total)}
          icon={AlertTriangle}
          tone="blue"
        />
        <MetricCard
          label="Open Findings"
          value={metricValue(open)}
          sublabel={isSuccess ? `${total > 0 ? Math.round((open / total) * 100) : 0}% open` : undefined}
          icon={AlertTriangle}
          tone={!isSuccess ? "blue" : open > 0 ? "red" : "green"}
        />
        <MetricCard
          label="Closed Findings"
          value={metricValue(closed)}
          sublabel={isSuccess ? `${total > 0 ? Math.round((closed / total) * 100) : 0}% closed` : undefined}
          icon={BarChart3}
          tone="green"
        />
        <MetricCard
          label="Level 3 (Critical)"
          value={metricValue(byLevel["3"] ?? 0)}
          icon={ShieldAlert}
          tone={!isSuccess ? "blue" : byLevel["3"] ? "red" : "green"}
        />
      </section>

      <section className="mb-7 grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="app-surface overflow-hidden">
          <div className="border-b border-kfl-border p-4">
            <h2 className="text-sm font-bold text-kfl-text uppercase tracking-wider">
              Findings by Level
            </h2>
          </div>
          <div className="p-5">
            {Object.entries(byLevel).map(([level, count]) => (
              <div key={level} className="flex items-center justify-between py-3 border-b border-kfl-border last:border-0">
                <span className="text-sm text-kfl-text">Level {level}</span>
                <span className="font-mono text-[12px] text-kfl-text">{count}</span>
              </div>
            ))}
            {Object.keys(byLevel).length === 0 && (
              <div className="p-5 text-center text-sm text-kfl-muted">
                No data
              </div>
            )}
          </div>
        </div>

        <div className="app-surface overflow-hidden">
          <div className="border-b border-kfl-border p-4">
            <h2 className="text-sm font-bold text-kfl-text uppercase tracking-wider">
              Findings by Area
            </h2>
          </div>
          <div className="p-5">
            {Object.entries(byArea).map(([area, count]) => (
              <div key={area} className="flex items-center justify-between py-3 border-b border-kfl-border last:border-0">
                <span className="text-sm text-kfl-text">{area}</span>
                <span className="font-mono text-[12px] text-kfl-text">{count}</span>
              </div>
            ))}
            {Object.keys(byArea).length === 0 && (
              <div className="p-5 text-center text-sm text-kfl-muted">
                No data
              </div>
            )}
          </div>
        </div>

        <div className="app-surface overflow-hidden">
          <div className="border-b border-kfl-border p-4">
            <h2 className="text-sm font-bold text-kfl-text uppercase tracking-wider">
              Findings by Status
            </h2>
          </div>
          <div className="p-5">
            {Object.entries(byStatus).map(([status, count]) => (
              <div key={status} className="flex items-center justify-between py-3 border-b border-kfl-border last:border-0">
                <span className="text-sm text-kfl-text">
                  {status.replace(/_/g, " ").toUpperCase()}
                </span>
                <span className="font-mono text-[12px] text-kfl-text">{count}</span>
              </div>
            ))}
            {Object.keys(byStatus).length === 0 && (
              <div className="p-5 text-center text-sm text-kfl-muted">
                No data
              </div>
            )}
          </div>
        </div>
      </section>
    </div>
  );
}
