import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { safetyApi } from "../api/safety";
import { ToastProvider } from "../components/ui/Toast";
import { Notifications } from "./Notifications";

vi.mock("../api/safety", () => ({
  safetyApi: {
    listNotifications: vi.fn(),
    getNotificationPreferences: vi.fn(),
    updateNotificationPreferences: vi.fn(),
    markNotificationRead: vi.fn(),
  },
}));

const notifications = [
  { notification_id: "N-1", subject: "MOR deadline approaching", body: "Submit the MOR within 24h.", recipient: "u-safety", status: "sent", priority: "high", created_at: "2026-11-01", entity_type: "occurrence", entity_id: "OCC-1" },
  { notification_id: "N-2", subject: "Already read notice", body: "Seen.", recipient: "u-librarian", status: "read", priority: "low", created_at: "2026-11-01" },
];

function renderPage(items: typeof notifications = notifications) {
  vi.mocked(safetyApi.listNotifications).mockResolvedValue({ notifications: items } as never);
  vi.mocked(safetyApi.getNotificationPreferences).mockResolvedValue({} as never);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <Notifications />
      </ToastProvider>
    </QueryClientProvider>,
  );
}

beforeEach(() => { vi.clearAllMocks(); });

describe("Notifications", () => {
  it("lists notifications and only offers mark-read on unread ones", async () => {
    renderPage();
    expect(screen.getByRole("heading", { name: "Notifications" })).toBeInTheDocument();
    await screen.findByText("MOR deadline approaching");
    expect(screen.getByText("Submit the MOR within 24h.")).toBeInTheDocument();
    // Only the unread notification gets a mark-read action.
    expect(screen.getAllByRole("button", { name: /Mark read/ })).toHaveLength(1);
  });

  it("marks a notification read via the API", async () => {
    const user = userEvent.setup();
    vi.mocked(safetyApi.markNotificationRead).mockResolvedValue({} as never);
    renderPage();
    await screen.findByText("MOR deadline approaching");
    await user.click(screen.getByRole("button", { name: /Mark read/ }));
    await waitFor(() => expect(safetyApi.markNotificationRead).toHaveBeenCalledWith("N-1"));
  });

  it("shows the empty state when there are no notifications", async () => {
    renderPage([]);
    expect(await screen.findByText("No notifications in this view.")).toBeInTheDocument();
  });
});