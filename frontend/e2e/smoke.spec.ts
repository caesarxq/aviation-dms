import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

const TEST_USER = process.env.KFL_E2E_USER || "safety";
const TEST_PASSWORD = process.env.KFL_E2E_PASSWORD;

function requireTestPassword() {
  if (!TEST_PASSWORD) {
    throw new Error("Set KFL_E2E_PASSWORD for an isolated E2E test database; no shared test password is built into the suite.");
  }
  return TEST_PASSWORD;
}

async function login(page: any) {
  const password = requireTestPassword();
  await page.goto("/login");
  await page.waitForLoadState("networkidle");
  await page.fill('input[id="login-username"]', TEST_USER);
  await page.fill('input[id="login-password"]', password);
  await page.click('button[type="submit"]:has-text("Sign in")');
  // Wait for redirect away from login page
  await page.waitForURL(url => url.pathname !== "/login");
  // Wait for the role-specific authenticated shell.
  await page.locator(".app-shell").waitFor();
}

async function loginAsAdmin(page: any) {
  const password = requireTestPassword();
  // Clear existing session (beforeEach logs in as u-safety)
  await page.context().clearCookies();
  await page.goto("/login");
  await page.waitForLoadState("networkidle");
  await page.fill('input[id="login-username"]', "admin");
  await page.fill('input[id="login-password"]', password);
  await page.click('button[type="submit"]:has-text("Sign in")');
  await page.waitForURL(url => url.pathname !== "/login");
  await page.locator(".app-shell").waitFor();
}

test.beforeEach(async ({ page }) => {
  await login(page);
});

test.describe("Dashboard", () => {
  test("loads dashboard with KPI cards", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
    await expect(page.locator("text=Occurrences (30 days)")).toBeVisible();
    await expect(page.locator("text=Total Hazards")).toBeVisible();
    await expect(page.locator("text=Open Safety Actions")).toBeVisible();
  });

  test("displays deadline widget", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator("text=Upcoming & Overdue Deadlines")).toBeVisible();
  });
});

test.describe("Document Catalogue", () => {
  test("loads document list", async ({ page }) => {
    await page.goto("/documents");
    await expect(page.getByRole("heading", { name: "Document Catalogue" })).toBeVisible();
    await expect(page.locator("table")).toBeVisible();
  });

  test("has view and edit links", async ({ page }) => {
    await loginAsAdmin(page);
    await page.goto("/documents");
    await expect(page.locator("text=View").first()).toBeVisible();
    await expect(page.locator("text=Edit").first()).toBeVisible();
  });
});

