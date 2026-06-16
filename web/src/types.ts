// Mirrors fixmate/api/schemas.py (Phase 6/7). Keep these in lockstep with the
// API payloads — Appendix A.7: citation markers and source_type drive the UI.

export type Confidence = "high" | "medium" | "low";

export type SourceType = "manual" | "field_fix";

export interface Equipment {
  id: string;
  name: string;
  manufacturer: string | null;
  model: string | null;
  created_at: string;
}

export interface Citation {
  chunk_id: string;
  document_id: string | null;
  document_title: string | null;
  page: number | null;
  source_type: SourceType;
}

export interface Figure {
  page: number;
  caption: string | null;
  url: string;
}

export interface Answer {
  message_id: string;
  answer_log_id: string;
  text: string;
  confidence: Confidence;
  escalated: boolean;
  citations: Citation[];
  figures: Figure[];
}

export interface Conversation {
  id: string;
  equipment_id: string | null;
  created_at: string;
  messages: MessageOut[];
}

export interface MessageOut {
  id: string;
  role: "user" | "assistant";
  content: string;
  answer_log_id: string | null;
  created_at: string;
}

export interface FeedbackResult {
  feedback_id: string;
  helped: boolean;
  fix_id: string | null;
}

// --- Curator / Admin console (Phase 11) ---

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

export interface DocumentRow {
  id: string;
  equipment_id: string;
  title: string;
  version: number;
  superseded_by: string | null;
  created_at: string;
}

export type Role = "tech" | "curator" | "admin";

export interface UserRow {
  id: string;
  name: string;
  email: string | null;
  role: Role;
  created_at: string;
}

export interface DevIdentityResponse {
  org_id: string;
  user_id: string;
  role: Role;
}

// A fix in any lifecycle state, for the console's "all items" table.
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

export interface UploadAccepted {
  task_id: string;
  status: string;
}
