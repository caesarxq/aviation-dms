import { Link } from "react-router-dom";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowUpRight,
  BarChart3,
  CalendarClock,
  CheckCircle2,
  FileCheck2,
  ShieldCheck,
  Users,
  Plane,
  Briefcase,
  Target,
  TrendingUp,
  TrendingDown,
  Wrench,
} from "lucide-react";
import { safetyApi } from "../api/safety";
import { SafetyKPIsModal } from "../components/ui/modals/SafetyKPIsModal";
import { useAuth } from "../auth/AuthContext";
import { ROLE_WORKSPACES } from "../auth/permissions";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

function MetricCard({
  label,
  value,
  context,
  icon: Icon,
  tone = "blue",
  href,
  trend,
}: {
  label: string;
  value: string | number;
  context?: string;
  icon: any;
  tone?: string;
  href?: string;
  trend?: string;
}) {
  const tones: Record<string, string> = {
    blue: "bg-kfl-status-info-bg text-kfl-status-info",
    green: "bg-kfl-status-success-bg text-kfl-status-success",
    amber: "bg-kfl-status-warning-bg text-kfl-status-warning",
    red: "bg-kfl-status-danger-bg text-kfl-status-danger",
  };
  const trendTone = trend === "up" ? "text-emerald-600" : trend === "down" ? "text-rose-600" : "text-kfl-muted";
  const trendIcon = trend === "up" ? <TrendingUp size={12} /> : trend === "down" ? <TrendingDown size={12} /> : null;

  const CardContent = (
    <div className="flex items-start justify-between gap-3">
      <div>
        <div className="app-label">{label}</div>
        <div className="mt-3 text-3xl font-bold tracking-tight text-kfl-text">{value}</div>
        {context && <div className="mt-1 text-xs text-kfl-muted">{context}</div>}
        {trend && (
          <div className="mt-1 flex items-center gap-1">
            {trendIcon}
            <span className={`text-xs font-semibold ${trendTone}`}>{trend}</span>
          </div>
        )}
      </div>
      <div className={`rounded-lg p-2.5 ${tones[tone] || tones.blue}`}>
        <Icon size={19} strokeWidth={1.8} />
      </div>
    </div>
  );

  if (href) {
    return (
      <Link to={href} className="block">
        <div className="app-surface p-5 transition hover:-translate-y-0.5 hover:shadow-card cursor-pointer border border-kfl-border hover:border-kfl-blue rounded-lg">
          {CardContent}
        </div>
      </Link>
    );
  }
  return (
    <div className="app-surface p-5 transition hover:-translate-y-0.5 hover:shadow-card">
      {CardContent}
    </div>
  );
}

function priorityClass(priority: string) {
  if (priority === "critical") return "badge badge-destructive";
  if (priority === "high") return "badge badge-secondary";
  return "badge badge-outline";
}

