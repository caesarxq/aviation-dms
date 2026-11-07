import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AuthContext } from "../auth/AuthContext";
import { auditApi } from "../api/audit";
import { AuditReports } from "./AuditReports";

vi.mock("../api/audit", () => ({ auditApi: { listAuditReports: vi.fn(), createAuditReport: vi.fn(), listAuditFindings: vi.fn(), createAuditFinding: vi.fn() } }));

const audit = { audit_id: "audit-1", audit_number: "A-001", audit_date: "2026-10-01", auditor_id: "u1", auditee_id: "u2", scope: "Safety", regulatory_basis: null, status: "open", evidence_file: null, created_at: null, updated_at: null };
function CurrentLocation() { const location = useLocation(); return <output data-testid="location">{location.pathname}{location.search}</output>; }
function renderPage(permissions = ["audit_report:read", "audit_report:create", "audit_finding:read"]) {
  const profile = { user: { user_id: "u1", username: "user", email: "u@example.test", full_name: "User", role: "head_quality", active_role: "head_quality", roles: ["head_quality"] }, role: "head_quality", active_role: "head_quality", roles: ["head_quality"], authenticated_via: "session_cookie", onboarding_completed: true, permissions };
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><AuthContext.Provider value={{ profile, state: "authenticated", login: async () => profile, switchRole: async () => profile, logout: async () => {}, refreshProfile: async () => profile, hasPermission: (permission) => permissions.includes(permission) }}><MemoryRouter initialEntries={["/audit-reports"]}><CurrentLocation /><Routes><Route path="/audit-reports" element={<AuditReports />} /><Route path="/audit-findings" element={<div>Findings page</div>} /></Routes></MemoryRouter></AuthContext.Provider></QueryClientProvider>);
}

beforeEach(() => { vi.clearAllMocks(); vi.mocked(auditApi.listAuditReports).mockResolvedValue([audit] as never); });

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
    await user.type(screen.getByLabelText(/Audit Date/), "2026-10-02");
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

  it("shows a mutation error without closing or clearing the form", async () => {
    const user = userEvent.setup();
    vi.mocked(auditApi.createAuditReport).mockRejectedValueOnce(new Error("network"));
    renderPage();
    await user.click(screen.getByRole("button", { name: "New Audit" }));
    await user.type(screen.getByLabelText(/Audit Number/), "A-002");
    await user.type(screen.getByLabelText(/Audit Date/), "2026-10-02");
    await user.type(screen.getByLabelText(/Auditor User ID/), "u-auditor");
    await user.type(screen.getByLabelText(/Auditee User ID/), "u-admin");
    await user.click(screen.getByRole("button", { name: "Create Audit" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Unable to create audit report");
    expect(screen.getByLabelText(/Audit Number/)).toHaveValue("A-002");
  });
});
