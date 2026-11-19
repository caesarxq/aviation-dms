import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { rocApi } from "../api/roc";
import { ROCRegister } from "./ROCRegister";

vi.mock("../api/roc", () => ({ rocApi: { listROC: vi.fn(), listAircraft: vi.fn() } }));

const rocs = [{ roc_number: "ROC-KFL-001", serial_number: "SN-001", expiry_date: "2027-12-31", bvlos_authorized: true, night_authorized: false }];
const aircraft = [{ aircraft_id: "AC-1", registration: "5Y-KFL", model: "DJI M300", serial_number: "SN-AC1", status: "active", category: "UAS" }];

function renderPage(fleet: typeof aircraft = aircraft) {
  vi.mocked(rocApi.listROC).mockResolvedValue(rocs as never);
  vi.mocked(rocApi.listAircraft).mockResolvedValue(fleet as never);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ROCRegister />
    </QueryClientProvider>,
  );
}

beforeEach(() => { vi.clearAllMocks(); });

describe("ROCRegister", () => {
  it("shows ROC details, authorization flags, and the registered fleet", async () => {
    renderPage();
    expect(screen.getByRole("heading", { name: "ROC & UAS Fleet" })).toBeInTheDocument();
    await screen.findByText("5Y-KFL");
    expect(screen.getByText("ROC-KFL-001")).toBeInTheDocument();
    expect(screen.getByText("Authorized")).toBeInTheDocument();
    expect(screen.getByText("Not Authorized")).toBeInTheDocument();
    expect(screen.getByText("DJI M300")).toBeInTheDocument();
    expect(screen.getByText("1 aircraft on record")).toBeInTheDocument();
  });

  it("shows the empty fleet state when no aircraft are registered", async () => {
    renderPage([]);
    expect(await screen.findByText("No aircraft registered.")).toBeInTheDocument();
    expect(screen.getByText("0 aircraft on record")).toBeInTheDocument();
  });
});