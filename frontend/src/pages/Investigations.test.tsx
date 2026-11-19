import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { safetyApi } from "../api/safety";
import { ToastProvider } from "../components/ui/Toast";
import { Investigations } from "./Investigations";

vi.mock("../api/safety", () => ({
  safetyApi: { listInvestigations: vi.fn(), createInvestigation: vi.fn(), updateInvestigation: vi.fn() },
}));

const investigations = [
  { investigation_id: "INV-1", title: "Incursion investigation", description: "d", status: "open", occurrence_id: "OCC-1" },
  { investigation_id: "INV-2", title: "Bird strike investigation", description: "d", status: "in_progress", occurrence_id: "OCC-2" },
  { investigation_id: "INV-3", title: "Closed investigation", description: "d", status: "completed", occurrence_id: "OCC-3" },
];

function statValue(label: string) {
  return screen.getByText(label).nextElementSibling as HTMLElement;
}

function renderPage(items: typeof investigations = investigations) {
  vi.mocked(safetyApi.listInvestigations).mockResolvedValue(items as never);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <Investigations />
      </ToastProvider>
    </QueryClientProvider>,
  );
}

beforeEach(() => { vi.clearAllMocks(); });

describe("Investigations", () => {
  it("computes total, open, in-progress, and completed stats", async () => {
    renderPage();
    await screen.findByText("INV-1");
    expect(statValue("Total Investigations")).toHaveTextContent("3");
    expect(statValue("Open")).toHaveTextContent("1");
    expect(statValue("In Progress")).toHaveTextContent("1");
    expect(statValue("Completed")).toHaveTextContent("1");
  });

  it("shows zeroed stats and the empty state when there are no investigations", async () => {
    renderPage([]);
    expect(await screen.findByText("No investigations recorded.")).toBeInTheDocument();
    expect(statValue("Open")).toHaveTextContent("0");
    expect(statValue("Completed")).toHaveTextContent("0");
  });
});