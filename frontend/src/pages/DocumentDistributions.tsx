import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { p2Api } from "../api/p2";
import { Distribution } from "../types";
import { MailOpen, Plus, Send } from "lucide-react";

function statusClass(status: string) {
  switch (status.toLowerCase()) {
    case "pending": return "app-status app-status-warning";
    case "acknowledged": return "app-status app-status-healthy";
    case "sent": return "app-status app-status-info";
    case "failed": return "app-status app-status-critical";
    default: return "app-status app-status-info";
  }
}

export function DocumentDistributions() {
  const qc = useQueryClient();
  const [versionId, setVersionId] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [isCreating, setIsCreating] = useState(false);
  const [form, setForm] = useState({ version_id: "", recipient_id: "", channel: "email" });

  const { data: distributions = [], isLoading } = useQuery({
    queryKey: ["distributions", versionId, statusFilter],
    queryFn: () => p2Api.listDistributions({ version_id: versionId || undefined, status: statusFilter || undefined }),
  });

  const createMutation = useMutation({
    mutationFn: (data: any) => p2Api.createDistribution(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["distributions"] });
      setIsCreating(false);
      setForm({ version_id: "", recipient_id: "", channel: "email" });
    },
  });

  const ackMutation = useMutation({
    mutationFn: (id: string) => p2Api.acknowledgeDistribution(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["distributions"] }),
  });

  const stats = {
    total: distributions.length,
    pending: distributions.filter((d: Distribution) => d.status === "pending").length,
    acknowledged: distributions.filter((d: Distribution) => d.status === "acknowledged").length,
  };

  return (
    <div className="app-page">
      <header className="app-page-header">
        <div>
          <div className="app-eyebrow">Document Control</div>
          <h1 className="app-title">Document Distributions</h1>
          <p className="app-subtitle">Track issuance and acknowledgement of controlled document versions.</p>
        </div>
        <button className="app-btn" onClick={() => setIsCreating(true)}>
          <Plus size={16} /> New Distribution
        </button>
      </header>

      <section className="mb-5 grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="app-surface p-4">
          <div className="app-label">Total Distributions</div>
          <div className="mt-2 text-2xl font-bold text-kfl-text">{stats.total}</div>
        </div>
        <div className="app-surface p-4">
          <div className="app-label">Pending Acknowledgement</div>
          <div className="mt-2 text-2xl font-bold text-kfl-text">{stats.pending}</div>
        </div>
        <div className="app-surface p-4">
          <div className="app-label">Acknowledged</div>
          <div className="mt-2 text-2xl font-bold text-kfl-text">{stats.acknowledged}</div>
        </div>
      </section>

      <section className="app-surface overflow-hidden">
        <div className="flex flex-col gap-3 border-b border-kfl-border p-4 md:flex-row md:items-center md:justify-between">
          <div className="text-sm font-semibold text-kfl-text">Distributions</div>
          <div className="flex gap-2">
            <input
              id="distribution_version_id"
              name="version_id"
              placeholder="Version ID"
              className="app-input w-full md:w-auto"
              value={versionId}
              onChange={(e) => setVersionId(e.target.value)}
            />
            <select
              id="distribution_status"
              name="status"
              aria-label="Filter by status"
              className="app-input w-full md:w-auto"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
            >
              <option value="">All statuses</option>
              <option value="pending">Pending</option>
              <option value="acknowledged">Acknowledged</option>
              <option value="sent">Sent</option>
              <option value="failed">Failed</option>
            </select>
          </div>
        </div>

        {isLoading ? (
          <div className="p-10 text-center text-sm text-kfl-muted">Loading distributions…</div>
        ) : distributions.length === 0 ? (
          <div className="app-surface border-dashed p-10 text-center">
            <MailOpen size={26} className="mx-auto mb-2 text-kfl-muted" />
            <p className="text-sm font-bold text-kfl-text">No distributions recorded.</p>
            <p className="mt-1 text-xs text-kfl-muted">Issue a new distribution to track receipt and acknowledgement.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full">
              <thead className="border-b border-kfl-border bg-kfl-surface-subtle">
                <tr>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">ID</th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Version</th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Recipient</th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Channel</th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Status</th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Acknowledged</th>
                  <th className="px-4 py-3 text-right text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-kfl-border">
                {distributions.map((d: Distribution) => (
                  <tr key={d.distribution_id} className="transition hover:bg-kfl-surface-subtle">
                    <td className="px-4 py-4 font-mono text-[12px] text-kfl-text">{d.distribution_id}</td>
                    <td className="px-4 py-4 text-sm text-kfl-secondary">{d.version_id}</td>
                    <td className="px-4 py-4 text-sm text-kfl-secondary">{d.recipient_id}</td>
                    <td className="px-4 py-4 text-sm text-kfl-secondary">{d.channel}</td>
                    <td className="px-4 py-4"><span className={statusClass(d.status)}>{d.status}</span></td>
                    <td className="px-4 py-4 text-sm text-kfl-secondary">
                      {d.acknowledged_at ? new Date(d.acknowledged_at).toLocaleString() : "—"}
                    </td>
                    <td className="px-4 py-4 text-right">
                      {d.status !== "acknowledged" && (
                        <button
                          id={`ack_${d.distribution_id}`}
                          className="app-btn"
                          onClick={() => ackMutation.mutate(d.distribution_id)}
                        >
                          <Send size={14} /> Acknowledge
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {isCreating && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="app-surface w-full max-w-lg">
            <div className="border-b border-kfl-border px-5 py-4">
              <h2 className="app-modal-title">New Distribution</h2>
              <p className="mt-1 text-xs text-kfl-muted">Issue a controlled document version to a recipient.</p>
            </div>
            <div className="space-y-3 px-5 py-4">
              <label className="block text-sm text-kfl-secondary">
                <span className="mb-1 block text-xs font-semibold text-kfl-muted">Version ID</span>
                <input
                  id="distribution_create_version"
                  name="version_id"
                  className="app-input"
                  value={form.version_id}
                  onChange={(e) => setForm({ ...form, version_id: e.target.value })}
                />
              </label>
              <label className="block text-sm text-kfl-secondary">
                <span className="mb-1 block text-xs font-semibold text-kfl-muted">Recipient ID</span>
                <input
                  id="distribution_create_recipient"
                  name="recipient_id"
                  className="app-input"
                  value={form.recipient_id}
                  onChange={(e) => setForm({ ...form, recipient_id: e.target.value })}
                />
              </label>
              <label className="block text-sm text-kfl-secondary">
                <span className="mb-1 block text-xs font-semibold text-kfl-muted">Channel</span>
                <select
                  id="distribution_create_channel"
                  name="channel"
                  className="app-input"
                  value={form.channel}
                  onChange={(e) => setForm({ ...form, channel: e.target.value })}
                >
                  <option value="email">Email</option>
                  <option value="print">Print</option>
                  <option value="portal">Portal</option>
                </select>
              </label>
            </div>
            <div className="flex justify-end gap-2 border-t border-kfl-border px-5 py-4">
              <button className="app-btn app-btn-ghost" onClick={() => setIsCreating(false)}>Cancel</button>
              <button
                id="create_distribution_submit"
                className="app-btn"
                disabled={!form.version_id || !form.recipient_id || createMutation.isPending}
                onClick={() => createMutation.mutate(form)}
              >
                {createMutation.isPending ? "Creating…" : "Create"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
