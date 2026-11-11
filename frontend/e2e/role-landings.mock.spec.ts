import { expect, test, type Page, type Route } from "@playwright/test";

type LandingCase = {
  role: string;
  path: string;
  heading: string;
  workspaceLink: string;
  permissions: string[];
};

const landingCases: LandingCase[] = [
  { role: "system_admin", path: "/admin/observability", heading: "System Observability", workspaceLink: "System Observability", permissions: ["organization:overview", "safety:read"] },
  { role: "accountable_manager", path: "/organization-overview", heading: "Organization overview", workspaceLink: "Organization overview", permissions: ["organization:overview", "audit_report:read", "document:read", "safety:read", "compliance:read", "roc:read", "aircraft:read"] },
  { role: "librarian", path: "/documents", heading: "Document Catalogue", workspaceLink: "Documents", permissions: ["document:read", "document:propose"] },
  { role: "head_quality", path: "/audit-dashboard", heading: "Audit Dashboard", workspaceLink: "Audit Dashboard", permissions: ["audit_finding:read", "audit_report:read", "document:read", "safety:read"] },
  { role: "head_safety", path: "/safety-actions", heading: "Safety Actions", workspaceLink: "Safety Actions", permissions: ["safety:read"] },
  { role: "head_security", path: "/security-reviews", heading: "Security Review Meetings", workspaceLink: "Security Reviews", permissions: ["security:read_sensitive", "safety:read"] },
  { role: "head_operations", path: "/missions", heading: "Missions", workspaceLink: "Missions", permissions: ["safety:read", "roc:read", "aircraft:read", "personnel:read"] },
  { role: "chief_pilot", path: "/missions", heading: "Missions", workspaceLink: "Missions", permissions: ["safety:read", "roc:read", "personnel:read"] },
  { role: "flight_ops_officer", path: "/missions", heading: "Missions", workspaceLink: "Missions", permissions: ["safety:read", "roc:read"] },
  { role: "head_training", path: "/training", heading: "Training Management", workspaceLink: "Training Management", permissions: ["personnel:read"] },
  { role: "head_maintenance", path: "/maintenance", heading: "Maintenance Management", workspaceLink: "Maintenance Management", permissions: ["aircraft:read"] },
  { role: "dg_coordinator", path: "/dangerous-goods", heading: "Dangerous Goods Shipments", workspaceLink: "Dangerous Goods", permissions: ["safety:read"] },
  { role: "occurrence_reporter", path: "/occurrences", heading: "Safety Occurrences", workspaceLink: "Safety Occurrences", permissions: ["safety:read"] },
  { role: "records_custodian", path: "/documents", heading: "Document Catalogue", workspaceLink: "Documents", permissions: ["document:read"] },
  { role: "independent_auditor", path: "/audit-reports", heading: "Audit Reports", workspaceLink: "Audit Reports", permissions: ["audit_report:read", "audit_finding:read", "audit:read"] },
  { role: "as_contracted", path: "/documents", heading: "Document Catalogue", workspaceLink: "Documents", permissions: ["document:read", "safety:read"] },
];

const organizationOverview = {
  trends: {
    occurrences_by_type: {}, occurrences_by_severity: {}, safety_actions_by_status: {},
    hazards_by_risk_level: {}, occurrences_last_30_days: 0,
  },
  deadlines: { total: 0, overdue_count: 0, upcoming_count: 0, overdue: [], upcoming: [] },
  operations: { total: 0, planned: 0, released: 0, in_progress: 0, completed: 0, cancelled: 0, aborted: 0 },
  fleet: { total: 0, status_counts: {}, opspec_authorized: 0, not_opspec_authorized: 0 },
};

function profileFor(landing: LandingCase) {
  const userId = `mock-${landing.role}`;
  return {
    user: {
      user_id: userId,
      username: landing.role,
      email: `${landing.role}@example.test`,
      full_name: landing.role.replace(/_/g, " "),
      role: landing.role,
      active_role: landing.role,
      roles: [landing.role],
    },
    role: landing.role,
    active_role: landing.role,
    roles: [landing.role],
    authenticated_via: "session_cookie",
    onboarding_completed: true,
    permissions: landing.permissions,
  };
}

