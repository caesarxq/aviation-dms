import { useQuery } from "@tanstack/react-query";
import { safetyApi } from "../api/safety";

export function Dashboard() {
  const { data: trends } = useQuery({
    queryKey: ["trends"],
    queryFn: () => safetyApi.getTrends(),
  });

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-6">Dashboard</h1>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white p-4 rounded shadow">
          <h3 className="text-gray-500 text-sm">Occurrences (30 days)</h3>
          <p className="text-3xl font-bold">{trends?.occurrences_last_30_days ?? 0}</p>
        </div>
        <div className="bg-white p-4 rounded shadow">
          <h3 className="text-gray-500 text-sm">Total Hazards</h3>
          <p className="text-3xl font-bold">{Object.values(trends?.hazards_by_risk_level ?? {}).reduce((a: number, b: any) => a + (b as number), 0)}</p>
        </div>
        <div className="bg-white p-4 rounded shadow">
          <h3 className="text-gray-500 text-sm">Open Safety Actions</h3>
          <p className="text-3xl font-bold">{trends?.safety_actions_by_status?.open ?? 0}</p>
        </div>
      </div>
    </div>
  );
}
