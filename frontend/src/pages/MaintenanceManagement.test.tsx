import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { safetyApi } from "../api/safety";
import { ToastProvider } from "../components/ui/Toast";
import { MaintenanceManagement } from "./MaintenanceManagement";

vi.mock("../api/safety", () => ({
  safetyApi: { listMaintenanceRecords: vi.fn(), createMaintenanceRecord: vi.fn(), updateMaintenanceRecord: vi.fn(), deleteMaintenanceRecord: vi.fn() },
}));

const records = [
  { record_id: "MX-1", aircraft_registration: "5Y-KFL", maintenance_type: "A-check", description: "d", status: "completed" },
  { record_id: "MX-2", aircraft_registration: "5Y-KFL", maintenance_type: "B-check", description: "d", status: "pending" },
  { record_id: "MX-3", aircraft_registration: "5Y-ABC", maintenance_type: "C-check", description: "d", status: "overdue" },
];

function statValue(label: string) {
  const el = screen.getAllByText(label).find((n) => n.classList.contains("app-label"));
  return el!.nextElementSibling as HTMLElement;
}

function renderPage(items: typeof records = records) {
  vi.mocked(safetyApi.listMaintenanceRecords).mockResolvedValue(items as never);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <MaintenanceManagement />
      </ToastProvider>
    </QueryClientProvider>,
  );
}

beforeEach(() => { vi.clearAllMocks(); });

describe("MaintenanceManagement", () => {
  it("computes total/completed/pending-overdue stats and lists the records", async () => {
    renderPage();
    await screen.findByText("MX-1");
    expect(statValue("Total Records")).toHaveTextContent("3");
    expect(statValue("Completed")).toHaveTextContent("1");
    expect(statValue("Pending / Overdue")).toHaveTextContent("2");
    expect(screen.getByText("A-check")).toBeInTheDocument();
  });

  it("refetches with the aircraft-registration filter applied", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("MX-1");
    await user.type(screen.getByPlaceholderText("Aircraft registration"), "5Y-KFL");
    await waitFor(() => expect(safetyApi.listMaintenanceRecords).toHaveBeenCalledWith({ aircraft_registration: "5Y-KFL", status: undefined }));
  });

  it("shows the empty state when there are no maintenance records", async () => {
    renderPage([]);
    expect(await screen.findByText("No maintenance records found.")).toBeInTheDocument();
    expect(statValue("Total Records")).toHaveTextContent("0");
  });
});