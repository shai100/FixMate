import { useState } from "react";
import { getIdentity, clearIdentity, type DevIdentity } from "./auth";
import { DevLogin } from "./components/DevLogin";
import { EquipmentPicker } from "./components/EquipmentPicker";
import { ChatView } from "./components/ChatView";
import { Console } from "./components/Console";
import type { Equipment } from "./types";

export function App() {
  const [identity, setIdentityState] = useState<DevIdentity | null>(getIdentity());
  const [equipment, setEquipment] = useState<Equipment | null>(null);
  const [chosen, setChosen] = useState(false);

  if (!identity) {
    return <DevLogin onLogin={setIdentityState} />;
  }

  function signOut() {
    clearIdentity();
    setIdentityState(null);
  }

  // Curators and admins land in the console (Phase 11); technicians get the
  // chat flow (Phase 10). Role comes from the authenticated identity (CLAUDE.md §6).
  if (identity.role === "curator" || identity.role === "admin") {
    return (
      <div className="app app--console">
        <button type="button" className="app__signout" onClick={signOut}>
          Sign out
        </button>
        <Console role={identity.role} />
      </div>
    );
  }

  if (!chosen) {
    return (
      <div className="app">
        <button type="button" className="app__signout" onClick={signOut}>
          Sign out
        </button>
        <EquipmentPicker
          onSelect={(e) => {
            setEquipment(e);
            setChosen(true);
          }}
        />
      </div>
    );
  }

  return (
    <div className="app">
      <button type="button" className="app__back" onClick={() => setChosen(false)}>
        ← Change equipment
      </button>
      <ChatView equipment={equipment} />
    </div>
  );
}
