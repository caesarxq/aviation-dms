import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { safetyApi } from "../api/safety";
import { ToastProvider } from "../components/ui/Toast";
import { ChangeRequests } from "./ChangeRequests";

vi.mock("../api/safety", () => ({
  safetyApi: {
    listChangeRequests: vi.fn(),
    createChangeRequest: vi.fn(),
    submitChangeRequest: vi.fn(),
    reviewChangeRequest: vi.fn(),
    approveChangeRequest: vi.fn(),
    rejectChangeRequest: vi.fn(),
    deleteChangeRequest: vi.fn(),
    listReviewComments: vi.fn(),
    addReviewComment: vi.fn(),
  },
}));

const crs = [
  { cr_id: "CR-1", document_id: "DOC-001", version_id: "v1", title: "Open change", description: "d", change_type: "minor", status: "open", requester_id: "u-lib" },
  { cr_id: "CR-2", document_id: "DOC-002", version_id: "v2", title: "Submitted change", description: "d", change_type: "major", status: "submitted", requester_id: "u-lib" },
  { cr_id: "CR-3", document_id: "DOC-003", version_id: "v3", title: "Approved change", description: "d", change_type: "minor", status: "approved", requester_id: "u-quality" },
];

function renderPage() {
  vi.mocked(safetyApi.listChangeRequests).mockResolvedValue(crs as never);
  vi.mocked(safetyApi.listReviewComments).mockResolvedValue([] as never);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <ChangeRequests />
      </ToastProvider>
    </QueryClientProvider>,
  );
}

beforeEach(() => { vi.clearAllMocks(); });

describe("ChangeRequests", () => {
  it("renders the heading and aggregate status counts from the loaded requests", async () => {
    renderPage();
    expect(screen.getByRole("heading", { name: "Change Requests" })).toBeInTheDocument();
    await screen.findByText("CR-1");
    expect(screen.getByText("Total").nextElementSibling).toHaveTextContent("3");
    expect(screen.getByText("Open").nextElementSibling).toHaveTextContent("1");
    expect(screen.getByText("Submitted").nextElementSibling).toHaveTextContent("1");
    expect(screen.getByText("Approved").nextElementSibling).toHaveTextContent("1");
    expect(screen.getByText("Rejected").nextElementSibling).toHaveTextContent("0");
    expect(safetyApi.listChangeRequests).toHaveBeenCalled();
  });

  it("offers edit/delete only for open requests, not submitted or approved ones", async () => {
    renderPage();
    await screen.findByText("CR-1");
    expect(screen.getByRole("button", { name: "Delete change request CR-1" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Delete change request CR-2" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Delete change request CR-3" })).not.toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "Edit" })).toHaveLength(1);
    // Every row keeps a View action.
    expect(screen.getAllByRole("button", { name: "View" })).toHaveLength(3);
  });

  it("opens the create form with a title field from the New Change Request action", async () => {
    const user = userEvent.setup({ pointerEventsCheck: 0 });
    renderPage();
    await screen.findByText("CR-1");
    await user.click(screen.getByRole("button", { name: /New Change Request/ }));
    expect(await screen.findByRole("heading", { name: "New Change Request" })).toBeInTheDocument();
    expect(document.querySelector('input[name="title"]')).toBeInTheDocument();
  });
});