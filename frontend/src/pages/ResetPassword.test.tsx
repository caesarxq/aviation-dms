import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import api from "../api/client";
import { ResetPasswordPage } from "./ResetPassword";

vi.mock("../api/client", () => ({ default: { post: vi.fn() } }));

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/reset/tok-123"]}>
      <Routes>
        <Route path="/reset/:token" element={<ResetPasswordPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

beforeEach(() => { vi.clearAllMocks(); });

describe("ResetPasswordPage", () => {
  it("renders the form and prefills the reset token from the route", () => {
    renderPage();
    expect(screen.getByRole("heading", { name: "Reset password" })).toBeInTheDocument();
    expect(screen.getByLabelText("Reset token")).toHaveValue("tok-123");
    expect(screen.getByLabelText("New password")).toBeInTheDocument();
    expect(screen.getByLabelText("Confirm new password")).toBeInTheDocument();
  });

  it("rejects mismatched passwords before calling the API", async () => {
    const user = userEvent.setup();
    renderPage();
    await user.type(screen.getByLabelText("New password"), "ValidPass123!");
    await user.type(screen.getByLabelText("Confirm new password"), "DifferentPass123!");
    await user.click(screen.getByRole("button", { name: "Reset password" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("The passwords do not match.");
    expect(api.post).not.toHaveBeenCalled();
  });

  it("submits a valid matching password with the reset token and confirms success", async () => {
    const user = userEvent.setup();
    vi.mocked(api.post).mockResolvedValue({ data: {} } as never);
    renderPage();
    await user.type(screen.getByLabelText("New password"), "ValidPass123!");
    await user.type(screen.getByLabelText("Confirm new password"), "ValidPass123!");
    await user.click(screen.getByRole("button", { name: "Reset password" }));
    await waitFor(() => expect(api.post).toHaveBeenCalledWith("/p0/auth/reset-password", { reset_token: "tok-123", password: "ValidPass123!" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Password reset. Sign in with your new password.");
  });

  it("surfaces an invalid/expired token error from the server", async () => {
    const user = userEvent.setup();
    vi.mocked(api.post).mockRejectedValue({ response: { data: { detail: "Reset token has expired." } } } as never);
    renderPage();
    await user.type(screen.getByLabelText("New password"), "ValidPass123!");
    await user.type(screen.getByLabelText("Confirm new password"), "ValidPass123!");
    await user.click(screen.getByRole("button", { name: "Reset password" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Reset token has expired.");
  });
});