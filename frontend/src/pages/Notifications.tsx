import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, AlertCircle, Info, Settings, SlidersHorizontal } from "lucide-react";
import { safetyApi } from "../api/safety";

const defaultPreferences = {
  email_enabled: true,
  document_review_hours: 48,
  mor_deadline_hours: 24,
  car_due_days: 3,
  roc_expiry_days: 90,
  distribution_ack_days: 7,
};

export function Notifications() {
  const qc = useQueryClient();
  const [statusFilter, setStatusFilter] = useState("");
  const [showPrefs, setShowPrefs] = useState(false);
  const [prefsForm, setPrefsForm] = useState(defaultPreferences);

  const { data, isLoading } = useQuery({
    queryKey: ["notifications", statusFilter],
    queryFn: () => safetyApi.listNotifications(statusFilter ? { status: statusFilter } : {}),
  });
  const { data: prefs } = useQuery({
    queryKey: ["notification-preferences"],
    queryFn: () => safetyApi.getNotificationPreferences(),
  });

  useEffect(() => {
    if (prefs) setPrefsForm({ ...defaultPreferences, ...prefs });
  }, [prefs]);

  const savePrefsMutation = useMutation({
    mutationFn: () => safetyApi.updateNotificationPreferences(prefsForm),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["notification-preferences"] }),
  });
  const markReadMutation = useMutation({
    mutationFn: (id: string) => safetyApi.markNotificationRead(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["notifications"] });
      qc.invalidateQueries({ queryKey: ["unread-notifications"] });
    },
  });

  const notifications = data?.notifications ?? [];
  const updatePref = (key: string, value: boolean | number) => setPrefsForm((current) => ({ ...current, [key]: value }));

  return (
    <div className="app-page">
      <header className="app-page-header">
        <div>
          <div className="app-eyebrow">Control centre</div>
          <h1 className="app-title">Notifications</h1>
          <p className="app-subtitle">Review system alerts and tune the timing of compliance reminders.</p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => setShowPrefs(!showPrefs)} className="app-btn-secondary">
            <Settings size={16} /> Preferences
          </button>
          <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="app-input w-auto min-w-[120px]">
            <option value="">All statuses</option>
            <option value="pending">Pending</option>
            <option value="sent">Sent</option>
            <option value="logged">Logged</option>
            <option value="read">Read</option>
          </select>
        </div>
      </header>

      {showPrefs && (
        <section className="app-surface mb-5 p-5" aria-label="Notification preferences">
          <div className="mb-5 flex items-start justify-between gap-4">
            <div>
              <div className="flex items-center gap-2"><SlidersHorizontal size={17} className="text-kfl-blue" /><h2 className="text-base font-bold text-kfl-text">Notification preferences</h2></div>
              <p className="mt-1 text-xs text-kfl-muted">Set when reminders should reach you. Changes apply to future checks.</p>
            </div>
            <button onClick={() => savePrefsMutation.mutate()} disabled={savePrefsMutation.isPending} className="app-btn-primary">
              {savePrefsMutation.isPending ? "Saving…" : "Save preferences"}
            </button>
          </div>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <label className="flex min-h-10 items-center gap-2 rounded-md border border-kfl-border bg-kfl-surface-subtle px-3 text-sm font-medium text-kfl-text">
              <input type="checkbox" checked={Boolean(prefsForm.email_enabled)} onChange={(e) => updatePref("email_enabled", e.target.checked)} className="h-4 w-4 accent-kfl-blue" />
              Email notifications enabled
            </label>
            {[
              ["document_review_hours", "Document review alert", "hours before"],
              ["mor_deadline_hours", "MOR deadline alert", "hours before"],
              ["car_due_days", "CAR due alert", "days before"],
              ["roc_expiry_days", "ROC expiry alert", "days before"],
              ["distribution_ack_days", "Distribution acknowledgement", "days before"],
            ].map(([key, label, suffix]) => (
              <label key={key} className="text-sm text-kfl-secondary">
                <span className="mb-1 block text-xs font-semibold text-kfl-muted">{label} ({suffix})</span>
                <input type="number" min={0} value={Number(prefsForm[key as keyof typeof prefsForm])} onChange={(e) => updatePref(key, Number(e.target.value))} className="app-input" />
              </label>
            ))}
          </div>
          {savePrefsMutation.isSuccess && <p className="mt-3 text-xs font-semibold text-emerald-700">Preferences saved.</p>}
        </section>
      )}

      {isLoading ? (
        <div className="app-surface p-10 text-center text-sm text-kfl-muted">Loading notifications…</div>
      ) : notifications.length === 0 ? (
        <div className="app-surface border-dashed p-10 text-center">
          <Check className="mx-auto mb-2 text-emerald-600" size={26} />
          <p className="text-sm font-bold text-kfl-text">No notifications in this view.</p>
          <p className="mt-1 text-xs text-kfl-muted">The system will surface new compliance and operational alerts here.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {notifications.map((n: any) => (
            <article key={n.notification_id} className={`app-surface border-l-4 p-4 ${n.status === "read" ? "border-l-kfl-border" : "border-l-kfl-blue"}`}>
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    {n.priority === "critical" || n.priority === "high" ? <AlertCircle size={16} className={n.priority === "critical" ? "text-red-600" : "text-amber-600"} /> : <Info size={16} className="text-kfl-blue" />}
                    <h2 className="truncate text-sm font-bold text-kfl-text">{n.subject}</h2>
                  </div>
                  <p className="mt-2 text-sm leading-6 text-kfl-secondary">{n.body}</p>
                  <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-kfl-muted">
                    <span>To: {n.recipient}</span><span>·</span><span>{n.created_at}</span>
                    <span className="app-status app-status-info">{n.status}</span>
                    {n.entity_type && <span className="rounded-full bg-purple-50 px-2 py-1 font-semibold text-purple-700">{n.entity_type}: {n.entity_id}</span>}
                  </div>
                </div>
                {n.status !== "read" && <button onClick={() => markReadMutation.mutate(n.notification_id)} className="app-btn-secondary shrink-0 px-3 py-2 text-xs"><Check size={14} /> Mark read</button>}
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}