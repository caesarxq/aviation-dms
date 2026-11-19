import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { safetyApi } from "../api/safety";
import { ToastProvider } from "../components/ui/Toast";
import { Hazards } from "./Hazards";

vi.mock("../api/safety", () => ({
  safetyApi: { listHazards: vi.fn(), createHazard: vi.fn(), updateHazard: vi.fn() },
}));

const hazards = [
  { hazard_id: "HAZ-1", title: "Bird strike risk", description: "Wildlife near runway", category: "wildlife", risk_level: "high", status: "identified" },
  { hazard_id: "HAZ-2", title: "Fatigue", description: "Crew fatigue", category: "human", risk_level: "medium", status: "mitigated" },
  { hazard_id: "HAZ-3", title: "Old hazard", description: "Resolved", category: "ops", risk_level: "low", status: "closed" },
];

function statValue(label: string) {
  return screen.getByText(label).nextElementSibling as HTMLElement;
}

function renderPage(items: typeof hazards = hazards) {
  vi.mocked(safetyApi.listHazards).mockResolvedValue(items as never);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <Hazards />
      </ToastProvider>
    </QueryClientProvider>,
  );
}

beforeEach(() => { vi.clearAllMocks(); });

describe("Hazards", () => {
  it("computes total, open/identified, high/critical risk, and mitigated/closed stats", async () => {
    renderPage();
    await screen.findByText("HAZ-1");
    expect(statValue("Total Hazards")).toHaveTextContent("3");
    expect(statValue("Open / Identified")).toHaveTextContent("1");
    expect(statValue("High / Critical Risk")).toHaveTextContent("1");
    expect(statValue("Mitigated / Closed")).toHaveTextContent("2");
  });

  it("shows zeroed stats and the empty state when there are no hazards", async () => {
    renderPage([]);
    expect(await screen.findByText("No hazards recorded.")).toBeInTheDocument();
    expect(statValue("Total Hazards")).toHaveTextContent("0");
    expect(statValue("Open / Identified")).toHaveTextContent("0");
  });
});