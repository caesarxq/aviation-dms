import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import api from "../api/client";
import { AuthContext } from "../auth/AuthContext";
import { ToastProvider } from "../components/ui/Toast";
import { DangerousGoods } from "./DangerousGoods";

vi.mock("../api/client", () => ({ default: { get: vi.fn(), post: vi.fn() } }));

const shipments = [
  { shipment_id: "DG-1", un_number: "UN3480", proper_shipping_name: "Lithium ion batteries", dg_class: "9", status: "accepted" },
  { shipment_id: "DG-2", un_number: "UN1203", proper_shipping_name: "Motor fuel", dg_class: "3", status: "pending" },
];

function renderPage(permissions: string[], items: typeof shipments = shipments) {
  vi.mocked(api.get).mockResolvedValue({ data: items } as never);
  const profile = { user_id: "u-1", username: "tester", role: "safety", permissions } as never;
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <AuthContext.Provider value={{ profile, state: "authenticated", login: async () => profile, switchRole: async () => profile, logout: async () => {}, refreshProfile: async () => profile, hasPermission: (p: string) => permissions.includes(p) } as never}>
          <DangerousGoods />
        </AuthContext.Provider>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

beforeEach(() => { vi.clearAllMocks(); });

describe("DangerousGoods", () => {
  it("lists DG shipments and shows the create action with safety:create", async () => {
    renderPage(["safety:create"]);
    await screen.findByText("UN3480");
    expect(screen.getByText("Lithium ion batteries")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /New Shipment/ })).toBeInTheDocument();
  });

  it("hides the create action without safety:create permission", async () => {
    renderPage([]);
    await screen.findByText("UN3480");
    expect(screen.queryByRole("button", { name: /New Shipment/ })).not.toBeInTheDocument();
  });

  it("shows the empty state when there are no DG shipments", async () => {
    renderPage(["safety:create"], []);
    expect(await screen.findByText("No DG shipments.")).toBeInTheDocument();
  });
});