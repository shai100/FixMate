import { useEffect, useState, type FormEvent } from "react";
import { api, ApiError } from "../api";
import type { DocumentRow, Equipment } from "../types";

// Upload a manual, watch its ingestion status, and see the version history
// (FR-8/FR-9). A document whose superseded_by is null is the live revision.
export function DocumentsAdmin() {
  const [equipment, setEquipment] = useState<Equipment[]>([]);
  const [docs, setDocs] = useState<DocumentRow[] | null>(null);
  const [equipmentId, setEquipmentId] = useState("");
  const [title, setTitle] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [revision, setRevision] = useState(0);

  useEffect(() => {
    api
      .listEquipment()
      .then(setEquipment)
      .catch(() => undefined);
    api
      .listDocuments()
      .then(setDocs)
      .catch((e) => setError(e instanceof ApiError ? e.detail : "Could not load documents"));
  }, [revision]);

  async function upload(e: FormEvent) {
    e.preventDefault();
    if (!file || !equipmentId || busy) return;
    setBusy(true);
    setError(null);
    setStatus(null);
    try {
      const res = await api.uploadDocument(file, equipmentId, title.trim() || undefined);
      setStatus(`Queued for ingestion (task ${res.task_id}).`);
      setFile(null);
      setTitle("");
      setRevision((r) => r + 1);
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : "Upload failed");
    } finally {
      setBusy(false);
    }
  }

  const live = new Set(docs?.filter((d) => d.superseded_by === null).map((d) => d.id));
  const equipmentName = new Map(equipment.map((e) => [e.id, e.name]));

  return (
    <section className="console-section" aria-label="Documents admin">
      <h2>Documents</h2>

      <form className="console-form" onSubmit={upload}>
        <label htmlFor="doc-eq">Equipment</label>
        <select id="doc-eq" value={equipmentId} onChange={(e) => setEquipmentId(e.target.value)}>
          <option value="">Select equipment…</option>
          {equipment.map((e) => (
            <option key={e.id} value={e.id}>
              {e.name}
            </option>
          ))}
        </select>
        <label htmlFor="doc-title">Title (optional)</label>
        <input id="doc-title" value={title} onChange={(e) => setTitle(e.target.value)} />
        <label htmlFor="doc-file">PDF manual</label>
        <input
          id="doc-file"
          type="file"
          accept="application/pdf"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
        />
        <button type="submit" disabled={busy || !file || !equipmentId}>
          Upload &amp; ingest
        </button>
      </form>

      {status && <p className="console-status">{status}</p>}
      {error && <p className="console-error">{error}</p>}

      <h3>Version history</h3>
      <ul className="console-list" data-testid="doc-list">
        {docs?.map((d) => (
          <DocRow
            key={d.id}
            doc={d}
            equipmentName={equipmentName.get(d.equipment_id) ?? "—"}
            live={live.has(d.id)}
            onChanged={() => setRevision((r) => r + 1)}
            onError={setError}
          />
        ))}
      </ul>
      {docs && docs.length === 0 && <p className="console-empty">No documents yet.</p>}
    </section>
  );
}

function fmtDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

function DocRow({
  doc,
  equipmentName,
  live,
  onChanged,
  onError,
}: {
  doc: DocumentRow;
  equipmentName: string;
  live: boolean;
  onChanged: () => void;
  onError: (msg: string | null) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [title, setTitle] = useState(doc.title);
  const [busy, setBusy] = useState(false);

  async function save() {
    if (!title.trim() || busy) return;
    setBusy(true);
    onError(null);
    try {
      await api.updateDocument(doc.id, { title: title.trim() });
      setEditing(false);
      onChanged();
    } catch (e) {
      onError(e instanceof ApiError ? e.detail : "Could not rename document");
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (!confirm(`Delete "${doc.title}"? It is removed from retrieval immediately.`)) return;
    setBusy(true);
    onError(null);
    try {
      await api.deleteDocument(doc.id);
      onChanged();
    } catch (e) {
      onError(e instanceof ApiError ? e.detail : "Could not delete document");
    } finally {
      setBusy(false);
    }
  }

  return (
    <li className="doc-row">
      {editing ? (
        <div className="row-gap">
          <input value={title} onChange={(e) => setTitle(e.target.value)} aria-label="Document title" />
          <button type="button" className="btn" disabled={busy || !title.trim()} onClick={save}>
            Save
          </button>
          <button type="button" className="btn btn--ghost" disabled={busy} onClick={() => setEditing(false)}>
            Cancel
          </button>
        </div>
      ) : (
        <>
          <strong>{doc.title}</strong>
          <span className="console-muted">v{doc.version}</span>
          {live ? (
            <span className="doc-badge doc-badge--live">live</span>
          ) : (
            <span className="doc-badge doc-badge--superseded">superseded</span>
          )}
          <span className="console-muted">{equipmentName}</span>
          <span className="console-muted">{fmtDate(doc.created_at)}</span>
          <span className="row-gap">
            <button type="button" className="btn btn--ghost" disabled={busy} onClick={() => setEditing(true)}>
              Rename
            </button>
            <button type="button" className="btn btn--danger" disabled={busy} onClick={remove}>
              Delete
            </button>
          </span>
        </>
      )}
    </li>
  );
}
