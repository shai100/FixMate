import { useEffect, useRef, useState } from "react";
import { api, ApiError } from "../api";
import type { Answer, Equipment } from "../types";
import { AnswerCard } from "./AnswerCard";
import { EscalationCard } from "./EscalationCard";
import { FeedbackBar } from "./FeedbackBar";

interface Turn {
  question: string;
  answer: Answer | null; // null while in flight
}

export function ChatView({ equipment }: { equipment: Equipment | null }) {
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

  async function ask() {
    const q = question.trim();
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

  return (
    <div className="chat-view">
      <header className="chat-view__header">
        <h1>FixMate</h1>
        <span className="chat-view__equipment">
          {equipment ? equipment.name : "General"}
        </span>
      </header>

      <div className="chat-view__transcript">
        {turns.map((turn, i) => (
          <div key={i} className="chat-turn">
            <p className="chat-turn__question">{turn.question}</p>
            {turn.answer === null ? (
              <p className="chat-turn__thinking">Thinking…</p>
            ) : turn.answer.escalated ? (
              <EscalationCard answer={turn.answer} />
            ) : (
              <AnswerCard answer={turn.answer}>
                <FeedbackBar messageId={turn.answer.message_id} />
              </AnswerCard>
            )}
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {error && <p className="chat-view__error">{error}</p>}

      <form
        className="chat-view__composer"
        onSubmit={(e) => {
          e.preventDefault();
          ask();
        }}
      >
        <label htmlFor="question" className="visually-hidden">
          Your question
        </label>
        <input
          id="question"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Describe the problem or error code…"
          disabled={!conversationId || pending}
        />
        <button type="submit" disabled={!conversationId || pending || !question.trim()}>
          Ask
        </button>
      </form>
    </div>
  );
}
