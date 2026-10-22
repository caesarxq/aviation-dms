import { useQuery } from "@tanstack/react-query";
import { rocApi } from "../api/roc";

export function ROCRegister() {
  const { data: rocs = [] } = useQuery({ queryKey: ["roc"], queryFn: () => rocApi.listROC() });
  const { data: aircraft = [] } = useQuery({ queryKey: ["aircraft"], queryFn: () => rocApi.listAircraft() });

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-4">ROC & UAS Fleet</h1>
      {rocs.map((roc: any) => (
        <div key={roc.roc_id} className="bg-white p-4 rounded shadow mb-4">
          <h2 className="font-semibold">ROC {roc.roc_number}</h2>
          <p className="text-sm text-gray-600">Serial: {roc.serial_number} | KCAA: {roc.kcaa_reference}</p>
          <p className="text-sm text-gray-600">Issued: {roc.issue_date} | Expires: {roc.expiry_date}</p>
          <p className="text-sm text-gray-600">Categories: {roc.categories} | BVLOS: {roc.bvlos_authorized ? "Yes" : "No"} | Night: {roc.night_authorized ? "Yes" : "No"} | EVLOS: {roc.evlos_authorized ? "Yes" : "No"}</p>
          <p className="text-sm text-gray-600">Max Alt: {roc.max_altitude_agl} ft | DG: {roc.dg_category}</p>
        </div>
      ))}
      <h2 className="text-lg font-semibold mb-2">Aircraft ({aircraft.length})</h2>
      <table className="min-w-full bg-white border rounded shadow">
        <thead className="bg-gray-50">
          <tr>
            <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Registration</th>
            <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Model</th>
            <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Serial</th>
            <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
          </tr>
        </thead>
        <tbody className="divide-y">
          {aircraft.map((ac: any) => (
            <tr key={ac.aircraft_id} className="hover:bg-gray-50">
              <td className="px-4 py-2 text-sm font-medium">{ac.registration}</td>
              <td className="px-4 py-2 text-sm">{ac.model}</td>
              <td className="px-4 py-2 text-sm">{ac.serial_number || "—"}</td>
              <td className="px-4 py-2 text-sm">{ac.status}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
