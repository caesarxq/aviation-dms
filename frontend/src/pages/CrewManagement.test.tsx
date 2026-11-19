import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { safetyApi } from "../api/safety";
import { ToastProvider } from "../components/ui/Toast";
import { CrewManagement } from "./CrewManagement";

vi.mock("../api/safety", () => ({
  safetyApi: {
    listCrewMembers: vi.fn(),
    createCrewMember: vi.fn(),
    updateCrewMember: vi.fn(),
    deleteCrewMember: vi.fn(),
  },
}));

const crew = [
  { crew_id: "CRW-1", full_name: "Amina Pilot", role: "pilot", base: "Nairobi", status: "active" },
  { crew_id: "CRW-2", full_name: "Brian Engineer", role: "engineer", base: "Wilson", status: "inactive" },
];

function renderPage(items: typeof crew = crew) {
  vi.mocked(safetyApi.listCrewMembers).mockResolvedValue(items as never);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <CrewManagement />
      </ToastProvider>
    </QueryClientProvider>,
  );
}

beforeEach(() => { vi.clearAllMocks(); });

describe("CrewManagement", () => {
  it("renders the crew directory with name, role, and status", async () => {
    renderPage();
    expect(screen.getByRole("heading", { name: "Crew Management" })).toBeInTheDocument();
    await screen.findByText("Amina Pilot");
    expect(screen.getByText("Brian Engineer")).toBeInTheDocument();
    expect(screen.getByText("pilot")).toBeInTheDocument();
    expect(screen.getByText("inactive")).toBeInTheDocument();
  });

  it("shows the empty state when there are no crew members", async () => {
    renderPage([]);
    expect(await screen.findByText("No crew members found.")).toBeInTheDocument();
  });

  it("refetches with the role filter applied", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("Amina Pilot");
    await user.type(screen.getByPlaceholderText("Filter by role"), "pilot");
    await waitFor(() => expect(safetyApi.listCrewMembers).toHaveBeenCalledWith({ role: "pilot", status: undefined }));
  });

  it("creates a crew member with the entered details", async () => {
    const user = userEvent.setup();
    vi.mocked(safetyApi.createCrewMember).mockResolvedValue({ crew_id: "CRW-NEW" } as never);
    renderPage();
    await screen.findByText("Amina Pilot");
    await user.click(screen.getByRole("button", { name: /Add Crew/ }));
    expect(await screen.findByRole("heading", { name: "New Crew Member" })).toBeInTheDocument();
    // Submit stays disabled until name and role are present.
    expect(screen.getByRole("button", { name: "Create" })).toBeDisabled();
    await user.type(document.querySelector("#crew_full_name") as HTMLElement, "New Crew");
    await user.type(document.querySelector("#crew_role") as HTMLElement, "pilot");
    await user.click(screen.getByRole("button", { name: "Create" }));
    await waitFor(() => expect(safetyApi.createCrewMember).toHaveBeenCalledWith(expect.objectContaining({ full_name: "New Crew", role: "pilot", base: "Nairobi", status: "active" })));
  });

  it("prefills the edit form and saves updates to the existing crew member", async () => {
    const user = userEvent.setup();
    vi.mocked(safetyApi.updateCrewMember).mockResolvedValue({} as never);
    renderPage();
    await screen.findByText("Amina Pilot");
    await user.click(document.querySelector("#edit_crew_CRW-1") as HTMLElement);
    expect(await screen.findByRole("heading", { name: "Edit Crew Member" })).toBeInTheDocument();
    expect(document.querySelector("#crew_full_name")).toHaveValue("Amina Pilot");
    await user.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(safetyApi.updateCrewMember).toHaveBeenCalledWith("CRW-1", expect.objectContaining({ full_name: "Amina Pilot", role: "pilot" })));
  });
});