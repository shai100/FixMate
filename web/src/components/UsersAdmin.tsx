/**
 * The Users admin screen — admin-only user and role management (FR-14).
 *
 * Add users, edit their name/email, change their role, and delete them; every
 * change is audited server-side. Role assignment is the sensitive part:
 * promoting a tech to curator is exactly what grants them access to the review
 * queue. Updates are applied to the in-memory list optimistically. Exports the
 * screen plus the `UserItem` row component.
 */
import { useEffect, useState } from "react";
import { api, ApiError } from "../api";
import type { UserRow } from "../types";

/** The selectable roles, in increasing privilege order. */
const ROLES: UserRow["role"][] = ["tech", "curator", "admin"];

export function UsersAdmin() {
  const [users, setUsers] = useState<UserRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  const [newName, setNewName] = useState("");
  const [newEmail, setNewEmail] = useState("");
  const [newRole, setNewRole] = useState<UserRow["role"]>("tech");
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    api
      .listUsers()
      .then((u) => {
        setUsers(u);
        setError(null);
      })
      .catch((e) => setError(e instanceof ApiError ? e.detail : "Could not load users"));
  }, []);

  function fail(e: unknown, fallback: string) {
    setError(e instanceof ApiError ? e.detail : fallback);
  }

  async function changeRole(user: UserRow, role: UserRow["role"]) {
    if (role === user.role) return;
    setBusyId(user.id);
    setError(null);
    try {
      const updated = await api.setUserRole(user.id, role);
      setUsers((prev) => prev?.map((u) => (u.id === updated.id ? updated : u)) ?? null);
    } catch (e) {
      fail(e, "Could not change role");
    } finally {
      setBusyId(null);
    }
  }

  async function saveDetails(user: UserRow, name: string, email: string) {
    const trimmed = name.trim();
    if (!trimmed || (trimmed === user.name && email === (user.email ?? ""))) return;
    setBusyId(user.id);
    setError(null);
    try {
      const updated = await api.updateUser(user.id, { name: trimmed, email: email || null });
      setUsers((prev) => prev?.map((u) => (u.id === updated.id ? updated : u)) ?? null);
    } catch (e) {
      fail(e, "Could not save user");
    } finally {
      setBusyId(null);
    }
  }

  async function remove(user: UserRow) {
    if (!confirm(`Delete user "${user.name}"? This cannot be undone.`)) return;
    setBusyId(user.id);
    setError(null);
    try {
      await api.deleteUser(user.id);
      setUsers((prev) => prev?.filter((u) => u.id !== user.id) ?? null);
    } catch (e) {
      fail(e, "Could not delete user");
    } finally {
      setBusyId(null);
    }
  }

  async function create(e: React.FormEvent) {
    e.preventDefault();
    if (!newName.trim()) return;
    setCreating(true);
    setError(null);
    try {
      const created = await api.createUser({
        name: newName.trim(),
        email: newEmail || null,
        role: newRole,
      });
      setUsers((prev) => [...(prev ?? []), created]);
      setNewName("");
      setNewEmail("");
      setNewRole("tech");
    } catch (e) {
      fail(e, "Could not create user");
    } finally {
      setCreating(false);
    }
  }

  return (
    <section className="console-section" aria-label="Users admin">
      <h2>Users</h2>
      {error && <p className="console-error">{error}</p>}

      <form className="user-create" onSubmit={create} aria-label="Add user">
        <input
          className="inp"
          placeholder="Name"
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
          aria-label="New user name"
          required
        />
        <input
          className="inp"
          placeholder="Email (optional)"
          value={newEmail}
          onChange={(e) => setNewEmail(e.target.value)}
          aria-label="New user email"
        />
        <select
          className="inp"
          value={newRole}
          onChange={(e) => setNewRole(e.target.value as UserRow["role"])}
          aria-label="New user role"
        >
          {ROLES.map((r) => (
            <option key={r} value={r}>
              {r}
            </option>
          ))}
        </select>
        <button type="submit" className="btn" disabled={creating || !newName.trim()}>
          {creating ? "Adding…" : "Add user"}
        </button>
      </form>

      <ul className="console-list" data-testid="user-list">
        {users?.map((u) => (
          <UserItem
            key={u.id}
            user={u}
            busy={busyId === u.id}
            onChangeRole={changeRole}
            onSaveDetails={saveDetails}
            onDelete={remove}
          />
        ))}
      </ul>
    </section>
  );
}

/** One editable user row (name, email, role) with save and delete actions. */
function UserItem({
  user,
  busy,
  onChangeRole,
  onSaveDetails,
  onDelete,
}: {
  user: UserRow;
  busy: boolean;
  onChangeRole: (u: UserRow, role: UserRow["role"]) => void;
  onSaveDetails: (u: UserRow, name: string, email: string) => void;
  onDelete: (u: UserRow) => void;
}) {
  // Local edit buffer; the parent re-keys this row by user id, so a different
  // user remounts with fresh state rather than needing an effect to resync.
  const [name, setName] = useState(user.name);
  const [email, setEmail] = useState(user.email ?? "");

  const dirty = name.trim() !== user.name || email !== (user.email ?? "");

  return (
    <li className="user-row">
      <input
        className="inp"
        value={name}
        disabled={busy}
        onChange={(e) => setName(e.target.value)}
        aria-label={`Name for ${user.name}`}
      />
      <input
        className="inp"
        value={email}
        disabled={busy}
        placeholder="no email"
        onChange={(e) => setEmail(e.target.value)}
        aria-label={`Email for ${user.name}`}
      />
      <label htmlFor={`role-${user.id}`} className="visually-hidden">
        Role for {user.name}
      </label>
      <select
        id={`role-${user.id}`}
        value={user.role}
        disabled={busy}
        onChange={(e) => onChangeRole(user, e.target.value as UserRow["role"])}
      >
        {ROLES.map((r) => (
          <option key={r} value={r}>
            {r}
          </option>
        ))}
      </select>
      <button
        type="button"
        className="btn btn--ghost"
        disabled={busy || !dirty}
        onClick={() => onSaveDetails(user, name, email)}
      >
        Save
      </button>
      <button
        type="button"
        className="btn btn--danger"
        disabled={busy}
        onClick={() => onDelete(user)}
        aria-label={`Delete ${user.name}`}
      >
        Delete
      </button>
    </li>
  );
}
