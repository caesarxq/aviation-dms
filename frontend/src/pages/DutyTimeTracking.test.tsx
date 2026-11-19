import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { safetyApi } from "../api/safety";
import { ToastProvider } from "../components/ui/Toast";
import { DutyTimeTracking } from "./DutyTimeTracking";

vi.mock("../api/safety", () => ({
  safetyApi: {
    listDutyRecords: vi.fn(),
    listCrewMembers: vi.fn(),
    createDutyRecord: vi.fn(),
    updateDutyRecord: vi.fn(),
    deleteDutyRecord: vi.fn(),
  },
}));

const crewList = [{ crew_id: "CRW-1", full_name: "Amina Pilot", role: "pilot", base: "Nairobi", status: "active" }];
const duties = [
  { duty_id: "DUTY-1", crew_id: "CRW-1", duty_start: "2026-11-01T08:00", duty_end: "2026-11-01T16:00", aircraft_reg: "5Y-KFL", block_hours: 2.5, role: "pilot", location: "Nairobi", notes: "" },
  { duty_id: "DUTY-2", crew_id: "CRW-1", duty_start: "2026-11-02T08:00", duty_end: "2026-11-02T12:00", aircraft_reg: "", block_hours: null, role: "pilot", location: "", notes: "" },
];

function renderPage(dutyItems: typeof duties = duties) {
  vi.mocked(safetyApi.listDutyRecords).mockResolvedValue(dutyItems as never);
  vi.mocked(safetyApi.listCrewMembers).mockResolvedValue(crewList as never);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <DutyTimeTracking />
      </ToastProvider>
    </QueryClientProvider>,
  );
}

beforeEach(() => { vi.clearAllMocks(); });

describe("DutyTimeTracking", () => {
  it("resolves crew names and formats block hours, showing a dash for missing hours", async () => {
    renderPage();
    expect(screen.getByRole("heading", { name: "Duty Time Tracking" })).toBeInTheDocument();
    await screen.findByText("DUTY-1");
    // Crew name resolved from the crew directory (both rows).
    expect(screen.getAllByText("Amina Pilot")).toHaveLength(2);
    expect(screen.getByText("2.5h")).toBeInTheDocument();
    // DUTY-2 shows a dash for both empty aircraft registration and null block hours.
    expect(screen.getAllByText("—")).toHaveLength(2);
  });

  it("shows the empty state when there are no duty records", async () => {
    renderPage([]);
    expect(await screen.findByText("No duty records found.")).toBeInTheDocument();
  });

  it("prefills the edit form from the duty record and saves the update", async () => {
    const user = userEvent.setup();
    vi.mocked(safetyApi.updateDutyRecord).mockResolvedValue({} as never);
    renderPage();
    await screen.findByText("DUTY-1");
    await user.click(document.querySelector("#edit_duty_DUTY-1") as HTMLElement);
    expect(await screen.findByRole("heading", { name: "Edit Duty Record" })).toBeInTheDocument();
    expect(document.querySelector("#duty_start")).toHaveValue("2026-11-01T08:00");
    expect(document.querySelector("#duty_block_hours")).toHaveValue(2.5);
    await user.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(safetyApi.updateDutyRecord).toHaveBeenCalledWith("DUTY-1", expect.objectContaining({ crew_id: "CRW-1", duty_start: "2026-11-01T08:00", block_hours: "2.5" })));
  });
});