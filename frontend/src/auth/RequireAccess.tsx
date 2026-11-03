import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "./AuthContext";
import { canAccessScreen } from "./permissions";

function AuthLoading() {
  return (
    <main className="app-page min-h-screen">
      <div role="status" className="app-surface p-10 text-center text-sm text-kfl-muted">Checking secure session…</div>
    </main>
  );
}

export function RequireAuth({ children }: { children: ReactNode }) {
  const { state } = useAuth();
  const location = useLocation();
  if (state === "loading") return <AuthLoading />;
  if (state !== "authenticated") {
    return <Navigate to="/login" replace state={{ from: `${location.pathname}${location.search}` }} />;
  }
  return <>{children}</>;
}

export function RequireAccess({
  children,
  permission,
  permissions,
  anyPermissions,
  role,
}: {
  children: ReactNode;
  permission?: string;
  permissions?: string[];
  anyPermissions?: string[];
  role?: string;
}) {
  const { profile, state } = useAuth();
  if (state === "loading") return <AuthLoading />;
  if (state !== "authenticated") return <Navigate to="/login" replace />;
  if (!canAccessScreen(profile, { permission, permissions, anyPermissions, role })) {
    return (
      <main className="app-page" role="alert">
        <div className="app-surface border border-rose-200 bg-rose-50 p-6 text-sm text-rose-800">
          Access to this area is not included in your assigned profile. Contact the system administrator if you need access.
        </div>
      </main>
    );
  }
  return <>{children}</>;
}
