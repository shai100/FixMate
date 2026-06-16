import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { ReviewDetail } from "./ReviewDetail";
import type { ReviewItem } from "../types";

const approveFix = vi.fn().mockResolvedValue(undefined);
const rejectFix = vi.fn().mockResolvedValue(undefined);
const flagUnsafe = vi.fn().mockResolvedValue(undefined);
vi.mock("../api", () => ({
  api: {
    approveFix: (...a: unknown[]) => approveFix(...a),
    rejectFix: (...a: unknown[]) => rejectFix(...a),
    flagUnsafe: (...a: unknown[]) => flagUnsafe(...a),
  },
  ApiError: class ApiError extends Error {},
}));

function item(overrides: Partial<ReviewItem> = {}): ReviewItem {
  return {
    fix_id: "f1",
    state: "pending_review",
    question: "Pump throws E47",
    original_answer: "Check the valve.",
    proposed_text: "Clear the concentrate valve blockage.",
    submitted_by: "u1",
    equipment_id: "e1",
    manual_chunks: [{ chunk_id: "c1", page: 41, text: "Valve section.", score: 0.8 }],
    prescreen: {
      overall_risk: "high",
      hazard_flags: ["pressure"],
      contradictions: [],
      missing_safety_steps: ["depressurize first"],
    },
    created_at: "2026-06-16T00:00:00Z",
    ...overrides,
  };
}

describe("ReviewDetail", () => {
  beforeEach(() => vi.clearAllMocks());

  it("renders the pre-screen advisory with hazard flags and the advisory-only note", () => {
    render(<ReviewDetail item={item()} onResolved={() => {}} onBack={() => {}} />);
    const prescreen = screen.getByTestId("prescreen");
    expect(prescreen).toHaveTextContent(/pressure/i);
    expect(prescreen).toHaveTextContent(/depressurize first/i);
    expect(screen.getByTestId("prescreen-risk")).toHaveTextContent(/high/i);
    // The pre-screen advises; it never decides (CLAUDE.md §2.5).
    expect(prescreen).toHaveTextContent(/advisory only/i);
  });

  it("approves without edited_text when the proposed text is unchanged", async () => {
    render(<ReviewDetail item={item()} onResolved={() => {}} onBack={() => {}} />);
    await userEvent.click(screen.getByRole("button", { name: /^approve$/i }));
    expect(approveFix).toHaveBeenCalledWith("f1", undefined);
  });

  it("sends edited text and labels the button Edit & Approve after an edit", async () => {
    render(<ReviewDetail item={item()} onResolved={() => {}} onBack={() => {}} />);
    const textarea = screen.getByLabelText(/proposed fix text/i);
    await userEvent.clear(textarea);
    await userEvent.type(textarea, "Clear the valve AND replace the seal.");
    expect(screen.getByTestId("edited-flag")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /edit & approve/i }));
    expect(approveFix).toHaveBeenCalledWith("f1", "Clear the valve AND replace the seal.");
  });

  it("blocks reject until a reason is given, then submits it", async () => {
    render(<ReviewDetail item={item()} onResolved={() => {}} onBack={() => {}} />);
    await userEvent.click(screen.getByRole("button", { name: /reject/i }));
    expect(rejectFix).not.toHaveBeenCalled();
    expect(screen.getByText(/reason is required/i)).toBeInTheDocument();

    await userEvent.type(screen.getByLabelText(/reason/i), "duplicate of existing fix");
    await userEvent.click(screen.getByRole("button", { name: /reject/i }));
    expect(rejectFix).toHaveBeenCalledWith("f1", "duplicate of existing fix");
  });

  it("shows a manual-review note when the pre-screen failed (never blocks)", () => {
    render(
      <ReviewDetail
        item={item({ prescreen: { error: "prescreen_failed" } })}
        onResolved={() => {}}
        onBack={() => {}}
      />,
    );
    expect(screen.getByTestId("prescreen")).toHaveTextContent(/could not run/i);
    // Approve is still available — a failed pre-screen advises, it does not gate.
    expect(screen.getByRole("button", { name: /^approve$/i })).toBeEnabled();
  });
});
