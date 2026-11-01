const LEGACY_IDENTITY_KEY = "kfl-dms-identity";

/** Remove pre-session role/actor data written by the former localStorage identity flow. */
export function clearLegacyIdentity(): void {
  try {
    window.localStorage.removeItem(LEGACY_IDENTITY_KEY);
  } catch {
    // Storage may be unavailable in hardened browser contexts; server sessions remain authoritative.
  }
}

