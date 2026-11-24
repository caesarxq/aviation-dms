import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useToast } from "../components/ui/Toast";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogTrigger } from "@/components/ui/dialog";
import { UserPlus, User, X } from "lucide-react";
import api from "../api/client";

const ROLE_OPTIONS = [
  { value: "flight_ops_officer", label: "Flight Operations Officer (u-flight-ops)" },
  { value: "occurrence_reporter", label: "Occurrence Reporter (u-reporter)" },
  { value: "independent_auditor", label: "Auditor (u-auditor)" },
  { value: "head_operations", label: "Head of Operations" },
  { value: "head_safety", label: "Head of Safety" },
  { value: "head_quality", label: "Head of Quality" },
  { value: "head_security", label: "Head of Security" },
  { value: "head_training", label: "Head of Training" },
  { value: "head_maintenance", label: "Head of Maintenance" },
  { value: "chief_pilot", label: "Chief Pilot" },
  { value: "dg_coordinator", label: "DG Coordinator" },
  { value: "librarian", label: "Librarian / Records Custodian" },
  { value: "accountable_manager", label: "Accountable Manager" },
];

export function BulkRoleInvite() {
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const [selectedRole, setSelectedRole] = useState("");
  const [emails, setEmails] = useState<string[]>([""]);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const inviteMutation = useMutation({
    mutationFn: async (data: { role: string; emails: string[] }) => {
      const resp = await api.post("/api/p0/auth/invites/role", data);
      return resp.data;
    },
    onSuccess: (data) => {
      toast({ title: "Invitations sent", message: `${data.created_count} user(s) invited to ${data.role}`, type: "success" });
      setEmails([""]);
      setSelectedRole("");
      setDialogOpen(false);
      queryClient.invalidateQueries({ queryKey: ["users"] });
    },
    onError: (err: any) => {
      toast({ title: "Failed to send invitations", message: err?.response?.data?.detail || "Unknown error", type: "error" });
    },
    onSettled: () => setSubmitting(false),
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const validEmails = emails.filter(e => e.trim() && e.includes("@"));
    if (validEmails.length === 0) {
      toast({ title: "No valid emails", message: "Please enter at least one valid email address", type: "error" });
      return;
    }
    if (!selectedRole) {
      toast({ title: "No role selected", message: "Please select a role", type: "error" });
      return;
    }
    setSubmitting(true);
    inviteMutation.mutate({ role: selectedRole, emails: validEmails });
  };

  const addEmail = () => {
    if (emails.length < 20) setEmails([...emails, ""]);
  };

  const removeEmail = (index: number) => {
    if (emails.length > 1) setEmails(emails.filter((_, i) => i !== index));
  };

  const updateEmail = (index: number, value: string) => {
    const newEmails = [...emails];
    newEmails[index] = value;
    setEmails(newEmails);
  };

  return (
    <div className="app-page">
      <header className="app-page-header">
        <div>
          <div className="app-eyebrow">Administration</div>
          <h1 className="app-title">Bulk Role Invitations</h1>
          <p className="app-subtitle">
            Invite multiple individuals to the same role simultaneously. Each person receives a unique account with the selected role.
          </p>
        </div>
      </header>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-2xl w-full">
          <DialogHeader>
            <DialogTitle>Invite Multiple Users to Role</DialogTitle>
            <DialogDescription>
              Enter email addresses for individuals who should receive the <strong>{ROLE_OPTIONS.find(r => r.value === selectedRole)?.label || "selected role"}</strong> role.
              Each person gets a unique account and can access the system immediately.
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={handleSubmit} className="mt-4 space-y-4">
            <div>
              <Label htmlFor="role-select">Role</Label>
              <Select value={selectedRole} onValueChange={setSelectedRole} disabled={submitting}>
                <SelectTrigger id="role-select">
                  <SelectValue placeholder="Select role..." />
                </SelectTrigger>
                <SelectContent>
                  {ROLE_OPTIONS.map((role) => (
                    <SelectItem key={role.value} value={role.value}>{role.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div>
              <Label htmlFor="emails">Email Addresses</Label>
              <div className="space-y-2 mt-1">
                {emails.map((email, index) => (
                  <div key={index} className="flex gap-2">
                    <Input
                      id={`email-${index}`}
                      type="email"
                      value={email}
                      onChange={(e) => updateEmail(index, e.target.value)}
                      placeholder="user@example.com"
                      disabled={submitting}
                      className="flex-1"
                    />
                    {emails.length > 1 && (
                      <button
                        type="button"
                        onClick={() => removeEmail(index)}
                        disabled={submitting}
                        className="p-2 text-rose-500 hover:bg-rose-500/10 rounded transition"
                        aria-label="Remove email"
                      >
                        <X size={16} />
                      </button>
                    )}
                  </div>
                ))}
                <button
                  type="button"
                  onClick={addEmail}
                  disabled={submitting || emails.length >= 20}
                  className="flex items-center gap-1 text-sm text-kfl-blue hover:underline mt-2"
                >
                  <UserPlus size={14} /> Add another email
                </button>
                <p className="text-xs text-kfl-muted">Maximum 20 emails per batch. Each person receives a unique account.</p>
              </div>
            </div>

            <div className="flex gap-2 justify-end pt-3 border-t border-kfl-border">
              <Button type="button" variant="outline" onClick={() => setDialogOpen(false)} disabled={submitting}>Cancel</Button>
              <Button type="submit" disabled={submitting || !selectedRole || emails.filter(e => e.trim()).length === 0}>
                {submitting ? "Sending…" : "Send Invitations"}
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>

      <div className="mt-4">
        <Dialog>
          <DialogTrigger asChild>
            <Button onClick={() => setDialogOpen(true)}>
              <UserPlus size={16} className="mr-2" />
              Invite Multiple Users
            </Button>
          </DialogTrigger>
        </Dialog>
      </div>

      <div className="mt-6 app-surface p-4">
        <h3 className="font-semibold text-kfl-text mb-3">Roles Supporting Multiple Individuals</h3>
        <p className="text-sm text-kfl-muted mb-4">
          The following roles can have more than one person assigned simultaneously. All invited users share the same permissions.
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {ROLE_OPTIONS.map((role) => (
            <div key={role.value} className="flex items-center gap-2 p-3 rounded border border-kfl-border bg-kfl-surface-subtle">
              <User size={16} className="text-kfl-blue" />
              <span className="text-sm text-kfl-text">{role.label}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export default BulkRoleInvite;