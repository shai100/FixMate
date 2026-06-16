/**
 * The visual shell for the technician app and its small chrome pieces.
 *
 * On a desktop browser the app is shown inside a mocked-up phone frame with an
 * explanatory side panel (the "stage"); on a real phone the frame collapses and
 * the app fills the screen — the actual PWA presentation. This file exports the
 * reusable layout/chrome bits used across technician screens: <PhoneShell> (the
 * frame), <TabBar> (bottom navigation), <Toast> (transient notifications), plus
 * the faux status bar.
 */
import { useEffect, useState, type ReactNode } from "react";
import { Icon, type IconName } from "./Icon";

/** Faux iOS-style status bar showing a live clock and signal/battery glyphs. */
function StatusBar() {
  const [time, setTime] = useState(formatNow);
  useEffect(() => {
    const id = setInterval(() => setTime(formatNow()), 15000);
    return () => clearInterval(id);
  }, []);
  return (
    <div className="statusbar">
      <span className="ltr">{time}</span>
      <span className="sbIcons" aria-hidden="true">
        <svg width="16" height="12" viewBox="0 0 18 12" fill="currentColor">
          <rect x="0" y="7" width="3" height="5" rx="1" />
          <rect x="5" y="5" width="3" height="7" rx="1" />
          <rect x="10" y="2.5" width="3" height="9.5" rx="1" />
          <rect x="15" y="0" width="3" height="12" rx="1" opacity=".35" />
        </svg>
        <svg width="22" height="11" viewBox="0 0 25 12">
          <rect x="0.5" y="0.5" width="21" height="11" rx="3" fill="none" stroke="currentColor" opacity=".4" />
          <rect x="2" y="2" width="15" height="8" rx="1.6" fill="currentColor" />
          <rect x="22.6" y="3.6" width="2" height="4.8" rx="1" fill="currentColor" opacity=".4" />
        </svg>
      </span>
    </div>
  );
}

/** Current time as a "H:MM" string for the status bar clock. */
function formatNow(): string {
  const d = new Date();
  return `${d.getHours()}:${String(d.getMinutes()).padStart(2, "0")}`;
}

const TIPS = [
  <>
    <b>Sign in</b> with the org/user IDs from <code>scripts/seed_demo.py</code>.
  </>,
  <>
    <b>Pick equipment</b> to scope retrieval to its manuals and approved fixes.
  </>,
  <>
    Ask about an <b>error code</b> — answers cite the manual sections they came from.
  </>,
  <>
    Answer didn't help? Tap <b>👎 No</b> to submit a field fix for curator review.
  </>,
];

/** Wraps the app in the desktop stage + phone frame; renders ``children`` as the
 *  phone's screen content. */
export function PhoneShell({ children }: { children: ReactNode }) {
  return (
    <div className="stage">
      <aside className="stageInfo">
        <div className="siLogo">
          <div className="siMark">
            <Icon name="wrench" size={24} />
          </div>
          <div>
            <h1>FixMate</h1>
            <div className="siSub">TECHNICIAN APP · NIGHT THEME</div>
          </div>
        </div>
        <p>
          AI troubleshooting copilot for field technicians — grounded in your
          team's service manuals and human-approved field fixes.
        </p>
        <div className="tips">
          {TIPS.map((tip, i) => (
            <div className="tip" key={i}>
              <span className="tipN">{i + 1}</span>
              <span>{tip}</span>
            </div>
          ))}
        </div>
        <div className="siFoot">GUI SPEC v1.0 · NIGHT THEME</div>
      </aside>

      <div className="phoneFrame">
        <div className="phoneScreen">
          <div className="island" />
          <StatusBar />
          {children}
        </div>
      </div>
    </div>
  );
}

/** One bottom-navigation tab: its id, icon, label, and optional numeric badge. */
export interface TabDef {
  id: string;
  icon: IconName;
  label: string;
  badge?: number;
}

/** Bottom navigation bar; highlights the ``active`` tab and calls ``onSelect``
 *  with the tapped tab's id. */
export function TabBar({
  tabs,
  active,
  onSelect,
}: {
  tabs: TabDef[];
  active: string;
  onSelect: (id: string) => void;
}) {
  return (
    <nav className="tabbar" aria-label="Main navigation">
      {tabs.map((tb) => (
        <button
          key={tb.id}
          type="button"
          className={`tab${active === tb.id ? " on" : ""}`}
          aria-current={active === tb.id ? "page" : undefined}
          onClick={() => onSelect(tb.id)}
        >
          <Icon name={tb.icon} size={20} />
          <span>{tb.label}</span>
          {tb.badge ? <span className="tabBdg">{tb.badge}</span> : null}
        </button>
      ))}
    </nav>
  );
}

/** A transient toast notification: the message and whether it's success or info. */
export interface ToastState {
  message: string;
  kind: "ok" | "info";
}

/** Renders the toast (slides in when ``toast`` is set, hidden when null). */
export function Toast({ toast }: { toast: ToastState | null }) {
  return (
    <div className="toastWrap">
      <div className={`toast${toast ? " show" : ""}`}>
        {toast && (
          <>
            <span className={toast.kind === "ok" ? "okIc" : "infoIc"}>
              <Icon name={toast.kind === "ok" ? "check" : "bulb"} size={15} />
            </span>
            <span>{toast.message}</span>
          </>
        )}
      </div>
    </div>
  );
}
