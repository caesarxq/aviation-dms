import { AuthContext } from "../auth/AuthContext";
import { PasswordSetupPage } from "./PasswordSetup";
import api from "../api/client";
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("../api/client", () => ({ default: { get: vi.fn(), post: vi.fn() } }));

function renderSetup() {
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
      <MemoryRouter><PasswordSetupPage /></MemoryRouter>
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
});
