import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AuthContext } from "../auth/AuthContext";
import { ToastProvider } from "../components/ui/Toast";
import { safetyApi } from "../api/safety";
import { RiskAssessments } from "./RiskAssessments";

vi.mock("../api/safety", () => ({
  safetyApi: {
    listRiskAssessments: vi.fn(),
    getRiskAssessmentSummary: vi.fn(),
    createRiskAssessment: vi.fn(),
    updateRiskAssessment: vi.fn(),
    approveRiskAssessment: vi.fn(),
    listMissions: vi.fn(),
  },
}));

const api = safetyApi as any;

const assessments = [
  {
    assessment_id: "RA-DRAFT-HIGH", title: "Draft high risk", description: "High risk scenario",
    likelihood: "possible", severity: "major", risk_level: "high", risk_model: "sms_5x5",
    risk_score: 12, scrutiny_required: false, flight_cancelled: false, status: "draft",
    mission_id: null, occurrence_id: null, hazard_ids: [], assessor_id: "u-other", can_approve_for_current_user: true,
  },
  {
    assessment_id: "RA-APPROVED-LOW", title: "Approved low risk", description: "Low risk scenario",
    likelihood: "rare", severity: "negligible", risk_level: "low", risk_model: "sms_5x5",
    risk_score: 1, scrutiny_required: false, flight_cancelled: false, status: "approved",
    mission_id: null, occurrence_id: null, hazard_ids: [], assessor_id: "u-other", can_approve_for_current_user: false,
  },
];

function renderPage(permissions = ["safety:read", "safety:create", "risk_assessment:approve"], rows: any[] = assessments) {
  vi.mocked(safetyApi.listRiskAssessments).mockImplementation(async (params?: Record<string, any>) => {
    const filtered = rows.filter((row) =>
      (!params?.status || row.status === params.status) &&
      (!params?.risk_level || row.risk_level === params.risk_level)
    );
    const offset = Number(params?.offset ?? 0);
    const limit = Number(params?.limit ?? 50);
    return filtered.slice(offset, offset + limit) as any;
  });
  api.getRiskAssessmentSummary.mockResolvedValue({ total: rows.length, draft: 1, scrutiny_required: 0, approved: 1, cancelled: 0, high_or_critical: 1 });
  api.listMissions.mockResolvedValue([{ mission_id: "MSN-001", title: "Planned mission", status: "planned" }]);
  const profile = {
    user: { user_id: "u-admin", username: "admin", email: "admin@example.test", full_name: "Admin", role: "system_admin", active_role: "system_admin", roles: ["system_admin"] },
    role: "system_admin", active_role: "system_admin", roles: ["system_admin"], authenticated_via: "session_cookie", onboarding_completed: true, permissions,
  };
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <AuthContext.Provider value={{
          profile, state: "authenticated", login: async () => profile, switchRole: async () => profile,
          logout: async () => {}, refreshProfile: async () => profile,
          hasPermission: (permission) => profile.permissions.includes(permission),
        }}>
          <RiskAssessments />
        </AuthContext.Provider>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(safetyApi.listRiskAssessments).mockResolvedValue(assessments as any);
  api.getRiskAssessmentSummary.mockResolvedValue({ total: 2, draft: 1, scrutiny_required: 0, approved: 1, cancelled: 0, high_or_critical: 1 });
  vi.mocked(safetyApi.createRiskAssessment).mockResolvedValue({} as any);
  api.approveRiskAssessment.mockResolvedValue({} as any);
  api.listMissions.mockResolvedValue([]);
});

