import { Children, cloneElement, isValidElement } from "react";
import type { ReactElement, ReactNode } from "react";

type FormFieldProps = {
  htmlFor: string;
  label: string;
  hint?: string;
  required?: boolean;
  children: ReactNode;
  className?: string;
};

export default function FormField({ htmlFor, label, hint, required, children, className = "" }: FormFieldProps) {
  const describedChildren = Children.map(children, (child) => {
    if (!hint || !isValidElement(child) || !["input", "select", "textarea"].includes(String(child.type))) return child;
    const existing = (child.props as { "aria-describedby"?: string })["aria-describedby"];
    return cloneElement(child as ReactElement<{ "aria-describedby"?: string }>, {
      "aria-describedby": [`${htmlFor}-hint`, existing].filter(Boolean).join(" "),
    });
  });

  return (
    <div className={`space-y-1 ${className}`}>
      <label htmlFor={htmlFor} className="block text-xs font-semibold text-kfl-text">
        {label}{required && <span className="ml-1 text-rose-700" aria-hidden="true">*</span>}
        {required && <span className="sr-only"> (required)</span>}
      </label>
      {hint && <p id={`${htmlFor}-hint`} className="text-[11px] leading-4 text-kfl-muted">{hint}</p>}
      {describedChildren}
    </div>
  );
}