const ROLE_DASHBOARD_CONFIG: Record<string, {
  metrics: Array<{ label: string; valueKey: string; context: string; icon: any; tone: string; href: string; trendKey?: string }>;
  quickActions: Array<{ label: string; href: string; icon: any }>;
}> = {
  head_operations: {
    metrics: [
      { label: "Active Missions", valueKey: "missions_count", context: "Current operations", icon: Plane, tone: "blue", href: "/missions?status=in_progress", trendKey: "missions_trend" },
      { label: "Crew On Duty", valueKey: "crew_on_duty", context: "FDTL-compliant assignments", icon: Users, tone: "green", href: "/duties", trendKey: "crew_trend" },
    ],
    quickActions: [
      { label: "New Mission", href: "/missions", icon: Plane },
      { label: "Release Flight", href: "/missions", icon: Briefcase },
    ],
  },
  head_safety: {
    metrics: [
      { label: "Open Occurrences", valueKey: "open_occurrences", context: "Awaiting classification", icon: AlertTriangle, tone: "amber", href: "/occurrences?status=reported", trendKey: "occurrences_trend" },
      { label: "Safety Actions Overdue", valueKey: "safety_actions_overdue", context: "Past due date", icon: CheckCircle2, tone: "red", href: "/safety-actions?status=overdue", trendKey: "safety_actions_trend" },
    ],
    quickActions: [
      { label: "Report Occurrence", href: "/occurrences", icon: AlertTriangle },
      { label: "Review Hazard", href: "/hazards", icon: ShieldCheck },
    ],
  },
  head_quality: {
    metrics: [
      { label: "Audit Findings Open", valueKey: "audit_findings_open", context: "Pending closure", icon: ShieldCheck, tone: "amber", href: "/audit-findings?status=open", trendKey: "findings_trend" },
      { label: "Quality Audits Due", valueKey: "quality_audits_due", context: "Scheduled this month", icon: Briefcase, tone: "blue", href: "/quality-audits?status=planned", trendKey: "audits_trend" },
    ],
    quickActions: [
      { label: "New Audit", href: "/audit-reports", icon: Briefcase },
      { label: "Review Findings", href: "/audit-findings?status=open", icon: ShieldCheck },
    ],
  },
  accountable_manager: {
    metrics: [
      { label: "Audit Findings Open", valueKey: "audit_findings_open", context: "Pending closure", icon: ShieldCheck, tone: "amber", href: "/audit-findings?status=open", trendKey: "findings_trend" },
      { label: "Quality Audits Due", valueKey: "quality_audits_due", context: "Scheduled this month", icon: Briefcase, tone: "blue", href: "/quality-audits?status=planned", trendKey: "audits_trend" },
    ],
    quickActions: [
      { label: "Review Compliance", href: "/compliance", icon: FileCheck2 },
      { label: "View Reports", href: "/audit-reports", icon: BarChart3 },
    ],
  },
  head_maintenance: {
    metrics: [
      { label: "Aircraft in Service", valueKey: "aircraft_in_service", context: "Airworthy fleet", icon: Plane, tone: "green", href: "/roc?status=serviceable", trendKey: "fleet_trend" },
      { label: "Maintenance Due", valueKey: "maintenance_due", context: "Scheduled inspections", icon: Wrench, tone: "amber", href: "/maintenance", trendKey: "maintenance_trend" },
    ],
    quickActions: [
      { label: "Manage Aircraft", href: "/roc", icon: Plane },
      { label: "Schedule Maintenance", href: "/maintenance", icon: Wrench },
    ],
  },
  head_training: {
    metrics: [
      { label: "Personnel Qualified", valueKey: "personnel_qualified", context: "Current qualifications", icon: Target, tone: "green", href: "/personnel-licenses?status=valid", trendKey: "training_trend" },
      { label: "Training Due", valueKey: "training_due", context: "Recency expiring", icon: CalendarClock, tone: "amber", href: "/training?expiring=30", trendKey: "training_due_trend" },
    ],
    quickActions: [
      { label: "Manage Licenses", href: "/personnel-licenses", icon: Target },
      { label: "View Training", href: "/training", icon: CalendarClock },
    ],
  },
  dg_coordinator: {
    metrics: [
      { label: "DG Shipments Active", valueKey: "dg_shipments_active", context: "In transit", icon: Plane, tone: "amber", href: "/dangerous-goods", trendKey: "dg_trend" },
      { label: "DG Training Current", valueKey: "dg_training_current", context: "Certified staff", icon: Users, tone: "green", href: "/training", trendKey: "dg_training_trend" },
    ],
    quickActions: [
      { label: "DG Shipments", href: "/dangerous-goods", icon: Plane },
      { label: "DG Acceptance", href: "/dangerous-goods", icon: ShieldCheck },
    ],
  },
  head_security: {
    metrics: [
      { label: "Security Reviews Open", valueKey: "security_reviews_open", context: "Pending action", icon: ShieldCheck, tone: "amber", href: "/security-reviews", trendKey: "security_trend" },
      { label: "Incidents Reported", valueKey: "security_incidents", context: "Last 30 days", icon: AlertTriangle, tone: "red", href: "/security", trendKey: "security_incidents_trend" },
    ],
    quickActions: [
      { label: "Security Reviews", href: "/security-reviews", icon: ShieldCheck },
      { label: "Security Incidents", href: "/security", icon: AlertTriangle },
    ],
  },
  records_custodian: {
    metrics: [
      { label: "Documents in Catalogue", valueKey: "documents_count", context: "Controlled documents", icon: FileCheck2, tone: "blue", href: "/documents", trendKey: "documents_trend" },
      { label: "Distributions Pending", valueKey: "distributions_pending", context: "Awaiting release", icon: Plane, tone: "amber", href: "/distributions?status=pending", trendKey: "distributions_trend" },
    ],
    quickActions: [
      { label: "Documents", href: "/documents", icon: FileCheck2 },
      { label: "Distributions", href: "/distributions", icon: Plane },
    ],
  },
  independent_auditor: {
    metrics: [
      { label: "Audit Reports Open", valueKey: "audit_reports_open", context: "Awaiting review", icon: Briefcase, tone: "blue", href: "/audit-reports?status=open", trendKey: "audit_reports_trend" },
      { label: "Findings Unresolved", valueKey: "findings_unresolved", context: "Not yet closed", icon: AlertTriangle, tone: "red", href: "/audit-findings?status=open", trendKey: "findings_trend" },
    ],
    quickActions: [
      { label: "Audit Reports", href: "/audit-reports", icon: Briefcase },
      { label: "Findings", href: "/audit-findings", icon: AlertTriangle },
    ],
  },
};