function fixtureFor(path: string, profile: ReturnType<typeof profileFor>) {
  if (path === "/api/p0/auth/profile") return profile;
  if (path === "/api/p0/admin/observability") {
    return {
      health: { status: "ok", scheduler: "mock" },
      database: { status: "ok", integrity: "ok" },
      users: { active: 0, total: 0 },
      audit: { events_last_24h: 0 },
      workflows: { document_versions: {} },
      tables: {}, user_profiles: [], role_matrix: [],
    };
  }
  if (path === "/api/p0/backup/history") return [];
  if (path === "/api/p3/audit-findings/summary") {
    return { total: 0, open: 0, closed: 0, by_level: {}, by_status: {}, by_area: {} };
  }
  if (path === "/api/p1/missions/summary") {
    return { total: 0, planned: 0, released: 0, in_progress: 0, completed: 0, cancelled: 0, aborted: 0 };
  }
  if (path === "/api/p1/organization/overview") return organizationOverview;
  if (path === "/api/p1/notifications/unread-count") return { unread_count: 0 };
  if ([
    "/api/p0/documents", "/api/p1/safety-actions", "/api/p1/security-reviews",
    "/api/p1/missions", "/api/p1/training-records", "/api/p1/maintenance-records",
    "/api/p1/dg-shipments", "/api/p1/dg-responsibility-matrix", "/api/p1/occurrences", "/api/p3/audit-reports",
  ].includes(path)) return [];
  return undefined;
}

async function mockApi(page: Page, landing: LandingCase) {
  const profile = profileFor(landing);
  const unexpectedRequests: string[] = [];
  const writes: string[] = [];
  await page.route(/\/api\/p[0-9]\//, async (route: Route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (request.method() !== "GET") {
      writes.push(`${request.method()} ${path}`);
      await route.fulfill({ status: 405, contentType: "application/json", body: JSON.stringify({ detail: "Read-only landing smoke test" }) });
      return;
    }
    const fixture = fixtureFor(path, profile);
    if (fixture === undefined) unexpectedRequests.push(path);
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(fixture ?? []) });
  });
  return { unexpectedRequests, writes };
}

test("all role landings render in isolated mock-backed browser contexts", async ({ browser }) => {
  test.setTimeout(120_000);
  for (const landing of landingCases) {
    const context = await browser.newContext();
    const page = await context.newPage();
    const pageErrors: string[] = [];
    const consoleErrors: string[] = [];
    page.on("pageerror", (error) => pageErrors.push(error.message));
    page.on("console", (message) => {
      if (message.type() === "error") consoleErrors.push(message.text());
    });
    const { unexpectedRequests, writes } = await mockApi(page, landing);

    await page.goto(landing.path);
    await expect(page.getByRole("heading", { name: landing.heading, exact: true }), `${landing.role} landing ${landing.path}`).toBeVisible();
    await expect(page.getByRole("navigation", { name: "My workspace" }).getByRole("link", { name: landing.workspaceLink, exact: true })).toBeVisible();
    await expect(page.getByRole("region", { name: "One-time workspace tips" }), `${landing.role} first-visit tips`).toBeVisible();
    await expect(page).toHaveURL(new RegExp(`${landing.path.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}$`));
    await page.getByRole("button", { name: "Got it" }).click();
    await expect(page.getByRole("region", { name: "One-time workspace tips" })).toHaveCount(0);
    await page.reload();
    await expect(page.getByRole("heading", { name: landing.heading, exact: true })).toBeVisible();
    await expect(page.getByRole("region", { name: "One-time workspace tips" })).toHaveCount(0);
    expect(writes, `${landing.role} landing must not write data`).toEqual([]);
    expect(pageErrors, `${landing.role} uncaught browser errors`).toEqual([]);
    expect(consoleErrors, `${landing.role} console errors`).toEqual([]);
    expect(unexpectedRequests, `${landing.role} unexpected API calls`).toEqual([]);

    await context.close();
  }
});
