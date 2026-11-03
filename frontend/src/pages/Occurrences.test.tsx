import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AuthContext } from "../auth/AuthContext";
import { safetyApi } from "../api/safety";
import { Occurrences } from "./Occurrences";

vi.mock("../api/safety", () => ({ safetyApi: { listOccurrences: vi.fn(), createOccurrence: vi.fn() } }));

const records = [
  { occurrence_id: "occ-1", serial_number: "OCC-2026-0001", title: "Runway incursion", occurrence_type: "incident", severity: "major", status: "reported", location: "Nairobi" },
  { occurrence_id: "occ-2", serial_number: "OCC-2026-0002", title: "Bird strike", occurrence_type: "near_miss", severity: "minor", status: "closed", location: "Mombasa" },
];

function Location() {
  const location = useLocation();
  return <output data-testid="path">{location.pathname}</output>;
}

function renderPage(permissions = ["safety:read", "safety:create"]) {
  const profile = {
    user: { user_id: "u1", username: "user", email: "user@example.test", full_name: "User", role: "head_safety", active_role: "head_safety", roles: ["head_safety"] },
    role: "head_safety", active_role: "head_safety", roles: ["head_safety"], authenticated_via: "session_cookie", onboarding_completed: true, permissions,
  };
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <AuthContext.Provider value={{ profile, state: "authenticated", login: async () => profile, switchRole: async () => profile, logout: async () => {}, refreshProfile: async () => profile, hasPermission: (permission) => permissions.includes(permission) }}>
        <MemoryRouter initialEntries={["/occurrences"]}>
          <Location />
          <Routes>
            <Route path="/occurrences" element={<Occurrences />} />
            <Route path="/occurrences/:occurrenceId" element={<div>Occurrence detail route</div>} />
          </Routes>
        </MemoryRouter>
      </AuthContext.Provider>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(safetyApi.listOccurrences).mockResolvedValue(records as never);
});

describe("Occurrences list controls", () => {
  it("filters by independent search and status controls and opens the occurrence route", async () => {
    const user = userEvent.setup();
    renderPage();
    expect(await screen.findByText("Runway incursion")).toBeInTheDocument();

    await user.type(screen.getByRole("searchbox", { name: "Search occurrences" }), "Bird");
    expect(screen.getByText("Bird strike")).toBeInTheDocument();
    expect(screen.queryByText("Runway incursion")).not.toBeInTheDocument();
    await user.clear(screen.getByRole("searchbox", { name: "Search occurrences" }));
    await user.selectOptions(screen.getByRole("combobox", { name: "Filter occurrences by status" }), "reported");
    expect(screen.getByText("Runway incursion")).toBeInTheDocument();
    expect(screen.queryByText("Bird strike")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Open OCC-2026-0001" }));
    expect(screen.getByTestId("path")).toHaveTextContent("/occurrences/occ-1");
  });

  it("keeps search text independent from the occurrence title form field", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("Runway incursion");
    await user.type(screen.getByRole("searchbox", { name: "Search occurrences" }), "runway");
    await user.click(screen.getByRole("button", { name: "Report Occurrence" }));
    expect(screen.getByLabelText(/Occurrence title/)).toHaveValue("");
    expect(screen.getByRole("searchbox", { name: "Search occurrences" })).toHaveValue("runway");
  });

  it("shows the load failure separately from an empty list and offers retry", async () => {
    vi.mocked(safetyApi.listOccurrences).mockRejectedValueOnce(new Error("network"));
    renderPage();
    expect(await screen.findByRole("alert")).toHaveTextContent("Unable to load occurrences");
    expect(screen.queryByText("No occurrences reported.")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Retry loading occurrences" }));
    await waitFor(() => expect(safetyApi.listOccurrences).toHaveBeenCalledTimes(2));
  });

  it("hides reporting controls when the profile lacks create permission", async () => {
    renderPage(["safety:read"]);
    await screen.findByText("Runway incursion");
    expect(screen.queryByRole("button", { name: "Report Occurrence" })).not.toBeInTheDocument();
  });
});
