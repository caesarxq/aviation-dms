import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AuthContext } from "../auth/AuthContext";
import api from "../api/client";
import { ToastProvider } from "../components/ui/Toast";
import { Missions } from "./Missions";

vi.mock("../api/client", () => ({ default: { get: vi.fn(), post: vi.fn(), patch: vi.fn() } }));

const missions = [
  { mission_id: "m-1", title: "Coastal survey", mission_type: "survey", status: "planned", priority: "normal", planned_date: "2026-11-01" },
  { mission_id: "m-2", title: "Lake inspection", mission_type: "inspection", status: "completed", priority: "high", planned_date: "2026-11-02" },
];

const lifecycleMissions = [
  { mission_id: "m-planned", title: "Planned flight", mission_type: "survey", status: "planned", priority: "normal", planned_date: "2026-11-01" },
  { mission_id: "m-released", title: "Released flight", mission_type: "survey", status: "released", priority: "normal", planned_date: "2026-11-01" },
  { mission_id: "m-active", title: "Active flight", mission_type: "survey", status: "in_progress", priority: "normal", planned_date: "2026-11-01" },
];

function renderPage(items: typeof missions = missions, permissions: string[] = ["safety:read", "safety:create"], summaryResult: any = { data: { total: 2, planned: 1, in_progress: 0, completed: 1 } }, listResult: (config?: any) => any = () => items) {
  vi.mocked(api.get).mockImplementation((path: string, config?: any) => path === "/p1/missions/summary" ? (typeof summaryResult === "function" ? summaryResult() : Promise.resolve(summaryResult)) as never : Promise.resolve({ data: listResult(config) }) as never);
  const profile = { user: { user_id: "u1", username: "user", email: "u@example.test", full_name: "User", role: "head_operations", active_role: "head_operations", roles: ["head_operations"] }, role: "head_operations", active_role: "head_operations", roles: ["head_operations"], authenticated_via: "session_cookie", onboarding_completed: true, permissions };
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><ToastProvider><AuthContext.Provider value={{ profile, state: "authenticated", login: async () => profile, switchRole: async () => profile, logout: async () => {}, refreshProfile: async () => profile, hasPermission: (permission) => profile.permissions.includes(permission) }}><Missions /></AuthContext.Provider></ToastProvider></QueryClientProvider>);
}

beforeEach(() => { vi.clearAllMocks(); vi.mocked(api.get).mockResolvedValue({ data: missions }); });

