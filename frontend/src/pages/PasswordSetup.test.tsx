import { AuthContext } from "../auth/AuthContext";
import { PasswordSetupPage } from "./PasswordSetup";
import api from "../api/client";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom";
import { MemoryRouter, useLocation } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("../api/client", () => ({ default: { get: vi.fn(), post: vi.fn() } }));

function CurrentLocation() {
  const location = useLocation();
  return <output data-testid="current-location">{location.pathname}{location.search}{location.hash}</output>;
}

function renderSetup(initialEntry = "/setup") {
  return render(
    <AuthContext.Provider value={{
      profile: null,
      state: "unauthenticated",
      login: async () => { throw new Error("not used"); },
      switchRole: async () => { throw new Error("not used"); },
      logout: async () => {},
      refreshProfile: async () => { throw new Error("not used"); },
      hasPermission: () => false,
    }}>
      <MemoryRouter initialEntries={[initialEntry]}>
        <PasswordSetupPage />
        <CurrentLocation />
      </MemoryRouter>
    </AuthContext.Provider>
  );
}

afterEach(() => vi.restoreAllMocks());

describe("PasswordSetupPage", () => {
  it("includes the assigned username in the form and blocks blank usernames", async () => {
    vi.mocked(api.get).mockResolvedValue({ data: { setup_required: false, bootstrap_configured: true, bootstrap_token_required: true } } as any);
    renderSetup();

    const username = await screen.findByLabelText("Assigned username");
    const form = screen.getByRole("button", { name: "Set password" }).closest("form");
    expect(form).not.toBeNull();
    expect(form).toContainElement(username);

    await userEvent.type(screen.getByLabelText("One-time setup token"), "valid-setup-token");
    await userEvent.type(screen.getByLabelText("New password"), "AValid-Test-Password-2026!");
    await userEvent.type(screen.getByLabelText("Confirm new password"), "AValid-Test-Password-2026!");
    fireEvent.submit(form!);

    expect(await screen.findByRole("alert")).toHaveTextContent(/enter your assigned username/i);
    expect(api.post).not.toHaveBeenCalled();
  });

  it("shows setup-status failures and lets the user retry", async () => {
    vi.mocked(api.get)
      .mockRejectedValueOnce(new Error("offline"))
      .mockResolvedValueOnce({ data: { setup_required: false, bootstrap_configured: true, bootstrap_token_required: true } } as any);
    renderSetup();

    expect(await screen.findByRole("alert")).toHaveTextContent(/unable to determine/i);
    const attemptsBeforeRetry = vi.mocked(api.get).mock.calls.length;
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByLabelText("Assigned username")).toBeInTheDocument();
    expect(vi.mocked(api.get).mock.calls.length).toBeGreaterThan(attemptsBeforeRetry);
  });

  it("uses the one-time token from an invitation email fragment", async () => {
    vi.mocked(api.get).mockClear();
    vi.mocked(api.post).mockResolvedValue({ data: { status: "ok" } } as any);
    const setupToken = "a".repeat(64);
    renderSetup(`/setup?username=librarian#setup_token=${setupToken}`);

    expect(await screen.findByText(/secure invitation link/i)).toBeInTheDocument();
    await waitFor(() => expect(screen.getByTestId("current-location")).toHaveTextContent(/^\/setup$/));
    expect(screen.queryByLabelText("One-time setup token")).not.toBeInTheDocument();
    await userEvent.type(screen.getByLabelText("New password"), "AValid-Test-Password-2026!");
    await userEvent.type(screen.getByLabelText("Confirm new password"), "AValid-Test-Password-2026!");
    await userEvent.click(screen.getByRole("button", { name: "Set password" }));

    expect(await screen.findByText("Password set. Sign in with your assigned username and new password.")).toBeInTheDocument();
    expect(api.get).not.toHaveBeenCalled();
    expect(api.post).toHaveBeenCalledWith("/p0/auth/password-setup", {
      username: "librarian",
      setup_token: setupToken,
      password: "AValid-Test-Password-2026!",
    });
  });
});
