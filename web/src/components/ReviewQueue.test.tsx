/**
 * Tests for <ReviewQueue> (the curation queue list).
 *
 * They verify the count badge, that selecting an item opens its detail view, and
 * the empty state. The `api` module is mocked so the queue's load-on-mount call
 * returns controlled data.
 */
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { ReviewQueue } from "./ReviewQueue";
import type { ReviewItem } from "../types";

const reviewQueue = vi.fn();
vi.mock("../api", () => ({
  api: {
    reviewQueue: (...a: unknown[]) => reviewQueue(...a),
    approveFix: vi.fn(),
    rejectFix: vi.fn(),
    flagUnsafe: vi.fn(),
  },
  ApiError: class ApiError extends Error {},
}));

function item(overrides: Partial<ReviewItem> = {}): ReviewItem {
  return {
    fix_id: "f1",
    state: "pending_review",
    question: "Pump throws E47 on startup",
    original_answer: "Check the concentrate valve.",
    proposed_text: "Clear the blockage in the concentrate valve, then reset.",
    submitted_by: "u1",
    equipment_id: "e1",
    manual_chunks: [{ chunk_id: "c1", page: 41, text: "Valve service section.", score: 0.8 }],
    prescreen: { overall_risk: "low", hazard_flags: [] },
    created_at: "2026-06-16T00:00:00Z",
    ...overrides,
  };
}

describe("ReviewQueue", () => {
  beforeEach(() => vi.clearAllMocks());

  it("shows the pending count as a badge", async () => {
    reviewQueue.mockResolvedValue([item(), item({ fix_id: "f2" })]);
    render(<ReviewQueue />);
    await waitFor(() => expect(screen.getByTestId("queue-badge")).toHaveTextContent("2"));
  });

  it("opens the detail view when an item is clicked", async () => {
    reviewQueue.mockResolvedValue([item()]);
    render(<ReviewQueue />);
    const row = await screen.findByText(/pump throws e47/i);
    await userEvent.click(row);
    expect(screen.getByRole("region", { name: /review fix/i })).toBeInTheDocument();
  });

  it("renders an empty-state when nothing is pending", async () => {
    reviewQueue.mockResolvedValue([]);
    render(<ReviewQueue />);
    await waitFor(() => expect(screen.getByTestId("queue-badge")).toHaveTextContent("0"));
    expect(screen.getByText(/nothing awaiting review/i)).toBeInTheDocument();
  });
});
