import type { Answer } from "../types";
import { Icon } from "./Icon";

// Low-confidence path (FR-4): the composer replaces the answer body with a
// "don't know" response and sets escalated=true. We never dress this up as a
// confident answer — we show the nearest sections (citations) and an explicit
// escalate action.
export function EscalationCard({
  answer,
  onEscalate,
}: {
  answer: Answer;
  onEscalate?: () => void;
}) {
  return (
    <article className="escalation-card" role="alert" aria-label="Escalation">
      <h3 className="escalation-card__heading">
        <Icon name="alert" size={17} />
        Not confident enough to answer
      </h3>
      <p className="escalation-card__body">{answer.text}</p>

      {answer.citations.length > 0 && (
        <div className="escalation-card__nearest">
          <h4>Nearest sections</h4>
          <ul>
            {answer.citations.map((c) => (
              <li key={c.chunk_id} className="ltr">
                {(c.document_title ?? "Source") +
                  (c.page != null ? `, p.${c.page}` : "")}
              </li>
            ))}
          </ul>
        </div>
      )}

      <button type="button" className="escalation-card__action" onClick={onEscalate}>
        Escalate to a senior technician
      </button>
    </article>
  );
}
