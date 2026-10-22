import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { safetyApi } from "../api/safety";
import { Check, AlertCircle, Info } from "lucide-react";

export function Notifications() {
  const qc = useQueryClient();
  const [statusFilter, setStatusFilter] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["notifications", statusFilter],
    queryFn: () => safetyApi.listNotifications(statusFilter ? { status: statusFilter } : {}),
  });

  const notifications = data?.notifications ?? [];

  const markRead = (id: string) => {
    fetch(`/api/p1/notifications/${id}/read`, {
      method: "PATCH",
      headers: { "X-Role": "system_admin", "X-Actor": "admin" },
    }).then(() => {
      qc.invalidateQueries({ queryKey: ["notifications"] });
      qc.invalidateQueries({ queryKey: ["unread-notifications"] });
    });
  };

  return (
    <div className="p-6">
      <div className="flex justify-between items-center mb-4">
        <h1 className="text-2xl font-bold">Notifications</h1>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="border rounded px-3 py-2 text-sm"
        >
          <option value="">All</option>
          <option value="pending">Pending</option>
          <option value="sent">Sent</option>
          <option value="logged">Logged</option>
          <option value="read">Read</option>
        </select>
      </div>

      {isLoading ? (
        <p>Loading...</p>
      ) : notifications.length === 0 ? (
        <p className="text-gray-500">No notifications.</p>
      ) : (
        <div className="space-y-3">
          {notifications.map((n: any) => (
            <div
              key={n.notification_id}
              className={`bg-white p-4 rounded shadow border-l-4 ${
                n.status === "read" ? "border-gray-300" : "border-kfl-teal"
              }`}
            >
              <div className="flex justify-between items-start">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    {n.priority === "critical" && <AlertCircle size={16} className="text-red-500" />}
                    {n.priority === "high" && <AlertCircle size={16} className="text-orange-500" />}
                    {n.priority !== "critical" && n.priority !== "high" && <Info size={16} className="text-blue-500" />}
                    <span className="font-semibold text-sm">{n.subject}</span>
                  </div>
                  <p className="text-sm text-gray-600 mb-2">{n.body}</p>
                  <div className="flex gap-3 text-xs text-gray-400">
                    <span>To: {n.recipient}</span>
                    <span>{n.created_at}</span>
                    <span className={`px-1.5 py-0.5 rounded ${
                      n.status === "read" ? "bg-gray-100 text-gray-600" :
                      n.status === "sent" ? "bg-green-100 text-green-700" :
                      n.status === "logged" ? "bg-blue-100 text-blue-700" :
                      "bg-yellow-100 text-yellow-700"
                    }`}>
                      {n.status}
                    </span>
                    {n.entity_type && (
                      <span className="px-1.5 py-0.5 rounded bg-purple-100 text-purple-700">
                        {n.entity_type}: {n.entity_id}
                      </span>
                    )}
                  </div>
                </div>
                {n.status !== "read" && (
                  <button
                    onClick={() => markRead(n.notification_id)}
                    className="ml-3 text-xs text-kfl-teal hover:underline flex items-center gap-1"
                  >
                    <Check size={14} /> Mark read
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}