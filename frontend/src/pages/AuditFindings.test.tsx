import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AuthContext } from "../auth/AuthContext";
import { auditApi } from "../api/audit";
import { AuditFindings } from "./AuditFindings";

vi.mock("../api/audit", () => ({ auditApi: { listAuditReports: vi.fn(), createAuditReport: vi.fn(), listAuditFindings: vi.fn(), getAuditFinding: vi.fn(), createAuditFinding: vi.fn() } }));

const audit = { audit_id: "audit-1", audit_number: "A-001", audit_date: "2026-10-01", auditor_id: "u1", auditee_id: "u2", scope: "Safety", regulatory_basis: null, status: "open", evidence_file: null, created_at: null, updated_at: null };
const finding = { finding_id: "finding-1", audit_id: "audit-1", finding_number: "1", area: "Safety", level: 2, title: "Training record missing", description: "Evidence was not available.", regulatory_reference: null, status: "open", corrective_action_id: null, due_date: null, closed_at: null, closed_by: null, created_at: null, updated_at: null };
function CurrentLocation() { const location = useLocation(); return <output data-testid="location">{location.pathname}{location.search}</output>; }
function renderPage(permissions = ["audit_finding:read", "audit_finding:create"], initialPath = "/audit-findings") {
  const profile = { user: { user_id: "u1", username: "user", email: "u@example.test", full_name: "User", role: "head_quality", active_role: "head_quality", roles: ["head_quality"] }, role: "head_quality", active_role: "head_quality", roles: ["head_quality"], authenticated_via: "session_cookie", onboarding_completed: true, permissions };
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><AuthContext.Provider value={{ profile, state: "authenticated", login: async () => profile, switchRole: async () => profile, logout: async () => {}, refreshProfile: async () => profile, hasPermission: (permission) => permissions.includes(permission) }}><MemoryRouter initialEntries={[initialPath]}><CurrentLocation /><Routes><Route path="/audit-findings" element={<AuditFindings />} /><Route path="/audit-findings/:findingId" element={<AuditFindings />} /></Routes></MemoryRouter></AuthContext.Provider></QueryClientProvider>);
}

beforeEach(() => { vi.clearAllMocks(); vi.mocked(auditApi.listAuditReports).mockResolvedValue([audit] as never); vi.mocked(auditApi.listAuditFindings).mockResolvedValue([finding] as never); vi.mocked(auditApi.getAuditFinding).mockResolvedValue(finding as never); });

