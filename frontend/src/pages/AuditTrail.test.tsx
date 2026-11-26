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
  { event_id: "EVT-2", entity_type: "document", entity_id: "DOC-002", action: "deleted", actor_id: "u-admin", timestamp: now, details: "" },
  { event_id: "EVT-3", entity_type: "corrective_action", entity_id: "CAR-1", action: "closed", actor_id: "u-head-safety", timestamp: now, details: "" },
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
  it("renders system audit tab by default", async () => {
    renderPage();
    expect(screen.getByRole("heading", { name: "Audit Trail" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /System Audit/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Aviation Audits/ })).toBeInTheDocument();
    // System tab is active by default
    expect(screen.getByText(/System administrator only/)).toBeInTheDocument();
  });

  it("renders audit events with action badges in system tab", async () => {
    renderPage();
    await screen.findByText("EVT-1");
    expect(screen.getByText("created")).toBeInTheDocument();
    expect(screen.getByText("deleted")).toBeInTheDocument();
    expect(screen.getByText("closed")).toBeInTheDocument();
    expect(screen.getByText("u-head-quality")).toBeInTheDocument();
    expect(screen.getByText("u-admin")).toBeInTheDocument();
    // Empty details render as a dash.
    expect(screen.getAllByText("—")).toHaveLength(2);
  });

  it("switches to aviation tab and filters by entity type", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("EVT-1");
    await user.click(screen.getByRole("button", { name: /Aviation Audits/ }));
    await waitFor(() => expect(safetyApi.listAuditEvents).toHaveBeenLastCalledWith({ entity_type: undefined, entity_id: undefined, limit: 100 }));
    await user.type(screen.getByPlaceholderText("Entity type (e.g. audit_finding)"), "audit_finding");
    await waitFor(() => expect(safetyApi.listAuditEvents).toHaveBeenLastCalledWith({ entity_type: "audit_finding", entity_id: undefined, limit: 100 }));
  });

  it("shows the empty state when there are no audit events", async () => {
    renderPage([]);
    expect(await screen.findByText("No audit events found.")).toBeInTheDocument();
  });
});
