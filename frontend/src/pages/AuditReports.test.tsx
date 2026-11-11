import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AuthContext } from "../auth/AuthContext";
import { auditApi } from "../api/audit";
import { AuditReports } from "./AuditReports";

const auditApiMocks = vi.hoisted(() => ({
  listAuditReports: vi.fn(),
  createAuditReport: vi.fn(),
  listAuditFindings: vi.fn(),
  createAuditFinding: vi.fn(),
  listAuditReportImports: vi.fn(),
  getAuditReportImport: vi.fn(),
  createAuditReportImport: vi.fn(),
  verifyAuditReportImport: vi.fn(),
  rejectAuditReportImport: vi.fn(),
}));
vi.mock("../api/audit", () => ({ auditApi: auditApiMocks }));

const audit = { audit_id: "audit-1", audit_number: "A-001", audit_date: "2026-10-01", auditor_id: "u1", auditee_id: "u2", scope: "Safety", regulatory_basis: null, status: "open", evidence_file: null, created_at: null, updated_at: null };
function CurrentLocation() { const location = useLocation(); return <output data-testid="location">{location.pathname}{location.search}</output>; }
function renderPage(permissions = ["audit_report:read", "audit_report:create", "audit_finding:read"], role = "head_quality") {
  const profile = { user: { user_id: "u1", username: "user", email: "u@example.test", full_name: "User", role, active_role: role, roles: [role] }, role, active_role: role, roles: [role], authenticated_via: "session_cookie", onboarding_completed: true, permissions };
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><AuthContext.Provider value={{ profile, state: "authenticated", login: async () => profile, switchRole: async () => profile, logout: async () => {}, refreshProfile: async () => profile, hasPermission: (permission) => permissions.includes(permission) }}><MemoryRouter initialEntries={["/audit-reports"]}><CurrentLocation /><Routes><Route path="/audit-reports" element={<AuditReports />} /><Route path="/audit-findings" element={<div>Findings page</div>} /></Routes></MemoryRouter></AuthContext.Provider></QueryClientProvider>);
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(auditApi.listAuditReports).mockResolvedValue([audit] as never);
  auditApiMocks.listAuditReportImports.mockResolvedValue([]);
});

