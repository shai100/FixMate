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
