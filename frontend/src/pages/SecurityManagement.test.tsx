import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import api from "../api/client";
import { AuthContext } from "../auth/AuthContext";
import { ToastProvider } from "../components/ui/Toast";
import { SecurityManagement } from "./SecurityManagement";

vi.mock("../api/client", () => ({ default: { get: vi.fn(), post: vi.fn() } }));

function statValue(label: string) {
  const el = screen.getAllByText(label).find((n) => n.classList.contains("app-label"));
  return el!.nextElementSibling as HTMLElement;
}

function renderPage(permissions: string[]) {
  vi.mocked(api.get).mockImplementation((url: string) => {
    if (url.includes("/summary")) return Promise.resolve({ data: { total: 5, critical_high: 2, open: 3 } });
    if (url.includes("/p1/security-incidents")) return Promise.resolve({ data: [{ incident_id: "SEC-1", title: "Unauthorized access", status: "reported", severity: "high" }] });
    return Promise.resolve({ data: [] });
  });
  const profile = { user_id: "u-1", username: "tester", role: "security", permissions } as never;
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <AuthContext.Provider value={{ profile, state: "authenticated", login: async () => profile, switchRole: async () => profile, logout: async () => {}, refreshProfile: async () => profile, hasPermission: (p: string) => permissions.includes(p) } as never}>
          <SecurityManagement />
        </AuthContext.Provider>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

beforeEach(() => { vi.clearAllMocks(); });

describe("SecurityManagement RBAC", () => {
  it("restricts incident details and hides metrics without security:read_sensitive", async () => {
    renderPage([]);
    expect(await screen.findByText(/restricted to users with security:read_sensitive access/)).toBeInTheDocument();
    expect(screen.queryByText("Total Incidents")).not.toBeInTheDocument();
    expect(screen.queryByText("Unauthorized access")).not.toBeInTheDocument();
  });

  it("shows incident metrics and the incident list with security:read_sensitive", async () => {
    renderPage(["security:read_sensitive"]);
    expect(await screen.findByText("Total Incidents")).toBeInTheDocument();
    await waitFor(() => expect(statValue("Total Incidents")).toHaveTextContent("5"));
    expect(statValue("Critical / High")).toHaveTextContent("2");
    expect(statValue("Open")).toHaveTextContent("3");
    expect(await screen.findByText("Unauthorized access")).toBeInTheDocument();
    expect(screen.queryByText(/restricted to users with security:read_sensitive access/)).not.toBeInTheDocument();
  });
});