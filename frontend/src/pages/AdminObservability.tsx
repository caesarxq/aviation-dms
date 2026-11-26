import { useQuery, useQueryClient, useMutation } from "@tanstack/react-query";
import { useState } from "react";
import type { ReactNode } from "react";
import {
  Activity,
  Database,
  GitCommitHorizontal,
  Mail,
  Play,
  RefreshCw,
  ShieldCheck,
  UserCircle,
  Users,
  Wifi,
} from "lucide-react";
import api from "../api/client";
import { auditApi } from "../api/audit";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

function StatusPill({ ok, children, size }: { ok?: boolean; children: ReactNode; size?: "sm" | "md" | "xs" }) {
  const base = "badge px-2 py-0.5 rounded font-semibold";
  const sizeClass = size === "xs" ? "text-[9px] px-1" : size === "sm" ? "text-[10px] px-1.5" : "text-xs px-2";
  return <Badge variant={ok ? "default" : "destructive"} className={base + " " + sizeClass + " " + (ok ? "bg-kfl-status-success-bg text-kfl-status-success" : "bg-kfl-status-danger-bg text-kfl-status-danger")}>{children}</Badge>;
}

export default function AdminObservability() {
  const queryClient = useQueryClient();
  const [roleDrafts, setRoleDrafts] = useState<Record<string, string[]>>({});
  const [savingUserId, setSavingUserId] = useState<string | null>(null);
  const [invitingUserId, setInvitingUserId] = useState<string | null>(null);
  const [inviteError, setInviteError] = useState("");
  const [inviteNotice, setInviteNotice] = useState("");
  const [deliveryEmailDrafts, setDeliveryEmailDrafts] = useState<Record<string, string>>({});
  const [issuedInvites, setIssuedInvites] = useState<{
    user_id: string;
    full_name: string;
    delivery_id: string;
    recipient_email: string;
    delivery_status: string;
    delivery_method: "email" | "manual";
    expires_at: string;
    setup_url: string;
  }[]>([]);
  const [onboardingStep, setOnboardingStep] = useState<number | null>(null);

  const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

  const {
    data,
    isLoading,
    isError,
    error,
    refetch,
    isFetching,
  } = useQuery({
    queryKey: ["admin-observability"],
    queryFn: () => api.get("/p0/admin/observability").then((response: any) => response.data),
    refetchInterval: 15000,
  });

  // Backup trigger mutation
  const backupRunMutation = useMutation({
    mutationFn: () => api.post("/p0/backup/run").then((r: any) => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-observability"] });
      queryClient.invalidateQueries({ queryKey: ["backup-history"] });
      setBackupNotice("Backup run triggered successfully.");
    },
    onError: (cause: any) => {
      setBackupError(cause?.response?.data?.detail || "Backup run failed.");
    },
  });

  // Scanner test mutation
  const scannerTestMutation = useMutation({
    mutationFn: () => api.post("/p0/scanner/test").then((r: any) => r.data),
    onSuccess: (result) => {
      setScannerTestResult(result);
      queryClient.invalidateQueries({ queryKey: ["admin-observability"] });
    },
    onError: (cause: any) => {
      setScannerTestResult({ configured: false, reachable: null, detail: cause?.response?.data?.detail || "Scanner test failed" });
    },
  });

  // Upgrade notification mutation
  const [sendingNotification, setSendingNotification] = useState<string | null>(null);
  const sendNotificationMutation = useMutation({
    mutationFn: (versionId: string) => auditApi.sendUpgradeNotification(versionId),
    onSuccess: (_result, _versionId) => {
      setSendingNotification(null);
      queryClient.invalidateQueries({ queryKey: ["app-versions"] });
    },
    onError: (_cause, _versionId) => {
      setSendingNotification(null);
    },
  });

  // Backup history query
  const { data: backupHistoryRaw } = useQuery({
    queryKey: ["backup-history"],
    queryFn: () => api.get("/p0/backup/history?limit=10").then((response: any) => response.data),
    refetchInterval: 30000,
    enabled: true,
  });

  // Ensure backupHistory is always an object with events array
  const backupHistory = backupHistoryRaw && typeof backupHistoryRaw === 'object' && Array.isArray(backupHistoryRaw.events)
    ? backupHistoryRaw
    : { events: [] };

  const backupRuns = backupHistory.events;

  // App version releases
  const { data: appVersionsRaw, isLoading: versionsLoading } = useQuery({
    queryKey: ["app-versions"],
    queryFn: () => api.get("/p0/app-versions").then((response: any) => response.data),
    refetchInterval: 60000,
  });

  // Ensure appVersions is always an array
  const appVersions = Array.isArray(appVersionsRaw) ? appVersionsRaw : [];

  // Audit events browser
  const { data: auditEventsRaw, isLoading: auditLoading } = useQuery({
    queryKey: ["audit-events-admin"],
    queryFn: () => api.get("/p0/audit-events", { params: { limit: 50 } }).then((response: any) => response.data),
    refetchInterval: 120000,
  });

  // Ensure auditEvents is always an array
  const auditEvents = Array.isArray(auditEventsRaw) ? auditEventsRaw : [];

  const [backupNotice, setBackupNotice] = useState("");
  const [backupError, setBackupError] = useState("");
  const [scannerTestResult, setScannerTestResult] = useState<any>(null);

  async function saveRoles(user: any) {
    const roles = roleDrafts[user.user_id] ?? user.roles ?? [user.role];
    if (roles.length === 0) {
      return;
    }
    setSavingUserId(user.user_id);
    try {
      await api.put("/p0/auth/users/" + encodeURIComponent(user.user_id) + "/roles", { roles });
      setRoleDrafts((current) => {
        const next = { ...current };
        delete next[user.user_id];
        return next;
      });
      await queryClient.invalidateQueries({ queryKey: ["admin-observability"] });
    } catch (cause: any) {
      // Error will be shown by the invalidated query refetch
    } finally {
      setSavingUserId(null);
    }
  }

  async function handleInvite(user: any, deliveryMethod: "email" | "manual", deliveryEmail?: string) {
    setInviteError("");
    setInviteNotice("");
    const overrideEmail = (deliveryEmail || "").trim();
    const email = overrideEmail || (user.email || "").trim();
    if (!email) {
      setInviteError("This account has no registered email address. Update and verify it against the approved roster first, or enter a delivery address.");
      return;
    }
    if (!EMAIL_REGEX.test(email)) {
      setInviteError("The delivery email address is invalid. Correct the address before inviting.");
      return;
    }
    setInvitingUserId(user.user_id);
    try {
      const resend = issuedInvites.some((invite) => invite.user_id === user.user_id);
      const payload: Record<string, unknown> = {
        username: user.username,
        delivery_method: deliveryMethod,
        resend,
      };
      if (overrideEmail) {
        payload.delivery_email = overrideEmail;
      }
      const inviteResponse = await api.post("/p0/auth/invites", payload);
      const delivery = {
        user_id: user.user_id,
        full_name: user.full_name || user.username,
        delivery_id: inviteResponse.data.delivery_id,
        recipient_email: inviteResponse.data.recipient_email,
        delivery_status: inviteResponse.data.delivery_status,
        delivery_method: deliveryMethod,
        expires_at: inviteResponse.data.expires_at,
        setup_url: inviteResponse.data.setup_url || "",
      };
      setIssuedInvites((previous) => [
        ...previous.filter((invite) => invite.user_id !== user.user_id),
        delivery,
      ]);
      setInviteNotice(deliveryMethod === "manual"
        ? "Manual setup link generated for " + delivery.recipient_email + ". Share it only through the approved secure channel; it expires within 24 hours."
        : "Email accepted by SMTP for " + delivery.recipient_email + ". The one-time setup link expires within 24 hours.");
      await queryClient.invalidateQueries({ queryKey: ["admin-observability"] });
    } catch (cause: any) {
      const failedDelivery = cause?.response?.data;
      if (failedDelivery?.delivery_id) {
        setIssuedInvites((previous) => [
          ...previous.filter((invite) => invite.user_id !== user.user_id),
          {
            user_id: user.user_id,
            full_name: user.full_name || user.username,
            delivery_id: failedDelivery.delivery_id,
            recipient_email: failedDelivery.recipient_email || email,
            delivery_status: failedDelivery.delivery_status || "failed",
            delivery_method: failedDelivery.delivery_status === "manual"
              ? "manual"
              : failedDelivery.delivery_status === "sent" || failedDelivery.delivery_status === "pending"
                ? "email"
                : deliveryMethod,
            expires_at: failedDelivery.expires_at || "",
            setup_url: failedDelivery.setup_url || "",
          },
        ]);
      }
      setInviteError(cause?.response?.data?.detail || "Unable to issue invite. Retry or check administrator access.");
    } finally {
      setInvitingUserId(null);
    }
  }

  if (isLoading) return <div className="app-page"><div className="app-surface p-10 text-center text-sm text-kfl-muted">Loading system observability…</div></div>;
  if (isError) {
    const status = (error as any)?.response?.status;
    return <div className="app-page"><div className="app-surface border border-rose-200 bg-rose-50 p-6 text-sm text-rose-800">{status === 403 ? "System administrator access is required." : "Unable to load observability data."}</div></div>;
  }

  const dbOk = data?.database?.status === "ok";
  const healthOk = data?.health?.status === "ok";
  const workflowCounts = data?.workflows?.document_versions || {};
  const health = data?.health || {};
  const backup = health.backup || {};
  const scanner = health.scanner || {};

  return (
    <div className="app-page">
      <header className="app-page-header">
        <div>
          <div className="app-eyebrow">Administration</div>
          <h1 className="app-title">System Observability</h1>
          <p className="app-subtitle">System health, workflow posture, audit activity, backup state, and administrator-controlled access profiles.
</p>
        </div>
        <Button onClick={() => refetch()} variant="outline" size="sm" disabled={isFetching}>
          <RefreshCw size={15} className={isFetching ? "animate-spin" : ""} /> Refresh
        </Button>
      </header>

      <section className="mb-6 grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-6">
        <div className="app-surface p-5">
          <div className="flex items-center justify-between">
            <div className="app-label">API health</div>
            <Activity className="text-emerald-600" size={20} />
          </div>
          <div className="mt-3"><StatusPill ok={healthOk}>{healthOk ? "Healthy" : "Degraded"}</StatusPill></div>
          <p className="mt-2 text-xs text-kfl-muted">Scheduler: {data?.health?.scheduler}</p>
        </div>
        <div className="app-surface p-5">
          <div className="flex items-center justify-between">
            <div className="app-label">Database</div>
            <Database className="text-kfl-blue" size={20} />
          </div>
          <div className="mt-3"><StatusPill ok={dbOk}>{dbOk ? "Healthy" : "Degraded"}</StatusPill></div>
          <p className="mt-2 text-xs text-kfl-muted">Integrity: {data?.database?.integrity}</p>
        </div>
        <div className="app-surface p-5">
          <div className="flex items-center justify-between">
            <div className="app-label">Build version</div>
            <GitCommitHorizontal className="text-kfl-blue" size={20} />
          </div>
          <div className="mt-3 text-sm font-bold text-kfl-text break-all">{data?.version?.release_tag || "dev"}</div>
          <p className="mt-2 text-xs text-kfl-muted break-all">API {data?.version?.api_version || "—"}{data?.version?.git_sha ? ` · ${data?.version?.git_sha.slice(0, 12)}` : ""}</p>
        </div>
        <div className="app-surface p-5">
          <div className="flex items-center justify-between">
            <div className="app-label">Active users</div>
            <Users className="text-kfl-blue" size={20} />
          </div>
          <div className="mt-3 text-3xl font-bold text-kfl-text">{data?.users?.active ?? 0}</div>
          <p className="mt-2 text-xs text-kfl-muted">{data?.users?.total ?? 0} total profiles</p>
        </div>
        <div className="app-surface p-5">
          <div className="flex items-center justify-between">
            <div className="app-label">Audit activity</div>
            <ShieldCheck className="text-amber-600" size={20} />
          </div>
          <div className="mt-3 text-3xl font-bold text-kfl-text">{data?.audit?.events_last_24h ?? 0}</div>
          <p className="mt-2 text-xs text-kfl-muted">events in last 24 hours</p>
        </div>
        <div className="app-surface p-5">
          <div className="flex items-center justify-between">
            <div className="app-label">Backup scheduler</div>
            <Play className={backup.enabled ? "text-emerald-600" : "text-kfl-muted"} size={20} />
          </div>
          <div className="mt-3"><StatusPill ok={backup.enabled && backup.running}>{backup.running ? "Running" : backup.enabled ? "Stopped" : "Disabled"}</StatusPill></div>
          <p className="mt-2 text-xs text-kfl-muted">{backup.enabled ? `Runs: ${backup.run_count} · Failures: ${backup.failure_count}` : "Backups not configured"}</p>
          {backup.last_error && (
            <p className="mt-1 text-xs text-rose-600" title={backup.last_error}>Last error: {backup.last_error.slice(0, 60)}…</p>
          )}
        </div>
        <div className="app-surface p-5">
          <div className="flex items-center justify-between">
            <div className="app-label">ClamAV scanner</div>
            <Wifi className={scanner.reachable === true ? "text-emerald-600" : scanner.reachable === false ? "text-rose-600" : "text-kfl-muted"} size={20} />
          </div>
          <div className="mt-3">
            {scanner.configured === false ? (
              <StatusPill ok={false}>Not configured</StatusPill>
            ) : scanner.reachable === true ? (
              <StatusPill ok={true}>Reachable</StatusPill>
            ) : scanner.reachable === false ? (
              <StatusPill ok={false}>Unreachable</StatusPill>
            ) : (
              <span className="text-xs text-kfl-muted">Testing…</span>
            )}
          </div>
          <p className="mt-2 text-xs text-kfl-muted">{scanner.detail || (scanner.configured === false ? "Set DMS_CLAMD_HOST/PORT" : "")}</p>
          <Button
            className="mt-2 px-3 py-1.5 text-xs"
            variant="outline"
            size="sm"
            onClick={() => scannerTestMutation.mutate()}
            disabled={scannerTestMutation.isPending}
          >
            {scannerTestMutation.isPending ? "Testing…" : "Test connection"}
          </Button>
          {scannerTestResult && (
            <p className="mt-1 text-xs">{scannerTestResult.reachable === true ? "✓ Reachable" : scannerTestResult.reachable === false ? "✗ Unreachable" : "—"} {scannerTestResult.detail}</p>
          )}
        </div>
      </section>

      <section className="mb-6 grid grid-cols-1 gap-5 xl:grid-cols-2">
        <div className="app-surface overflow-hidden">
          <div className="border-b border-kfl-border px-5 py-4"><h2 className="font-bold text-kfl-text">Workflow posture</h2><p className="mt-1 text-xs text-kfl-muted">Current state counts; unexpected states are visible immediately.</p></div>
          <div className="grid grid-cols-2 gap-3 p-5 md:grid-cols-4">
            {Object.entries(workflowCounts).map(([state, count]) => <div key={state} className="rounded-lg border border-kfl-border bg-kfl-surface-subtle p-3"><div className="text-xs text-kfl-muted">{state.replace(/_/g, " ")}</div><div className="mt-1 text-2xl font-bold text-kfl-text">{String(count)}</div></div>)}
          </div>
        </div>
        <div className="app-surface overflow-hidden">
          <div className="border-b border-kfl-border px-5 py-4"><h2 className="font-bold text-kfl-text">Table volumes</h2><p className="mt-1 text-xs text-kfl-muted">Persisted records across the core control domains.</p></div>
          <div className="grid grid-cols-2 gap-3 p-5 md:grid-cols-4">
            {Object.entries(data?.tables || {}).map(([table, count]) => <div key={table} className="rounded-lg border border-kfl-border bg-kfl-surface-subtle p-3"><div className="truncate text-xs text-kfl-muted">{table.replace(/_/g, " ")}</div><div className="mt-1 text-2xl font-bold text-kfl-text">{String(count)}</div></div>)}
          </div>
        </div>
      </section>

      <section className="mb-6 grid grid-cols-1 gap-6 xl:grid-cols-2">
        <section className="app-surface overflow-hidden">
          <div className="flex items-center gap-2 border-b border-kfl-border px-5 py-4">
            <UserCircle className="text-kfl-blue" size={18} />
            <div>
              <h2 className="font-bold text-kfl-text">User Onboarding Guide</h2>
              <p className="mt-1 text-xs text-kfl-muted">Step-by-step process for onboarding a new user to Aviation DMS.</p>
            </div>
          </div>
          <div className="p-5 space-y-4">
            <div className="flex gap-3">
              <div className="flex-shrink-0 w-6 h-6 rounded-full border border-kfl-border text-xs text-kfl-muted flex items-center justify-center">
                {onboardingStep !== null && onboardingStep <= 1 ? (
                  <span className="text-emerald-600 font-bold">1</span>
                ) : (
                  <span className="text-kfl-muted">1</span>
                )}
              </div>
              <div>
                <div className="font-semibold text-kfl-text">{onboardingStep !== null && onboardingStep <= 1 ? "1. Invite the user" : "1. Invite the user ✓"}</div>
                <div className="text-xs text-kfl-muted">
                  {onboardingStep !== null && onboardingStep <= 1
                    ? "Confirm the account's registered email against the approved roster. Send the invitation to that address; role assignments are managed separately."
                    : "Confirm the registered email against the approved roster, then send the invitation email."}
                </div>
              </div>
            </div>
            <div className="flex gap-3">
              <div className="flex-shrink-0 w-6 h-6 rounded-full border border-kfl-border text-xs text-kfl-muted flex items-center justify-center">
                {onboardingStep !== null && onboardingStep <= 2 ? (
                  <span className="text-emerald-600 font-bold">2</span>
                ) : (
                  <span className="text-kfl-muted">2</span>
                )}
              </div>
              <div>
                <div className="font-semibold text-kfl-text">{onboardingStep !== null && onboardingStep <= 2 ? "2. Confirm email status" : "2. Confirm email status"}</div>
                <div className="text-xs text-kfl-muted">
                  {onboardingStep !== null && onboardingStep <= 2
                    ? "A successful request means SMTP accepted the message, not that it reached the inbox. Check the delivery reference; reissuing creates a fresh link and invalidates the prior one."
                    : "Review the delivery status and reference. Reissue only when needed; a new link invalidates the previous invitation."}
                </div>
              </div>
            </div>
            <div className="flex gap-3">
              <div className="flex-shrink-0 w-6 h-6 rounded-full border border-kfl-border text-xs text-kfl-muted flex items-center justify-center">
                {onboardingStep !== null && onboardingStep <= 3 ? (
                  <span className="text-emerald-600 font-bold">3</span>
                ) : (
                  <span className="text-kfl-muted">3</span>
                )}
              </div>
              <div>
                <div className="font-semibold text-kfl-text">{onboardingStep !== null && onboardingStep <= 3 ? "3. User completes password setup" : "3. User completes password setup"}</div>
                <div className="text-xs text-kfl-muted">
                  {onboardingStep !== null && onboardingStep <= 3
                    ? "The user follows the secure one-time link in the email and creates a password within 24 hours."
                    : "The user follows the secure one-time email link and creates a password within 24 hours."}
                </div>
              </div>
            </div>
            <div className="flex gap-3">
              <div className="flex-shrink-0 w-6 h-6 rounded-full border border-kfl-border text-xs text-kfl-muted flex items-center justify-center">
                {onboardingStep !== null && onboardingStep <= 4 ? (
                  <span className="text-emerald-600 font-bold">4</span>
                ) : (
                  <span className="text-kfl-muted">4</span>
                )}
              </div>
              <div>
                <div className="font-semibold text-kfl-text">{onboardingStep !== null && onboardingStep <= 4 ? "4. Verify access" : "4. Verify access"}</div>
                <div className="text-xs text-kfl-muted">
                  {onboardingStep !== null && onboardingStep <= 4
                    ? "Confirm the user can log in and access the features assigned to their roles. Adjust roles here if needed."
                    : "Confirm the user can log in and access their assigned features."}
                </div>
              </div>
            </div>
            <div className="flex items-center gap-2 mt-4">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setOnboardingStep((s) => (s === null ? 1 : s === 4 ? null : (s ?? 1) + 1))}
              >
                {onboardingStep === null ? "Start guide" : onboardingStep === 4 ? "Complete guide" : "Next step"}
              </Button>
            </div>
          </div>
        </section>

        <section className="app-surface overflow-hidden">
          <div className="flex items-center gap-2 border-b border-kfl-border px-5 py-4">
            <Mail className="text-kfl-blue" size={18} />
            <div>
              <h2 className="font-bold text-kfl-text">Backup control</h2>
              <p className="mt-1 text-xs text-kfl-muted">Trigger an on-demand backup and review recent backup history.</p>
            </div>
          </div>
          <div className="p-5">
            <Button
              variant="default"
              size="sm"
              onClick={() => backupRunMutation.mutate()}
              disabled={backupRunMutation.isPending || !backup.enabled}
            >
              {backupRunMutation.isPending ? "Running backup…" : "Run backup now"}
            </Button>
            {!backup.enabled && (
              <p className="mt-3 text-xs text-rose-600">Backup scheduler is not enabled. Set DMS_BACKUP_ENABLED=true and configure DMS_BACKUP_DATA_ROOT and DMS_BACKUP_DEST_ROOT.</p>
            )}
            {backupNotice && <div role="status" className="mt-3 rounded border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800">{backupNotice}</div>}
            {backupError && <div role="alert" className="mt-3 rounded border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">{backupError}</div>}
          </div>
          <div className="border-t border-kfl-border px-5 py-4">
            <h3 className="font-semibold text-kfl-text text-sm">Recent backup history</h3>
            <div className="overflow-x-auto mt-3">
              <table className="min-w-full text-xs">
                <thead className="border-b border-kfl-border bg-kfl-surface-subtle">
                  <tr>
                    <th className="px-3 py-2 text-left font-semibold text-kfl-muted">Time</th>
                    <th className="px-3 py-2 text-left font-semibold text-kfl-muted">Action</th>
                    <th className="px-3 py-2 text-left font-semibold text-kfl-muted">Status</th>
                    <th className="px-3 py-2 text-left font-semibold text-kfl-muted">Detail</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-kfl-border">
                  {backupRuns.length === 0 ? (
                    <tr><td colSpan={4} className="px-3 py-4 text-center text-xs text-kfl-muted">No backup events recorded yet.</td></tr>
                  ) : (
                    backupRuns.slice(0, 10).map((event: any) => {
                      const details = typeof event.details === "string" ? event.details : JSON.stringify(event.details || {});
                      const accepted = event.details?.accepted;
                      return (
                        <tr key={event.event_id}>
                          <td className="px-3 py-2 font-mono">{event.timestamp?.slice(0, 19).replace("T", " ") ?? "—"}</td>
                          <td className="px-3 py-2 font-mono">{event.action}</td>
                          <td className="px-3 py-2">
                            <StatusPill ok={accepted !== false} size="xs">{accepted === true ? "Accepted" : accepted === false ? "Rejected" : event.action}</StatusPill>
                          </td>
                          <td className="px-3 py-2 truncate max-w-[200px] text-kfl-muted">{details.slice(0, 100)}</td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </section>

        <div className="app-surface overflow-hidden">
          <div className="border-b border-kfl-border px-5 py-4"><h2 className="font-bold text-kfl-text">Scanner status</h2><p className="mt-1 text-xs text-kfl-muted">Malware scanner (clamd) connectivity and last probe result.</p></div>
          <div className="p-5">
            <div className="flex items-center justify-between mb-4">
              <div>
                <div className="font-bold text-kfl-text">ClamAV endpoint</div>
                <div className="text-xs text-kfl-muted font-mono">{scanner.host ?? "—"}:{scanner.port ?? "—"}</div>
              </div>
              <div className="text-right">
                <div className="text-2xl font-bold">
                  {scanner.reachable === true ? "OK" : scanner.reachable === false ? "DOWN" : "—"}
                </div>
              </div>
            </div>
            <div className="space-y-3">
              <div className="flex items-center justify-between p-3 rounded border border-kfl-border bg-kfl-surface">
                <span className="text-sm text-kfl-muted">Configured</span>
                <span className="text-sm font-mono">{scanner.configured === true ? "Yes" : "No"}</span>
              </div>
              <div className="flex items-center justify-between p-3 rounded border border-kfl-border bg-kfl-surface">
                <span className="text-sm text-kfl-muted">Reachable</span>
                <span className={`text-sm font-mono ${scanner.reachable === true ? "text-emerald-600" : scanner.reachable === false ? "text-rose-600" : "text-kfl-muted"}`}>
                  {scanner.reachable === true ? "Yes" : scanner.reachable === false ? "No" : "Unknown"}
                </span>
              </div>
            </div>
            <p className="mt-3 text-xs text-kfl-muted">{scanner.detail || "No scanner configured. Set DMS_CLAMD_HOST and DMS_CLAMD_PORT."}</p>
          </div>
        </div>
      </section>

      <section className="app-surface overflow-hidden">
        <div className="border-b border-kfl-border px-5 py-4"><h2 className="font-bold text-kfl-text">User invitations</h2><p className="mt-1 text-xs text-kfl-muted">Email one-time account setup links to registered addresses; use manual-link fallback only through an approved secure channel.</p></div>
        {inviteError && <div role="alert" className="m-4 rounded border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">{inviteError}</div>}
        {inviteNotice && <div role="status" className="m-4 rounded border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800">{inviteNotice}</div>}
        <div className="overflow-x-auto">
          <table className="min-w-full">
            <thead className="border-b border-kfl-border bg-kfl-surface-subtle">
              <tr>
                <th className="px-5 py-3 text-left text-[11px] uppercase text-kfl-muted">Username</th>
                <th className="px-5 py-3 text-left text-[11px] uppercase text-kfl-muted">Assigned roles</th>
                <th className="px-5 py-3 text-left text-[11px] uppercase text-kfl-muted">Invite email</th>
                <th className="px-5 py-3 text-left text-[11px] uppercase text-kfl-muted">Department</th>
                <th className="px-5 py-3 text-left text-[11px] uppercase text-kfl-muted">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-kfl-border">
              {(data?.user_profiles || []).map((user: any) => {
                const assignedRoles = user.roles || [user.role];
                const selectedRoles = roleDrafts[user.user_id] ?? assignedRoles;
                const existingInvite = issuedInvites.find((inv) => inv.user_id === user.user_id);
                const controlKey = encodeURIComponent(user.user_id).replace(/%/g, "_");
                return (
                  <tr key={user.user_id}>
                    <td className="px-5 py-3">
                      <div className="text-sm font-semibold text-kfl-text">{user.full_name}</div>
                      <div className="text-xs text-kfl-muted">{user.user_id} · {user.email}</div>
                    </td>
                    <td className="px-5 py-3 text-xs text-kfl-text">
                      {user.merged_into_user_id ? (
                        <>
                          <div className="font-mono">{assignedRoles.join(", ")}</div>
                          <div className="mt-1 text-[10px] text-kfl-muted">Merged into {user.merged_into_user_id}; historical ID retained</div>
                        </>
                      ) : user.is_active ? (
                        <div className="min-w-[230px] space-y-2">
                          <label htmlFor={`roles-${controlKey}`} className="block font-semibold">Assigned roles for {user.full_name}</label>
                          <p className="text-[10px] text-kfl-muted">Use Ctrl/Command to select multiple roles.</p>
                          <select
                            id={`roles-${controlKey}`}
                            name={`roles-${controlKey}`}
                            aria-label={`Assigned roles for ${user.full_name}`}
                            multiple
                            size={Math.min(5, Math.max(3, data?.role_matrix?.length || 3))}
                            value={selectedRoles}
                            onChange={(event) => {
                              const roles = Array.from(event.currentTarget.selectedOptions, (option) => option.value).sort();
                              setRoleDrafts((current) => ({ ...current, [user.user_id]: roles }));
                            }}
                            className="w-full rounded border border-kfl-border bg-kfl-surface px-2 py-1.5 text-xs text-kfl-text"
                          >
                            {(data?.role_matrix || []).map((profile: any) => <option key={profile.role} value={profile.role}>{profile.role.replace(/_/g, " ")}</option>)}
                          </select>
                          <div className="text-[10px] text-kfl-muted">Default role: {user.role}</div>
                          <Button
                            type="button"
                            variant="outline"
                            size="sm"
                            disabled={savingUserId !== null}
                            aria-label={`Save roles for ${user.full_name}`}
                            onClick={() => void saveRoles(user)}
                          >
                            {savingUserId === user.user_id ? "Saving…" : "Save roles"}
                          </Button>
                        </div>
                      ) : (
                        <span className="font-mono">{assignedRoles.join(", ")}</span>
                      )}
                    </td>
                    <td className="px-5 py-3 text-xs text-kfl-text">
                      {!user.has_password && user.is_active ? (
                        <div className="space-y-2">
                          <div className="font-semibold">{user.email || "No registered email"}</div>
                          <p className="text-[10px] text-kfl-muted">Optional: enter a delivery address to override the registered email. Blank delivers to the registered address.</p>
                          <input
                            type="email"
                            value={(deliveryEmailDrafts[user.user_id] || "")}
                            onChange={(event) => setDeliveryEmailDrafts((prev) => ({ ...prev, [user.user_id]: event.target.value }))}
                            placeholder={user.email || "Delivery email (optional)"}
                            disabled={invitingUserId !== null}
                            className="w-full rounded border border-kfl-border bg-kfl-bg px-2 py-1.5 text-xs text-kfl-text"
                            aria-label={`Delivery email override for ${user.full_name}`}
                          />
                          <div className="text-[10px] text-kfl-muted">Roles: {assignedRoles.map((r: string) => r.replace(/_/g, " ")).join(", ")}</div>
                          <div className="flex flex-wrap gap-2">
                            <Button
                              type="button"
                              variant="outline"
                              size="sm"
                              disabled={invitingUserId !== null}
                              aria-label={`${existingInvite?.delivery_method === "email" ? "Reissue" : "Send"} invite email for ${user.full_name}`}
                              onClick={() => void handleInvite(user, "email", deliveryEmailDrafts[user.user_id] || undefined)}
                            >
                              {invitingUserId === user.user_id ? "Sending…" : existingInvite?.delivery_method === "email" ? "Reissue invite email" : "Send invite email"}
                            </Button>
                            <Button
                              type="button"
                              variant="outline"
                              size="sm"
                              disabled={invitingUserId !== null}
                              aria-label={`${existingInvite?.delivery_method === "manual" ? "Reissue" : "Generate"} manual invite for ${user.full_name}`}
                              onClick={() => void handleInvite(user, "manual", deliveryEmailDrafts[user.user_id] || undefined)}
                            >
                              {invitingUserId === user.user_id ? "Preparing…" : existingInvite?.delivery_method === "manual" ? "Reissue manual invite" : "Generate manual invite"}
                            </Button>
                          </div>
                        </div>
                      ) : (
                        <span className="font-mono">{user.has_password ? "Password set" : "Inactive"}</span>
                      )}
                      {existingInvite && (
                        <div className="mt-2 space-y-1" aria-label={`Latest invite delivery for ${user.full_name}`}>
                          <div className="text-[10px] text-kfl-muted">Delivery: {existingInvite.delivery_status}</div>
                          <div className="font-mono text-[10px] text-kfl-muted">Reference: {existingInvite.delivery_id}</div>
                          {existingInvite.expires_at && <div className="text-[10px] text-kfl-muted">Expires: {existingInvite.expires_at}</div>}
                          {existingInvite.delivery_method === "manual" && existingInvite.setup_url && (
                            <div className="space-y-1">
                              <label htmlFor={`manual-invite-link-${controlKey}`} className="block text-[10px] font-semibold">Manual link — share securely; shown once</label>
                              <textarea
                                id={`manual-invite-link-${controlKey}`}
                                aria-label={`Manual setup link for ${user.full_name}`}
                                readOnly
                                rows={2}
                                value={existingInvite.setup_url}
                                onFocus={(event) => event.currentTarget.select()}
                                className="w-full rounded border border-kfl-border bg-kfl-surface px-2 py-1 font-mono text-[10px] text-kfl-text"
                              />
                            </div>
                          )}
                        </div>
                      )}
                    </td>
                    <td className="px-5 py-3 text-sm text-kfl-secondary">{user.department || "—"}</td>
                    <td className="px-5 py-3"><StatusPill ok={Boolean(user.is_active)}>{user.is_active ? "Active" : "Inactive"}</StatusPill></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

      <section className="app-surface overflow-hidden">
        <div className="border-b border-kfl-border px-5 py-4"><h2 className="font-bold text-kfl-text">Role matrix</h2><p className="mt-1 text-xs text-kfl-muted">Explicit permissions granted to each profile.</p></div>
        <div className="overflow-x-auto"><table className="min-w-full"><thead className="border-b border-kfl-border bg-kfl-surface-subtle"><tr><th className="px-5 py-3 text-left text-[11px] uppercase text-kfl-muted">Role</th><th className="px-5 py-3 text-left text-[11px] uppercase text-kfl-muted">Access level</th><th className="px-5 py-3 text-left text-[11px] uppercase text-kfl-muted">Permissions</th></tr></thead><tbody className="divide-y divide-kfl-border">{data?.role_matrix?.map((profile: any) => <tr key={profile.role}><td className="px-5 py-3 font-mono text-xs font-semibold text-kfl-text">{profile.role}</td><td className="px-5 py-3 text-sm text-kfl-secondary">{profile.access_level}</td><td className="px-5 py-3 text-xs text-kfl-secondary">{profile.permissions.join(", ")}</td></tr>)}</tbody></table></div>
      </section>

      {/* Release History */}
      <section className="mb-6 app-surface overflow-hidden">
        <div className="border-b border-kfl-border px-5 py-4">
          <h2 className="font-bold text-kfl-text">Release history</h2>
          <p className="mt-1 text-xs text-kfl-muted">Application versions released and upgrade notifications sent.</p>
        </div>
        <div className="p-5">
          {versionsLoading ? (
            <div className="text-center text-xs text-kfl-muted py-4">Loading release history…</div>
          ) : appVersions.length === 0 ? (
            <div className="text-center text-xs text-kfl-muted py-4">No releases recorded yet.</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full text-xs">
                <thead className="border-b border-kfl-border bg-kfl-surface-subtle">
                  <tr>
                    <th className="px-3 py-2 text-left font-semibold text-kfl-muted">Version</th>
                    <th className="px-3 py-2 text-left font-semibold text-kfl-muted">Released</th>
                    <th className="px-3 py-2 text-left font-semibold text-kfl-muted">Released by</th>
                    <th className="px-3 py-2 text-left font-semibold text-kfl-muted">Notifications</th>
                    <th className="px-3 py-2 text-right font-semibold text-kfl-muted">Changelog</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-kfl-border">
                  {appVersions.slice(0, 10).map((v: any) => (
                    <tr key={v.version_id}>
                      <td className="px-3 py-2 font-mono text-kfl-text">{v.version_number}</td>
                      <td className="px-3 py-2 text-kfl-muted">{v.released_at?.slice(0, 16).replace("T", " ") ?? "—"}</td>
                      <td className="px-3 py-2 text-kfl-muted">{v.released_by}</td>
                      <td className="px-3 py-2">
                        <span className={`text-xs font-mono ${v.notification_sent ? "text-emerald-600" : "text-kfl-muted"}`}>
                          {v.notification_sent ? "Sent" : "Pending"}
                        </span>
                      </td>
                      <td className="px-3 py-2 text-right">
                        <div className="flex items-center justify-end gap-1">
                          {!v.notification_sent && (
                            <button
                              type="button"
                              disabled={sendingNotification === v.version_id || sendNotificationMutation.isPending}
                              onClick={() => void sendNotificationMutation.mutate(v.version_id)}
                              className="text-xs text-kfl-blue hover:underline"
                            >
                              {sendingNotification === v.version_id ? "Sending…" : "Send notification"}
                            </button>
                          )}
                          <button
                            type="button"
                            onClick={() => alert(v.changelog_non_technical)}
                            className="text-xs text-kfl-blue hover:underline"
                          >
                            View changelog
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </section>

      {/* Audit Events */}
      <section className="app-surface overflow-hidden">
        <div className="border-b border-kfl-border px-5 py-4">
          <h2 className="font-bold text-kfl-text">System audit events</h2>
          <p className="mt-1 text-xs text-kfl-muted">Recent database mutations and user actions across the control system.</p>
        </div>
        <div className="p-5">
          {auditLoading ? (
            <div className="text-center text-xs text-kfl-muted py-4">Loading audit events…</div>
          ) : auditEvents.length === 0 ? (
            <div className="text-center text-xs text-kfl-muted py-4">No audit events recorded.</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full text-xs">
                <thead className="border-b border-kfl-border bg-kfl-surface-subtle">
                  <tr>
                    <th className="px-3 py-2 text-left font-semibold text-kfl-muted">Time</th>
                    <th className="px-3 py-2 text-left font-semibold text-kfl-muted">Entity</th>
                    <th className="px-3 py-2 text-left font-semibold text-kfl-muted">Action</th>
                    <th className="px-3 py-2 text-left font-semibold text-kfl-muted">Actor</th>
                    <th className="px-3 py-2 text-left font-semibold text-kfl-muted">Details</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-kfl-border">
                  {auditEvents.slice(0, 20).map((e: any) => (
                    <tr key={e.event_id}>
                      <td className="px-3 py-2 font-mono text-kfl-muted">{e.timestamp?.slice(0, 16).replace("T", " ") ?? "—"}</td>
                      <td className="px-3 py-2 font-mono text-kfl-text">{e.entity_type}</td>
                      <td className="px-3 py-2 text-kfl-text">{e.action}</td>
                      <td className="px-3 py-2 font-mono text-kfl-muted">{e.actor_id}</td>
                      <td className="px-3 py-2 truncate max-w-[200px] text-kfl-muted">{e.details ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </section>
    </div>
  );
};