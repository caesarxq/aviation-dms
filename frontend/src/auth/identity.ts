export type Identity = { role: string; actor: string };

const STORAGE_KEY = "kfl-dms-identity";
const DEFAULT_IDENTITY: Identity = { role: "system_admin", actor: "admin" };

export function getIdentity(): Identity {
  try {
    const value = window.localStorage.getItem(STORAGE_KEY);
    if (!value) return DEFAULT_IDENTITY;
    const parsed = JSON.parse(value) as Partial<Identity>;
    if (typeof parsed.role !== "string" || typeof parsed.actor !== "string") return DEFAULT_IDENTITY;
    return { role: parsed.role, actor: parsed.actor };
  } catch {
    return DEFAULT_IDENTITY;
  }
}

export function setIdentity(identity: Identity): void {
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(identity));
}

export function clearIdentity(): void {
  window.localStorage.removeItem(STORAGE_KEY);
}
