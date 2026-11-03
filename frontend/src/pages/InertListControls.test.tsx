import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AuthContext } from "../auth/AuthContext";
import api from "../api/client";
import { ToastProvider } from "../components/ui/Toast";
import { QualityAudits } from "./QualityAudits";
import { DangerousGoods } from "./DangerousGoods";
import { SecurityManagement } from "./SecurityManagement";

vi.mock("../api/client", () => ({ default: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() } }));
vi.mock("../components/ui/modals/CorrectiveActionsModal", () => ({ CorrectiveActionsModal: () => null }));
vi.mock("../components/ui/modals/DGResponsibilityMatrixModal", () => ({ DGResponsibilityMatrixModal: () => null }));
vi.mock("../components/ui/modals/SecurityReviewsModal", () => ({ SecurityReviewsModal: () => null }));
vi.mock("../components/ui/modals/OutsourcedFunctionsModal", () => ({ OutsourcedFunctionsModal: () => null }));

const lists: Record<string, any> = {
  "/p1/quality-audits": [{ audit_id: "qa1", title: "Internal safety audit", audit_type: "internal", status: "planned", findings_count: 0 }, { audit_id: "qa2", title: "External security audit", audit_type: "external", status: "completed", findings_count: 2 }],
  "/p1/dg-shipments": [{ shipment_id: "dg1", proper_shipping_name: "Lithium batteries", dg_class: "9", un_number: "UN3480", status: "pending" }, { shipment_id: "dg2", proper_shipping_name: "Paint", dg_class: "3", un_number: "UN1263", status: "accepted" }],
  "/p1/security-incidents": [{ incident_id: "sec1", title: "Badge access anomaly", incident_type: "unauthorized_access", severity: "low", status: "reported" }, { incident_id: "sec2", title: "Perimeter alarm", incident_type: "intrusion", severity: "high", status: "investigating" }, { incident_id: "sec3", title: "Unresolved access issue", incident_type: "unauthorized_access", severity: "critical", status: "open" }],
  "/p1/security-incidents/summary": { total: 75, critical_high: 13, open: 22 },
};
const profile = { user: { user_id: "u1", username: "user", email: "u@example.test", full_name: "User", role: "head_quality", active_role: "head_quality", roles: ["head_quality"] }, role: "head_quality", active_role: "head_quality", roles: ["head_quality"], authenticated_via: "session_cookie", onboarding_completed: true, permissions: ["safety:read", "safety:create", "security:read_sensitive"] };
function renderPage(page: React.ReactNode, permissions: string[] = profile.permissions) {
  const userProfile = { ...profile, permissions };
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><ToastProvider><AuthContext.Provider value={{ profile: userProfile, state: "authenticated", login: async () => userProfile, switchRole: async () => userProfile, logout: async () => {}, refreshProfile: async () => userProfile, hasPermission: (permission) => permissions.includes(permission) }}><MemoryRouter>{page}</MemoryRouter></AuthContext.Provider></ToastProvider></QueryClientProvider>);
}

beforeEach(() => { vi.clearAllMocks(); vi.mocked(api.get).mockImplementation((path: string) => Promise.resolve({ data: lists[path] ?? [] }) as never); });

