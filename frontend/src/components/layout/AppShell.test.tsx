import { AuthContext } from "../../auth/AuthContext";
import { AppShell } from "./AppShell";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

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
              <Route path="/notifications" element={<div data-testid="notifications-screen">Notifications</div>} />
            </Route>
          </Routes>
        </MemoryRouter>
      </AuthContext.Provider>
    </QueryClientProvider>
  );
}

afterEach(() => vi.restoreAllMocks());

describe("AppShell authentication screens", () => {
  it("lets a multi-role user select an assigned active role", async () => {
    const multiRoleProfile = {
      ...recordsCustodianProfile,
      user: { ...recordsCustodianProfile.user, role: "librarian", roles: ["librarian", "head_quality"] },
      role: "librarian",
      active_role: "librarian",
      roles: ["librarian", "head_quality"],
    };
    const switchRole = vi.fn().mockResolvedValue({
      ...multiRoleProfile,
      user: { ...multiRoleProfile.user, role: "head_quality" },
      role: "head_quality",
      active_role: "head_quality",
    });
    renderShell(async () => {}, "/documents", multiRoleProfile, switchRole);

    const selector = screen.getByLabelText("Active role");
    expect(selector).toHaveValue("librarian");
    expect(screen.getByRole("option", { name: "head quality" })).toBeInTheDocument();
    await userEvent.selectOptions(selector, "head_quality");

    expect(switchRole).toHaveBeenCalledWith("head_quality");
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
    renderShell(async () => {});

    expect(screen.getByTestId("documents-screen")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Document Control" }));
    expect(screen.getByRole("link", { name: "Documents" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Dashboard" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Notifications/ })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Account security" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sign out" })).toBeInTheDocument();
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
