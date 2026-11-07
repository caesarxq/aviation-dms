import { AuthContext } from "../../auth/AuthContext";
import { AppShell } from "./AppShell";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { safetyApi } from "../../api/safety";

const recordsCustodianProfile = {
  user: {
    user_id: "u-records",
    username: "records",
    email: "records@example.test",
    full_name: "Records Custodian",
    role: "records_custodian",
    active_role: "records_custodian",
    roles: ["records_custodian"],
  },
  role: "records_custodian",
  active_role: "records_custodian",
  roles: ["records_custodian"],
  authenticated_via: "session_cookie",
  onboarding_completed: true,
  permissions: ["document:read", "audit:read", "compliance:read"],
};

function CurrentPath() {
  const location = useLocation();
  return <output data-testid="current-path">{location.pathname}</output>;
}

function renderShell(
  logout: () => Promise<void>,
  initialPath = "/documents",
  authProfile = recordsCustodianProfile,
  switchRole: (activeRole: string) => Promise<typeof recordsCustodianProfile> = async () => authProfile,
) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const authValue = {
    profile: authProfile,
    state: "authenticated" as const,
    login: async () => authProfile,
    switchRole,
    logout,
    refreshProfile: async () => authProfile,
    hasPermission: (permission: string) => authProfile.permissions.includes(permission),
  };

  return render(
    <QueryClientProvider client={queryClient}>
      <AuthContext.Provider value={authValue}>
        <MemoryRouter initialEntries={[initialPath]}>
          <CurrentPath />
          <Routes>
            <Route path="/login" element={<div data-testid="login-screen">Sign in</div>} />
            <Route element={<AppShell />}>
              <Route path="/documents" element={<div data-testid="documents-screen">Documents</div>} />
              <Route path="/document-proposals" element={<div data-testid="document-proposals-screen">Document proposals</div>} />
              <Route path="/notifications" element={<div data-testid="notifications-screen">Notifications</div>} />
              <Route path="/organization-overview" element={<div data-testid="organization-overview-screen">Organization overview</div>} />
              <Route path="/occurrences" element={<div data-testid="occurrences-screen">Occurrences</div>} />
              <Route path="/admin/observability" element={<div data-testid="observability-screen">System observability</div>} />
            </Route>
          </Routes>
        </MemoryRouter>
      </AuthContext.Provider>
    </QueryClientProvider>
  );
}

afterEach(() => vi.restoreAllMocks());

const switchableRoleGroups = [
  ["system administrator and maintenance", ["system_admin", "head_maintenance"]],
  ["librarian, quality, and records", ["librarian", "head_quality", "records_custodian"]],
  ["safety and security", ["head_safety", "head_security"]],
  ["operations, pilot, and training", ["head_operations", "chief_pilot", "head_training"]],
  ["flight operations and dangerous goods", ["flight_ops_officer", "dg_coordinator"]],
] as const;
const switchableRoleTransitions = switchableRoleGroups.flatMap(([group, roles]) =>
  roles.flatMap((sourceRole) =>
    roles
      .filter((targetRole) => targetRole !== sourceRole)
      .map((targetRole) => [group, sourceRole, targetRole, roles] as const),
  ),
);

