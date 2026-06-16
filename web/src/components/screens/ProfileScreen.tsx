import type { DevIdentity } from "../../auth";
import { Icon } from "../Icon";

function initials(id: string): string {
  const clean = id.replace(/[^a-z0-9]/gi, "");
  return (clean.slice(0, 2) || "FX").toUpperCase();
}

// Technician profile. Usage analytics and shared-fix history are Phase 2, so we
// show the real signed-in identity and label the rest as a preview.
export function ProfileScreen({
  identity,
  onOpenSettings,
}: {
  identity: DevIdentity;
  onOpenSettings: () => void;
}) {
  return (
    <div className="screen anim-fade" style={{ position: "relative" }}>
      <div className="hd">
        <div>
          <div className="hdTitle">Profile</div>
          <div className="hdSub">Signed in as {identity.role}</div>
        </div>
        <button className="iconBtn spacer" onClick={onOpenSettings} aria-label="Settings">
          <Icon name="settings" size={20} />
        </button>
      </div>
      <div className="scroll">
        <div className="eqWrap">
          <div className="profHero">
            <div className="avatar">{initials(identity.userId)}</div>
            <div>
              <div className="pName ltr">{identity.userId.slice(0, 18) || "Technician"}</div>
              <div className="pRole">Field technician</div>
            </div>
          </div>

          <div className="statRow">
            <div className="stat">
              <b>—</b>
              <span>Questions</span>
            </div>
            <div className="stat">
              <b style={{ color: "var(--okT)" }}>—</b>
              <span>Helped</span>
            </div>
            <div className="stat">
              <b style={{ color: "var(--infoT)" }}>—</b>
              <span>Fixes shared</span>
            </div>
          </div>

          <div className="sectionLbl">Identity</div>
          <div className="setGroup">
            <div className="setRow">
              <div className="srIc">
                <Icon name="user" size={17} />
              </div>
              <div>
                <div className="srT">Organization</div>
                <div className="srS ltr">{identity.orgId}</div>
              </div>
            </div>
            <div className="setRow">
              <div className="srIc">
                <Icon name="user" size={17} />
              </div>
              <div>
                <div className="srT">User ID</div>
                <div className="srS ltr">{identity.userId}</div>
              </div>
            </div>
          </div>

          <div className="noticeInfo">
            <Icon name="bulb" size={16} />
            <span>Usage stats and your shared-fix history arrive with analytics (Phase 2).</span>
          </div>
        </div>
      </div>
    </div>
  );
}
