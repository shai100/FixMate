import { authHeaders } from "./auth";
import type {
  Answer,
  Conversation,
  Equipment,
  FeedbackResult,
} from "./types";

class ApiError extends Error {
  constructor(
    public status: number,
    public detail: string,
  ) {
    super(`API ${status}: ${detail}`);
    this.name = "ApiError";
  }
}

async function request<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(),
      ...(init.headers ?? {}),
    },
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : detail;
    } catch {
      // non-JSON error body; keep statusText
    }
    throw new ApiError(res.status, detail);
  }
  return (await res.json()) as T;
}

export const api = {
  listEquipment(): Promise<Equipment[]> {
    return request<Equipment[]>("/equipment");
  },

  createConversation(equipmentId: string | null): Promise<Conversation> {
    return request<Conversation>("/conversations", {
      method: "POST",
      body: JSON.stringify({ equipment_id: equipmentId }),
    });
  },

  ask(conversationId: string, question: string): Promise<Answer> {
    return request<Answer>(`/conversations/${conversationId}/ask`, {
      method: "POST",
      body: JSON.stringify({ question }),
    });
  },

  submitFeedback(
    messageId: string,
    helped: boolean,
    fixText?: string,
    photos?: string[],
  ): Promise<FeedbackResult> {
    return request<FeedbackResult>(`/messages/${messageId}/feedback`, {
      method: "POST",
      body: JSON.stringify({
        helped,
        fix_text: fixText ?? null,
        photos: photos ?? null,
      }),
    });
  },
};

export { ApiError };
