/**
 * The dev-only sign-in screen.
 *
 * Two ways in: if the backend has auto-login enabled it drops straight into the
 * demo tenant as admin (no typing); otherwise it shows a form where a developer
 * pastes the org/user UUIDs printed by `scripts/seed_demo.py` and picks a role.
 * Either way it stores the chosen identity (via `setIdentity`) and notifies the
 * parent through `onLogin`. This is replaced by the Keycloak login redirect when
 * Phase 9 reaches the client.
 */
import { useEffect, useState } from "react";
import { setIdentity, type DevIdentity } from "../auth";
import { api } from "../api";
import { Icon } from "./Icon";

/** @param onLogin Called with the chosen identity once sign-in succeeds. */
export function DevLogin({ onLogin }: { onLogin: (id: DevIdentity) => void }) {
  const [orgId, setOrgId] = useState("");
  const [userId, setUserId] = useState("");
  const [role, setRole] = useState<DevIdentity["role"]>("tech");
  const [busy, setBusy] = useState(false);
  // When DEV_AUTO_LOGIN is on the backend, drop straight into the demo tenant as
  // admin — no UUID paste. A 404 (feature off / not seeded) just shows the form.
  const [autoTrying, setAutoTrying] = useState(true);

  useEffect(() => {
    let active = true;
    api
      .devAutoLogin()
      .then((id) => {
        if (!active) return;
        const identity: DevIdentity = { orgId: id.org_id, userId: id.user_id, role: id.role };
        setIdentity(identity);
        onLogin(identity);
      })
      .catch(() => {
        if (active) setAutoTrying(false);
      });
    return () => {
      active = false;
    };
  }, [onLogin]);

  if (autoTrying) {
    return (
      <div className="screen signin">
        <div className="signin__inner" style={{ alignItems: "center" }}>
          <span className="spin" />
        </div>
      </div>
    );
  }

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!orgId || !userId) return;
    setBusy(true);
    const id: DevIdentity = { orgId, userId, role };
    setIdentity(id);
    // Brief spinner to match the mockup's sign-in feel before routing.
    setTimeout(() => onLogin(id), 200);
  }

  return (
    <form className="screen signin" onSubmit={submit}>
      <div className="signin__inner">
        <div className="siBrand">
          <div className="logoMark">
            <Icon name="wrench" size={30} />
          </div>
          <div className="name">FixMate</div>
          <div className="tag">Your AI repair copilot</div>
        </div>

        <div>
          <label className="fieldLbl" htmlFor="org">
            Organization ID
          </label>
          <input
            id="org"
            className="inp ltr"
            value={orgId}
            onChange={(e) => setOrgId(e.target.value)}
            placeholder="org UUID from seed_demo.py"
            required
          />
        </div>
        <div>
          <label className="fieldLbl" htmlFor="user">
            User ID
          </label>
          <input
            id="user"
            className="inp ltr"
            value={userId}
            onChange={(e) => setUserId(e.target.value)}
            placeholder="user UUID from seed_demo.py"
            required
          />
        </div>
        <div>
          <label className="fieldLbl" htmlFor="role">
            Role
          </label>
          <select
            id="role"
            className="inp"
            value={role}
            onChange={(e) => setRole(e.target.value as DevIdentity["role"])}
          >
            <option value="tech">tech</option>
            <option value="curator">curator</option>
            <option value="admin">admin</option>
          </select>
        </div>

        <button type="submit" className="btn" disabled={!orgId || !userId || busy}>
          {busy ? <span className="spin" /> : <span>Continue</span>}
        </button>
        <div className="siDivider">dev auth</div>
        <div className="fixFoot">
          DEV_AUTH header identity. Swaps to Keycloak SSO in Phase 9.
        </div>
      </div>
    </form>
  );
}
