import { useState } from "react";
import { getIdentity, clearIdentity, type DevIdentity } from "./auth";
import { DevLogin } from "./components/DevLogin";
import { EquipmentPicker } from "./components/EquipmentPicker";
import { ChatView } from "./components/ChatView";
import type { Equipment } from "./types";

export function App() {
  const [identity, setIdentityState] = useState<DevIdentity | null>(getIdentity());
  const [equipment, setEquipment] = useState<Equipment | null>(null);
  const [chosen, setChosen] = useState(false);

  if (!identity) {
    return <DevLogin onLogin={setIdentityState} />;
  }

  if (!chosen) {
    return (
      <div className="app">
        <button
          type="button"
          className="app__signout"
          onClick={() => {
            clearIdentity();
            setIdentityState(null);
          }}
        >
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
