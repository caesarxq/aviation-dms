import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

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
    await page.goto("/documents");
    await expect(page.locator("text=View").first()).toBeVisible();
    await expect(page.locator("text=Edit").first()).toBeVisible();
  });
});

test.describe("Navigation", () => {
  test("sidebar navigation works", async ({ page }) => {
    await page.goto("/");
    // Safety & Flight section is collapsed by default; expand it first
    await page.getByRole("button", { name: "Safety & Flight" }).click();
    await page.getByRole("link", { name: "Missions" }).click();
    await expect(page).toHaveURL(/\/missions/);
    await expect(page.getByRole("heading", { name: "Missions" })).toBeVisible();
  });

  test("notifications page accessible", async ({ page }) => {
    await page.goto("/notifications");
    await expect(page.getByRole("heading", { name: "Notifications" })).toBeVisible();
  });

  test("sidebar exposes the revised control structure", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("link", { name: "Dashboard" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Operations" })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Fleet & Registry" })).toHaveCount(0);

    await page.getByRole("button", { name: "Document Control" }).click();
    await expect(page.getByRole("link", { name: "Documents" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Document Viewer" })).toHaveCount(0);
    await expect(page.getByRole("link", { name: "Document Editor" })).toHaveCount(0);
  });

  test("system administrator observability page loads", async ({ page }) => {
    await page.goto("/admin/observability");
    await expect(page.getByRole("heading", { name: "System Observability" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Role matrix" })).toBeVisible();
    await expect(page.getByRole("cell", { name: "system_admin" }).first()).toBeVisible();
  });

  test("document editor exposes a draggable toolbar", async ({ page }) => {
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
    await page.goto("/documents/DOC-001/edit");
    const editor = page.locator('[contenteditable="true"]');
    await editor.click();
    await page.keyboard.press("End");
    await page.keyboard.type(" live-suggestion-test");
    await expect(page.getByTestId("inline-suggestion-stream")).toContainText("live-suggestion-test");
    await expect(page.locator("ins").filter({ hasText: "live-suggestion-test" })).toBeVisible();
  });

  test("opens the submit modal with auto-detected section references", async ({ page }) => {
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
  test("viewer provides heading outline navigation and fullscreen fallback", async ({ page }) => {
    await page.goto("/documents/DOC-001/view");
    await expect(page.getByRole("heading", { name: "DOC-001" })).toBeVisible();
    await page.getByTitle("Show document outline").click();
    await expect(page.getByRole("navigation", { name: "Document outline" })).toBeVisible();
    await expect(page.getByRole("button", { name: "1.1 THE COMPANY", exact: true })).toBeVisible();
    await page.getByRole("button", { name: "1.1 THE COMPANY", exact: true }).click();
    await expect(page.getByRole("button", { name: "1.1 THE COMPANY", exact: true })).toHaveClass(/font-semibold/);
    const viewerScroll = await page.frames().find((frame) => frame !== page.mainFrame() && frame.url() === "about:blank")?.evaluate(() => document.querySelector<HTMLElement>("#page-container")?.scrollTop || 0);
    expect(viewerScroll).toBeGreaterThan(0);
    await page.getByTitle("Enter fullscreen").click();
    await expect(page.getByTitle("Exit fullscreen")).toBeVisible();
  });

  test("editor outline navigation scrolls to the selected heading", async ({ page }) => {
    await page.goto("/documents/DOC-001/edit");
    await page.getByTitle("Show document outline").click();
    await expect(page.getByRole("button", { name: "1.1 THE COMPANY", exact: true })).toBeVisible();
    await page.getByRole("button", { name: "1.1 THE COMPANY", exact: true }).click();
    await expect(page.getByRole("button", { name: "1.1 THE COMPANY", exact: true })).toHaveClass(/font-semibold/);
    await expect(page.locator('[contenteditable="true"] .proposal-target-highlight')).toHaveCount(1);
    await expect(page.locator('[contenteditable="true"] .proposal-target-highlight')).toBeVisible();
  });

  test("submitting a proposal clears pending editor suggestions", async ({ page }) => {
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
  test("renders the source manual inside the iframe", async ({ page }) => {
    await page.goto("/documents/DOC-001/view");
    await expect(page.getByRole("heading", { name: "DOC-001" })).toBeVisible();
    const frame = page.frames().find((candidate) => candidate !== page.mainFrame() && candidate.url() === "about:blank");
    expect(frame).toBeDefined();
    await expect(frame!.locator("body")).toContainText("COMPANY OPERATIONS MANUAL", { timeout: 20000 });
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

  test("can create a risk assessment", async ({ page }) => {
    await page.goto("/risk-assessments");
    await page.click("text=New Assessment");
    await page.waitForSelector('input[placeholder="Assessment title"]');
    await page.fill('input[placeholder="Assessment title"]', "E2E Test Risk Assessment");
    await page.fill('textarea[placeholder="Describe the risk scenario"]', "A test risk assessment for E2E validation");
    await page.click("text=Submit Assessment");
    await page.waitForTimeout(1500);
    await expect(page.locator("table").locator("text=E2E Test Risk Assessment").first()).toBeVisible({ timeout: 8000 });
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
    await page.fill('input[placeholder="e.g. u-safety"]', "u-safety");
    await page.click("text=Open Investigation");
    await page.waitForTimeout(1500);
    await expect(page.locator("text=u-safety").first()).toBeVisible({ timeout: 8000 });
  });
});

test.describe("Accessibility", () => {
  for (const route of ["/documents", "/documents/DOC-001/edit", "/documents/DOC-001/view", "/hazards", "/risk-assessments", "/investigations"]) {
    test(`${route} has no automated accessibility violations`, async ({ page }) => {
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
