import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AuthContext } from "../auth/AuthContext";
import { p2Api } from "../api/p2";
import { ToastProvider } from "../components/ui/Toast";
import { DGResponsibilityMatrix, OutsourcedFunctions, SafetyKPIs, SecurityReviews } from "./P2Pages";

vi.mock("../api/p2", () => ({ p2Api: {
  listOutsourcedFunctions: vi.fn(), createOutsourcedFunction: vi.fn(),
  listSafetyKPIs: vi.fn(), createSafetyKPI: vi.fn(),
  listSecurityReviews: vi.fn(), createSecurityReview: vi.fn(),
  listDGMatrix: vi.fn(), createDGMatrix: vi.fn(),
} }));

const profile = { user: { user_id: "u1", username: "user", email: "u@example.test", full_name: "User", role: "head_quality", active_role: "head_quality", roles: ["head_quality"] }, role: "head_quality", active_role: "head_quality", roles: ["head_quality"], authenticated_via: "session_cookie", onboarding_completed: true, permissions: ["safety:read", "safety:create"] };
function renderPage(page: React.ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><ToastProvider><AuthContext.Provider value={{ profile, state: "authenticated", login: async () => profile, switchRole: async () => profile, logout: async () => {}, refreshProfile: async () => profile, hasPermission: (permission) => profile.permissions.includes(permission) }}>{page}</AuthContext.Provider></ToastProvider></QueryClientProvider>);
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(p2Api.listOutsourcedFunctions).mockResolvedValue([{ function_id: "of1", provider_name: "Alpha Air", scope: "Inspection", status: "active" }, { function_id: "of2", provider_name: "Beta Labs", scope: "Calibration", status: "inactive" }] as never);
  vi.mocked(p2Api.listSafetyKPIs).mockResolvedValue([{ kpi_id: "k1", kpi_name: "Incident rate", target: "0", status: "active" }] as never);
  vi.mocked(p2Api.listSecurityReviews).mockResolvedValue([{ review_id: "sr1", meeting_date: "2026-10-01", attendees: "Security team", status: "scheduled" }] as never);
  vi.mocked(p2Api.listDGMatrix).mockResolvedValue([{ matrix_id: "dm1", project_or_route: "Nairobi route", process_stage: "Acceptance", responsible_role: "DG coordinator", status: "active" }] as never);
});

describe("P2 list search controls", () => {
  it("filters provider records without using search as the create field", async () => {
    const user = userEvent.setup();
    renderPage(<OutsourcedFunctions />);
    await screen.findByText("Alpha Air");
    await user.type(screen.getByPlaceholderText("Search providers…"), "Alpha");
    expect(screen.getByText("Alpha Air")).toBeInTheDocument();
    expect(screen.queryByText("Beta Labs")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Add Provider" }));
    expect(screen.getByLabelText(/Provider name/)).toHaveValue("");
  });

  it("filters KPI records", async () => {
    const user = userEvent.setup();
    renderPage(<SafetyKPIs />);
    await screen.findByText("Incident rate");
    await user.type(screen.getByPlaceholderText("Search KPIs…"), "missing");
    expect(screen.getByText("No safety KPIs match these filters.")).toBeInTheDocument();
  });

  it("filters security reviews", async () => {
    const user = userEvent.setup();
    renderPage(<SecurityReviews />);
    await screen.findByText("Security team");
    await user.type(screen.getByPlaceholderText("Search reviews…"), "2026-11");
    expect(screen.getByText("No security reviews match these filters.")).toBeInTheDocument();
  });

  it("filters DG responsibility entries", async () => {
    const user = userEvent.setup();
    renderPage(<DGResponsibilityMatrix />);
    await screen.findByText("Nairobi route");
    await user.type(screen.getByPlaceholderText("Search matrix entries…"), "coastal");
    expect(screen.getByText("No matrix entries match these filters.")).toBeInTheDocument();
  });
});
