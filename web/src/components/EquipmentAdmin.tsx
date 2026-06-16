import { useEffect, useState, type FormEvent } from "react";
import { api, ApiError } from "../api";
import type { DocumentRow, Equipment } from "../types";

function fmtDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

// Full equipment management (FR-10): add, edit, view details and delete a
// profile, plus manage the manuals (files) attached to it. Deleting a profile
// cascades to its documents, chunks and fixes server-side.
export function EquipmentAdmin() {
  const [items, setItems] = useState<Equipment[] | null>(null);
  const [name, setName] = useState("");
  const [manufacturer, setManufacturer] = useState("");
  const [model, setModel] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [revision, setRevision] = useState(0);

  useEffect(() => {
    api
      .listEquipment()
      .then((eq) => {
        setItems(eq);
        setError(null);
      })
      .catch((e) => setError(e instanceof ApiError ? e.detail : "Could not load equipment"));
  }, [revision]);

  function reload() {
    setRevision((r) => r + 1);
  }

  async function create(e: FormEvent) {
    e.preventDefault();
    if (!name.trim() || busy) return;
    setBusy(true);
    setError(null);
    try {
      await api.createEquipment({
        name: name.trim(),
        manufacturer: manufacturer.trim() || null,
        model: model.trim() || null,
      });
      setName("");
      setManufacturer("");
      setModel("");
      reload();
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : "Could not create equipment");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="console-section" aria-label="Equipment admin">
      <h2>Equipment</h2>

      <form className="console-form" onSubmit={create}>
        <label htmlFor="eq-name">Name</label>
        <input id="eq-name" value={name} onChange={(e) => setName(e.target.value)} required />
        <label htmlFor="eq-mfr">Manufacturer</label>
        <input id="eq-mfr" value={manufacturer} onChange={(e) => setManufacturer(e.target.value)} />
        <label htmlFor="eq-model">Model</label>
        <input id="eq-model" value={model} onChange={(e) => setModel(e.target.value)} />
        <button type="submit" disabled={busy || !name.trim()}>
          Add equipment
        </button>
      </form>

      {error && <p className="console-error">{error}</p>}

      <ul className="console-list" data-testid="equipment-list">
        {items?.map((e) => (
          <EquipmentRow key={e.id} item={e} onChanged={reload} onError={setError} />
        ))}
      </ul>
      {items && items.length === 0 && <p className="console-empty">No equipment yet.</p>}
    </section>
  );
}

