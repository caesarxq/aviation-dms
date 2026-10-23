import { useQuery } from "@tanstack/react-query";
import { rocApi } from "../api/roc";
import { Plane, ShieldCheck, AlertTriangle } from "lucide-react";

export function ROCRegister() {
  const { data: rocs = [] } = useQuery({ queryKey: ["roc"], queryFn: () => rocApi.listROC() });
  const { data: aircraft = [] } = useQuery({ queryKey: ["aircraft"], queryFn: () => rocApi.listAircraft() });

  return (
    <div className="app-page">
      <header className="app-page-header">
        <div>
          <div className="app-eyebrow">Regulatory Operations</div>
          <h1 className="app-title">ROC & UAS Fleet</h1>
          <p className="app-subtitle">Remote Operator Certificate details and registered aircraft fleet.</p>
        </div>
        <div className="flex items-center gap-2">
          <Plane size={18} className="text-kfl-blue" />
          <span className="app-status app-status-healthy">ROC Active</span>
        </div>
      </header>

      <section className="mb-5 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <div className="app-surface p-4">
          <div className="app-label">ROC Number</div>
          <div className="mt-2 text-sm font-bold text-kfl-text">{rocs[0]?.roc_number || "—"}</div>
        </div>
        <div className="app-surface p-4">
          <div className="app-label">Serial Number</div>
          <div className="mt-2 text-sm font-bold text-kfl-text">{rocs[0]?.serial_number || "—"}</div>
        </div>
        <div className="app-surface p-4">
          <div className="app-label">Registered Aircraft</div>
          <div className="mt-2 text-sm font-bold text-kfl-text">{aircraft.length}</div>
        </div>
        <div className="app-surface p-4">
          <div className="app-label">Expires</div>
          <div className="mt-2 text-sm font-bold text-kfl-text">{rocs[0]?.expiry_date || "—"}</div>
        </div>
        <div className="app-surface p-4">
          <div className="app-label">BVLOS</div>
          <div className="mt-2 flex items-center gap-1 text-sm">
            {rocs[0]?.bvlos_authorized ? <ShieldCheck size={16} className="text-emerald-700" /> : <AlertTriangle size={16} className="text-amber-700" />}
            {rocs[0]?.bvlos_authorized ? "Authorized" : "Not Authorized"}
          </div>
        </div>
        <div className="app-surface p-4">
          <div className="app-label">Night Operations</div>
          <div className="mt-2 flex items-center gap-1 text-sm">
            {rocs[0]?.night_authorized ? <ShieldCheck size={16} className="text-emerald-700" /> : <AlertTriangle size={16} className="text-amber-700" />}
            {rocs[0]?.night_authorized ? "Authorized" : "Not Authorized"}
          </div>
        </div>
      </section>

      <section className="app-surface overflow-hidden">
        <div className="flex items-start justify-between border-b border-kfl-border p-4">
          <div>
            <div className="flex items-center gap-2">
              <Plane size={18} className="text-kfl-blue" />
              <h2 className="text-base font-bold text-kfl-text">Registered Aircraft</h2>
            </div>
            <p className="mt-1 text-xs text-kfl-muted">{aircraft.length} aircraft on record</p>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="min-w-full">
            <thead className="border-b border-kfl-border bg-kfl-surface-subtle">
              <tr>
                <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Registration</th>
                <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Model</th>
                <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Serial</th>
                <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Status</th>
                <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Category</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-kfl-border">
              {aircraft.map((ac: any) => (
                <tr key={ac.aircraft_id} className="transition hover:bg-kfl-surface-subtle">
                  <td className="px-4 py-4 font-mono text-[12px] text-kfl-text">{ac.registration}</td>
                  <td className="px-4 py-4 text-sm text-kfl-secondary">{ac.model}</td>
                  <td className="px-4 py-4 text-sm text-kfl-secondary">{ac.serial_number || "—"}</td>
                  <td className="px-4 py-4">
                    <span className={missionStatusClass(ac.status)}>{ac.status}</span>
                  </td>
                  <td className="px-4 py-4 text-sm text-kfl-secondary">{ac.category || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {aircraft.length === 0 && (
          <div className="app-surface border-dashed p-10 text-center">
            <Plane size={26} className="mx-auto mb-2 text-kfl-muted" />
            <p className="text-sm font-bold text-kfl-text">No aircraft registered.</p>
            <p className="mt-1 text-xs text-kfl-muted">Add fleet aircraft to manage operations.</p>
          </div>
        )}
      </section>
    </div>
  );
}

function missionStatusClass(status: string) {
  switch (status) {
    case "active": return "app-status app-status-healthy";
    case "maintenance": return "app-status app-status-info";
    case "retired": return "app-status app-status-critical";
    default: return "app-status app-status-info";
  }
}