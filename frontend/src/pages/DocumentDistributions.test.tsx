import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { p2Api } from "../api/p2";
import { ToastProvider } from "../components/ui/Toast";
import { DocumentDistributions } from "./DocumentDistributions";

vi.mock("../api/p2", () => ({
  p2Api: { listDistributions: vi.fn(), createDistribution: vi.fn(), acknowledgeDistribution: vi.fn() },
}));

const distributions = [
  { distribution_id: "DIST-1", version_id: "V-1", recipient_id: "u-safety", channel: "email", status: "pending", acknowledged_at: null },
  { distribution_id: "DIST-2", version_id: "V-2", recipient_id: "u-librarian", channel: "email", status: "acknowledged", acknowledged_at: "2026-11-01T08:00" },
];

function statValue(label: string) {
  const el = screen.getAllByText(label).find((n) => n.classList.contains("app-label"));
  return el!.nextElementSibling as HTMLElement;
}

function renderPage(items: typeof distributions = distributions) {
  vi.mocked(p2Api.listDistributions).mockResolvedValue(items as never);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <DocumentDistributions />
      </ToastProvider>
    </QueryClientProvider>,
  );
}

beforeEach(() => { vi.clearAllMocks(); });

describe("DocumentDistributions", () => {
  it("computes pending/acknowledged stats and lists the distributions", async () => {
    renderPage();
    await screen.findByText("DIST-1");
    expect(statValue("Pending Acknowledgement")).toHaveTextContent("1");
    expect(statValue("Acknowledged")).toHaveTextContent("1");
    expect(screen.getByText("u-safety")).toBeInTheDocument();
    expect(screen.getByText("V-1")).toBeInTheDocument();
  });

  it("acknowledges a pending distribution via the API", async () => {
    const user = userEvent.setup();
    vi.mocked(p2Api.acknowledgeDistribution).mockResolvedValue({} as never);
    renderPage();
    await screen.findByText("DIST-1");
    // Only the pending distribution offers an acknowledge action.
    expect(screen.getAllByRole("button", { name: /Acknowledge/ })).toHaveLength(1);
    await user.click(document.querySelector("#ack_DIST-1") as HTMLElement);
    await waitFor(() => expect(p2Api.acknowledgeDistribution).toHaveBeenCalledWith("DIST-1"));
  });

  it("shows the empty state when there are no distributions", async () => {
    renderPage([]);
    expect(await screen.findByText("No distributions recorded.")).toBeInTheDocument();
  });
});