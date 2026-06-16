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
          <li key={d.id}>
            <strong>{d.title}</strong>
            <span className="console-muted">v{d.version}</span>
            {live.has(d.id) ? (
              <span className="doc-badge doc-badge--live">live</span>
            ) : (
              <span className="doc-badge doc-badge--superseded">superseded</span>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
