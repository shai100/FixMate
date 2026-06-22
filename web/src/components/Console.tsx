/**
 * The desktop curator/admin console — the shell for everything reviewers do.
 *
 * It's a tabbed layout: Review queue, All fixes, Documents, Equipment, and (for
 * admins only) Users. The tab list is filtered by role so curators never see the
 * admin-only Users tab — a defense-in-depth UI guard on top of the backend's own
 * role checks (FR-14). Each tab simply renders its corresponding admin component.
 */
import { useState } from "react";
import type { DevIdentity } from "../auth";
import { ReviewQueue } from "./ReviewQueue";
import { FixesAdmin } from "./FixesAdmin";
import { DocumentsAdmin } from "./DocumentsAdmin";
import { EquipmentAdmin } from "./EquipmentAdmin";
import { UsersAdmin } from "./UsersAdmin";
import { Icon } from "./Icon";

/** The console's tab identifiers. */
type Tab = "queue" | "fixes" | "documents" | "equipment" | "users";

/** One console tab; ``adminOnly`` tabs are hidden from curators. */
interface TabDef {
  id: Tab;
  label: string;
  adminOnly?: boolean;
}

const TABS: TabDef[] = [
  { id: "queue", label: "Review queue" },
  { id: "fixes", label: "All fixes" },
  { id: "documents", label: "Documents" },
  { id: "equipment", label: "Equipment" },
  { id: "users", label: "Users", adminOnly: true },
];

export function Console({
  role,
  onSignOut,
  onOpenTechView,
}: {
  role: DevIdentity["role"];
  onSignOut?: () => void;
  /** Opens the technician "tech screen" so the curator/admin can ask about their
   *  equipment and see how the system answers, then return to the console. */
  onOpenTechView?: () => void;
}) {
  const tabs = TABS.filter((t) => !t.adminOnly || role === "admin");
  const [tab, setTab] = useState<Tab>("queue");

  return (
    <div className="console">
      <header className="console-topbar">
        <div className="logoMark">
          <Icon name="wrench" size={22} />
        </div>
        <div>
          <div className="ctTitle">FixMate</div>
          <div className="ctSub">
            CURATION CONSOLE · {role.toUpperCase()} · <span className="ltr">v{__APP_VERSION__}</span>
          </div>
        </div>
        {onOpenTechView && (
          <button type="button" className="console-techview" onClick={onOpenTechView}>
            Open technician view
          </button>
        )}
        {onSignOut && (
          <button type="button" className="console-signout" onClick={onSignOut}>
            Sign out
          </button>
        )}
      </header>

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
        {tab === "fixes" && <FixesAdmin />}
        {tab === "documents" && <DocumentsAdmin />}
        {tab === "equipment" && <EquipmentAdmin />}
        {tab === "users" && role === "admin" && <UsersAdmin />}
      </main>
    </div>
  );
}
