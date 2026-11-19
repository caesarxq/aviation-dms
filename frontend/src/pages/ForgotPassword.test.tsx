import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import api from "../api/client";
import { ForgotPasswordPage } from "./ForgotPassword";

vi.mock("../api/client", () => ({ default: { post: vi.fn() } }));

function renderPage() {
  return render(
    <MemoryRouter>
      <ForgotPasswordPage />
    </MemoryRouter>,
  );
}

beforeEach(() => { vi.clearAllMocks(); });

describe("ForgotPasswordPage", () => {
  it("renders the username form and keeps submit disabled until a username is entered", () => {
    renderPage();
    expect(screen.getByRole("heading", { name: "Forgot password" })).toBeInTheDocument();
    expect(screen.getByLabelText("Assigned username")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Request reset" })).toBeDisabled();
  });

  it("requests a reset and shows a generic anti-enumeration confirmation", async () => {
    const user = userEvent.setup();
    vi.mocked(api.post).mockResolvedValue({ data: {} } as never);
    renderPage();
    await user.type(screen.getByLabelText("Assigned username"), "  librarian  ");
    await user.click(screen.getByRole("button", { name: "Request reset" }));
    await waitFor(() => expect(api.post).toHaveBeenCalledWith("/p0/auth/forgot-password", { username: "librarian" }));
    // The confirmation must not reveal whether the account exists.
    expect(await screen.findByRole("status")).toHaveTextContent(/If an active account/i);
  });

  it("surfaces a server error as an alert without claiming success", async () => {
    const user = userEvent.setup();
    vi.mocked(api.post).mockRejectedValue({ response: { data: { detail: "Rate limited. Try again shortly." } } } as never);
    renderPage();
    await user.type(screen.getByLabelText("Assigned username"), "librarian");
    await user.click(screen.getByRole("button", { name: "Request reset" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Rate limited. Try again shortly.");
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });
});