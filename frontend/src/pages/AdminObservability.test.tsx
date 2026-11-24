import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import api from "../api/client";
import AdminObservability from "./AdminObservability";

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

const healthData = { 
    backup: { enabled: true, running: false, run_count: 0, failure_count: 0, last_error: null },
    scanner: { configured: true, reachable: true, host: "localhost", port: 3310, detail: "OK" }
  };

const observability = {
  version: {
    name: "KFL Aviation DMS",
    api_version: "1.0.0",
    release_tag: "canonical-5012309115b2a2d3b38a23e35dc6cf92a26ebcc3-20261118T200056Z",
    git_sha: "5012309115b2a2d3b38a23e35dc6cf92a26ebcc3",
  },
  health: { status: "ok", scheduler: "running", ...healthData },
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

const appVersions = [
  {
    version_id: "v1",
    version_number: "1.0.0",
    released_at: "2026-11-18T20:00:56Z",
    released_by: "u-admin",
    changelog_non_technical: "Initial release",
    changelog_technical: "Initial release",
    notification_sent: true,
  },
];

const backupHistory = {
  events: [
    {
      event_id: "evt-1",
      timestamp: "2026-11-18T20:00:56Z",
      action: "backup_run",
      details: { accepted: true },
    },
  ],
};

const auditEvents = [
  {
    event_id: "evt-1",
    timestamp: "2026-11-18T20:00:56Z",
    entity_type: "user",
    action: "created",
    actor_id: "u-admin",
    details: "User created",
  },
];

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
    vi.spyOn(api, "get").mockImplementation((url: string) => {
      if (url === "/p0/admin/observability") {
        return Promise.resolve({ data: observability } as any);
      }
      if (url === "/p0/app-versions") {
        return Promise.resolve({ data: appVersions } as any);
      }
      if (url === "/p0/backup/history") {
        return Promise.resolve({ data: backupHistory } as any);
      }
      if (url === "/p0/audit-events") {
        return Promise.resolve({ data: auditEvents } as any);
      }
      return Promise.resolve({ data: {} } as any);
    });
    vi.spyOn(api, "put").mockResolvedValue({ data: { user_id: "u-quality", roles: ["head_quality", "librarian", "records_custodian"] } } as any);
    vi.spyOn(api, "post").mockResolvedValue({ data: { delivery_id: "delivery-1", recipient_email: "librarian@example.test", delivery_status: "sent", setup_url: undefined, expires_at: "2026-11-19T12:00:00Z" } } as any);
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

  it("shows the runtime build version and Git SHA tile", async () => {
    renderAdmin();

    expect(await screen.findByText("Build version")).toBeInTheDocument();
    expect(screen.getByText("canonical-5012309115b2a2d3b38a23e35dc6cf92a26ebcc3-20261118T200056Z")).toBeInTheDocument();
    expect(screen.getByText(/API 1\.0\.0/)).toBeInTheDocument();
    expect(screen.getByText(/5012309115b2a/)).toBeInTheDocument();
  });

  it("displays preserved merged account IDs without offering them role editing", async () => {
    vi.spyOn(api, "get").mockResolvedValue({
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
    vi.spyOn(api, "get").mockResolvedValue({
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

  it("sends the invitation to the registered address without displaying a bearer token", async () => {
    const invitee = { ...userProfile, has_password: false };
    vi.spyOn(api, "get").mockResolvedValue({
      data: { ...observability, user_profiles: [invitee] },
    } as any);
    const post = vi.spyOn(api, "post").mockResolvedValue({
      data: {
        delivery_id: "delivery-1",
        recipient_email: invitee.email,
        delivery_status: "sent",
        setup_url: undefined,
        expires_at: "2026-11-19T12:00:00Z",
      },
    } as any);
    renderAdmin();

    expect(await screen.findAllByText(new RegExp(invitee.email))).toHaveLength(2);
    expect(screen.queryByLabelText("Email for invite")).not.toBeInTheDocument();
    fireEvent.click(await screen.findByRole("button", { name: "Send invite email for Canonical User" }));

    await waitFor(() => expect(post).toHaveBeenNthCalledWith(1, "/p0/auth/invites", {
      username: "librarian",
      delivery_method: "email",
      resend: false,
    }));
    expect(await screen.findByRole("status")).toHaveTextContent("Email accepted by SMTP for librarian@example.test.");
    fireEvent.click(await screen.findByRole("button", { name: "Reissue invite email for Canonical User" }));
    await waitFor(() => expect(post).toHaveBeenNthCalledWith(2, "/p0/auth/invites", {
      username: "librarian",
      delivery_method: "email",
      resend: true,
    }));
    expect(screen.queryByText(/invite code|setup url/i)).not.toBeInTheDocument();
  });

  it("keeps manual secure-link delivery available as an explicit fallback", async () => {
    const invitee = { ...userProfile, has_password: false };
    vi.spyOn(api, "get").mockResolvedValue({ data: { ...observability, user_profiles: [invitee] } } as any);
    const setupUrl = "https://dms.example.test/setup?username=librarian#setup_token=opaque-test-token";
    const post = vi.spyOn(api, "post").mockResolvedValue({
      data: {
        delivery_id: "manual-1",
        recipient_email: invitee.email,
        delivery_status: "manual",
        setup_url: setupUrl,
        expires_at: "2026-11-19T12:00:00Z",
      },
    } as any);
    renderAdmin();

    fireEvent.click(await screen.findByRole("button", { name: "Generate manual invite for Canonical User" }));
    await waitFor(() => expect(post).toHaveBeenCalledWith("/p0/auth/invites", {
      username: "librarian",
      delivery_method: "manual",
      resend: false,
    }));
    expect(await screen.findByLabelText("Manual setup link for Canonical User")).toHaveValue(setupUrl);
    expect(await screen.findByRole("status")).toHaveTextContent(/share it only through the approved secure channel/i);
  });
});