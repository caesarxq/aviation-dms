export type AccessProfile = {
  role?: string | null;
  active_role?: string | null;
  permissions?: readonly string[] | null;
} | null;

export type ScreenRequirement = {
  permission?: string;
  permissions?: readonly string[];
  anyPermissions?: readonly string[];
  role?: string;
};

export type RoleWorkspace = {
  home: string;
  primaryPaths: readonly string[];
};

export const ROLE_WORKSPACES: Readonly<Record<string, RoleWorkspace>> = {
  system_admin: { home: "/admin/observability", primaryPaths: ["/admin/observability", "/organization-overview"] },
  accountable_manager: { home: "/organization-overview", primaryPaths: ["/organization-overview", "/change-requests", "/audit-reports", "/missions", "/roc"] },
  librarian: { home: "/documents", primaryPaths: ["/documents", "/document-proposals", "/change-requests", "/distributions"] },
  head_quality: { home: "/audit-dashboard", primaryPaths: ["/audit-dashboard", "/audit-findings", "/audit-reports", "/quality-audits", "/change-requests"] },
  head_safety: { home: "/safety-actions", primaryPaths: ["/safety-actions", "/investigations", "/occurrences", "/hazards", "/risk-assessments"] },
  head_security: { home: "/security-reviews", primaryPaths: ["/security-reviews", "/security", "/occurrences"] },
  head_operations: { home: "/missions", primaryPaths: ["/missions", "/roc", "/maintenance", "/crew", "/duties"] },
  chief_pilot: { home: "/missions", primaryPaths: ["/missions", "/roc", "/crew", "/duties", "/occurrences"] },
  flight_ops_officer: { home: "/missions", primaryPaths: ["/missions", "/roc", "/occurrences"] },
  head_training: { home: "/training", primaryPaths: ["/training", "/crew-qualifications", "/crew", "/personnel-licenses"] },
  head_maintenance: { home: "/maintenance", primaryPaths: ["/maintenance", "/aircraft-insurance", "/roc"] },
  dg_coordinator: { home: "/dangerous-goods", primaryPaths: ["/dangerous-goods", "/dg-responsibility-matrix", "/missions"] },
  occurrence_reporter: { home: "/occurrences", primaryPaths: ["/occurrences"] },
  records_custodian: { home: "/documents", primaryPaths: ["/documents", "/distributions", "/change-requests"] },
  independent_auditor: { home: "/audit-reports", primaryPaths: ["/audit-reports", "/audit-findings", "/audit-dashboard", "/audit-trail"] },
  as_contracted: { home: "/documents", primaryPaths: ["/documents"] },
};

const ROUTE_PERMISSIONS: Array<[string, string]> = [
  ["/organization-overview", "organization:overview"],
  ["/audit-reports", "audit_report:read"],
  ["/audit-findings", "audit_finding:read"],
  ["/audit-dashboard", "audit_finding:read"],
  ["/notifications", "compliance:read"],
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

export function hasPermission(profile: AccessProfile, permission: string): boolean {
  return Boolean(profile && profile.permissions?.includes(permission));
}

export function canAccessScreen(profile: AccessProfile, requirement: ScreenRequirement): boolean {
  if (!profile) return false;
  if (requirement.role && profile.active_role !== requirement.role) return false;
  if (requirement.permission && !hasPermission(profile, requirement.permission)) return false;
  if (requirement.permissions?.some((permission) => !hasPermission(profile, permission))) return false;
  if (requirement.anyPermissions?.length && !requirement.anyPermissions.some((permission) => hasPermission(profile, permission))) return false;
  return true;
}

export function getPostLoginPath(profile: AccessProfile, returnTo?: string): string {
  if (!profile) return "/login";

  const fallbackRoute = [
    { path: "/", permission: "safety:read" },
    { path: "/documents", permission: "document:read" },
    { path: "/documents", permission: "document:propose" },
    { path: "/roc", permission: "roc:read" },
    { path: "/personnel-licenses", permission: "personnel:read" },
    { path: "/aircraft-insurance", permission: "aircraft:read" },
  ].find((candidate) => hasPermission(profile, candidate.permission))?.path ?? "/account/security";

  const role = profile.active_role ?? profile.role ?? "";
  const preferredHome = ROLE_WORKSPACES[role]?.home;
  const defaultRoute = preferredHome && canAccessPath(profile, preferredHome) ? preferredHome : fallbackRoute;

  if (!returnTo || !returnTo.startsWith("/") || returnTo[1] === "/" || returnTo.charCodeAt(1) === 92) {
    return defaultRoute;
  }

  const pathname = returnTo.split(/[?#]/, 1)[0].replace(/\/+$/, "") || "/";
  return canAccessPath(profile, pathname) ? returnTo : defaultRoute;
}

function canAccessPath(profile: AccessProfile, pathname: string): boolean {
  if (!profile) return false;
  if (pathname === "/account/security" || pathname === "/account/profile") return true;
  if (pathname === "/admin/observability") return (profile.active_role ?? profile.role) === "system_admin";
  if (pathname === "/" || pathname === "") return hasPermission(profile, "safety:read");
  if (pathname === "/documents" || pathname === "/document-proposals") {
    return hasPermission(profile, "document:read") || hasPermission(profile, "document:propose");
  }
  if (/^\/documents\/[^/]+\/edit$/.test(pathname)) {
    return hasPermission(profile, "document:update") || hasPermission(profile, "document:propose");
  }
  if (/^\/documents\/[^/]+\/view$/.test(pathname)) {
    return hasPermission(profile, "document:read")
      || hasPermission(profile, "document:propose")
      || hasPermission(profile, "document:update");
  }
  const required = ROUTE_PERMISSIONS.find(([base]) => pathname === base || pathname.startsWith(`${base}/`));
  return Boolean(required && hasPermission(profile, required[1]));
}

