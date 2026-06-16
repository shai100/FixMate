import { useEffect, useState } from "react";
import { api, ApiError } from "../api";
import type { UserRow } from "../types";

const ROLES: UserRow["role"][] = ["tech", "curator", "admin"];

// Admin-only role assignment (FR-14). Promoting a tech to curator is what lets
// them into the review queue; every change is audited server-side.
export function UsersAdmin() {
  const [users, setUsers] = useState<UserRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [savingId, setSavingId] = useState<string | null>(null);

  useEffect(() => {
    api
      .listUsers()
      .then((u) => {
        setUsers(u);
        setError(null);
      })
      .catch((e) => setError(e instanceof ApiError ? e.detail : "Could not load users"));
  }, []);

  async function changeRole(user: UserRow, role: UserRow["role"]) {
    if (role === user.role) return;
    setSavingId(user.id);
    setError(null);
    try {
      const updated = await api.setUserRole(user.id, role);
      setUsers((prev) => prev?.map((u) => (u.id === updated.id ? updated : u)) ?? null);
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : "Could not change role");
    } finally {
      setSavingId(null);
    }
  }

  return (
    <section className="console-section" aria-label="Users admin">
      <h2>Users</h2>
      {error && <p className="console-error">{error}</p>}
      <ul className="console-list" data-testid="user-list">
        {users?.map((u) => (
          <li key={u.id} className="user-row">
            <span>
              <strong>{u.name}</strong>{" "}
              <span className="console-muted">{u.email ?? "no email"}</span>
            </span>
            <label htmlFor={`role-${u.id}`} className="visually-hidden">
              Role for {u.name}
            </label>
            <select
              id={`role-${u.id}`}
              value={u.role}
              disabled={savingId === u.id}
              onChange={(e) => changeRole(u, e.target.value as UserRow["role"])}
            >
              {ROLES.map((r) => (
                <option key={r} value={r}>
                  {r}
                </option>
              ))}
            </select>
          </li>
        ))}
      </ul>
    </section>
  );
}
