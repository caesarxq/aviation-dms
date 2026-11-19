import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { safetyApi } from "../api/safety";
import { ToastProvider } from "../components/ui/Toast";
import { TrainingManagement } from "./TrainingManagement";

vi.mock("../api/safety", () => ({
  safetyApi: {
    listTrainingRecords: vi.fn(),
    createTrainingRecord: vi.fn(),
    updateTrainingRecord: vi.fn(),
    deleteTrainingRecord: vi.fn(),
  },
}));

const records = [
  { record_id: "TRN-1", person_id: "P-1", training_category: "general", training_type: "CRM", status: "valid", training_date: "2026-01-01", expiry_date: "2027-01-01", certificate_number: "", notes: "" },
  { record_id: "TRN-2", person_id: "P-2", training_category: "safety", training_type: "Dangerous Goods", status: "valid", training_date: "2026-02-01", expiry_date: "2027-02-01", certificate_number: "", notes: "" },
  { record_id: "TRN-3", person_id: "P-3", training_category: "general", training_type: "Security Awareness", status: "expired", training_date: "2025-01-01", expiry_date: "2026-01-01", certificate_number: "", notes: "" },
];

function renderPage(items: typeof records = records) {
  vi.mocked(safetyApi.listTrainingRecords).mockResolvedValue(items as never);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <TrainingManagement />
      </ToastProvider>
    </QueryClientProvider>,
  );
}

beforeEach(() => { vi.clearAllMocks(); });

describe("TrainingManagement", () => {
  it("computes total/valid/expired stats and lists the training records", async () => {
    renderPage();
    expect(screen.getByRole("heading", { name: "Training Management" })).toBeInTheDocument();
    await screen.findByText("TRN-1");
    // 3 records: 2 valid, 1 expired.
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
    expect(screen.getByText("1")).toBeInTheDocument();
    expect(screen.getByText("CRM")).toBeInTheDocument();
    expect(screen.getByText("Dangerous Goods")).toBeInTheDocument();
    expect(screen.getByText("Security Awareness")).toBeInTheDocument();
  });

  it("shows zeroed stats and the empty state when there are no records", async () => {
    renderPage([]);
    expect(await screen.findByText("No training records found.")).toBeInTheDocument();
    expect(screen.getAllByText("0")).toHaveLength(3);
  });
});