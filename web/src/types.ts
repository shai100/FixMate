/**
 * TypeScript shapes for the data the API returns — the frontend's copy of the
 * backend contract.
 *
 * Each interface here mirrors a Pydantic model in `fixmate/api/schemas.py`; keep
 * the two in lockstep so the compiler catches drift between client and server.
 * These types are what make the rest of the app type-safe: components receive
 * `Answer`, `ReviewItem`, etc. and the compiler verifies every field access.
 */

/** How sure the system is about an answer; drives the confidence badge and the
 *  low-confidence escalation path. */
export type Confidence = "high" | "medium" | "low";

/** Where a cited chunk came from: a manual page or a human-approved field fix. */
export type SourceType = "manual" | "field_fix";

/** A piece of equipment the technician troubleshoots. */
export interface Equipment {
  id: string;
  name: string;
  manufacturer: string | null;
  model: string | null;
  created_at: string;
}

/** A source backing a claim in an answer (rendered as a clickable citation). */
export interface Citation {
  chunk_id: string;
  document_id: string | null;
  document_title: string | null;
  page: number | null;
  source_type: SourceType;
}

/** An image shown with an answer; `url` is a short-lived signed link. */
export interface Figure {
  page: number;
  caption: string | null;
  url: string;
}

/** The full result of asking a question (mirrors `AnswerOut`). When `escalated`
 *  is true the UI shows the escalation card instead of a normal answer. */
export interface Answer {
  message_id: string;
  answer_log_id: string;
  text: string;
  confidence: Confidence;
  escalated: boolean;
  citations: Citation[];
  figures: Figure[];
}

/** A Q&A session and its messages. */
export interface Conversation {
  id: string;
  equipment_id: string | null;
  created_at: string;
  messages: MessageOut[];
}

/** One turn in a conversation (user question or assistant reply). */
export interface MessageOut {
  id: string;
  role: "user" | "assistant";
  content: string;
  answer_log_id: string | null;
  created_at: string;
}

/** Result of submitting feedback; `fix_id` is set if a candidate fix was opened. */
export interface FeedbackResult {
  feedback_id: string;
  helped: boolean;
  fix_id: string | null;
}

// --- Curator / Admin console (Phase 11) ---

/** A manual excerpt shown to a curator as review evidence, with its relevance score. */
export interface ManualChunk {
  chunk_id: string;
  page: number | null;
  text: string;
  score: number;
}

// AI pre-screen advisory (FR-15). It informs the human; it never decides.
export interface Prescreen {
  hazard_flags?: string[];
  contradictions?: string[];
  missing_safety_steps?: string[];
  overall_risk?: "low" | "medium" | "high";
  error?: string;
}

/** A fix in the review queue, bundled with the evidence a curator needs. */
export interface ReviewItem {
  fix_id: string;
  state: string;
  question: string | null;
  original_answer: string | null;
  proposed_text: string;
  submitted_by: string;
  equipment_id: string;
  manual_chunks: ManualChunk[];
  prescreen: Prescreen | null;
  created_at: string;
}

/** A manual row for the documents admin table; `superseded_by` marks old versions. */
export interface DocumentRow {
  id: string;
  equipment_id: string;
  title: string;
  version: number;
  superseded_by: string | null;
  created_at: string;
}

/** A user's permission level. */
export type Role = "tech" | "curator" | "admin";

/** A user row for the admin users table. */
export interface UserRow {
  id: string;
  name: string;
  email: string | null;
  role: Role;
  created_at: string;
}

/** The identity returned by the local dev auto-login endpoint. */
export interface DevIdentityResponse {
  org_id: string;
  user_id: string;
  role: Role;
}

/** A fix in any lifecycle state, with submitter/reviewer names, for the admin table. */
export interface FixSummary {
  fix_id: string;
  state: string;
  question: string | null;
  proposed_text: string;
  equipment_id: string;
  submitted_by: string;
  submitted_by_name: string | null;
  reviewed_by: string | null;
  reviewed_by_name: string | null;
  review_notes: string | null;
  approved_at: string | null;
  created_at: string;
  updated_at: string;
}

/** Returned when a document upload is queued; `task_id` polls ingestion progress. */
export interface UploadAccepted {
  task_id: string;
  status: string;
}
