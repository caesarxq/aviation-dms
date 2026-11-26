import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { MessageCircle, X } from "lucide-react";
import { safetyApi } from "../api/safety";
import { FeedbackCreate } from "../types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select";

export function FloatingFeedbackButton() {
  const qc = useQueryClient();
  const [isOpen, setIsOpen] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
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
    media_file: null,
  });

  const createMutation = useMutation({
    mutationFn: async (data: FeedbackCreate) => {
      const result = await safetyApi.createFeedback(data);
      if (data.media_file) {
        await safetyApi.uploadFeedbackMedia(result.feedback_id, data.media_file);
      }
      return result;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["feedback"] });
      setIsOpen(false);
      setSelectedFile(null);
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
        media_file: null,
      });
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.goal.trim() || !form.contact.trim()) return;
    createMutation.mutate({ ...form, media_file: selectedFile });
  };

  return (
    <>
      {/* Floating action button */}
      <button
        type="button"
        onClick={() => setIsOpen(true)}
        className="fixed bottom-6 right-6 z-50 flex h-10 w-10 items-center justify-center rounded-full bg-kfl-blue text-white shadow-lg hover:bg-kfl-blue-700 transition-all hover:scale-105 active:scale-95"
        aria-label="Submit feedback"
        title="Submit feedback"
      >
        <MessageCircle size={20} className="shrink-0" />
        <span className="sr-only">Submit feedback</span>
      </button>

      {/* Modal overlay */}
      {isOpen && (
        <div
          className="fixed inset-0 z-60 flex items-center justify-center bg-black/50 backdrop-blur-sm"
          onClick={(e) => {
            if (e.target === e.currentTarget) setIsOpen(false);
          }}
        >
          <div className="relative w-full max-w-md p-4">
            {/* Modal panel */}
            <div className="relative w-full max-w-md bg-kfl-surface rounded-2xl border border-kfl-border shadow-2xl overflow-hidden">
              {/* Modal header */}
              <div className="flex items-center justify-between px-6 py-4 border-b border-kfl-border bg-kfl-surface-subtle">
                <div className="flex items-center gap-2">
                  <MessageCircle size={20} className="text-kfl-blue" />
                  <h2 className="text-sm font-semibold text-kfl-text">Submit Feedback</h2>
                </div>
                <button
                  type="button"
                  onClick={() => setIsOpen(false)}
                  className="rounded-md p-2 text-kfl-muted hover:bg-kfl-surface-subtle hover:text-kfl-text transition"
                  aria-label="Close"
                >
                  <X size={18} className="shrink-0" />
                </button>
              </div>

              {/* Modal body */}
              <div className="px-6 py-5 space-y-4">
                <form onSubmit={handleSubmit} className="space-y-4">
                  <label className="block text-xs font-semibold text-kfl-muted uppercase tracking-wider">
                    Issue Type
                  </label>
                  <Select
                    onValueChange={(e) => setForm({ ...form, issue_type: e })}
                    value={form.issue_type}
                  >
                    <SelectTrigger id="fb_issue_type" name="issue_type" className="h-9">
                      <SelectValue placeholder={form.issue_type} />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="bug">Bug</SelectItem>
                      <SelectItem value="usability">Usability</SelectItem>
                      <SelectItem value="proposal">Proposal</SelectItem>
                    </SelectContent>
                  </Select>

                  <label className="block text-xs font-semibold text-kfl-muted uppercase tracking-wider">
                    App Area / Page
                  </label>
                  <Input
                    id="fb_app_area"
                    name="app_area"
                    value={form.app_area}
                    onChange={(e) => setForm({ ...form, app_area: e.target.value })}
                    placeholder="e.g. Document Viewer, Change Requests"
                    className="h-9"
                  />

                  <label className="block text-xs font-semibold text-kfl-muted uppercase tracking-wider">
                    Goal
                  </label>
                  <Input
                    id="fb_goal"
                    name="goal"
                    value={form.goal}
                    onChange={(e) => setForm({ ...form, goal: e.target.value })}
                    placeholder="What are you trying to do?"
                    className="h-9"
                  />

                  <label className="block text-xs font-semibold text-kfl-muted uppercase tracking-wider">
                    Impact
                  </label>
                  <Select
                    onValueChange={(e) => setForm({ ...form, impact: e })}
                    value={form.impact}
                  >
                    <SelectTrigger id="fb_impact" name="impact" className="h-9">
                      <SelectValue placeholder={form.impact} />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="block">Blocks my work</SelectItem>
                      <SelectItem value="workaround">Workaround exists</SelectItem>
                      <SelectItem value="suggestion">Suggestion</SelectItem>
                    </SelectContent>
                  </Select>

                  <label className="block text-xs font-semibold text-kfl-muted uppercase tracking-wider">
                    Priority
                  </label>
                  <Select
                    onValueChange={(e) => setForm({ ...form, priority: e })}
                    value={form.priority}
                  >
                    <SelectTrigger id="fb_priority" name="priority" className="h-9">
                      <SelectValue placeholder={form.priority} />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="P1">P1 - Critical</SelectItem>
                      <SelectItem value="P2">P2 - High</SelectItem>
                      <SelectItem value="P3">P3 - Medium</SelectItem>
                      <SelectItem value="P4">P4 - Low</SelectItem>
                      <SelectItem value="P5">P5 - Trivial</SelectItem>
                    </SelectContent>
                  </Select>

                  <label className="block text-xs font-semibold text-kfl-muted uppercase tracking-wider">
                    Contact
                  </label>
                  <Input
                    id="fb_contact"
                    name="contact"
                    value={form.contact}
                    onChange={(e) => setForm({ ...form, contact: e.target.value })}
                    placeholder="your username or email"
                    className="h-9"
                  />

                  <label className="block text-xs font-semibold text-kfl-muted uppercase tracking-wider">
                    Media / Screenshot
                  </label>
                  <input
                    id="fb_media_file"
                    name="media_file"
                    type="file"
                    accept=".pdf,.png,.jpg,.jpeg,image/png,image/jpeg,application/pdf"
                    onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
                    className="mt-1 block w-full text-sm border border-kfl-border rounded p-2 h-9"
                  />
                  {selectedFile && (
                    <p className="mt-1 text-xs text-kfl-muted">
                      {selectedFile.name} ({Math.round(selectedFile.size / 1024)} KB)
                    </p>
                  )}

                  <div className="flex flex-col gap-3 pt-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setIsOpen(false)}
                      className="w-32"
                    >
                      Cancel
                    </Button>
                    <Button
                      id="fb_submit"
                      variant="default"
                      size="sm"
                      disabled={createMutation.isPending || !form.goal.trim() || !form.contact.trim()}
                      onClick={handleSubmit}
                    >
                      {createMutation.isPending ? "Submitting…" : "Submit"}
                    </Button>
                  </div>
                </form>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

export default FloatingFeedbackButton;