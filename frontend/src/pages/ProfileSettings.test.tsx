import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import api from "../api/client";
import { AuthContext } from "../auth/AuthContext";
import { ProfileSettingsPage } from "./ProfileSettings";

vi.mock("../api/client", () => ({ default: { get: vi.fn(), post: vi.fn() } }));

const profile = {
  user_id: "u-safety", username: "safety", email: "safety@kfl.ke", full_name: "Safety Officer",
  role: "safety", active_role: "safety", roles: ["safety", "quality"], department: "Safety", onboarding_completed: true,
};

function renderPage() {
  vi.mocked(api.get).mockResolvedValue({ data: profile } as never);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <AuthContext.Provider value={{ profile, state: "authenticated", login: async () => profile, switchRole: async () => profile, logout: async () => {}, refreshProfile: async () => profile, hasPermission: () => true } as never}>
        <ProfileSettingsPage />
      </AuthContext.Provider>
    </QueryClientProvider>,
  );
}

beforeEach(() => { vi.clearAllMocks(); });

describe("ProfileSettingsPage", () => {
  it("renders the account profile with roles and onboarding state", async () => {
    renderPage();
    expect(await screen.findByRole("heading", { name: "Profile Settings" })).toBeInTheDocument();
    expect(screen.getAllByText("Safety Officer")).toHaveLength(2);
    expect(screen.getByText("safety@kfl.ke")).toBeInTheDocument();
    expect(screen.getByText("safety, quality")).toBeInTheDocument();
    expect(screen.getByText("Complete")).toBeInTheDocument();
  });

  it("rejects mismatched passwords before calling the API", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByRole("heading", { name: "Profile Settings" });
    await user.type(screen.getByLabelText("Current Password"), "OldPass123!");
    await user.type(screen.getByLabelText("New Password"), "ValidPass123!");
    await user.type(screen.getByLabelText("Confirm New Password"), "DifferentPass123!");
    await user.click(screen.getByRole("button", { name: "Change Password" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("The passwords do not match.");
    expect(api.post).not.toHaveBeenCalled();
  });

  it("changes the password and confirms other sessions were signed out", async () => {
    const user = userEvent.setup();
    vi.mocked(api.post).mockResolvedValue({ data: {} } as never);
    renderPage();
    await screen.findByRole("heading", { name: "Profile Settings" });
    await user.type(screen.getByLabelText("Current Password"), "OldPass123!");
    await user.type(screen.getByLabelText("New Password"), "ValidPass123!");
    await user.type(screen.getByLabelText("Confirm New Password"), "ValidPass123!");
    await user.click(screen.getByRole("button", { name: "Change Password" }));
    await waitFor(() => expect(api.post).toHaveBeenCalledWith("/p0/auth/change-password", { current_password: "OldPass123!", new_password: "ValidPass123!" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Password changed successfully. Your other sessions were signed out.");
  });
});