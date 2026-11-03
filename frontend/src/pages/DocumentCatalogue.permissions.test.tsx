import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { AuthContext } from "../auth/AuthContext";
import api from "../api/client";
import { ToastProvider } from "../components/ui/Toast";
import { DocumentCatalogue } from "./DocumentCatalogue";

vi.mock("../api/client", () => ({ default: { get: vi.fn(), post: vi.fn() } }));

const documents = [
  {
    document_id: "DOC-001",
    title: "Operations Manual",
    doc_class: "manual",
    status: "published",
    classification: "S2",
    kcaa_approval_required: false,
    review_due_date: null,
  },
];

function renderCatalogue(permissions: string[]) {
  vi.mocked(api.get).mockResolvedValue({ data: documents } as never);
  const profile = {
    user: { user_id: "u1", username: "user", email: "u@example.test", full_name: "User", role: "head_safety", active_role: "head_safety", roles: ["head_safety"] },
    role: "head_safety",
    active_role: "head_safety",
    roles: ["head_safety"],
    authenticated_via: "session_cookie",
    onboarding_completed: true,
    permissions,
  };
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <AuthContext.Provider value={{
          profile,
          state: "authenticated",
          login: async () => profile,
          switchRole: async () => profile,
          logout: async () => {},
          refreshProfile: async () => profile,
          hasPermission: (permission) => permissions.includes(permission),
        }}>
          <MemoryRouter><DocumentCatalogue /></MemoryRouter>
        </AuthContext.Provider>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

beforeEach(() => vi.clearAllMocks());

describe("Document Catalogue permission-aware actions", () => {
  it("does not expose create or edit actions to a read-only user", async () => {
    renderCatalogue(["document:read"]);

    expect(await screen.findByRole("link", { name: "View" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Edit" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Open editor/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "New Document" })).not.toBeInTheDocument();
  });

  it("exposes edit and create actions only to users with the matching permissions", async () => {
    renderCatalogue(["document:read", "document:update", "document:create"]);

    expect(await screen.findByRole("link", { name: "Edit" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Open editor/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "New Document" })).toBeInTheDocument();
  });

  it("exposes editor links to proposal-only users without granting document creation", async () => {
    renderCatalogue(["document:propose"]);

    expect(await screen.findByRole("link", { name: "Edit" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Open editor/ })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "New Document" })).not.toBeInTheDocument();
  });
});
