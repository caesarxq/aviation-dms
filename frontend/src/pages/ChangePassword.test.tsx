import ChangePasswordPage from "./ChangePassword";
import api from "../api/client";
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("../api/client", () => ({ default: { get: vi.fn(), post: vi.fn() } }));

function CurrentPath() {
  const location = useLocation();
  return <output data-testid="current-path">{location.pathname}</output>;
}

afterEach(() => vi.restoreAllMocks());

describe("ChangePasswordPage", () => {
  it("keeps the success confirmation visible after a successful change", async () => {
    vi.mocked(api.post).mockResolvedValue({ data: { message: "Password changed" } } as any);
    render(
      <MemoryRouter initialEntries={["/account/security"]}>
        <CurrentPath />
        <Routes>
          <Route path="/account/security" element={<ChangePasswordPage />} />
          <Route path="/" element={<div data-testid="dashboard-screen">Dashboard</div>} />
        </Routes>
      </MemoryRouter>
    );

    await userEvent.type(screen.getByLabelText("Current password"), "Current-Test-Password-2026!");
    await userEvent.type(screen.getByLabelText("New password"), "New-Test-Password-2026!");
    await userEvent.type(screen.getByLabelText("Confirm new password"), "New-Test-Password-2026!");
    fireEvent.click(screen.getByRole("button", { name: "Change password" }));

    expect(await screen.findByText(/password changed/i)).toBeInTheDocument();
    expect(screen.getByTestId("current-path")).toHaveTextContent("/account/security");
    expect(screen.queryByTestId("dashboard-screen")).not.toBeInTheDocument();
  });
});