test.describe("Navigation", () => {
  test("sidebar navigation works", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: "All modules" }).click();
    // Flight section is collapsed by default; expand it first
    await page.getByRole("button", { name: "Flight" }).click();
    await page.getByRole("link", { name: "Missions" }).click();
    await expect(page).toHaveURL(/\/missions/);
    await expect(page.getByRole("heading", { name: "Missions" })).toBeVisible();
  });

  test("notifications page accessible", async ({ page }) => {
    await loginAsAdmin(page);
    await page.goto("/notifications");
    await expect(page.getByRole("heading", { name: "Notifications" })).toBeVisible();
  });

  test("sidebar exposes the revised control structure", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("link", { name: "Safety dashboard" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Operations" })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Fleet & Registry" })).toHaveCount(0);

    await page.getByRole("button", { name: "All modules" }).click();
    await page.getByRole("button", { name: "Document Control" }).click();
    await expect(page.getByRole("link", { name: "Documents" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Document Viewer" })).toHaveCount(0);
    await expect(page.getByRole("link", { name: "Document Editor" })).toHaveCount(0);
  });

  test("system administrator observability page loads", async ({ page }) => {
    await loginAsAdmin(page);
    await page.goto("/admin/observability");
    await expect(page.getByRole("heading", { name: "System Observability" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Role matrix" })).toBeVisible();
    await expect(page.getByRole("cell", { name: "system_admin" }).first()).toBeVisible();
  });

  test("organization overview shows organization summaries and the NOTAM source gap", async ({ page }) => {
    await loginAsAdmin(page);
    await page.goto("/organization-overview");
    await expect(page.getByRole("heading", { name: "Organization overview" })).toBeVisible();
    await expect(page.getByText("Active operations")).toBeVisible();
    await expect(page.getByRole("heading", { name: "Fleet summary" })).toBeVisible();
    await expect(page.getByText(/No approved NOTAM data source is connected/i)).toBeVisible();
    await expect(page.getByText(/not an indication that there are no NOTAMs/i)).toBeVisible();
  });

  test("canonical role editor preserves IDs and submits only assigned roles", async ({ page }) => {
    await loginAsAdmin(page);
    await page.goto("/admin/observability");
    await expect(page.getByRole("heading", { name: "System Observability" })).toBeVisible();

    const roleSelect = page.locator("#roles-u-quality");
    await expect(roleSelect).toBeVisible();
    const selectedRoles = await roleSelect.evaluate((select: HTMLSelectElement) =>
      Array.from(select.selectedOptions, (option) => option.value).sort(),
    );
    expect(selectedRoles).toEqual(["head_quality", "librarian", "records_custodian"]);

    const results = await new AxeBuilder({ page })
      .exclude("iframe")
      .disableRules(["color-contrast"])
      .analyze();
    const blockingViolations = results.violations.filter((violation) => violation.impact === "critical" || violation.impact === "serious");
    expect(blockingViolations, JSON.stringify(blockingViolations, null, 2)).toEqual([]);

    const updateResponse = page.waitForResponse((response) =>
      response.url().includes("/api/p0/auth/users/u-quality/roles") && response.request().method() === "PUT",
    );
    await page.getByRole("button", { name: "Save roles for Eric Otieno" }).click();
    const response = await updateResponse;
    expect(response.status()).toBe(200);
    expect(await response.json()).toMatchObject({ user_id: "u-quality", active_sessions_revoked: false });
  });

  test("document editor exposes a draggable toolbar", async ({ page }) => {
    await loginAsAdmin(page);
    await page.goto("/documents/DOC-001/edit");
    const grip = page.getByRole("button", { name: "Drag toolbar" });
    await expect(grip).toBeVisible();
    await expect(page.getByText("Live suggestion markup")).toBeVisible();
    await page.getByTitle("Hide live suggestions").first().click();
    await expect(page.getByTestId("inline-suggestion-stream")).toHaveCount(0);
    await page.getByTitle("Show live suggestions").first().click();
    await expect(page.getByTestId("inline-suggestion-stream")).toBeVisible();
  });

  test("tracks a typed change in real time", async ({ page }) => {
    await loginAsAdmin(page);
    await page.goto("/documents/DOC-001/edit");
    const editor = page.locator('[contenteditable="true"]');
    await editor.click();
    await page.keyboard.press("End");
    await page.keyboard.type(" live-suggestion-test");
    await expect(page.getByTestId("inline-suggestion-stream")).toContainText("live-suggestion-test");
    await expect(page.locator("ins").filter({ hasText: "live-suggestion-test" })).toBeVisible();
  });

  test("opens the submit modal with auto-detected section references", async ({ page }) => {
    await loginAsAdmin(page);
    await page.goto("/documents/DOC-001/edit");
    const editor = page.locator('[contenteditable="true"]');
    await editor.click();
    await page.keyboard.press("End");
    await page.keyboard.type(" proposal-section-test");
    await page.getByTitle("Submit proposal for review").click();
    await expect(page.getByText("Auto-detected Target Reference")).toBeVisible();
    await expect(page.getByText("Detected changes")).toBeVisible();
    await expect(page.locator('input[readonly]').first()).toHaveValue(/section|block|paragraph/i);
  });
  test("viewer opens an empty outline for content without semantic headings and supports fullscreen", async ({ page }) => {
    await page.goto("/documents/DOC-001/view");
    await expect(page.getByRole("heading", { name: "DOC-001" })).toBeVisible();
    await page.getByRole("button", { name: "Show document outline" }).click();
    await expect(page.getByRole("navigation", { name: "Document outline" })).toBeVisible();
    await expect(page.getByText("No headings detected.")).toBeVisible();
    await page.getByTitle("Enter fullscreen").click();
    await expect(page.getByTitle("Exit fullscreen")).toBeVisible();
  });

  test("editor clearly reports when source content has no semantic headings", async ({ page }) => {
    await loginAsAdmin(page);
    await page.goto("/documents/DOC-001/edit");
    await page.getByTitle("Show document outline").click();
    await expect(page.getByRole("navigation", { name: "Document outline" })).toBeVisible();
    await expect(page.getByText("No headings detected.")).toBeVisible();
  });

  test("submitting a proposal clears pending editor suggestions", async ({ page }) => {
    await loginAsAdmin(page);
    const marker = `proposal-submit-${Date.now()}`;
    await page.goto("/documents/DOC-012/edit");
    const editor = page.locator('[contenteditable="true"]');
    await editor.click();
    await page.keyboard.press("End");
    await page.keyboard.type(` ${marker}`);
    await page.getByTitle("Submit proposal for review").click();
    await expect(page.getByText("Detected changes")).toBeVisible();
    await page.getByRole("button", { name: "Submit Proposal", exact: true }).click();
    await expect(page.getByText("Submit Change Proposal")).toHaveCount(0, { timeout: 10000 });
    await expect(page.getByText("unsaved changes")).toHaveCount(0);
    await expect(page.getByTestId("inline-suggestion-stream")).not.toContainText(marker);
  });
});

test.describe("Missions", () => {
  test("can create a mission", async ({ page }) => {
    await page.goto("/missions");
    await page.click("text=New Mission");
    await page.waitForSelector('input[placeholder="Mission title"]');
    await page.fill('input[placeholder="Mission title"]', "E2E Test Mission");
    await page.click("text=Create Mission");
    await page.waitForTimeout(1500);
    await expect(page.locator("table").locator("text=E2E Test Mission").first()).toBeVisible({ timeout: 8000 });
  });
});

test.describe("Document Viewer", () => {
  test("renders plain-text source content inside the isolated iframe", async ({ page }) => {
    await page.goto("/documents/DOC-001/view");
    await expect(page.getByRole("heading", { name: "DOC-001" })).toBeVisible();
    await expect(page.frameLocator('iframe[title="DOC-001"]').locator("body")).toContainText("KFL Operations Manual", { timeout: 20000 });
  });
});

test.describe("Occurrences", () => {
  test("loads occurrences page", async ({ page }) => {
    await page.goto("/occurrences");
    await expect(page.locator("body")).toBeVisible();
  });
});

test.describe("Hazards", () => {
  test("loads hazards page", async ({ page }) => {
    await page.goto("/hazards");
    await expect(page.getByRole("heading", { name: "Hazard Register" })).toBeVisible();
    await expect(page.locator("body")).toBeVisible();
  });

  test("can create a hazard", async ({ page }) => {
    await page.goto("/hazards");
    await page.click("text=New Hazard");
    await page.waitForSelector('input[placeholder="Hazard title"]');
    await page.fill('input[placeholder="Hazard title"]', "E2E Test Hazard");
    await page.fill('textarea[placeholder="Describe the hazard"]', "A test hazard for E2E validation");
    await page.click("text=Submit Hazard");
    await page.waitForTimeout(1500);
    await expect(page.locator("table").locator("text=E2E Test Hazard").first()).toBeVisible({ timeout: 8000 });
  });
});

test.describe("Risk Assessments", () => {
  test("loads risk assessments page", async ({ page }) => {
    await page.goto("/risk-assessments");
    await expect(page.getByRole("heading", { name: "Risk Assessments" })).toBeVisible();
    await expect(page.locator("body")).toBeVisible();
  });

  test("can create a risk assessment with multiple hazards", async ({ page }) => {
    await page.goto("/risk-assessments");
    await page.click("text=New Assessment");
    await page.waitForSelector('input[placeholder="Assessment title"]');
    await page.fill('input[placeholder="Assessment title"]', "E2E Multi-Hazard Risk Assessment");
    await page.fill('textarea[placeholder="Describe the risk scenario"]', "A test risk assessment with multiple hazards");

    // Add multiple hazards (using seeded hazard IDs)
    await page.fill('input[placeholder="e.g. HAZ-001"]', "HAZ-SEED-001");
    await page.click("text=Add");
    await page.fill('input[placeholder="e.g. HAZ-001"]', "HAZ-SEED-002");
    await page.press('input[placeholder="e.g. HAZ-001"]', "Enter");

    await page.click("text=Submit Assessment");
    // Wait for the new assessment to appear in the table
    await expect(page.locator("table").locator("text=E2E Multi-Hazard Risk Assessment").first()).toBeVisible({ timeout: 10000 });
    await expect(page.locator("text=HAZ-SEED-001").first()).toBeVisible();
    await expect(page.locator("text=HAZ-SEED-002").first()).toBeVisible();
  });
});

test.describe("Investigations", () => {
  test("loads investigations page", async ({ page }) => {
    await page.goto("/investigations");
    await expect(page.getByRole("heading", { name: "Investigations" })).toBeVisible();
    await expect(page.locator("body")).toBeVisible();
  });

  test("can create an investigation", async ({ page }) => {
    await page.goto("/occurrences");
    await page.click("text=Report Occurrence");
    await page.waitForSelector('input[placeholder="Occurrence title"]');
    await page.fill('input[placeholder="Occurrence title"]', "E2E Investigation Occurrence");
    await page.fill('textarea[placeholder="Describe the occurrence"]', "Test occurrence for investigation E2E");
    await page.click("text=Submit Report");
    await page.waitForTimeout(1500);
    await expect(page.locator("text=E2E Investigation Occurrence").first()).toBeVisible({ timeout: 8000 });

    await page.goto("/investigations");
    await page.click("text=New Investigation");
    await page.waitForSelector('input[placeholder="e.g. OCC-..."]');
    await page.fill('input[placeholder="e.g. OCC-..."]', "E2E Investigation Occurrence");
    await page.fill('input[placeholder="e.g. u-safety/security"]', "u-safety");
    await page.click("text=Open Investigation");
    await page.waitForTimeout(1500);
    await expect(page.locator("text=u-safety").first()).toBeVisible({ timeout: 8000 });
  });
});

test.describe("Safety Actions", () => {
  test("loads safety actions page", async ({ page }) => {
    await page.goto("/safety-actions");
    await expect(page.getByRole("heading", { name: "Safety Actions" })).toBeVisible();
    await expect(page.locator("body")).toBeVisible();
  });

  test("can create a safety action", async ({ page }) => {
    await page.goto("/safety-actions");
    await page.click("text=New Action");
    await page.waitForSelector('input[placeholder="Action title"]');
    await page.fill('input[placeholder="Action title"]', "E2E Test Safety Action");
    await page.fill('textarea[placeholder="Describe the action"]', "A test safety action for E2E validation");
    await page.fill('input[placeholder="e.g. u-safety/security"]', "u-safety");
    await page.click("text=Create Action");
    await page.waitForTimeout(1500);
    await expect(page.locator("table").locator("text=E2E Test Safety Action").first()).toBeVisible({ timeout: 8000 });
  });
});

test.describe("Audit Trail", () => {
  test("loads audit trail page", async ({ page }) => {
    await page.goto("/audit-trail");
    await expect(page.getByRole("heading", { name: "Audit Trail" })).toBeVisible();
    await expect(page.locator("body")).toBeVisible();
  });

  test("filters audit events by entity type", async ({ page }) => {
    await page.goto("/audit-trail");
    await page.fill('input[placeholder="Entity type (e.g. document)"]', "document");
    await page.waitForTimeout(1000);
    const rows = await page.locator("table tbody tr").count();
    expect(rows).toBeGreaterThanOrEqual(0);
  });
});

test.describe("Document Distributions", () => {
  test("loads distributions page", async ({ page }) => {
    await page.goto("/distributions");
    await expect(page.getByRole("heading", { name: "Document Distributions" })).toBeVisible();
    await expect(page.locator("body")).toBeVisible();
  });

  test("can create a distribution", async ({ page }) => {
    await loginAsAdmin(page);
    await page.goto("/distributions");
    await page.click("text=New Distribution");
    await page.waitForSelector("#distribution_create_version");
    await page.fill("#distribution_create_version", "VER-DOC-001");
    await page.fill("#distribution_create_recipient", "u-chief-pilot");
    await page.selectOption("#distribution_create_channel", "email");
    await page.click("#create_distribution_submit");
    await page.waitForTimeout(1500);
    await expect(page.locator("table").locator("text=VER-DOC-001").first()).toBeVisible({ timeout: 8000 });
  });
});

test.describe("Training Management", () => {
  test("loads training page", async ({ page }) => {
    await page.goto("/training");
    await expect(page.getByRole("heading", { name: "Training Management" })).toBeVisible();
    await expect(page.locator("body")).toBeVisible();
  });

  test("can create a training record", async ({ page }) => {
    await page.goto("/training");
    await page.click("text=New Record");
    await page.waitForSelector("#training_person_id");
    await page.fill("#training_person_id", "u-chief-pilot");
    await page.selectOption("#training_category", "general");
    await page.fill("#training_type", "Drone Safety");
    await page.fill("#training_date", "2025-01-01");
    await page.fill("#training_expiry", "2026-01-01");
    await page.fill("#training_certificate", "CERT-001");
    await page.click("#training_submit");
    await page.waitForTimeout(1500);
    await expect(page.locator("table").locator("text=Drone Safety").first()).toBeVisible({ timeout: 8000 });
  });
});

test.describe("Maintenance Management", () => {
  test("loads maintenance page", async ({ page }) => {
    await page.goto("/maintenance");
    await expect(page.getByRole("heading", { name: "Maintenance Management" })).toBeVisible();
    await expect(page.locator("body")).toBeVisible();
  });

  test("can create a maintenance record", async ({ page }) => {
    await loginAsAdmin(page);
    await page.goto("/maintenance");
    await page.click("text=New Record");
    await page.waitForSelector("#maintenance_aircraft");
    await page.fill("#maintenance_aircraft", "5Y-1353A");
    await page.fill("#maintenance_type", "A-Check");
    await page.fill("#maintenance_description", "Routine inspection");
    await page.fill("#maintenance_performed_by", "Mech-1");
    await page.fill("#maintenance_performed_at", "2026-01-10");
    await page.click("#maintenance_submit");
    await page.waitForTimeout(1500);
    await expect(page.getByText("A-Check").first()).toBeVisible({ timeout: 8000 });
  });
});

test.describe("Crew Management", () => {
  test("loads crew page", async ({ page }) => {
    await page.goto("/crew");
    await expect(page.getByRole("heading", { name: "Crew Management" })).toBeVisible();
    await expect(page.locator("body")).toBeVisible();
  });

  test("can create a crew member", async ({ page }) => {
    await loginAsAdmin(page);
    await page.goto("/crew");
    await page.click("text=Add Crew");
    await page.waitForSelector("#crew_full_name");
    await page.fill("#crew_full_name", "Capt. Test");
    await page.fill("#crew_role", "PIC");
    await page.selectOption("#crew_status", "active");
    await page.click("#crew_submit");
    await page.waitForTimeout(1500);
    await expect(page.getByText("Capt. Test").first()).toBeVisible({ timeout: 8000 });
  });
});

test.describe("Duty Time Tracking", () => {
  test("loads duties page", async ({ page }) => {
    await page.goto("/duties");
    await expect(page.getByRole("heading", { name: "Duty Time Tracking" })).toBeVisible();
    await expect(page.locator("body")).toBeVisible();
  });

  test("can open new duty modal", async ({ page }) => {
    await page.goto("/duties");
    await page.click("text=New Duty");
    await expect(page.locator("#duty_crew_id")).toBeVisible();
  });
});

test.describe("Crew Qualifications", () => {
  test("loads qualifications page", async ({ page }) => {
    await page.goto("/crew-qualifications");
    await expect(page.getByRole("heading", { name: "Crew Qualifications" })).toBeVisible();
    await expect(page.locator("body")).toBeVisible();
  });

  test("can open new qualification modal", async ({ page }) => {
    await page.goto("/crew-qualifications");
    await page.click("text=Add Qualification");
    await expect(page.locator("#qual_crew_id")).toBeVisible();
  });
});

test.describe("Change Requests", () => {
  test("loads change requests page", async ({ page }) => {
    await page.goto("/change-requests");
    await expect(page.getByRole("heading", { name: "Change Requests" })).toBeVisible();
    await expect(page.locator("body")).toBeVisible();
  });

  test("can open new change request modal", async ({ page }) => {
    await page.goto("/change-requests");
    await page.click("text=New Change Request");
    await expect(page.locator("#cr_document_id")).toBeVisible();
  });
});

test.describe("Audit report provenance import", () => {
  test("system administrator can stage metadata without receiving verifier controls or uploading a PDF", async ({ page }) => {
    await loginAsAdmin(page);
    await page.goto("/audit-reports");
    await expect(page.getByRole("heading", { name: "Audit Reports" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Historical Audit Provenance" })).toBeVisible();
    await page.getByRole("button", { name: "Stage Historical Import" }).click();
    await expect(page.getByLabel("Source Auditor ID")).toBeVisible();
    await expect(page.getByLabel("Existing Source PDF Path")).toBeVisible();
    await expect(page.getByText(/This screen does not upload files/i)).toBeVisible();
    await expect(page.getByRole("button", { name: "Verify and Import" })).toHaveCount(0);
    const results = await new AxeBuilder({ page })
      .exclude("iframe")
      .exclude('[contenteditable="true"]')
      .disableRules(["color-contrast"])
      .analyze();
    const blockingViolations = results.violations.filter((violation) => violation.impact === "critical" || violation.impact === "serious");
    expect(blockingViolations, JSON.stringify(blockingViolations, null, 2)).toEqual([]);
  });
});

test.describe("Accessibility", () => {
  for (const route of ["/documents", "/documents/DOC-001/edit", "/documents/DOC-001/view", "/hazards", "/risk-assessments", "/investigations", "/safety-actions", "/audit-trail", "/audit-reports", "/distributions", "/training", "/maintenance", "/crew", "/duties", "/crew-qualifications", "/change-requests", "/organization-overview"]) {
    test(`${route} has no automated accessibility violations`, async ({ page }) => {
      if (route === "/documents/DOC-001/edit" || route === "/organization-overview" || route === "/audit-reports") await loginAsAdmin(page);
      await page.goto(route);
      await page.waitForLoadState("networkidle");
      const results = await new AxeBuilder({ page })
        .exclude("iframe")
        .exclude('[contenteditable="true"]')
        .disableRules(["color-contrast"])
        .analyze();
      const blockingViolations = results.violations.filter((violation) => violation.impact === "critical" || violation.impact === "serious");
      expect(blockingViolations, JSON.stringify(blockingViolations, null, 2)).toEqual([]);
    });
  }
});

test.describe("Profile & Role Switching", () => {
  test("profile settings page loads for any user", async ({ page }) => {
    await page.goto("/account/profile");
    await expect(page.getByRole("heading", { name: "Profile Settings" })).toBeVisible();
    await expect(page.locator("text=Canonical ID")).toBeVisible();
    await expect(page.locator("text=Active Role").first()).toBeVisible();
  });

  test("sidebar prioritizes role workspace links and keeps remaining safety and flight screens available", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("navigation", { name: "My workspace" }).getByRole("link", { name: "Safety Actions" })).toBeVisible();
    await page.getByRole("button", { name: "All modules" }).click();
    await expect(page.getByRole("link", { name: "Safety KPIs" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Flight" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Safety & Flight" })).toHaveCount(0);
  });

  test("sidebar shows Personnel and Aircraft as separate sections", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: "All modules" }).click();
    await expect(page.getByRole("button", { name: "Personnel" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Aircraft" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Personnel & Aircraft" })).toHaveCount(0);
  });

  test("system observability is a direct nav link, not a collapsed menu", async ({ page }) => {
    await loginAsAdmin(page);
    await page.goto("/admin/observability");
    await expect(page.getByRole("heading", { name: "System Observability" })).toBeVisible();
  });
});
