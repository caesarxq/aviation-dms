import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { AuthContext } from "../auth/AuthContext";
import api from "../api/client";
import { ToastProvider } from "../components/ui/Toast";
import { DocumentProposals } from "./DocumentProposals";

vi.mock("../api/client", () => ({ default: { get: vi.fn(), post: vi.fn(), patch: vi.fn() } }));

const documents = [{ document_id: "DOC-001", title: "Operations Manual" }];
const proposals = [{
  proposal_id: "PROP-001",
  document_id: "DOC-001",
  status: "submitted",
  severity: "minor",
  proposal_type: "word",
  target_ref: "Section 1",
  rationale: "Clarify wording",
  anchor_id: "anchor-1",
}];

function renderPage(permissions: string[], status = "submitted") {
  vi.mocked(api.get).mockImplementation((path: string) => Promise.resolve({
    data: path === "/p0/documents" ? documents : proposals.map((proposal) => ({ ...proposal, status })),
  }) as never);
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
          <MemoryRouter><DocumentProposals /></MemoryRouter>
        </AuthContext.Provider>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

beforeEach(() => vi.clearAllMocks());

describe("Document proposal editor links", () => {
  it("hides affected-section editor links from read-only users", async () => {
    const user = userEvent.setup();
    renderPage(["document:read"]);
    await screen.findByText("DOC-001 — Operations Manual");
    await user.selectOptions(screen.getByRole("combobox"), "DOC-001");
    await screen.findByText("PROP-001");
    expect(screen.queryByRole("link", { name: "Open affected section" })).not.toBeInTheDocument();
  });

  it("shows affected-section editor links to users with update permission", async () => {
    const user = userEvent.setup();
    renderPage(["document:read", "document:update"]);
    await screen.findByText("DOC-001 — Operations Manual");
    await user.selectOptions(screen.getByRole("combobox"), "DOC-001");
    expect(await screen.findByRole("link", { name: "Open affected section" })).toBeInTheDocument();
  });
});

describe("Document proposal controls", () => {
  async function selectDocument(user: ReturnType<typeof userEvent.setup>) {
    await screen.findByText("DOC-001 — Operations Manual");
    await user.selectOptions(screen.getByRole("combobox"), "DOC-001");
    await screen.findByText("PROP-001");
  }

  it("hides proposal creation and status actions from read-only users", async () => {
    const user = userEvent.setup();
    renderPage(["document:read"], "submitted");
    await selectDocument(user);

    expect(screen.queryByRole("button", { name: "New Proposal" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Submit" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Approve/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Reject/ })).not.toBeInTheDocument();
  });

  it("hides draft submission from read-only users", async () => {
    const user = userEvent.setup();
    renderPage(["document:read"], "draft");
    await selectDocument(user);

    expect(screen.queryByRole("button", { name: "Submit" })).not.toBeInTheDocument();
  });

  it("allows proposal-only users to create proposals, submit drafts, and open affected sections", async () => {
    const user = userEvent.setup();
    renderPage(["document:propose"], "draft");
    await selectDocument(user);

    await user.click(screen.getByRole("button", { name: "New Proposal" }));
    expect(screen.getByRole("button", { name: "Submit Proposal" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Submit" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Approve/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Reject/ })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open affected section" })).toBeInTheDocument();
  });

  it("does not allow update-only users to create proposals or submit drafts", async () => {
    const user = userEvent.setup();
    renderPage(["document:read", "document:update"], "draft");
    await selectDocument(user);

    expect(screen.queryByRole("button", { name: "New Proposal" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Submit" })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open affected section" })).toBeInTheDocument();
  });

  it("shows approval controls to update-only users and keeps publishing restricted", async () => {
    const user = userEvent.setup();
    renderPage(["document:read", "document:update"], "submitted");
    await selectDocument(user);

    expect(screen.getByRole("button", { name: /Approve/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Reject/ })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Apply to New Version" })).not.toBeInTheDocument();
  });

  it("shows approve and reject controls to approve-only users without proposal creation", async () => {
    const user = userEvent.setup();
    renderPage(["document:read", "document:approve"], "submitted");
    await selectDocument(user);

    expect(screen.queryByRole("button", { name: "New Proposal" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Approve/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Reject/ })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Open affected section" })).not.toBeInTheDocument();
  });

  it("does not allow approve-only users to submit drafts", async () => {
    const user = userEvent.setup();
    renderPage(["document:read", "document:approve"], "draft");
    await selectDocument(user);

    expect(screen.queryByRole("button", { name: "Submit" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "New Proposal" })).not.toBeInTheDocument();
  });

  it("shows only apply controls to publish-only users for approved proposals", async () => {
    const user = userEvent.setup();
    renderPage(["document:read", "document:publish"], "approved");
    await selectDocument(user);

    expect(screen.getByRole("button", { name: "Apply to New Version" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "New Proposal" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Submit" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Approve/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Reject/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Open affected section" })).not.toBeInTheDocument();
  });
});
