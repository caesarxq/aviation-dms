import { Link } from "react-router-dom";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, ArrowUpRight, BarChart3, CalendarClock, CheckCircle2, FileCheck2, ShieldCheck, Users, Plane, Briefcase, Target } from "lucide-react";
import { safetyApi } from "../api/safety";
import { SafetyKPIsModal } from "../components/ui/modals/SafetyKPIsModal";
import { useAuth } from "../auth/AuthContext";
import { ROLE_WORKSPACES } from "../auth/permissions";

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

  const hazardTotal = Object.values(trends?.hazards_by_risk_level ?? {}).reduce((a: number, b: any) => a + Number(b || 0), 0);
  const isLoading = trendsLoading || deadlinesLoading;
  const hasDataErrors = trendsError || deadlinesError;

  // Role-specific metric cards
  const roleMetrics: Array<{ label: string; value: string | number; context: string; icon: any; tone: string }> = [];
  const showUnavailable = trendsLoading || trendsError || deadlinesLoading || deadlinesError;
  if (activeRole === "head_operations" || activeRole === "chief_pilot" || activeRole === "flight_ops_officer") {
    roleMetrics.push(
      { label: "Active Missions", value: showUnavailable ? (trendsLoading ? "—" : "Unavailable") : trends?.missions_count ?? 0, context: "Current operations", icon: Plane, tone: "blue" },
      { label: "Crew On Duty", value: showUnavailable ? (trendsLoading ? "—" : "Unavailable") : trends?.crew_on_duty ?? 0, context: "FDTL-compliant assignments", icon: Users, tone: "green" },
    );
  } else if (activeRole === "head_safety") {
    roleMetrics.push(
      { label: "Open Occurrences", value: showUnavailable ? (trendsLoading ? "—" : "Unavailable") : trends?.open_occurrences ?? 0, context: "Awaiting classification", icon: AlertTriangle, tone: "amber" },
      { label: "Safety Actions Overdue", value: showUnavailable ? (trendsLoading ? "—" : "Unavailable") : trends?.safety_actions_overdue ?? 0, context: "Past due date", icon: CheckCircle2, tone: "red" },
    );
  } else if (activeRole === "head_quality" || activeRole === "accountable_manager") {
    roleMetrics.push(
      { label: "Audit Findings Open", value: showUnavailable ? (trendsLoading ? "—" : "Unavailable") : trends?.audit_findings_open ?? 0, context: "Pending closure", icon: ShieldCheck, tone: "amber" },
      { label: "Quality Audits Due", value: showUnavailable ? (trendsLoading ? "—" : "Unavailable") : trends?.quality_audits_due ?? 0, context: "Scheduled this month", icon: Briefcase, tone: "blue" },
    );
  } else if (activeRole === "head_maintenance") {
    roleMetrics.push(
      { label: "Aircraft in Service", value: showUnavailable ? (trendsLoading ? "—" : "Unavailable") : trends?.aircraft_in_service ?? 0, context: "Airworthy fleet", icon: Plane, tone: "green" },
      { label: "Maintenance Due", value: showUnavailable ? (trendsLoading ? "—" : "Unavailable") : trends?.maintenance_due ?? 0, context: "Scheduled inspections", icon: CalendarClock, tone: "amber" },
    );
  } else if (activeRole === "head_training") {
    roleMetrics.push(
      { label: "Personnel Qualified", value: showUnavailable ? (trendsLoading ? "—" : "Unavailable") : trends?.personnel_qualified ?? 0, context: "Current qualifications", icon: Target, tone: "green" },
      { label: "Training Due", value: showUnavailable ? (trendsLoading ? "—" : "Unavailable") : trends?.training_due ?? 0, context: "Recency expiring", icon: CalendarClock, tone: "amber" },
    );
  } else if (activeRole === "dg_coordinator") {
    roleMetrics.push(
      { label: "DG Shipments Active", value: showUnavailable ? (trendsLoading ? "—" : "Unavailable") : trends?.dg_shipments_active ?? 0, context: "In transit", icon: Plane, tone: "amber" },
      { label: "DG Training Current", value: showUnavailable ? (trendsLoading ? "—" : "Unavailable") : trends?.dg_training_current ?? 0, context: "Certified staff", icon: Users, tone: "green" },
    );
  } else if (activeRole === "head_security") {
    roleMetrics.push(
      { label: "Security Reviews Open", value: showUnavailable ? (trendsLoading ? "—" : "Unavailable") : trends?.security_reviews_open ?? 0, context: "Pending action", icon: ShieldCheck, tone: "amber" },
      { label: "Incidents Reported", value: showUnavailable ? (trendsLoading ? "—" : "Unavailable") : trends?.security_incidents ?? 0, context: "Last 30 days", icon: AlertTriangle, tone: "red" },
    );
  } else if (activeRole === "records_custodian") {
    roleMetrics.push(
      { label: "Documents in Catalogue", value: showUnavailable ? (trendsLoading ? "—" : "Unavailable") : trends?.documents_count ?? 0, context: "Controlled documents", icon: FileCheck2, tone: "blue" },
      { label: "Distributions Pending", value: showUnavailable ? (trendsLoading ? "—" : "Unavailable") : trends?.distributions_pending ?? 0, context: "Awaiting release", icon: Plane, tone: "amber" },
    );
  } else if (activeRole === "independent_auditor") {
    roleMetrics.push(
      { label: "Audit Reports Open", value: showUnavailable ? (trendsLoading ? "—" : "Unavailable") : trends?.audit_reports_open ?? 0, context: "Awaiting review", icon: Briefcase, tone: "blue" },
      { label: "Findings Unresolved", value: showUnavailable ? (trendsLoading ? "—" : "Unavailable") : trends?.findings_unresolved ?? 0, context: "Not yet closed", icon: AlertTriangle, tone: "red" },
    );
  } else if (activeRole === "librarian" || activeRole === "as_contracted" || activeRole === "occurrence_reporter" || activeRole === "system_admin") {
    roleMetrics.push(
      { label: "System Status", value: trendsError ? "Degraded" : "Operational", context: "All services", icon: ShieldCheck, tone: trendsError ? "red" : "green" },
    );
  }

  return (
    <div className="app-page">
      <header className="app-page-header">
        <div>
          <div className="app-eyebrow">{workspace ? `${roleLabel} · Primary function` : "Operations control centre"}</div>
          <h1 className="app-title">{workspace?.home ? `Dashboard — ${roleLabel}` : "Dashboard"}</h1>
          <p className="app-subtitle">{profile?.user.full_name ? `Welcome, ${profile.user.full_name}. ` : ""}A clear view of safety, compliance, and operational commitments.</p>
        </div>
        <div className="flex items-center gap-2">
          <span className={`app-status ${hasDataErrors ? "app-status-warning" : "app-status-info"}`}>
            {isLoading ? "Checking dashboard data" : hasDataErrors ? "Some dashboard data is unavailable" : "Dashboard data loaded"}
          </span>
          <Link to="/notifications" className="app-btn-secondary">
            View notifications <ArrowUpRight size={15} />
          </Link>
          <button
            onClick={() => setShowKpiModal(true)}
            className="app-btn-secondary"
          >
            <BarChart3 size={16} /> View Safety KPIs
          </button>
        </div>
      </header>

      <section className="mb-7 grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4" aria-label="Key metrics">
        {roleMetrics.length > 0 ? roleMetrics.map((card, i) => (
          <MetricCard key={i} label={card.label} value={card.value} context={card.context} icon={card.icon} tone={card.tone} />
        )) : (
          <>
            <MetricCard label="Occurrences (30 days)" value={trendsLoading ? "—" : trendsError ? "Unavailable" : trends?.occurrences_last_30_days ?? 0} context="Reported safety events" icon={AlertTriangle} tone="amber" />
            <MetricCard label="Total Hazards" value={trendsLoading ? "—" : trendsError ? "Unavailable" : hazardTotal} context="Across active risk registers" icon={ShieldCheck} tone="blue" />
            <MetricCard label="Open Safety Actions" value={trendsLoading ? "—" : trendsError ? "Unavailable" : trends?.safety_actions_by_status?.open ?? 0} context="Awaiting completion" icon={CheckCircle2} tone="blue" />
            <MetricCard label="Deadlines requiring attention" value={deadlinesLoading ? "—" : deadlinesError ? "Unavailable" : deadlines?.overdue_count ?? 0} context={deadlinesError ? "Deadline data unavailable" : "Overdue items"} icon={CalendarClock} tone={deadlinesError ? "blue" : deadlines?.overdue_count ? "red" : "green"} />
          </>
        )}
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
              ["Safety reporting", trendsError ? "Safety data unavailable" : trendsLoading ? "Checking safety data" : "Safety data available", "info", trendsError ? "Unavailable" : trendsLoading ? "Checking" : "Data available"],
              ["Deadline monitoring", deadlinesError ? "Deadline data unavailable" : deadlinesLoading ? "Checking deadlines" : deadlines?.overdue_count ? `${deadlines.overdue_count} overdue item(s)` : "No overdue items", deadlinesError ? "info" : deadlinesLoading ? "info" : deadlines?.overdue_count ? "critical" : "healthy", deadlinesError ? "Unavailable" : deadlinesLoading ? "Checking" : deadlines?.overdue_count ? "Action" : "Clear"],
              ["Notification service", "Notification status not checked", "info", "Not checked"],
            ].map(([label, value, tone, status]) => (
              <div key={label} className="flex items-center justify-between gap-3 border-b border-kfl-border pb-3 last:border-0 last:pb-0">
                <div>
                  <p className="text-sm font-semibold text-kfl-text">{label}</p>
                  <p className="mt-0.5 text-xs text-kfl-muted">{value}</p>
                </div>
                <span className={`app-status ${tone === "critical" ? "app-status-critical" : tone === "healthy" ? "app-status-healthy" : "app-status-info"}`}>{status}</span>
              </div>
            ))}
          </div>
        </div>
      </section>
      <SafetyKPIsModal open={showKpiModal} onClose={() => setShowKpiModal(false)} />
    </div>
  );
}