import { useState } from "react";

// Candidate-fix submission (FR-12). Opened when the technician taps "No" in the
// FeedbackBar. Photos are read as base64 data URLs and passed through to the
// feedback endpoint (Phase 7 accepts photos[]).
export function FixSubmitForm({
  onSubmit,
  onCancel,
  submitting,
}: {
  onSubmit: (fixText: string, photos: string[]) => void;
  onCancel: () => void;
  submitting: boolean;
}) {
  const [fixText, setFixText] = useState("");
  const [photos, setPhotos] = useState<string[]>([]);

  async function handleFiles(files: FileList | null) {
    if (!files) return;
    const encoded = await Promise.all(
      Array.from(files).map(
        (file) =>
          new Promise<string>((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => resolve(reader.result as string);
            reader.onerror = () => reject(reader.error);
            reader.readAsDataURL(file);
          }),
      ),
    );
    setPhotos((prev) => [...prev, ...encoded]);
  }

  return (
    <form
      className="fix-form"
      onSubmit={(e) => {
        e.preventDefault();
        if (fixText.trim()) onSubmit(fixText.trim(), photos);
      }}
    >
      <label htmlFor="fix-text">What actually fixed it?</label>
      <textarea
        id="fix-text"
        value={fixText}
        onChange={(e) => setFixText(e.target.value)}
        rows={4}
        required
        placeholder="Describe the steps that resolved the issue…"
      />

      <label htmlFor="fix-photos">Add photos (optional)</label>
      <input
        id="fix-photos"
        type="file"
        accept="image/*"
        multiple
        onChange={(e) => handleFiles(e.target.files)}
      />
      {photos.length > 0 && (
        <p className="fix-form__count">{photos.length} photo(s) attached</p>
      )}

      <div className="fix-form__actions">
        <button type="button" onClick={onCancel} disabled={submitting}>
          Cancel
        </button>
        <button type="submit" disabled={submitting || !fixText.trim()}>
          {submitting ? "Submitting…" : "Submit fix for review"}
        </button>
      </div>
    </form>
  );
}
