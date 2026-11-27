import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { FloatingFeedbackButton } from "./FloatingFeedbackButton";
import { ToastProvider } from "./ui/Toast";

vi.mock("../api/safety", () => ({
  safetyApi: {
    createFeedback: vi.fn(),
    uploadFeedbackMedia: vi.fn(),
  },
}));

import { safetyApi } from "../api/safety";

function renderFeedbackButton() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <FloatingFeedbackButton />
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("FloatingFeedbackButton", () => {
  beforeEach(() => vi.clearAllMocks());

  it("confirms cancellation without claiming the draft was submitted", async () => {
    const user = userEvent.setup();
    renderFeedbackButton();

    await user.click(screen.getByRole("button", { name: "Submit feedback" }));
    await user.click(screen.getByRole("button", { name: "Cancel" }));

    expect(await screen.findByText("Feedback form closed. Nothing was submitted.")).toBeInTheDocument();
    expect(safetyApi.createFeedback).not.toHaveBeenCalled();
  });

  it("keeps a saved feedback id and retries only a failed attachment", async () => {
    const user = userEvent.setup();
    vi.mocked(safetyApi.createFeedback).mockResolvedValue({ feedback_id: "FBK-TEST-1" } as never);
    vi.mocked(safetyApi.uploadFeedbackMedia)
      .mockRejectedValueOnce(new Error("scanner unavailable"))
      .mockResolvedValueOnce({ media_url: "/media" } as never);
    renderFeedbackButton();

    await user.click(screen.getByRole("button", { name: "Submit feedback" }));
    await user.type(screen.getByLabelText("Goal"), "Report a page problem");
    await user.type(screen.getByLabelText("Contact"), "u-quality");
    const file = new File(["image"], "capture.png", { type: "image/png" });
    await user.upload(screen.getByLabelText("Media / Screenshot"), file);
    await user.click(screen.getByRole("button", { name: "Submit" }));

    expect(await screen.findByRole("status")).toHaveTextContent("Feedback saved as FBK-TEST-1");
    expect(safetyApi.createFeedback).toHaveBeenCalledTimes(1);
    await user.click(screen.getByRole("button", { name: "Retry attachment" }));
    expect(await screen.findByText(/saved feedback now includes its attachment/i)).toBeInTheDocument();
    expect(safetyApi.createFeedback).toHaveBeenCalledTimes(1);
    expect(safetyApi.uploadFeedbackMedia).toHaveBeenCalledTimes(2);
    expect(safetyApi.uploadFeedbackMedia).toHaveBeenLastCalledWith("FBK-TEST-1", file);
  });
});
