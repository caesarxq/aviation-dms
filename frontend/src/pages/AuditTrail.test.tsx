import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { safetyApi } from "../api/safety";
import { AuditTrail } from "./AuditTrail";

vi.mock("../api/safety", () => ({ safetyApi: { listAuditEvents: vi.fn() } }));

const now = new Date().toISOString();
const events = [
  { event_id: "EVT-1", entity_type: "audit_finding", entity_id: "FIND-001", action: "created", actor_id: "u-head-quality", timestamp: now, details: "New finding" },
  { event_id: "EVT-2", entity_type: "corrective_action", entity_id: "CAR-1", action: "closed", actor_id: "u-head-safety", timestamp: now, details: "" },
  { event_id: "EVT-3", entity_type: "risk_assessment", entity_id: "RA-1", action: "submitted", actor_id: "u-head-operations", timestamp: now, details: "" },
];

function renderPage(items: typeof events = events) {
  vi.mocked(safetyApi.listAuditEvents).mockResolvedValue(items as never);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <AuditTrail />
    </QueryClientProvider>,
  );
}

beforeEach(() => { vi.clearAllMocks(); });

describe("AuditTrail", () => {
  it("renders aviation audit trail heading", async () => {
    renderPage();
    expect(screen.getByRole("heading", { name: "Aviation Audit Trail" })).toBeInTheDocument();
  });

  it("renders aviation audit events with action badges", async () => {
    renderPage();
    await screen.findByText("EVT-1");
    expect(screen.getByText("created")).toBeInTheDocument();
    expect(screen.getByText("closed")).toBeInTheDocument();
    expect(screen.getByText("submitted")).toBeInTheDocument();
    expect(screen.getByText("u-head-quality")).toBeInTheDocument();
    expect(screen.getByText("u-head-safety")).toBeInTheDocument();
    expect(screen.getByText("u-head-operations")).toBeInTheDocument();
    // Empty details render as N/A (2 events have empty details).
    expect(screen.getAllByText("N/A")).toHaveLength(2);
  });

  it("filters aviation audit events by entity type", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("EVT-1");
    await user.type(screen.getByPlaceholderText("Entity type (e.g. audit_finding)"), "audit_finding");
    await waitFor(() => expect(safetyApi.listAuditEvents).toHaveBeenLastCalledWith({ entity_type: "audit_finding", entity_id: undefined, limit: 100 }));
  });

  it("shows the empty state when there are no aviation audit events", async () => {
    renderPage([]);
    expect(await screen.findByText("No aviation audit events found.")).toBeInTheDocument();
  });
});
