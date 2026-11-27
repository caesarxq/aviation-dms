import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AuthContext } from "../auth/AuthContext";
import { qualityAuditApi } from "../api/audit";
import { ToastProvider } from "../components/ui/Toast";
import { AuditPlanning } from "./AuditPlanning";

vi.mock("../api/audit", () => ({
  qualityAuditApi: {
    listQualityAudits: vi.fn().mockResolvedValue([]),
    createQualityAudit: vi.fn().mockResolvedValue({ audit_id: "QA-TEST-1" }),
    createAuditResource: vi.fn().mockResolvedValue({ resource_id: "AR-TEST-1" }),
    updateQualityAudit: vi.fn(),
    listAuditResources: vi.fn().mockResolvedValue([]),
    updateAuditResource: vi.fn(),
    deleteAuditResource: vi.fn(),
  },
}));

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const permissions = ["safety:create", "safety:read", "safety:update"];
  const profile = { permissions };
  return render(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <AuthContext.Provider value={{
          profile: profile as never,
          state: "authenticated",
          login: async () => profile as never,
          switchRole: async () => profile as never,
          logout: async () => undefined,
          refreshProfile: async () => profile as never,
          hasPermission: (permission: string) => permissions.includes(permission),
        } as never}>
          <AuditPlanning />
        </AuthContext.Provider>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("AuditPlanning checklist creation", () => {
  beforeEach(() => vi.clearAllMocks());

  it("creates checklist items with the audit plan", async () => {
    const user = userEvent.setup();
    renderPage();
    await user.click(screen.getByRole("button", { name: "Plan Audit" }));
    await user.type(screen.getByPlaceholderText("Audit title"), "Annual safety audit");
    await user.type(screen.getByPlaceholderText("e.g. u-head-quality"), "u-auditor");
    await user.type(screen.getByLabelText(/Planned Date/), "2027-01-15");
    await user.type(screen.getByLabelText("Checklist items"), "Review flight records\nInterview operations staff");
    await user.click(screen.getByRole("button", { name: "Create Audit Plan" }));

    await waitFor(() => expect(qualityAuditApi.createAuditResource).toHaveBeenCalledWith("QA-TEST-1", {
      resource_type: "checklist",
      resource_name: "Audit checklist",
      description: "☐ Review flight records\n☐ Interview operations staff",
    }));
  });
});
