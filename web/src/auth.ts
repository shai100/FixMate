// Dev-auth identity (Phase 6.1): the API reads X-Org-Id / X-User-Id / X-Role
// headers when DEV_AUTH=true. We keep the identity in localStorage so it
// survives reloads. When Phase 9 (Keycloak) lands in the client, swap this
// module for the Keycloak JS adapter and emit a Bearer token instead — the
// api.ts call sites only depend on authHeaders().

export interface DevIdentity {
  orgId: string;
  userId: string;
  role: "tech" | "curator" | "admin";
}

const KEY = "fixmate.devIdentity";

export function getIdentity(): DevIdentity | null {
  const raw = localStorage.getItem(KEY);
  return raw ? (JSON.parse(raw) as DevIdentity) : null;
}

export function setIdentity(identity: DevIdentity): void {
  localStorage.setItem(KEY, JSON.stringify(identity));
}

export function clearIdentity(): void {
  localStorage.removeItem(KEY);
}

export function authHeaders(): Record<string, string> {
  const id = getIdentity();
  if (!id) return {};
  return {
    "X-Org-Id": id.orgId,
    "X-User-Id": id.userId,
    "X-Role": id.role,
  };
}
