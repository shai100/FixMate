/**
 * The form a technician fills in to propose a fix (FR-12).
 *
 * Opened from the <FeedbackBar> when an answer didn't help. It collects the
 * fix text and optional photos; each selected photo is read into a base64 data
 * URL (via FileReader) so it can be sent as JSON to the feedback endpoint.
 * Submitting calls `onSubmit(text, photos)`; the parent handles the API call.
 */
import { useState } from "react";
import { Icon } from "./Icon";

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

  // Read each chosen image into a base64 data URL and append it to the photo list.
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
      className="fixWrap"
      style={{ padding: 0 }}
      onSubmit={(e) => {
        e.preventDefault();
        if (fixText.trim()) onSubmit(fixText.trim(), photos);
      }}
    >
      <div className="noticeWarn">
        <Icon name="bulb" size={16} />
        <span>Your fix helps the next technician — after a senior tech approves it.</span>
      </div>

      <div>
        <label className="fieldLbl" htmlFor="fix-text">
          What actually fixed it?
        </label>
        <textarea
          id="fix-text"
          className="inp"
          value={fixText}
          onChange={(e) => setFixText(e.target.value)}
          required
          placeholder="Describe the real cause and what you did. Include part numbers and timings where possible."
        />
      </div>

      <label className={`photoBtn${photos.length > 0 ? " has" : ""}`}>
        <Icon name="camera" size={17} />
        <span>
          {photos.length > 0
            ? `${photos.length} photo(s) attached`
            : "Add photos (optional)"}
        </span>
        <input type="file" accept="image/*" multiple onChange={(e) => handleFiles(e.target.files)} />
      </label>

      <div className="fbRow" style={{ border: "none", paddingTop: 0, gap: 8 }}>
        <button type="button" className="btn sec" onClick={onCancel} disabled={submitting}>
          Cancel
        </button>
        <button type="submit" className="btn okBtn" disabled={submitting || !fixText.trim()}>
          <Icon name="check" size={17} />
          {submitting ? "Submitting…" : "Submit fix for review"}
        </button>
      </div>
    </form>
  );
}
