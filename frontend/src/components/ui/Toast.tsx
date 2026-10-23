import { createContext, useCallback, useContext, useMemo, useState } from "react";

export type ToastType = "success" | "error" | "warning" | "info";

export interface Toast {
  id: string;
  title: string;
  message?: string;
  type: ToastType;
  duration?: number;
}

interface ToastContextValue {
  toasts: Toast[];
  toast: (toast: Omit<Toast, "id">) => void;
  dismiss: (id: string) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

let idCounter = 0;

function nextId(): string {
  idCounter += 1;
  return String(idCounter);
}

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const dismiss = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const toast = useCallback((t: Omit<Toast, "id">) => {
    const id = nextId();
    const entry: Toast = { ...t, id, duration: t.duration ?? 4000 };
    setToasts((prev) => [entry, ...prev]);
    if (entry.duration && entry.duration > 0) {
      setTimeout(() => dismiss(entry.id), entry.duration);
    }
    return id;
  }, [dismiss]);

  const value = useMemo<ToastContextValue>(
    () => ({ toasts, toast, dismiss }),
    [toasts, toast, dismiss]
  );

  return (
    <ToastContext.Provider value={value}>
      {children}
      <ToastList />
    </ToastContext.Provider>
  );
}

function ToastList() {
  const { toasts, dismiss } = useContext(ToastContext) as ToastContextValue;
  return (
    <div className="fixed top-4 right-4 z-[200] flex flex-col gap-2 pointer-events-none">
      {toasts.map((t) => (
        <div
          key={t.id}
          className={`pointer-events-auto flex w-64 items-start gap-3 rounded-xl border p-4 shadow-lg animate-in slide-in-from-top duration-200 ${
            t.type === "success"
              ? "border-emerald-200 bg-emerald-50/90 text-emerald-900"
              : t.type === "error"
              ? "border-rose-200 bg-rose-50/90 text-rose-900"
              : t.type === "warning"
              ? "border-amber-200 bg-amber-50/90 text-amber-900"
              : "border-blue-200 bg-blue-50/90 text-blue-900"
          }`}
        >
          <div className="flex-1">
            <h4 className="text-sm font-semibold">{t.title}</h4>
            {t.message && (
              <p className="mt-1 text-xs opacity-85">{t.message}</p>
            )}
          </div>
          <button
            onClick={() => dismiss(t.id)}
            className="rounded-md p-1 opacity-60 hover:opacity-100 transition"
            aria-label="Dismiss"
          >
            <span className="block w-4 h-4" />
          </button>
        </div>
      ))}
    </div>
  );
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used within a ToastProvider");
  return ctx;
}

export default ToastProvider;
