import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import api from "../api/client";
import { AuthContext } from "../auth/AuthContext";
import { ToastProvider } from "../components/ui/Toast";
import { QualityAudits } from "./QualityAudits";

vi.mock("../api/client", () => ({ default: { get: vi.fn(), post: vi.fn() } }));

const audits = [
  { audit_id: "QA-1", title: "Annual quality audit", audit_type: "internal", status: "completed" },
  { audit_id: "QA-2", title: "Supplier audit", audit_type: "external", status: "in_progress" },
  { audit_id: "QA-3", title: "Planned audit", audit_type: "internal", status: "scheduled" },
];

function statValue(label: string) {
  const el = screen.getAllByText(label).find((n) => n.classList.contains("app-label"));
  return el!.nextElementSibling as HTMLElement;
}

function renderPage(permissions: string[], items: typeof audits = audits) {
  vi.mocked(api.get).mockResolvedValue({ data: items } as never);
  const profile = { user_id: "u-1", username: "tester", role: "quality", permissions } as never;
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <AuthContext.Provider value={{ profile, state: "authenticated", login: async () => profile, switchRole: async () => profile, logout: async () => {}, refreshProfile: async () => profile, hasPermission: (p: string) => permissions.includes(p) } as never}>
          <QualityAudits />
        </AuthContext.Provider>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

beforeEach(() => { vi.clearAllMocks(); });

describe("QualityAudits", () => {
  it("computes total/completed/in-progress stats and lists the audits", async () => {
    renderPage(["safety:create"]);
    await screen.findByText("QA-1");
    expect(statValue("Total Audits")).toHaveTextContent("3");
    expect(statValue("Completed")).toHaveTextContent("1");
    expect(statValue("In Progress")).toHaveTextContent("1");
    expect(screen.getByText("Annual quality audit")).toBeInTheDocument();
    expect(screen.getByText("external")).toBeInTheDocument();
  });

  it("hides the create actions without safety:create permission", async () => {
    renderPage([]);
    await screen.findByText("QA-1");
    expect(screen.queryByRole("button", { name: /New Audit/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Create CAR/ })).not.toBeInTheDocument();
  });

  it("shows the empty state when there are no audits", async () => {
    renderPage(["safety:create"], []);
    expect(await screen.findByText("No quality audits.")).toBeInTheDocument();
    expect(statValue("Total Audits")).toHaveTextContent("0");
  });
});