/**
 * The chat screen — the main Q&A interface for technicians.
 *
 * On mount it creates a conversation scoped to the chosen equipment. Asking a
 * question optimistically appends a "turn" (the question with a null answer,
 * shown as a typing indicator), calls the API, then fills in the answer — or
 * removes the turn and shows an error if the call fails. Each answered turn
 * renders either an <EscalationCard> (when the system declined to answer) or an
 * <AnswerCard> with a <FeedbackBar>. Auto-scrolls to the newest turn.
 */
import { useEffect, useRef, useState } from "react";
import { api, ApiError } from "../api";
import type { Answer, Equipment } from "../types";
import { AnswerCard } from "./AnswerCard";
import { EscalationCard } from "./EscalationCard";
import { FeedbackBar } from "./FeedbackBar";
import { Icon } from "./Icon";

/** One question and its answer; ``answer`` is null while the request is in flight. */
interface Turn {
  question: string;
  answer: Answer | null; // null while in flight
}

export function ChatView({
  equipment,
  onBack,
}: {
  equipment: Equipment | null;
  onBack: () => void;
}) {
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [question, setQuestion] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api
      .createConversation(equipment?.id ?? null)
      .then((c) => setConversationId(c.id))
      .catch((e) =>
        setError(e instanceof ApiError ? e.detail : "Could not start conversation"),
      );
  }, [equipment]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns]);

  // Send a question: optimistically show it, await the answer, then fill it in
  // (or roll back the turn and surface an error on failure).
  async function ask(text: string) {
    const q = text.trim();
    if (!q || !conversationId || pending) return;
    setQuestion("");
    setError(null);
    setPending(true);
    setTurns((prev) => [...prev, { question: q, answer: null }]);
    try {
      const answer = await api.ask(conversationId, q);
      setTurns((prev) => {
        const next = [...prev];
        next[next.length - 1] = { question: q, answer };
        return next;
      });
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : "Something went wrong");
      setTurns((prev) => prev.slice(0, -1));
    } finally {
      setPending(false);
    }
  }

  const hasText = question.trim().length > 0;
  const started = turns.length > 0;

  return (
    <div className="screen anim-fwd">
      <div className="hd">
        <button className="iconBtn" onClick={onBack} aria-label="Back">
          <Icon name="back" size={22} />
        </button>
        <div className="eqIc" style={{ width: 36, height: 36, fontSize: "1.05rem" }}>
          <Icon name="wrench" size={18} />
        </div>
        <div style={{ minWidth: 0 }}>
          <div
            className="hdTitle ltr"
            style={{ whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}
          >
            {equipment ? equipment.name : "General"}
          </div>
          <div className="hdSub">
            {equipment
              ? [equipment.manufacturer, equipment.model].filter(Boolean).join(" · ") || "Equipment"
              : "No specific equipment"}
          </div>
        </div>
      </div>

      <div className="chatLog" aria-live="polite">
        <div className="dayDiv">Today</div>

        {!started && (
          <>
            <div className="chatHello">
              <div className="chIc">
                <Icon name="wrench" size={26} />
              </div>
              <div className="chT">Ask about this unit</div>
              <div className="chS">
                Answers are grounded in the service manuals and your team's approved fixes.
              </div>
            </div>
            <div className="suggRow">
              {SUGGESTIONS.map((s) => (
                <button key={s} className="suggChip" onClick={() => ask(s)}>
                  {s}
                </button>
              ))}
            </div>
          </>
        )}

        {turns.map((turn, i) => (
          <div key={i} className="chat-turn">
            <div className="uMsg reveal">{turn.question}</div>
            {turn.answer === null ? (
              <div className="typing">
                <i />
                <i />
                <i />
              </div>
            ) : turn.answer.escalated ? (
              <div className="aMsg reveal">
                <EscalationCard answer={turn.answer} />
              </div>
            ) : (
              <div className="aMsg reveal">
                <AnswerCard answer={turn.answer}>
                  <FeedbackBar messageId={turn.answer.message_id} />
                </AnswerCard>
              </div>
            )}
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {error && <p className="chatError">{error}</p>}

      <form
        className="composer"
        onSubmit={(e) => {
          e.preventDefault();
          ask(question);
        }}
      >
        <label htmlFor="question" className="visually-hidden">
          Your question
        </label>
        <input
          id="question"
          className="inp"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Describe the issue…"
          autoComplete="off"
          disabled={!conversationId || pending}
        />
        <button
          type="submit"
          className="compBtn prime"
          aria-label="Send"
          disabled={!conversationId || pending || !hasText}
        >
          <Icon name={hasText ? "send" : "mic"} size={19} />
        </button>
      </form>
    </div>
  );
}

// Static starter prompts (UI affordance only; the real answer comes from the API).
const SUGGESTIONS = [
  "What does this error code mean?",
  "Output dropped — where do I start?",
  "There's a leak at the housing",
];
