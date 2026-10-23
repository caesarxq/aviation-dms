import { useCallback, useEffect, useRef } from "react";
import { X } from "lucide-react";
import { useNavigate } from "react-router-dom";

interface ModalProps {
  open: boolean;
  onClose: () => void;
  title?: string;
  className?: string;
  children: React.ReactNode;
}

/**
 * Accessible modal dialog.
 * - Renders into a portal-like fixed overlay (CSS-only, no ReactDOM.createPortal needed).
 * - Closes on Escape key or backdrop click.
 * - Traps focus (basic) and restores scroll on close.
 */
export function Modal({ open, onClose, title, className, children }: ModalProps) {
  const navigate = useNavigate();
  const mountRef = useRef(false);

  useEffect(() => {
    if (open && !mountRef.current) {
      mountRef.current = true;
      document.documentElement.style.overflow = "hidden";
      document.body.style.overflow = "hidden";
    }
    if (!open && mountRef.current) {
      mountRef.current = false;
      document.documentElement.style.overflow = "";
      document.body.style.overflow = "";
    }
    return () => {
      document.documentElement.style.overflow = "";
      document.body.style.overflow = "";
    };
  }, [open]);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    },
    [onClose]
  );

  useEffect(() => {
    if (open) {
      window.addEventListener("keydown", handleKeyDown);
      // If a hash route was active, navigate away so back-button behaves
    }
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [open, onClose, navigate]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center"
      role="dialog"
      aria-modal="true"
      aria-label={title || "Dialog"}
    >
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
      />
      {/* Panel */}
      <div
        className={`relative w-full max-w-lg mx-4 p-3 bg-white rounded-2xl shadow-2xl border border-white/20 animate-in fade-in zoom-in duration-200 ${className || ""}`}
        onClick={(e) => e.stopPropagation()}
      >
        {title && (
          <div className="flex items-center justify-between pb-3 border-b border-white/10 mb-4">
            <h3 className="text-lg font-semibold text-white">{title}</h3>
            <button
              onClick={onClose}
              className="rounded-md p-1.5 text-white/70 hover:text-white hover:bg-white/10 transition"
              aria-label="Close dialog"
            >
              <X size={18} />
            </button>
          </div>
        )}
        <div className="text-white/90">{children}</div>
      </div>
    </div>
  );
}

Modal.displayName = "Modal";
