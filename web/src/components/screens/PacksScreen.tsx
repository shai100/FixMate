import type { Equipment } from "../../types";
import { Icon } from "../Icon";

// Offline packs are Phase 2 (no backend yet). This screen reproduces the
// mockup's design against real equipment names and is explicitly labelled as a
// preview so it never masquerades as a working feature.
export function PacksScreen({
  equipment,
  onOpenSettings,
}: {
  equipment: Equipment[];
  onOpenSettings: () => void;
}) {
  return (
    <div className="screen anim-fade" style={{ position: "relative" }}>
      <div className="hd">
        <div>
          <div className="hdTitle">Offline packs</div>
          <div className="hdSub">Answers without signal · preview</div>
        </div>
        <button className="iconBtn spacer" onClick={onOpenSettings} aria-label="Settings">
          <Icon name="settings" size={20} />
        </button>
      </div>
      <div className="scroll">
        <div className="eqWrap">
          <div className="noticeInfo">
            <Icon name="wifi" size={16} />
            <span>
              Packs will answer from cached manual sections &amp; approved fixes
              when you have no signal. Pack building ships in Phase 2.
            </span>
          </div>
          {equipment.length === 0 && (
            <div className="emptyHint">No equipment available to pack yet.</div>
          )}
          {equipment.map((e) => (
            <div className="packCard" key={e.id}>
              <span className="eqIc">
                <Icon name="pack" size={20} />
              </span>
              <div className="pcBody">
                <div className="pcName ltr">{e.name}</div>
                <div className="pcMeta">
                  {[e.manufacturer, e.model].filter(Boolean).join(" · ") || "manual pack"} · not downloaded
                </div>
              </div>
              <span className="chip outline pcState">
                <Icon name="download" size={13} />
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
