import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { FeedbackPage } from "./Feedback";
import { safetyApi } from "../api/safety";

vi.mock("../api/safety", () => ({
  safetyApi: {
    listFeedback: vi.fn(),
    createFeedback: vi.fn(),
  },
}));

const queryClient = new QueryClient();

const renderWithProvider = (component: React.ReactElement) =>
  render(
    <QueryClientProvider client={queryClient}>{component}</QueryClientProvider>
  );

describe("FeedbackPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders feedback page with title", () => {
    vi.mocked(safetyApi.listFeedback).mockResolvedValue([]);
    renderWithProvider(<FeedbackPage />);
    expect(screen.getByText(/Pilot Feedback/i)).toBeInTheDocument();
  });

  it("displays feedback items in table", async () => {
    vi.mocked(safetyApi.listFeedback).mockResolvedValue([
      {
        feedback_id: "1",
        ticket_number: "FBK-20260101-0001",
        actor_user_id: "user1",
        actor_role: "pilot",
        source_route: "web",
        issue_type: "bug",
        app_area: "Document Viewer",
        goal: "Test goal",
        impact: "workaround",
        status: "new",
        priority: "medium",
        owner_id: null,
        zoho_form_record_id: null,
        zoho_form_sync_state: "pending",
        zoho_sheet_row_id: null,
        next_update_at: null,
        created_at: "2026-01-01T00:00:00Z",
        updated_at: "2026-01-01T00:00:00Z",
        created_by: "user1",
      },
    ]);
    renderWithProvider(<FeedbackPage />);
    expect(await screen.findByText("FBK-20260101-0001")).toBeInTheDocument();
  });

  it("shows empty state when no feedback", async () => {
    vi.mocked(safetyApi.listFeedback).mockResolvedValue([]);
    renderWithProvider(<FeedbackPage />);
    expect(await screen.findByText(/No feedback found/i)).toBeInTheDocument();
  });

  it("opens submit feedback modal", async () => {
    vi.mocked(safetyApi.listFeedback).mockResolvedValue([]);
    renderWithProvider(<FeedbackPage />);
    fireEvent.click(screen.getAllByText(/Submit Feedback/i)[0]);
    expect(screen.getByText(/New Feedback/i)).toBeInTheDocument();
  });
});
