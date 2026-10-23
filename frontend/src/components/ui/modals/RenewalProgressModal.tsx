import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import api from "../../../api/client";
import { KeyRound, Shield, CheckCircle, Clock, AlertTriangle } from "lucide-react";
import { Modal } from "../Modal";

export function RenewalProgressModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [tab, setTab] = useState<"licenses" | "insurance">("licenses");

  const { data: licenses = [] } = useQuery({
    queryKey: ["renewal-modal-licenses"],
    queryFn: () => api.get("/p2/personnel/licenses").then((r: any) => r.data),
  });

  const { data: expiringIns = [] } = useQuery({
    queryKey: ["renewal-modal-expiring-insurance"],
    queryFn: () => api.get("/p2/insurance/expiring?days=90").then((r: any) => r.data),
  });

  const { data: aircraft = [] } = useQuery({
    queryKey: ["renewal-modal-aircraft"],
    queryFn: () => api.get("/p1/aircraft").then((r: any) => r.data),
  });

  const [selectedAircraft, setSelectedAircraft] = useState("");

  const { data: insurance = [] } = useQuery({
    queryKey: ["renewal-modal-insurance", selectedAircraft],
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
    if (days === null) return <CheckCircle size={12} className="text-gray-400" />;
    if (days <= 0) return <AlertTriangle size={12} className="text-red-600" />;
    if (days <= 7) return <AlertTriangle size={12} className="text-red-500" />;
    if (days <= 30) return <Clock size={12} className="text-yellow-500" />;
    return <CheckCircle size={12} className="text-green-500" />;
  };

  const statusColor = (days: number | null) => {
    if (days === null) return "text-gray-500";
    if (days <= 0) return "text-red-600 font-bold";
    if (days <= 7) return "text-red-500 font-semibold";
    if (days <= 30) return "text-yellow-600";
    return "text-green-600";
  };

  const licensesByPerson = licenses.reduce((acc: any, lic: any) => {
    if (!acc[lic.person_id]) acc[lic.person_id] = [];
    acc[lic.person_id].push(lic);
    return acc;
  }, {});

  return (
    <Modal open={open} onClose={onClose} title="Renewal Progress" className="max-w-3xl">
      <div className="flex gap-2 mb-4">
        <button
          onClick={() => setTab("licenses")}
          className={`px-3 py-1.5 text-sm rounded ${tab === "licenses" ? "bg-kfl-blue/20 text-white" : "bg-white/10 text-white/70"}`}
        >
          <KeyRound size={12} className="inline mr-1" /> Licenses
        </button>
        <button
          onClick={() => setTab("insurance")}
          className={`px-3 py-1.5 text-sm rounded ${tab === "insurance" ? "bg-kfl-blue/20 text-white" : "bg-white/10 text-white/70"}`}
        >
          <Shield size={12} className="inline mr-1" /> Insurance
        </button>
      </div>

      {tab === "licenses" && (
        <div className="space-y-3">
          {Object.entries(licensesByPerson).map(([person, lics]: [string, any]) => (
            <div key={person} className="p-2 rounded bg-white/5">
              <h4 className="text-xs font-medium text-white mb-2 flex items-center gap-2">
                <KeyRound size={14} /> {person}
                <span className="text-[10px] font-normal text-white/50 ml-auto">({lics.length})</span>
              </h4>
              <div className="space-y-1">
                {lics.map((l: any) => {
                  const days = daysUntil(l.expiry_date);
                  return (
                    <div key={l.license_id} className="flex items-center gap-2 p-1.5 rounded bg-white/3">
                      {statusIcon(days)}
                      <div className="flex-1 min-w-0">
                        <div className="text-xs font-medium text-white">{l.license_type.replace(/_/g, " ")}</div>
                        <div className="text-[10px] text-white/50">{l.license_number || "—"} · {l.issuing_authority || "—"}</div>
                      </div>
                      <div className="text-right">
                        <div className={`text-xs font-bold ${statusColor(days)}`}>{l.expiry_date}</div>
                        <div className="text-[10px] text-white/50">{days !== null ? `${days} days` : "—"}</div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
          {licenses.length === 0 && (
            <div className="p-4 text-center text-white/50 text-sm">No personnel licenses on record.</div>
          )}
        </div>
      )}

      {tab === "insurance" && (
        <div className="space-y-3">
          <div className="mb-3">
            <label className="block text-xs font-medium text-white/70 mb-1">Select Aircraft</label>
            <select
              className="w-full border border-white/20 rounded p-1.5 text-sm bg-white/10 text-white focus:border-kfl-blue focus:outline-none"
              value={selectedAircraft}
              onChange={(e) => setSelectedAircraft(e.target.value)}
            >
              <option value="">— Select an aircraft —</option>
              {aircraft.map((a: any) => (
                <option key={a.aircraft_id} value={a.aircraft_id}>
                  {a.registration} — {a.model}
                </option>
              ))}
            </select>
          </div>

          {expiringIns.length > 0 && (
            <div className="mb-3 p-2 rounded bg-rose-50/60 border border-rose-200 text-rose-800 text-xs">
              {expiringIns.length} Policy/Policies Expiring Within 90 Days
            </div>
          )}

          {selectedAircraft && (
            <div className="space-y-2">
              {insurance.map((i: any) => {
                const days = daysUntil(i.expiry_date);
                return (
                  <div key={i.insurance_id} className="p-2 rounded bg-white/5 flex justify-between items-start">
                    <div>
                      <div className="text-xs font-medium text-white">{i.insurance_type.replace(/_/g, " ")}</div>
                      <div className="text-[10px] text-white/50">{i.insurer} · {i.policy_number || "—"}</div>
                    </div>
                    <div className="text-right">
                      <div className={`text-xs font-bold ${statusColor(days)}`}>{i.expiry_date}</div>
                      <div className="text-[10px] text-white/50">{days !== null ? `${days} days remaining` : "—"}</div>
                    </div>
                  </div>
                );
              })}
              {insurance.length === 0 && (
                <div className="p-4 text-center text-white/50 text-sm">No insurance policies for this aircraft.</div>
              )}
            </div>
          )}
        </div>
      )}
    </Modal>
  );
}