describe("AuditReports", () => {
  it("opens findings for the selected audit using the audit filter route", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("A-001");
    await user.click(screen.getByRole("button", { name: "View Findings for A-001" }));
    expect(screen.getByTestId("location")).toHaveTextContent("/audit-findings?audit_id=audit-1");
  });

  it("hides the findings link when the report reader lacks finding-read permission", async () => {
    renderPage(["audit_report:read"]);
    await screen.findByText("A-001");
    expect(screen.queryByRole("button", { name: "View Findings for A-001" })).not.toBeInTheDocument();
  });

  it("paginates audit reports so records beyond the first 50 are reachable", async () => {
    const user = userEvent.setup();
    const allReports = Array.from({ length: 101 }, (_, index) => ({
      ...audit,
      audit_id: `audit-${index + 1}`,
      audit_number: `A-${String(index + 1).padStart(3, "0")}`,
    }));
    auditApiMocks.listAuditReports.mockImplementation((params?: { limit?: number; offset?: number }) => {
      const offset = params?.offset ?? 0;
      const limit = params?.limit ?? 51;
      return Promise.resolve(allReports.slice(offset, offset + limit));
    });
    renderPage();

    await screen.findByText("A-001");
    expect(auditApiMocks.listAuditReports).toHaveBeenNthCalledWith(
      1,
      expect.objectContaining({ limit: 51, offset: 0 }),
    );
    expect(screen.getByText("A-050")).toBeInTheDocument();
    expect(screen.queryByText("A-051")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Next audit reports" }));
    expect(await screen.findByText("A-051")).toBeInTheDocument();
    expect(screen.queryByText("A-001")).not.toBeInTheDocument();
    expect(auditApiMocks.listAuditReports).toHaveBeenLastCalledWith(
      expect.objectContaining({ limit: 51, offset: 50 }),
    );
  });

  it("offers the authenticated evidence download for reports with an evidence file", async () => {
    vi.mocked(auditApi.listAuditReports).mockResolvedValueOnce([
      { ...audit, evidence_file: "attachments/report.pdf" },
    ] as never);
    renderPage(["audit_report:read"]);

    const link = await screen.findByRole("link", { name: "Download Evidence for A-001" });

    expect(link).toHaveAttribute("href", "/api/p3/audit-reports/audit-1/evidence");
  });

  it("shows read failures separately from the empty state and hides creation without permission", async () => {
    vi.mocked(auditApi.listAuditReports).mockRejectedValueOnce(new Error("network"));
    renderPage(["audit_report:read"]);
    expect(await screen.findByRole("alert")).toHaveTextContent("Unable to load audit reports");
    expect(screen.queryByText("No audit reports recorded.")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "New Audit" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Retry loading audit reports" }));
  });

  it("requires explicit auditor and auditee identifiers before creating a report", async () => {
    const user = userEvent.setup();
    vi.mocked(auditApi.createAuditReport).mockResolvedValue({ audit_id: "audit-2" } as never);
    renderPage();
    await user.click(screen.getByRole("button", { name: "New Audit" }));
    await user.type(screen.getByLabelText(/Audit Number/), "A-002");
    await user.type(screen.getByLabelText(/Audit Date/), new Date().toISOString().slice(0, 10));
    const create = screen.getByRole("button", { name: "Create Audit" });
    expect(create).toBeDisabled();
    await user.type(screen.getByLabelText(/Auditor User ID/), "u-auditor");
    await user.type(screen.getByLabelText(/Auditee User ID/), "u-admin");
    expect(create).toBeEnabled();
    await user.click(create);
    await waitFor(() => expect(auditApi.createAuditReport).toHaveBeenCalledWith(expect.objectContaining({
      auditor_id: "u-auditor", auditee_id: "u-admin",
    })));
  });

  it("routes backdated in-app audits through historical provenance import", async () => {
    const user = userEvent.setup();
    renderPage();
    await user.click(screen.getByRole("button", { name: "New Audit" }));
    const today = new Date().toISOString().slice(0, 10);
    const dateField = screen.getByLabelText(/Audit Date/);
    expect(dateField).toHaveAttribute("min", today);
    expect(screen.getByText(/historical source audits must use the provenance import workflow/i)).toBeVisible();

    await user.type(screen.getByLabelText(/Audit Number/), "A-BACKDATED");
    await user.type(screen.getByLabelText(/Auditor User ID/), "u-auditor");
    await user.type(screen.getByLabelText(/Auditee User ID/), "u-admin");
    const yesterday = new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString().slice(0, 10);
    fireEvent.change(dateField, { target: { value: yesterday } });
    expect(screen.getByRole("button", { name: "Create Audit" })).toBeDisabled();
  });

  it("shows a mutation error without closing or clearing the form", async () => {
    const user = userEvent.setup();
    vi.mocked(auditApi.createAuditReport).mockRejectedValueOnce(new Error("network"));
    renderPage();
    await user.click(screen.getByRole("button", { name: "New Audit" }));
    await user.type(screen.getByLabelText(/Audit Number/), "A-002");
    await user.type(screen.getByLabelText(/Audit Date/), new Date().toISOString().slice(0, 10));
    await user.type(screen.getByLabelText(/Auditor User ID/), "u-auditor");
    await user.type(screen.getByLabelText(/Auditee User ID/), "u-admin");
    await user.click(screen.getByRole("button", { name: "Create Audit" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Unable to create audit report");
    expect(screen.getByLabelText(/Audit Number/)).toHaveValue("A-002");
  });

  it("lets the system administrator stage a candidate while preserving exact source attribution", async () => {
    const user = userEvent.setup();
    auditApiMocks.createAuditReportImport.mockResolvedValue({ import_id: "AIMP-1", audit_number: "AUD-001", status: "pending_verification" });
    renderPage(["audit_report:read", "audit_report:import"], "system_admin");

    await screen.findByText("Historical Audit Provenance");
    await user.click(screen.getByRole("button", { name: "Stage Historical Import" }));
    await user.type(screen.getByLabelText(/Import Audit Number/), "AUD-001");
    await user.type(screen.getByLabelText(/Import Audit Date/), "2026-09-28");
    await user.type(screen.getByLabelText(/Source Auditor ID/), "u-safety/security");
    await user.type(screen.getByLabelText(/Source Auditor Name/), "Brian Swanya");
    await user.type(screen.getByLabelText(/Import Auditee ID/), "u-accountable");
    await user.type(screen.getByLabelText(/Existing Source PDF Path/), "attachments/source.pdf");
    await user.type(screen.getByLabelText(/Expected Source SHA-256/), "a".repeat(64));
    await user.type(screen.getByLabelText("Import Scope"), "Safety and Security");
    await user.type(screen.getByLabelText("Import Regulatory Basis"), "Controlled source report");
    fireEvent.change(screen.getByLabelText(/Findings JSON/), {
      target: { value: JSON.stringify([{
        finding_number: "1",
        area: "Safety",
        level: 2,
        title: "Finding one",
        description: "Source text",
        regulatory_reference: "KCAA source report",
      }]) },
    });

    await user.click(screen.getByRole("button", { name: "Stage Candidate" }));

    await waitFor(() => expect(auditApiMocks.createAuditReportImport).toHaveBeenCalledWith({
      audit_number: "AUD-001",
      audit_date: "2026-09-28",
      source_auditor_id: "u-safety/security",
      source_auditor_name: "Brian Swanya",
      auditee_id: "u-accountable",
      scope: "Safety and Security",
      regulatory_basis: "Controlled source report",
      evidence_file: "attachments/source.pdf",
      expected_evidence_sha256: "a".repeat(64),
      findings: [{
        finding_number: "1",
        area: "Safety",
        level: 2,
        title: "Finding one",
        description: "Source text",
        regulatory_reference: "KCAA source report",
      }],
    }));
    expect(await screen.findByText(/Candidate AUD-001 staged for independent review/)).toBeInTheDocument();
  });

  it("lets only an independent auditor review and verify a pending import", async () => {
    const user = userEvent.setup();
    const candidate = {
      import_id: "AIMP-3",
      audit_number: "AUD-003",
      audit_date: "2026-09-28",
      source_auditor_id: "u-safety/security",
      source_auditor_name: "Brian Swanya",
      auditee_id: "u-accountable",
      scope: "Safety and Security",
      regulatory_basis: "Controlled source report",
      evidence_sha256: "b".repeat(64),
      payload_sha256: "c".repeat(64),
      evidence_download_url: "/api/p3/audit-report-imports/AIMP-3/evidence",
      imported_by: "u-admin",
      created_at: "2026-11-08T10:00:00Z",
      status: "pending_verification",
      verified_by: null,
      verified_at: null,
      verification_notes: null,
      audit_id: null,
    };
    auditApiMocks.listAuditReportImports.mockResolvedValue([candidate]);
    auditApiMocks.getAuditReportImport.mockResolvedValue({
      ...candidate,
      findings: [{
        finding_number: "1",
        area: "Safety",
        level: 2,
        title: "Source finding",
        description: "Finding detail from the candidate.",
        regulatory_reference: "KCAA source report",
        due_date: null,
      }],
    });
    auditApiMocks.verifyAuditReportImport.mockResolvedValue({ audit_number: "AUD-003" });
    renderPage(["audit_report:read", "audit_report:provenance_verify"], "independent_auditor");

    await user.click(await screen.findByRole("button", { name: "View import AUD-003" }));
    expect(await screen.findByRole("heading", { name: "Review AUD-003" })).toBeVisible();
    expect(screen.getByText("Brian Swanya (u-safety/security)")).toBeInTheDocument();
    expect(screen.getByText("Audit date", { selector: "dt" })).toBeInTheDocument();
    expect(screen.getByText("Scope", { selector: "dt" })).toBeInTheDocument();
    expect(screen.getByText("Regulatory basis", { selector: "dt" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Download source PDF for AUD-003" })).toHaveAttribute(
      "href", "/api/p3/audit-report-imports/AIMP-3/evidence",
    );
    expect(screen.getByText("Finding detail from the candidate.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Stage Historical Import" })).not.toBeInTheDocument();

    const verify = screen.getByRole("button", { name: "Verify and Import" });
    expect(verify).toBeDisabled();
    await user.click(screen.getByLabelText(/I confirmed the source PDF checksum/));
    await user.click(screen.getByLabelText(/I reconciled every finding/));
    await user.type(screen.getByLabelText(/Verification Notes/), "Compared the controlled source and reconciled each finding.");
    expect(verify).toBeEnabled();
    await user.click(verify);

    await waitFor(() => expect(auditApiMocks.verifyAuditReportImport).toHaveBeenCalledWith("AIMP-3", {
      source_checksum_confirmed: true,
      findings_reconciled: true,
      verification_notes: "Compared the controlled source and reconciled each finding.",
    }));
    expect(await screen.findByText(/Candidate AUD-003 was verified/)).toBeInTheDocument();
  });

  it("does not expose the import queue to users with report-read permission only", async () => {
    renderPage(["audit_report:read"], "head_quality");

    await screen.findByText("A-001");

    expect(screen.queryByText("Historical Audit Provenance")).not.toBeInTheDocument();
    expect(auditApiMocks.listAuditReportImports).not.toHaveBeenCalled();
  });

  it("keeps verification controls hidden from the system administrator import operator", async () => {
    const user = userEvent.setup();
    const candidate = {
      import_id: "AIMP-4",
      audit_number: "AUD-004",
      audit_date: "2026-09-28",
      source_auditor_id: "u-safety/security",
      source_auditor_name: "Brian Swanya",
      auditee_id: "u-accountable",
      scope: null,
      regulatory_basis: null,
      evidence_sha256: "d".repeat(64),
      payload_sha256: "e".repeat(64),
      evidence_download_url: "/api/p3/audit-report-imports/AIMP-4/evidence",
      imported_by: "u-admin",
      created_at: "2026-11-08T10:00:00Z",
      status: "pending_verification",
      verified_by: null,
      verified_at: null,
      verification_notes: null,
      audit_id: null,
      findings: [],
    };
    auditApiMocks.listAuditReportImports.mockResolvedValue([candidate]);
    auditApiMocks.getAuditReportImport.mockResolvedValue(candidate);
    renderPage(["audit_report:read", "audit_report:import"], "system_admin");

    await user.click(await screen.findByRole("button", { name: "View import AUD-004" }));
    expect(await screen.findByRole("heading", { name: "Review AUD-004" })).toBeVisible();
    expect(screen.getByRole("button", { name: "Stage Historical Import" })).toBeVisible();
    expect(screen.queryByRole("button", { name: "Verify and Import" })).not.toBeInTheDocument();
    expect(screen.getByText(/Only a distinct independent_auditor can verify or reject/)).toBeInTheDocument();
  });

  it("lets an independent auditor reject a pending import with a recorded reason", async () => {
    const user = userEvent.setup();
    const candidate = {
      import_id: "AIMP-5",
      audit_number: "AUD-005",
      audit_date: "2026-09-28",
      source_auditor_id: "u-safety/security",
      source_auditor_name: "Brian Swanya",
      auditee_id: "u-accountable",
      scope: null,
      regulatory_basis: null,
      evidence_sha256: "f".repeat(64),
      payload_sha256: "0".repeat(64),
      evidence_download_url: "/api/p3/audit-report-imports/AIMP-5/evidence",
      imported_by: "u-admin",
      created_at: "2026-11-08T10:00:00Z",
      status: "pending_verification",
      verified_by: null,
      verified_at: null,
      verification_notes: null,
      audit_id: null,
      findings: [],
    };
    auditApiMocks.listAuditReportImports.mockResolvedValue([candidate]);
    auditApiMocks.getAuditReportImport.mockResolvedValue(candidate);
    auditApiMocks.rejectAuditReportImport.mockResolvedValue({ import_id: "AIMP-5" });
    renderPage(["audit_report:read", "audit_report:provenance_verify"], "independent_auditor");

    await user.click(await screen.findByRole("button", { name: "View import AUD-005" }));
    const reject = screen.getByRole("button", { name: "Reject Import" });
    expect(reject).toBeDisabled();
    await user.type(screen.getByLabelText(/Rejection Reason/), "The source payload did not reconcile.");
    expect(reject).toBeEnabled();
    await user.click(reject);

    await waitFor(() => expect(auditApiMocks.rejectAuditReportImport).toHaveBeenCalledWith(
      "AIMP-5", "The source payload did not reconcile.",
    ));
    expect(await screen.findByText(/Candidate AIMP-5 was rejected/)).toBeInTheDocument();
  });

  it("paginates the import queue so pending candidates beyond the first page are reachable", async () => {
    const user = userEvent.setup();
    const candidates = Array.from({ length: 51 }, (_, index) => ({
      import_id: `AIMP-${index}`,
      audit_number: `AUD-${String(index).padStart(2, "0")}`,
      audit_date: "2026-09-28",
      source_auditor_id: "u-safety/security",
      source_auditor_name: "Brian Swanya",
      auditee_id: "u-accountable",
      scope: null,
      regulatory_basis: null,
      evidence_sha256: "a".repeat(64),
      payload_sha256: "b".repeat(64),
      evidence_download_url: `/api/p3/audit-report-imports/AIMP-${index}/evidence`,
      imported_by: "u-admin",
      created_at: "2026-11-08T10:00:00Z",
      status: "pending_verification",
      verified_by: null,
      verified_at: null,
      verification_notes: null,
      audit_id: null,
    }));
    auditApiMocks.listAuditReportImports
      .mockResolvedValueOnce(candidates)
      .mockResolvedValueOnce(candidates.slice(50));
    renderPage(["audit_report:read", "audit_report:provenance_verify"], "independent_auditor");

    expect(await screen.findByText("AUD-49")).toBeInTheDocument();
    expect(screen.queryByText("AUD-50")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Load more candidates" }));
    expect(await screen.findByText("AUD-50")).toBeInTheDocument();
    await waitFor(() => expect(auditApiMocks.listAuditReportImports).toHaveBeenNthCalledWith(2, {
      limit: 51,
      offset: 50,
    }));
  });
});
