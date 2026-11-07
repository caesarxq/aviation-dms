import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { AuthContext } from "../auth/AuthContext";
import type { AuthProfile } from "../auth/AuthContext";
import api from "../api/client";
import { WelcomePage } from "./Welcome";

vi.mock("../api/client", () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

const initialProfile: AuthProfile = {
  user: {
    user_id: "u-safety/security",
    username: "safety",
    email: "safety@example.test",
    full_name: "Amina Njeri",
    department: "Operations",
    role: "head_safety",
    active_role: "head_safety",
    roles: ["head_safety", "head_security"],
  },
  role: "head_safety",
  active_role: "head_safety",
  roles: ["head_safety", "head_security"],
  authenticated_via: "session_cookie",
  permissions: ["safety:read"],
  onboarding_completed: false,
};

function RoutePath() {
  const location = useLocation();
  return <output data-testid="route-path">{location.pathname}</output>;
}

function renderWelcome(authProfile = initialProfile) {
  const selectedProfile: AuthProfile = {
    ...authProfile,
    role: "head_security",
    active_role: "head_security",
    permissions: ["security:read_sensitive"],
  };
  const authValue = {
    profile: authProfile,
    state: "authenticated" as const,
    login: vi.fn(),
    switchRole: vi.fn().mockResolvedValue(selectedProfile),
    logout: vi.fn(),
    refreshProfile: vi.fn().mockResolvedValue(selectedProfile),
    hasPermission: vi.fn(() => false),
  };

  return render(
    <AuthContext.Provider value={authValue as never}>
      <MemoryRouter initialEntries={["/welcome"]}>
        <RoutePath />
        <Routes>
          <Route path="/welcome" element={<WelcomePage />} />
          <Route path="/safety-actions" element={<h1>Safety workspace</h1>} />
          <Route path="/security-reviews" element={<h1>Security workspace</h1>} />
        </Routes>
      </MemoryRouter>
    </AuthContext.Provider>,
  );
}

beforeEach(() => {
  vi.mocked(api.get).mockResolvedValue({
    data: {
      onboarding_completed: false,
      assigned_roles: ["head_safety", "head_security"],
      active_role: "head_safety",
      canonical_user_id: "u-safety/security",
      full_name: "Amina Njeri",
    },
  } as never);
  vi.mocked(api.post).mockResolvedValue({ status: 200, data: {} } as never);
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("WelcomePage", () => {
  it("shows the person's name, canonical ID, and department for identity confirmation", async () => {
    renderWelcome();

    expect(await screen.findByText("Amina Njeri")).toBeInTheDocument();
    expect(screen.getByText("u-safety/security")).toBeInTheDocument();
    expect(screen.getByText("Operations")).toBeInTheDocument();
  });

  it("lands in the selected role's workspace after completing onboarding", async () => {
    const user = userEvent.setup();
    renderWelcome();

    await screen.findByLabelText("Active role for this session");
    await user.selectOptions(screen.getByLabelText("Active role for this session"), "head_security");
    await user.click(screen.getByRole("button", { name: "Continue to work" }));

    await waitFor(() => expect(screen.getByTestId("route-path")).toHaveTextContent("/security-reviews"));
  });
});
