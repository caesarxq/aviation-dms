import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { safetyApi } from "../api/safety";
import { AuditTrail } from "./AuditTrail";

vi.mock("../api/safety", () => ({ safetyApi: { listAuditEvents: vi.fn() } }));

const now = new Date().toISOString();
const events = [
  { event_id: "EVT-1", entity_type: "document", entity_id: "DOC-001", action: "published", actor_id: "u-librarian", timestamp: now, details: "Published v2" },
  { event_id: "EVT-2", entity_type: "document", entity_id: "DOC-002", action: "deleted", actor_id: "u-admin", timestamp: now, details: "" },
  { event_id: "EVT-3", entity_type: "crew", entity_id: "CRW-1", action: "created", actor_id: "u-safety", timestamp: now, details: "" },
];

function statValue(label: string) {
  return screen.getByText(label).nextElementSibling as HTMLElement;
}

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
  it("renders audit events with action badges and computes total/entity-type stats", async () => {
    renderPage();
    expect(screen.getByRole("heading", { name: "Audit Trail" })).toBeInTheDocument();
    await screen.findByText("EVT-1");
    expect(statValue("Total Events")).toHaveTextContent("3");
    expect(statValue("Entity Types")).toHaveTextContent("2");
    expect(screen.getByText("published")).toBeInTheDocument();
    expect(screen.getByText("deleted")).toBeInTheDocument();
    expect(screen.getByText("created")).toBeInTheDocument();
    expect(screen.getByText("u-librarian")).toBeInTheDocument();
    // Empty details render as a dash.
    expect(screen.getAllByText("—")).toHaveLength(2);
  });

  it("refetches with the entity-type filter applied", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("EVT-1");
    await user.type(screen.getByPlaceholderText("Entity type (e.g. document)"), "document");
    await waitFor(() => expect(safetyApi.listAuditEvents).toHaveBeenCalledWith({ entity_type: "document", entity_id: undefined, limit: 100 }));
  });

  it("shows the empty state when there are no audit events", async () => {
    renderPage([]);
    expect(await screen.findByText("No audit events found.")).toBeInTheDocument();
    expect(statValue("Total Events")).toHaveTextContent("0");
  });
});