describe("Risk assessment workflow", () => {
  it("applies status and risk filters independently without destroying the loaded list", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("Draft high risk");

    const status = screen.getByRole("combobox", { name: "Filter by status" });
    const risk = screen.getByRole("combobox", { name: "Filter by risk level" });
    await user.selectOptions(status, "draft");
    expect(screen.getByText("Draft high risk")).toBeInTheDocument();
    expect(screen.queryByText("Approved low risk")).not.toBeInTheDocument();

    await user.selectOptions(status, "");
    await user.selectOptions(risk, "low");
    expect(screen.getByText("Approved low risk")).toBeInTheDocument();
    expect(screen.queryByText("Draft high risk")).not.toBeInTheDocument();
  });

  it("disables next page when the final page contains exactly 50 assessments", async () => {
    const rows = Array.from({ length: 50 }, (_, index) => ({
      ...assessments[0],
      assessment_id: `RA-PAGE-${index}`,
      title: `Boundary assessment ${index}`,
    }));
    renderPage(undefined, rows);

    expect(await screen.findByText("Boundary assessment 49")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Next page" })).toBeDisabled();
  });

  it("submits the selected OM flight risk model and presents the server-calculated result", async () => {
    const user = userEvent.setup();
    vi.mocked(safetyApi.createRiskAssessment).mockResolvedValue({
      assessment_id: "RA-NEW", title: "Severe flight risk", risk_model: "om_flight_26", exposure: "rare",
      likelihood: "frequent", severity: "catastrophic", risk_level: "critical", risk_score: 26,
      scrutiny_required: true, flight_cancelled: true, status: "cancelled", assessor_id: "u-admin",
      hazard_ids: [], mission_id: null, occurrence_id: null,
    } as any);
    renderPage();
    await screen.findByText("Draft high risk");
    await user.click(screen.getByRole("button", { name: "New Assessment" }));
    await user.type(screen.getByLabelText(/Assessment title/), "Severe flight risk");
    await user.type(screen.getByLabelText(/Description/), "Unfamiliar route in severe weather");
    await user.selectOptions(screen.getByRole("combobox", { name: /Risk model/ }), "om_flight_26");
    await user.selectOptions(screen.getByRole("combobox", { name: /Likelihood/ }), "frequent");
    await user.selectOptions(screen.getByRole("combobox", { name: /Severity/ }), "catastrophic");
    await user.selectOptions(screen.getByRole("combobox", { name: /Exposure/ }), "rare");
    await user.click(screen.getByRole("button", { name: "Submit Assessment" }));

    await waitFor(() => expect(safetyApi.createRiskAssessment).toHaveBeenCalledWith(expect.objectContaining({
      title: "Severe flight risk", risk_model: "om_flight_26", likelihood: "frequent", severity: "catastrophic", exposure: "rare",
    })));
    expect(await screen.findByRole("alert")).toHaveTextContent(/risk score 26/i);
    expect(screen.getByRole("alert")).toHaveTextContent("Flight cancelled");
  });

  it("searches planned missions on the server instead of limiting selection to the first page", async () => {
    const user = userEvent.setup();
    renderPage();
    vi.mocked(safetyApi.listMissions).mockImplementation(async (params?: Record<string, any>) => {
      return params?.search === "remote" ? [{ mission_id: "MSN-REMOTE", title: "Remote planned mission", status: "planned" }] as any : [] as any;
    });
    await screen.findByText("Draft high risk");
    await user.click(screen.getByRole("button", { name: "New Assessment" }));
    await user.type(screen.getByLabelText("Search planned missions"), "remote");

    expect(await screen.findByRole("option", { name: /MSN-REMOTE/ })).toBeInTheDocument();
    expect(safetyApi.listMissions).toHaveBeenCalledWith(expect.objectContaining({
      status: "planned", search: "remote", limit: 100, offset: 0,
    }));
  });

  it("uses the explicit approval command and offers no unsupported status mutations", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("Draft high risk");
    const draftRow = screen.getByRole("row", { name: /RA-DRAFT-HIGH/ });
    expect(within(draftRow).getByRole("button", { name: "Approve RA-DRAFT-HIGH" })).toBeInTheDocument();
    expect(within(draftRow).queryByRole("combobox", { name: /Update status/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("option", { name: "Under Review" })).not.toBeInTheDocument();

    await user.click(within(draftRow).getByRole("button", { name: "Approve RA-DRAFT-HIGH" }));
    await waitFor(() => expect(api.approveRiskAssessment).toHaveBeenCalledWith("RA-DRAFT-HIGH"));
  });

  it("hides approval when the current principal is the assessor through a legacy alias", async () => {
    const aliasedSelfAssessment = {
      ...assessments[0], assessor_id: "admin", can_approve_for_current_user: false,
    };
    renderPage(undefined, [aliasedSelfAssessment]);
    await screen.findByText("Draft high risk");

    expect(screen.queryByRole("button", { name: "Approve RA-DRAFT-HIGH" })).not.toBeInTheDocument();
    expect(screen.getByText("Independent reviewer required")).toBeInTheDocument();
  });

  it("surfaces server errors when assessment creation fails", async () => {
    const user = userEvent.setup();
    vi.mocked(safetyApi.createRiskAssessment).mockRejectedValue({ response: { data: { detail: "Mission not found for risk assessment" } } });
    renderPage();
    await screen.findByText("Draft high risk");
    await user.click(screen.getByRole("button", { name: "New Assessment" }));
    await user.type(screen.getByLabelText(/Assessment title/), "Linked assessment");
    await user.type(screen.getByLabelText(/Description/), "Detailed risk scenario");
    await user.click(screen.getByRole("button", { name: "Submit Assessment" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Mission not found for risk assessment");
  });
});
