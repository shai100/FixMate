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
    return (
      <div className="console-stage">
        <Console role={identity.role} onSignOut={signOut} />
      </div>
    );
  }

  return <TechnicianApp identity={identity} onSignOut={signOut} />;
}

function TechnicianApp({
  identity,
  onSignOut,
}: {
  identity: DevIdentity;
  onSignOut: () => void;
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
            />
          )}
        </div>
        {tabbed && <TabBar tabs={TABS} active={screen} onSelect={goTab} />}
      </div>
    </PhoneShell>
  );
}
