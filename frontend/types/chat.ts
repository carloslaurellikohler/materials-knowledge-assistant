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
  result?: string;
};

export type DocumentStatus =
  | "pending"
  | "processing"
  | "chunking"
  | "embedding"
  | "indexed"
  | "error";

export type UserDocument = {
  id: string;
  filename: string;
  original_filename: string;
  size: number;
  indexing_status: DocumentStatus;
  indexing_error?: string | null;
  chunk_count?: number | null;
  embedding_model?: string | null;
  qdrant_collection: string;
  created_at: string;
};

export type SseEvent =
  | { event: "token"; data: string }
  | { event: "citations"; data: Citation[] }
  | { event: "done"; data: string }
  | { event: "error"; data: string };
