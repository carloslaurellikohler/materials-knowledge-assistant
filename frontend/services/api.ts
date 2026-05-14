import { Citation } from "@/types/chat";
import { parseSseStream } from "@/services/sse";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

export type StreamHandlers = {
  onToken: (token: string) => void;
  onCitations: (citations: Citation[]) => void;
  onDone: () => void;
  onError: (message: string) => void;
};

export async function fetchDocuments(token: string): Promise<string[]> {
  const res = await fetch(`${API_URL}/documents`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) {
    throw new Error("Failed to load documents");
  }
  const data = (await res.json()) as Array<{ source: string }>;
  return data.map((item) => item.source);
}

export async function streamChat(
  token: string,
  message: string,
  metadata_filters: Record<string, string>,
  handlers: StreamHandlers,
): Promise<void> {
  const res = await fetch(`${API_URL}/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ message, attachments: [], metadata_filters }),
  });
  if (!res.ok || !res.body) {
    const body = await res.text().catch(() => "");
    throw new Error(`HTTP ${res.status}: ${body || "Unable to stream answer"}`);
  }

  for await (const event of parseSseStream(res.body)) {
    if (event.event === "token") handlers.onToken(event.data);
    if (event.event === "citations") handlers.onCitations(event.data);
    if (event.event === "done") handlers.onDone();
    if (event.event === "error") handlers.onError(event.data);
  }
}

export async function uploadAttachment(
  token: string,
  file: File,
  type: "image" | "audio",
): Promise<{ result: string }> {
  const endpoint = type === "image" ? "upload/image" : "upload/audio";
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(`${API_URL}/${endpoint}`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: formData,
  });
  if (!res.ok) throw new Error(`Failed to upload ${type} (HTTP ${res.status})`);
  const data = (await res.json()) as { description?: string; transcript?: string };
  return { result: data.description ?? data.transcript ?? "" };
}
