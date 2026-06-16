/**
 * Dev-only client-side authentication (Phase 6.1).
 *
 * In local development the backend trusts X-Org-Id / X-User-Id / X-Role request
 * headers (DEV_AUTH=true). This module is the client side of that: it stores the
 * chosen identity in the browser's localStorage so it survives page reloads, and
 * turns it into the headers every API call attaches. When Keycloak (Phase 9)
 * lands in the client, only this module changes — it would emit a Bearer token
 * instead — because every caller depends solely on `authHeaders()`.
 */

/** The signed-in identity: which tenant, which user, and their role. */
export interface DevIdentity {
  orgId: string;
  userId: string;
  role: "tech" | "curator" | "admin";
}

const KEY = "fixmate.devIdentity";

/** Read the stored identity, or null if no one is signed in. */
export function getIdentity(): DevIdentity | null {
  const raw = localStorage.getItem(KEY);
  return raw ? (JSON.parse(raw) as DevIdentity) : null;
}

/** Persist the identity to localStorage (sign in). */
export function setIdentity(identity: DevIdentity): void {
  localStorage.setItem(KEY, JSON.stringify(identity));
}

/** Remove the stored identity (sign out). */
export function clearIdentity(): void {
  localStorage.removeItem(KEY);
}

/** Build the auth headers for an API request (empty object if signed out). */
export function authHeaders(): Record<string, string> {
  const id = getIdentity();
  if (!id) return {};
  return {
    "X-Org-Id": id.orgId,
    "X-User-Id": id.userId,
    "X-Role": id.role,
  };
}
