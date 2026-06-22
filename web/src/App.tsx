/**
 * Root component and top-level router.
 *
 * <App> decides what the whole screen shows based on who is signed in:
 *   - nobody signed in        -> the dev login screen
 *   - a curator or admin      -> the desktop curator/admin <Console>, which can
 *                                open the technician app to try the live system
 *   - a technician            -> the phone-framed <TechnicianApp>
 *
 * Every user type can reach the <TechnicianApp> ("tech screen") so curators and
 * admins can ask about their equipment and see exactly what their technicians
 * experience — useful for sanity-checking retrieval and how the system answers.
 * Technicians live there permanently; curators/admins toggle into it from the
 * console and back.
 *
 * <TechnicianApp> is the field-technician experience: a tabbed shell (Equipment,
 * Packs, Profile, plus a Settings screen and a Chat screen reached by selecting
 * equipment). It owns the small amount of cross-screen state — the loaded
 * equipment list, the chosen equipment, and which screen is visible — and passes
 * it down to each screen component. The role always comes from the authenticated
 * identity, never user input (CLAUDE.md §6).
 *
 * This app deliberately routes by state rather than a URL router; it's a small,
 * mostly-linear flow, so a `screen` string in state is simpler than routes.
 */
import { useEffect, useState } from "react";
import { getIdentity, clearIdentity, type DevIdentity } from "./auth";
import { api, ApiError } from "./api";
import type { Equipment } from "./types";
import { DevLogin } from "./components/DevLogin";
import { EquipmentPicker } from "./components/EquipmentPicker";
import { ChatView } from "./components/ChatView";
import { Console } from "./components/Console";
import { PhoneShell, TabBar, type TabDef } from "./components/Shell";
import { PacksScreen } from "./components/screens/PacksScreen";
import { ProfileScreen } from "./components/screens/ProfileScreen";
import { SettingsScreen } from "./components/screens/SettingsScreen";

type Screen = "equipment" | "chat" | "packs" | "profile" | "settings";

const TABS: TabDef[] = [
  { id: "equipment", icon: "grid", label: "Equipment" },
  { id: "packs", icon: "pack", label: "Packs" },
  { id: "profile", icon: "user", label: "Profile" },
];
const TAB_IDS = new Set<Screen>(["equipment", "packs", "profile"]);

/** Top-level router: chooses login / console / technician app by identity + role. */
export function App() {
  const [identity, setIdentityState] = useState<DevIdentity | null>(getIdentity());

  if (!identity) {
    return (
      <PhoneShell>
        <div className="app">
          <div className="screens">
            <DevLogin onLogin={setIdentityState} />
          </div>
        </div>
      </PhoneShell>
    );
  }

  function signOut() {
    clearIdentity();
    setIdentityState(null);
  }

  // Curators and admins land in the desktop console (Phase 11); technicians get
  // the phone-framed chat flow (Phase 10). Role comes from the authenticated
  // identity (CLAUDE.md §6).
  if (identity.role === "curator" || identity.role === "admin") {
    return <ConsoleApp identity={identity} onSignOut={signOut} />;
  }

  return <TechnicianApp identity={identity} onSignOut={signOut} />;
}

/** The curator/admin experience: the desktop console, with the ability to open
 *  the technician "tech screen" to try the live system as a technician would and
 *  return to the console afterward. */
function ConsoleApp({
  identity,
  onSignOut,
}: {
  identity: DevIdentity;
  onSignOut: () => void;
}) {
  const [view, setView] = useState<"console" | "tech">("console");

  if (view === "tech") {
    return (
      <TechnicianApp
        identity={identity}
        onSignOut={onSignOut}
        onBackToConsole={() => setView("console")}
      />
    );
  }

  return (
    <div className="console-stage">
      <Console
        role={identity.role}
        onSignOut={onSignOut}
        onOpenTechView={() => setView("tech")}
      />
    </div>
  );
}

/** The field-technician experience: a phone-framed, tabbed shell that loads the
 *  equipment list and switches between the equipment/chat/packs/profile/settings
 *  screens. */
function TechnicianApp({
  identity,
  onSignOut,
  onBackToConsole,
}: {
  identity: DevIdentity;
  onSignOut: () => void;
  /** When present (curator/admin trying the tech screen), Settings shows a
   *  "Back to console" action that returns to the curation console. */
  onBackToConsole?: () => void;
}) {
  const [screen, setScreen] = useState<Screen>("equipment");
  const [lastTab, setLastTab] = useState<Screen>("equipment");
  const [equipment, setEquipment] = useState<Equipment[]>([]);
  const [chosen, setChosen] = useState<Equipment | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .listEquipment()
      .then(setEquipment)
      .catch((e) => setError(e instanceof ApiError ? e.detail : "Could not load equipment"))
      .finally(() => setLoading(false));
  }, []);

  function goTab(id: string) {
    setScreen(id as Screen);
    setLastTab(id as Screen);
  }
  function openSettings() {
    setScreen("settings");
  }

  const tabbed = TAB_IDS.has(screen);

  return (
    <PhoneShell>
      <div className="app">
        <div className="screens">
          {screen === "equipment" && (
            <EquipmentPicker
              key="equipment"
              equipment={equipment}
              loading={loading}
              error={error}
              onOpenSettings={openSettings}
              onSelect={(e) => {
                setChosen(e);
                setScreen("chat");
              }}
            />
          )}
          {screen === "chat" && (
            <ChatView key="chat" equipment={chosen} onBack={() => setScreen("equipment")} />
          )}
          {screen === "packs" && (
            <PacksScreen key="packs" equipment={equipment} onOpenSettings={openSettings} />
          )}
          {screen === "profile" && (
            <ProfileScreen key="profile" identity={identity} onOpenSettings={openSettings} />
          )}
          {screen === "settings" && (
            <SettingsScreen
              key="settings"
              identity={identity}
              onBack={() => setScreen(lastTab)}
              onSignOut={onSignOut}
              onBackToConsole={onBackToConsole}
            />
          )}
        </div>
        {tabbed && <TabBar tabs={TABS} active={screen} onSelect={goTab} />}
      </div>
    </PhoneShell>
  );
}
