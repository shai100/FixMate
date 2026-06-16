/**
 * The single HTTP client for talking to the FixMate backend.
 *
 * Every screen calls methods on the exported `api` object rather than using
 * `fetch` directly, so request shaping, auth headers, and error handling live in
 * one place. Two private helpers do the heavy lifting: `request<T>` for endpoints
 * that return JSON, and `requestVoid` for 204-No-Content endpoints (the curation
 * actions). Both attach the dev-auth headers and convert any non-2xx response
 * into a typed `ApiError` the UI can display. The methods are grouped by feature
 * (chat, curation, equipment/document/fix/user admin) and each mirrors one
 * backend route.
 */
import { authHeaders } from "./auth";
import type {
  Answer,
  Conversation,
  DevIdentityResponse,
  DocumentRow,
  Equipment,
  FeedbackResult,
  FixSummary,
  ReviewItem,
  UploadAccepted,
  UserRow,
} from "./types";

/** Error thrown for any non-2xx API response; carries the HTTP status and the
 *  server's detail message so callers can branch on `status` or show `detail`. */
class ApiError extends Error {
  constructor(
    public status: number,
    public detail: string,
  ) {
    super(`API ${status}: ${detail}`);
    this.name = "ApiError";
  }
}

/** Make a request and parse the JSON response as type `T`, throwing `ApiError`
 *  on failure. Auto-sets the JSON content type unless the body is FormData. */
async function request<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  // FormData sets its own multipart Content-Type (with boundary); forcing JSON
  // here would corrupt uploads, so only default the header for non-FormData bodies.
  const isForm = init.body instanceof FormData;
  const res = await fetch(path, {
    ...init,
    headers: {
      ...(isForm ? {} : { "Content-Type": "application/json" }),
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

/** Like `request`, but for endpoints that return 204 No Content (no body to
 *  parse). Same auth + error handling. */
async function requestVoid(path: string, init: RequestInit = {}): Promise<void> {
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
      // no body
    }
    throw new ApiError(res.status, detail);
  }
}

/** The backend API surface, one method per endpoint. Import this object and call
 *  e.g. `api.ask(convId, question)`; each method returns a typed Promise. */
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

  // --- Curation (curator/admin) ---

  reviewQueue(): Promise<ReviewItem[]> {
    return request<ReviewItem[]>("/curation/queue");
  },

  approveFix(fixId: string, editedText?: string): Promise<void> {
    return requestVoid(`/fixes/${fixId}/approve`, {
      method: "POST",
      body: JSON.stringify({ edited_text: editedText ?? null }),
    });
  },

  rejectFix(fixId: string, reason: string): Promise<void> {
    return requestVoid(`/fixes/${fixId}/reject`, {
      method: "POST",
      body: JSON.stringify({ reason }),
    });
  },

  flagUnsafe(fixId: string, reason: string): Promise<void> {
    return requestVoid(`/fixes/${fixId}/unsafe`, {
      method: "POST",
      body: JSON.stringify({ reason }),
    });
  },

  retireFix(fixId: string, reason: string): Promise<void> {
    return requestVoid(`/fixes/${fixId}/retire`, {
      method: "POST",
      body: JSON.stringify({ reason }),
    });
  },

  // --- Equipment admin ---

  createEquipment(body: {
    name: string;
    manufacturer?: string | null;
    model?: string | null;
  }): Promise<Equipment> {
    return request<Equipment>("/equipment", {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  updateEquipment(
    equipmentId: string,
    body: { name?: string; manufacturer?: string | null; model?: string | null },
  ): Promise<Equipment> {
    return request<Equipment>(`/equipment/${equipmentId}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    });
  },

  deleteEquipment(equipmentId: string): Promise<void> {
    return requestVoid(`/equipment/${equipmentId}`, { method: "DELETE" });
  },

  // --- Documents admin ---

  listDocuments(equipmentId?: string): Promise<DocumentRow[]> {
    const q = equipmentId ? `?equipment_id=${encodeURIComponent(equipmentId)}` : "";
    return request<DocumentRow[]>(`/documents${q}`);
  },

  updateDocument(documentId: string, body: { title: string }): Promise<DocumentRow> {
    return request<DocumentRow>(`/documents/${documentId}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    });
  },

  deleteDocument(documentId: string): Promise<void> {
    return requestVoid(`/documents/${documentId}`, { method: "DELETE" });
  },

  uploadDocument(
    file: File,
    equipmentId: string,
    title?: string,
  ): Promise<UploadAccepted> {
    const form = new FormData();
    form.append("file", file);
    form.append("equipment_id", equipmentId);
    if (title) form.append("title", title);
    return request<UploadAccepted>("/documents/upload", {
      method: "POST",
      body: form,
    });
  },

  // --- Fixes admin (curator/admin): list all, create, edit, delete ---

  listFixes(state?: string): Promise<FixSummary[]> {
    const q = state ? `?state=${encodeURIComponent(state)}` : "";
    return request<FixSummary[]>(`/curation/fixes${q}`);
  },

  createFix(body: {
    equipment_id: string;
    proposed_text: string;
    question?: string | null;
  }): Promise<{ fix_id: string }> {
    return request<{ fix_id: string }>("/fixes", {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  updateFix(
    fixId: string,
    body: { proposed_text?: string | null; question?: string | null },
  ): Promise<void> {
    return requestVoid(`/fixes/${fixId}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    });
  },

  deleteFix(fixId: string): Promise<void> {
    return requestVoid(`/fixes/${fixId}`, { method: "DELETE" });
  },

  // --- Users admin ---

  listUsers(): Promise<UserRow[]> {
    return request<UserRow[]>("/admin/users");
  },

  setUserRole(userId: string, role: UserRow["role"]): Promise<UserRow> {
    return request<UserRow>(`/admin/users/${userId}/role`, {
      method: "POST",
      body: JSON.stringify({ role }),
    });
  },

  createUser(body: {
    name: string;
    email?: string | null;
    role: UserRow["role"];
  }): Promise<UserRow> {
    return request<UserRow>("/admin/users", {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  updateUser(
    userId: string,
    body: { name?: string; email?: string | null; role?: UserRow["role"] },
  ): Promise<UserRow> {
    return request<UserRow>(`/admin/users/${userId}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    });
  },

  deleteUser(userId: string): Promise<void> {
    return requestVoid(`/admin/users/${userId}`, { method: "DELETE" });
  },

  // --- Dev auto-login (local only) ---

  devAutoLogin(): Promise<DevIdentityResponse> {
    return request<DevIdentityResponse>("/dev/auto-login");
  },
};

export { ApiError };
