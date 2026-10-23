import { test, expect } from "@playwright/test";

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
    await page.click("nav >> text=Missions");
    await expect(page).toHaveURL(/\/missions/);
    await expect(page.getByRole("heading", { name: "Missions" })).toBeVisible();
  });

  test("notifications page accessible", async ({ page }) => {
    await page.goto("/notifications");
    await expect(page.getByRole("heading", { name: "Notifications" })).toBeVisible();
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

test.describe("Occurrences", () => {
  test("loads occurrences page", async ({ page }) => {
    await page.goto("/occurrences");
    await expect(page.locator("body")).toBeVisible();
  });
});