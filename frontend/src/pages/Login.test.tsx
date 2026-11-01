import { AuthContext, type AuthProfile } from "../auth/AuthContext";
import { LoginPage } from "./Login";
import api from "../api/client";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../api/client", () => ({ default: { get: vi.fn(), post: vi.fn() } }));

const recordsCustodian: AuthProfile = {
  user: { user_id: "u-records", username: "records", email: "records@example.test", full_name: "Records Custodian", role: "records_custodian", active_role: "records_custodian", roles: ["records_custodian"] },
  role: "records_custodian",
  active_role: "records_custodian",
  roles: ["records_custodian"],
  authenticated_via: "session_cookie",
  onboarding_completed: true,
  permissions: ["document:read", "audit:read"],
  };

function renderLogin({ state, profile, login, initialEntry = "/login" }: {
  state: "loading" | "authenticated" | "unauthenticated";
  profile: AuthProfile | null;
  login: (username: string, password: string) => Promise<AuthProfile>;
  initialEntry?: string | { pathname: string; state?: unknown };
}) {
  const authValue = {
    profile,
    state,
    login,
    switchRole: async () => { throw new Error("not used"); },
    logout: async () => {},
    refreshProfile: async () => { throw new Error("not used"); },
    hasPermission: (permission: string) => Boolean(profile?.permissions.includes(permission)),
  };
  return render(
    <AuthContext.Provider value={authValue}>
      <MemoryRouter initialEntries={[initialEntry]}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/" element={<div data-testid="dashboard-screen">Dashboard</div>} />
          <Route path="/documents" element={<div data-testid="documents-screen">Documents</div>} />
          <Route path="/notifications" element={<div data-testid="notifications-screen">Notifications</div>} />
        </Routes>
      </MemoryRouter>
    </AuthContext.Provider>
  );
}

describe("LoginPage role-aware routing", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.get).mockResolvedValue({ data: { setup_required: false, bootstrap_configured: false } } as any);
  });

  it("sends an already-authenticated records custodian to an accessible screen", async () => {
    renderLogin({ state: "authenticated", profile: recordsCustodian, login: vi.fn() });

    expect(await screen.findByTestId("documents-screen")).toBeInTheDocument();
    expect(screen.queryByTestId("dashboard-screen")).not.toBeInTheDocument();
  });

  it("falls back from a forbidden return path after login to an accessible screen", async () => {
    const login = vi.fn().mockResolvedValue(recordsCustodian);
    renderLogin({
      state: "unauthenticated",
      profile: null,
      login,
      initialEntry: { pathname: "/login", state: { from: "/notifications" } },
    });

    await userEvent.type(screen.getByLabelText("Username"), "records");
    await userEvent.type(screen.getByLabelText("Password"), "a-test-password");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByTestId("documents-screen")).toBeInTheDocument();
    expect(screen.queryByTestId("notifications-screen")).not.toBeInTheDocument();
  });
});
