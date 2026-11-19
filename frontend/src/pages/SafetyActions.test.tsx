import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { safetyApi } from "../api/safety";
import { ToastProvider } from "../components/ui/Toast";
import { SafetyActions } from "./SafetyActions";

vi.mock("../api/safety", () => ({
  safetyApi: { listSafetyActions: vi.fn(), createSafetyAction: vi.fn(), updateSafetyAction: vi.fn() },
}));

const actions = [
  { action_id: "SA-1", title: "Install signage", description: "d", status: "open", hazard_id: "HAZ-1" },
  { action_id: "SA-2", title: "Update procedure", description: "d", status: "in_progress", hazard_id: "HAZ-1" },
  { action_id: "SA-3", title: "Training done", description: "d", status: "completed", hazard_id: "HAZ-2" },
  { action_id: "SA-4", title: "Verified fix", description: "d", status: "verified", hazard_id: "HAZ-2" },
];

function statValue(label: string) {
  return screen.getByText(label).nextElementSibling as HTMLElement;
}

function renderPage(items: typeof actions = actions) {
  vi.mocked(safetyApi.listSafetyActions).mockResolvedValue(items as never);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <SafetyActions />
      </ToastProvider>
    </QueryClientProvider>,
  );
}

beforeEach(() => { vi.clearAllMocks(); });

describe("SafetyActions", () => {
  it("counts completed and verified actions together in the closed stat", async () => {
    renderPage();
    await screen.findByText("SA-1");
    expect(statValue("Total Actions")).toHaveTextContent("4");
    expect(statValue("Open")).toHaveTextContent("1");
    expect(statValue("In Progress")).toHaveTextContent("1");
    expect(statValue("Completed / Verified")).toHaveTextContent("2");
  });

  it("shows zeroed stats and the empty state when there are no actions", async () => {
    renderPage([]);
    expect(await screen.findByText("No safety actions recorded.")).toBeInTheDocument();
    expect(statValue("Total Actions")).toHaveTextContent("0");
    expect(statValue("Completed / Verified")).toHaveTextContent("0");
  });
});