describe("AppShell authentication screens", () => {
  it.each(switchableRoleTransitions)("lets %s users switch from %s to %s", async (_group, sourceRole, targetRole, roles) => {
    const multiRoleProfile = {
      ...recordsCustodianProfile,
      user: {
        ...recordsCustodianProfile.user,
        role: sourceRole,
        active_role: sourceRole,
        roles: [...roles],
      },
      role: sourceRole,
      active_role: sourceRole,
      roles: [...roles],
      permissions: ["document:read"],
    };
    const switchRole = vi.fn().mockImplementation(async (activeRole: string) => ({
      ...multiRoleProfile,
      user: { ...multiRoleProfile.user, role: activeRole, active_role: activeRole },
      role: activeRole,
      active_role: activeRole,
    }));
    renderShell(async () => {}, "/documents", multiRoleProfile, switchRole);

    const selector = screen.getByLabelText("Active role");
    expect(selector).toHaveValue(sourceRole);
    expect(
      Array.from((selector as HTMLSelectElement).options, (option) => option.value).sort(),
    ).toEqual([...roles].sort());

    await userEvent.selectOptions(selector, targetRole);
    await waitFor(() => expect(switchRole).toHaveBeenCalledWith(targetRole));
    await waitFor(() => expect(selector).not.toBeDisabled());
  });

  it("puts accountable-manager priorities first and keeps secondary modules collapsed", async () => {
    const managerProfile = {
      ...recordsCustodianProfile,
      user: {
        ...recordsCustodianProfile.user,
        user_id: "u-accountable",
        role: "accountable_manager",
        active_role: "accountable_manager",
        roles: ["accountable_manager"],
      },
      role: "accountable_manager",
      active_role: "accountable_manager",
      roles: ["accountable_manager"],
      permissions: [
        "organization:overview", "document:read", "change_request:review", "change_request:approve",
        "audit_report:read", "audit_finding:read", "safety:read", "roc:read", "aircraft:read",
      ],
    };
    renderShell(async () => {}, "/organization-overview", managerProfile);

    const workspace = screen.getByRole("navigation", { name: "My workspace" });
    expect(workspace).toContainElement(screen.getByRole("link", { name: "Organization overview" }));
    expect(workspace).toContainElement(screen.getByRole("link", { name: "Audit Reports" }));
    expect(screen.queryByRole("button", { name: "Safety" })).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "All modules" }));
    expect(screen.getByRole("button", { name: "Safety" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Flight" }));
    expect(within(screen.getByLabelText("All modules navigation")).getByRole("link", { name: "Dangerous Goods" })).toBeInTheDocument();
    expect(within(screen.getByLabelText("All modules navigation")).queryByRole("link", { name: "Missions" })).not.toBeInTheDocument();
  });

  it("keeps occurrence reporters' safety read workspace and screens available", async () => {
    const occurrenceProfile = {
      ...recordsCustodianProfile,
      user: {
        ...recordsCustodianProfile.user,
        user_id: "u-occurrence",
        role: "occurrence_reporter",
        active_role: "occurrence_reporter",
        roles: ["occurrence_reporter"],
      },
      role: "occurrence_reporter",
      active_role: "occurrence_reporter",
      roles: ["occurrence_reporter"],
      permissions: ["safety:read"],
    };
    renderShell(async () => {}, "/occurrences", occurrenceProfile);

    const workspace = screen.getByRole("navigation", { name: "My workspace" });
    expect(within(workspace).getByRole("link", { name: "Safety Occurrences" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "All modules" }));
    await userEvent.click(screen.getByRole("button", { name: "Safety" }));
    const allModules = screen.getByLabelText("All modules navigation");
    expect(within(allModules).queryByRole("link", { name: "Safety Occurrences" })).not.toBeInTheDocument();
    expect(within(allModules).getByRole("link", { name: "Hazard Register" })).toBeInTheDocument();
  });

  it("shows one-time workspace tips per canonical user and remembers dismissal", async () => {
    const guideKey = "kfl:workspace-guide:v1:u-records";
    localStorage.removeItem(guideKey);
    const firstRender = renderShell(async () => {});

    expect(screen.getByRole("region", { name: "One-time workspace tips" })).toBeInTheDocument();
    expect(screen.getByText(/shortcuts for your active role/i)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Got it" }));
    expect(screen.queryByRole("region", { name: "One-time workspace tips" })).not.toBeInTheDocument();
    expect(localStorage.getItem(guideKey)).toBe("dismissed");

    firstRender.unmount();
    const sameUserRender = renderShell(async () => {});
    expect(screen.queryByRole("region", { name: "One-time workspace tips" })).not.toBeInTheDocument();
    sameUserRender.unmount();

    const otherUserProfile = {
      ...recordsCustodianProfile,
      user: { ...recordsCustodianProfile.user, user_id: "u-other-records" },
    };
    const otherUserRender = renderShell(async () => {}, "/documents", otherUserProfile);
    expect(screen.getByRole("region", { name: "One-time workspace tips" })).toBeInTheDocument();
    otherUserRender.unmount();

    localStorage.removeItem(guideKey);
    localStorage.removeItem("kfl:workspace-guide:v1:u-other-records");
  });

  it("does not show workspace tips while onboarding is incomplete", () => {
    const incompleteProfile = { ...recordsCustodianProfile, onboarding_completed: false };
    renderShell(async () => {}, "/documents", incompleteProfile);

    expect(screen.queryByRole("region", { name: "One-time workspace tips" })).not.toBeInTheDocument();
  });

  it("keeps account and session controls in a labeled mobile utility panel", () => {
    renderShell(async () => {});
    const utilities = screen.getByRole("region", { name: "Account and session controls" });
    expect(utilities).toHaveClass("mobile-session-controls");
    expect(utilities).toContainElement(screen.getByRole("link", { name: "Account security" }));
    expect(utilities).toContainElement(screen.getByRole("link", { name: "Profile settings" }));
    expect(utilities).toContainElement(screen.getByRole("button", { name: "Sign out" }));
  });

  it("shows only screens and utility links allowed to records custodians", async () => {
    vi.spyOn(safetyApi, "getUnreadCount").mockResolvedValue({ unread_count: 0 });
    renderShell(async () => {});

    expect(screen.queryByLabelText("Active role")).not.toBeInTheDocument();
    expect(screen.getByTestId("documents-screen")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "All modules" }));
    await userEvent.click(screen.getByRole("button", { name: "Document Control" }));
    expect(within(screen.getByRole("navigation", { name: "My workspace" })).getByRole("link", { name: "Documents" })).toBeInTheDocument();
    expect(within(screen.getByLabelText("All modules navigation")).queryByRole("link", { name: "Documents" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Dashboard" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Notifications/ })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Account security" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sign out" })).toBeInTheDocument();
  });

  it("does not show notification controls to safety-only roles without compliance read access", () => {
    vi.spyOn(safetyApi, "getUnreadCount").mockResolvedValue({ unread_count: 0 });
    const safetyOnlyProfile = {
      ...recordsCustodianProfile,
      user: {
        ...recordsCustodianProfile.user,
        role: "head_safety",
        active_role: "head_safety",
        roles: ["head_safety"],
      },
      role: "head_safety",
      active_role: "head_safety",
      roles: ["head_safety"],
      permissions: ["safety:read"],
    };

    renderShell(async () => {}, "/occurrences", safetyOnlyProfile);

    expect(screen.queryByRole("button", { name: /Notifications/ })).not.toBeInTheDocument();
    expect(safetyApi.getUnreadCount).not.toHaveBeenCalled();
  });

  it("shows document catalogue and proposal navigation for proposal-only users", async () => {
    const proposalOnlyProfile = {
      ...recordsCustodianProfile,
      permissions: ["document:propose"],
    };
    renderShell(async () => {}, "/documents", proposalOnlyProfile);

    await userEvent.click(screen.getByRole("button", { name: "All modules" }));
    const modules = screen.getByLabelText("All modules navigation");
    expect(within(screen.getByRole("navigation", { name: "My workspace" })).getByRole("link", { name: "Documents" })).toBeInTheDocument();
    const proposalsLink = within(modules).getByRole("link", { name: "Document Proposals" });
    expect(proposalsLink).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Change Requests" })).not.toBeInTheDocument();

    await userEvent.click(proposalsLink);
    await waitFor(() => expect(screen.getByTestId("current-path")).toHaveTextContent("/document-proposals"));
    expect(screen.getByTestId("document-proposals-screen")).toBeInTheDocument();
  });

  it("uses the records custodian's permitted landing screen from the brand control", async () => {
    renderShell(async () => {});

    fireEvent.click(screen.getByRole("button", { name: "Go to Documents" }));
    await waitFor(() => expect(screen.getByTestId("current-path")).toHaveTextContent("/documents"));
    expect(screen.getByTestId("documents-screen")).toBeInTheDocument();
  });

  it("does not claim sign-out succeeded when the server cannot confirm it", async () => {
    const logout = vi.fn().mockRejectedValue(new Error("network unavailable"));
    renderShell(logout);

    fireEvent.click(screen.getByRole("button", { name: "Sign out" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/sign-out was not confirmed/i);
    expect(screen.getByTestId("documents-screen")).toBeInTheDocument();
    expect(screen.queryByTestId("login-screen")).not.toBeInTheDocument();
    expect(logout).toHaveBeenCalledOnce();
  });

  it("navigates to sign-in only after the server confirms logout", async () => {
    const logout = vi.fn().mockResolvedValue(undefined);
    renderShell(logout);

    fireEvent.click(screen.getByRole("button", { name: "Sign out" }));

    expect(await screen.findByTestId("login-screen")).toBeInTheDocument();
    expect(logout).toHaveBeenCalledOnce();
  });
});