function getFallbackMetrics(trends: any, deadlines: any, trendsLoading: boolean, deadlinesLoading: boolean, trendsError: any, deadlinesError: any) {
  const showUnavailable = trendsLoading || trendsError || deadlinesLoading || deadlinesError;
  const hazardTotal = Object.values(trends?.hazards_by_risk_level ?? {}).reduce((a: number, b: any) => a + Number(b || 0), 0);
  return [
    { label: "Occurrences (30 days)", value: showUnavailable ? (trendsLoading ? "—" : "Unavailable") : trends?.occurrences_last_30_days ?? 0, context: "Reported safety events", icon: AlertTriangle, tone: "amber", href: "/occurrences" },
    { label: "Total Hazards", value: trendsLoading ? "—" : trendsError ? "Unavailable" : hazardTotal, context: "Across active risk registers", icon: ShieldCheck, tone: "blue", href: "/hazards" },
    { label: "Open Safety Actions", value: trendsLoading ? "—" : trendsError ? "Unavailable" : trends?.safety_actions_by_status?.open ?? 0, context: "Awaiting completion", icon: CheckCircle2, tone: "blue", href: "/safety-actions" },
    { label: "Deadlines requiring attention", value: deadlinesLoading ? "—" : deadlinesError ? "Unavailable" : deadlines?.overdue_count ?? 0, context: deadlinesError ? "Deadline data unavailable" : "Overdue items", icon: CalendarClock, tone: deadlinesError ? "blue" : deadlines?.overdue_count ? "red" : "green", href: "/notifications" },
  ];
}

