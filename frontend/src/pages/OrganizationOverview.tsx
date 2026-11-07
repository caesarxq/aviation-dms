import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, ArrowUpRight, CalendarClock, CheckCircle2, ClipboardList, Plane, ShieldCheck } from "lucide-react";
import { Link } from "react-router-dom";
import { safetyApi, OrganizationOverviewData } from "../api/safety";

type ActionPrompt = { text: string; to: string; link: string };

export function buildOrganizationPrompts(data: OrganizationOverviewData): ActionPrompt[] {
  const prompts: ActionPrompt[] = [];
  const overdue = Number(data.deadlines.overdue_count || 0);
  const inProgress = Number(data.operations.in_progress || 0);
  const openActions = Number(data.trends.safety_actions_by_status.open || 0);
  const withoutOpspecFlag = Number(data.fleet.not_opspec_authorized || 0);

  if (overdue > 0) {
    prompts.push({
      text: `Review ${overdue} overdue organization deadline${overdue === 1 ? "" : "s"}.`,
      to: "#overdue-deadlines",
      link: "View overdue records",
    });
  }
  if (inProgress > 0) {
    prompts.push({
      text: `Review the status of ${inProgress} operation${inProgress === 1 ? "" : "s"} currently in progress.`,
      to: "/missions",
      link: "Open missions",
    });
  }
  if (openActions > 0) {
    prompts.push({
      text: `Review ${openActions} open safety action${openActions === 1 ? "" : "s"} and current owners.`,
      to: "/safety-actions",
      link: "Open safety actions",
    });
  }
  if (withoutOpspecFlag > 0) {
    prompts.push({
      text: `Review ${withoutOpspecFlag} fleet record${withoutOpspecFlag === 1 ? "" : "s"} without an OpSpec authorization flag.`,
      to: "/roc",
      link: "Review ROC and OpSpec records",
    });
  }
  return prompts;
}

function Metric({ label, value, context, icon: Icon }: { label: string; value: number | string; context: string; icon: typeof AlertTriangle }) {
  return (
    <div className="app-surface p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="app-label">{label}</div>
          <div className="mt-3 text-3xl font-bold tracking-tight text-kfl-text">{value}</div>
          <div className="mt-1 text-xs text-kfl-muted">{context}</div>
        </div>
        <div className="rounded-lg bg-sky-50 p-2.5 text-kfl-blue"><Icon size={19} strokeWidth={1.8} /></div>
      </div>
    </div>
  );
}

function Breakdown({ title, values }: { title: string; values: Record<string, number> }) {
  const rows = Object.entries(values).sort(([left], [right]) => left.localeCompare(right));
  return (
    <div>
      <h3 className="text-sm font-semibold text-kfl-text">{title}</h3>
      {rows.length > 0 ? (
        <ul className="mt-2 divide-y divide-kfl-border rounded-lg border border-kfl-border">
          {rows.map(([label, count]) => (
            <li key={label} className="flex items-center justify-between gap-3 px-3 py-2 text-sm">
              <span className="capitalize text-kfl-muted">{label.replace(/_/g, " ")}</span>
              <span className="font-semibold text-kfl-text">{String(count)}</span>
            </li>
          ))}
        </ul>
      ) : <p className="mt-2 text-sm text-kfl-muted">No trend records available.</p>}
    </div>
  );
}

