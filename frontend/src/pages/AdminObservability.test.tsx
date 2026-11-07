import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import api from "../api/client";
import AdminObservability from "./AdminObservability";

vi.mock("../api/client", () => ({ default: { get: vi.fn(), put: vi.fn() } }));

const userProfile = {
  user_id: "u-quality",
  username: "librarian",
  email: "librarian@example.test",
  full_name: "Canonical User",
  role: "head_quality",
  roles: ["head_quality", "librarian", "records_custodian"],
  department: "Quality",
  is_active: 1,
  merged_into_user_id: null,
  has_password: true,
};

const observability = {
  health: { status: "ok", scheduler: "running" },
  database: { status: "ok", integrity: "ok" },
  tables: {},
  users: { total: 1, active: 1, inactive: 0 },
  user_profiles: [userProfile],
  audit: { events_last_24h: 0, total_events: 0 },
  workflows: { document_versions: {} },
  role_matrix: [
    { role: "head_quality", access_level: "L2", permissions: ["document:approve"] },
    { role: "librarian", access_level: "L2", permissions: ["document:read"] },
    { role: "records_custodian", access_level: "L2", permissions: ["document:read"] },
  ],
};

function renderAdmin() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <AdminObservability />
    </QueryClientProvider>,
  );
}

describe("AdminObservability role assignments", () => {
  beforeEach(() => {
    vi.mocked(api.get).mockResolvedValue({ data: observability } as any);
    vi.mocked(api.put).mockResolvedValue({ data: { user_id: "u-quality", roles: ["head_quality", "librarian", "records_custodian"] } } as any);
  });
  afterEach(() => vi.restoreAllMocks());

  it("updates roles on the canonical account through the admin API", async () => {
    renderAdmin();
    const roleSelect = await screen.findByLabelText("Assigned roles for Canonical User");

    await userEvent.selectOptions(roleSelect, ["head_quality", "librarian", "records_custodian"]);
    fireEvent.click(screen.getByRole("button", { name: "Save roles for Canonical User" }));

    await waitFor(() => expect(api.put).toHaveBeenCalledWith(
      "/p0/auth/users/u-quality/roles",
      { roles: ["head_quality", "librarian", "records_custodian"] },
    ));
  });

  it("displays preserved merged account IDs without offering them role editing", async () => {
    vi.mocked(api.get).mockResolvedValue({
      data: {
        ...observability,
        user_profiles: [
          userProfile,
          { ...userProfile, user_id: "u-lib", username: "librarian", roles: ["librarian"], is_active: 0, merged_into_user_id: "u-quality", has_password: false },
        ],
      },
    } as any);
    renderAdmin();

    expect(await screen.findByText(/Merged into u-quality; historical ID retained/i)).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /Save roles for/ })).toHaveLength(1);
  });

  it("URL-encodes a literal slash in the canonical ID when saving roles", async () => {
    const slashUser = {
      ...userProfile,
      user_id: "u-safety/security",
      full_name: "Safety Security User",
      role: "head_safety",
      roles: ["head_safety", "head_security"],
    };
    vi.mocked(api.get).mockResolvedValue({
      data: {
        ...observability,
        user_profiles: [slashUser],
        role_matrix: [
          ...observability.role_matrix,
          { role: "head_safety", access_level: "L2", permissions: [] },
          { role: "head_security", access_level: "L2", permissions: [] },
        ],
      },
    } as any);
    renderAdmin();

    await screen.findByLabelText("Assigned roles for Safety Security User");
    fireEvent.click(screen.getByRole("button", { name: "Save roles for Safety Security User" }));

    await waitFor(() => expect(api.put).toHaveBeenCalledWith(
      "/p0/auth/users/u-safety%2Fsecurity/roles",
      { roles: ["head_safety", "head_security"] },
    ));
  });
});
