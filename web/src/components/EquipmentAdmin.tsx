import { useEffect, useState, type FormEvent } from "react";
import { api, ApiError } from "../api";
import type { Equipment } from "../types";

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
      setRevision((r) => r + 1);
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

      <ul className="console-list">
        {items?.map((e) => (
          <li key={e.id}>
            <strong>{e.name}</strong>
            <span className="console-muted">
              {[e.manufacturer, e.model].filter(Boolean).join(" · ") || "—"}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}
