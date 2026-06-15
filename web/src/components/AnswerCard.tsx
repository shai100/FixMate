import type { Answer, Citation, Confidence } from "../types";

// Lines the answer prompt (Phase 5.4) emits as safety warnings. We surface them
// ABOVE everything else regardless of where they appear in the body — the spec
// pitfall table requires warnings-first presentation.
const SAFETY_PREFIX = /^\s*(?:⚠️?|warning|danger|caution|safety)\b[:\s-]*/i;

const CONFIDENCE_LABEL: Record<Confidence, string> = {
  high: "High confidence",
  medium: "Medium confidence",
  low: "Low confidence",
};

interface ParsedBody {
  warnings: string[];
  rest: string[];
}

function parseBody(text: string): ParsedBody {
  const warnings: string[] = [];
  const rest: string[] = [];
  for (const rawLine of text.split("\n")) {
    const line = rawLine.trimEnd();
    if (SAFETY_PREFIX.test(line)) {
      warnings.push(line.replace(SAFETY_PREFIX, "").trim());
    } else if (line.length > 0) {
      rest.push(line);
    }
  }
  return { warnings, rest };
}

function CitationLink({ citation }: { citation: Citation }) {
  const label =
    (citation.document_title ?? "Source") +
    (citation.page != null ? `, p.${citation.page}` : "");
  return (
    <li className="citation">
      <span
        className={`citation-badge citation-badge--${citation.source_type}`}
        data-testid={`citation-source-${citation.source_type}`}
      >
        {citation.source_type === "field_fix" ? "Field fix" : "Manual"}
      </span>
      <span className="citation-label">{label}</span>
    </li>
  );
}

export function AnswerCard({
  answer,
  children,
}: {
  answer: Answer;
  children?: React.ReactNode;
}) {
  const { warnings, rest } = parseBody(answer.text);
  const hasFieldFix = answer.citations.some(
    (c) => c.source_type === "field_fix",
  );

  return (
    <article className="answer-card" aria-label="Answer">
      {warnings.length > 0 && (
        <section className="safety-warnings" role="alert" aria-label="Safety warnings">
          <h3 className="safety-warnings__heading">⚠️ Safety</h3>
          <ul>
            {warnings.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        </section>
      )}

      <div className="answer-card__meta">
        <span
          className={`confidence-chip confidence-chip--${answer.confidence}`}
          data-testid="confidence-chip"
        >
          {CONFIDENCE_LABEL[answer.confidence]}
        </span>
        {hasFieldFix && (
          <span className="fieldfix-badge" data-testid="fieldfix-badge">
            ✓ Includes field-verified fix
          </span>
        )}
      </div>

      <div className="answer-card__body">
        {rest.map((line, i) => (
          <p key={i}>{line}</p>
        ))}
      </div>

      {answer.figures.length > 0 && (
        <div className="answer-card__figures">
          {answer.figures.map((fig, i) => (
            <figure key={i}>
              <img src={fig.url} alt={fig.caption ?? `Figure on page ${fig.page}`} />
              {fig.caption && <figcaption>{fig.caption}</figcaption>}
            </figure>
          ))}
        </div>
      )}

      {answer.citations.length > 0 && (
        <footer className="answer-card__citations">
          <h4>Sources</h4>
          <ul>
            {answer.citations.map((c) => (
              <CitationLink key={c.chunk_id} citation={c} />
            ))}
          </ul>
        </footer>
      )}

      {children}
    </article>
  );
}
