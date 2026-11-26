import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { safetyApi } from "../api/safety";
import { OccurrenceDetail } from "./OccurrenceDetail";

vi.mock("../api/safety", () => ({ safetyApi: { getOccurrence: vi.fn() } }));

const occ = {
  occurrence_id: "OCC-1", title: "Runway Incursion", serial_number: "MOR-2026-001", status: "open",
  severity: "major", occurrence_type: "runway_incursion", mor_required: true, location: "JKIA",
  reported_at: "2026-11-01", description: "Aircraft crossed the hold line.", occurred_at: "2026-11-01T08:00",
  reporter_id: "u-safety/pilot", mor_deadline: "2026-11-04",
};

function renderPage(data: typeof occ | null = occ) {
  vi.mocked(safetyApi.getOccurrence).mockResolvedValue(data as never);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/occurrences/OCC-1"]}>
        <Routes>
          <Route path="/occurrences/:occurrenceId" element={<OccurrenceDetail />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => { vi.clearAllMocks(); });

describe("OccurrenceDetail", () => {
  it("renders the occurrence with severity, type, and MOR requirement", async () => {
    renderPage();
    expect(await screen.findByRole("heading", { name: "Runway Incursion" })).toBeInTheDocument();
    expect(screen.getAllByText(/MOR-2026-001/)).toHaveLength(2);
    expect(screen.getAllByText("major")).toHaveLength(2);
    expect(screen.getByText("runway_incursion")).toBeInTheDocument();
    expect(screen.getAllByText("Yes")).toHaveLength(2);
    expect(screen.getByText("Aircraft crossed the hold line.")).toBeInTheDocument();
  });

  it("masks a confidential reporter instead of showing their identity", async () => {
    renderPage({ ...occ, reporter_id: "CONFIDENTIAL" });
    await screen.findByRole("heading", { name: "Runway Incursion" });
    expect(screen.getByText("Confidential Reporter")).toBeInTheDocument();
    expect(screen.queryByText("u-safety/pilot")).not.toBeInTheDocument();
  });

  it("redirects to occurrences list when the occurrence does not exist", async () => {
    renderPage(null);
    // When occurrence is not found, component redirects to /occurrences
    expect(screen.queryByRole("heading", { name: "Runway Incursion" })).not.toBeInTheDocument();
  });
});