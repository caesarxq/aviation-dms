import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import api from "../api/client";
import { ToastProvider } from "../components/ui/Toast";
import { BulkRoleInvite } from "./BulkRoleInvite";

vi.mock("../api/client", () => ({
  default: { post: vi.fn().mockResolvedValue({ data: { created_count: 1, role: "flight_ops_officer" } }) },
}));

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <BulkRoleInvite />
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("BulkRoleInvite", () => {
  beforeEach(() => vi.clearAllMocks());

  it("posts to the client base URL without duplicating the API prefix", async () => {
    const user = userEvent.setup();
    renderPage();
    await user.click(screen.getByRole("button", { name: /invite multiple users/i }));
    await user.click(screen.getByRole("combobox"));
    await user.click(screen.getByRole("option", { name: /Flight Operations Officer/ }));
    await user.type(screen.getByPlaceholderText("user@example.com"), "pilot@example.com");
    await user.click(screen.getByRole("button", { name: "Send Invitations" }));

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith("/p0/auth/invites/role", {
        role: "flight_ops_officer",
        emails: ["pilot@example.com"],
      });
    });
  });
});
