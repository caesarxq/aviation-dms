import { describe, expect, it } from "vitest";
import { canAccessScreen, hasPermission, getPostLoginPath } from "./permissions";

const librarian = { role: "librarian", active_role: "librarian", permissions: ["document:read", "distribution:manage"] };
const security = { role: "head_security", active_role: "head_security", permissions: ["safety:read", "security:read_sensitive"] };
const admin = { role: "system_admin", active_role: "system_admin", permissions: ["document:read", "security:read_sensitive", "safety:read"] };

describe("authentication authorization policy", () => {
  it("denies access when no authenticated profile exists", () => {
    expect(hasPermission(null, "document:read")).toBe(false);
    expect(canAccessScreen(null, { permission: "document:read" })).toBe(false);
  });

  it("grants a screen only when the server profile includes its permission", () => {
    expect(canAccessScreen(librarian, { permission: "document:read" })).toBe(true);
    expect(canAccessScreen(librarian, { permission: "document:approve" })).toBe(false);
  });

  it("enforces role-limited zones independently of permission lists", () => {
    expect(canAccessScreen(security, { role: "head_security" })).toBe(true);
    expect(canAccessScreen(security, { role: "system_admin" })).toBe(false);
    expect(canAccessScreen(admin, { role: "system_admin" })).toBe(true);
  });

  it("requires all permissions when a screen declares a permission list", () => {
    expect(canAccessScreen(security, { permissions: ["safety:read", "security:read_sensitive"] })).toBe(true);
    expect(canAccessScreen(security, { permissions: ["security:read_sensitive", "security:manage"] })).toBe(false);
  });

  it("routes profiles without dashboard access to an accessible landing screen", () => {
    const recordsCustodian = { role: "records_custodian", active_role: "records_custodian", permissions: ["document:read", "audit:read"] };
    expect(getPostLoginPath(recordsCustodian)).toBe("/documents");
    expect(getPostLoginPath(recordsCustodian, "/")).toBe("/documents");
    expect(getPostLoginPath(recordsCustodian, "/notifications")).toBe("/documents");
  });

  it("preserves an authorized local return path and falls back from an unauthorized one", () => {
    const recordsCustodian = { role: "records_custodian", permissions: ["document:read"] };
    expect(getPostLoginPath(recordsCustodian, "/documents/DOC-001/view")).toBe("/documents/DOC-001/view");
    expect(getPostLoginPath(recordsCustodian, "//example.com")).toBe("/documents");
    expect(getPostLoginPath(recordsCustodian, "/admin/observability")).toBe("/documents");
  });

  it("keeps the dashboard as the landing screen for profiles with safety access", () => {
    expect(getPostLoginPath(security)).toBe("/");
    expect(getPostLoginPath(admin, "/notifications")).toBe("/notifications");
  });

  it("aligns audit return paths with report and finding read permissions", () => {
    const reportReader = { role: "independent_auditor", active_role: "independent_auditor", permissions: ["audit_report:read"] };
    const findingReader = { role: "head_quality", active_role: "head_quality", permissions: ["audit_finding:read"] };
    expect(getPostLoginPath(reportReader, "/audit-reports")).toBe("/audit-reports");
    expect(getPostLoginPath(reportReader, "/audit-findings")).toBe("/account/security");
    expect(getPostLoginPath(findingReader, "/audit-findings")).toBe("/audit-findings");
  });
});
