import { AuthContext } from "../auth/AuthContext";
import { safetyApi } from "../api/safety";
import { Dashboard } from "./Dashboard";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ToastProvider } from "../components/ui/Toast";
import { MemoryRouter } from "react-router-dom";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";
import { describe, expect, it, vi } from "vitest";

vi.mock("../api/safety", () => ({
  safetyApi: {
    getTrends: vi.fn().mockResolvedValue({ hazards_by_risk_level: {}, occurrences_last_30_days: 0, safety_actions_by_status: { open: 0 } }),
    getDeadlines: vi.fn().mockResolvedValue({ overdue_count: 0, overdue: [], upcoming: [] }),
  },
}));

function renderDashboard(fullName: string) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const profile = {
    user: { user_id: "u-user", username: "user", email: "user@example.test", full_name: fullName, role: "head_safety", active_role: "head_safety", roles: ["head_safety"] },
    role: "head_safety",
    active_role: "head_safety",
    roles: ["head_safety"],
    authenticated_via: "session_cookie",
    onboarding_completed: true,
    permissions: ["safety:read"],
};
  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter>
          <AuthContext.Provider value={{
            profile,
            state: "authenticated",
            login: async () => profile,
            switchRole: async () => profile,
            logout: async () => {},
            refreshProfile: async () => profile,
            hasPermission: (permission) => profile.permissions.includes(permission),
          }}>
            <Dashboard />
          </AuthContext.Provider>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>
  );
}

describe("Dashboard greeting", () => {
  it("uses the authenticated profile name", () => {
    renderDashboard("Miriam Njoroge");
    expect(screen.getByText(/Welcome, Miriam Njoroge/i)).toBeInTheDocument();
  });

  it("uses a neutral greeting when the profile name is empty", () => {
    renderDashboard("");
    expect(screen.getByText(/A clear view of safety, compliance, and operational commitments/i)).toBeInTheDocument();
  });

  it("does not describe the whole system as healthy without dedicated health data", async () => {
    renderDashboard("Miriam Njoroge");
    expect(await screen.findByText("Dashboard data loaded" )).toBeInTheDocument();
    expect(screen.queryByText("System healthy")).not.toBeInTheDocument();
    expect(screen.getByText("Status not verified")).toBeInTheDocument();
    expect(screen.getByText("Notification status not checked")).toBeInTheDocument();
  });

  it("shows unavailable dashboard metrics when their data query fails", async () => {
    vi.mocked(safetyApi.getTrends).mockRejectedValueOnce(new Error("network"));
    renderDashboard("Miriam Njoroge");
    expect(await screen.findByText("Some dashboard data is unavailable")).toBeInTheDocument();
    expect(screen.getAllByText("Unavailable", { selector: "div" })).toHaveLength(2);
  });

  it("does not show an all-clear deadline state when deadline data fails", async () => {
    vi.mocked(safetyApi.getDeadlines).mockRejectedValueOnce(new Error("network"));
    renderDashboard("Miriam Njoroge");
    expect(await screen.findByText("Unable to load deadline data.")).toBeInTheDocument();
    expect(screen.queryByText("No deadlines require attention.")).not.toBeInTheDocument();
  });
});
