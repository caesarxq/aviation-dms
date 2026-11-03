import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import api from "../api/client";
import { AuthContext } from "../auth/AuthContext";
import { ToastProvider } from "../components/ui/Toast";
import { DocumentEditor } from "./DocumentEditor";

vi.mock("../api/client", () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
  },
}));

const hostileDocument = `<h1>Controlled proposal</h1><p onclick="window.appXss = true">Safe text</p><img src="x" onerror="window.appXss = true"><script>window.appXss = true</script><a href="javascript:window.appXss=true">link</a>`;

function renderEditor() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const permissions = ["document:read", "document:update", "document:propose"];
  const profile = {
    user: { user_id: "u1", username: "user", email: "u@example.test", full_name: "User", role: "librarian", active_role: "librarian", roles: ["librarian"] },
    role: "librarian",
    active_role: "librarian",
    roles: ["librarian"],
    authenticated_via: "session_cookie",
    onboarding_completed: true,
    permissions,
  };
  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <AuthContext.Provider value={{
          profile,
          state: "authenticated",
          login: async () => profile,
          switchRole: async () => profile,
          logout: async () => {},
          refreshProfile: async () => profile,
          hasPermission: (permission) => permissions.includes(permission),
        }}>
          <MemoryRouter initialEntries={["/documents/DOC-1/edit"]}>
            <Routes>
              <Route path="/documents/:docId/edit" element={<DocumentEditor />} />
            </Routes>
          </MemoryRouter>
        </AuthContext.Provider>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.mocked(api.get).mockResolvedValue({ data: { content: hostileDocument, version_number: 1 } } as never);
  vi.mocked(api.put).mockResolvedValue({ data: {} } as never);
  (window as Window & { appXss?: boolean }).appXss = false;
});

