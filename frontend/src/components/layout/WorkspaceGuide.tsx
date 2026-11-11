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

const ROLE_GUIDES: Readonly<Record<string, { tips: string[]; note?: string }>> = {
  system_admin: {
    tips: [
      "My workspace: shortcuts for system administration screens.",
      "All modules: expand to view every screen available to your role.",
      "Role switching: not applicable — system_admin is your only role.",
    ],
    note: "Organization summaries are not operational or regulatory approvals. The NOTAM feed is not connected; consult the approved official source.",
  },
  accountable_manager: {
    tips: [
      "My workspace: shortcuts for organization overview, change requests, audit reports, missions, and ROC.",
      "All modules: expand to view every screen available to your role.",
      "Role switching: choose an assigned role in the account panel.",
    ],
    note: "Organization summaries are not operational or regulatory approvals. The NOTAM feed is not connected; consult the approved official source.",
  },
  head_operations: {
    tips: [
      "My workspace: shortcuts for missions, ROC, maintenance, crew, and duty time tracking.",
      "All modules: expand to view every screen available to your role.",
      "Role switching: choose an assigned role in the account panel.",
    ],
  },
  chief_pilot: {
    tips: [
      "My workspace: shortcuts for missions, ROC, crew, duty time tracking, and occurrences.",
      "All modules: expand to view every screen available to your role.",
      "Role switching: choose an assigned role in the account panel.",
    ],
  },
  head_safety: {
    tips: [
      "My workspace: shortcuts for safety actions, investigations, occurrences, hazards, and risk assessments.",
      "All modules: expand to view every screen available to your role.",
      "Role switching: choose an assigned role in the account panel.",
    ],
  },
  head_quality: {
    tips: [
      "My workspace: shortcuts for audit dashboard, audit findings, audit reports, quality audits, and change requests.",
      "All modules: expand to view every screen available to your role.",
      "Role switching: choose an assigned role in the account panel.",
    ],
  },
  head_maintenance: {
    tips: [
      "My workspace: shortcuts for maintenance, aircraft insurance, and ROC.",
      "All modules: expand to view every screen available to your role.",
      "Role switching: choose an assigned role in the account panel.",
    ],
  },
  librarian: {
    tips: [
      "My workspace: shortcuts for documents, document proposals, change requests, and distributions.",
      "All modules: expand to view every screen available to your role.",
      "Role switching: choose an assigned role in the account panel.",
    ],
  },
  records_custodian: {
    tips: [
      "My workspace: shortcuts for documents, distributions, and change requests.",
      "All modules: expand to view every screen available to your role.",
      "Role switching: choose an assigned role in the account panel.",
    ],
  },
  independent_auditor: {
    tips: [
      "My workspace: shortcuts for audit reports, audit findings, audit dashboard, and audit trail.",
      "All modules: expand to view every screen available to your role.",
      "Role switching: choose an assigned role in the account panel.",
    ],
  },
  occurrence_reporter: {
    tips: [
      "My workspace: shortcuts for safety occurrences.",
      "All modules: expand to view every screen available to your role.",
      "Role switching: choose an assigned role in the account panel.",
    ],
  },
  head_training: {
    tips: [
      "My workspace: shortcuts for training, crew qualifications, crew, and personnel licenses.",
      "All modules: expand to view every screen available to your role.",
      "Role switching: choose an assigned role in the account panel.",
    ],
  },
  dg_coordinator: {
    tips: [
      "My workspace: shortcuts for dangerous goods, DG responsibility matrix, and missions.",
      "All modules: expand to view every screen available to your role.",
      "Role switching: choose an assigned role in the account panel.",
    ],
  },
  head_security: {
    tips: [
      "My workspace: shortcuts for security reviews, security, and occurrences.",
      "All modules: expand to view every screen available to your role.",
      "Role switching: choose an assigned role in the account panel.",
    ],
  },
  flight_ops_officer: {
    tips: [
      "My workspace: shortcuts for missions, ROC, and occurrences.",
      "All modules: expand to view every screen available to your role.",
      "Role switching: choose an assigned role in the account panel.",
    ],
  },
  as_contracted: {
    tips: [
      "My workspace: shortcuts for documents.",
      "All modules: expand to view every screen available to your role.",
      "Role switching: choose an assigned role in the account panel.",
    ],
  },
};

function guideFor(role: string) {
  return ROLE_GUIDES[role] ?? {
    tips: [
      "My workspace: shortcuts for your active role.",
      "All modules: expand to view every screen available to your role.",
      "Role switching: choose an assigned role in the account panel.",
    ],
  };
}

export function WorkspaceGuide({ userId, activeRole }: WorkspaceGuideProps) {
  const [open, setOpen] = useState(() => !dismissedForUser(userId));
  const guide = guideFor(activeRole);

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
        {guide.tips.map((tip, i) => (
          <li key={i}>{tip}</li>
        ))}
      </ul>
      {guide.note && (
        <p className="mt-3 text-xs text-kfl-muted">{guide.note}</p>
      )}
      <div className="mt-4 flex justify-end">
        <button type="button" onClick={dismiss} className="app-btn-secondary px-3 py-1.5 text-xs">
          Got it
        </button>
      </div>
    </section>
  );
}
