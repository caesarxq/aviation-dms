import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import api from "../api/client";
import { AuthContext } from "../auth/AuthContext";
import { ToastProvider } from "../components/ui/Toast";
import { SelfServiceUpload } from "./SelfServiceUpload";

vi.mock("../api/client", () => ({ default: { get: vi.fn(), post: vi.fn(), patch: vi.fn() } }));

const user = {
  user_id: "person-42", username: "crew", email: "crew@example.test", full_name: "Crew Member",
  role: "chief_pilot", active_role: "chief_pilot", roles: ["chief_pilot"],
};

function renderPage(permissions = ["personnel:view"]) {
  const profile = {
    user, role: user.active_role, active_role: user.active_role, roles: user.roles,
    authenticated_via: "session_cookie", onboarding_completed: true, permissions,
  };
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <AuthContext.Provider value={{
        profile, state: "authenticated", login: async () => profile, switchRole: async () => profile,
        logout: async () => {}, refreshProfile: async () => profile,
        hasPermission: (permission) => permissions.includes(permission),
      }}>
        <ToastProvider><SelfServiceUpload /></ToastProvider>
      </AuthContext.Provider>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(api.get).mockResolvedValue({ status: 200, data: [] } as never);
  vi.mocked(api.post).mockResolvedValue({ status: 200, data: {} } as never);
});

