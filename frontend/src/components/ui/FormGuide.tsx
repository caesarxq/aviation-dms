import type { ReactNode } from "react";

export function FormGuide({ children, id }: { children: ReactNode; id?: string }) {
  return (
    <p id={id} role="note" className="mb-4 rounded-md border border-kfl-blue/20 bg-kfl-blue/5 px-3 py-2 text-xs leading-5 text-kfl-secondary">
      {children}
    </p>
  );
}
