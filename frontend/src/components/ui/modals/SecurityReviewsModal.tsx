import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "../../../api/client";
import { Modal } from "../Modal";
import { useToast } from "../Toast";

export function SecurityReviewsModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const qc = useQueryClient();
  const { toast } = useToast();
  const [date, setDate] = useState("");
  const [error, setError] = useState("");

  const { data: items = [] } = useQuery({
    queryKey: ["security-reviews-modal"],
    queryFn: () => api.get("/p1/security-reviews").then((r: any) => r.data),
  });

  const createMutation = useMutation({
    mutationFn: (data: any) => api.post("/p1/security-reviews", data).then((r: any) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["security-reviews-modal"] });
      setDate("");
      setError("");
      toast({ title: "Security Review scheduled", type: "success" });
    },
    onError: () => setError("Failed to schedule security review."),
  });

  return (
    <Modal open={open} onClose={onClose} title="Security Reviews" className="max-w-2xl">
      {error && (
        <div className="mb-3 p-3 rounded bg-rose-50/60 border border-rose-200 text-rose-800 text-sm">{error}</div>
      )}
      <div className="flex justify-between items-center mb-3">
        <h3 className="font-medium text-white">Security Review Meetings</h3>
        <button onClick={() => onClose()} className="text-xs text-white/70 hover:text-white underline">
          Close
        </button>
      </div>

      <div className="mb-4">
        <label className="block text-xs font-medium text-white/70 mb-1">Meeting Date</label>
        <input
          type="date"
          className="w-full border border-white/20 rounded p-2 text-sm bg-white/10 text-white focus:border-kfl-blue focus:outline-none"
          value={date}
          onChange={(e) => setDate(e.target.value)}
        />
      </div>
      <button
        disabled={!date || createMutation.isPending}
        onClick={() => {
          setError("");
          if (!date) {
            setError("Meeting date is required.");
            return;
          }
          createMutation.mutate({ meeting_date: date });
        }}
        className="w-full bg-kfl-blue hover:bg-kfl-blue/90 text-white px-4 py-2 rounded disabled:opacity-50 transition"
      >
        {createMutation.isPending ? "Scheduling…" : "Schedule Review"}
      </button>

      {items.length > 0 && (
        <div className="mt-4 overflow-auto max-h-48">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="border-b border-white/10 text-white/60 text-[10px] uppercase">
                <th className="text-left px-2 py-1">Meeting Date</th>
                <th className="text-left px-2 py-1">Status</th>
                <th className="text-left px-2 py-1">Attendees</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/10">
              {items.map((i: any) => (
                <tr key={i.review_id}>
                  <td className="px-2 py-1 text-xs text-white">{i.meeting_date}</td>
                  <td className="px-2 py-1 text-xs text-white/70">{i.status}</td>
                  <td className="px-2 py-1 text-xs text-white">{i.attendees || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Modal>
  );
}