describe("SelfServiceUpload", () => {
  it("uses the authenticated profile identity and does not expose an editable person ID", async () => {
    renderPage();
    await waitFor(() => expect(api.get).toHaveBeenCalledWith("/p2/personnel/uploads/person-42", {
      params: { status: undefined, limit: 51, offset: 0 },
    }));

    fireEvent.click(screen.getByRole("button", { name: /Upload Credential/ }));
    expect(screen.queryByLabelText(/Person ID/)).not.toBeInTheDocument();
  });

  it("shows verification actions only to personnel managers", async () => {
    vi.mocked(api.get).mockResolvedValue({
      status: 200,
      data: [{ upload_id: "upload-1", person_id: "person-42", created_by: "u-other", can_review: true, file_name: "license.pdf", download_url: "/api/p2/personnel/uploads/upload-1/file", file_size: 12, content_type: "application/pdf", license_type: "pilot_license", document_type: "license_copy", verification_status: "pending" }],
    } as never);
    const { unmount } = renderPage(["personnel:view"]);
    expect(await screen.findByText("license.pdf")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Verify" })).not.toBeInTheDocument();

    unmount();
    renderPage(["personnel:view", "personnel:manage"]);
    expect(await screen.findByRole("button", { name: "Verify upload-1" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reject upload-1" })).toBeInTheDocument();
  });

  it("shows a protected download in the manager queue and requires a rejection reason", async () => {
    const userActions = userEvent.setup();
    vi.mocked(api.get).mockImplementation((path: string) => Promise.resolve({
      status: 200,
      data: path === "/p2/personnel/uploads/person-42" ? [] : [{
        upload_id: "staff-upload", person_id: "person-99", created_by: "u-other", file_name: "staff-license.pdf",
        can_review: true,
        download_url: "/api/p2/personnel/uploads/staff-upload/file", file_size: 64, content_type: "application/pdf",
        license_type: "pilot_license", document_type: "license_copy", verification_status: "pending",
      }],
    }) as never);
    renderPage(["personnel:view", "personnel:read", "personnel:manage"]);

    const download = await screen.findByRole("link", { name: "Download staff-license.pdf" });
    expect(download).toHaveAttribute("href", "/api/p2/personnel/uploads/staff-upload/file");
    await userActions.click(screen.getByRole("button", { name: "Reject staff-upload" }));
    const reason = screen.getByLabelText(/Rejection reason/);
    expect(screen.getByRole("button", { name: "Confirm rejection" })).toBeDisabled();
    await userActions.type(reason, "Image is not legible");
    await userActions.click(screen.getByRole("button", { name: "Confirm rejection" }));
    await waitFor(() => expect(api.patch).toHaveBeenCalledWith("/p2/personnel/uploads/staff-upload/verify", {
      verification_status: "rejected", rejection_reason: "Image is not legible",
    }));
  });

  it("paginates the verification queue beyond its first page", async () => {
    const userActions = userEvent.setup();
    const uploads = Array.from({ length: 51 }, (_, index) => ({
      upload_id: `staff-${index + 1}`,
      person_id: "person-99",
      created_by: "u-other",
      file_name: `staff-${index + 1}.pdf`,
      download_url: `/api/p2/personnel/uploads/staff-${index + 1}/file`,
      file_size: 64,
      content_type: "application/pdf",
      license_type: "pilot_license",
      document_type: "license_copy",
      verification_status: "pending",
    }));
    vi.mocked(api.get).mockImplementation(((path: string, config?: any) => {
      if (path === "/p2/personnel/uploads/person-42") return Promise.resolve({ status: 200, data: [] });
      const offset = Number(config?.params?.offset ?? 0);
      return Promise.resolve({ status: 200, data: uploads.slice(offset, offset + 51) });
    }) as never);
    renderPage(["personnel:view", "personnel:read", "personnel:manage"]);

    expect(await screen.findByRole("heading", { name: "staff-50.pdf" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "staff-51.pdf" })).not.toBeInTheDocument();
    await userActions.click(screen.getByRole("button", { name: "Next verification queue page" }));

    expect(await screen.findByRole("heading", { name: "staff-51.pdf" })).toBeInTheDocument();
    expect(api.get).toHaveBeenCalledWith("/p2/personnel/uploads", {
      params: { status: "pending", limit: 51, offset: 50 },
    });
  });

  it("paginates personal upload history and applies status filters on the server", async () => {
    const userActions = userEvent.setup();
    const uploads = Array.from({ length: 51 }, (_, index) => ({
      upload_id: `personal-${index + 1}`,
      person_id: "person-42",
      file_name: `personal-${index + 1}.pdf`,
      download_url: `/download/personal-${index + 1}`,
      file_size: 64,
      content_type: "application/pdf",
      license_type: "pilot_license",
      document_type: "license_copy",
      verification_status: index === 0 ? "verified" : "pending",
      verified_by: index === 0 ? "u-ops" : null,
      verified_at: index === 0 ? "2026-11-07T10:00:00" : null,
    }));
    vi.mocked(api.get).mockImplementation(((path: string, config?: any) => {
      if (path === "/p2/personnel/uploads/person-42") {
        const filtered = config?.params?.status === "verified"
          ? uploads.filter((upload) => upload.verification_status === "verified")
          : uploads;
        const offset = Number(config?.params?.offset ?? 0);
        return Promise.resolve({ status: 200, data: filtered.slice(offset, offset + 51) });
      }
      return Promise.resolve({ status: 200, data: [] });
    }) as never);
    renderPage();

    expect(await screen.findByRole("heading", { name: "personal-50.pdf" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "personal-51.pdf" })).not.toBeInTheDocument();
    await userActions.click(screen.getByRole("button", { name: "Next upload history page" }));
    expect(await screen.findByRole("heading", { name: "personal-51.pdf" })).toBeInTheDocument();
    expect(api.get).toHaveBeenCalledWith("/p2/personnel/uploads/person-42", {
      params: { status: undefined, limit: 51, offset: 50 },
    });

    await userActions.click(screen.getByRole("button", { name: "verified" }));
    expect(await screen.findByRole("heading", { name: "personal-1.pdf" })).toBeInTheDocument();
    expect(api.get).toHaveBeenCalledWith("/p2/personnel/uploads/person-42", {
      params: { status: "verified", limit: 51, offset: 0 },
    });
  });

  it("hides review actions when the server recognizes the uploader as the same principal through an alias", async () => {
    vi.mocked(api.get).mockImplementation(((path: string) => Promise.resolve({
      status: 200,
      data: path === "/p2/personnel/uploads/person-42" ? [] : [{
        upload_id: "legacy-own-upload", person_id: "legacy-person-id", created_by: "legacy-user-id",
        can_review: false, file_name: "legacy-credential.pdf", download_url: "/download/legacy-own-upload",
        file_size: 64, content_type: "application/pdf", license_type: "pilot_license",
        document_type: "license_copy", verification_status: "pending",
      }],
    })) as never);
    renderPage(["personnel:view", "personnel:read", "personnel:manage"]);

    expect(await screen.findByText("This upload cannot be reviewed by the current account.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Verify legacy-own-upload" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Reject legacy-own-upload" })).not.toBeInTheDocument();
  });

  it("fails closed when the server omits review eligibility", async () => {
    vi.mocked(api.get).mockImplementation(((path: string) => Promise.resolve({
      status: 200,
      data: path === "/p2/personnel/uploads/person-42" ? [] : [{
        upload_id: "missing-eligibility", person_id: "person-99", created_by: "u-other",
        file_name: "eligibility-unknown.pdf", download_url: "/download/eligibility-unknown",
        file_size: 64, content_type: "application/pdf", license_type: "pilot_license",
        document_type: "license_copy", verification_status: "pending",
      }],
    })) as never);
    renderPage(["personnel:view", "personnel:read", "personnel:manage"]);

    expect(await screen.findByText("This upload cannot be reviewed by the current account.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Verify missing-eligibility" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Reject missing-eligibility" })).not.toBeInTheDocument();
  });

  it("shows who reviewed a verified or rejected upload and when", async () => {
    const reviewed = [
      {
        upload_id: "verified-1", person_id: "person-42", file_name: "verified.pdf", download_url: "/download/verified-1",
        file_size: 64, content_type: "application/pdf", license_type: "pilot_license", document_type: "license_copy",
        verification_status: "verified", verified_by: "u-ops", verified_at: "2026-11-07T10:00:00", updated_by: "u-ops", updated_at: "2026-11-07T10:00:00",
      },
      {
        upload_id: "rejected-1", person_id: "person-42", file_name: "rejected.pdf", download_url: "/download/rejected-1",
        file_size: 64, content_type: "application/pdf", license_type: "pilot_license", document_type: "license_copy",
        verification_status: "rejected", verified_by: null, verified_at: null, rejection_reason: "Image is not legible",
        updated_by: "u-ops", updated_at: "2026-11-07T10:05:00",
      },
    ];
    vi.mocked(api.get).mockImplementation(((path: string) => Promise.resolve({
      status: 200,
      data: path === "/p2/personnel/uploads/person-42" ? reviewed : [],
    })) as never);
    renderPage();

    expect(await screen.findByText("Verified by u-ops on 2026-11-07T10:00:00")).toBeInTheDocument();
    expect(screen.getByText("Rejected by u-ops on 2026-11-07T10:05:00")).toBeInTheDocument();
  });

  it("lets the browser set the multipart boundary for credential uploads", async () => {
    const userActions = userEvent.setup();
    renderPage();
    await userActions.click(await screen.findByRole("button", { name: /Upload Credential/ }));
    const file = new File(["%PDF-1.7 credential"], "license.pdf", { type: "application/pdf" });
    await userActions.upload(screen.getByLabelText(/Credential file/), file);
    await userActions.click(screen.getByRole("button", { name: "Submit for Verification" }));
    await waitFor(() => expect(api.post).toHaveBeenCalledWith("/p2/personnel/uploads/file", expect.any(FormData)));
  });

  it("shows upload failures to the user", async () => {
    const userActions = userEvent.setup();
    vi.mocked(api.post).mockRejectedValueOnce(Object.assign(new Error("request failed"), {
      response: { data: { detail: "Upload exceeds the 10 MiB limit" } },
    }));
    renderPage();
    await userActions.click(await screen.findByRole("button", { name: /Upload Credential/ }));
    const file = new File(["%PDF-1.7 credential"], "license.pdf", { type: "application/pdf" });
    await userActions.upload(screen.getByLabelText(/Credential file/), file);
    await userActions.click(screen.getByRole("button", { name: "Submit for Verification" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Upload exceeds the 10 MiB limit");
    const formData = vi.mocked(api.post).mock.calls[0][1] as FormData;
    expect(formData.has("person_id")).toBe(false);
  });
});
