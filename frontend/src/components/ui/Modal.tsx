import { useEffect, useRef } from "react";
import { X } from "lucide-react";

import { FormGuide } from "./FormGuide";

interface ModalProps {
  open: boolean;
  onClose: () => void;
  title?: string;
  className?: string;
  description?: string;
  children: React.ReactNode;
}

/**
 * Accessible modal dialog.
 * - Renders into a portal-like fixed overlay (CSS-only, no ReactDOM.createPortal needed).
 * - Closes on Escape key or backdrop click.
 * - Traps focus (basic) and restores scroll on close.
 */
export function Modal({ open, onClose, title, className, description = "Complete the required fields below. Use the examples and guidance provided before saving." , children }: ModalProps) {
  const panelRef = useRef<HTMLDivElement>(null);
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  useEffect(() => {
    if (!open) return;
    const previouslyFocused = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const previousHtmlOverflow = document.documentElement.style.overflow;
    const previousBodyOverflow = document.body.style.overflow;
    document.documentElement.style.overflow = "hidden";
    document.body.style.overflow = "hidden";

    const getFocusableElements = () => Array.from(panelRef.current?.querySelectorAll<HTMLElement>(
      'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
    ) ?? []).filter((element) => element.getAttribute("aria-hidden") !== "true");

    const focusableElements = getFocusableElements();
    (focusableElements[0] ?? panelRef.current)?.focus();

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onCloseRef.current();
        return;
      }
      if (event.key !== "Tab") return;
      const currentFocusableElements = getFocusableElements();
      if (currentFocusableElements.length === 0) {
        event.preventDefault();
        panelRef.current?.focus();
        return;
      }
      const first = currentFocusableElements[0];
      const last = currentFocusableElements[currentFocusableElements.length - 1];
      if (event.shiftKey && (document.activeElement === first || !panelRef.current?.contains(document.activeElement))) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && (document.activeElement === last || !panelRef.current?.contains(document.activeElement))) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", handleKeyDown);

    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.documentElement.style.overflow = previousHtmlOverflow;
      document.body.style.overflow = previousBodyOverflow;
      previouslyFocused?.focus();
    };
  }, [open]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center"
      role="dialog"
      aria-modal="true"
      aria-labelledby={title ? "modal-title" : undefined}
      aria-describedby={description ? "modal-description" : undefined}
      aria-label={title || "Dialog"}
    >
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
      />
      {/* Panel */}
      <div
        ref={panelRef}
        tabIndex={-1}
        className={`relative w-full max-w-lg mx-4 p-3 bg-white rounded-2xl shadow-2xl border border-kfl-border animate-in fade-in zoom-in duration-200 ${className || ""}`}
        onClick={(e) => e.stopPropagation()}
      >
        {title && (
          <div className="flex items-center justify-between pb-3 border-b border-kfl-border mb-4">
            <h3 id="modal-title" className="text-lg font-semibold text-kfl-text">{title}</h3>
            <button
              onClick={onClose}
              className="rounded-md p-1.5 text-kfl-secondary hover:text-kfl-text hover:bg-kfl-surface-subtle transition"
              aria-label="Close dialog"
            >
              <X size={18} />
            </button>
          </div>
        )}
        {description && <FormGuide id="modal-description">{description}</FormGuide>}
        <div className="text-kfl-text">{children}</div>
      </div>
    </div>
  );
}

Modal.displayName = "Modal";