describe("inert list controls", () => {
  it("requires security:manage to report incidents while preserving existing review action gates", () => {
    renderPage(<SecurityManagement />, ["safety:create"]);
    expect(screen.queryByRole("button", { name: "Report Incident" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Schedule Review" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Register Outsourced Function" })).toBeInTheDocument();
  });

  it("filters quality audits independently from the create audit field", async () => {
    const user = userEvent.setup();
    renderPage(<QualityAudits />);
    await screen.findByText("Internal safety audit");
    await user.type(screen.getByRole("searchbox", { name: "Search quality audits" }), "Internal");
    expect(screen.getByText("Internal safety audit")).toBeInTheDocument();
    expect(screen.queryByText("External security audit")).not.toBeInTheDocument();
    await user.selectOptions(screen.getByRole("combobox", { name: "Filter quality audits by status" }), "planned");
    expect(screen.getByText("Internal safety audit")).toBeInTheDocument();
    expect(screen.queryByText("External security audit")).not.toBeInTheDocument();
  });

  it("filters dangerous goods shipments by text and status", async () => {
    const user = userEvent.setup();
    renderPage(<DangerousGoods />);
    await screen.findByText("Lithium batteries");
    await user.type(screen.getByRole("searchbox", { name: "Search shipments" }), "Paint");
    expect(screen.getByText("Paint")).toBeInTheDocument();
    expect(screen.queryByText("Lithium batteries")).not.toBeInTheDocument();
    await user.clear(screen.getByRole("searchbox", { name: "Search shipments" }));
    await user.selectOptions(screen.getByRole("combobox", { name: "Filter shipments by status" }), "pending");
    expect(screen.getByText("Lithium batteries")).toBeInTheDocument();
    expect(screen.queryByText("Paint")).not.toBeInTheDocument();
  });

  it("sends security search and status filters to the backend and includes closed", async () => {
    const user = userEvent.setup();
    vi.mocked(api.get).mockImplementation((path: string, config?: any) => {
      if (path === "/p1/security-incidents/summary") return Promise.resolve({ data: lists[path] }) as never;
      const params = config?.params ?? {};
      let result = lists[path] ?? [];
      if (params.search) result = result.filter((incident: any) => incident.title.includes(params.search));
      if (params.status) result = result.filter((incident: any) => incident.status === params.status);
      return Promise.resolve({ data: result }) as never;
    });
    renderPage(<SecurityManagement />);
    await screen.findByText("Badge access anomaly");
    expect(screen.getByText("Total Incidents").nextElementSibling).toHaveTextContent("75");
    expect(screen.getByText("Critical / High").nextElementSibling).toHaveTextContent("13");
    expect(screen.getAllByText("Open")[0].nextElementSibling).toHaveTextContent("22");
    expect(api.get).toHaveBeenCalledWith("/p1/security-incidents/summary");
    await user.type(screen.getByRole("searchbox", { name: "Search security incidents" }), "Perimeter");
    expect(await screen.findByText("Perimeter alarm")).toBeInTheDocument();
    await waitFor(() => expect(api.get).toHaveBeenLastCalledWith("/p1/security-incidents", { params: { search: "Perimeter", limit: 50, offset: 0 } }));
    await user.clear(screen.getByRole("searchbox", { name: "Search security incidents" }));
    const statusFilter = screen.getByRole("combobox", { name: "Filter security incidents by status" });
    expect(screen.getByRole("option", { name: "Open" })).toHaveValue("open");
    expect(screen.getByRole("option", { name: "Closed" })).toHaveValue("closed");
    await user.selectOptions(statusFilter, "open");
    expect(await screen.findByText("Unresolved access issue")).toBeInTheDocument();
    await waitFor(() => expect(api.get).toHaveBeenLastCalledWith("/p1/security-incidents", { params: { status: "open", limit: 50, offset: 0 } }));
    await user.selectOptions(statusFilter, "closed");
    await waitFor(() => expect(api.get).toHaveBeenLastCalledWith("/p1/security-incidents", { params: { status: "closed", limit: 50, offset: 0 } }));
  });

  it("does not request incident records for readers without sensitive access", async () => {
    renderPage(<SecurityManagement />, ["safety:read"]);
    expect(await screen.findByRole("alert")).toHaveTextContent("restricted");
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    expect(screen.queryByText("No security incidents.")).not.toBeInTheDocument();
    expect(screen.queryByText("Total Incidents")).not.toBeInTheDocument();
    expect(api.get).not.toHaveBeenCalledWith("/p1/security-incidents", expect.anything());
    expect(api.get).not.toHaveBeenCalledWith("/p1/security-incidents/summary", expect.anything());
  });

  it("clears an incident draft immediately when switching to a role without security management", async () => {
    const user = userEvent.setup();
    const profileFor = (activeRole: string, permissions: string[]) => ({
      ...profile, active_role: activeRole, role: activeRole, permissions,
      user: { ...profile.user, active_role: activeRole, role: activeRole },
    });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const renderWithProfile = (activeRole: string, permissions: string[]) => (
      <QueryClientProvider client={client}><ToastProvider><AuthContext.Provider value={{
        profile: profileFor(activeRole, permissions), state: "authenticated", login: async () => profile,
        switchRole: async () => profile, logout: async () => {}, refreshProfile: async () => profile,
        hasPermission: (permission) => permissions.includes(permission),
      }}><MemoryRouter><SecurityManagement /></MemoryRouter></AuthContext.Provider></ToastProvider></QueryClientProvider>
    );
    const view = render(renderWithProfile("head_security", ["security:read_sensitive", "security:manage"]));
    await screen.findByText("Badge access anomaly");
    await user.click(screen.getByRole("button", { name: "Report Incident" }));
    await user.type(screen.getByRole("textbox", { name: /Incident title/ }), "Unsubmitted sensitive draft");

    view.rerender(renderWithProfile("head_safety", ["security:read_sensitive"]));
    expect(screen.queryByRole("button", { name: "Report Incident" })).not.toBeInTheDocument();
    expect(screen.queryByText("New Security Incident")).not.toBeInTheDocument();

    view.rerender(renderWithProfile("head_security", ["security:read_sensitive", "security:manage"]));
    await user.click(screen.getByRole("button", { name: "Report Incident" }));
    expect(screen.getByRole("textbox", { name: /Incident title/ })).toHaveValue("");
    expect(screen.queryByDisplayValue("Unsubmitted sensitive draft")).not.toBeInTheDocument();
  });

  it("shows API failures from incident reporting", async () => {
    const user = userEvent.setup();
    vi.mocked(api.post).mockRejectedValue(new Error("request failed"));
    renderPage(<SecurityManagement />, ["security:read_sensitive", "security:manage"]);
    await screen.findByText("Badge access anomaly");
    await user.click(screen.getByRole("button", { name: "Report Incident" }));
    await user.type(screen.getByRole("textbox", { name: /Incident title/ }), "Failed report");
    await user.click(screen.getByRole("button", { name: "Report Incident" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Unable to report security incident");
  });
});
