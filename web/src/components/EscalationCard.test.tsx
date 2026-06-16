/**
 * Tests for <EscalationCard> (the low-confidence "I don't know" path, FR-4).
 *
 * They verify the card shows the honest message, lists the nearest sections, and
 * fires the escalate callback when the button is clicked.
 */
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import { EscalationCard } from "./EscalationCard";
import type { Answer } from "../types";

const escalated: Answer = {
  message_id: "m1",
  answer_log_id: "l1",
  text: "I'm not confident enough to answer this safely.",
  confidence: "low",
  escalated: true,
  citations: [
    {
      chunk_id: "c1",
      document_id: "d1",
      document_title: "Pump Manual",
      page: 12,
      source_type: "manual",
    },
  ],
  figures: [],
};

describe("EscalationCard", () => {
  it("shows the don't-know body and an escalate action", async () => {
    const onEscalate = vi.fn();
    render(<EscalationCard answer={escalated} onEscalate={onEscalate} />);

    expect(
      screen.getByRole("heading", { name: /not confident enough to answer/i }),
    ).toBeInTheDocument();
    expect(screen.getByText(/answer this safely/i)).toBeInTheDocument();
    expect(screen.getByText(/Pump Manual, p\.12/)).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /escalate/i }));
    expect(onEscalate).toHaveBeenCalledOnce();
  });
});
