import { useState } from "react";
import { api, ApiError } from "../api";
import type { ReviewItem } from "../types";

type Action = "approve" | "reject" | "unsafe";

// Side-by-side curation view (FR-15/16): the question, the answer the technician
// got, the proposed fix (editable for Edit & Approve), the supporting manual
// excerpts, and the AI pre-screen advisory. The pre-screen advises; the human
// decides — it never blocks or auto-resolves (CLAUDE.md §2.5).
export function ReviewDetail({
  item,
  onResolved,
  onBack,
}: {
  item: ReviewItem;
  onResolved: () => void;
  onBack: () => void;
}) {
  const [editedText, setEditedText] = useState(item.proposed_text);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState<Action | null>(null);
  const [error, setError] = useState<string | null>(null);

  const edited = editedText.trim() !== item.proposed_text.trim();
  const prescreen = item.prescreen;

  async function run(action: Action) {
    if (busy) return;
    if ((action === "reject" || action === "unsafe") && !reason.trim()) {
      setError("A reason is required so the submitter sees why.");
      return;
    }
    setError(null);
    setBusy(action);
    try {
      if (action === "approve") {
        await api.approveFix(item.fix_id, edited ? editedText.trim() : undefined);
      } else if (action === "reject") {
        await api.rejectFix(item.fix_id, reason.trim());
      } else {
        await api.flagUnsafe(item.fix_id, reason.trim());
      }
      onResolved();
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : "Action failed");
      setBusy(null);
    }
  }

  return (
    <section className="review-detail" aria-label="Review fix">
      <button type="button" className="console-back" onClick={onBack}>
        ← Back to queue
      </button>

      <div className="review-detail__grid">
        <div className="review-panel">
          <h3>Question</h3>
          <p>{item.question ?? "(no question recorded)"}</p>

          <h3>Answer given</h3>
          <p className="review-panel__answer">{item.original_answer ?? "(no answer recorded)"}</p>

          <h3>Manual excerpts</h3>
          {item.manual_chunks.length === 0 ? (
            <p className="console-empty">No supporting manual content found.</p>
          ) : (
            <ul className="review-panel__chunks">
              {item.manual_chunks.map((c) => (
                <li key={c.chunk_id}>
                  {c.page != null && <span className="chunk-page">p.{c.page}</span>}
                  <span>{c.text}</span>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="review-panel">
          <h3>
            Proposed fix{" "}
            {edited && (
              <span className="edited-flag" data-testid="edited-flag">
                edited
              </span>
            )}
          </h3>
          <label htmlFor="proposed" className="visually-hidden">
            Proposed fix text
          </label>
          <textarea
            id="proposed"
            rows={6}
            value={editedText}
            onChange={(e) => setEditedText(e.target.value)}
          />

          <h3>AI pre-screen advisory</h3>
          <div className="prescreen" data-testid="prescreen">
            {!prescreen ? (
              <p className="console-empty">No pre-screen available.</p>
            ) : prescreen.error ? (
              <p className="prescreen__error">
                Pre-screen could not run — review manually. (advisory only)
              </p>
            ) : (
              <>
                {prescreen.overall_risk && (
                  <p
                    className={`risk-chip risk-chip--${prescreen.overall_risk}`}
                    data-testid="prescreen-risk"
                  >
                    Overall risk: {prescreen.overall_risk}
                  </p>
                )}
                <PrescreenList label="Hazard flags" values={prescreen.hazard_flags} />
                <PrescreenList label="Contradictions" values={prescreen.contradictions} />
                <PrescreenList
                  label="Missing safety steps"
                  values={prescreen.missing_safety_steps}
                />
              </>
            )}
            <p className="prescreen__note">
              Advisory only — a human decides. Pre-screen never approves or rejects.
            </p>
          </div>

          <label htmlFor="reason">Reason (required to reject / flag unsafe)</label>
          <textarea
            id="reason"
            rows={2}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          />

          {error && <p className="console-error">{error}</p>}

          <div className="review-detail__actions">
            <button type="button" disabled={busy !== null} onClick={() => run("approve")}>
              {edited ? "Edit & Approve" : "Approve"}
            </button>
            <button
              type="button"
              className="btn-reject"
              disabled={busy !== null}
              onClick={() => run("reject")}
            >
              Reject
            </button>
            <button
              type="button"
              className="btn-unsafe"
              disabled={busy !== null}
              onClick={() => run("unsafe")}
            >
              Flag Unsafe
            </button>
          </div>
        </div>
      </div>
    </section>
  );
}

function PrescreenList({ label, values }: { label: string; values?: string[] }) {
  if (!values || values.length === 0) return null;
  return (
    <div className="prescreen__group">
      <strong>{label}:</strong>
      <ul>
        {values.map((v, i) => (
          <li key={i}>{v}</li>
        ))}
      </ul>
    </div>
  );
}
