import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import api from "../api/client";
import { KeyRound, Shield, CheckCircle, Clock, AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

export function RenewalProgress() {
  const [tab, setTab] = useState<"licenses" | "insurance">("licenses");

  const { data: licenses = [], isLoading: licLoading } = useQuery({
    queryKey: ["personnel-licenses-all"],
    queryFn: () => api.get("/p2/personnel/licenses").then((r: any) => r.data),
  });

  const { data: expiringLic = [] } = useQuery({
    queryKey: ["expiring-licenses-90"],
    queryFn: () => api.get("/p2/personnel/expiring-licenses?days=90").then((r: any) => r.data),
  });

  const { data: expiringIns = [] } = useQuery({
    queryKey: ["expiring-insurance-90"],
    queryFn: () => api.get("/p2/insurance/expiring?days=90").then((r: any) => r.data),
  });

  const { data: aircraft = [] } = useQuery({
    queryKey: ["aircraft-list"],
    queryFn: () => api.get("/p1/aircraft").then((r: any) => r.data),
  });

  const [selectedAircraft, setSelectedAircraft] = useState("");

  const { data: insurance = [] } = useQuery({
    queryKey: ["aircraft-insurance", selectedAircraft],
    queryFn: () => selectedAircraft
      ? api.get(`/p2/aircraft/${selectedAircraft}/insurance`).then((r: any) => r.data)
      : Promise.resolve([]),
    enabled: !!selectedAircraft,
  });

  const daysUntil = (date: string) => {
    if (!date) return null;
    const d = new Date(date);
    const now = new Date();
    return Math.ceil((d.getTime() - now.getTime()) / (1000 * 60 * 60 * 24));
  };

  const statusIcon = (days: number | null) => {
    if (days === null) return <CheckCircle size={14} className="text-kfl-muted" />;
    if (days <= 0) return <AlertTriangle size={14} className="text-kfl-status-danger" />;
    if (days <= 7) return <AlertTriangle size={14} className="text-kfl-status-danger" />;
    if (days <= 30) return <Clock size={14} className="text-kfl-status-warning" />;
    return <CheckCircle size={14} className="text-kfl-status-info" />;
  };

  const statusColor = (days: number | null) => {
    if (days === null) return "text-kfl-muted";
    if (days <= 0) return "text-kfl-status-danger font-bold";
    if (days <= 7) return "text-kfl-status-danger font-semibold";
    if (days <= 30) return "text-kfl-status-warning";
    return "text-kfl-status-info";
  };

  const licensesByPerson = licenses.reduce((acc: any, lic: any) => {
    if (!acc[lic.person_id]) acc[lic.person_id] = [];
    acc[lic.person_id].push(lic);
    return acc;
  }, {});

  return (
    <div className="app-page">
      <header className="app-page-header">
        <div>
          <div className="app-eyebrow">Compliance & Renewals</div>
          <h1 className="app-title">Renewal Progress</h1>
          <p className="app-subtitle">Track credential and insurance renewal status across all personnel and aircraft.</p>
        </div>
        <div className="flex gap-2">
          <Button variant={tab === "licenses" ? "default" : "outline"} size="sm" onClick={() => setTab("licenses")}>
            <KeyRound size={14} className="inline mr-1" /> Licenses
          </Button>
          <Button variant={tab === "insurance" ? "default" : "outline"} size="sm" onClick={() => setTab("insurance")}>
            <Shield size={14} className="inline mr-1" /> Insurance
          </Button>
        </div>
      </header>

      {/* Summary cards */}
      <section className="mb-5 grid grid-cols-1 gap-4 sm:grid-cols-4">
        <div className="app-surface p-4">
          <div className="app-label">Total Licenses</div>
          <div className="mt-2 text-2xl font-bold text-kfl-text">{licenses.length}</div>
        </div>
        <div className="app-surface p-4">
          <div className="app-label">Expiring (90d)</div>
          <div className="mt-2 text-2xl font-bold text-kfl-status-warning">{expiringLic.length}</div>
        </div>
        <div className="app-surface p-4">
          <div className="app-label">Critical (7d)</div>
          <div className="mt-2 text-2xl font-bold text-kfl-status-danger">
            {expiringLic.filter((l: any) => daysUntil(l.expiry_date) !== null && daysUntil(l.expiry_date)! <= 7).length}
          </div>
        </div>
        <div className="app-surface p-4">
          <div className="app-label">Expired</div>
          <div className="mt-2 text-2xl font-bold text-kfl-status-danger">
            {licenses.filter((l: any) => l.status === "expired").length}
          </div>
        </div>
      </section>

      {tab === "licenses" && (
        <>
          {licLoading ? (
            <div className="p-8 text-kfl-muted">Loading licenses…</div>
          ) : (
            <div className="space-y-4">
              {Object.entries(licensesByPerson).map(([person, lics]: [string, any]) => (
                <div key={person} className="app-surface p-4">
                  <h3 className="font-semibold text-kfl-text mb-3 flex items-center gap-2">
                    <KeyRound size={16} /> {person}
                    <span className="text-xs text-kfl-muted font-normal">({lics.length} license{lics.length !== 1 ? "s" : ""})</span>
                  </h3>
                  <div className="space-y-2">
                    {lics.map((l: any) => {
                      const days = daysUntil(l.expiry_date);
                      return (
                        <div key={l.license_id} className="flex items-center gap-3 p-2 rounded bg-kfl-surface-subtle">
                          {statusIcon(days)}
                          <div className="flex-1 min-w-0">
                            <div className="text-sm font-medium">{l.license_type.replace(/_/g, " ")}</div>
                            <div className="text-xs text-kfl-muted">{l.license_number || "—"} · {l.issuing_authority || "—"}</div>
                          </div>
                          <div className="text-right">
                            <div className={`text-sm ${statusColor(days)}`}>{l.expiry_date}</div>
                            <div className="text-xs text-kfl-muted">{days !== null ? `${days} days` : "—"}</div>
                          </div>
                          <Badge variant={l.status === "valid" ? "default" : l.status === "expiring_soon" ? "secondary" : "destructive"} className={`badge ${l.status === "valid" ? "bg-kfl-status-info-bg text-kfl-status-info" : l.status === "expiring_soon" ? "bg-kfl-status-warning-bg text-kfl-status-warning" : "bg-kfl-status-danger-bg text-kfl-status-danger"}`}>{l.status}</Badge>
                          {l.renewal_status && l.renewal_status !== "not_started" && (
                            <span className="px-2 py-0.5 rounded text-xs bg-kfl-status-info-bg text-kfl-status-info">{l.renewal_status.replace(/_/g, " ")}</span>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              ))}
              {licenses.length === 0 && (
                <div className="app-surface p-8 text-center text-kfl-muted">No personnel licenses on record.</div>
              )}
            </div>
          )}
        </>
      )}

      {tab === "insurance" && (
        <>
          <div className="app-surface p-4 mb-4">
            <label className="text-sm font-semibold text-kfl-muted mb-2 block">Select Aircraft</label>
            <select id="selectedaircraft_164" name="selectedaircraft" className="border border-kfl-border rounded p-2 text-sm w-full max-w-md" value={selectedAircraft} onChange={e => setSelectedAircraft(e.target.value)}>
              <option value="">— Select an aircraft —</option>
              {aircraft.map((a: any) => <option key={a.aircraft_id} value={a.aircraft_id}>{a.registration} — {a.model}</option>)}
            </select>
          </div>

          {/* Expiring insurance summary */}
          {expiringIns.length > 0 && (
            <div className="app-surface p-4 mb-4 border-l-4 border-kfl-status-warning-bg">
              <h3 className="font-semibold text-kfl-status-warning flex items-center gap-2 mb-2">
                <AlertTriangle size={16} /> {expiringIns.length} Policy/Policies Expiring Within 90 Days
              </h3>
              {expiringIns.map((i: any) => (
                <div key={i.insurance_id} className="text-sm text-kfl-status-warning">
                  {i.insurance_type} — {i.aircraft_id} — expires {i.expiry_date} ({daysUntil(i.expiry_date)} days)
                </div>
              ))}
            </div>
          )}

          {selectedAircraft && (
            <div className="space-y-3">
              {insurance.map((i: any) => {
                const days = daysUntil(i.expiry_date);
                return (
                  <div key={i.insurance_id} className="app-surface p-4">
                    <div className="flex justify-between items-start mb-2">
                      <div>
                        <h4 className="font-semibold text-kfl-text">{i.insurance_type.replace(/_/g, " ")}</h4>
                        <div className="text-sm text-kfl-muted">{i.insurer} · {i.policy_number || "—"}</div>
                      </div>
                      <div className="text-right">
                        <div className={`text-sm ${statusColor(days)}`}>{i.expiry_date}</div>
                        <div className="text-xs text-kfl-muted">{days !== null ? `${days} days remaining` : "—"}</div>
                      </div>
                    </div>
                    <div className="flex gap-2 flex-wrap">
                      <Badge variant={i.status === "active" ? "default" : "secondary"} className={`badge ${i.status === "active" ? "bg-kfl-status-info-bg text-kfl-status-info" : "bg-kfl-surface-subtle text-kfl-muted"}`}>{i.status}</Badge>
                      {i.renewal_status && i.renewal_status !== "not_started" && (
                        <span className="px-2 py-0.5 rounded text-xs bg-kfl-status-info-bg text-kfl-status-info">{i.renewal_status.replace(/_/g, " ")}</span>
                      )}
                      {i.broker && <span className="px-2 py-0.5 rounded text-xs bg-kfl-surface-subtle text-kfl-muted">Broker: {i.broker}</span>}
                      {i.coverage_amount && <span className="px-2 py-0.5 rounded text-xs bg-kfl-surface-subtle text-kfl-muted">Coverage: {i.coverage_amount} {i.currency}</span>}
                    </div>
                  </div>
                );
              })}
              {insurance.length === 0 && (
                <div className="app-surface p-8 text-center text-kfl-muted">No insurance policies for this aircraft.</div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}

export default RenewalProgress;