export function OrganizationOverview() {
  const { data, isLoading, isError, isFetching, refetch } = useQuery({
    queryKey: ["organization-overview"],
    queryFn: () => safetyApi.getOrganizationOverview(),
    staleTime: 60_000,
  });

  if (isLoading) {
    return <div className="app-page" role="status">Loading organization overview…</div>;
  }
  if (isError || !data) {
    return (
      <div className="app-page">
        <header className="app-page-header">
          <div><div className="app-eyebrow">Organization-wide view</div><h1 className="app-title">Organization overview</h1></div>
        </header>
        <div role="alert" className="rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">
          Unable to load organization overview data. No status should be inferred from unavailable data.
          <button
            type="button"
            onClick={() => void refetch()}
            disabled={isFetching}
            className="app-btn-secondary mt-3"
          >
            {isFetching ? "Retrying…" : "Retry loading overview"}
          </button>
        </div>
      </div>
    );
  }

  const activeOperations = Number(data.operations.released || 0) + Number(data.operations.in_progress || 0);
  const prompts = buildOrganizationPrompts(data);
  const fleetStatuses = Object.entries(data.fleet.status_counts).sort(([left], [right]) => left.localeCompare(right));

  return (
    <div className="app-page">
      <header className="app-page-header">
        <div>
          <div className="app-eyebrow">Executive workspace</div>
          <h1 className="app-title">Organization overview</h1>
          <p className="app-subtitle">Organization-wide trends, tracked commitments, operations, and fleet records. These summaries are not operational or regulatory approvals.</p>
        </div>
        <span className="app-status app-status-info">Summary data loaded</span>
      </header>

      <section className="mb-7 grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4" aria-label="Organization metrics">
        <Metric label="Occurrences (last 30 days)" value={data.trends.occurrences_last_30_days} context="Reported occurrences in the last 30 days" icon={AlertTriangle} />
        <Metric label="Overdue tracked deadlines" value={data.deadlines.overdue_count} context="Tracked items; next 30 days" icon={CalendarClock} />
        <Metric label="Active operations" value={activeOperations} context="Released plus in-progress records; not flight authorization" icon={ClipboardList} />
        <Metric label="Completed operations" value={data.operations.completed} context="Recorded as completed" icon={CheckCircle2} />
      </section>

      <section id="overdue-deadlines" className="app-surface mb-7 p-5" aria-labelledby="overdue-deadlines-heading">
        <div className="mb-4 flex items-center gap-2">
          <CalendarClock size={18} className="text-kfl-blue" />
          <h2 id="overdue-deadlines-heading" className="text-base font-bold text-kfl-text">Overdue tracked deadlines</h2>
        </div>
        <p className="mb-4 text-xs text-kfl-muted">Deadline records returned by the current organization-wide 30-day query; review the source record before acting.</p>
        {data.deadlines.overdue.length > 0 ? (
          <ul className="space-y-2">
            {data.deadlines.overdue.map((deadline) => (
              <li key={`${deadline.entity_type}:${deadline.entity_id}:${deadline.due_date}`} className="flex flex-col gap-2 rounded-lg border border-rose-200 bg-rose-50/60 p-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <p className="text-sm font-semibold text-kfl-text">{deadline.title}</p>
                  <p className="mt-1 text-xs text-kfl-muted">Record: {deadline.entity_id} · Type: {deadline.entity_type.replace(/_/g, " ")}</p>
                </div>
                <span className="text-xs font-semibold text-rose-800">Due {deadline.due_date} · {deadline.priority}</span>
              </li>
            ))}
          </ul>
        ) : data.deadlines.overdue_count > 0 ? (
          <p role="status" className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
            {data.deadlines.overdue_count} overdue item(s) were counted, but their record details were not returned.
          </p>
        ) : (
          <p className="rounded-lg border border-dashed border-kfl-border p-4 text-sm text-kfl-muted">
            No overdue records were returned by the current tracked-deadlines query.
          </p>
        )}
        {data.deadlines.overdue.length < data.deadlines.overdue_count && data.deadlines.overdue.length > 0 && (
          <p role="status" className="mt-3 text-xs text-kfl-muted">
            {data.deadlines.overdue_count - data.deadlines.overdue.length} additional overdue record(s) are not included in this response.
          </p>
        )}
      </section>

      <section className="mb-7 grid grid-cols-1 gap-5 xl:grid-cols-[1.15fr_0.85fr]">
        <div className="app-surface p-5">
          <div className="mb-4 flex items-center gap-2">
            <ShieldCheck size={18} className="text-kfl-blue" />
            <h2 className="text-base font-bold text-kfl-text">Operational trends</h2>
          </div>
          <p className="mb-4 text-xs text-kfl-muted">Record counts by category and status; these are descriptive summaries, not risk assessments.</p>
          <div className="grid gap-5 md:grid-cols-2">
            <Breakdown title="Occurrences by severity" values={data.trends.occurrences_by_severity} />
            <Breakdown title="Hazards by recorded risk level" values={data.trends.hazards_by_risk_level} />
            <Breakdown title="Safety actions by status" values={data.trends.safety_actions_by_status} />
            <Breakdown title="Operations by lifecycle" values={{
              planned: data.operations.planned,
              released: data.operations.released,
              in_progress: data.operations.in_progress,
              completed: data.operations.completed,
              cancelled: data.operations.cancelled,
              aborted: data.operations.aborted,
            }} />
          </div>
        </div>

        <div className="app-surface p-5">
          <div className="mb-4 flex items-center gap-2">
            <Plane size={18} className="text-kfl-blue" />
            <h2 className="text-base font-bold text-kfl-text">Fleet summary</h2>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="rounded-lg bg-kfl-surface-subtle p-4"><div className="app-label">Fleet records</div><div className="mt-2 text-2xl font-bold text-kfl-text">{data.fleet.total}</div></div>
            <div className="rounded-lg bg-kfl-surface-subtle p-4"><div className="app-label">OpSpec authorization flag</div><div className="mt-2 text-2xl font-bold text-kfl-text">{data.fleet.opspec_authorized}</div></div>
          </div>
          <p className="mt-2 text-xs text-kfl-muted">Authorization flags are record fields only and do not establish flight release or aircraft airworthiness.</p>
          <h3 className="mt-5 text-sm font-semibold text-kfl-text">Aircraft records by status</h3>
          {fleetStatuses.length > 0 ? (
            <ul className="mt-2 divide-y divide-kfl-border rounded-lg border border-kfl-border">
              {fleetStatuses.map(([status, count]) => <li key={status} className="flex justify-between px-3 py-2 text-sm"><span className="capitalize text-kfl-muted">{status.replace(/_/g, " ")}</span><span className="font-semibold text-kfl-text">{String(count)}</span></li>)}
            </ul>
          ) : <p className="mt-2 text-sm text-kfl-muted">No fleet records available.</p>}
        </div>
      </section>

      <section className="mb-7 grid grid-cols-1 gap-5 xl:grid-cols-2">
        <div className="app-surface p-5">
          <div className="mb-4 flex items-center gap-2"><CalendarClock size={18} className="text-kfl-blue" /><h2 className="text-base font-bold text-kfl-text">Action prompts</h2></div>
          <p className="mb-4 text-xs text-kfl-muted">Rule-based prompts derived from recorded counts. Review the underlying record before acting.</p>
          {prompts.length > 0 ? (
            <ul className="space-y-3">
              {prompts.map((prompt) => (
                <li key={prompt.text} className="flex flex-col gap-2 rounded-lg border border-kfl-border p-3 sm:flex-row sm:items-center sm:justify-between">
                  <span className="text-sm font-semibold text-kfl-text">{prompt.text}</span>
                  <Link to={prompt.to} className="inline-flex shrink-0 items-center gap-1 text-xs font-bold text-kfl-blue hover:text-kfl-blue-ink">{prompt.link}<ArrowUpRight size={14} /></Link>
                </li>
              ))}
            </ul>
          ) : <p className="rounded-lg border border-dashed border-kfl-border p-4 text-sm text-kfl-muted">No data-driven follow-ups from currently available records.</p>}
        </div>

        <div className="app-surface p-5" aria-labelledby="notams-heading">
          <div className="mb-3 flex items-center gap-2"><AlertTriangle size={18} className="text-amber-700" /><h2 id="notams-heading" className="text-base font-bold text-kfl-text">NOTAMs</h2></div>
          <p className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900" role="status">
            No approved NOTAM data source is connected. This is not an indication that there are no NOTAMs; consult the applicable official source.
          </p>
        </div>
      </section>

      <div className="flex flex-wrap gap-3 text-sm">
        <Link to="/missions" className="app-btn-secondary">Operations <ArrowUpRight size={14} /></Link>
        <Link to="/roc" className="app-btn-secondary">ROC and OpSpec records <ArrowUpRight size={14} /></Link>
        <Link to="/audit-reports" className="app-btn-secondary">Audit reports <ArrowUpRight size={14} /></Link>
      </div>
    </div>
  );
}
