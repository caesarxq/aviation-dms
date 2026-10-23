import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import api from "../api/client";
import { KeyRound, Shield, CheckCircle, Clock, AlertTriangle } from "lucide-react";

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

  // Fetch insurance for all aircraft
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
    if (days === null) return <CheckCircle size={14} className="text-gray-400" />;
    if (days <= 0) return <AlertTriangle size={14} className="text-red-600" />;
    if (days <= 7) return <AlertTriangle size={14} className="text-red-500" />;
    if (days <= 30) return <Clock size={14} className="text-yellow-500" />;
    return <CheckCircle size={14} className="text-green-500" />;
  };

  const statusColor = (days: number | null) => {
    if (days === null) return "text-gray-500";
    if (days <= 0) return "text-red-600 font-bold";
    if (days <= 7) return "text-red-500 font-semibold";
    if (days <= 30) return "text-yellow-600";
    return "text-green-600";
  };

  // Group licenses by person
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
          <button onClick={() => setTab("licenses")} className={`px-3 py-1.5 text-sm rounded ${tab === "licenses" ? "bg-kfl-primary text-white" : "bg-kfl-surface text-kfl-muted"}`}>
            <KeyRound size={14} className="inline mr-1" /> Licenses
          </button>
          <button onClick={() => setTab("insurance")} className={`px-3 py-1.5 text-sm rounded ${tab === "insurance" ? "bg-kfl-primary text-white" : "bg-kfl-surface text-kfl-muted"}`}>
            <Shield size={14} className="inline mr-1" /> Insurance
          </button>
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
          <div className="mt-2 text-2xl font-bold text-yellow-600">{expiringLic.length}</div>
        </div>
        <div className="app-surface p-4">
          <div className="app-label">Critical (7d)</div>
          <div className="mt-2 text-2xl font-bold text-red-600">
            {expiringLic.filter((l: any) => daysUntil(l.expiry_date) !== null && daysUntil(l.expiry_date)! <= 7).length}
          </div>
        </div>
        <div className="app-surface p-4">
          <div className="app-label">Expired</div>
          <div className="mt-2 text-2xl font-bold text-red-700">
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
                          <span className={`px-2 py-0.5 rounded text-xs font-semibold ${
                            l.status === "valid" ? "bg-green-100 text-green-800" :
                            l.status === "expiring_soon" ? "bg-yellow-100 text-yellow-800" :
                            "bg-red-100 text-red-800"
                          }`}>{l.status}</span>
                          {l.renewal_status && l.renewal_status !== "not_started" && (
                            <span className="px-2 py-0.5 rounded text-xs bg-blue-100 text-blue-800">{l.renewal_status.replace(/_/g, " ")}</span>
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
            <select className="border border-kfl-border rounded p-2 text-sm w-full max-w-md" value={selectedAircraft} onChange={e => setSelectedAircraft(e.target.value)}>
              <option value="">— Select an aircraft —</option>
              {aircraft.map((a: any) => <option key={a.aircraft_id} value={a.aircraft_id}>{a.registration} — {a.model}</option>)}
            </select>
          </div>

          {/* Expiring insurance summary */}
          {expiringIns.length > 0 && (
            <div className="app-surface p-4 mb-4 border-l-4 border-yellow-500">
              <h3 className="font-semibold text-yellow-700 flex items-center gap-2 mb-2">
                <AlertTriangle size={16} /> {expiringIns.length} Policy/Policies Expiring Within 90 Days
              </h3>
              {expiringIns.map((i: any) => (
                <div key={i.insurance_id} className="text-sm text-yellow-600">
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
                      <span className={`px-2 py-0.5 rounded text-xs font-semibold ${i.status === "active" ? "bg-green-100 text-green-800" : "bg-gray-100 text-gray-800"}`}>{i.status}</span>
                      {i.renewal_status && i.renewal_status !== "not_started" && (
                        <span className="px-2 py-0.5 rounded text-xs bg-blue-100 text-blue-800">{i.renewal_status.replace(/_/g, " ")}</span>
                      )}
                      {i.broker && <span className="px-2 py-0.5 rounded text-xs bg-gray-100 text-gray-600">Broker: {i.broker}</span>}
                      {i.coverage_amount && <span className="px-2 py-0.5 rounded text-xs bg-gray-100 text-gray-600">Coverage: {i.coverage_amount} {i.currency}</span>}
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
