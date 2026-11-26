import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AuthContext } from "../auth/AuthContext";
import { ToastProvider } from "../components/ui/Toast";
import { ChangeRequests } from "./ChangeRequests";

const listChangeRequests = vi.fn();
const listReviewComments = vi.fn();

vi.mock("../api/safety", () => ({
  safetyApi: {
    listChangeRequests: (...args: unknown[]) => listChangeRequests(...args),
    listReviewComments: (...args: unknown[]) => listReviewComments(...args),
    createChangeRequest: vi.fn(),
    submitChangeRequest: vi.fn(),
    reviewChangeRequest: vi.fn(),
    approveChangeRequest: vi.fn(),
    rejectChangeRequest: vi.fn(),
    deleteChangeRequest: vi.fn(),
    addReviewComment: vi.fn(),
  },
}));

const changeRequests = [
  {
    cr_id: "CR-001",
    document_id: "DOC-001",
    version_id: null,
    title: "Revise emergency procedures",
    description: "Update the diversion guidance.",
    change_type: "minor",
    status: "submitted",
    requester_id: "u-ops",
    reviewer_id: null,
    approver_id: null,
    created_at: "2026-11-20T00:00:00Z",
    updated_at: "2026-11-20T00:00:00Z",
  },
];

function renderPage(permissions: string[], rows: unknown[] = changeRequests) {
  listChangeRequests.mockResolvedValue(rows);
  listReviewComments.mockResolvedValue([]);
  const profile = {
    user: { user_id: "u1", username: "user", email: "u@example.test", full_name: "User", role: "head_quality", active_role: "head_quality", roles: ["head_quality"] },
    role: "head_quality",
    active_role: "head_quality",
    roles: ["head_quality"],
    authenticated_via: "session_cookie",
    onboarding_completed: true,
    permissions,
  };
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <AuthContext.Provider
          value={{
            profile,
            state: "authenticated",
            login: async () => profile,
            switchRole: async () => profile,
            logout: async () => {},
            refreshProfile: async () => profile,
            hasPermission: (permission: string) => permissions.includes(permission),
          } as never}
        >
          <ChangeRequests />
        </AuthContext.Provider>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("ChangeRequests permissions", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("hides the create action and the register from a read-only user", async () => {
    renderPage(["document:read"]);

    expect(screen.queryByRole("button", { name: /new change request/i })).not.toBeInTheDocument();
    expect(await screen.findByText(/register is restricted/i)).toBeInTheDocument();
    // The register request would 403, so it must not be sent.
    expect(listChangeRequests).not.toHaveBeenCalled();
  });

  it("shows the create action but not the register to a requester", async () => {
    renderPage(["document:read", "change_request:create"]);

    expect(screen.getByRole("button", { name: /new change request/i })).toBeInTheDocument();
    expect(await screen.findByText(/register is restricted/i)).toBeInTheDocument();
    expect(listChangeRequests).not.toHaveBeenCalled();
  });

  it("offers review to a reviewer but not approval", async () => {
    renderPage(["document:read", "change_request:review"]);

    expect(await screen.findByText("Revise emergency procedures")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /new change request/i })).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /^view$/i }));

    expect(screen.getByRole("button", { name: /start review/i })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^approve$/i })).not.toBeInTheDocument();
  });

  it("offers approval to an approver but not review", async () => {
    renderPage(
      ["document:read", "change_request:review", "change_request:approve"],
      [{ ...changeRequests[0], status: "under_review" }],
    );

    expect(await screen.findByText("Revise emergency procedures")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /^view$/i }));

    expect(screen.getByRole("button", { name: /^approve$/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^reject$/i })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /start review/i })).not.toBeInTheDocument();
  });
});
