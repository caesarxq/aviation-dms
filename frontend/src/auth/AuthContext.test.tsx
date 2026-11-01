import { AuthProvider, useAuth } from "./AuthContext";
import api from "../api/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("../api/client", () => ({ default: { get: vi.fn(), post: vi.fn() } }));

const profile = {
  user: { user_id: "u-records", username: "records", email: "records@example.test", full_name: "Records Custodian", role: "records_custodian", roles: ["records_custodian", "head_quality"] },
  role: "records_custodian",
  active_role: "records_custodian",
  roles: ["records_custodian", "head_quality"],
  authenticated_via: "session_cookie",
  onboarding_completed: true,
  permissions: ["document:read"],
};

function AuthControls() {
  const { state, profile: currentProfile, logout, switchRole } = useAuth();
  const handleSwitchRole = async () => {
    try {
      await switchRole("head_quality");
    } catch {
      // The real AppShell displays a warning after the profile reconciliation attempt.
    }
  };
  const handleLogout = async () => {
    try {
      await logout();
    } catch {
      // The real AppShell reports the failure and exposes a retry control.
    }
  };
  return (
    <div>
      <span data-testid="auth-state">{state}</span>
      <span data-testid="auth-name">{currentProfile?.user.full_name ?? ""}</span>
      <span data-testid="active-role">{currentProfile?.active_role ?? ""}</span>
      <button type="button" onClick={() => void handleSwitchRole()}>Switch to quality</button>
      <button type="button" onClick={() => void handleLogout()}>Sign out</button>
    </div>
  );
}

function renderAuth() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider><AuthControls /></AuthProvider>
    </QueryClientProvider>
  );
}

describe("AuthProvider logout", () => {
  afterEach(() => vi.restoreAllMocks());

  it("preserves the authenticated UI if server-side logout is not confirmed", async () => {
    vi.mocked(api.get).mockResolvedValue({ data: profile, status: 200 } as any);
    vi.mocked(api.post).mockRejectedValue(new Error("network unavailable"));
    renderAuth();

    await waitFor(() => expect(screen.getByTestId("auth-state").textContent).toBe("authenticated"));
    fireEvent.click(screen.getByRole("button", { name: "Sign out" }));

    await waitFor(() => expect(vi.mocked(api.post)).toHaveBeenCalledWith("/p0/auth/logout"));
    expect(screen.getByTestId("auth-state").textContent).toBe("authenticated");
    expect(screen.getByTestId("auth-name")).toHaveTextContent("Records Custodian");
  });

  it("switches the active role through the server and replaces the client permission profile", async () => {
    const switchedProfile = {
      ...profile,
      role: "head_quality",
      active_role: "head_quality",
      user: { ...profile.user, role: "head_quality" },
      permissions: ["document:read", "document:approve"],
    };
    vi.mocked(api.get).mockResolvedValue({ data: profile, status: 200 } as any);
    vi.mocked(api.post).mockResolvedValue({ data: switchedProfile } as any);
    renderAuth();

    await waitFor(() => expect(screen.getByTestId("auth-state").textContent).toBe("authenticated"));
    fireEvent.click(screen.getByRole("button", { name: "Switch to quality" }));

    await waitFor(() => expect(screen.getByTestId("active-role")).toHaveTextContent("head_quality"));
    expect(vi.mocked(api.post)).toHaveBeenCalledWith("/p0/auth/active-role", { active_role: "head_quality" });
  });

  it("refreshes the server profile when a role-switch response is lost", async () => {
    const switchedProfile = {
      ...profile,
      role: "head_quality",
      active_role: "head_quality",
      user: { ...profile.user, role: "head_quality" },
      permissions: ["document:read", "document:approve"],
      onboarding_completed: true,
    };
    vi.mocked(api.get)
      .mockResolvedValueOnce({ data: profile, status: 200 } as any)
      .mockResolvedValueOnce({ data: { onboarding_completed: true }, status: 200 } as any)
      .mockResolvedValueOnce({ data: switchedProfile, status: 200 } as any)
      .mockResolvedValueOnce({ data: { onboarding_completed: true }, status: 200 } as any);
    vi.mocked(api.post).mockRejectedValueOnce(new Error("response lost"));
    renderAuth();

    await waitFor(() => expect(screen.getByTestId("auth-state").textContent).toBe("authenticated"));
    fireEvent.click(screen.getByRole("button", { name: "Switch to quality" }));

    await waitFor(() => expect(screen.getByTestId("active-role")).toHaveTextContent("head_quality"));
  });

  it("clears the authenticated UI after the server confirms logout", async () => {
    vi.mocked(api.get).mockResolvedValue({ data: profile, status: 200 } as any);
    vi.mocked(api.post).mockResolvedValue({ data: { message: "Logout successful" } } as any);
    renderAuth();

    await waitFor(() => expect(screen.getByTestId("auth-state").textContent).toBe("authenticated"));
    fireEvent.click(screen.getByRole("button", { name: "Sign out" }));

    await waitFor(() => expect(screen.getByTestId("auth-state").textContent).toBe("unauthenticated"));
    expect(screen.getByTestId("auth-name")).toBeEmptyDOMElement();
  });
});
