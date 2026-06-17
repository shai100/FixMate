/**
 * The Documents admin screen — upload manuals and manage their versions (FR-8/9).
 *
 * Uploading a PDF queues it for background ingestion; the screen then polls the
 * task status (queued → processing → ingested/failed) so the technician sees live
 * progress and an explicit error if ingestion fails. The version history lists
 * every document; the one whose `superseded_by` is null is the current ("live")
 * revision and the rest are "superseded". Each row (`DocRow`) can be downloaded,
 * renamed, or deleted (delete removes it from retrieval at once). Data reloads via
 * a `revision` counter — bumped only once ingestion finishes, so the new manual
 * actually appears in the list.
 */
import { useEffect, useState, type FormEvent } from "react";
import { api, ApiError } from "../api";
import type { DocumentRow, Equipment } from "../types";

/** Poll interval (ms) and cap while waiting for background ingestion to finish. */
const POLL_INTERVAL_MS = 2000;
const POLL_MAX_ATTEMPTS = 150; // ~5 minutes; matches the 500-page <10min SLO.

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

/** Turn a raw Celery task state into a human progress message. */
function statusLabel(status: string): string {
  switch (status) {
    case "ingested":
      return "Ingestion complete — manual is now live.";
    case "started":
      return "Processing — extracting text, figures, and embeddings…";
    case "queued":
    case "pending":
      return "Queued for ingestion…";
    default:
      return `Processing (${status})…`;
  }
}

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
      // The upload itself is done the moment the API accepts it (202). Clear the
      // form and release the button straight away so the technician can queue the
      // next manual — ingestion then progresses in the background via polling,
      // which no longer blocks the form.
      setFile(null);
      setTitle("");
      setBusy(false);
      void pollIngestion(res.task_id);
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : "Upload failed");
      setStatus(null);
      setBusy(false);
    }
  }

  /**
   * Poll the ingestion task until it finishes, surfacing live progress.
   *
   * The document row is created by the background worker, not by the upload
   * request, so the list is only refreshed (via `revision`) once the task reports
   * "ingested" — otherwise the new manual would never appear. A "failure" state
   * shows an explicit error; if polling times out the manual may still finish
   * later, so we refresh anyway and tell the user to check back.
   */
  async function pollIngestion(taskId: string) {
    setStatus(statusLabel("queued"));
    for (let i = 0; i < POLL_MAX_ATTEMPTS; i++) {
      const s = await api.documentStatus(taskId);
      if (s.status === "ingested") {
        setStatus(statusLabel("ingested"));
        setRevision((r) => r + 1);
        return;
      }
      if (s.status === "failure") {
        setStatus(null);
        setError("Ingestion failed — the file could not be processed. Please try again.");
        return;
      }
      setStatus(statusLabel(s.status));
      await sleep(POLL_INTERVAL_MS);
    }
    setStatus("Still processing in the background — check back shortly.");
    setRevision((r) => r + 1);
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

      {status && (
        <p className="console-status" role="status" aria-live="polite">
          {status}
        </p>
      )}
      {error && (
        <p className="console-error" role="alert">
          {error}
        </p>
      )}

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

/** Format an ISO timestamp as a short localized date. */
function fmtDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

/** One document row with live/superseded badge and inline rename/delete. */
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

  async function download() {
    if (busy) return;
    setBusy(true);
    onError(null);
    try {
      // The download is auth-gated, so we can't use a plain <a href>; fetch the
      // PDF as a Blob and trigger a save via a temporary object URL.
      const blob = await api.downloadDocument(doc.id);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = doc.title.toLowerCase().endsWith(".pdf") ? doc.title : `${doc.title}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (e) {
      onError(e instanceof ApiError ? e.detail : "Could not download document");
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
            <button type="button" className="btn btn--ghost" disabled={busy} onClick={download}>
              Download
            </button>
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
