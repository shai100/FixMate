import { useEffect, useState } from "react";
import { api, ApiError } from "../api";
import type { Equipment } from "../types";

// Equipment profile selection (FR-10). A conversation is scoped to one piece of
// equipment so retrieval can filter by equipment_id.
export function EquipmentPicker({
  onSelect,
}: {
  onSelect: (equipment: Equipment | null) => void;
}) {
  const [equipment, setEquipment] = useState<Equipment[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .listEquipment()
      .then(setEquipment)
      .catch((e) =>
        setError(e instanceof ApiError ? e.detail : "Could not load equipment"),
      )
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p className="equipment-picker">Loading equipment…</p>;
  if (error) return <p className="equipment-picker equipment-picker__error">{error}</p>;

  return (
    <div className="equipment-picker">
      <h2>Select equipment</h2>
      <ul>
        <li>
          <button type="button" onClick={() => onSelect(null)}>
            General (no specific equipment)
          </button>
        </li>
        {equipment.map((e) => (
          <li key={e.id}>
            <button type="button" onClick={() => onSelect(e)}>
              {e.name}
              {e.manufacturer ? ` — ${e.manufacturer}` : ""}
              {e.model ? ` ${e.model}` : ""}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
