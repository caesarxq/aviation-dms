import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AuthContext } from "../auth/AuthContext";
import api from "../api/client";
import { ToastProvider } from "../components/ui/Toast";
import { VersionDiff } from "./VersionDiff";

vi.mock("../api/client", () => ({ default: { get: vi.fn(), post: vi.fn(), patch: vi.fn() } }));

const docs = [{ document_id: "DOC-001", title: "Operations Manual" }];
const versions = [
  { version_id: "v1", version_number: "01.01.00", state: "published", content: "<p>The quick brown fox.</p>" },
  { version_id: "v2", version_number: "01.01.01", state: "draft", content: "<p>The quick red fox jumps.</p>" },
];

function renderPage() {
  vi.mocked(api.get).mockImplementation((path: string) => {
    if (path === "/p0/documents") return Promise.resolve({ data: docs }) as never;
    if (path === "/p0/documents/DOC-001/versions") return Promise.resolve({ data: versions }) as never;
    return Promise.resolve({ data: [] }) as never;
  });
  const profile = {
    user: { user_id: "u1", username: "user", email: "u@example.test", full_name: "User", role: "librarian", active_role: "librarian", roles: ["librarian"] },
    role: "librarian", active_role: "librarian", roles: ["librarian"], authenticated_via: "session_cookie",
    onboarding_completed: true, permissions: ["document:read", "document:propose"],
  };
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <AuthContext.Provider value={{ profile, state: "authenticated", login: async () => profile, switchRole: async () => profile, logout: async () => {}, refreshProfile: async () => profile, hasPermission: (p) => profile.permissions.includes(p) }}>
          <VersionDiff />
        </AuthContext.Provider>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

beforeEach(() => { vi.clearAllMocks(); });

describe("VersionDiff", () => {
  it("renders the heading and the initial guidance state", async () => {
    renderPage();
    expect(screen.getByRole("heading", { name: "Version Diff" })).toBeInTheDocument();
    expect(await screen.findByText("Select a document and two versions to compare.")).toBeInTheDocument();
    await waitFor(() => expect(api.get).toHaveBeenCalledWith("/p0/documents"));
  });

  it("loads documents and versions, then renders a readable suggestion stream for the two selected versions", async () => {
    const user = userEvent.setup({ pointerEventsCheck: 0 });
    renderPage();
    await screen.findByText("Select a document and two versions to compare.");

    const combos = screen.getAllByRole("combobox");
    await user.click(combos[0]);
    await user.click(await screen.findByRole("option", { name: /DOC-001 — Operations Manual/ }));
    await waitFor(() => expect(api.get).toHaveBeenCalledWith("/p0/documents/DOC-001/versions"));

    const combosAfterDoc = screen.getAllByRole("combobox");
    await user.click(combosAfterDoc[1]);
    await user.click(await screen.findByRole("option", { name: /01\.01\.00 \(published\)/ }));
    await user.click(screen.getAllByRole("combobox")[2]);
    await user.click(await screen.findByRole("option", { name: /01\.01\.01 \(draft\)/ }));

    // The diff is rendered as a suggestion stream (deleted + inserted text), not side-by-side.
    await waitFor(() => expect(screen.queryByText("Select a document and two versions to compare.")).not.toBeInTheDocument());
    expect(screen.getByText(/quick/)).toBeInTheDocument();
  });

  it("shows an explicit empty state when both selected versions have no content", async () => {
    vi.mocked(api.get).mockImplementation((path: string) => {
      if (path === "/p0/documents") return Promise.resolve({ data: docs }) as never;
      if (path === "/p0/documents/DOC-001/versions") return Promise.resolve({ data: [
        { version_id: "v1", version_number: "01.01.00", state: "published", content: "" },
        { version_id: "v2", version_number: "01.01.01", state: "draft", content: "" },
      ] }) as never;
      return Promise.resolve({ data: [] }) as never;
    });
    const user = userEvent.setup({ pointerEventsCheck: 0 });
    const profile = { user: { user_id: "u1", username: "user", email: "u@example.test", full_name: "User", role: "librarian", active_role: "librarian", roles: ["librarian"] }, role: "librarian", active_role: "librarian", roles: ["librarian"], authenticated_via: "session_cookie", onboarding_completed: true, permissions: ["document:read"] };
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}><ToastProvider>
        <AuthContext.Provider value={{ profile, state: "authenticated", login: async () => profile, switchRole: async () => profile, logout: async () => {}, refreshProfile: async () => profile, hasPermission: (p) => profile.permissions.includes(p) }}>
          <VersionDiff />
        </AuthContext.Provider>
      </ToastProvider></QueryClientProvider>,
    );
    await screen.findByText("Select a document and two versions to compare.");
    await user.click(screen.getAllByRole("combobox")[0]);
    await user.click(await screen.findByRole("option", { name: /DOC-001/ }));
    await waitFor(() => expect(api.get).toHaveBeenCalledWith("/p0/documents/DOC-001/versions"));
    await user.click(screen.getAllByRole("combobox")[1]);
    await user.click(await screen.findByRole("option", { name: /01\.01\.00/ }));
    await user.click(screen.getAllByRole("combobox")[2]);
    await user.click(await screen.findByRole("option", { name: /01\.01\.01/ }));
    expect(await screen.findByText("No content to compare.")).toBeInTheDocument();
  });
});