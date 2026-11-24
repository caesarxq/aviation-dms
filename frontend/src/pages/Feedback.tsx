import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { safetyApi } from "../api/safety";
import { Feedback, FeedbackCreate } from "../types";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select";

export function FeedbackPage() {
  const qc = useQueryClient();
  const [statusFilter, setStatusFilter] = useState("");
  const [issueFilter, setIssueFilter] = useState("");
  const [isCreating, setIsCreating] = useState(false);
  const [viewing, setViewing] = useState<Feedback | null>(null);
  const [form, setForm] = useState<FeedbackCreate>({
    issue_type: "bug",
    app_area: "",
    goal: "",
    reproduction_steps: "",
    expected_result: "",
    actual_result: "",
    impact: "workaround",
    priority: "P3",
    observation_time: "",
    contact: "",
    screenshot_info: "",
  });

  const { data: items = [], isLoading } = useQuery({
    queryKey: ["feedback", statusFilter, issueFilter],
    queryFn: () =>
      safetyApi.listFeedback({
        status: statusFilter || undefined,
        issue_type: issueFilter || undefined,
      }),
  });

  const createMutation = useMutation({
    mutationFn: (data: any) => safetyApi.createFeedback(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["feedback"] });
      setIsCreating(false);
      setForm({
        issue_type: "bug",
        app_area: "",
        goal: "",
        reproduction_steps: "",
        expected_result: "",
        actual_result: "",
        impact: "workaround",
        priority: "P3",
        observation_time: "",
        contact: "",
        screenshot_info: "",
      });
    },
  });

  const statusBadge = (s: string) => {
    const map: Record<string, string> = {
      new: "bg-kfl-status-warning-bg text-kfl-status-warning",
      triaging: "bg-kfl-status-warning-bg text-kfl-status-warning",
      accepted: "bg-kfl-status-info-bg text-kfl-status-info",
      in_progress: "bg-kfl-status-info-bg text-kfl-status-info",
      ready_to_verify: "bg-kfl-status-warning-bg text-kfl-status-warning",
      closed: "bg-kfl-status-info-bg text-kfl-status-info",
      rejected: "bg-kfl-status-danger-bg text-kfl-status-danger",
      duplicate: "bg-kfl-status-neutral-bg text-kfl-status-neutral",
      not_planned: "bg-kfl-status-neutral-bg text-kfl-status-neutral",
      needs_info: "bg-kfl-status-warning-bg text-kfl-status-warning",
    };
    return (
      <Badge variant="outline" className={`badge ${map[s] || "bg-kfl-surface-subtle text-kfl-muted"}`}>
        {s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}
      </Badge>
    );
  };

  const stats = {
    total: items.length,
    new: items.filter((f: Feedback) => f.status === "new").length,
    in_progress: items.filter((f: Feedback) => f.status === "in_progress").length,
    closed: items.filter((f: Feedback) => f.status === "closed").length,
  };

  return (
    <div className="app-page">
      <header className="app-page-header">
        <div>
          <div className="app-eyebrow">Pilot Feedback</div>
          <h1 className="app-title">Feedback</h1>
          <p className="app-subtitle">
            Report a bug, a usability issue, or an improvement proposal. Reports are reviewed by the
            pilot team and tracked to closure.
          </p>
        </div>
        <Button onClick={() => setIsCreating(true)} variant="default" size="sm">
          Submit Feedback
        </Button>
      </header>

      <div className="mb-5 grid grid-cols-1 gap-4 sm:grid-cols-4">
        <div className="app-surface p-4">
          <div className="app-label">Total</div>
          <div className="mt-2 text-2xl font-bold text-kfl-text">{stats.total}</div>
        </div>
        <div className="app-surface p-4">
          <div className="app-label">New / Triaging</div>
          <div className="mt-2 text-2xl font-bold text-kfl-text">{stats.new}</div>
        </div>
        <div className="app-surface p-4">
          <div className="app-label">In Progress</div>
          <div className="mt-2 text-2xl font-bold text-kfl-text">{stats.in_progress}</div>
        </div>
        <div className="app-surface p-4">
          <div className="app-label">Closed</div>
          <div className="mt-2 text-2xl font-bold text-kfl-text">{stats.closed}</div>
        </div>
      </div>

      <div className="app-surface overflow-hidden">
        <div className="flex flex-col gap-3 border-b border-kfl-border p-4 md:flex-row md:items-center md:justify-between">
          <div className="text-sm font-semibold text-kfl-text">Feedback</div>
          <div className="flex gap-2">
            <Select onValueChange={(e) => setStatusFilter(e)}><SelectTrigger id="feedback_status_filter" name="status" aria-label="Filter by status"><SelectValue placeholder={statusFilter || "All statuses"} /></SelectTrigger><SelectContent><SelectItem value="">All statuses</SelectItem><SelectItem value="new">New</SelectItem><SelectItem value="triaging">Triaging</SelectItem><SelectItem value="accepted">Accepted</SelectItem><SelectItem value="in_progress">In Progress</SelectItem><SelectItem value="ready_to_verify">Ready to Verify</SelectItem><SelectItem value="closed">Closed</SelectItem><SelectItem value="reopened">Reopened</SelectItem><SelectItem value="duplicate">Duplicate</SelectItem><SelectItem value="not_planned">Not Planned</SelectItem></SelectContent></Select>
            <Select onValueChange={(e) => setIssueFilter(e)}><SelectTrigger id="feedback_issue_filter" name="issue_type" aria-label="Filter by issue type"><SelectValue placeholder={issueFilter || "All types"} /></SelectTrigger><SelectContent><SelectItem value="">All types</SelectItem><SelectItem value="bug">Bug</SelectItem><SelectItem value="usability">Usability</SelectItem><SelectItem value="proposal">Proposal</SelectItem></SelectContent></Select>
          </div>
        </div>

        {isLoading ? (
          <div className="p-10 text-center text-sm text-kfl-muted">Loading feedback...</div>
        ) : items.length === 0 ? (
          <div className="app-surface border-dashed p-10 text-center">
            <p className="text-sm font-bold text-kfl-text">No feedback found.</p>
            <p className="mt-1 text-xs text-kfl-muted">Submit feedback to start tracking an issue.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full">
              <thead className="border-b border-kfl-border bg-kfl-surface-subtle">
                <tr>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Ticket</th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Type</th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Area</th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Impact</th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Status</th>
                  <th className="px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Reported</th>
                  <th className="px-4 py-3 text-right text-[11px] font-bold uppercase tracking-wider text-kfl-muted">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-kfl-border">
                {items.map((f: Feedback) => (
                  <tr key={f.feedback_id} className="transition hover:bg-kfl-surface-subtle">
                    <td className="px-4 py-4 font-mono text-[12px] text-kfl-text">{f.ticket_number}</td>
                    <td className="px-4 py-4 text-sm text-kfl-secondary">{f.issue_type.replace(/_/g, " ")}</td>
                    <td className="px-4 py-4 text-sm text-kfl-secondary max-w-xs truncate">{f.app_area}</td>
                    <td className="px-4 py-4 text-sm text-kfl-secondary">{f.impact}</td>
                    <td className="px-4 py-4">{statusBadge(f.status)}</td>
                    <td className="px-4 py-4 text-sm text-kfl-secondary">{f.created_at.slice(0, 10)}</td>
                    <td className="px-4 py-4 text-right">
                      <Button variant="outline" size="sm" onClick={() => setViewing(f)}>
                        View
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {(isCreating || viewing) && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="app-surface w-full max-w-2xl">
            {viewing && !isCreating ? (
              <>
                <div className="border-b border-kfl-border px-5 py-4">
                  <h2 className="app-modal-title">Feedback {viewing.ticket_number}</h2>
                  <p className="mt-1 text-xs text-kfl-muted">{viewing.app_area}</p>
                </div>
                <div className="space-y-4 px-5 py-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-xs font-semibold text-kfl-muted">Type</label>
                      <p className="text-sm text-kfl-secondary">{viewing.issue_type}</p>
                    </div>
                    <div>
                      <label className="block text-xs font-semibold text-kfl-muted">Impact</label>
                      <p className="text-sm text-kfl-secondary">{viewing.impact}</p>
                    </div>
                    <div>
                      <label className="block text-xs font-semibold text-kfl-muted">Status</label>
                      {statusBadge(viewing.status)}
                    </div>
                    <div>
                      <label className="block text-xs font-semibold text-kfl-muted">Priority</label>
                      <p className="text-sm text-kfl-secondary">{viewing.priority}</p>
                    </div>
                    <div>
                      <label className="block text-xs font-semibold text-kfl-muted">Owner</label>
                      <p className="text-sm text-kfl-secondary">{viewing.owner_id || "—"}</p>
                    </div>
                    <div>
                      <label className="block text-xs font-semibold text-kfl-muted">Reported</label>
                      <p className="text-sm text-kfl-secondary">{viewing.created_at}</p>
                    </div>
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-kfl-muted">Goal</label>
                    <p className="mt-1 text-sm text-kfl-secondary whitespace-pre-wrap">{viewing.goal}</p>
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-kfl-muted">Source</label>
                    <p className="text-sm text-kfl-secondary">{viewing.source_route}</p>
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-kfl-muted">Actor</label>
                    <p className="text-sm text-kfl-secondary">{viewing.actor_user_id}</p>
                  </div>
                </div>
                <div className="flex justify-end gap-2 border-t border-kfl-border pt-4">
                  <Button variant="outline" size="sm" onClick={() => setViewing(null)}>
                    Close
                  </Button>
                </div>
              </>
            ) : (
              <>
                <div className="border-b border-kfl-border px-5 py-4">
                  <h2 className="app-modal-title">New Feedback</h2>
                  <p className="mt-1 text-xs text-kfl-muted">
                    Report a bug, a usability issue, or an improvement proposal. Reports are reviewed by the
                    pilot team and tracked to closure.
                  </p>
                </div>
                <div className="space-y-3 px-5 py-4">
                  <label className="block text-sm text-kfl-secondary">
                    <span className="mb-1 block text-xs font-semibold text-kfl-muted">Issue Type</span>
                    <Select onValueChange={(e) => setForm({ ...form, issue_type: e })} value={form.issue_type}><SelectTrigger id="fb_issue_type" name="issue_type"><SelectValue placeholder={form.issue_type} /></SelectTrigger><SelectContent><SelectItem value="bug">Bug</SelectItem><SelectItem value="usability">Usability</SelectItem><SelectItem value="proposal">Proposal</SelectItem></SelectContent></Select>
                  </label>
                  <label className="block text-sm text-kfl-secondary">
                    <span className="mb-1 block text-xs font-semibold text-kfl-muted">App Area / Page</span>
                    <Input
                      id="fb_app_area"
                      name="app_area"
                      value={form.app_area}
                      onChange={(e) => setForm({ ...form, app_area: e.target.value })}
                      placeholder="e.g. Document Viewer, Change Requests"
                    />
                  </label>
                  <label className="block text-sm text-kfl-secondary">
                    <span className="mb-1 block text-xs font-semibold text-kfl-muted">Goal</span>
                    <Input
                      id="fb_goal"
                      name="goal"
                      value={form.goal}
                      onChange={(e) => setForm({ ...form, goal: e.target.value })}
                      placeholder="What are you trying to do?"
                    />
                  </label>
                  {form.issue_type === "bug" && (
                    <label className="block text-sm text-kfl-secondary">
                      <span className="mb-1 block text-xs font-semibold text-kfl-muted">Reproduction Steps</span>
                      <Textarea
                        id="fb_reproduction_steps"
                        name="reproduction_steps"
                        value={form.reproduction_steps}
                        onChange={(e) => setForm({ ...form, reproduction_steps: e.target.value })}
                      />
                    </label>
                  )}
                  <label className="block text-sm text-kfl-secondary">
                    <span className="mb-1 block text-xs font-semibold text-kfl-muted">Expected Result</span>
                    <Input
                      id="fb_expected_result"
                      name="expected_result"
                      value={form.expected_result}
                      onChange={(e) => setForm({ ...form, expected_result: e.target.value })}
                    />
                  </label>
                  <label className="block text-sm text-kfl-secondary">
                    <span className="mb-1 block text-xs font-semibold text-kfl-muted">Actual Result</span>
                    <Input
                      id="fb_actual_result"
                      name="actual_result"
                      value={form.actual_result}
                      onChange={(e) => setForm({ ...form, actual_result: e.target.value })}
                    />
                  </label>
                  <label className="block text-sm text-kfl-secondary">
                    <span className="mb-1 block text-xs font-semibold text-kfl-muted">Impact</span>
                    <Select onValueChange={(e) => setForm({ ...form, impact: e })} value={form.impact}><SelectTrigger id="fb_impact" name="impact"><SelectValue placeholder={form.impact} /></SelectTrigger><SelectContent><SelectItem value="block">Blocks my work</SelectItem><SelectItem value="workaround">Workaround exists</SelectItem><SelectItem value="suggestion">Suggestion</SelectItem></SelectContent></Select>
                  </label>
                  <label className="block text-sm text-kfl-secondary">
                    <span className="mb-1 block text-xs font-semibold text-kfl-muted">Priority</span>
                    <Select onValueChange={(e) => setForm({ ...form, priority: e })} value={form.priority}><SelectTrigger id="fb_priority" name="priority"><SelectValue placeholder={form.priority} /></SelectTrigger><SelectContent><SelectItem value="P1">P1 - Critical</SelectItem><SelectItem value="P2">P2 - High</SelectItem><SelectItem value="P3">P3 - Medium</SelectItem><SelectItem value="P4">P4 - Low</SelectItem><SelectItem value="P5">P5 - Trivial</SelectItem></SelectContent></Select>
                  </label>
                  <label className="block text-sm text-kfl-secondary">
                    <span className="mb-1 block text-xs font-semibold text-kfl-muted">Observation Time</span>
                    <Input
                      id="fb_observation_time"
                      name="observation_time"
                      type="datetime-local"
                      value={form.observation_time}
                      onChange={(e) => setForm({ ...form, observation_time: e.target.value })}
                    />
                  </label>
                  <label className="block text-sm text-kfl-secondary">
                    <span className="mb-1 block text-xs font-semibold text-kfl-muted">Contact</span>
                    <Input
                      id="fb_contact"
                      name="contact"
                      value={form.contact}
                      onChange={(e) => setForm({ ...form, contact: e.target.value })}
                      placeholder="your username or email"
                    />
                  </label>
                  <label className="block text-sm text-kfl-secondary">
                    <span className="mb-1 block text-xs font-semibold text-kfl-muted">Screenshot Info</span>
                    <Input
                      id="fb_screenshot_info"
                      name="screenshot_info"
                      value={form.screenshot_info ?? ""}
                      onChange={(e) => setForm({ ...form, screenshot_info: e.target.value })}
                      placeholder="Optional. Do not include sensitive data."
                    />
                  </label>
                </div>
                <div className="flex justify-end gap-2 border-t border-kfl-border pt-4">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      setIsCreating(false);
                      setForm({
                        issue_type: "bug",
                        app_area: "",
                        goal: "",
                        reproduction_steps: "",
                        expected_result: "",
                        actual_result: "",
                        impact: "workaround",
                        priority: "P3",
                        observation_time: "",
                        contact: "",
                        screenshot_info: "",
                      });
                    }}
                  >
                    Cancel
                  </Button>
                  <Button
                    id="fb_submit"
                    variant="default"
                    size="sm"
                    disabled={createMutation.isPending || !form.goal.trim() || !form.contact.trim()}
                    onClick={() => createMutation.mutate(form)}
                  >
                    {createMutation.isPending ? "Submitting…" : "Submit"}
                  </Button>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}