export function Dashboard() {
  const { profile } = useAuth();
  const { data: trends, isLoading: trendsLoading, isError: trendsError } = useQuery({
    queryKey: ["trends"],
    queryFn: () => safetyApi.getTrends(),
  });
  const { data: deadlines, isLoading: deadlinesLoading, isError: deadlinesError } = useQuery({
    queryKey: ["deadlines"],
    queryFn: () => safetyApi.getDeadlines(30),
  });
  const [showKpiModal, setShowKpiModal] = useState(false);

  const activeRole = profile?.user.active_role ?? profile?.user.role ?? "";
  const workspace = ROLE_WORKSPACES[activeRole];
  const roleLabel = activeRole.replace(/_/g, " ");

  const isLoading = trendsLoading || deadlinesLoading;
  const hasDataErrors = trendsError || deadlinesError;
  const showUnavailable = isLoading || hasDataErrors;

  const config = ROLE_DASHBOARD_CONFIG[activeRole];
  const roleMetrics = config
    ? config.metrics.map((m) => ({
        ...m,
        value: showUnavailable ? (trendsLoading ? "—" : "Unavailable") : trends?.[m.valueKey] ?? 0,
        trend: showUnavailable ? undefined : m.trendKey ? (trends?.[m.trendKey] === "up" ? "up" : trends?.[m.trendKey] === "down" ? "down" : "stable") : undefined,
      }))
    : getFallbackMetrics(trends, deadlines, trendsLoading, deadlinesLoading, trendsError, deadlinesError);

  return (
    <div className="app-page">
      <header className="app-page-header">
        <div>
          <div className="app-eyebrow">{workspace ? `${roleLabel} · Primary function` : "Operations control centre"}</div>
          <h1 className="app-title">{workspace?.home ? `Dashboard — ${roleLabel}` : "Dashboard"}</h1>
          <p className="app-subtitle">{profile?.user.full_name ? `Welcome, ${profile.user.full_name}. ` : ""}A clear view of safety, compliance, and operational commitments.</p>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant={hasDataErrors ? "secondary" : "outline"} className={hasDataErrors ? "bg-kfl-status-warning-bg text-kfl-status-warning" : "bg-kfl-status-info-bg text-kfl-status-info"}>
            {isLoading ? "Checking dashboard data" : hasDataErrors ? "Some dashboard data is unavailable" : "Dashboard data loaded"}
          </Badge>
          <Button asChild variant="outline" size="sm">
            <Link to="/notifications">
              View notifications <ArrowUpRight size={15} />
            </Link>
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setShowKpiModal(true)}
          >
            <BarChart3 size={16} /> View Safety KPIs
          </Button>
        </div>
      </header>

      <section className="mb-7 grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4" aria-label="Key metrics">
        {roleMetrics.map((card, i) => (
          <MetricCard key={i} {...card} />
        ))}
      </section>

      {config?.quickActions && config.quickActions.length > 0 && (
        <section className="mb-7">
          <div className="flex items-start justify-between gap-4 border-b border-kfl-border px-5 py-4">
            <div>
              <h2 className="text-base font-bold text-kfl-text">Quick actions</h2>
              <p className="mt-1 text-xs text-kfl-muted">Common tasks for {roleLabel}</p>
            </div>
          </div>
          <div className="p-5 grid grid-cols-1 sm:grid-cols-2 gap-4">
            {config.quickActions.map((action, i) => (
              <Link key={i} to={action.href} className="block">
                <div className="app-surface p-4 transition hover:-translate-y-0.5 hover:shadow-card cursor-pointer border border-kfl-border hover:border-kfl-blue rounded-lg">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="text-sm font-semibold text-kfl-text">{action.label}</div>
                      <p className="mt-0.5 text-xs text-kfl-muted">Quick access</p>
                    </div>
                    <action.icon size={19} strokeWidth={1.8} className="text-kfl-blue" />
                  </div>
                </div>
              </Link>
            ))}
          </div>
        </section>
      )}

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
            <Button asChild variant="outline" size="sm" className="text-xs">
              <Link to="/notifications">Open centre</Link>
            </Button>
          </div>

          <div className="p-5">
            {deadlinesError && (
              <div role="alert" className="rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">Unable to load deadline data.</div>
            )}
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
            {!deadlinesError && !deadlinesLoading && deadlines && !deadlines?.overdue?.length && !deadlines?.upcoming?.length && (
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
              ["Document control", "Status not verified", "info", "Unverified"],
              [
                "Safety reporting",
                trendsError ? "Safety data unavailable" : trendsLoading ? "Checking safety data" : "Safety data available",
                "info",
                trendsError ? "Unavailable" : trendsLoading ? "Checking" : "Data available",
              ],
              [
                "Deadline monitoring",
                deadlinesError ? "Deadline data unavailable" : deadlinesLoading ? "Checking deadlines" : deadlines?.overdue_count ? `${deadlines.overdue_count} overdue item(s)` : "No overdue items",
                deadlinesError ? "info" : deadlinesLoading ? "info" : deadlines?.overdue_count ? "critical" : "healthy",
                deadlinesError ? "Unavailable" : deadlinesLoading ? "Checking" : deadlines?.overdue_count ? "Action" : "Clear",
              ],
              ["Notification service", "Notification status not checked", "info", "Not checked"],
            ].map(([label, value, tone, status]) => (
              <div key={label} className="flex items-center justify-between gap-3 border-b border-kfl-border pb-3 last:border-0 last:pb-0">
                <div>
                  <p className="text-sm font-semibold text-kfl-text">{label}</p>
                  <p className="mt-0.5 text-xs text-kfl-muted">{value}</p>
                </div>
                <Badge variant={tone === "critical" ? "destructive" : tone === "healthy" ? "default" : "outline"} className={tone === "critical" ? "bg-kfl-status-danger-bg text-kfl-status-danger" : tone === "healthy" ? "bg-kfl-status-success-bg text-kfl-status-success" : "bg-kfl-status-info-bg text-kfl-status-info"}>
                  {status}
                </Badge>
              </div>
            ))}
          </div>
        </div>
      </section>
      <SafetyKPIsModal open={showKpiModal} onClose={() => setShowKpiModal(false)} />
    </div>
  );
}

export default Dashboard;
