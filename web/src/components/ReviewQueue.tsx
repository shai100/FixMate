import { useEffect, useState } from "react";
import { api, ApiError } from "../api";
import type { ReviewItem } from "../types";
import { ReviewDetail } from "./ReviewDetail";

// The curation queue is the moat (CLAUDE.md §2.4/§2.5). It lists every fix
// awaiting human review with a badge count, and opens a side-by-side detail
// view where a curator approves, edits, rejects, or flags it unsafe (FR-14/15/16).
export function ReviewQueue() {
  const [items, setItems] = useState<ReviewItem[] | null>(null);
  const [selected, setSelected] = useState<ReviewItem | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Incrementing this triggers a reload without calling setState synchronously
  // inside an effect body (react-hooks/set-state-in-effect).
  const [revision, setRevision] = useState(0);

  useEffect(() => {
    api
      .reviewQueue()
      .then((q) => {
        setItems(q);
        setError(null);
      })
      .catch((e) =>
        setError(e instanceof ApiError ? e.detail : "Could not load the review queue"),
      );
  }, [revision]);

  function onResolved() {
    setSelected(null);
    setRevision((r) => r + 1);
  }

  if (selected) {
    return <ReviewDetail item={selected} onResolved={onResolved} onBack={() => setSelected(null)} />;
  }

  return (
    <section className="review-queue" aria-label="Review queue">
      <header className="review-queue__header">
        <h2>
          Review queue{" "}
          <span className="review-queue__badge" data-testid="queue-badge">
            {items?.length ?? 0}
          </span>
        </h2>
        <button type="button" onClick={() => setRevision((r) => r + 1)}>
          Refresh
        </button>
      </header>

      {error && <p className="console-error">{error}</p>}

      {items && items.length === 0 && <p className="console-empty">Nothing awaiting review. 🎉</p>}

      <ul className="review-queue__list">
        {items?.map((item) => (
          <li key={item.fix_id}>
            <button
              type="button"
              className="review-queue__item"
              onClick={() => setSelected(item)}
            >
              <span className="review-queue__question">
                {item.question ?? "(no question recorded)"}
              </span>
              {item.prescreen?.overall_risk && (
                <span
                  className={`risk-chip risk-chip--${item.prescreen.overall_risk}`}
                  data-testid={`risk-${item.fix_id}`}
                >
                  {item.prescreen.overall_risk} risk
                </span>
              )}
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
