import axios, { AxiosError, InternalAxiosRequestConfig } from "axios";

const api = axios.create({ baseURL: "/api", withCredentials: true });

function readCsrfToken(): string | null {
  if (typeof document === "undefined") return null;
  const values = document.cookie.split(";").map((part) => part.trim());
  const csrfCookie = values.find((part) => part.startsWith("__Host-kfl_csrf="))
    ?? values.find((part) => part.startsWith("kfl_csrf="));
  if (!csrfCookie) return null;
  return decodeURIComponent(csrfCookie.substring(csrfCookie.indexOf("=") + 1));
}

api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  config.withCredentials = true;
  const method = (config.method || "get").toLowerCase();
  if (!["get", "head", "options"].includes(method)) {
    const csrfToken = readCsrfToken();
    if (csrfToken) config.headers["X-CSRF-Token"] = csrfToken;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    const status = error.response?.status;
    const url = error.config?.url || "";
    const credentialRoute = /\/auth\/(login|bootstrap|bootstrap-status|password-setup|change-password|forgot-password|reset-password)/.test(url);
    if (status === 401 && !credentialRoute && typeof window !== "undefined") {
      window.dispatchEvent(new Event("kfl:session-expired"));
    }
    // Surface unexpected API errors globally so users are never left staring
    // at a silent failure. Components that show their own inline error UI
    // handle 400/422 themselves; we surface 403/404/429/500 here as a safety net.
    if (
      typeof window !== "undefined" &&
      status &&
      status !== 401 &&
      [403, 404, 429, 500].includes(status)
    ) {
      const detail =
        (error.response?.data as { detail?: string } | undefined)?.detail ||
        (typeof error.response?.data === "string" ? error.response.data : undefined) ||
        error.message;
      const evt = new CustomEvent("kfl:api-error", {
        detail: { status, url, message: String(detail || `Request failed (${status})`) } as unknown as CustomEventInit<{
          status: number;
          url: string;
          message: string;
        }>["detail"],
      });
      window.dispatchEvent(evt);
    }
    return Promise.reject(error);
  },
);

export default api;