function EquipmentRow({
  item,
  onChanged,
  onError,
}: {
  item: Equipment;
  onChanged: () => void;
  onError: (msg: string | null) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [open, setOpen] = useState(false);
  const [name, setName] = useState(item.name);
  const [manufacturer, setManufacturer] = useState(item.manufacturer ?? "");
  const [model, setModel] = useState(item.model ?? "");
  const [busy, setBusy] = useState(false);

  async function save() {
    if (!name.trim() || busy) return;
    setBusy(true);
    onError(null);
    try {
      await api.updateEquipment(item.id, {
        name: name.trim(),
        manufacturer: manufacturer.trim() || null,
        model: model.trim() || null,
      });
      setEditing(false);
      onChanged();
    } catch (e) {
      onError(e instanceof ApiError ? e.detail : "Could not save equipment");
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (
      !confirm(
        `Delete "${item.name}"? Its manuals, indexed content and fixes are removed immediately.`,
      )
    )
      return;
    setBusy(true);
    onError(null);
    try {
      await api.deleteEquipment(item.id);
      onChanged();
    } catch (e) {
      onError(e instanceof ApiError ? e.detail : "Could not delete equipment");
    } finally {
      setBusy(false);
    }
  }

  if (editing) {
    return (
      <li className="eq-row">
        <div className="row-gap">
          <input value={name} onChange={(e) => setName(e.target.value)} aria-label="Name" />
          <input
            value={manufacturer}
            onChange={(e) => setManufacturer(e.target.value)}
            aria-label="Manufacturer"
            placeholder="Manufacturer"
          />
          <input
            value={model}
            onChange={(e) => setModel(e.target.value)}
            aria-label="Model"
            placeholder="Model"
          />
          <button type="button" className="btn" disabled={busy || !name.trim()} onClick={save}>
            Save
          </button>
          <button type="button" className="btn btn--ghost" disabled={busy} onClick={() => setEditing(false)}>
            Cancel
          </button>
        </div>
      </li>
    );
  }

  return (
    <li className="eq-row">
      <div className="eq-row__head">
        <strong>{item.name}</strong>
        <span className="console-muted">
          {[item.manufacturer, item.model].filter(Boolean).join(" · ") || "—"}
        </span>
        <span className="console-muted">{fmtDate(item.created_at)}</span>
        <span className="row-gap">
          <button type="button" className="btn btn--ghost" onClick={() => setOpen((o) => !o)}>
            {open ? "Hide files" : "Files"}
          </button>
          <button type="button" className="btn btn--ghost" disabled={busy} onClick={() => setEditing(true)}>
            Edit
          </button>
          <button type="button" className="btn btn--danger" disabled={busy} onClick={remove}>
            Delete
          </button>
        </span>
      </div>
      {open && <EquipmentFiles equipmentId={item.id} onError={onError} />}
    </li>
  );
}

// Manuals attached to one equipment profile: upload (add file) and delete
// (remove file), reusing the documents/ingestion pipeline.
function EquipmentFiles({
  equipmentId,
  onError,
}: {
  equipmentId: string;
  onError: (msg: string | null) => void;
}) {
  const [docs, setDocs] = useState<DocumentRow[] | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [status, setStatus] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [revision, setRevision] = useState(0);

  useEffect(() => {
    api
      .listDocuments(equipmentId)
      .then(setDocs)
      .catch((e) => onError(e instanceof ApiError ? e.detail : "Could not load files"));
  }, [equipmentId, revision, onError]);

  async function upload(e: FormEvent) {
    e.preventDefault();
    if (!file || busy) return;
    setBusy(true);
    onError(null);
    setStatus(null);
    try {
      const res = await api.uploadDocument(file, equipmentId, title.trim() || undefined);
      setStatus(`Queued for ingestion (task ${res.task_id}).`);
      setFile(null);
      setTitle("");
      setRevision((r) => r + 1);
    } catch (e) {
      onError(e instanceof ApiError ? e.detail : "Upload failed");
    } finally {
      setBusy(false);
    }
  }

  async function remove(doc: DocumentRow) {
    if (!confirm(`Delete "${doc.title}"?`)) return;
    setBusy(true);
    onError(null);
    try {
      await api.deleteDocument(doc.id);
      setRevision((r) => r + 1);
    } catch (e) {
      onError(e instanceof ApiError ? e.detail : "Could not delete file");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="eq-files" data-testid="equipment-files">
      <form className="console-form" onSubmit={upload}>
        <label htmlFor={`eqf-title-${equipmentId}`}>Title (optional)</label>
        <input
          id={`eqf-title-${equipmentId}`}
          value={title}
          onChange={(e) => setTitle(e.target.value)}
        />
        <label htmlFor={`eqf-file-${equipmentId}`}>PDF manual</label>
        <input
          id={`eqf-file-${equipmentId}`}
          type="file"
          accept="application/pdf"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
        />
        <button type="submit" disabled={busy || !file}>
          Add file
        </button>
      </form>

      {status && <p className="console-status">{status}</p>}

      <ul className="console-list">
        {docs?.map((d) => (
          <li key={d.id}>
            <strong>{d.title}</strong>
            <span className="console-muted">v{d.version}</span>
            <button type="button" className="btn btn--danger" disabled={busy} onClick={() => remove(d)}>
              Remove
            </button>
          </li>
        ))}
      </ul>
      {docs && docs.length === 0 && <p className="console-empty">No files attached.</p>}
    </div>
  );
}
