import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import api from "../api/client";
import { ToastProvider } from "../components/ui/Toast";
import { RenewalProgress } from "./RenewalProgress";

vi.mock("../api/client", () => ({ default: { get: vi.fn(), post: vi.fn() } }));

const licenses = [
  { license_id: "LIC-1", person_id: "u-1", license_type: "ATPL", license_number: "K-1", issuing_authority: "KCAA", status: "valid", expiry_date: "2027-06-01" },
  { license_id: "LIC-2", person_id: "u-2", license_type: "Medical", license_number: "K-2", issuing_authority: "KCAA", status: "valid", expiry_date: "2027-01-01" },
  { license_id: "LIC-3", person_id: "u-3", license_type: "Rating", license_number: "K-3", issuing_authority: "KCAA", status: "expired", expiry_date: "2026-01-01" },
];
const expiringLic = [{ license_id: "LIC-4", person_id: "u-4", license_type: "ATPL", expiry_date: "2026-12-01", status: "expiring_soon" }];

function statValue(label: string) {
  const el = screen.getAllByText(label).find((n) => n.classList.contains("app-label"));
  return el!.nextElementSibling as HTMLElement;
}

function renderPage(lic: typeof licenses = licenses, exp: typeof expiringLic = expiringLic) {
  vi.mocked(api.get).mockImplementation((url: string) => {
    if (url.includes("/p2/personnel/expiring-licenses")) return Promise.resolve({ data: exp });
    if (url.includes("/p2/personnel/licenses")) return Promise.resolve({ data: lic });
    if (url.includes("/p2/insurance/expiring")) return Promise.resolve({ data: [] });
    if (url.includes("/p1/aircraft")) return Promise.resolve({ data: [] });
    return Promise.resolve({ data: [] });
  });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <RenewalProgress />
      </ToastProvider>
    </QueryClientProvider>,
  );
}

beforeEach(() => { vi.clearAllMocks(); });

describe("RenewalProgress", () => {
  it("computes total, expiring-90d, and expired license stats", async () => {
    renderPage();
    expect(screen.getByRole("heading", { name: "Renewal Progress" })).toBeInTheDocument();
    await screen.findByText("u-1");
    expect(statValue("Total Licenses")).toHaveTextContent("3");
    expect(statValue("Expiring (90d)")).toHaveTextContent("1");
    expect(statValue("Expired")).toHaveTextContent("1");
  });

  it("shows the empty state when there are no personnel licenses", async () => {
    renderPage([], []);
    expect(await screen.findByText("No personnel licenses on record.")).toBeInTheDocument();
    expect(statValue("Total Licenses")).toHaveTextContent("0");
  });
});