import { expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

const profile = {
  user: {
    user_id: "u-accountable",
    username: "accountable",
    email: "accountable@example.test",
    full_name: "Accountable Manager",
    role: "accountable_manager",
    active_role: "accountable_manager",
    roles: ["accountable_manager"],
  },
  role: "accountable_manager",
  active_role: "accountable_manager",
  roles: ["accountable_manager"],
  authenticated_via: "session_cookie",
  onboarding_completed: true,
  permissions: [
    "organization:overview", "audit_report:read", "document:read", "safety:read",
    "compliance:read", "roc:read", "aircraft:read",
  ],
};

const organizationOverview = {
  trends: {
    occurrences_by_type: { incident: 2 },
    occurrences_by_severity: { moderate: 2 },
    safety_actions_by_status: { open: 1 },
    hazards_by_risk_level: { medium: 1 },
    occurrences_last_30_days: 2,
  },
  deadlines: {
    total: 1,
    overdue_count: 1,
    upcoming_count: 0,
    overdue: [{ entity_type: "aircraft_insurance", entity_id: "INS-E2E-001", title: "Insurance expiry: hull - AC-001", due_date: "2026-11-01", priority: "critical" }],
    upcoming: [],
  },
  operations: { total: 4, planned: 1, released: 1, in_progress: 1, completed: 1, cancelled: 0, aborted: 0 },
  fleet: { total: 3, status_counts: { active: 2, grounded: 1 }, opspec_authorized: 2, not_opspec_authorized: 1 },
};

test("renders the authenticated accountable-manager overview from isolated API fixtures", async ({ page }) => {
  await page.route(/\/api\/p[01]\//, async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/api/p0/auth/profile") {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(profile) });
      return;
    }
    if (path === "/api/p1/organization/overview") {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(organizationOverview) });
      return;
    }
    if (path === "/api/p1/notifications/unread-count") {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ unread_count: 0 }) });
      return;
    }
    await route.fulfill({ status: 200, contentType: "application/json", body: "{}" });
  });

  await page.goto("/organization-overview");

  await expect(page.getByRole("heading", { name: "Organization overview" })).toBeVisible();
  await expect(page.getByRole("navigation", { name: "My workspace" }).getByRole("link", { name: "Organization overview" })).toBeVisible();
  await expect(page.getByText("Active operations")).toBeVisible();
  await expect(page.getByText("Completed operations")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Fleet summary" })).toBeVisible();
  await expect(page.getByText(/Record: INS-E2E-001/)).toBeVisible();
  const overdueRecordsLink = page.getByRole("link", { name: "View overdue records" });
  await expect(overdueRecordsLink).toHaveAttribute("href", "/organization-overview#overdue-deadlines");
  await overdueRecordsLink.click();
  await expect(page).toHaveURL(/\/organization-overview#overdue-deadlines$/);
  await expect(page.getByText(/No approved NOTAM data source is connected/i)).toBeVisible();
  await expect(page.getByText(/not an indication that there are no NOTAMs/i)).toBeVisible();

  const results = await new AxeBuilder({ page }).disableRules(["color-contrast"]).analyze();
  const blockingViolations = results.violations.filter((violation) => violation.impact === "critical" || violation.impact === "serious");
  expect(blockingViolations, JSON.stringify(blockingViolations, null, 2)).toEqual([]);
});
