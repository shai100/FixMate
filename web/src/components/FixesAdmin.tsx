import { useEffect, useState } from "react";
import { api, ApiError } from "../api";
import type { Equipment, FixSummary } from "../types";

function fmtDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

// All-fixes admin (FR-15/16): the full fix catalogue across every lifecycle
// state with date, creator and approval status. Curators/admins can open a new
// issue, edit text, or delete. Approve/reject still flow through the review queue
// (which carries the AI pre-screen); this is the management/audit table.
export function FixesAdmin() {
  const [fixes, setFixes] = useState<FixSummary[] | null>(null);
  const [equipment, setEquipment] = useState<Equipment[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [revision, setRevision] = useState(0);
  const [adding, setAdding] = useState(false);

  useEffect(() => {
    Promise.all([api.listFixes(), api.listEquipment()])
      .then(([f, e]) => {
        setFixes(f);
        setEquipment(e);
        setError(null);
      })
      .catch((e) => setError(e instanceof ApiError ? e.detail : "Could not load fixes"));
  }, [revision]);

  function reload() {
    setRevision((r) => r + 1);
  }

  return (
    <section className="console-section" aria-label="Fixes admin">
      <header className="review-queue__header">
        <h2>All fixes <span className="review-queue__badge">{fixes?.length ?? 0}</span></h2>
        <div className="row-gap">
          <button type="button" className="btn btn--ghost" onClick={reload}>
            Refresh
          </button>
          <button type="button" className="btn" onClick={() => setAdding(true)}>
            New issue
          </button>
        </div>
      </header>

      {error && <p className="console-error">{error}</p>}

      {adding && (
        <NewFixForm
          equipment={equipment}
          onCancel={() => setAdding(false)}
          onCreated={() => {
            setAdding(false);
            reload();
          }}
          onError={setError}
        />
      )}

      <table className="fixes-table" data-testid="fixes-table">
        <thead>
          <tr>
            <th>Question / Issue</th>
            <th>State</th>
            <th>Creator</th>
            <th>Created</th>
            <th>Approved</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {fixes?.map((f) => (
            <FixRow key={f.fix_id} fix={f} onChanged={reload} onError={setError} />
          ))}
        </tbody>
      </table>
      {fixes && fixes.length === 0 && <p className="console-empty">No fixes yet.</p>}
    </section>
  );
}

function FixRow({
  fix,
  onChanged,
  onError,
}: {
  fix: FixSummary;
  onChanged: () => void;
  onError: (msg: string) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [question, setQuestion] = useState(fix.question ?? "");
  const [text, setText] = useState(fix.proposed_text);
  const [busy, setBusy] = useState(false);

  function fail(e: unknown, fallback: string) {
    onError(e instanceof ApiError ? e.detail : fallback);
  }

  async function save() {
    setBusy(true);
    try {
      await api.updateFix(fix.fix_id, { proposed_text: text, question: question || null });
      setEditing(false);
      onChanged();
    } catch (e) {
      fail(e, "Could not save fix");
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (!confirm("Delete this fix? It will be removed from retrieval immediately.")) return;
    setBusy(true);
    try {
      await api.deleteFix(fix.fix_id);
      onChanged();
    } catch (e) {
      fail(e, "Could not delete fix");
    } finally {
      setBusy(false);
    }
  }

  if (editing) {
    return (
      <tr className="fixes-row--editing">
        <td colSpan={6}>
          <label className="fieldLbl">Question</label>
          <input className="inp" value={question} onChange={(e) => setQuestion(e.target.value)} />
          <label className="fieldLbl">Proposed fix</label>
          <textarea className="inp" rows={3} value={text} onChange={(e) => setText(e.target.value)} />
          <div className="row-gap">
            <button type="button" className="btn" disabled={busy || !text.trim()} onClick={save}>
              Save
            </button>
            <button type="button" className="btn btn--ghost" disabled={busy} onClick={() => setEditing(false)}>
              Cancel
            </button>
          </div>
        </td>
      </tr>
    );
  }

  return (
    <tr>
      <td>{fix.question ?? <span className="console-muted">{fix.proposed_text.slice(0, 60)}…</span>}</td>
      <td>
        <span className={`state-chip state-chip--${fix.state}`}>{fix.state}</span>
      </td>
      <td>{fix.submitted_by_name ?? "—"}</td>
      <td>{fmtDate(fix.created_at)}</td>
      <td>{fix.approved_at ? fmtDate(fix.approved_at) : "—"}</td>
      <td className="row-gap">
        <button type="button" className="btn btn--ghost" disabled={busy} onClick={() => setEditing(true)}>
          Edit
        </button>
        <button type="button" className="btn btn--danger" disabled={busy} onClick={remove}>
          Delete
        </button>
      </td>
    </tr>
  );
}

function NewFixForm({
  equipment,
  onCancel,
  onCreated,
  onError,
}: {
  equipment: Equipment[];
  onCancel: () => void;
  onCreated: () => void;
  onError: (msg: string) => void;
}) {
  // The form only mounts after equipment has loaded (it opens on a button
  // click), so the first profile is a safe initial selection.
  const [equipmentId, setEquipmentId] = useState(equipment[0]?.id ?? "");
  const [question, setQuestion] = useState("");
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!equipmentId || !text.trim()) return;
    setBusy(true);
    try {
      await api.createFix({
        equipment_id: equipmentId,
        proposed_text: text.trim(),
        question: question || null,
      });
      onCreated();
    } catch (err) {
      onError(err instanceof ApiError ? err.detail : "Could not create fix");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="fix-create" onSubmit={submit} aria-label="New issue">
      <label className="fieldLbl">Equipment</label>
      <select className="inp" value={equipmentId} onChange={(e) => setEquipmentId(e.target.value)} required>
        {equipment.map((eq) => (
          <option key={eq.id} value={eq.id}>
            {eq.name}
          </option>
        ))}
      </select>
      <label className="fieldLbl">Question / symptom</label>
      <input className="inp" value={question} onChange={(e) => setQuestion(e.target.value)} />
      <label className="fieldLbl">Proposed fix</label>
      <textarea className="inp" rows={3} value={text} onChange={(e) => setText(e.target.value)} required />
      <div className="row-gap">
        <button type="submit" className="btn" disabled={busy || !equipmentId || !text.trim()}>
          {busy ? "Adding…" : "Add to review queue"}
        </button>
        <button type="button" className="btn btn--ghost" disabled={busy} onClick={onCancel}>
          Cancel
        </button>
      </div>
    </form>
  );
}
