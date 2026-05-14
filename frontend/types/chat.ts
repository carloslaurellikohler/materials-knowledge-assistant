export type Citation = {
  source: string;
  chapter?: string | null;
  section?: string | null;
  page?: number | null;
  excerpt: string;
};

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  text: string;
  citations?: Citation[];
  createdAt: number;
  status?: "streaming" | "done" | "error";
};

export type UploadItem = {
  id: string;
  filename: string;
  type: "image" | "audio";
  status: "queued" | "uploading" | "processing" | "success" | "error";
  error?: string;
};

export type SseEvent =
  | { event: "token"; data: string }
  | { event: "citations"; data: Citation[] }
  | { event: "done"; data: string }
  | { event: "error"; data: string };

