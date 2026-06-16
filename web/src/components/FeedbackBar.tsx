/**
 * The "Did it help?" bar under each answer (FR-12/FR-13).
 *
 * It's a small state machine. From `idle`: tapping Yes records a positive signal
 * and shows a thank-you; tapping No opens the <FixSubmitForm> so the technician
 * can propose a better fix, which is submitted to the curation queue. The
 * `State` type enumerates every screen the bar can be in (idle, submitting, the
 * two done states, and the fix form), which keeps the render logic a simple
 * switch on the current state.
 */
import { useState } from "react";
import { api, ApiError } from "../api";
import { FixSubmitForm } from "./FixSubmitForm";
import { Icon } from "./Icon";

/** The feedback bar's possible UI states. */
type State = "idle" | "submitting" | "thanks" | "fix-form" | "fix-submitted";

export function FeedbackBar({ messageId }: { messageId: string }) {
  const [state, setState] = useState<State>("idle");
  const [error, setError] = useState<string | null>(null);

  // Handle the Yes/No tap: No opens the fix form; Yes records a positive signal.
  async function sayHelped(helped: boolean) {
    setError(null);
    if (!helped) {
      setState("fix-form");
      return;
    }
    setState("submitting");
    try {
      await api.submitFeedback(messageId, true);
      setState("thanks");
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : "Could not send feedback");
      setState("idle");
    }
  }

  // Submit a proposed fix (the "No" path) to the feedback endpoint for review.
  async function submitFix(fixText: string, photos: string[]) {
    setState("submitting");
    setError(null);
    try {
      await api.submitFeedback(messageId, false, fixText, photos);
      setState("fix-submitted");
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : "Could not submit fix");
      setState("fix-form");
    }
  }

  if (state === "thanks") {
    return (
      <p className="fbRow fbDone">
        <Icon name="check" size={14} /> Logged as helpful — thanks!
      </p>
    );
  }
  if (state === "fix-submitted") {
    return (
      <p className="fbRow fbDone">
        <Icon name="check" size={14} /> Fix submitted for review. A curator verifies it
        before other technicians see it.
      </p>
    );
  }
  if (state === "fix-form") {
    return (
      <div className="fbRow" style={{ flexDirection: "column", alignItems: "stretch" }}>
        {error && <p className="fbError">{error}</p>}
        <FixSubmitForm
          submitting={false}
          onSubmit={submitFix}
          onCancel={() => setState("idle")}
        />
      </div>
    );
  }

  return (
    <div className="fbRow">
      {error && <p className="fbError">{error}</p>}
      <b>Did it help?</b>
      <button
        type="button"
        className="fbBtn fbYes"
        onClick={() => sayHelped(true)}
        disabled={state === "submitting"}
      >
        <Icon name="thumbsUp" size={13} /> Yes
      </button>
      <button
        type="button"
        className="fbBtn fbNo"
        onClick={() => sayHelped(false)}
        disabled={state === "submitting"}
      >
        <Icon name="thumbsDown" size={13} /> No
      </button>
    </div>
  );
}
