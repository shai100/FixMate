import { useState } from "react";
import type { DevIdentity } from "../auth";
import { ReviewQueue } from "./ReviewQueue";
import { DocumentsAdmin } from "./DocumentsAdmin";
import { EquipmentAdmin } from "./EquipmentAdmin";
import { UsersAdmin } from "./UsersAdmin";

type Tab = "queue" | "documents" | "equipment" | "users";

interface TabDef {
  id: Tab;
  label: string;
  adminOnly?: boolean;
}

const TABS: TabDef[] = [
  { id: "queue", label: "Review queue" },
  { id: "documents", label: "Documents" },
  { id: "equipment", label: "Equipment" },
  { id: "users", label: "Users", adminOnly: true },
];

// Curator/Admin console (Phase 11). Route guard by role: curators reach the
// review queue + content admin; only admins see user/role management (FR-14).
export function Console({ role }: { role: DevIdentity["role"] }) {
  const tabs = TABS.filter((t) => !t.adminOnly || role === "admin");
  const [tab, setTab] = useState<Tab>("queue");

  return (
    <div className="console">
      <nav className="console-nav" aria-label="Console sections">
        {tabs.map((t) => (
          <button
            key={t.id}
            type="button"
            className={tab === t.id ? "console-tab console-tab--active" : "console-tab"}
            aria-current={tab === t.id ? "page" : undefined}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </nav>

      <main className="console-body">
        {tab === "queue" && <ReviewQueue />}
        {tab === "documents" && <DocumentsAdmin />}
        {tab === "equipment" && <EquipmentAdmin />}
        {tab === "users" && role === "admin" && <UsersAdmin />}
      </main>
    </div>
  );
}
