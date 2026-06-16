/**
 * The card shown when the system declines to answer (FR-4).
 *
 * When confidence is too low or the answer couldn't be grounded, the backend
 * sets `escalated=true` and replaces the body with an honest "I don't know"
 * message. This card renders that plainly — it deliberately does NOT look like a
 * confident answer. It shows the nearest matching sections (so the technician has
 * a starting point) and an explicit "escalate to a senior technician" action.
 */
import type { Answer } from "../types";
import { Icon } from "./Icon";

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
