import { describe, expect, it, beforeEach } from "vitest";
import { clearLegacyIdentity } from "./identity";

beforeEach(() => localStorage.clear());

describe("legacy local identity cleanup", () => {
  it("removes the former localStorage role/actor override", () => {
    localStorage.setItem("kfl-dms-identity", JSON.stringify({ role: "system_admin", actor: "admin" }));
    clearLegacyIdentity();
    expect(localStorage.getItem("kfl-dms-identity")).toBeNull();
  });
});

