/**
 * The equipment-selection screen — the first step of the technician flow (FR-10).
 *
 * Picking a piece of equipment scopes the upcoming conversation to its manuals
 * and approved fixes (retrieval filters by `equipment_id`), or "General" for no
 * scope. The list is provided by the parent (loaded once in <App>) and filtered
 * locally by a search box over name/manufacturer/model. Selecting an item calls
 * `onSelect`, which moves the app to the chat screen.
 */
import { useMemo, useState } from "react";
import type { Equipment } from "../types";
import { Icon } from "./Icon";

export function EquipmentPicker({
  equipment,
  loading,
  error,
  onSelect,
  onOpenSettings,
}: {
  equipment: Equipment[];
  loading: boolean;
  error: string | null;
  onSelect: (equipment: Equipment | null) => void;
  onOpenSettings: () => void;
}) {
  const [query, setQuery] = useState("");

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return equipment;
    return equipment.filter((e) =>
      [e.name, e.manufacturer, e.model]
        .filter(Boolean)
        .some((s) => s!.toLowerCase().includes(q)),
    );
  }, [equipment, query]);

  return (
    <div className="screen anim-fade">
      <div className="hd">
        <div className="logoMark" style={{ width: 34, height: 34, borderRadius: 10, margin: 0, boxShadow: "none" }}>
          <Icon name="wrench" size={17} />
        </div>
        <div>
          <div className="hdTitle">Select equipment</div>
          <div className="hdSub">Scopes answers to its manuals &amp; fixes</div>
        </div>
        <button className="iconBtn spacer" onClick={onOpenSettings} aria-label="Settings">
          <Icon name="settings" size={20} />
        </button>
      </div>

      <div className="scroll">
        <div className="eqWrap">
          <div className="searchBox">
            <Icon name="search" size={17} />
            <input
              className="inp"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search model…"
              aria-label="Search equipment"
            />
          </div>

          {loading && <div className="emptyHint">Loading equipment…</div>}
          {error && <div className="emptyHint" style={{ color: "#fca5a5" }}>{error}</div>}

          {!loading && !error && (
            <>
              <div className="sectionLbl">Equipment</div>
              <div style={{ display: "flex", flexDirection: "column", gap: 9 }}>
                <button className="eqCard" onClick={() => onSelect(null)}>
                  <span className="eqIc">
                    <Icon name="grid" size={20} />
                  </span>
                  <span style={{ minWidth: 0 }}>
                    <span className="eqName">General</span>
                    <span className="eqMeta">No specific equipment</span>
                  </span>
                  <span className="chev">
                    <Icon name="chevR" size={18} />
                  </span>
                </button>

                {filtered.map((e) => (
                  <button className="eqCard" key={e.id} onClick={() => onSelect(e)}>
                    <span className="eqIc">
                      <Icon name="wrench" size={20} />
                    </span>
                    <span style={{ minWidth: 0 }}>
                      <span className="eqName ltr">{e.name}</span>
                      <span className="eqMeta ltr">
                        {[e.manufacturer, e.model].filter(Boolean).join(" · ") || "—"}
                      </span>
                    </span>
                    <span className="chev">
                      <Icon name="chevR" size={18} />
                    </span>
                  </button>
                ))}

                {filtered.length === 0 && (
                  <div className="emptyHint">No equipment matches your search.</div>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
