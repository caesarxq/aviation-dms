import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import api from "../api/client";
import { ToastProvider } from "../components/ui/Toast";
import { AircraftInsurance } from "./AircraftInsurance";

vi.mock("../api/client", () => ({ default: { get: vi.fn(), post: vi.fn() } }));

const expiringIns = [{ insurance_id: "INS-1", insurance_type: "Hull", registration: "5Y-KFL", expiry_date: "2026-12-01" }];

function renderPage(ins: typeof expiringIns = expiringIns, docs: never[] = []) {
  vi.mocked(api.get).mockImplementation((url: string) => {
    if (url.includes("/p2/insurance/expiring")) return Promise.resolve({ data: ins });
    if (url.includes("/p2/aircraft-documents/expiring")) return Promise.resolve({ data: docs });
    if (url.includes("/p1/aircraft")) return Promise.resolve({ data: [{ aircraft_id: "AC-1", registration: "5Y-KFL" }] });
    return Promise.resolve({ data: [] });
  });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <AircraftInsurance />
      </ToastProvider>
    </QueryClientProvider>,
  );
}

beforeEach(() => { vi.clearAllMocks(); });

describe("AircraftInsurance", () => {
  it("raises an expiring-soon alert for insurance nearing expiry", async () => {
    renderPage();
    expect(await screen.findByText("Expiring Soon")).toBeInTheDocument();
    expect(screen.getByText(/Insurance: Hull/)).toBeInTheDocument();
    expect(screen.getAllByText(/5Y-KFL/).length).toBeGreaterThan(0);
  });

  it("shows no expiring alert when nothing is nearing expiry", async () => {
    renderPage([], []);
    await screen.findByText("Select Aircraft");
    expect(screen.queryByText("Expiring Soon")).not.toBeInTheDocument();
  });
});