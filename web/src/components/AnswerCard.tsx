import type { Answer, Citation, Confidence } from "../types";
import { Icon, type IconName } from "./Icon";

// Lines the answer prompt (Phase 5.4) emits as safety warnings. We surface them
// ABOVE everything else regardless of where they appear in the body — the spec
// pitfall table requires warnings-first presentation.
const SAFETY_PREFIX = /^\s*(?:⚠️?|warning|danger|caution|safety)\b[:\s-]*/i;

const CONFIDENCE: Record<Confidence, { label: string; icon: IconName }> = {
  high: { label: "High confidence", icon: "check" },
  medium: { label: "Medium confidence", icon: "halfdot" },
  low: { label: "Low confidence", icon: "alert" },
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
  const isFieldFix = citation.source_type === "field_fix";
  return (
    <li className="citation">
      <span
        className={`citation-badge citation-badge--${citation.source_type}`}
        data-testid={`citation-source-${citation.source_type}`}
      >
        <Icon name={isFieldFix ? "bulb" : "book"} size={11} />
        {isFieldFix ? "Field fix" : "Manual"}
      </span>
      <span className="citation-label ltr">{label}</span>
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
  const hasFieldFix = answer.citations.some((c) => c.source_type === "field_fix");
  const conf = CONFIDENCE[answer.confidence];

  return (
    <article className="aCard" aria-label="Answer">
      <div className="answer-card__meta">
        <span
          className={`badge ${answer.confidence}`}
          data-testid="confidence-chip"
        >
          <Icon name={conf.icon} size={13} />
          {conf.label}
        </span>
        {hasFieldFix && (
          <span className="chip okC" data-testid="fieldfix-badge">
            <Icon name="check" size={12} />
            Field-verified fix
          </span>
        )}
      </div>

      {warnings.length > 0 && (
        <section className="safety safety-warnings" role="alert" aria-label="Safety warnings">
          <Icon name="alert" size={16} />
          <div>
            <h3 className="safety__heading">Safety</h3>
            <ul>
              {warnings.map((w, i) => (
                <li key={i}>{w}</li>
              ))}
            </ul>
          </div>
        </section>
      )}

      <div className="aHead aBody answer-card__body">
        {rest.map((line, i) => (
          <p key={i}>{line}</p>
        ))}
      </div>

      {answer.figures.length > 0 && (
        <div>
          {answer.figures.map((fig, i) => (
            <figure className="figBox" key={i}>
              <img src={fig.url} alt={fig.caption ?? `Figure on page ${fig.page}`} />
              {fig.caption && (
                <figcaption className="figCap">
                  <Icon name="image" size={11} />
                  <span>{fig.caption}</span>
                </figcaption>
              )}
            </figure>
          ))}
        </div>
      )}

      {answer.citations.length > 0 && (
        <footer className="citeRow">
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
