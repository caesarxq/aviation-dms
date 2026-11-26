import { useCallback, useEffect } from "react";
import { useToast } from "./Toast";

/**
 * Global API error toaster.
 *
 * The axios client dispatches a `kfl:api-error` CustomEvent for unexpected
 * responses (403, 404, 429, 500) that components do not handle inline. This
 * component listens for those events and renders a toast, so users are never
 * left staring at a silent failure.
 *
 * Mount once inside the ToastProvider (e.g. in App.tsx).
 */

declare global {
  interface WindowEventMap {
    "kfl:api-error": CustomEvent<{
      status: number;
      url: string;
      message: string;
    }>;
  }
}

export function ErrorToaster() {
  const { toast } = useToast();

  const handleApiError = useCallback(
    (event: CustomEvent<{ status: number; url: string; message: string }>) => {
      const { status, message } = event.detail;
      const title =
        status === 403
          ? "Not permitted"
          : status === 404
          ? "Not found"
          : status === 429
          ? "Too many requests"
          : "Request failed";
      toast({ title, message, type: "error", duration: 6000 });
    },
    [toast],
  );

  useEffect(() => {
    window.addEventListener("kfl:api-error", handleApiError);
    return () => window.removeEventListener("kfl:api-error", handleApiError);
  }, [handleApiError]);

  return null;
}

export default ErrorToaster;
