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
    await waitFor(() => expect(api.get).toHaveBeenCalledWith("/p2/personnel/uploads/person-42"));

    fireEvent.click(screen.getByRole("button", { name: /Upload Credential/ }));
    expect(screen.queryByLabelText(/Person ID/)).not.toBeInTheDocument();
  });

  it("shows verification actions only to personnel managers", async () => {
    vi.mocked(api.get).mockResolvedValue({
      status: 200,
      data: [{ upload_id: "upload-1", file_name: "license.pdf", file_path: "stored", file_size: 12, content_type: "application/pdf", license_type: "pilot_license", document_type: "license_copy", verification_status: "pending" }],
    } as never);
    const { unmount } = renderPage(["personnel:view"]);
    expect(await screen.findByText("license.pdf")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Verify" })).not.toBeInTheDocument();

    unmount();
    renderPage(["personnel:view", "personnel:manage"]);
    expect(await screen.findByRole("button", { name: "Verify" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reject" })).toBeInTheDocument();
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
