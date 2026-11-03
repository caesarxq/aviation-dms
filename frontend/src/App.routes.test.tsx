import type { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import api from "./api/client";
import App from "./App";

const { mockAuth } = vi.hoisted(() => ({ mockAuth: { current: null as any } }));

vi.mock("./auth/AuthContext", () => ({
  AuthProvider: ({ children }: { children: ReactNode }) => children,
  useAuth: () => mockAuth.current,
}));

vi.mock("./api/client", () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
  },
}));

vi.mock("./pages/DocumentCatalogue", () => ({
  DocumentCatalogue: () => <h1>Document Catalogue</h1>,
}));

vi.mock("./pages/DocumentProposals", () => ({
  default: () => <h1>Document Proposals</h1>,
}));

vi.mock("./pages/DocumentViewer", () => ({
  DocumentViewer: () => <h1>Document Viewer</h1>,
}));

function renderEditRoute(permissions: string[], path = "/documents/DOC-1/edit") {
  const profile = {
    user: { user_id: "u1", username: "user", email: "user@example.test", full_name: "Test User", role: "librarian", active_role: "librarian", roles: ["librarian"] },
    role: "librarian",
    active_role: "librarian",
    roles: ["librarian"],
    authenticated_via: "session_cookie",
    permissions,
    onboarding_completed: true,
  };
  mockAuth.current = {
    profile,
    state: "authenticated",
    login: vi.fn(),
    switchRole: vi.fn(),
    logout: vi.fn(),
    refreshProfile: vi.fn(),
    hasPermission: (permission: string) => permissions.includes(permission),
  };
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[path]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.mocked(api.get).mockResolvedValue({ data: { content: "<p>Document content</p>", version_number: 1 } } as never);
});

describe("document editor route access", () => {
  it("allows proposal-only users to open the catalogue and proposal routes", async () => {
    const proposalOnly = ["document:propose"];

    const catalogue = renderEditRoute(proposalOnly, "/documents");
    expect(await screen.findByRole("heading", { name: "Document Catalogue" })).toBeInTheDocument();
    catalogue.unmount();

    renderEditRoute(proposalOnly, "/document-proposals");
    expect(await screen.findByRole("heading", { name: "Document Proposals" })).toBeInTheDocument();
  });

  it("allows proposal-only users to open the published-content viewer", async () => {
    renderEditRoute(["document:propose"], "/documents/DOC-1/view");

    expect(await screen.findByRole("heading", { name: "Document Viewer" })).toBeInTheDocument();
  });

  it("keeps proposal/edit access for users allowed to update documents", async () => {
    renderEditRoute(["document:read", "document:update", "document:propose"]);

    expect(await screen.findByRole("heading", { name: "Document Editor" })).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("allows users with only proposal permission into the editor without exposing direct draft save", async () => {
    renderEditRoute(["document:propose"]);

    expect(await screen.findByRole("heading", { name: "Document Editor" })).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "Submit proposal for review" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Save as Draft" })).not.toBeInTheDocument();
  });

  it("allows update-only users into the editor with direct draft save and without proposal submission", async () => {
    renderEditRoute(["document:read", "document:update"]);

    expect(await screen.findByRole("heading", { name: "Document Editor" })).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "Save as Draft" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Submit proposal for review" })).not.toBeInTheDocument();
  });

  it("does not let a read-only user reach the editing UI", async () => {
    renderEditRoute(["document:read"]);

    expect(await screen.findByRole("alert")).toHaveTextContent("Access to this area is not included");
    expect(screen.queryByRole("heading", { name: "Document Editor" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Submit proposal for review" })).not.toBeInTheDocument();
  });

  it("allows update-only profiles into the editor without requiring read permission", async () => {
    renderEditRoute(["document:update"]);

    expect(await screen.findByRole("heading", { name: "Document Editor" })).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "Save as Draft" })).toBeInTheDocument();
  });

  it("allows proposal-only permission when document read access is also present", async () => {
    renderEditRoute(["document:read", "document:propose"]);

    expect(await screen.findByRole("heading", { name: "Document Editor" })).toBeInTheDocument();
  });
});
