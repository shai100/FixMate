import { useState } from "react";
import { setIdentity, type DevIdentity } from "../auth";

// Dev-only identity entry (Phase 6 dev auth). Replaced by the Keycloak login
// redirect when Phase 9 reaches the client. Lets a developer paste the org/user
// UUIDs printed by scripts/seed_demo.py and start chatting.
export function DevLogin({ onLogin }: { onLogin: (id: DevIdentity) => void }) {
  const [orgId, setOrgId] = useState("");
  const [userId, setUserId] = useState("");
  const [role, setRole] = useState<DevIdentity["role"]>("tech");

  return (
    <form
      className="dev-login"
      onSubmit={(e) => {
        e.preventDefault();
        const id: DevIdentity = { orgId, userId, role };
        setIdentity(id);
        onLogin(id);
      }}
    >
      <h2>Sign in (dev)</h2>
      <label htmlFor="org">Organization ID</label>
      <input id="org" value={orgId} onChange={(e) => setOrgId(e.target.value)} required />
      <label htmlFor="user">User ID</label>
      <input id="user" value={userId} onChange={(e) => setUserId(e.target.value)} required />
      <label htmlFor="role">Role</label>
      <select
        id="role"
        value={role}
        onChange={(e) => setRole(e.target.value as DevIdentity["role"])}
      >
        <option value="tech">tech</option>
        <option value="curator">curator</option>
        <option value="admin">admin</option>
      </select>
      <button type="submit" disabled={!orgId || !userId}>
        Continue
      </button>
    </form>
  );
}
