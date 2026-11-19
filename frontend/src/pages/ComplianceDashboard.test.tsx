import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import api from "../api/client";
import { controlledDocumentApi } from "../api/controlledDocument";
import { AuthContext } from "../auth/AuthContext";
import { ToastProvider } from "../components/ui/Toast";
import { ComplianceDashboard } from "./ComplianceDashboard";

vi.mock("../api/client", () => ({ default: { get: vi.fn(), post: vi.fn() } }));
vi.mock("../api/controlledDocument", () => ({
  controlledDocumentApi: {
    listExtractionRequests: vi.fn(),
    approveExtractionRequest: vi.fn(),
    rejectExtractionRequest: vi.fn(),
  },
}));

const requests = [
  { id: "ER-1", document_id: "DOC-001", section_id: "SEC-1", requested_by: "u-editor", status: "pending", created_at: "2026-11-01" },
];

function renderPage(permissions: string[]) {
  vi.mocked(controlledDocumentApi.listExtractionRequests).mockResolvedValue(requests as never);
  vi.mocked(api.get).mockResolvedValue({ data: [] } as never);
  const profile = { user_id: "u-1", username: "tester", role: "quality", permissions } as never;
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <AuthContext.Provider value={{ profile, state: "authenticated", login: async () => profile, switchRole: async () => profile, logout: async () => {}, refreshProfile: async () => profile, hasPermission: (p: string) => permissions.includes(p) } as never}>
          <ComplianceDashboard />
        </AuthContext.Provider>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

beforeEach(() => { vi.clearAllMocks(); });

describe("ComplianceDashboard RBAC", () => {
  it("shows an access-restricted state without extract or audit-read permission", async () => {
    renderPage([]);
    expect(await screen.findByText("Access Restricted")).toBeInTheDocument();
    expect(screen.getByText(/do not have permission to view compliance data/)).toBeInTheDocument();
    expect(controlledDocumentApi.listExtractionRequests).not.toHaveBeenCalled();
  });

  it("shows approve/reject actions for a pending request with approve permission", async () => {
    renderPage(["document.section.extract", "document.extract.approve", "audit:read"]);
    expect(await screen.findByText("ER-1")).toBeInTheDocument();
    expect(screen.getByText("Pending Requests")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Approve" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reject" })).toBeInTheDocument();
  });

  it("hides approve/reject actions without document.extract.approve (read-only)", async () => {
    renderPage(["document.section.extract", "audit:read"]);
    expect(await screen.findByText("ER-1")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Approve" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Reject" })).not.toBeInTheDocument();
  });
});