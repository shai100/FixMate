import { useState } from "react";
import type { DevIdentity } from "../../auth";
import { Icon } from "../Icon";

// Settings. Text size is functional (scales the root rem unit, per the mockup's
// "layout holds to 130%" glove/low-light requirement). Voice/notification
// toggles are cosmetic placeholders until those features land.
export function SettingsScreen({
  identity,
  onBack,
  onSignOut,
}: {
  identity: DevIdentity;
  onBack: () => void;
  onSignOut: () => void;
}) {
  const [scale, setScale] = useState(100);
  const [voice, setVoice] = useState(true);
  const [notif, setNotif] = useState(true);

  function applyScale(v: number) {
    setScale(v);
    document.documentElement.style.fontSize = `${v}%`;
  }

  return (
    <div className="screen anim-fwd" style={{ position: "relative" }}>
      <div className="hd">
        <button className="iconBtn" onClick={onBack} aria-label="Back">
          <Icon name="back" size={22} />
        </button>
        <div className="hdTitle">Settings</div>
      </div>
      <div className="scroll">
        <div className="eqWrap">
          <div className="sectionLbl">Display</div>
          <div className="setGroup">
            <div className="setRow">
              <div className="srIc">
                <Icon name="text" size={17} />
              </div>
              <div>
                <div className="srT">Text size</div>
                <div className="srS">Layout holds up to 130%</div>
              </div>
              <div className="slider">
                <input
                  type="range"
                  min={100}
                  max={130}
                  step={10}
                  value={scale}
                  onChange={(e) => applyScale(Number(e.target.value))}
                  aria-label="Text size"
                />
                <span className="sliderVal ltr">{scale}%</span>
              </div>
            </div>
          </div>

          <div className="sectionLbl">Input &amp; alerts</div>
          <div className="setGroup">
            <button className="setRow" onClick={() => setVoice((v) => !v)}>
              <div className="srIc">
                <Icon name="mic" size={17} />
              </div>
              <div>
                <div className="srT">Voice input</div>
                <div className="srS">Hands-free questions</div>
              </div>
              <span className={`switch${voice ? " on" : ""}`} aria-pressed={voice} />
            </button>
            <button className="setRow" onClick={() => setNotif((v) => !v)}>
              <div className="srIc">
                <Icon name="bell" size={17} />
              </div>
              <div>
                <div className="srT">Notifications</div>
                <div className="srS">Fix review results, pack updates</div>
              </div>
              <span className={`switch${notif ? " on" : ""}`} aria-pressed={notif} />
            </button>
          </div>

          <div className="sectionLbl">Account</div>
          <div className="setGroup">
            <div className="setRow">
              <div className="srIc">
                <Icon name="user" size={17} />
              </div>
              <div>
                <div className="srT">Role</div>
                <div className="srS ltr">{identity.role}</div>
              </div>
            </div>
            <button className="setRow" onClick={onSignOut}>
              <div className="srIc">
                <Icon name="logout" size={17} />
              </div>
              <div>
                <div className="srT">Sign out</div>
              </div>
            </button>
          </div>

          <div
            className="ltr"
            style={{
              textAlign: "center",
              color: "var(--txt3)",
              fontSize: ".66rem",
              fontFamily: "var(--mono)",
              padding: "8px 0",
            }}
          >
            FixMate · web client
          </div>
        </div>
      </div>
    </div>
  );
}
