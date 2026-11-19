import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import api from "../api/client";
import { controlledDocumentApi } from "../api/controlledDocument";
import { AuthContext } from "../auth/AuthContext";
import { ToastProvider } from "../components/ui/Toast";
import { DocumentControllerDashboard } from "./DocumentControllerDashboard";

vi.mock("../api/client", () => ({ default: { get: vi.fn(), post: vi.fn(), put: vi.fn() } }));
vi.mock("../api/controlledDocument", () => ({
  controlledDocumentApi: {
    listDocumentClassifications: vi.fn(),
    listExtractionRequests: vi.fn(),
  },
}));

const docs = [
  { document_id: "DOC-001", title: "Operations Manual", classification: "CONTROLLED", kcaa_approval_required: false },
  { document_id: "DOC-002", title: "Safety Manual", classification: "KCAA_APPROVED", kcaa_approval_required: true },
];

function renderPage(permissions: string[]) {
  vi.mocked(api.get).mockResolvedValue({ data: docs } as never);
  vi.mocked(controlledDocumentApi.listDocumentClassifications).mockResolvedValue([] as never);
  vi.mocked(controlledDocumentApi.listExtractionRequests).mockResolvedValue([] as never);
  const profile = { user_id: "u-1", username: "tester", role: "librarian", permissions } as never;
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <AuthContext.Provider value={{ profile, state: "authenticated", login: async () => profile, switchRole: async () => profile, logout: async () => {}, refreshProfile: async () => profile, hasPermission: (p: string) => permissions.includes(p) } as never}>
          <DocumentControllerDashboard />
        </AuthContext.Provider>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

beforeEach(() => { vi.clearAllMocks(); });

describe("DocumentControllerDashboard RBAC", () => {
  it("restricts access and fetches nothing without document.policy.manage", async () => {
    renderPage([]);
    expect(await screen.findByText("Access Restricted")).toBeInTheDocument();
    expect(screen.getByText(/do not have permission to manage document classifications/)).toBeInTheDocument();
    expect(api.get).not.toHaveBeenCalled();
  });

  it("lists documents with classification badges for a document controller", async () => {
    renderPage(["document.policy.manage"]);
    expect(await screen.findByRole("heading", { name: "Document Controller" })).toBeInTheDocument();
    await screen.findByText("DOC-001");
    expect(screen.getByText("Operations Manual")).toBeInTheDocument();
    expect(screen.getByText("CONTROLLED")).toBeInTheDocument();
    expect(screen.getByText("KCAA_APPROVED")).toBeInTheDocument();
  });
});