export type AccessProfile = {
  role?: string | null;
  active_role?: string | null;
  permissions?: readonly string[] | null;
} | null;

export type ScreenRequirement = {
  permission?: string;
  permissions?: readonly string[];
  role?: string;
};

export function hasPermission(profile: AccessProfile, permission: string): boolean {
  return Boolean(profile && profile.permissions?.includes(permission));
}

export function canAccessScreen(profile: AccessProfile, requirement: ScreenRequirement): boolean {
  if (!profile) return false;
  if (requirement.role && profile.active_role !== requirement.role) return false;
  if (requirement.permission && !hasPermission(profile, requirement.permission)) return false;
  if (requirement.permissions?.some((permission) => !hasPermission(profile, permission))) return false;
  return true;
}

export function getPostLoginPath(profile: AccessProfile, returnTo?: string): string {
  if (!profile) return "/login";

  const defaultRoute = [
    { path: "/", permission: "safety:read" },
    { path: "/documents", permission: "document:read" },
    { path: "/roc", permission: "roc:read" },
    { path: "/personnel-licenses", permission: "personnel:read" },
    { path: "/aircraft-insurance", permission: "aircraft:read" },
  ].find((candidate) => hasPermission(profile, candidate.permission))?.path ?? "/account/security";

  if (!returnTo || !returnTo.startsWith("/") || returnTo[1] === "/" || returnTo.charCodeAt(1) === 92) {
    return defaultRoute;
  }

  const pathname = returnTo.split(/[?#]/, 1)[0];
  if (pathname === "/account/security") return returnTo;
  if (pathname === "/admin/observability") {
    return profile.active_role === "system_admin" ? returnTo : defaultRoute;
  }

  const routePermissions: Array<[string, string]> = [
    ["/notifications", "safety:read"],
    ["/occurrences", "safety:read"],
    ["/missions", "safety:read"],
    ["/quality-audits", "safety:read"],
    ["/corrective-actions", "safety:read"],
    ["/dangerous-goods", "safety:read"],
    ["/hazards", "safety:read"],
    ["/risk-assessments", "safety:read"],
    ["/investigations", "safety:read"],
    ["/safety-actions", "safety:read"],
    ["/safety-kpis", "safety:read"],
    ["/dg-responsibility-matrix", "safety:read"],
    ["/roc", "roc:read"],
    ["/audit-trail", "audit:read"],
    ["/documents", "document:read"],
    ["/distributions", "document:read"],
    ["/change-requests", "document:read"],
    ["/document-proposals", "document:read"],
    ["/version-diff", "document:read"],
    ["/training", "personnel:read"],
    ["/crew", "personnel:read"],
    ["/duties", "personnel:read"],
    ["/crew-qualifications", "personnel:read"],
    ["/personnel-licenses", "personnel:read"],
    ["/renewal-progress", "personnel:read"],
    ["/self-service-upload", "personnel:view"],
    ["/maintenance", "aircraft:read"],
    ["/aircraft-insurance", "aircraft:read"],
    ["/security-reviews", "security:read_sensitive"],
    ["/security", "security:read_sensitive"],
    ["/outsourced-functions", "compliance:read"],
  ];
  const required = routePermissions.find(([base]) => pathname === base || pathname.startsWith(`${base}/`));
  if (pathname === "/") return hasPermission(profile, "safety:read") ? returnTo : defaultRoute;
  if (!required || !hasPermission(profile, required[1])) return defaultRoute;
  return returnTo;
}

