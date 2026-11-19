import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { safetyApi } from "../api/safety";
import { ToastProvider } from "../components/ui/Toast";
import { CrewQualifications } from "./CrewQualifications";

vi.mock("../api/safety", () => ({
  safetyApi: {
    listCrewQualifications: vi.fn(),
    listCrewMembers: vi.fn(),
    createCrewQualification: vi.fn(),
    updateCrewQualification: vi.fn(),
    deleteCrewQualification: vi.fn(),
  },
}));

const crewList = [{ crew_id: "CRW-1", full_name: "Amina Pilot", role: "pilot", base: "Nairobi", status: "active" }];
const quals = [
  { qual_id: "QUAL-1", crew_id: "CRW-1", qual_type: "ATPL", rating: "B737", issue_date: "2025-01-01", expiry_date: "2027-01-01", status: "valid", notes: "" },
  { qual_id: "QUAL-2", crew_id: "CRW-1", qual_type: "Medical", rating: "", issue_date: "2025-01-01", expiry_date: "2026-01-01", status: "expired", notes: "" },
];

function renderPage(items: typeof quals = quals) {
  vi.mocked(safetyApi.listCrewQualifications).mockResolvedValue(items as never);
  vi.mocked(safetyApi.listCrewMembers).mockResolvedValue(crewList as never);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <CrewQualifications />
      </ToastProvider>
    </QueryClientProvider>,
  );
}

beforeEach(() => { vi.clearAllMocks(); });

describe("CrewQualifications", () => {
  it("renders qualifications with resolved crew names and currency status badges", async () => {
    renderPage();
    expect(screen.getByRole("heading", { name: "Crew Qualifications" })).toBeInTheDocument();
    await screen.findByText("QUAL-1");
    expect(screen.getAllByText("Amina Pilot")).toHaveLength(2);
    expect(screen.getByText("ATPL")).toBeInTheDocument();
    expect(screen.getByText("B737")).toBeInTheDocument();
    // Currency status badges for a valid and an expired qualification.
    expect(screen.getByText("valid")).toBeInTheDocument();
    expect(screen.getByText("expired")).toBeInTheDocument();
    // Empty rating renders as a dash.
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("shows the empty state when there are no qualifications", async () => {
    renderPage([]);
    expect(await screen.findByText(/Add qualifications to track expiry and currency/)).toBeInTheDocument();
  });

  it("prefills the edit form and saves the qualification update", async () => {
    const user = userEvent.setup();
    vi.mocked(safetyApi.updateCrewQualification).mockResolvedValue({} as never);
    renderPage();
    await screen.findByText("QUAL-1");
    await user.click(document.querySelector("#edit_qual_QUAL-1") as HTMLElement);
    expect(await screen.findByRole("heading", { name: "Edit Qualification" })).toBeInTheDocument();
    expect(document.querySelector("#qual_type")).toHaveValue("ATPL");
    await user.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(safetyApi.updateCrewQualification).toHaveBeenCalledWith("QUAL-1", expect.objectContaining({ qual_type: "ATPL", rating: "B737", expiry_date: "2027-01-01" })));
  });
});