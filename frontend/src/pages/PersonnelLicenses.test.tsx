import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import api from "../api/client";
import { ToastProvider } from "../components/ui/Toast";
import PersonnelLicenses from "./PersonnelLicenses";

vi.mock("../api/client", () => ({ default: { get: vi.fn(), post: vi.fn() } }));
// The renewal-progress modal fetches on its own; stub it so this page is tested in isolation.
vi.mock("../components/ui/modals/RenewalProgressModal", () => ({ RenewalProgressModal: () => null }));

const licenses = [
  { license_id: "LIC-1", person_id: "u-safety/pilot", license_type: "ATPL", license_number: "KFL-001", issuing_authority: "KCAA", expiry_date: "2027-06-01", status: "valid" },
  { license_id: "LIC-2", person_id: "u-safety/engineer", license_type: "medical_certificate", license_number: "", issuing_authority: "KCAA", expiry_date: "2026-01-01", status: "expired" },
];
const expiring = [{ license_id: "LIC-3", license_type: "ATPL", person_id: "u-safety/pilot2", expiry_date: "2026-12-01" }];

function renderPage(lic: typeof licenses = licenses, exp: typeof expiring = []) {
  vi.mocked(api.get).mockImplementation((url: string) => {
    if (url.includes("expiring-licenses")) return Promise.resolve({ data: exp });
    if (url.includes("/p2/personnel/licenses")) return Promise.resolve({ data: lic });
    return Promise.resolve({ data: [] });
  });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <PersonnelLicenses />
      </ToastProvider>
    </QueryClientProvider>,
  );
}

beforeEach(() => { vi.clearAllMocks(); });

describe("PersonnelLicenses", () => {
  it("shows an expiring-soon alert listing the affected credential", async () => {
    renderPage(licenses, expiring);
    expect(await screen.findByText(/1 License\(s\) Expiring Soon/)).toBeInTheDocument();
    expect(screen.getByText(/u-safety\/pilot2/)).toBeInTheDocument();
  });

  it("lists licenses with humanised type, authority, and a dash for a missing number", async () => {
    renderPage();
    expect(await screen.findByRole("heading", { name: "Personnel Licenses" })).toBeInTheDocument();
    await screen.findByText("u-safety/pilot");
    expect(screen.getByText("u-safety/engineer")).toBeInTheDocument();
    // Underscores in the license type are rendered as spaces.
    expect(screen.getByText("medical certificate")).toBeInTheDocument();
    expect(screen.getAllByText("KCAA")).toHaveLength(2);
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("shows the empty state when there are no licenses", async () => {
    renderPage([], []);
    expect(await screen.findByText("No licenses found.")).toBeInTheDocument();
  });
});