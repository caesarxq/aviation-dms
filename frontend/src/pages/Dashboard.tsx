import { useQuery } from "@tanstack/react-query";
import { safetyApi } from "../api/safety";

export function Dashboard() {
  const { data: trends } = useQuery({
    queryKey: ["trends"],
    queryFn: () => safetyApi.getTrends(),
  });

  const { data: deadlines } = useQuery({
    queryKey: ["deadlines"],
    queryFn: () => safetyApi.getDeadlines(30),
  });

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-6">Dashboard</h1>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
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

      <div className="bg-white rounded shadow p-4">
        <div className="flex justify-between items-center mb-3">
          <h2 className="text-lg font-semibold">Upcoming & Overdue Deadlines</h2>
          <div className="flex gap-2 text-sm">
            <span className="px-2 py-1 rounded bg-red-100 text-red-800">
              Overdue: {deadlines?.overdue_count ?? 0}
            </span>
            <span className="px-2 py-1 rounded bg-yellow-100 text-yellow-800">
              Upcoming: {deadlines?.upcoming_count ?? 0}
            </span>
          </div>
        </div>
        {deadlines?.overdue?.length > 0 && (
          <div className="mb-4">
            <h3 className="text-sm font-medium text-red-700 mb-2">Overdue</h3>
            <ul className="space-y-1">
              {deadlines.overdue.map((d: any, i: number) => (
                <li key={i} className="flex justify-between items-center text-sm p-2 bg-red-50 rounded">
                  <span className="font-medium">{d.title}</span>
                  <span className="text-red-600 text-xs">{d.due_date} · {d.priority}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
        {deadlines?.upcoming?.length > 0 && (
          <div>
            <h3 className="text-sm font-medium text-gray-700 mb-2">Upcoming (30 days)</h3>
            <ul className="space-y-1">
              {deadlines.upcoming.slice(0, 10).map((d: any, i: number) => (
                <li key={i} className="flex justify-between items-center text-sm p-2 bg-gray-50 rounded">
                  <span>{d.title}</span>
                  <span className="text-gray-500 text-xs">{d.due_date} · {d.priority}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
        {!deadlines?.overdue?.length && !deadlines?.upcoming?.length && (
          <p className="text-gray-500 text-sm">No upcoming or overdue deadlines.</p>
        )}
      </div>
    </div>
  );
}