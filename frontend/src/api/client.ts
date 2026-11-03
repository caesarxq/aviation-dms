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
    return Promise.reject(error);
  },
);

export default api;

