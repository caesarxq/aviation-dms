import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { auditApi } from "../api/audit";
import { AuditDashboard } from "./AuditDashboard";

vi.mock("../api/audit", () => ({ auditApi: { getAuditFindingsSummary: vi.fn() } }));

function renderDashboard() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><AuditDashboard /></QueryClientProvider>);
}

describe("AuditDashboard", () => {
  beforeEach(() => vi.clearAllMocks());

  it("does not present zero counts while the summary is loading", () => {
    vi.mocked(auditApi.getAuditFindingsSummary).mockReturnValue(new Promise(() => {}) as never);
    renderDashboard();
    expect(screen.getAllByText("—")).toHaveLength(4);
    expect(screen.queryByText("0% open")).not.toBeInTheDocument();
  });

  it("does not present zero counts when the summary request fails", async () => {
    vi.mocked(auditApi.getAuditFindingsSummary).mockRejectedValue(new Error("network"));
    renderDashboard();
    expect(await screen.findByRole("alert")).toHaveTextContent("Unable to load audit summary");
    expect(screen.getAllByText("—")).toHaveLength(4);
    expect(screen.queryByText("0% open")).not.toBeInTheDocument();
  });

  it("shows real zero counts after an empty summary loads successfully", async () => {
    vi.mocked(auditApi.getAuditFindingsSummary).mockResolvedValue({ total: 0, open: 0, closed: 0, by_level: {}, by_status: {}, by_area: {} } as never);
    renderDashboard();
    expect(await screen.findByText("0% open")).toBeInTheDocument();
    expect(screen.getAllByText("0").length).toBeGreaterThan(0);
  });
});
