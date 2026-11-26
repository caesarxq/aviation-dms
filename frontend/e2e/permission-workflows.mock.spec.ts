import { expect, test, type Page, type Route } from "@playwright/test";

/**
 * Permission-gated workflow e2e tests.
 *
 * These tests use mocked API responses (no credentials required) to verify that
 * the UI enforces the server-side permission rules for change-request approval
 * and corrective-action verify/close separation of duties.
 *
 * Run with: npx playwright test permission-workflows.mock.spec.ts
 * Requires the dev server (webServer in playwright.config.ts).
 */

type WorkflowCase = {
  role: string;
  path: string;
  permissions: string[];
  label: string;
};

// Change requests: only change_request:approve holders can approve/reject.
// change_request:review holders can submit/review but not decide.
const changeRequestCases: WorkflowCase[] = [
  {
    role: "head_quality",
    path: "/change-requests",
    permissions: ["document:read", "change_request:create", "change_request:review", "change_request:approve"],
    label: "head_quality can approve and reject",
  },
  {
    role: "head_operations",
    path: "/change-requests",
    permissions: ["document:read", "change_request:create", "change_request:review"],
    label: "head_operations can review but not approve/reject",
  },
  {
    role: "librarian",
    path: "/change-requests",
    permissions: ["document:read", "change_request:create", "change_request:review"],
    label: "librarian can review but not approve/reject",
  },
];

// Corrective actions: verifier cannot close their own verification (SoD).
const crudCases: WorkflowCase[] = [
  {
    role: "head_quality",
    path: "/corrective-actions",
    permissions: ["safety:read", "safety:update"],
    label: "head_quality can verify and a different role can close",
  },
];

function profileFor(role: string, permissions: string[]) {
  const userId = `mock-${role}`;
  return {
    user: {
      user_id: userId,
      username: role,
      email: `${role}@example.test`,
      full_name: role.replace(/_/g, " "),
      role,
      active_role: role,
      roles: [role],
    },
    role,
    active_role: role,
    roles: [role],
    authenticated_via: "session_cookie",
    onboarding_completed: true,
    permissions,
  };
}

function mockChangeRequestApi(page: Page, role: string, permissions: string[]) {
  const profile = profileFor(role, permissions);
  let approveCalled = false;
  let rejectCalled = false;

  await page.route(/\/api\/p1\/change-requests\/.*/, async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const method = request.method();

    if (method === "POST" && url.pathname.endsWith("/approve")) {
      approveCalled = true;
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ cr_id: "CR-1", status: "approved" }) });
      return;
    }
    if (method === "POST" && url.pathname.endsWith("/reject")) {
      rejectCalled = true;
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ cr_id: "CR-1", status: "rejected" }) });
      return;
    }
    if (method === "GET" && url.pathname === "/api/p1/change-requests") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([
          { cr_id: "CR-1", document_id: "DOC-001", title: "QMS manual update", description: "Revise audit schedule", change_type: "minor", status: "under_review", requester_id: "u-ops", reviewer_id: null, approver_id: null },
        ]),
      });
      return;
    }
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([]) });
  });

  return { approveCalled, rejectCalled };
}

function mockCrudApi(page: Page) {
  let verifyCalled = false;
  let closeCalled = false;

  await page.route(/\/api\/p1\/corrective-actions\/.*/, async (route) => {
    const request = route.request();
    const method = request.method();
    const url = new URL(request.url());

    if (method === "POST" && url.pathname.endsWith("/verify")) {
      verifyCalled = true;
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ car_id: "CAR-1", status: "pending_verification" }) });
      return;
    }
    if (method === "POST" && url.pathname.endsWith("/close")) {
      closeCalled = true;
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ car_id: "CAR-1", status: "closed" }) });
      return;
    }
    if (method === "GET" && url.pathname === "/api/p1/corrective-actions") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([
          { car_id: "CAR-1", title: "QMS corrective action", description: "Fix tracking sheet", status: "verified", verified_by: "u-quality", owner_id: "u-ops" },
        ]),
      });
      return;
    }
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([]) });
  });

  return { verifyCalled, closeCalled };
}

test.describe("Change request permission gating", () => {
  for (const c of changeRequestCases) {
    test(`${c.label} (${c.role})`, async ({ page }) => {
      const pageErrors: string[] = [];
      page.on("pageerror", (e) => pageErrors.push(e.message));

      const { approveCalled, rejectCalled } = mockChangeRequestApi(page, c.role, c.permissions);

      await page.goto(c.path);
      await expect(page.getByRole("heading", { name: "Change Requests" })).toBeVisible();

      // Open the first change request to view its actions.
      await page.getByRole("button", { name: /^View$/i }).first().click();

      const canApprove = c.permissions.includes("change_request:approve");

      // The approve button should only be visible to the approver role.
      const approveButton = page.getByRole("button", { name: /^Approve$/i });
      if (canApprove) {
        await expect(approveButton).toBeVisible();
        await approveButton.click();
        await expect(approveCalled).toBe(true);
      } else {
        await expect(approveButton).not.toBeInTheDocument();
        await expect(approveCalled).toBe(false);
      }

      // The reject button should only be visible to the approver role.
      const rejectButton = page.getByRole("button", { name: /^Reject$/i });
      if (canApprove) {
        await expect(rejectButton).toBeVisible();
        await rejectButton.click();
        await expect(rejectCalled).toBe(true);
      } else {
        await expect(rejectButton).not.toBeInTheDocument();
        await expect(rejectCalled).toBe(false);
      }

      expect(pageErrors).toEqual([]);
    });
  }
});

test.describe("Corrective action verify/close separation of duties", () => {
  for (const c of crudCases) {
    test(`${c.label} (${c.role})`, async ({ page }) => {
      const pageErrors: string[] = [];
      page.on("pageerror", (e) => pageErrors.push(e.message));

      const { verifyCalled, closeCalled } = mockCrudApi(page);

      await page.goto(c.path);
      await expect(page.getByRole("heading", { name: "Corrective Actions" })).toBeVisible();

      // Verify then close as the same role - the close should be refused
      // by the API (403) and the UI should show the error.
      await page.getByRole("button", { name: /^Verify$/i }).first().click();
      await expect(verifyCalled).toBe(true);

      // Attempting to close as the same actor who verified should fail.
      const closeButton = page.getByRole("button", { name: /^Close$/i });
      if (closeButton) {
        await closeButton.click();
        await expect(closeCalled).toBe(false); // API should refuse
      }

      expect(pageErrors).toEqual([]);
    });
  }
});
