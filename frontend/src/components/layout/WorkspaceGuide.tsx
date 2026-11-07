import { useState } from "react";
import { X } from "lucide-react";

type WorkspaceGuideProps = {
  userId: string;
  activeRole: string;
};

const GUIDE_STORAGE_PREFIX = "kfl:workspace-guide:v1:";

function dismissedForUser(userId: string): boolean {
  try {
    return window.localStorage.getItem(`${GUIDE_STORAGE_PREFIX}${encodeURIComponent(userId)}`) === "dismissed";
  } catch {
    return false;
  }
}

export function WorkspaceGuide({ userId, activeRole }: WorkspaceGuideProps) {
  const [open, setOpen] = useState(() => !dismissedForUser(userId));

  function dismiss() {
    try {
      window.localStorage.setItem(`${GUIDE_STORAGE_PREFIX}${encodeURIComponent(userId)}`, "dismissed");
    } catch {
      // Keep the guide dismissible when browser storage is unavailable.
    }
    setOpen(false);
  }

  if (!open) return null;

  return (
    <section aria-label="One-time workspace tips" className="app-surface m-4 border border-sky-200 bg-sky-50/70 p-4 sm:p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="app-eyebrow">Getting started</div>
          <h2 className="mt-1 text-base font-bold text-kfl-text">Quick workspace guide</h2>
        </div>
        <button
          type="button"
          onClick={dismiss}
          aria-label="Close workspace guide tips"
          className="rounded p-2 text-kfl-muted hover:bg-sky-100 hover:text-kfl-text focus-visible:outline focus-visible:outline-2 focus-visible:outline-kfl-blue"
        >
          <X size={16} aria-hidden="true" />
        </button>
      </div>
      <ul className="mt-3 grid gap-2 text-sm text-kfl-text md:grid-cols-3">
        <li><strong>My workspace:</strong> shortcuts for your active role ({activeRole.replace(/_/g, " ")}); they do not add permissions.</li>
        <li><strong>All modules:</strong> expands other screens already allowed to your role.</li>
        <li><strong>Role switching:</strong> choose an assigned role in the account panel. The workspace changes, and permissions remain scoped to that active role.</li>
      </ul>
      {activeRole === "accountable_manager" && (
        <p className="mt-3 text-xs text-kfl-muted">
          Organization summaries are not operational or regulatory approvals. The NOTAM feed is not connected; consult the approved official source.
        </p>
      )}
      <div className="mt-4 flex justify-end">
        <button type="button" onClick={dismiss} className="app-btn-secondary px-3 py-1.5 text-xs">
          Got it
        </button>
      </div>
    </section>
  );
}
