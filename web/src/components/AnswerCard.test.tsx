/**
 * Tests for <AnswerCard>'s safety-critical rendering rules.
 *
 * These verify the behaviors that matter for trust: safety warnings render first
 * (above the body), the confidence chip and field-fix badge show correctly, and
 * figures/citations appear. They render the component with React Testing Library
 * and assert against the resulting DOM. `makeAnswer` is a factory that builds a
 * valid `Answer` so each test only specifies the fields it cares about.
 */
import { render, screen, within } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { AnswerCard } from "./AnswerCard";
import type { Answer } from "../types";

/** Build a complete `Answer` for tests, overriding only the fields under test. */
function makeAnswer(overrides: Partial<Answer> = {}): Answer {
  return {
    message_id: "m1",
    answer_log_id: "l1",
    text: "Diagnosis: valve blocked.\nStep 1: depressurize the system.",
    confidence: "high",
    escalated: false,
    citations: [],
    figures: [],
    ...overrides,
  };
}

describe("AnswerCard", () => {
  it("renders safety warnings first, above the body", () => {
    const answer = makeAnswer({
      text: "Step 1: remove cover.\nWARNING: depressurize before opening.\nStep 2: replace seal.",
    });
    render(<AnswerCard answer={answer} />);

    const warningSection = screen.getByRole("alert", { name: /safety warnings/i });
    expect(within(warningSection).getByText(/depressurize before opening/i)).toBeInTheDocument();

    // The warnings section must appear before the body in DOM order.
    const card = screen.getByRole("article", { name: /answer/i });
    const warnings = card.querySelector(".safety-warnings");
    const body = card.querySelector(".answer-card__body");
    expect(warnings).not.toBeNull();
    expect(body).not.toBeNull();
    expect(warnings!.compareDocumentPosition(body!)).toBe(
      Node.DOCUMENT_POSITION_FOLLOWING,
    );
  });

  it("shows the field-fix badge only when a field_fix citation is present", () => {
    const withoutFix = makeAnswer({
      citations: [
        {
          chunk_id: "c1",
          document_id: "d1",
          document_title: "Pump Manual",
          page: 41,
          source_type: "manual",
        },
      ],
    });
    const { rerender } = render(<AnswerCard answer={withoutFix} />);
    expect(screen.queryByTestId("fieldfix-badge")).not.toBeInTheDocument();

    const withFix = makeAnswer({
      citations: [
        {
          chunk_id: "c2",
          document_id: null,
          document_title: null,
          page: null,
          source_type: "field_fix",
        },
      ],
    });
    rerender(<AnswerCard answer={withFix} />);
    expect(screen.getByTestId("fieldfix-badge")).toBeInTheDocument();
    expect(screen.getByTestId("citation-source-field_fix")).toBeInTheDocument();
  });

  it("renders the confidence chip with the right band", () => {
    render(<AnswerCard answer={makeAnswer({ confidence: "medium" })} />);
    expect(screen.getByTestId("confidence-chip")).toHaveTextContent(/medium confidence/i);
  });

  it("renders figures with accessible alt text", () => {
    const answer = makeAnswer({
      figures: [{ page: 41, caption: "Concentrate valve location", url: "/img/v.png" }],
    });
    render(<AnswerCard answer={answer} />);
    expect(screen.getByAltText(/concentrate valve location/i)).toBeInTheDocument();
  });
});
