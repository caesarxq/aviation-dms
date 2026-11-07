import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { safetyApi } from "../api/safety";
import { OrganizationOverview } from "./OrganizationOverview";

vi.mock("../api/safety", () => ({
  safetyApi: {
    getOrganizationOverview: vi.fn(),
  },
}));

const summary = {
  trends: {
    occurrences_by_type: { incident: 4 },
    occurrences_by_severity: { moderate: 4 },
    safety_actions_by_status: { open: 3, closed: 2 },
    hazards_by_risk_level: { high: 1 },
    occurrences_last_30_days: 4,
  },
  deadlines: {
    total: 2,
    overdue_count: 2,
    upcoming_count: 0,
    overdue: [
      { entity_type: "aircraft_insurance", entity_id: "INS-TEST-01", title: "Insurance expiry: hull - AC-TEST-01", due_date: "2026-11-01", priority: "critical" },
      { entity_type: "personnel_license", entity_id: "LIC-TEST-02", title: "License expiry: operator - person-2", due_date: "2026-11-02", priority: "high" },
    ],
    upcoming: [],
  },
  operations: {
    total: 8,
    planned: 2,
    released: 1,
    in_progress: 2,
    completed: 3,
    cancelled: 0,
    aborted: 0,
  },
  fleet: {
    total: 6,
    status_counts: { active: 4, grounded: 2 },
    opspec_authorized: 3,
    not_opspec_authorized: 3,
  },
};

function renderOverview() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/organization-overview"]}>
        <OrganizationOverview />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("Organization overview", () => {
  beforeEach(() => vi.mocked(safetyApi.getOrganizationOverview).mockReset());

  it("summarizes organization trends, operations, fleet, and data-driven follow-ups", async () => {
    vi.mocked(safetyApi.getOrganizationOverview).mockResolvedValue(summary);
    renderOverview();

    expect(await screen.findByRole("heading", { name: "Organization overview" })).toBeInTheDocument();
    expect(screen.getByText("Occurrences (last 30 days)")).toBeInTheDocument();
    expect(screen.getByText("Active operations")).toBeInTheDocument();
    expect(screen.getByText("Completed operations")).toBeInTheDocument();
    expect(screen.getByText("Fleet summary")).toBeInTheDocument();
    expect(screen.getByText("Review 2 overdue organization deadlines.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "View overdue records" })).toHaveAttribute("href", "/organization-overview#overdue-deadlines");
    expect(screen.getByText("Insurance expiry: hull - AC-TEST-01")).toBeInTheDocument();
    expect(screen.getByText(/Record: INS-TEST-01/)).toBeInTheDocument();
    expect(screen.getByText("Review the status of 2 operations currently in progress.")).toBeInTheDocument();
    expect(screen.getByText("Review 3 open safety actions and current owners.")).toBeInTheDocument();
  });

  it("shows an explicit NOTAM feed gap without implying an all-clear", async () => {
    vi.mocked(safetyApi.getOrganizationOverview).mockResolvedValue(summary);
    renderOverview();

    expect(await screen.findByRole("heading", { name: "NOTAMs" })).toBeInTheDocument();
    expect(screen.getByText(/No approved NOTAM data source is connected/i)).toBeInTheDocument();
    expect(screen.getByText(/not an indication that there are no NOTAMs/i)).toBeInTheDocument();
    expect(screen.queryByText(/No active NOTAMs/i)).not.toBeInTheDocument();
  });

  it("shows unavailable state rather than an empty organization summary on errors", async () => {
    vi.mocked(safetyApi.getOrganizationOverview).mockRejectedValueOnce(new Error("network"));
    renderOverview();

    expect(await screen.findByRole("alert")).toHaveTextContent("Unable to load organization overview data.");
    expect(screen.queryByText(/No deadlines require attention/i)).not.toBeInTheDocument();
  });

  it("lets the manager retry after overview data fails to load", async () => {
    const user = userEvent.setup();
    vi.mocked(safetyApi.getOrganizationOverview)
      .mockRejectedValueOnce(new Error("network"))
      .mockResolvedValueOnce(summary);
    renderOverview();

    expect(await screen.findByRole("alert")).toHaveTextContent("Unable to load organization overview data.");
    await user.click(screen.getByRole("button", { name: "Retry loading overview" }));

    expect(await screen.findByRole("heading", { name: "Organization overview" })).toBeInTheDocument();
    expect(safetyApi.getOrganizationOverview).toHaveBeenCalledTimes(2);
  });
});
