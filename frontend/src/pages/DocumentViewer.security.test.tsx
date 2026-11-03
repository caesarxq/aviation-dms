import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import api from "../api/client";
import { DocumentViewer } from "./DocumentViewer";

vi.mock("../api/client", () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
  },
}));

const hostileDocument = `<!doctype html><html><body><h1>Controlled text</h1><script>parent.document.body.dataset.xss = 'executed'</script><img src=x onerror="parent.document.body.dataset.xss='executed'"></body></html>`;

function renderViewer() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/documents/DOC-1"]}>
        <Routes>
          <Route path="/documents/:docId" element={<DocumentViewer />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.mocked(api.get).mockImplementation((url: string) => Promise.resolve({
    data: url.includes("/annotations") ? [] : { content: hostileDocument, version_number: 1, state: "draft", kcaa_approved: false },
  }) as never);
  document.body.removeAttribute("data-xss");
});

describe("DocumentViewer untrusted document boundary", () => {
  it("renders source HTML in a script-disabled sandbox without executable content or bridges", async () => {
    renderViewer();
    const frame = await screen.findByTitle("DOC-1") as HTMLIFrameElement;

    await screen.findByText(/Version 1/);
    expect(frame.getAttribute("sandbox")).toBe("allow-same-origin");
    expect(frame.getAttribute("sandbox")).not.toMatch(/allow-scripts|allow-popups|allow-top-navigation/);
    expect(frame.srcdoc).toContain("<script>");
    expect(frame.srcdoc).toContain("Content-Security-Policy");
    expect(frame.srcdoc).not.toContain("TEXT_SELECTED");
    expect(frame.srcdoc).not.toContain("RENDER_HIGHLIGHTS");
    expect(document.querySelectorAll("script")).toHaveLength(0);
    expect(screen.getByText(/Select text in the document to create a comment or highlight/)).toBeInTheDocument();
    expect(document.body).not.toHaveAttribute("data-xss", "executed");
  });

  it("escapes plain-text manuals before placing them in the iframe document", async () => {
    const plainText = "# Test manual <script>parent.document.body.dataset.xss='bad'</script>";
    vi.mocked(api.get).mockImplementation((url: string) => Promise.resolve({
      data: url.includes("/annotations") ? [] : { content: plainText, version_number: 1, state: "published", kcaa_approved: true },
    }) as never);
    renderViewer();
    const frame = await screen.findByTitle("DOC-1") as HTMLIFrameElement;
    await screen.findByText(/Version 1/);
    expect(frame.srcdoc).toContain("<pre>");
    expect(frame.srcdoc).toContain("&lt;script&gt;");
    expect(frame.srcdoc).not.toContain("<script>");
  });

  it("creates an annotation from a selection observed by the trusted parent", async () => {
    vi.mocked(api.post).mockResolvedValue({ data: { annotation_id: "ANN-1" } } as never);
    renderViewer();
    const frame = await screen.findByTitle("DOC-1") as HTMLIFrameElement;
    await screen.findByText(/Version 1/);
    const frameDocument = frame.contentDocument;
    const frameWindow = frame.contentWindow;
    expect(frameDocument).toBeTruthy();
    expect(frameWindow).toBeTruthy();
    frameDocument!.body.innerHTML = "<p>select this controlled text</p>";
    fireEvent.load(frame);

    const textNode = frameDocument!.querySelector("p")!.firstChild!;
    const range = frameDocument!.createRange();
    range.selectNodeContents(textNode);
    const selection = frameWindow!.getSelection();
    selection!.removeAllRanges();
    selection!.addRange(range);
    fireEvent.mouseUp(frameDocument!.body);

    expect(await screen.findByText(/Selected: "select this controlled text"/)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Comment"), { target: { value: "Review this procedure" } });
    fireEvent.change(screen.getByLabelText("Target reference"), { target: { value: "Section 1.1" } });
    fireEvent.click(screen.getByRole("button", { name: "Add Annotation" }));

    await waitFor(() => expect(api.post).toHaveBeenCalledWith("/p2/documents/DOC-1/annotations", expect.objectContaining({
      annotation_type: "comment",
      target_ref: "Section 1.1 — Selected text: select this controlled text",
      content: "Review this procedure",
    })));
  });

  it("creates an annotation when text is selected with the keyboard", async () => {
    vi.mocked(api.post).mockResolvedValue({ data: { annotation_id: "ANN-KEYBOARD" } } as never);
    renderViewer();
    const frame = await screen.findByTitle("DOC-1") as HTMLIFrameElement;
    await screen.findByText(/Version 1/);
    const frameDocument = frame.contentDocument!;
    const frameWindow = frame.contentWindow!;
    frameDocument.body.innerHTML = "<p>keyboard selected text</p>";
    fireEvent.load(frame);

    const textNode = frameDocument.querySelector("p")!.firstChild!;
    const range = frameDocument.createRange();
    range.setStart(textNode, 0);
    range.setEnd(textNode, "keyboard selected text".length);
    const selection = frameWindow.getSelection()!;
    selection.removeAllRanges();
    selection.addRange(range);
    fireEvent.keyUp(frameDocument.body, { key: "ArrowRight", shiftKey: true });

    expect(await screen.findByText(/Selected: "keyboard selected text"/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Add Annotation" }));
    await waitFor(() => expect(api.post).toHaveBeenCalledWith("/p2/documents/DOC-1/annotations", expect.objectContaining({
      target_ref: "Selected text: keyboard selected text",
    })));
  });

  it("moves focus into the annotation dialog and restores it to the document frame on cancel", async () => {
    renderViewer();
    const frame = await screen.findByTitle("DOC-1") as HTMLIFrameElement;
    await screen.findByText(/Version 1/);
    const frameDocument = frame.contentDocument!;
    const frameWindow = frame.contentWindow!;
    frameDocument.body.innerHTML = "<p>focus this text</p>";
    fireEvent.load(frame);
    frame.focus();

    const textNode = frameDocument.querySelector("p")!.firstChild!;
    const range = frameDocument.createRange();
    range.selectNodeContents(textNode);
    frameWindow.getSelection()!.addRange(range);
    fireEvent.mouseUp(frameDocument.body);

    const dialog = await screen.findByRole("dialog", { name: "Add document annotation" });
    expect(dialog.contains(document.activeElement)).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(document.activeElement).toBe(frame);
  });

  it("ignores a same-origin selection message from anything other than the expected iframe", async () => {
    renderViewer();
    await screen.findByText(/Version 1/);

    fireEvent(window, new MessageEvent("message", {
      origin: window.location.origin,
      source: window,
      data: { type: "TEXT_SELECTED", payload: { text: "forged", x: 10, y: 20 } },
    }));

    expect(screen.queryByText(/Selected:/)).not.toBeInTheDocument();
  });

  it("ignores malformed selection messages from the expected iframe", async () => {
    renderViewer();
    const frame = await screen.findByTitle("DOC-1") as HTMLIFrameElement;
    await screen.findByText(/Version 1/);

    fireEvent(window, new MessageEvent("message", {
      origin: window.location.origin,
      source: frame.contentWindow,
      data: { type: "TEXT_SELECTED", payload: { text: "malformed", x: Number.NaN, y: "20" } },
    }));

    expect(screen.queryByText(/Selected:/)).not.toBeInTheDocument();
  });
});