describe("AuditFindings", () => {
  it("requires an existing audit selection and sends its id when creating a finding", async () => {
    const user = userEvent.setup();
    vi.mocked(auditApi.createAuditFinding).mockResolvedValue(finding as never);
    renderPage();
    await screen.findByText("Training record missing");
    await user.click(screen.getByRole("button", { name: "New Finding" }));
    const submit = screen.getByRole("button", { name: "Create Finding" });
    expect(submit).toBeDisabled();
    await user.selectOptions(screen.getByRole("combobox", { name: "Audit engagement" }), "audit-1");
    await user.type(screen.getByLabelText(/Finding Number/), "2");
    await user.type(screen.getByLabelText(/Area/), "Safety");
    await user.selectOptions(screen.getByLabelText(/Level/), "2");
    await user.type(screen.getByLabelText(/Title/), "Inspection records incomplete");
    await user.type(screen.getByLabelText(/Description/), "Inspection evidence was not retained.");
    await user.click(submit);
    await waitFor(() => expect(auditApi.createAuditFinding).toHaveBeenCalledWith(expect.objectContaining({ audit_id: "audit-1" })));
  });

  it("uses the audit query parameter to filter findings and navigates to a real finding detail route", async () => {
    const user = userEvent.setup();
    renderPage(["audit_finding:read"], "/audit-findings?audit_id=audit-1");
    await screen.findByText("Training record missing");
    await user.click(screen.getByRole("button", { name: "View details for finding 1" }));
    expect(screen.getByTestId("location")).toHaveTextContent("/audit-findings/finding-1");
    expect(await screen.findByRole("heading", { level: 2 })).toHaveTextContent("Training record missing");
    expect(auditApi.getAuditFinding).toHaveBeenCalledWith("finding-1");
  });

  it("fetches a detail URL directly by finding ID, even when it is outside the list page", async () => {
    vi.mocked(auditApi.listAuditFindings).mockResolvedValue([] as never);
    vi.mocked(auditApi.getAuditFinding).mockResolvedValue({ ...finding, finding_id: "finding-51", title: "Finding on later page" } as never);
    renderPage(["audit_finding:read"], "/audit-findings/finding-51");
    expect(await screen.findByRole("heading", { level: 2 })).toHaveTextContent("Finding on later page");
    expect(auditApi.getAuditFinding).toHaveBeenCalledWith("finding-51");
  });

  it("paginates through findings beyond the first 50 results", async () => {
    const user = userEvent.setup();
    const firstPage = Array.from({ length: 50 }, (_, index) => ({ ...finding, finding_id: `finding-${index + 1}`, finding_number: `${index + 1}`, title: `Finding ${index + 1}` }));
    const nextPageFinding = { ...finding, finding_id: "finding-51", finding_number: "51", title: "Finding 51" };
    vi.mocked(auditApi.listAuditFindings).mockResolvedValueOnce(firstPage as never).mockResolvedValueOnce([nextPageFinding] as never);
    renderPage();
    await screen.findByText("Finding 1");
    expect(auditApi.listAuditFindings).toHaveBeenCalledWith({ limit: 50, offset: 0 });
    await user.click(screen.getByRole("button", { name: "Next page" }));
    expect(await screen.findByText("Finding 51")).toBeInTheDocument();
    expect(auditApi.listAuditFindings).toHaveBeenLastCalledWith({ limit: 50, offset: 50 });
  });

  it("sends server-side search and supported status filters after resetting pagination", async () => {
    const user = userEvent.setup();
    const firstPage = Array.from({ length: 50 }, (_, index) => ({ ...finding, finding_id: `finding-${index + 1}`, finding_number: `${index + 1}`, title: `Finding ${index + 1}` }));
    const laterFinding = { ...finding, finding_id: "finding-51", finding_number: "51", title: "Needle target" };
    vi.mocked(auditApi.listAuditFindings).mockImplementation((params) => {
      if (params?.search) return Promise.resolve([laterFinding] as never);
      return Promise.resolve(params?.offset === 0 ? firstPage : [laterFinding]) as never;
    });
    renderPage();
    await screen.findByText("Finding 1");
    await user.click(screen.getByRole("button", { name: "Next page" }));
    expect(await screen.findByText("Needle target")).toBeInTheDocument();
    await user.type(screen.getByRole("searchbox", { name: "Search audit findings" }), "needle");
    await waitFor(() => expect(auditApi.listAuditFindings).toHaveBeenLastCalledWith({ limit: 50, offset: 0, search: "needle" }));

    const statusFilter = screen.getByRole("combobox", { name: "Filter audit findings by status" });
    expect(screen.getByRole("option", { name: "Open" })).toHaveValue("open");
    expect(screen.getByRole("option", { name: "In progress" })).toHaveValue("in_progress");
    expect(screen.getByRole("option", { name: "Closed" })).toHaveValue("closed");
    await user.selectOptions(statusFilter, "open");
    await waitFor(() => expect(auditApi.listAuditFindings).toHaveBeenLastCalledWith({ limit: 50, offset: 0, search: "needle", status: "open" }));

    await user.selectOptions(screen.getByRole("combobox", { name: "Filter findings by audit" }), "audit-1");
    await waitFor(() => expect(auditApi.listAuditFindings).toHaveBeenLastCalledWith({ audit_id: "audit-1", limit: 50, offset: 0, search: "needle", status: "open" }));
  });

  it("allows returning from the empty page after an exact multiple of 50 findings", async () => {
    const user = userEvent.setup();
    const firstPage = Array.from({ length: 50 }, (_, index) => ({ ...finding, finding_id: `finding-${index + 1}`, finding_number: `${index + 1}`, title: `Finding ${index + 1}` }));
    vi.mocked(auditApi.listAuditFindings).mockImplementation((params) => Promise.resolve(params?.offset === 0 ? firstPage : []) as never);
    renderPage();
    await screen.findByText("Finding 1");
    await user.click(screen.getByRole("button", { name: "Next page" }));
    expect(await screen.findByText("No findings on this page.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Previous page" }));
    expect(await screen.findByText("Finding 1")).toBeInTheDocument();
  });

  it("shows list and create failures explicitly and hides write actions without permission", async () => {
    vi.mocked(auditApi.listAuditFindings).mockRejectedValueOnce(new Error("network"));
    renderPage(["audit_finding:read"]);
    expect(await screen.findByRole("alert")).toHaveTextContent("Unable to load audit findings");
    expect(screen.queryByText("No audit findings recorded.")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "New Finding" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Retry loading audit findings" }));
  });

  it("keeps the form open and values intact when a finding mutation fails", async () => {
    const user = userEvent.setup();
    vi.mocked(auditApi.createAuditFinding).mockRejectedValueOnce(new Error("network"));
    renderPage();
    await screen.findByText("Training record missing");
    await user.click(screen.getByRole("button", { name: "New Finding" }));
    await user.selectOptions(screen.getByRole("combobox", { name: "Audit engagement" }), "audit-1");
    await user.type(screen.getByLabelText(/Finding Number/), "2");
    await user.type(screen.getByLabelText(/Area/), "Safety");
    await user.selectOptions(screen.getByLabelText(/Level/), "2");
    await user.type(screen.getByLabelText(/Title/), "Missing evidence");
    await user.type(screen.getByLabelText(/Description/), "Evidence unavailable.");
    await user.click(screen.getByRole("button", { name: "Create Finding" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Unable to create audit finding");
    expect(screen.getByLabelText(/Title/)).toHaveValue("Missing evidence");
  });
});