describe("Missions list filters", () => {
  it("filters mission records independently from the create form and by status", async () => {
    const user = userEvent.setup();
    renderPage(missions, undefined, undefined, (config) => missions.filter((mission: any) =>
      (!config?.params?.search || [mission.mission_id, mission.title, mission.mission_type, mission.location].some((value) => String(value ?? "").toLowerCase().includes(config.params.search.toLowerCase()))) &&
      (!config?.params?.status || mission.status === config.params.status)
    ));
    await screen.findByText("Coastal survey");
    await user.type(screen.getByRole("searchbox", { name: "Search missions" }), "Lake");
    await waitFor(() => expect(api.get).toHaveBeenLastCalledWith("/p1/missions", { params: { search: "Lake", limit: 50, offset: 0 } }));
    expect(screen.getByText("Lake inspection")).toBeInTheDocument();
    expect(screen.queryByText("Coastal survey")).not.toBeInTheDocument();
    await user.clear(screen.getByRole("searchbox", { name: "Search missions" }));
    await user.selectOptions(screen.getByRole("combobox", { name: "Filter missions by status" }), "planned");
    await waitFor(() => expect(api.get).toHaveBeenLastCalledWith("/p1/missions", { params: { status: "planned", limit: 50, offset: 0 } }));
    expect(screen.getByText("Coastal survey")).toBeInTheDocument();
    expect(screen.queryByText("Lake inspection")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "New Mission" }));
    expect(screen.getByLabelText(/Mission title/)).toHaveValue("");
  });

  it("uses server-side pagination and resets to the first page when a filter changes", async () => {
    const user = userEvent.setup();
    const firstPage = Array.from({ length: 50 }, (_, index) => ({
      mission_id: `m-${index}`, title: `Mission ${index}`, mission_type: "survey", status: "planned", priority: "normal", planned_date: "2026-11-01",
    }));
    renderPage(firstPage, ["safety:read"], { data: { total: 51, planned: 51 } }, (config) => config?.params?.offset === 50 ? [missions[1]] : firstPage);
    await screen.findByText("Mission 0");
    await user.click(screen.getByRole("button", { name: "Next page" }));
    await screen.findByText("Lake inspection");
    expect(api.get).toHaveBeenLastCalledWith("/p1/missions", { params: { limit: 50, offset: 50 } });
    await user.type(screen.getByRole("searchbox", { name: "Search missions" }), "lake");
    await waitFor(() => expect(api.get).toHaveBeenLastCalledWith("/p1/missions", { params: { search: "lake", limit: 50, offset: 0 } }));
    expect(screen.getByRole("button", { name: "Previous page" })).toBeDisabled();
    expect(screen.getByText("Total Missions").nextElementSibling).toHaveTextContent("51");
  });

  it("uses full-table aggregate metrics instead of deriving KPIs from the current list page", async () => {
    renderPage(missions, ["safety:read"], { data: { total: 125, planned: 20, in_progress: 7, completed: 98 } });
    await screen.findByText("Coastal survey");
    expect(screen.getByText("Total Missions").nextElementSibling).toHaveTextContent("125");
    expect(screen.getAllByText("Planned")[0].nextElementSibling).toHaveTextContent("20");
    expect(screen.getAllByText("In Progress")[0].nextElementSibling).toHaveTextContent("7");
    expect(screen.getAllByText("Completed")[0].nextElementSibling).toHaveTextContent("98");
    expect(api.get).toHaveBeenCalledWith("/p1/missions/summary");
  });

  it("keeps mission KPI cards in a loading state until summary data arrives", async () => {
    let resolveSummary!: (response: any) => void;
    const summaryRequest = () => new Promise((resolve) => { resolveSummary = resolve; });
    renderPage(missions, ["safety:read"], summaryRequest);
    expect(screen.getByText("Total Missions").nextElementSibling).toHaveTextContent("…");
    resolveSummary({ data: { total: 125, planned: 20, in_progress: 7, completed: 98 } });
    await waitFor(() => expect(screen.getByText("Total Missions").nextElementSibling).toHaveTextContent("125"));
  });

  it("shows KPI loading and error states and can retry without presenting zeroes", async () => {
    const user = userEvent.setup();
    const summaryRequest = vi.fn()
      .mockRejectedValueOnce(new Error("network"))
      .mockResolvedValueOnce({ data: { total: 125, planned: 20, in_progress: 7, completed: 98 } });
    renderPage(missions, ["safety:read"], summaryRequest);
    expect(await screen.findByRole("alert")).toHaveTextContent("Unable to load mission metrics");
    expect(screen.getByText("Total Missions").nextElementSibling).not.toHaveTextContent("0");
    await user.click(screen.getByRole("button", { name: "Retry mission metrics" }));
    await waitFor(() => expect(screen.getByText("Total Missions").nextElementSibling).toHaveTextContent("125"));
  });

  it("shows mission list-query failures with a retry instead of the empty state", async () => {
    const user = userEvent.setup();
    let attempts = 0;
    renderPage(missions, undefined, undefined, () => {
      attempts += 1;
      if (attempts === 1) throw new Error("mission list unavailable");
      return missions;
    });
    expect(await screen.findByRole("alert")).toHaveTextContent("Unable to load missions");
    expect(screen.queryByText("No missions found.")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Retry missions" }));
    expect(await screen.findByText("Coastal survey")).toBeInTheDocument();
  });

  it("offers only release- and report-valid lifecycle actions", async () => {
    renderPage(lifecycleMissions, ["safety:update", "safety:close"]);
    await screen.findByText("Planned flight");

    const plannedRow = screen.getByRole("row", { name: /m-planned/ });
    expect(within(plannedRow).queryByRole("button", { name: "Start" })).not.toBeInTheDocument();
    expect(within(plannedRow).getByRole("button", { name: "Cancel" })).toBeInTheDocument();

    const releasedRow = screen.getByRole("row", { name: /m-released/ });
    expect(within(releasedRow).getByRole("button", { name: "Start" })).toBeInTheDocument();
    expect(within(releasedRow).getByRole("button", { name: "Abort" })).toBeInTheDocument();

    const activeRow = screen.getByRole("row", { name: /m-active/ });
    expect(within(activeRow).queryByRole("button", { name: "Complete" })).not.toBeInTheDocument();
    expect(within(activeRow).getByRole("button", { name: "Abort" })).toBeInTheDocument();
  });

  it("hides abort actions without the safety close permission", async () => {
    renderPage(lifecycleMissions, ["safety:update"]);
    await screen.findByText("Released flight");
    const releasedRow = screen.getByRole("row", { name: /m-released/ });
    expect(within(releasedRow).getByRole("button", { name: "Start" })).toBeInTheDocument();
    expect(within(releasedRow).queryByRole("button", { name: "Abort" })).not.toBeInTheDocument();
  });
});
