import { useState } from "react";
import { api, ApiError } from "../api";
import { FixSubmitForm } from "./FixSubmitForm";

type State = "idle" | "submitting" | "thanks" | "fix-form" | "fix-submitted";

// "Did it help?" (FR-13). Yes → positive signal. No → opens the candidate-fix
// form (FR-12), which submits a fix that enters the curation queue.
export function FeedbackBar({ messageId }: { messageId: string }) {
  const [state, setState] = useState<State>("idle");
  const [error, setError] = useState<string | null>(null);

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
    return <p className="feedback-bar feedback-bar--done">Thanks for the feedback.</p>;
  }
  if (state === "fix-submitted") {
    return (
      <p className="feedback-bar feedback-bar--done">
        Fix submitted for review. A curator will verify it before it reaches other technicians.
      </p>
    );
  }
  if (state === "fix-form") {
    return (
      <div className="feedback-bar">
        {error && <p className="feedback-bar__error">{error}</p>}
        <FixSubmitForm
          submitting={false}
          onSubmit={submitFix}
          onCancel={() => setState("idle")}
        />
      </div>
    );
  }

  return (
    <div className="feedback-bar">
      {error && <p className="feedback-bar__error">{error}</p>}
      <span>Did it help?</span>
      <button
        type="button"
        onClick={() => sayHelped(true)}
        disabled={state === "submitting"}
      >
        Yes
      </button>
      <button
        type="button"
        onClick={() => sayHelped(false)}
        disabled={state === "submitting"}
      >
        No
      </button>
    </div>
  );
}