describe("DocumentEditor untrusted proposal HTML", () => {
  it("sanitizes stored HTML before placing it in the editable proposal surface", async () => {
    renderEditor();
    const editor = await waitFor(() => {
      const element = document.querySelector('[contenteditable="true"]');
      expect(element).toBeInTheDocument();
      expect(element?.textContent).toContain("Controlled proposal");
      return element as HTMLElement;
    });

    expect(editor.querySelector("script")).not.toBeInTheDocument();
    expect(editor.querySelector("[onclick], [onerror]")).not.toBeInTheDocument();
    expect(editor.querySelector("a")?.getAttribute("href")).toBeNull();
    expect(editor.querySelector("h1")).toHaveTextContent("Controlled proposal");
    expect((window as Window & { appXss?: boolean }).appXss).toBe(false);
  });

  it("blocks lossy direct saves for manuals with embedded styles", async () => {
    const formattedManual = `<html><head><style>.pf{position:absolute;font-family:Embedded}</style></head><body><div id="page-container"><div class="pf" style="position:absolute"><span class="t">Page title</span></div></div></body></html>`;
    vi.mocked(api.get).mockResolvedValue({ data: { content: formattedManual, version_number: 1 } } as never);
    renderEditor();
    const editor = await waitFor(() => {
      const element = document.querySelector('[contenteditable="true"]');
      expect(element).toBeInTheDocument();
      expect(element?.textContent).toContain("Page title");
      return element as HTMLElement;
    });
    editor.insertAdjacentHTML("beforeend", "<p>edited</p>");
    fireEvent.input(editor);
    const save = await screen.findByRole("button", { name: "Save as Draft" });
    expect(save).toBeDisabled();
    expect(screen.getByText(/Direct draft saving is disabled for this formatted manual/)).toBeInTheDocument();
    fireEvent.click(save);
    expect(api.put).not.toHaveBeenCalled();
  });

  it("blocks saves when formatting depends on a linked stylesheet", async () => {
    const linkedStylesheetManual = `<html><head><link rel="stylesheet" href="/manual.css"></head><body><p>Page title</p></body></html>`;
    vi.mocked(api.get).mockResolvedValue({ data: { content: linkedStylesheetManual, version_number: 1 } } as never);
    renderEditor();
    await screen.findByText("Page title");
    const save = await screen.findByRole("button", { name: "Save as Draft" });
    expect(save).toBeDisabled();
    expect(screen.getByText(/Direct draft saving is disabled for this formatted manual/)).toBeInTheDocument();
    fireEvent.click(save);
    expect(api.put).not.toHaveBeenCalled();
  });

  it("blocks proposal previews and submissions for formatted manuals it cannot preserve", async () => {
    const formattedManual = `<html><head><style>.pf{position:absolute;font-family:Embedded}</style></head><body><div id="page-container"><div class="pf" style="position:absolute"><span class="t">Page title</span></div></div></body></html>`;
    vi.mocked(api.get).mockResolvedValue({ data: { content: formattedManual, version_number: 1 } } as never);
    renderEditor();
    const editor = await waitFor(() => {
      const element = document.querySelector('[contenteditable="true"]');
      expect(element).toBeInTheDocument();
      expect(element?.textContent).toContain("Page title");
      return element as HTMLElement;
    });

    editor.insertAdjacentHTML("beforeend", "<p>edited manual content</p>");
    fireEvent.input(editor);
    const preservationWarning = screen.getByText(/Direct draft saving is disabled for this formatted manual/);
    expect(preservationWarning).toHaveTextContent(/proposal submission is also disabled/i);
    const submitProposal = screen.getByRole("button", { name: "Submit proposal for review" });
    expect(submitProposal).toBeDisabled();
    fireEvent.click(submitProposal);
    expect(api.post).not.toHaveBeenCalled();
  });

  it("sanitizes rich-text edits before they are saved as a proposal", async () => {
    renderEditor();
    const editor = await waitFor(() => {
      const element = document.querySelector('[contenteditable="true"]');
      expect(element).toBeInTheDocument();
      expect(element?.textContent).toContain("Controlled proposal");
      return element as HTMLElement;
    });

    editor.insertAdjacentHTML("beforeend", `<img src=x onerror="window.appXss=true"><script>window.appXss=true</script><strong>new text</strong>`);
    fireEvent.input(editor);

    expect(editor.querySelector("script, [onerror]")).not.toBeInTheDocument();
    await waitFor(() => expect(editor).toHaveTextContent("new text"));
    expect((window as Window & { appXss?: boolean }).appXss).toBe(false);

    fireEvent.click(screen.getByRole("button", { name: "Save as Draft" }));
    await waitFor(() => expect(api.put).toHaveBeenCalled());
    const savedContent = (vi.mocked(api.put).mock.calls[0]?.[1] as { content: string }).content;
    expect(savedContent).toContain("new text");
    expect(savedContent).not.toMatch(/<script|onerror|javascript:/i);
  });

  it("sanitizes clipboard HTML before inserting it into the editable surface", async () => {
    renderEditor();
    const editor = await waitFor(() => {
      const element = document.querySelector('[contenteditable="true"]');
      expect(element).toBeInTheDocument();
      expect(element?.textContent).toContain("Controlled proposal");
      return element as HTMLElement;
    });
    const clipboardHtml = `<img src=x onerror="window.appXss=true"><script>window.appXss=true</script><strong>pasted safely</strong>`;
    const originalDescriptor = Object.getOwnPropertyDescriptor(document, "execCommand");
    const execCommand = vi.fn((command: string, _showUi: boolean, value: string) => {
      if (command === "insertHTML") editor.insertAdjacentHTML("beforeend", value);
      return true;
    });
    Object.defineProperty(document, "execCommand", { configurable: true, value: execCommand });

    try {
      fireEvent.paste(editor, {
        clipboardData: { getData: (type: string) => type === "text/html" ? clipboardHtml : "" },
      });

      expect(execCommand).toHaveBeenCalledWith("insertHTML", false, expect.not.stringContaining("onerror"));
      expect(execCommand).toHaveBeenCalledWith("insertHTML", false, expect.not.stringContaining("<script"));
      expect(editor).toHaveTextContent("pasted safely");
      expect(editor.querySelector("script, [onerror]")).not.toBeInTheDocument();
      expect((window as Window & { appXss?: boolean }).appXss).toBe(false);
    } finally {
      if (originalDescriptor) Object.defineProperty(document, "execCommand", originalDescriptor);
      else Reflect.deleteProperty(document, "execCommand");
    }
  });
});
